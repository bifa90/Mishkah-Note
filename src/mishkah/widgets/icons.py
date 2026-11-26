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
