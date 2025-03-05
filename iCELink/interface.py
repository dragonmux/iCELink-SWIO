# SPDX-License-Identifier: BSD-3-Clause
from torii import Elaboratable, Module
from torii.build.plat import Platform
from torii.lib.stdio.serial import AsyncSerial
from .ardulink import ArdulinkProtocol

class iCELinkInterface(Elaboratable):
	def elaborate(self, platform: Platform) -> Module:
		m = Module()
		divisor = int(platform.default_clk_frequency // 115200)
		m.submodules.uart = uart = AsyncSerial(
			divisor = divisor, data_bits = 8, parity = 'none', pins = platform.request('uart', 0)
		)
		m.submodules.protocol = protocol = ArdulinkProtocol()

		m.d.comb += [
			# RX interface
			protocol.recvData.eq(uart.rx.data),
			protocol.recvReady.eq(uart.rx.rdy),
			uart.rx.ack.eq(protocol.recvDone),
			# TX interface
			uart.tx.data.eq(protocol.sendData),
			protocol.sendReady.eq(uart.tx.rdy),
			uart.tx.ack.eq(protocol.sendStart),
		]
		return m
