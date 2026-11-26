"""Small icons drawn with ``QPainter`` instead of loaded as glyphs.

The ``✕`` character looked fine in the source and empty in the window: the
font the user's desktop picked for the button had no glyph for it, so Qt drew
a tofu box.  Anything that must always look the same is therefore painted —
never typed.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QSize, Qt
from PySide6.QtGui import (
    QColor,
    QIcon,
    QPainter,
    QPen,
    QPixmap,
    QPolygonF,
    QRectF,
)


def cross_pixmap(size: int = 22, colour: str = "#B4B4B4",
                 width: float = 1.6, ratio: float = 2.0,
                 inset_ratio: float = 0.08) -> QPixmap:
    """A crisp ``×`` drawn at *ratio* times the requested size.

    Qt scales a high-DPI pixmap down for us, which keeps the two strokes sharp
    on every screen without a single glyph from the system font.
    """
    size = max(8, int(size))
    ratio = max(1.0, float(ratio))
    canvas = int(round(size * ratio))
    pixmap = QPixmap(canvas, canvas)
    pixmap.setDevicePixelRatio(ratio)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = QPen(QColor(colour))
    pen.setWidthF(width * ratio)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    inset = canvas * max(0.0, min(0.45, inset_ratio))
    painter.drawLine(QPointF(inset, inset), QPointF(canvas - inset, canvas - inset))
    painter.drawLine(QPointF(canvas - inset, inset), QPointF(inset, canvas - inset))
    painter.end()
    return pixmap


def cross_icon(size: int = 22, colour: str = "#B4B4B4") -> QIcon:
    """The same ``×`` as an :class:`QIcon`."""
    return QIcon(cross_pixmap(size, colour))


def themed_cross_icon(widget, size: int = 10) -> QIcon:
    """A ``×`` in the widget's own text colour (follows light/dark)."""
    from PySide6.QtGui import QPalette

    colour = widget.palette().color(QPalette.ColorRole.WindowText).name()
    return cross_icon(size, colour)


def close_button_stylesheet(radius: int, rest: str = "transparent") -> str:
    """A round, flat hover target for a small icon button."""
    return (
        "QPushButton {"
        f" border: none; border-radius: {radius}px; background: {rest}; }}"
        "QPushButton:hover { background: rgba(127, 127, 127, 60); }"
        "QPushButton:pressed { background: rgba(127, 127, 127, 110); }"
    )


def icon_size(size: int) -> QSize:  # pragma: no cover - convenience wrapper
    return QSize(size, size)


def document_pixmap(size: int = 14, colour: str = "#5C5C5C",
                    ratio: float = 2.0) -> QPixmap:
    """A page with a folded corner and two ruled lines.

    Drawn rather than shipped as an SVG: it must look identical in light and
    dark themes and at 14 px, which is exactly where a bitmap asset fails.
    """
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QPainterPath, QPolygonF

    size = max(8, int(size))
    canvas = int(round(size * ratio))
    pixmap = QPixmap(canvas, canvas)
    pixmap.setDevicePixelRatio(ratio)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    stroke = QColor(colour)
    pen = QPen(stroke)
    pen.setWidthF(1.25 * ratio)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    margin = canvas * 0.16
    fold = canvas * 0.30
    left = margin
    right = canvas - margin
    top = margin
    bottom = canvas - margin
    path = QPainterPath()
    path.moveTo(left, top)
    path.lineTo(right - fold, top)
    path.lineTo(right, top + fold)
    path.lineTo(right, bottom)
    path.lineTo(left, bottom)
    path.closeSubpath()
    painter.drawPath(path)
    painter.drawPolyline(QPolygonF([QPointF(right - fold, top),
                                    QPointF(right - fold, top + fold),
                                    QPointF(right, top + fold)]))
    painter.drawLine(QPointF(left + canvas * 0.14, canvas * 0.58),
                     QPointF(right - canvas * 0.14, canvas * 0.58))
    painter.drawLine(QPointF(left + canvas * 0.14, canvas * 0.74),
                     QPointF(right - canvas * 0.30, canvas * 0.74))
    painter.end()
    return pixmap


def document_icon(colour: str = "#5C5C5C", size: int = 14) -> QIcon:
    """The tab's document icon (CD-04)."""
    return QIcon(document_pixmap(size, colour))


# ---------------------------------------------------------------------------
# category icons (Settings)
# ---------------------------------------------------------------------------
#: Ink and accent per chrome, taken from the two stylesheets so a drawn icon is
#: never a guess: light = #3D3D3D on #F3F3F3, dark = #E4E4E4 on #202020.
#: The settings categories, in order — one list, so the icons and the pages
#: cannot drift apart.
CATEGORY_KEYS = (
    "appearance",
    "editor",
    "typing",
    "files",
    "tabs",
    "shortcuts",
    "advanced",
)

_INK = {"light": "#3D3D3D", "dark": "#E4E4E4"}
_ACCENT = {"light": "#0067C0", "dark": "#4CC2FF"}


def tinted_icon(icon: QIcon, colour: str, size: int = 18) -> QIcon:
    """*icon* flattened to one colour, for styles whose glyphs ignore the theme.

    Windows/Linux styles hand out pixmaps coloured for the *system* palette.  On
    a dark desktop with the light stylesheet those glyphs arrive near-white on
    white — the settings list read as empty rows (G3b follow-up).  Tinting keeps
    the shape and takes the colour from the theme that is actually painted.
    """
    if icon.isNull():
        return icon
    source = icon.pixmap(size, size)
    if source.isNull():
        return icon
    canvas = QPixmap(source.size())
    canvas.setDevicePixelRatio(source.devicePixelRatio())
    canvas.fill(Qt.GlobalColor.transparent)
    painter = QPainter(canvas)
    painter.drawPixmap(0, 0, source)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(canvas.rect(), QColor(colour))
    painter.end()
    return QIcon(canvas)


def category_pixmap(key: str, dark: bool = False, size: int = 18,
                    ratio: float = 2.0) -> QPixmap:
    """One settings category, drawn — ``appearance`` … ``advanced``."""
    ink = QColor(_INK["dark" if dark else "light"])
    accent = QColor(_ACCENT["dark" if dark else "light"])
    size = max(10, int(size))
    ratio = max(1.0, float(ratio))
    canvas = int(round(size * ratio))
    pixmap = QPixmap(canvas, canvas)
    pixmap.setDevicePixelRatio(ratio)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = QPen(ink)
    pen.setWidthF(1.3 * ratio)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    unit = canvas  # every coordinate below is a fraction of the square

    if key == "appearance":
        # A disc half filled with the accent: "light / dark".
        painter.drawEllipse(QPointF(unit / 2, unit / 2), unit * 0.34, unit * 0.34)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(accent)
        painter.drawChord(QRectF(unit * 0.16, unit * 0.16,
                                 unit * 0.68, unit * 0.68), 90 * 16, 180 * 16)
    elif key == "editor":
        painter.drawRoundedRect(QRectF(unit * 0.22, unit * 0.14,
                                       unit * 0.56, unit * 0.72),
                                unit * 0.08, unit * 0.08)
        for fraction in (0.34, 0.50, 0.66):
            painter.drawLine(QPointF(unit * 0.34, unit * fraction),
                             QPointF(unit * 0.66, unit * fraction))
    elif key == "typing":
        painter.drawLine(QPointF(unit * 0.50, unit * 0.22),
                         QPointF(unit * 0.50, unit * 0.62))
        painter.drawLine(QPointF(unit * 0.30, unit * 0.48),
                         QPointF(unit * 0.50, unit * 0.22))
        painter.drawLine(QPointF(unit * 0.70, unit * 0.48),
                         QPointF(unit * 0.50, unit * 0.22))
        pen.setColor(accent)
        painter.setPen(pen)
        painter.drawLine(QPointF(unit * 0.26, unit * 0.80),
                         QPointF(unit * 0.74, unit * 0.80))
    elif key == "files":
        painter.drawPolyline(QPolygonF([
            QPointF(unit * 0.16, unit * 0.72),
            QPointF(unit * 0.16, unit * 0.28),
            QPointF(unit * 0.42, unit * 0.28),
            QPointF(unit * 0.50, unit * 0.40),
            QPointF(unit * 0.84, unit * 0.40),
            QPointF(unit * 0.84, unit * 0.72),
            QPointF(unit * 0.16, unit * 0.72)]))
    elif key == "tabs":
        painter.drawRoundedRect(QRectF(unit * 0.16, unit * 0.24,
                                       unit * 0.46, unit * 0.34),
                                unit * 0.06, unit * 0.06)
        pen.setColor(accent)
        painter.setPen(pen)
        painter.drawRoundedRect(QRectF(unit * 0.38, unit * 0.44,
                                       unit * 0.46, unit * 0.34),
                                unit * 0.06, unit * 0.06)
    elif key == "shortcuts":
        painter.drawRoundedRect(QRectF(unit * 0.16, unit * 0.38,
                                       unit * 0.52, unit * 0.30),
                                unit * 0.10, unit * 0.10)
        painter.drawEllipse(QPointF(unit * 0.34, unit * 0.53), unit * 0.06, unit * 0.06)
        painter.drawLine(QPointF(unit * 0.48, unit * 0.53), QPointF(unit * 0.58, unit * 0.53))
        painter.drawLine(QPointF(unit * 0.68, unit * 0.50), QPointF(unit * 0.84, unit * 0.50))
        painter.drawLine(QPointF(unit * 0.78, unit * 0.50), QPointF(unit * 0.78, unit * 0.66))
        painter.drawLine(QPointF(unit * 0.86, unit * 0.50), QPointF(unit * 0.86, unit * 0.66))
    else:  # advanced: three sliders, the middle one on the accent
        for index, (fraction, knob) in enumerate(((0.28, 0.62), (0.50, 0.38),
                                                  (0.72, 0.70))):
            painter.setPen(QPen(ink, 1.3 * ratio))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawLine(QPointF(unit * 0.18, unit * fraction),
                             QPointF(unit * 0.82, unit * fraction))
            painter.setPen(QPen(accent if index == 1 else ink, 1.3 * ratio))
            painter.setBrush(ink)
            painter.drawEllipse(QPointF(unit * knob, unit * fraction),
                                unit * 0.075, unit * 0.075)
        painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.end()
    return pixmap


def category_icon(key: str, dark: bool = False, size: int = 18) -> QIcon:
    """The drawn category icon, theme-inked (see :func:`category_pixmap`)."""
    return QIcon(category_pixmap(key, dark, size))
