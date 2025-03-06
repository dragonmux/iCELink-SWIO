# SPDX-License-Identifier: BSD-3-Clause
from torii import Elaboratable, Module, Signal
from torii.build.plat import Platform
from torii.lib.io import Pin
from enum import IntEnum, auto, unique
from .bitWriter import SWIOBitWriter
from .bitReader import SWIOBitReader

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

		self.reg = Signal(7)
		self.dataRead = Signal(32)
		self.dataWrite = Signal(32)
		self.startRead = Signal()
		self.startWrite = Signal()
		self.ready = Signal()
		self.done = Signal()

		self._swio = swio

	def elaborate(self, platform: Platform) -> Module:
		m = Module()
		# The operation to perform on the register requested
		operation = Signal(Operation)
		# Data register for the chunk being sent
		data = Signal(32)
		# Current bit in the current value being output
		bitCounter = Signal(range(33))

		m.submodules.bitWriter = bitWriter = SWIOBitWriter(self._swio)
		m.submodules.bitReader = bitReader = SWIOBitReader(self._swio)

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
					bitWriter.bit.eq(1),
					bitCounter.eq(0),
					# Mirror the register address for ease of shifting out
					data.eq(self.reg[::-1]),
				]
				m.d.comb += bitWriter.start.eq(1)
				m.next = 'WAIT_START'
			with m.State('WAIT_START'):
				# Wait for the start bit to finish being transmitted
				with m.If(bitWriter.finish):
					m.next = 'SEND_REGISTER'
			with m.State('SEND_REGISTER'):
				# Set up sending each bit in turn, waiting for it to complete
				with m.If(bitCounter == 7):
					# We've sent all the bits in the register value, send the W/~R bit indicating if
					# this is a write (1) or a read (0)
					m.d.sync += bitWriter.bit.eq(operation == Operation.write)
					m.next = 'WAIT_READ_WRITE_BIT'
				with m.Else():
					m.d.sync += [
						bitWriter.bit.eq(data[0]),
						data.eq(data.shift_right(1)),
					]
					m.next = 'WAIT_SEND_REGISTER'
				m.d.comb += bitWriter.start.eq(1)
			with m.State('WAIT_SEND_REGISTER'):
				# Wait for the current bit to finish being transmitted
				with m.If(bitWriter.finish):
					m.d.sync += bitCounter.inc()
					m.next = 'SEND_REGISTER'
			with m.State('WAIT_READ_WRITE_BIT'):
				# Wait for the WRITE/~READ bit to finish being transmitted
				with m.If(bitWriter.finish):
					# Reset the bit counter so we start on the first bit of the value
					m.d.sync += bitCounter.eq(0)
					# If we're in a read operation, then start reading bits off the bus
					with m.If(operation == Operation.read):
						m.next = 'READ_VALUE'
					# Else if we're in a write operation, then start writing bits onto the bus
					with m.Elif(operation == Operation.write):
						m.d.sync += data.eq(self.dataWrite[::-1])
						m.next = 'WRITE_VALUE'
			with m.State('READ_VALUE'):
				# Set up sending a dummy '1' bit for each bit to read in turn, and timing
				# how many T SDIO stays low for to determine the bit value elicited from the target
				with m.If(bitCounter == 32):
					# If we've received all the data bits for this operation, do a stop bit
					m.d.comb += bitWriter.stop.eq(1)
					# Copy the resulting data to the output data register
					m.d.sync += self.dataRead.eq(data)
					m.next = 'STOP'
				with m.Else():
					# Set up a dummy '1' bit write
					m.d.comb += bitWriter.triggerRead.eq(1)
					# And set up to time the low duration
					m.d.comb += bitReader.start.eq(1)
					m.next = 'WAIT_READ_VALUE'
			with m.State('WAIT_READ_VALUE'):
				# Wait until the current bit has been timed
				with m.If(bitReader.finish):
					# Extract the resulting bit value into the local shift register and increment the bit counter
					m.d.sync += [
						data.eq(data.shift_left(1)),
						data[0].eq(bitReader.bit),
						bitCounter.inc(),
					]
					m.next = 'READ_VALUE'
			with m.State('WRITE_VALUE'):
				# Set up sending each bit in turn, waiting for it to complete
				with m.If(bitCounter == 32):
					# We've sent all the data bits for this operation, so request a stop bit
					m.d.comb += bitWriter.stop.eq(1)
					m.next = 'STOP'
				with m.Else():
					m.d.sync += [
						bitWriter.bit.eq(data[0]),
						data.eq(data.shift_right(1)),
					]
					m.d.comb += bitWriter.start.eq(1)
					m.next = 'WAIT_WRITE_VALUE'
			with m.State('WAIT_WRITE_VALUE'):
				# Wait for the current bit to finish being transmitted
				with m.If(bitWriter.finish):
					m.d.sync += bitCounter.inc()
					m.next = 'WRITE_VALUE'
			with m.State('STOP'):
				# Wait for the stop bit to be completed
				with m.If(bitWriter.finish):
					# Signal up that we're done, and go back to idle
					m.d.comb += self.done.eq(1)
					m.next = 'IDLE'

		m.d.comb += self.ready.eq(bitWriter.ready)
		return m
