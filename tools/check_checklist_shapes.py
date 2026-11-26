#!/usr/bin/env python3
"""Render every diagram in ``docs/G3B_CHECKLIST.html`` and show they are not blank.

The page is HTML, so nothing in the test suite looks at it — a typo in an SVG
(x/y swapped, a colour that matches the background, a viewBox that clips the
content) ships as a card with an empty box and nobody notices until a user
scrolls past it.  Qt can render SVG headlessly, so this draws all seventeen and
refuses a blank one.

    python tools/check_checklist_shapes.py --check     # exit 1 on a blank shape
    python tools/check_checklist_shapes.py --out /tmp/shapes.png   # contact sheet
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "docs" / "G3B_CHECKLIST.html"

SVG_RE = re.compile(r"<svg class=\"shape\".*?</svg>", re.S)
SIZE = (480, 208)                     # 2× the 240×104 viewBox
GRID_COLS = 4
PAD, CAPTION = 12, 22


def shapes() -> list[str]:
    return SVG_RE.findall(PAGE.read_text(encoding="utf-8"))


def render(svg: str):
    """(QImage, dark_pixel_count) for one inline SVG."""
    from PySide6.QtCore import QByteArray
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer

    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    image = QImage(SIZE[0], SIZE[1], QImage.Format.Format_RGB32)
    image.fill(0xFFFFFFFF)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()

    dark = 0
    for y in range(0, SIZE[1], 2):
        for x in range(0, SIZE[0], 2):
            if image.pixelColor(x, y).lightness() < 240:
                dark += 1
    return image, dark


def contact_sheet(images: list, out: Path) -> Path:
    """One picture with all seventeen, numbered — for a human to glance at."""
    from PySide6.QtGui import QColor, QFont, QImage, QPainter

    cols = GRID_COLS
    rows = (len(images) + cols - 1) // cols
    width = cols * (SIZE[0] + PAD) + PAD
    height = rows * (SIZE[1] + CAPTION + PAD) + PAD
    sheet = QImage(width, height, QImage.Format.Format_RGB32)
    sheet.fill(QColor("#f6fafc"))

    painter = QPainter(sheet)
    font = QFont()
    font.setPointSize(11)
    font.setBold(True)
    painter.setFont(font)
    for index, image in enumerate(images, start=1):
        col, row = (index - 1) % cols, (index - 1) // cols
        x = PAD + col * (SIZE[0] + PAD)
        y = PAD + row * (SIZE[1] + CAPTION + PAD)
        painter.setPen(QColor("#1f2d34"))
        painter.drawText(x, y + 14, f"#{index}")
        painter.drawImage(x, y + CAPTION, image)
    painter.end()

    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(str(out))
    return out


def main(argv: list | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)

    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])      # noqa: F841

    found = shapes()
    rendered, blank = [], []
    for index, svg in enumerate(found, start=1):
        image, dark = render(svg)
        rendered.append(image)
        if dark == 0:
            blank.append(index)

    print(f"{len(found)} diagrams rendered")
    if blank:
        print("blank diagrams (a card with an empty box): "
              + ", ".join(f"#{n}" for n in blank), file=sys.stderr)

    if "--out" in args:
        target = Path(args[args.index("--out") + 1])
        print(f"wrote {contact_sheet(rendered, target)}")
    if "--check" in args:
        if len(found) != 17:
            print(f"expected 17 diagrams, found {len(found)}", file=sys.stderr)
            return 1
        return 1 if blank else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
