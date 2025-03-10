# SPDX-License-Identifier: BSD-3-Clause
from torii import Signal, Record
from torii.hdl.rec import Direction
from torii.sim import Settle
from torii.test import ToriiTestCase

from ..swio import SWIO

class SWIORecord(Record):
	i: Signal[1, Direction.FANIN]
	o: Signal[1, Direction.FANOUT]
	oe: Signal[1, Direction.FANOUT]

swio = SWIORecord()

class Platform:
	@property
	def default_clk_frequency(self):
		return 12e6

class SWIOTestCase(ToriiTestCase):
	dut: SWIO = SWIO
	dut_args = {
		'swio': swio
	}
	domains = (('sync', 12e6), )
	platform = Platform()

	def checkSWIOBit(self, bit: int):
		# Precondition: bus idle
		self.assertEqual((yield swio.o), 0)
		self.assertEqual((yield swio.oe), 0)
		# SETUP phase
		yield
		self.assertEqual((yield swio.o), 0)
		self.assertEqual((yield swio.oe), 0)
		# Check that a bit is properly asserted onto the bus
		yield
		self.assertEqual((yield swio.o), 0)
		self.assertEqual((yield swio.oe), 1)
		if bit == 1:
			# Wait 2T save for one cycle
			yield from self.wait_for((2 / 8e6) - (1 / 12e6))
		else:
			# Wait 8T save for one cycle
			yield from self.wait_for((8 / 8e6) - (1 / 12e6))
		self.assertEqual((yield swio.o), 0)
		self.assertEqual((yield swio.oe), 1)
		# Check that the bit gets deassserted from the bus
		yield
		self.assertEqual((yield swio.o), 0)
		self.assertEqual((yield swio.oe), 0)
		# Wait 4T save for one cycle
		yield from self.wait_for((4 / 8e6) - (1 / 12e6))
		self.assertEqual((yield swio.o), 0)
		self.assertEqual((yield swio.oe), 0)
		# IDLE phase
		yield
		self.assertEqual((yield swio.o), 0)
		self.assertEqual((yield swio.oe), 0)

	def assertSWIOBit(self, bit: int):
		# Precondition: bus idle
		self.assertEqual((yield swio.o), 0)
		self.assertEqual((yield swio.oe), 0)
		# Assert the bit onto the bus
		yield
		self.assertEqual((yield swio.oe), 0)
		yield swio.i.eq(0)
		yield Settle()
		self.assertEqual((yield swio.oe), 1)
		if bit == 1:
			# Wait 2T save for one cycle
			yield from self.wait_for((2 / 8e6) - (1 / 12e6))
		else:
			# Wait 8T save for one cycle
			yield from self.wait_for((8 / 8e6) - (1 / 12e6))
		yield Settle()
		self.assertEqual((yield swio.oe), 0)
		# Deassert the bit from the bus
		yield
		yield swio.i.eq(1)
		yield Settle()
		self.assertEqual((yield swio.oe), 0)
		# Wait 4T save for one cycle
		yield from self.wait_for((4 / 8e6) - (1 / 12e6))
		self.assertEqual((yield swio.oe), 0)
		# IDLE phase
		yield
		self.assertEqual((yield swio.oe), 0)
		yield
		self.assertEqual((yield swio.oe), 0)
		yield
		self.assertEqual((yield swio.oe), 0)

	@ToriiTestCase.simulation
	@ToriiTestCase.sync_domain(domain = 'sync')
	def testRegisterWrite(self):
		dut = self.dut
		# Check our starting conditions and that we go into the start of the init sequence
		self.assertEqual((yield dut.ready), 0)
		self.assertEqual((yield swio.oe), 0)
		yield
		self.assertEqual((yield dut.ready), 0)
		self.assertEqual((yield swio.o), 1)
		self.assertEqual((yield swio.oe), 1)
		# Wait 5ms save for one cycle
		yield from self.wait_for(5e-3 - (1 / 12e6))
		self.assertEqual((yield dut.ready), 0)
		self.assertEqual((yield swio.o), 1)
		self.assertEqual((yield swio.oe), 1)
		# Make sure that we step inot the second phase of init correctly
		yield
		self.assertEqual((yield dut.ready), 0)
		self.assertEqual((yield swio.o), 0)
		self.assertEqual((yield swio.oe), 1)
		# Wait 20ms save for one cycle
		yield from self.wait_for(20e-3 - (1 / 12e6))
		self.assertEqual((yield dut.ready), 0)
		self.assertEqual((yield swio.o), 0)
		self.assertEqual((yield swio.oe), 1)
		# And then make sure we go into the idle state properly
		yield
		self.assertEqual((yield dut.ready), 1)
		self.assertEqual((yield swio.o), 0)
		self.assertEqual((yield swio.oe), 0)
		# Start the register write request
		yield dut.reg.eq(0xa5)
		yield dut.dataWrite.eq(0xaaca15aa)
		yield
		self.assertEqual((yield dut.done), 0)
		yield dut.startWrite.eq(1)
		# Wait for the transaction to start
		yield
		yield dut.startWrite.eq(0)
		yield
		# Check that the start bit occurs properly
		yield from self.checkSWIOBit(1)
		value = 0xa5
		for index in range(7):
			# Figure out what the value of the next bit is, and check it's asserted onto the bus properly
			bit = ((value << index) >> 6) & 1
			yield from self.checkSWIOBit(bit)
		# Check that the write bit gets asserted onto the bus
		yield from self.checkSWIOBit(1)
		value = 0xaaca15aa
		for index in range(32):
			# Figure out what the value of the next bit is, and check it's asserted onto the bus properly
			bit = ((value << index) >> 31) & 1
			yield from self.checkSWIOBit(bit)
		# Check that we're in bus idle (conditions for a stop bit)
		yield
		self.assertEqual((yield swio.o), 0)
		self.assertEqual((yield swio.oe), 0)
		# Wait 20T save for one cycle
		yield from self.wait_for((20 / 8e6) - (1 / 12e6))
		self.assertEqual((yield dut.done), 0)
		self.assertEqual((yield swio.o), 0)
		self.assertEqual((yield swio.oe), 0)
		# Check that the transaction completes properly
		yield
		self.assertEqual((yield dut.done), 1)
		self.assertEqual((yield swio.o), 0)
		self.assertEqual((yield swio.oe), 0)
		yield
		self.assertEqual((yield dut.done), 0)
		self.assertEqual((yield swio.o), 0)
		self.assertEqual((yield swio.oe), 0)
		yield from self.step(10)

	@ToriiTestCase.simulation
	@ToriiTestCase.sync_domain(domain = 'sync')
	def testRegisterRead(self):
		dut = self.dut
		# Check our starting conditions and that we go into the start of the init sequence
		self.assertEqual((yield dut.ready), 0)
		self.assertEqual((yield swio.oe), 0)
		yield swio.i.eq(1)
		yield
		self.assertEqual((yield dut.ready), 0)
		self.assertEqual((yield swio.o), 1)
		self.assertEqual((yield swio.oe), 1)
		# Wait 5ms save for one cycle
		yield from self.wait_for(5e-3 - (1 / 12e6))
		self.assertEqual((yield dut.ready), 0)
		self.assertEqual((yield swio.o), 1)
		self.assertEqual((yield swio.oe), 1)
		# Make sure that we step inot the second phase of init correctly
		yield
		self.assertEqual((yield dut.ready), 0)
		self.assertEqual((yield swio.o), 0)
		self.assertEqual((yield swio.oe), 1)
		# Wait 20ms save for one cycle
		yield from self.wait_for(20e-3 - (1 / 12e6))
		self.assertEqual((yield dut.ready), 0)
		self.assertEqual((yield swio.o), 0)
		self.assertEqual((yield swio.oe), 1)
		# And then make sure we go into the idle state properly
		yield
		self.assertEqual((yield dut.ready), 1)
		self.assertEqual((yield swio.o), 0)
		self.assertEqual((yield swio.oe), 0)
		# Start the register read request
		yield dut.reg.eq(0xa5)
		yield
		self.assertEqual((yield dut.done), 0)
		yield dut.startRead.eq(1)
		# Wait for the transaction to start
		yield
		yield dut.startRead.eq(0)
		yield
		# Check that the start bit occurs properly
		yield from self.checkSWIOBit(1)
		value = 0xa5
		for index in range(7):
			# Figure out what the value of the next bit is, and check it's asserted onto the bus properly
			bit = ((value << index) >> 6) & 1
			yield from self.checkSWIOBit(bit)
		# Check that the read bit gets asserted onto the bus
		yield from self.checkSWIOBit(0)
		value = 0xaaca15aa
		for index in range(32):
			# Figure out what the value of the next bit is, and check it's asserted onto the bus properly
			bit = ((value << index) >> 31) & 1
			yield from self.assertSWIOBit(bit)
		# Check that we're in bus idle (conditions for a stop bit)
		yield
		yield swio.i.eq(1)
		self.assertEqual((yield swio.o), 0)
		self.assertEqual((yield swio.oe), 0)
		# Wait 20T save for one cycle
		yield from self.wait_for((20 / 8e6) - (1 / 12e6))
		self.assertEqual((yield dut.done), 0)
		self.assertEqual((yield swio.o), 0)
		self.assertEqual((yield swio.oe), 0)
		# Check that the transaction completes properly
		yield
		self.assertEqual((yield dut.done), 1)
		self.assertEqual((yield dut.dataRead), value)
		self.assertEqual((yield swio.o), 0)
		self.assertEqual((yield swio.oe), 0)
		yield
		self.assertEqual((yield dut.done), 0)
		self.assertEqual((yield swio.o), 0)
		self.assertEqual((yield swio.oe), 0)
		yield from self.step(10)
