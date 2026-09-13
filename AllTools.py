#!/usr/bin/env python3
"""AllTool — center of action.

Thin dispatcher: every command lives in the Tools/ package (registered via
Tools/base.py registry) and runs through Tools:main. This file contains no
command logic, so `python3 AllTools.py`, `python3 alltool`, `python3 -m Tools`
and the installed `alltool` console_script all behave identically.

Layout contract (installer.sh + Makefile — DO NOT BREAK):
  - This file is copied to ~/bin/AllTools.py alongside ~/bin/Tools/ and
    ~/bin/alltool, so `import Tools` must resolve from this file's directory.
  - C libs + alltool_runner live in ~/.config/alltool/bin (see Tools/bindings.py,
    built with `make install-user`); commands use them when present and fall
    back to pure Python otherwise.
  - `__version__` is parsed by the `upa` updater regex; keep it in sync with
    Tools.__version__ and pyproject.toml.
"""

import os
import sys

__version__ = "2.0.0"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from Tools import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
