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

from mishkah.core.i18n import current_language, tr
from mishkah.core.syntax import display_name
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
        self._language = QLabel()
        self._words = QLabel()
        self._line_ending = _Chip()
        self._encoding = _Chip()
        self._direction = _Chip()
        self._direction.setObjectName("DirectionChip")
        self._direction.setToolTip(tr("direction.hint"))

        for widget in (self._position, self._selection, self._lines, self._size,
                       self._words, self._language):
            widget.setObjectName("StatusText")
            widget.setProperty("divider", False)
            layout.addWidget(widget)

        layout.addStretch(1)

        for chip in (self._zoom, self._line_ending, self._encoding, self._direction):
            layout.addWidget(chip)

        # Screen readers announce the *name*, sighted users read the text; the
        # description carries the current value so both say the same thing.
        self._encoding.setAccessibleName(tr("action.encoding"))
        self._line_ending.setAccessibleName(tr("menu.line_ending"))
        self._direction.setAccessibleName(tr("menu.direction"))
        self._zoom.setAccessibleName(tr("a11y.zoom"))
        self._zoom.setAccessibleDescription("100%")

        self._line_ending.clicked.connect(self.line_ending_clicked)
        self._encoding.clicked.connect(self.encoding_clicked)
        self._direction.clicked.connect(self._cycle_direction)

        # Every displayed value is remembered, because a language switch has to
        # re-render the *text* — the labels are built with tr() when they are
        # set, so a new language left the old words on screen while the tooltips
        # alone were refreshed (reported on the G3b gate: item 9).
        self._position_state = (1, 1, 0)
        self._line_count = 0
        self._size_label = ""
        self._word_count = 0
        self._language_code = ""
        self._language_label = ""
        self._zoom_percent = 100
        self._line_ending_mode = "\n"
        self._encoding_name = "utf-8"
        self._direction_state = (AUTO, LTR, None)

        self._direction_mode = AUTO
        self.set_position(1, 1, 0)
        self.set_lines(0)
        self.set_size("")
        self.set_words(0)
        self.set_zoom(100)
        self.set_line_ending("\n")
        self.set_encoding("utf-8")
        self.set_direction(AUTO, resolved=LTR)

    # ------------------------------------------------------------ updates
    def set_position(self, line: int, column: int, selection: int = 0) -> None:
        self._position_state = (line, column, selection)
        self._position.setText(tr("status.position", line=line, col=column))
        self._position.updateGeometry()
        self._selection.setText(tr("status.selection", chars=selection)
                                if selection else "")
        self._set_segment_visible(self._selection, bool(selection))

    def set_lines(self, count: int) -> None:
        self._line_count = count
        self._lines.setText(tr("status.lines", count=f"{count:,}"))
        self._lines.updateGeometry()
        self._set_segment_visible(self._lines, count > 0)

    def set_size(self, label: str) -> None:
        self._size_label = label
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

    def set_words(self, count: int) -> None:
        """Word count of the document (CD-23); hidden while it is zero."""
        self._word_count = count
        self._words.setText(tr("status.words", count=count) if count else "")
        self._set_segment_visible(self._words, bool(count))

    def set_language(self, label: str) -> None:
        """Which grammar is colouring this tab (empty hides the segment)."""
        self._language_code = ""
        self._language_label = label or ""
        self._language.setText(label or "")
        self._set_segment_visible(self._language, bool(label))

    def set_language_code(self, code: str) -> None:
        """Name the grammar by its *code*, so a language switch can re-name it.

        The label is a translated string (Arabic names for Arabic readers, the
        language's own name otherwise).  Storing the finished string meant that
        after switching the interface language the segment kept saying «بايثون»
        in an English window — the last thing on screen still in the old
        language.
        """
        self._language_code = code or ""
        self.set_language(self._language_name())

    def language_code(self) -> str:
        """The stored code (empty when no grammar is named)."""
        return self._language_code

    def _language_name(self) -> str:
        code = self._language_code
        if not code:
            return ""
        return display_name(code, current_language())

    def language_text(self) -> str:
        """The language segment as shown (empty when there is nothing to say)."""
        return self._language.text()

    def set_zoom(self, percent: int) -> None:
        self._zoom_percent = percent
        self._zoom.setText(f"{percent}%")
        self._zoom.setAccessibleDescription(f"{percent}%")

    def set_line_ending(self, line_ending: str) -> None:
        self._line_ending_mode = line_ending
        text = {"\r\n": "CRLF", "\r": "CR"}.get(line_ending, "LF")
        self._line_ending.setText(text)
        self._line_ending.setAccessibleDescription(text)

    def set_encoding(self, encoding: str) -> str:
        self._encoding_name = encoding
        text = encoding.upper().replace("-SIG", " with BOM")
        self._encoding.setText(text)
        self._encoding.setAccessibleDescription(text)
        return text

    def set_direction(self, mode: str, resolved: Optional[str] = None,
                      document: Optional[str] = None) -> None:
        """Show the caret paragraph, and the document's side when they differ.

        In auto mode the paragraph decides the *text order* while the document
        decides the *alignment*; saying only one of the two left the other
        looking like a bug.
        """
        self._direction_mode = mode
        self._direction_state = (mode, resolved, document)
        if mode != AUTO:
            self._direction.setText(f"{_DIRECTION_ICONS[mode]} {mode.upper()}")
            self._direction.setToolTip(tr("direction.hint"))
            return
        shown = resolved or LTR
        text = f"{_DIRECTION_ICONS[AUTO]} {shown.upper()}"
        if document and document != shown:
            text += " · " + tr("status.document_direction", direction=document.upper())
        self._direction.setText(text)
        self._direction.setToolTip(tr("direction.hint"))

    def tab_order(self) -> list:
        """The order Tab should visit the clickable chips in."""
        return [self._encoding, self._line_ending, self._direction]

    def direction_mode(self) -> str:
        return self._direction_mode

    def _cycle_direction(self) -> None:
        index = _DIRECTION_ORDER.index(self._direction_mode)
        self.direction_requested.emit(_DIRECTION_ORDER[(index + 1) % len(_DIRECTION_ORDER)])

    def retranslate(self) -> None:
        """Re-render every value in the new language.

        The labels are formatted when they are set, so refreshing only the
        tooltips left «Ln 1, Col 1 · 4 lines · 100%» in the previous language
        after a switch — the one thing on screen that stayed behind (G3b #9).
        """
        line, column, selection = self._position_state
        self.set_position(line, column, selection)
        self.set_lines(self._line_count)
        self.set_size(self._size_label)
        self.set_words(self._word_count)
        if self._language_code:
            self.set_language(self._language_name())
        else:
            self.set_language(self._language_label)
        self.set_zoom(self._zoom_percent)
        self.set_line_ending(self._line_ending_mode)
        self.set_encoding(self._encoding_name)
        mode, resolved, document = self._direction_state
        self.set_direction(mode, resolved=resolved, document=document)
        self._direction.setToolTip(tr("direction.hint"))
        self._encoding.setAccessibleName(tr("action.encoding"))
        self._line_ending.setAccessibleName(tr("menu.line_ending"))
        self._direction.setAccessibleName(tr("menu.direction"))
        self._zoom.setAccessibleName(tr("a11y.zoom"))


class _Chip(QPushButton):
    """Flat, borderless button used for the status-bar segments.

    The chips change the encoding, the line ending and the text direction, so
    a keyboard user has to be able to reach them: they take focus by Tab (never
    by click, which would steal the caret while typing) and each carries an
    accessible name plus the value it currently shows.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("StatusChip")
        self.setFlat(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)
