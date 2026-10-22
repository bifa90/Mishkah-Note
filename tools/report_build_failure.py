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
        # An annotation is truncated by GitHub at a few KiB. Emit the newest
        # chunk first so the real exception is visible even for verbose pip.
        text = text.replace("%0A", "\n").replace("%0D", "\r")
        tail = "\n".join(text.splitlines()[-140:])[-18000:]
        chunks = [tail[i:i + 2800] for i in range(0, len(tail), 2800)]
        for index in reversed(range(len(chunks))):
            message = f"{path.name} ({index + 1}/{len(chunks)}):\n{chunks[index]}"
            message = message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
            print(f"::error::{message}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
