#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause

from sys import argv, path, exit
from pathlib import Path

iCELinkPath = Path(argv[0]).resolve().parent
if (iCELinkPath / 'iCELink').is_dir():
	path.insert(0, str(iCELinkPath))
else:
	raise ImportError('Cannot find the iCELink gateware')

from iCELink import cli
if __name__ == '__main__':
	exit(cli())
