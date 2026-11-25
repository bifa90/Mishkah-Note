"""A small animated-free on/off switch (CD-01).

The user asked for the autosave control to look like a switch rather than a
checkbox: grey when off, green when on.  Painting it here keeps the look
identical on every platform and every theme, and avoids pulling in a style
dependency for one control.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

TRACK_OFF = QColor(150, 154, 160)
TRACK_ON = QColor(46, 160, 67)
KNOB = QColor(255, 255, 255)
BORDER = QColor(0, 0, 0, 40)

TRACK_WIDTH = 38
TRACK_HEIGHT = 20
KNOB_MARGIN = 2


class ToggleSwitch(QWidget):
    """A checkable switch: click, or press Space, to flip it."""

    toggled = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._checked = False
        self._hover = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFixedSize(QSize(TRACK_WIDTH, TRACK_HEIGHT))

    # ----------------------------------------------------------------- state
    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool, emit: bool = False) -> None:
        checked = bool(checked)
        if checked == self._checked:
            return
        self._checked = checked
        self.update()
        if emit:
            self.toggled.emit(checked)

    def toggle(self) -> None:
        self.setChecked(not self._checked, emit=True)

    def sizeHint(self) -> QSize:            # noqa: N802 - Qt naming
        return QSize(TRACK_WIDTH, TRACK_HEIGHT)

    # ----------------------------------------------------------------- paint
    def paintEvent(self, event) -> None:    # noqa: N802 - Qt naming
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        radius = TRACK_HEIGHT / 2
        track = QRectF(0.5, 0.5, TRACK_WIDTH - 1, TRACK_HEIGHT - 1)
        painter.setPen(QPen(BORDER, 1))
        painter.setBrush(TRACK_ON if self._checked else TRACK_OFF)
        painter.drawRoundedRect(track, radius, radius)

        knob_size = TRACK_HEIGHT - 2 * KNOB_MARGIN
        # Right-to-left interfaces put the "on" end on the other side, like
        # every native switch in an Arabic layout.
        rtl = self.layoutDirection() == Qt.LayoutDirection.RightToLeft
        on_left = self._checked != rtl
        x = KNOB_MARGIN if on_left else TRACK_WIDTH - KNOB_MARGIN - knob_size
        knob = QRectF(x, KNOB_MARGIN, knob_size, knob_size)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(KNOB)
        painter.drawEllipse(knob)
        painter.end()

    # ----------------------------------------------------------------- input
    def mouseReleaseEvent(self, event) -> None:   # noqa: N802 - Qt naming
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(
                event.position().toPoint()):
            self.toggle()
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:       # noqa: N802 - Qt naming
        if event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return,
                           Qt.Key.Key_Enter):
            self.toggle()
            event.accept()
            return
        super().keyPressEvent(event)

    def enterEvent(self, event) -> None:          # noqa: N802 - Qt naming
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:          # noqa: N802 - Qt naming
        self._hover = False
        self.update()
        super().leaveEvent(event)
