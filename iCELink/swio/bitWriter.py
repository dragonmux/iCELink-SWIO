# SPDX-License-Identifier: BSD-3-Clause
from torii import Elaboratable, Module, Signal
from torii.build.plat import Platform
from torii.lib.io import Pin

__all__ = (
	'SWIOBitWriter',
)

class SWIOBitWriter(Elaboratable):
	def __init__(self, swio: Pin):
		super().__init__()

		self.bit = Signal()
		self.ready = Signal()
		self.start = Signal()
		self.stop = Signal()
		self.finish = Signal()

		self._swio = swio

	def elaborate(self, platform: Platform) -> Module:
		m = Module()
		# SWIO GPIO
		swio = self._swio
		# 8MHz timer for counting out bits
		baseFrequency = int(platform.default_clk_frequency // 1e6) # 12MHz
		bitFrequency = 8 # MHz
		bitTimer = Signal(range(baseFrequency + bitFrequency))
		# We use normal mode clocking here - bits are defined by an 8MHz clock frequency
		# A '1' is given by a space time of 1-4 periods, and a mark time of 1-16
		# A '0' is given by a space time of 6-64 periods, and a mark time of 1-16
		# The bus idles high, hence space-then-mark. Provide enough range for the longest '0' period
		bitPeriod = Signal(range(64))

		# 1kHz timer for counting delays
		delayDuration = int(platform.default_clk_frequency // 1e3)
		delayTimer = Signal(range(delayDuration), reset = delayDuration - 1)
		# Delay to go in miliseconds
		delay = Signal(range(20))

		# Simple delay block - feed in the delay amount in delay and this will run till that becomes zero
		with m.If(delay != 0):
			with m.If(delayTimer == 0):
				m.d.sync += [
					delayTimer.eq(delayTimer.reset),
					delay.dec(),
				]
			with m.Else():
				m.d.sync += delayTimer.dec()

		# Simple delay block - feed in the delay amount in bitPeriod and this will run till that becomes zero
		with m.If(bitPeriod != 0):
			# This logic is taken from libAudio's emulator clock manager to allow
			# the correct handling of the frequency beating for two close values
			m.d.sync += bitTimer.eq(bitTimer + bitFrequency)
			with m.If(baseFrequency - bitTimer < bitFrequency):
				m.d.sync += [
					bitTimer.eq(bitTimer - baseFrequency),
					bitPeriod.dec(),
				]

		with m.FSM(name = 'bit'):
			with m.State('RESET'):
				# Start by outputting a 1 for 5ms
				m.d.sync += [
					swio.o.eq(1),
					swio.oe.eq(1),
					delay.eq(5),
				]
				m.next = 'WAIT_FIRST_DELAY'
			with m.State('WAIT_FIRST_DELAY'):
				with m.If(delay == 0):
					# Then output a 0 for 20ms
					m.d.sync += [
						swio.o.eq(0),
						delay.eq(20),
					]
					m.next = 'WAIT_SECOND_DELAY'
			with m.State('WAIT_SECOND_DELAY'):
				with m.If(delay == 0):
					# Now idle swio as an input
					m.d.sync += [
						swio.oe.eq(0),
						self.ready.eq(1),
					]
					m.next = 'IDLE'
			with m.State('IDLE'):
				# If we need to start transmitting a bit
				with m.If(self.start):
					m.next = 'SETUP'
				with m.Elif(self.stop):
					m.next = 'STOP'
			with m.State('SETUP'):
				# Load the bit period counter according to the value of the bit to send
				with m.If(self.bit):
					# Use 2T for '1'
					m.d.sync += bitPeriod.eq(2)
				with m.Else():
					# Use 8T for '0'
					m.d.sync += bitPeriod.eq(8)
				# Set SWIO as an output (we maintain it low on swio.o)
				m.d.sync += swio.oe.eq(1)
				m.next = 'WAIT_SPACE'
			with m.State('WAIT_SPACE'):
				# Wait for the bit period to reach 0
				with m.If(bitPeriod == 0):
					# Now load the mark bit period up and make SWIO high
					m.d.sync += [
						# Use 4T
						bitPeriod.eq(4),
						swio.oe.eq(0),
					]
					m.next = 'WAIT_MARK'
			with m.State('WAIT_MARK'):
				# Wait for the bit period to reach 0
				with m.If(bitPeriod == 0):
					# Signal that the bit is complete
					m.d.comb += self.finish.eq(1)
					m.next = 'IDLE'
			with m.State('STOP'):
				# Set up to run a stop bit (20T bus idle)
				m.d.sync += bitPeriod.eq(20)
				m.next = 'WAIT_STOP'
			with m.State('WAIT_STOP'):
				# Wait for the bit period to reach 0
				with m.If(bitPeriod == 0):
					# Signal that the bit is complete
					m.d.comb += self.finish.eq(1)
					m.next = 'IDLE'

		return m
