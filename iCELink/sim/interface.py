# SPDX-License-Identifier: BSD-3-Clause
from torii import Signal, Record
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

class ArdulinkProtocolTestCase(ToriiTestCase):
	dut: iCELinkInterface = iCELinkInterface
	domains = (('sync', 12e6), )
	platform = Platform()

	@ToriiTestCase.simulation
	@ToriiTestCase.sync_domain(domain = 'sync')
	def testIntegration(self):
		yield
