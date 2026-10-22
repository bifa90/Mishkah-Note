"""Windows 11-style status bar.

Layout (left → right in LTR chrome):
    Ln 1, Col 1   |  0 selected   |  100%   |  CRLF   |  UTF-8   |  ⟶ RTL
The direction chip is a button: clicking it cycles auto → rtl → ltr, which
gives the ``Ctrl+Shift`` chord a visible, discoverable equivalent.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QWidget

from mishkah.core.i18n import tr
from mishkah.core.text_direction import AUTO, LTR, RTL

#: A round glyph for "automatic" keeps the chip readable in both directions
#: (the old target-like mark read as "@" at 12 px).
_DIRECTION_ICONS = {AUTO: "◉", LTR: "→", RTL: "←"}
_DIRECTION_ORDER = (AUTO, RTL, LTR)


class StatusBarWidget(QFrame):
    direction_requested = Signal(str)   # emitted when the chip is clicked
    encoding_clicked = Signal()
    line_ending_clicked = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("StatusBar")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setFixedHeight(28)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(0)

        self._position = QLabel()
        self._selection = QLabel()
        self._lines = QLabel()
        self._size = QLabel()
        self._zoom = QLabel()
        self._line_ending = _Chip()
        self._encoding = _Chip()
        self._direction = _Chip()
        self._direction.setObjectName("DirectionChip")
        self._direction.setToolTip(tr("direction.hint"))

        for widget in (self._position, self._selection, self._lines, self._size):
            widget.setObjectName("StatusText")
            widget.setProperty("divider", False)
            layout.addWidget(widget)

        layout.addStretch(1)

        for chip in (self._zoom, self._line_ending, self._encoding, self._direction):
            layout.addWidget(chip)

        self._line_ending.clicked.connect(self.line_ending_clicked)
        self._encoding.clicked.connect(self.encoding_clicked)
        self._direction.clicked.connect(self._cycle_direction)

        self._direction_mode = AUTO
        self.set_position(1, 1, 0)
        self.set_lines(0)
        self.set_size("")
        self.set_zoom(100)
        self.set_line_ending("\n")
        self.set_encoding("utf-8")
        self.set_direction(AUTO, resolved=LTR)

    # ------------------------------------------------------------ updates
    def set_position(self, line: int, column: int, selection: int = 0) -> None:
        self._position.setText(tr("status.position", line=line, col=column))
        self._position.updateGeometry()
        self._selection.setText(tr("status.selection", chars=selection)
                                if selection else "")
        self._set_segment_visible(self._selection, bool(selection))

    def set_lines(self, count: int) -> None:
        self._lines.setText(tr("status.lines", count=f"{count:,}"))
        self._lines.updateGeometry()
        self._set_segment_visible(self._lines, count > 0)

    def set_size(self, label: str) -> None:
        self._size.setText(label)
        # The label grows from "0 B" to "1.2 MiB" while typing; without this the
        # segment keeps its old width and the unit gets clipped.
        self._size.updateGeometry()
        self._set_segment_visible(self._size, bool(label))

    @staticmethod
    def _set_segment_visible(label: QLabel, visible: bool) -> None:
        """Hide a segment *and* its separator (an empty label kept its border)."""
        label.setVisible(visible)
        if label.property("divider") == visible:
            return
        label.setProperty("divider", visible)
        style = label.style()
        style.unpolish(label)
        style.polish(label)

    def set_zoom(self, percent: int) -> None:
        self._zoom.setText(f"{percent}%")

    def set_line_ending(self, line_ending: str) -> None:
        self._line_ending.setText({"\r\n": "CRLF", "\r": "CR"}.get(line_ending, "LF"))

    def set_encoding(self, encoding: str) -> str:
        text = encoding.upper().replace("-SIG", " with BOM")
        self._encoding.setText(text)
        return text

    def set_direction(self, mode: str, resolved: Optional[str] = None) -> None:
        self._direction_mode = mode
        if mode == AUTO:
            shown = resolved or LTR
            self._direction.setText(f"{_DIRECTION_ICONS[AUTO]} {shown.upper()}")
        else:
            self._direction.setText(f"{_DIRECTION_ICONS[mode]} {mode.upper()}")

    def direction_mode(self) -> str:
        return self._direction_mode

    def _cycle_direction(self) -> None:
        index = _DIRECTION_ORDER.index(self._direction_mode)
        self.direction_requested.emit(_DIRECTION_ORDER[(index + 1) % len(_DIRECTION_ORDER)])

    def retranslate(self) -> None:
        self._direction.setToolTip(tr("direction.hint"))


class _Chip(QPushButton):
    """Flat, borderless button used for the status-bar segments."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("StatusChip")
        self.setFlat(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)
