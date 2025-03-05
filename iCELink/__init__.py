# SPDX-License-Identifier: BSD-3-Clause
from torii_boards.lattice.icebreaker import ICEBreakerPlatform
from torii.build import Resource, Pins, Attrs
from .interface import iCELinkInterface

__all__ = (
	'cli',
)

def cli() -> int:
	from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
	from subprocess import CalledProcessError
	import logging

	# Configure basic logging so it's ready to go from right at the start
	configureLogging()

	# Build the command line parser
	parser = ArgumentParser(formatter_class = ArgumentDefaultsHelpFormatter,
		description = 'iCELink-SWIO Ardulink-compatible gateware')
	parser.add_argument('--verbose', '-v', action = 'store_true', help = 'Enable debugging output')

	actions = parser.add_subparsers(dest = 'action', required = True)
	buildAction = actions.add_parser('build', help = 'Build the iCELink-SWIO gateware')
	actions.add_parser('sim', help = 'Simulate and test the gateware components')

	# Allow the user to pick a seed if their toolchain is not giving good nextpnr runs
	buildAction.add_argument('--seed', action = 'store', type = int, default = 0,
		help = 'The nextpnr seed to use for the gateware build (default 0)')

	# Parse the command line and, if `-v` is specified, bump up the logging level
	args = parser.parse_args()
	if args.verbose:
		from logging import root, DEBUG
		root.setLevel(DEBUG)

	# Dispatch the action requested
	if args.action == 'sim':
		from unittest.loader import TestLoader
		from unittest.runner import TextTestRunner

		loader = TestLoader()
		tests = loader.discover(start_dir = 'iCELink.sim', pattern = '*.py')

		runner = TextTestRunner()
		runner.run(tests)
		return 0
	elif args.action == 'build':
		platform = ICEBreakerPlatform()
		platform.add_resources((
			Resource('swio', 0, Pins('pmod_1:1', dir = 'io'), Attrs(IO_STANDARD = 'SB_LVCMOS')),
		))
		try:
			platform.build(iCELinkInterface(), name = 'iCELink', pnrSeed = args.seed)
		except CalledProcessError:
			logging.error('Synthesising gateware and building bitstream failed, see build logs for details')
			return 1
		return 0
	else:
		return 1

def configureLogging():
	from rich.logging import RichHandler
	import logging

	logging.basicConfig(
		force = True,
		format = '%(message)s',
		level = logging.INFO,
		handlers = [RichHandler(rich_tracebacks = True, show_path = False)]
	)
