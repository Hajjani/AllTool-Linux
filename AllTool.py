#!/usr/bin/env python3
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from Tools.version import get_version

# Global version — resolved from `.confs.json` (see Tools/version.py).
__version__ = get_version()

from Tools import main

if __name__ == "__main__":
    sys.exit(main())
