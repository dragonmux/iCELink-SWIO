# SPDX-License-Identifier: BSD-3-Clause
from torii import Elaboratable, Module, Signal
from torii.build.plat import Platform
from torii.lib.io import Pin
from enum import IntEnum, auto, unique

__all__ = (
	'SWIO',
)

@unique
class Operation(IntEnum):
	read = auto()
	write = auto()

class SWIO(Elaboratable):
	def __init__(self, swio: Pin):
		super().__init__()

		self.reg = Signal(8)
		self.dataRead = Signal(32)
		self.dataWrite = Signal(32)
		self.startRead = Signal()
		self.startWrite = Signal()
		self.ready = Signal()
		self.done = Signal()

		self._swio = swio

	def elaborate(self, platform: Platform) -> Module:
		m = Module()
		# SWIO GPIO
		swio = self._swio
		# The operation to perform on the register requested
		operation = Signal(Operation)
		# 8MHz timer for counting out bits
		bitDuration = int(platform.default_clk_frequency // 8e6)
		bitTimer = Signal(range(bitDuration), reset = bitDuration - 1)
		# We use normal mode clocking here - bits are defined by an 8MHz clock frequency
		# A '1' is given by a space time of 1-4 periods, and a mark time of 1-16
		# A '0' is given by a space time of 6-64 periods, and a mark time of 1-16
		# The bus idles high, hence space-then-mark. Provide enough range for the longest '0' period
		bitPeriod = Signal(range(64))
		# Current bit value being output
		bit = Signal()
		# Control signals for the bit FSM
		bitStart = Signal()
		bitFinish = Signal()
		# Current bit in the current value being output
		bitCounter = Signal(range(32))

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
			with m.If(bitTimer == 0):
				m.d.sync += [
					bitTimer.eq(bitTimer.reset),
					bitPeriod.dec(),
				]
			with m.Else():
				m.d.sync += bitTimer.dec()

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
				with m.If(bitStart):
					# Load the bit period counter according to the value of the bit to send
					with m.If(bit):
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
					m.d.comb += bitFinish.eq(1)
					m.next = 'IDLE'

		with m.FSM(name = 'swio'):
			with m.State('IDLE'):
				# If we're to start a read
				with m.If(self.startRead):
					m.d.sync += operation.eq(Operation.read)
					m.next = 'START'
				# If we're to start a write
				with m.Elif(self.startWrite):
					m.d.sync += operation.eq(Operation.write)
					m.next = 'START'
			with m.State('START'):
				# Set up a start bit, and reset the bit counter to the start of the register bits
				m.d.sync += [
					bit.eq(1),
					bitStart.eq(1),
					bitCounter.eq(0),
				]
				m.next = 'WAIT_START'
			with m.State('WAIT_START'):
				# Wait for the start bit to finish being transmitted
				with m.If(bitFinish):
					m.next = 'SEND_REGISTER'
			with m.State('SEND_REGISTER'):
				# Set up sending each bit in turn, waiting for it to complete
				pass

		return m
