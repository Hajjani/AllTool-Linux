#!/usr/bin/env python3
import os
import sys

__version__ = "2.0.0"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from Tools import main

if __name__ == "__main__":
    sys.exit(main())
