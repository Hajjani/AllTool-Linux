"""Enables `python -m Tools <command>` (used by Makefile uninstall target)."""
import sys

from . import main

if __name__ == "__main__":
    sys.exit(main())
