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

BUNDLED_FONT = FONTS_DIR / "IBMPlexSansArabic-Light.ttf"

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


def logo_pixmap(size: int = 128):
    """The brand mark as a ``QPixmap`` (vector first, raster fallback)."""
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
    required = ICONS_DIR / f"app-{size}.png"
    for candidate in (required, icon_file()):
        if candidate is not None and candidate.exists():
            return QPixmap(str(candidate))
    return QPixmap()


def icon_pixmap(size: int = 64):
    """Best available icon as a ``QPixmap`` (empty if none is bundled)."""
    from PySide6.QtGui import QIcon, QPixmap

    path = icon_file()
    if path is None:
        return QPixmap()
    if path.suffix == ".svg":
        icon = QIcon(str(path))
        return icon.pixmap(size, size)
    pixmap = QPixmap(str(path))
    if pixmap.isNull():
        return pixmap
    return pixmap


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
