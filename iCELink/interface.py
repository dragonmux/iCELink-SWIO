# SPDX-License-Identifier: BSD-3-Clause
from torii import Elaboratable, Module
from torii.build.plat import Platform
from torii.lib.stdio.serial import AsyncSerial
from .ardulink import ArdulinkProtocol
from .swio import SWIO

class iCELinkInterface(Elaboratable):
	def elaborate(self, platform: Platform) -> Module:
		m = Module()
		divisor = int(platform.default_clk_frequency // 115200)
		m.submodules.uart = uart = AsyncSerial(
			divisor = divisor, data_bits = 8, parity = 'none', pins = platform.request('uart', 0)
		)
		m.submodules.protocol = protocol = ArdulinkProtocol()
		m.submodules.swio = swio = SWIO(platform.request('swio', 0))

		m.d.comb += [
			# RX interface
			protocol.recvData.eq(uart.rx.data),
			uart.rx.ack.eq(protocol.recvReady),
			protocol.recvDone.eq(uart.rx.rdy),
			# TX interface
			uart.tx.data.eq(protocol.sendData),
			protocol.sendReady.eq(uart.tx.rdy),
			uart.tx.ack.eq(protocol.sendStart),
			# Downstream interface
			swio.reg.eq(protocol.reg),
			protocol.dataRead.eq(swio.dataRead),
			swio.dataWrite.eq(protocol.dataWrite),
			swio.startRead.eq(protocol.startRead),
			swio.startWrite.eq(protocol.startWrite),
			protocol.ready.eq(swio.ready),
			protocol.done.eq(swio.done),
		]

		# Use the LEDs as a simple transaction indicator
		greenLED = platform.request('led_g', 0)
		with m.If(protocol.startRead):
			m.d.sync += greenLED.eq(1)
		with m.Elif(swio.done):
			m.d.sync += greenLED.eq(0)

		redLed = platform.request('led_r', 0)
		with m.If(protocol.startWrite):
			m.d.sync += redLed.eq(1)
		with m.Elif(swio.done):
			m.d.sync += redLed.eq(0)
		return m
