"""Command-line metadata without loading the graphical runtime."""

from __future__ import annotations

import sys
from typing import List, Optional

from mishkah import APP_VERSION

USAGE = """mishkah — a Windows 11-style text editor with first-class RTL support

Usage:
  mishkah [OPTION]... [FILE]...

Options:
  --safe-mode   ignore the saved configuration and the previous session
  --version     print the version and exit
  -h, --help    print this help and exit

Files are opened one per tab.  Text direction can be switched with
Ctrl+Shift+Right (RTL), Ctrl+Shift+Left (LTR) or Ctrl+Shift+A (automatic).
"""



def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    flags = set(argv[1:])
    if "--help" in flags or "-h" in flags:
        print(USAGE)
        return 0
    if "--version" in flags:
        print(APP_VERSION)
        return 0
    from mishkah.app import main as run_gui

    return run_gui(argv)
