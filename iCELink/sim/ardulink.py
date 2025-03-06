# SPDX-License-Identifier: BSD-3-Clause
from torii import Signal
from torii.sim import Settle
from torii.test import ToriiTestCase

from ..ardulink import ArdulinkProtocol

class ArdulinkProtocolTestCase(ToriiTestCase):
	dut: ArdulinkProtocol = ArdulinkProtocol
	domains = (('sync', 12e6), )

	def sendByte(self, value: bytes):
		dut = self.dut
		yield dut.recvReady.eq(1)
		self.assertEqual((yield dut.recvDone), 0)
		yield
		self.assertEqual((yield dut.recvDone), 1)
		yield dut.recvReady.eq(0)
		yield dut.recvData.eq(ord(value))
		yield
		self.assertEqual((yield dut.recvDone), 0)
		yield dut.recvData.eq(0)

	def sendBytes(self, data: bytes):
		for byte in data:
			yield
			yield from self.sendByte(byte.to_bytes(1))

	def recvByte(self, value: bytes):
		dut = self.dut
		self.assertEqual((yield dut.sendStart), 0)
		yield dut.sendReady.eq(1)
		yield
		yield dut.sendReady.eq(0)
		# And check that we get the correct ACK byte out
		self.assertEqual((yield dut.sendData), ord(value))
		self.assertEqual((yield dut.sendStart), 1)
		yield
		self.assertEqual((yield dut.sendStart), 0)

	def recvBytes(self, data: bytes):
		for byte in data:
			yield from self.recvByte(byte.to_bytes(1))
			yield

	@ToriiTestCase.simulation
	@ToriiTestCase.sync_domain(domain = 'sync')
	def testCommandStateMachine(self):
		dut = self.dut
		# Wait a cycle and then tell the FSM we're ready
		yield
		yield dut.ready.eq(1)
		# Check that it elicited the start byte response
		yield from self.recvByte(b'!')
		# Now set up to send in the TEST command
		yield from self.sendByte(b'?')
		# Check for the ack byte back
		yield from self.recvByte(b'+')
		yield
		# Set up to send in the POWER_ON command
		self.assertEqual((yield dut.targetPower), 0)
		yield from self.sendByte(b'p')
		self.assertEqual((yield dut.targetPower), 0)
		yield
		# Check it powered on
		self.assertEqual((yield dut.targetPower), 1)
		# Check for the ack byte back
		yield from self.recvByte(b'+')
		# Set up to send in the POWER_OFF command
		self.assertEqual((yield dut.targetPower), 1)
		yield from self.sendByte(b'P')
		self.assertEqual((yield dut.targetPower), 1)
		yield
		# Check it powered on
		self.assertEqual((yield dut.targetPower), 0)
		# Check for the ack byte back
		yield from self.recvByte(b'+')
		# Set up to send in the WRITE_REG command
		yield from self.sendByte(b'w')
		yield
		yield from self.sendByte(0x7a.to_bytes(1))
		yield from self.sendBytes(0x55aaca15.to_bytes(4, byteorder = 'little'))
		# Now the controller has all the data, make sure it starts a write transaction
		yield
		self.assertEqual((yield dut.startWrite), 1)
		self.assertEqual((yield dut.reg), 0x7a)
		self.assertEqual((yield dut.dataWrite), 0x55aaca15)
		yield
		self.assertEqual((yield dut.startWrite), 0)
		yield from self.step(4)
		# After a short delay, tell it the transaction's done
		yield dut.done.eq(1)
		yield
		yield dut.done.eq(0)
		# Check for the ack byte back
		yield from self.recvByte(b'+')
		yield
		# Set up to send in the READ_REG command
		yield from self.sendByte(b'r')
		yield
		yield from self.sendByte(0x35.to_bytes(1))
		# Now the controller has the request parameters, make sure it starts a read transaction
		self.assertEqual((yield dut.startRead), 1)
		yield
		self.assertEqual((yield dut.reg), 0x35)
		self.assertEqual((yield dut.startRead), 0)
		yield from self.step(4)
		# After a short delay, tell it the transaction's done
		yield dut.dataRead.eq(0xfeedaa55)
		yield dut.done.eq(1)
		yield
		yield dut.done.eq(0)
		yield
		# Read back the result of the read
		yield from self.recvBytes(0xfeedaa55.to_bytes(4, byteorder = 'little'))
		yield
