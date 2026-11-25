"""Small icons drawn with ``QPainter`` instead of loaded as glyphs.

The ``✕`` character looked fine in the source and empty in the window: the
font the user's desktop picked for the button had no glyph for it, so Qt drew
a tofu box.  Anything that must always look the same is therefore painted —
never typed.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap


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
