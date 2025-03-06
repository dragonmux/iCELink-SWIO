# SPDX-License-Identifier: BSD-3-Clause
from torii import Elaboratable, Module, Signal
from torii.build.plat import Platform
from torii.lib.io import Pin

__all__ = (
	'SWIOBitReader',
)

class SWIOBitReader(Elaboratable):
	def __init__(self, swio: Pin):
		super().__init__()

		self.bit = Signal()
		self.error = Signal()
		self.start = Signal()
		self.finish = Signal()

		self._swio = swio

	def elaborate(self, platform: Platform) -> Module:
		m = Module()
		# SWIO GPIO
		swio = self._swio
		# 8MHz timer for counting in bits
		baseFrequency = int(platform.default_clk_frequency // 1e6) # 12MHz
		bitFrequency = 8 # MHz
		bitTimer = Signal(range(baseFrequency + bitFrequency))
		# While the writer uses normal mode clocking, we get to have to just deal with w/e we're thrown..
		# so.. make sure we have enough signal for 2* the longest '0' bit time to catch errors like
		# a target crashing and the line getting stuck low.
		bitPeriod = Signal(range(128))

		# Delay timer for 2T in the mark period
		delayTimer = Signal(range(baseFrequency + bitFrequency))
		delayPeriod = Signal(range(5))

		# Counts bit periods while SWIO is low
		with m.If(swio.i == 0):
			# This logic is taken from libAudio's emulator clock manager to allow
			# the correct handling of the frequency beating for two close values
			m.d.sync += bitTimer.eq(bitTimer + bitFrequency)
			with m.If(baseFrequency - bitTimer < bitFrequency):
				m.d.sync += [
					bitTimer.eq(bitTimer - baseFrequency),
					bitPeriod.inc(),
				]

		# Simple delay block - feed in the delay amount in delayPeriod and this will run till that becomes zero
		with m.If(delayPeriod != 0):
			# This logic is taken from libAudio's emulator clock manager to allow
			# the correct handling of the frequency beating for two close values
			m.d.sync += delayTimer.eq(delayTimer + bitFrequency)
			with m.If(baseFrequency - delayTimer < bitFrequency):
				m.d.sync += [
					delayTimer.eq(delayTimer - baseFrequency),
					delayPeriod.dec(),
				]

		with m.FSM(name = 'bit'):
			with m.State('IDLE'):
				# If we need to start receiving a bit
				with m.If(self.start):
					# Set up the bit period register and clear the error marker
					m.d.sync += [
						bitPeriod.eq(0),
						self.error.eq(0),
					]
					# If the SWIO line is not already low, wait for it to go low
					with m.If(swio.i):
						m.next = 'SETUP'
					with m.Else():
						m.next = 'CAPTURE'
			with m.State('SETUP'):
				# Wait for the SWIO line to go low
				with m.If(swio.i == 0):
					m.next = 'CAPTURE'
			with m.State('CAPTURE'):
				# While SWIO remains low, count. Othewise, if we reach the error threshold, stop
				with m.If((swio.i == 0) & (bitPeriod == 96)):
					# We reached the error threshold, so set error
					m.d.sync += self.error.eq(1)
					# Use a 4T mark period
					m.d.sync += delayPeriod.eq(4)
					m.next = 'FINISH'
				# And similarly if we reach a high, stop
				with m.Elif(swio.i):
					# Use a 4T mark period
					m.d.sync += delayPeriod.eq(4)
					m.next = 'FINISH'
			with m.State('FINISH'):
				# Determine the bit value from the period count achieved
				with m.If(bitPeriod <= 4): # 4T can be either a slightly long '1' or a slightly short '0'.. *shrug*!
					m.d.sync += self.bit.eq(1)
				with m.Else():
					m.d.sync += self.bit.eq(0)
				m.next = 'WAIT_MARK'
			with m.State('WAIT_MARK'):
				# Wait for the bit period to reach 0
				with m.If(delayPeriod == 0):
					# Signal that we're done reading this bit
					m.d.comb += self.finish.eq(1)
					m.next = 'IDLE'

		return m
