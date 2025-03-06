# SPDX-License-Identifier: BSD-3-Clause
from torii import Elaboratable, Module, Signal
from torii.build.plat import Platform
from enum import IntEnum, auto, unique

__all__ = (
	'ArdulinkProtocol',
)

@unique
class RegisterOperation(IntEnum):
	read = auto()
	write = auto()

class ArdulinkProtocol(Elaboratable):
	def __init__(self):
		super().__init__()

		# RX interface
		self.recvData = Signal(8)
		self.recvReady = Signal()
		self.recvDone = Signal()

		# TX Interface
		self.sendData = Signal(8)
		self.sendReady = Signal()
		self.sendStart = Signal()

		# Target/downstream interface
		self.targetPower = Signal()
		self.reg = Signal(7)
		self.dataRead = Signal(32)
		self.dataWrite = Signal(32)
		self.startRead = Signal()
		self.startWrite = Signal()
		self.ready = Signal()
		self.done = Signal()

	def elaborate(self, platform: Platform) -> Module:
		m = Module()

		operation = Signal(RegisterOperation)
		valueByte = Signal(range(5))

		# Protocol FSM
		with m.FSM(name = 'protocol'):
			with m.State('INIT'):
				# Wait for the UART and underlying protocol to become ready
				with m.If(self.sendReady & self.ready):
					# Once it is, send the protocol start byte
					m.d.comb += [
						self.sendData.eq(ord('!')),
						self.sendStart.eq(1),
					]
					# And wait for a command byte to come down the pipe
					m.next = 'WAIT_COMMAND'
			with m.State('WAIT_COMMAND'):
				# Wait for a byte to become available on the UART
				with m.If(self.recvReady):
					m.d.comb += self.recvDone.eq(1)
					m.next = 'DISPATCH'
			with m.State('DISPATCH'):
				# Figure out what to do about the command
				with m.Switch(self.recvData):
					# Command TEST
					with m.Case(ord('?')):
						m.next = 'SEND_ACK'
					# Command POWER_ON
					with m.Case(ord('p')):
						m.d.sync += self.targetPower.eq(1)
						m.next = 'SEND_ACK'
					# Command POWER_OFF
					with m.Case(ord('P')):
						m.d.sync += self.targetPower.eq(0)
						m.next = 'SEND_ACK'
					# Command WRITE_REG
					with m.Case(ord('w')):
						m.d.sync += operation.eq(RegisterOperation.write)
						m.next = 'RECV_REG_NUMBER'
					with m.Case(ord('r')):
						m.d.sync += operation.eq(RegisterOperation.read)
						m.next = 'RECV_REG_NUMBER'
					# If we don't recognise the command, do nothing and wait for another
					with m.Default():
						m.next = 'WAIT_COMMAND'
			with m.State('RECV_REG_NUMBER'):
				# Wait for a byte to become available on the UART
				with m.If(self.recvReady):
					m.d.comb += self.recvDone.eq(1)
					m.next = 'RECV_REGISTER'
			with m.State('RECV_REGISTER'):
				# Grab the register to operate on
				m.d.sync += self.reg.eq(self.recvData)
				# Dispatch to the next phase of the operation
				with m.If(operation == RegisterOperation.read):
					m.d.comb += self.startRead.eq(1)
					m.next = 'WAIT_READ'
				with m.Elif(operation == RegisterOperation.write):
					m.d.sync += valueByte.eq(0)
					m.next = 'RECV_WRITE_VALUE'
			with m.State('WAIT_READ'):
				# Wait for the operation to complete
				with m.If(self.done):
					# Start sending back the value we read
					m.d.sync += valueByte.eq(0)
					m.next = 'SEND_READ_VALUE'
			with m.State('SEND_READ_VALUE'):
				# Wait for the UART to become ready
				with m.If(self.sendReady):
					# Queue a byte to send
					m.d.comb += [
						self.sendData.eq(self.dataRead.bit_select(8 * valueByte, 8)),
						self.sendStart.eq(1),
					]
					# Advance to the next byte
					m.d.sync += valueByte.inc()
				# If we've sent the last byte then we're done
				with m.Elif(valueByte == 4):
					m.next = 'WAIT_COMMAND'
			with m.State('RECV_WRITE_VALUE'):
				# Wait for the UART to become ready
				with m.If(self.recvReady):
					m.d.comb += self.recvDone.eq(1)
					m.next = 'GRAB_WRITE_VALUE'
				# If we've received the last byte then we're done
				with m.Elif(valueByte == 4):
					m.d.comb += self.startWrite.eq(1)
					m.next = 'WAIT_WRITE'
			with m.State('GRAB_WRITE_VALUE'):
				m.d.sync += [
					self.dataWrite.bit_select(8 * valueByte, 8).eq(self.recvData),
					valueByte.inc(),
				]
				m.next = 'RECV_WRITE_VALUE'
			with m.State('WAIT_WRITE'):
				# Wait for the operation to complete
				with m.If(self.done):
					# Send the ack that goes with the request
					m.next = 'SEND_ACK'
			with m.State('SEND_ACK'):
				# Wait for the UART to become ready
				with m.If(self.sendReady):
					# Once it is, send the protocol ack byte
					m.d.comb += [
						self.sendData.eq(ord('+')),
						self.sendStart.eq(1),
					]
					# And wait for a command byte to come down the pipe
					m.next = 'WAIT_COMMAND'

		return m
