#!/usr/bin/env python3
"""Validate shipped icons without rewriting them with host-dependent renderers."""
from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent / "src/mishkah/resources"
SIZES = {16, 24, 32, 48, 64, 128, 256, 512}


def main() -> None:
    icons = ROOT / "icons"
    assert (icons / "app.svg").read_bytes() == (ROOT / "branding/logo.svg").read_bytes()
    for size in SIZES:
        with Image.open(icons / f"app-{size}.png") as image:
            assert image.size == (size, size)
            image.verify()
    with Image.open(icons / "app.ico") as image:
        # ICO's maximum native frame is 256px; 512px is a separate PNG asset.
        assert {(s, s) for s in (16, 24, 32, 48, 64, 128, 256)} <= image.info["sizes"]
        image.verify()
    print("All icon dimensions, ICO frames and vector source are valid.")


if __name__ == "__main__":
    main()
