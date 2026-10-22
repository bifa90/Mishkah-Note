#!/usr/bin/env python3
"""Regenerate every application icon from the brand logo.

The logo ships as ``src/mufakkira/resources/branding/logo.svg`` — a vector
master, so the icons stay sharp at any DPI and can be re-rendered at any size
instead of being hand-painted per size.

Small icon sizes cannot show a whole detailed illustration, so the generator
uses two framings:

* **16–32 px** — a tighter framing around the mark, which stays readable at
  taskbar size instead of turning into grey mush.
* **48 px and above** — the full mark, where the flowing body is an asset.

Usage::

    python tools/make_icon.py            # needs PySide6 (QSvgRenderer)

Outputs, all in ``src/mufakkira/resources/icons/``::

    app.svg                vector master (copy of the branding logo)
    app-16 … app-512.png   desktop entry sizes
    app.png                256 px default
    app.ico                Windows multi-size icon
    close-light/dark.png   tab close glyph
    check-white/dark.png   checkbox tick
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "src"))

BRANDING = ROOT / "src" / "mufakkira" / "resources" / "branding"
ICON_DIR = ROOT / "src" / "mufakkira" / "resources" / "icons"

LOGO_SVG = BRANDING / "logo.svg"
BACKGROUND = "#5FC1EA"          # the logo's own sky blue

SIZES = (16, 24, 32, 48, 64, 128, 256, 512)
SMALL_CROP_MAX = 32             # up to this size, frame the head instead
#: tight framing of the mark (x, y, w, h as fractions of the artwork) used for
#: the smallest sizes; measured on the logo grid
HEAD_CROP = (0.02, 0.04, 0.46, 0.46)
SUPERSAMPLE = 4

CLOSE_LIGHT = (92, 92, 92, 255)
CLOSE_DARK = (200, 200, 200, 255)
CHECK_WHITE = (255, 255, 255, 255)
CHECK_DARK = (16, 26, 32, 255)


# ---------------------------------------------------------------------------
# logo rendering
# ---------------------------------------------------------------------------
def _renderer(logo: Path):
    from PySide6.QtCore import QRectF
    from PySide6.QtSvg import QSvgRenderer

    if not logo.exists():
        raise SystemExit(f"logo not found: {logo}")
    return QSvgRenderer(str(logo)), QRectF


def render_logo(size: int, crop: bool = False) -> Image.Image:
    """Render the vector logo to a square RGBA image over the sky-blue field."""
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QColor, QImage, QPainter

    canvas = size * SUPERSAMPLE
    image = QImage(canvas, canvas, QImage.Format.Format_ARGB32)
    image.fill(QColor(BACKGROUND))

    renderer, rect_type = _renderer(LOGO_SVG)
    if crop:
        box = renderer.viewBoxF()
        x, y, w, h = HEAD_CROP
        renderer.setViewBox(QRectF(box.x() + x * box.width(),
                                   box.y() + y * box.height(),
                                   w * box.width(), h * box.height()))

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    renderer.render(painter, QRectF(0, 0, canvas, canvas))
    painter.end()

    image.save("/tmp/_mfk_icon.png")
    rendered = Image.open("/tmp/_mfk_icon.png").convert("RGBA")
    return rendered.resize((size, size), Image.LANCZOS)


def render_icon(size: int) -> Image.Image:
    return render_logo(size, crop=size <= SMALL_CROP_MAX)


# ---------------------------------------------------------------------------
# small glyphs (drawn, not font glyphs, so they never depend on the system)
# ---------------------------------------------------------------------------
def draw_close(colour: tuple, size: int = 32) -> Image.Image:
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    inset, width = size * 0.3, max(1.5, size * 0.055)
    draw.line([inset, inset, size - inset, size - inset],
              fill=colour, width=int(width))
    draw.line([size - inset, inset, inset, size - inset],
              fill=colour, width=int(width))
    return image


def draw_check(colour: tuple, size: int = 32) -> Image.Image:
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    width = max(2, int(size * 0.12))
    draw.line([(size * 0.22, size * 0.52), (size * 0.42, size * 0.72)],
              fill=colour, width=width)
    draw.line([(size * 0.42, size * 0.72), (size * 0.78, size * 0.28)],
              fill=colour, width=width)
    return image


def main() -> None:
    ICON_DIR.mkdir(parents=True, exist_ok=True)

    for size in SIZES:
        out = ICON_DIR / f"app-{size}.png"
        render_icon(size).save(out, "PNG")
        print(f"wrote {out.name}")

    render_icon(256).save(ICON_DIR / "app.png", "PNG")

    base = render_icon(256)
    base.save(ICON_DIR / "app.ico", format="ICO",
              sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64),
                     (128, 128), (256, 256)])
    print("wrote app.ico")

    (ICON_DIR / "app.svg").write_text(LOGO_SVG.read_text(encoding="utf-8"),
                                      encoding="utf-8")
    print("wrote app.svg")

    for name, colour in (("close-light", CLOSE_LIGHT), ("close-dark", CLOSE_DARK)):
        draw_close(colour).save(ICON_DIR / f"{name}.png", "PNG")
        print(f"wrote {name}.png")

    for name, colour in (("check-white", CHECK_WHITE), ("check-dark", CHECK_DARK)):
        draw_check(colour).save(ICON_DIR / f"{name}.png", "PNG")
        print(f"wrote {name}.png")


if __name__ == "__main__":
    main()
