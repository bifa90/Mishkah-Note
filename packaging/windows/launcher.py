"""Entry point for the frozen Windows build (PyInstaller)."""

from __future__ import annotations

import sys

from mishkah.cli import main

if __name__ == "__main__":
    sys.exit(main())
