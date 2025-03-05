# SPDX-License-Identifier: BSD-3-Clause
from torii import Elaboratable, Module
from torii.build.plat import Platform
from torii.lib.stdio.serial import AsyncSerial

class iCELinkInterface(Elaboratable):
	def elaborate(self, platform: Platform) -> Module:
		m = Module()
		divisor = int(platform.default_clk_frequency // 115200)
		m.submodules.uart = uart = AsyncSerial(
			divisor = divisor, data_bits = 8, parity = 'none', pins = platform.request('uart', 0)
		)
		return m
