"""Resource lookup: icons, stylesheets and the bundled Arabic typeface."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

RESOURCES_DIR = Path(__file__).resolve().parent.parent / "resources"
FONTS_DIR = RESOURCES_DIR / "fonts"
STYLES_DIR = RESOURCES_DIR / "styles"
ICONS_DIR = RESOURCES_DIR / "icons"
BRANDING_DIR = RESOURCES_DIR / "branding"

LOGO_SVG = BRANDING_DIR / "logo.svg"
LOGO_RASTER = BRANDING_DIR / "logo.webp"

#: Latin-free Arabic sans used by the Arabic interface chrome.
BUNDLED_FONT = FONTS_DIR / "IBMPlexSansArabic-Regular.ttf"
#: Urdu chrome face.  The reading face for Urdu stays Nastaliq, whose tall
#: strokes clip in 12 px menus; this one keeps the menu bar legible.
BUNDLED_URDU_FONT = FONTS_DIR / "NotoSansArabic-Regular.ttf"

_ICON_CANDIDATES = ("app-512.png", "app-256.png", "app-128.png", "app.png", "app.svg")


def resource_path(*parts: str) -> Path:
    return RESOURCES_DIR.joinpath(*parts)


def icon_file() -> Optional[Path]:
    for name in _ICON_CANDIDATES:
        candidate = ICONS_DIR / name
        if candidate.exists():
            return candidate
    return None


def application_icon():
    """Multi-resolution ``QIcon`` built from every bundled raster size.

    A single 512 px PNG would be downscaled by Qt for the taskbar and menus;
    handing Qt the exact sizes keeps small icons crisp.
    """
    from PySide6.QtGui import QIcon

    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256, 512):
        candidate = ICONS_DIR / f"app-{size}.png"
        if candidate.exists():
            icon.addFile(str(candidate))
    if icon.isNull():
        fallback = icon_file()
        if fallback is not None:
            icon = QIcon(str(fallback))
    return icon


_RASTER_SIZES = (16, 24, 32, 48, 64, 128, 256, 512)


def _pick_raster_icon(size: int) -> Optional[Path]:
    """Return the smallest bundled PNG at least *size* px, or the largest available."""
    for candidate_size in _RASTER_SIZES:
        if candidate_size >= size:
            candidate = ICONS_DIR / f"app-{candidate_size}.png"
            if candidate.exists():
                return candidate
    return icon_file()


def _scale_pixmap(pixmap, size: int):
    from PySide6.QtCore import Qt

    if pixmap.isNull() or size <= 0:
        return pixmap
    if pixmap.width() == size and pixmap.height() == size:
        return pixmap
    return pixmap.scaled(
        size,
        size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


def logo_pixmap(size: int = 128):
    """The brand mark as a ``QPixmap`` (vector first, crisp scaled raster fallback)."""
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QColor, QPainter, QPixmap

    if LOGO_SVG.exists():
        try:
            from PySide6.QtSvg import QSvgRenderer

            renderer = QSvgRenderer(str(LOGO_SVG))
            if renderer.isValid():
                pixmap = QPixmap(size, size)
                pixmap.fill(QColor("#5FC1EA"))
                painter = QPainter(pixmap)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                renderer.render(painter, QRectF(0, 0, size, size))
                painter.end()
                return pixmap
        except ImportError:  # pragma: no cover - PySide6 without QtSvg
            pass
    candidate = _pick_raster_icon(size)
    if candidate is not None and candidate.exists():
        return _scale_pixmap(QPixmap(str(candidate)), size)
    return QPixmap()


def icon_pixmap(size: int = 64):
    """Best available icon as a ``QPixmap`` scaled to *size* (empty if none is bundled)."""
    from PySide6.QtGui import QIcon, QPixmap

    path = _pick_raster_icon(size)
    if path is None:
        return QPixmap()
    if path.suffix == ".svg":
        icon = QIcon(str(path))
        return icon.pixmap(size, size)
    return _scale_pixmap(QPixmap(str(path)), size)


def stylesheet(theme: str) -> str:
    """Return the QSS for *theme* (``light`` or ``dark``), '' if missing.

    Qt resolves relative ``url()`` values against the process working
    directory, not the package, so sheets refer to resources through the
    ``@ICONS@`` token and we expand it to a real path here.
    """
    path = STYLES_DIR / f"{theme}.qss"
    if not path.exists():
        return ""
    qss = path.read_text(encoding="utf-8")
    return qss.replace("@ICONS@", ICONS_DIR.as_posix())


def available_fonts() -> List[Path]:
    if not FONTS_DIR.exists():
        return []
    return sorted(p for p in FONTS_DIR.iterdir()
                  if p.suffix.lower() in (".ttf", ".otf", ".ttc"))
