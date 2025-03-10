# SPDX-License-Identifier: BSD-3-Clause
from torii import Elaboratable, Module, Signal, Record
from torii.hdl.rec import Direction
from torii.sim import Settle
from torii.test import ToriiTestCase

from ..interface import iCELinkInterface

class SWIORecord(Record):
	i: Signal[1, Direction.FANIN]
	o: Signal[1, Direction.FANOUT]
	oe: Signal[1, Direction.FANOUT]

class UARTRxRecord(Record):
	i: Signal[1, Direction.FANIN]

class UARTTxRecord(Record):
	o: Signal[1, Direction.FANOUT]

class UARTRecord(Record):
	rx: UARTRxRecord
	tx: UARTTxRecord

class LEDRecord(Record):
	o: Signal[1, Direction.FANOUT]

swio = SWIORecord()
uart = UARTRecord()
ledR = LEDRecord()
ledG = LEDRecord()

class Platform:
	@property
	def default_clk_frequency(self):
		return 12e6

	def request(self, name: str, number: int):
		match name:
			case 'swio':
				assert number == 0
				return swio
			case 'uart':
				assert number == 0
				return uart
			case 'led_g':
				assert number == 0
				return ledG
			case 'led_r':
				assert number == 0
				return ledR
		raise AssertionError(f'Resource {name}_{number} not known')

class DUT(Elaboratable):
	def __init__(self):
		super().__init__()
		self.swio = Signal()
		self.interface = iCELinkInterface()

	def elaborate(self, platform) -> Module:
		m = Module()
		m.submodules.interfaace = self.interface

		with m.If(swio.oe):
			m.d.comb += [
				self.swio.eq(swio.o),
				swio.i.eq(swio.o)
			]
		with m.Else():
			m.d.comb += [
				self.swio.eq(swio.i),
				swio.i.eq(1),
			]

		return m

class ArdulinkProtocolTestCase(ToriiTestCase):
	dut: DUT = DUT
	domains = (('sync', 12e6), )
	platform = Platform()

	def readBytes(self, data: bytes):
		for byte in data:
			# Wait for the start bit (25 period 115200-baud timeout)
			yield from self.wait_until_low(uart.tx.o, timeout = int((12e6 / 115200) * 25))
			# Loop through each bit in the byte and check we get it
			for bit in range(8):
				value = (byte >> bit) & 1
				# Wait one bit period
				yield from self.wait_for(1 / 115200)
				# Grab the bit value and check it
				self.assertEqual((yield uart.tx.o), value)
			# Check we get a stop bit
			yield from self.wait_for(1 / 115200)
			self.assertEqual((yield uart.tx.o), 1)
			yield from self.wait_for(1 / 115200)

	def sendBytes(self, data: bytes, *, waitForStop: bool = True):
		bytes = len(data)
		for idx, byte in enumerate(data):
			# Do a start bit
			yield uart.rx.i.eq(0)
			yield from self.wait_for(1 / 115200)
			# Loop through each bit in the byte and send it in
			for bit in range(8):
				value = (byte >> bit) & 1
				yield uart.rx.i.eq(value)
				# Wait one bit period
				yield from self.wait_for(1 / 115200)
			# Do a stop bit
			yield uart.rx.i.eq(1)
			if waitForStop or idx != bytes - 1:
				yield from self.wait_for(1 / 115200)

	def swioCheckBit(self, bit: int):
		# Grab the DUT for the IOB'd SWIO signal
		dut = self.dut
		# Wait for SWIO to go low
		yield from self.wait_until_low(dut.swio)
		if bit == 1:
			# Wait 2T save for one cycle
			yield from self.wait_for((2 / 8e6) - (1 / 12e6))
		else:
			# Wait 8T save for one cycle
			yield from self.wait_for((8 / 8e6) - (1 / 12e6))
		# Validate SWIO goes back high
		self.assertEqual((yield dut.swio), 0)
		yield
		self.assertEqual((yield dut.swio), 1)
		# Wait 4T save for one cycle
		yield from self.wait_for((4 / 8e6) - (1 / 12e6))
		self.assertEqual((yield dut.swio), 1)
		# Should be back to idle now
		yield
		self.assertEqual((yield dut.swio), 1)

	def swioWrite(self, address: int, data: int):
		# Grab the DUT for the IOB'd SWIO signal
		dut = self.dut
		# Check we get a start bit
		yield from self.swioCheckBit(1)
		for index in range(7):
			# Figure out what the value of the next bit in the register address is
			bit = ((address << index) >> 6) & 1
			# Check that makes it to the bus correctly
			yield from self.swioCheckBit(bit)
		# Check that the write bit gets asserted onto the bus
		yield from self.swioCheckBit(1)
		for index in range(32):
			# Figure out what the value of the next bit in the register data is
			bit = ((data << index) >> 31) & 1
			# Check that makes it to the bus correctly
			yield from self.swioCheckBit(bit)
		# Check the SWIO controller does a proper stop bit
		self.assertEqual((yield dut.swio), 1)
		# Wait 20T save for one cycle
		yield from self.wait_for((20 / 8e6) - (1 / 12e6))
		self.assertEqual((yield dut.swio), 1)

	@ToriiTestCase.simulation
	@ToriiTestCase.sync_domain(domain = 'sync')
	def testIntegration(self):
		yield uart.rx.i.eq(1)
		yield
		# Wait for the SWIO protocol FSM to initialise state
		yield from self.wait_until_low(swio.o)
		yield from self.wait_until_low(swio.oe)
		yield from self.readBytes(b'!')
		# Do a short delay and then ask the Ardulink protocol to self-test
		yield from self.step(4)
		yield from self.sendBytes(b'?')
		yield from self.readBytes(b'+')
		# Do a short delay and then ask the Ardulink protocol to write register 7e with a value
		yield from self.step(4)
		yield from self.sendBytes(b'w')
		yield from self.sendBytes(0x7e.to_bytes(1))
		yield from self.sendBytes(0x5aa50400.to_bytes(4, byteorder = 'little'), waitForStop = False)
		# Watch SWIO do the transaction
		yield from self.swioWrite(0x7e, 0x5aa50400)
		# Check for the post-transaction ack from the protocol controller
		yield from self.readBytes(b'+')
