#!/usr/bin/env python3
"""Regenerate the application icon at every required size.

The mark is a flat geometric fish — white and black only — on a light sky
blue field, in the style of Getartcraft's icon sets.  Drawing it here rather
than shipping a bitmap means the icon is reproducible, reviewable in a diff,
and re-renderable at any DPI:

    python3 tools/make_icon.py

Outputs (into src/mufakkira/resources/icons/):
    app.svg                vector master
    app-16 … app-512.png   raster sizes for the desktop entry
    app.png                256 px default
    app.ico                Windows multi-size icon
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
ICON_DIR = HERE.parent / "src" / "mufakkira" / "resources" / "icons"

SKY = (142, 208, 232, 255)      # #8ED0E8 — light sky blue
WHITE = (255, 255, 255, 255)
BLACK = (24, 28, 32, 255)       # near-black ink

SIZES = (16, 24, 32, 48, 64, 128, 256, 512)
SUPERSAMPLE = 4                 # render big, downscale → crisp anti-aliasing


def _ellipse(draw, box, fill):
    draw.ellipse(box, fill=fill)


def _tri(draw, points, fill):
    draw.polygon(points, fill=fill)


def draw_fish(canvas: int) -> Image.Image:
    """Render the icon at *canvas* px (already supersampled by the caller)."""
    img = Image.new("RGBA", (canvas, canvas), SKY)
    d = ImageDraw.Draw(img)
    u = canvas / 100.0          # one design unit

    # Rounded-square field (the desktop environment may re-mask it anyway).
    radius = 22 * u
    d.rounded_rectangle([0, 0, canvas - 1, canvas - 1], radius=radius, fill=SKY)

    # --- tail: black triangle, drawn first so the body overlaps its root ---
    tail = [
        (72.0 * u, 50.0 * u),    # root (hidden under the body)
        (90.0 * u, 30.0 * u),
        (86.0 * u, 50.0 * u),
        (90.0 * u, 70.0 * u),
    ]
    _tri(d, tail, BLACK)

    # --- body: white ellipse -------------------------------------------
    body = [16.0 * u, 33.0 * u, 76.0 * u, 67.0 * u]
    _ellipse(d, body, WHITE)

    # --- dorsal fin: black triangle on the back ------------------------
    _tri(d, [(38.0 * u, 36.0 * u), (50.0 * u, 18.0 * u), (58.0 * u, 37.0 * u)], BLACK)

    # --- pelvic fin: black triangle under the belly -------------------
    _tri(d, [(42.0 * u, 63.0 * u), (52.0 * u, 78.0 * u), (58.0 * u, 62.0 * u)], BLACK)

    # --- gill: black arc-shaped wedge ---------------------------------
    d.chord([36.0 * u, 36.0 * u, 62.0 * u, 66.0 * u], start=110, end=250, fill=BLACK)
    # re-draw the front of the body so the chord reads as a stripe, not a bite
    d.pieslice([30.0 * u, 34.0 * u, 60.0 * u, 66.0 * u], start=250, end=110, fill=WHITE)

    # --- eye: black disc with a white glint ---------------------------
    _ellipse(d, [24.0 * u, 42.0 * u, 34.0 * u, 52.0 * u], BLACK)
    _ellipse(d, [26.5 * u, 44.0 * u, 30.0 * u, 47.5 * u], WHITE)

    # --- mouth: small black notch at the nose -------------------------
    _tri(d, [(16.5 * u, 47.0 * u), (22.0 * u, 50.0 * u), (16.5 * u, 53.0 * u)], BLACK)

    return img


def draw_close(color: tuple, size: int = 32) -> Image.Image:
    """A minimal ✕ for the tab close button (drawn, not a font glyph)."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    inset, width = size * 0.3, max(1.5, size * 0.055)
    d.line([inset, inset, size - inset, size - inset], fill=color, width=int(width))
    d.line([size - inset, inset, inset, size - inset], fill=color, width=int(width))
    return img


def draw_check(color: tuple, size: int = 32) -> Image.Image:
    """A crisp ✓ for checked check boxes (QSS cannot draw one itself)."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.line([(size * 0.22, size * 0.52), (size * 0.42, size * 0.72)],
           fill=color, width=max(2, int(size * 0.12)))
    d.line([(size * 0.42, size * 0.72), (size * 0.78, size * 0.28)],
           fill=color, width=max(2, int(size * 0.12)))
    return img


def render(size: int) -> Image.Image:
    big = draw_fish(size * SUPERSAMPLE)
    return big.resize((size, size), Image.LANCZOS)


SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100" height="100">
  <title>Notepad — مفكرتي</title>
  <rect width="100" height="100" rx="22" fill="#8ED0E8"/>
  <!-- tail -->
  <polygon points="72,50 90,30 86,50 90,70" fill="#181C20"/>
  <!-- body -->
  <ellipse cx="46" cy="50" rx="30" ry="17" fill="#FFFFFF"/>
  <!-- dorsal fin -->
  <polygon points="38,36 50,18 58,37" fill="#181C20"/>
  <!-- pelvic fin -->
  <polygon points="42,63 52,78 58,62" fill="#181C20"/>
  <!-- gill stripe -->
  <path d="M51 35.5 A15 15 0 0 0 51 64.5 L60 64.5 A15 15 0 0 1 60 35.5 Z" fill="#181C20"/>
  <!-- eye -->
  <circle cx="29" cy="47" r="5" fill="#181C20"/>
  <circle cx="28.2" cy="45.7" r="1.8" fill="#FFFFFF"/>
  <!-- mouth -->
  <polygon points="16.5,47 22,50 16.5,53" fill="#181C20"/>
</svg>
"""


def main() -> None:
    ICON_DIR.mkdir(parents=True, exist_ok=True)

    for size in SIZES:
        out = ICON_DIR / f"app-{size}.png"
        render(size).save(out, "PNG")
        print(f"wrote {out.relative_to(ICON_DIR.parent.parent.parent)}")

    render(256).save(ICON_DIR / "app.png", "PNG")

    # Windows multi-resolution icon
    base = render(256)
    base.save(ICON_DIR / "app.ico", format="ICO",
              sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64),
                     (128, 128), (256, 256)])
    print("wrote app.ico")

    (ICON_DIR / "app.svg").write_text(SVG, encoding="utf-8")
    print("wrote app.svg")

    for name, colour in (("close-light", (92, 92, 92, 255)),
                         ("close-dark", (200, 200, 200, 255))):
        draw_close(colour).save(ICON_DIR / f"{name}.png", "PNG")
        print(f"wrote {name}.png")

    for name, colour in (("check-white", (255, 255, 255, 255)),
                         ("check-dark", (16, 26, 32, 255))):
        draw_check(colour).save(ICON_DIR / f"{name}.png", "PNG")
        print(f"wrote {name}.png")


if __name__ == "__main__":
    main()
