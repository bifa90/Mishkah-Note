#!/usr/bin/env python3
"""Expose the tail of a failed native build as GitHub annotations."""
from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    for arg in sys.argv[1:]:
        path = Path(arg)
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        tail = "\n".join(text.splitlines()[-80:])[-14000:]
        message = f"{path.name}:\n{tail}"
        message = message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        print(f"::error::{message}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
