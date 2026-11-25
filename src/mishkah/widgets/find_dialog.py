"""Windows 11-style find/replace flyout (modeless, docked top-right)."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from mishkah.core.i18n import tr
from mishkah.widgets.icons import close_button_stylesheet, cross_icon, themed_cross_icon

#: How long typing in the find field has to pause before the search runs.
INCREMENTAL_MS = 180


class FindReplaceBar(QFrame):
    find_requested = Signal(str, bool)      # needle, backward
    incremental_requested = Signal(str)     # needle, as you type (CD-11)
    replace_requested = Signal(str, str)    # needle, replacement
    replace_all_requested = Signal(str, str)
    closed = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("FindBar")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._visible_mode = False

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 8, 12, 8)
        root.setSpacing(6)

        # ---- row 1: find ---------------------------------------------------
        row1 = QHBoxLayout()
        row1.setSpacing(6)
        self.find_edit = QLineEdit()
        self.find_edit.setPlaceholderText(tr("find.what"))
        self.find_edit.setClearButtonEnabled(True)
        self.find_edit.returnPressed.connect(self.find_next)
        self._find_prev = QPushButton(tr("find.previous"))
        self._find_next = QPushButton(tr("find.next"))
        # Painted, not typed: "✕" renders as an empty box on fonts that lack
        # the glyph (the same bug the banner's dismiss button had).
        self._close = QPushButton()
        self._close.setObjectName("CloseButton")
        self._close.setText("")
        self._close.setIcon(cross_icon(10))
        self._close.setIconSize(QSize(10, 10))
        self._close.setFixedSize(24, 24)
        self._close.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close.setStyleSheet(close_button_stylesheet(12))
        self._close.setToolTip(tr("dialog.close"))
        if not self._close.icon().isNull():
            self._close.setIcon(themed_cross_icon(self, 10))
        row1.addWidget(QLabel(tr("find.what")))
        row1.addWidget(self.find_edit, 1)
        row1.addWidget(self._find_prev)
        row1.addWidget(self._find_next)
        row1.addWidget(self._close)
        root.addLayout(row1)

        # ---- row 2: replace ------------------------------------------------
        self._replace_row = QWidget()
        row2 = QHBoxLayout(self._replace_row)
        row2.setContentsMargins(0, 0, 0, 0)
        row2.setSpacing(6)
        self.replace_edit = QLineEdit()
        self.replace_edit.setPlaceholderText(tr("find.replace_with"))
        self._replace = QPushButton(tr("find.replace"))
        self._replace_all = QPushButton(tr("find.replace_all"))
        row2.addWidget(QLabel(tr("find.replace_with")))
        row2.addWidget(self.replace_edit, 1)
        row2.addWidget(self._replace)
        row2.addWidget(self._replace_all)
        root.addWidget(self._replace_row)
        self._replace_row.setVisible(False)

        # ---- row 3: options ------------------------------------------------
        row3 = QHBoxLayout()
        row3.setSpacing(14)
        self.match_case = QCheckBox(tr("find.match_case"))
        self.whole_word = QCheckBox(tr("find.whole_word"))
        self.use_regex = QCheckBox(tr("find.regex"))
        self.wrap = QCheckBox(tr("find.wrap_around"))
        self.wrap.setChecked(True)
        self._incremental = QTimer(self)
        self._incremental.setSingleShot(True)
        self._incremental.setInterval(INCREMENTAL_MS)
        self._incremental.timeout.connect(self._emit_incremental)
        self.find_edit.textChanged.connect(self._incremental.start)
        self.match_case.stateChanged.connect(self._restart_incremental)
        self.whole_word.stateChanged.connect(self._restart_incremental)
        self.use_regex.stateChanged.connect(self._restart_incremental)

        self._toggle_replace = QPushButton(tr("action.replace"))
        self._toggle_replace.setCheckable(True)
        for widget in (self.match_case, self.whole_word, self.use_regex, self.wrap):
            row3.addWidget(widget)
        row3.addStretch(1)
        row3.addWidget(self._toggle_replace)
        root.addLayout(row3)

        # ---- wiring --------------------------------------------------------
        self._find_prev.clicked.connect(self.find_previous)
        self._find_next.clicked.connect(self.find_next)
        self._close.clicked.connect(self.hide_bar)
        self._replace.clicked.connect(self._on_replace)
        self._replace_all.clicked.connect(self._on_replace_all)
        self._toggle_replace.toggled.connect(self._on_toggle_replace)

    # ------------------------------------------------------------- options
    def options(self) -> dict:
        return {
            "case_sensitive": self.match_case.isChecked(),
            "whole_word": self.whole_word.isChecked(),
            "regex": self.use_regex.isChecked(),
            "wrap": self.wrap.isChecked(),
        }

    # ------------------------------------------------------------- actions
    def show_bar(self, replace_mode: bool = False, seed: str = "") -> None:
        self._toggle_replace.setChecked(replace_mode)
        if seed:
            self.find_edit.setText(seed)
        self.show()
        self.raise_()
        self.find_edit.setFocus()
        self.find_edit.selectAll()

    def hide_bar(self) -> None:
        self._incremental.stop()
        self.set_match_state(True)
        self.hide()
        self.closed.emit()

    # ----------------------------------------------------------- incremental
    def _restart_incremental(self, *_args) -> None:
        if self.isVisible() and self.find_edit.text():
            self._incremental.start()

    def _emit_incremental(self) -> None:
        needle = self.find_edit.text()
        if needle:
            self.incremental_requested.emit(needle)

    def set_match_state(self, found: bool) -> None:
        """Colour the placeholder side of the field, never the text itself."""
        self.find_edit.setProperty("noMatch", "true" if not found else "false")
        self.find_edit.style().unpolish(self.find_edit)
        self.find_edit.style().polish(self.find_edit)

    def find_next(self) -> None:
        self.find_requested.emit(self.find_edit.text(), False)

    def find_previous(self) -> None:
        self.find_requested.emit(self.find_edit.text(), True)

    def _on_replace(self) -> None:
        self.replace_requested.emit(self.find_edit.text(), self.replace_edit.text())

    def _on_replace_all(self) -> None:
        self.replace_all_requested.emit(self.find_edit.text(), self.replace_edit.text())

    def _on_toggle_replace(self, checked: bool) -> None:
        self._replace_row.setVisible(checked)
        if checked:
            self.replace_edit.setFocus()

    def replace_mode(self) -> bool:
        return self._toggle_replace.isChecked()

    # ------------------------------------------------------------- a11y
    def retranslate(self) -> None:
        self.find_edit.setPlaceholderText(tr("find.what"))
        self.replace_edit.setPlaceholderText(tr("find.replace_with"))
        self._find_prev.setText(tr("find.previous"))
        self._find_next.setText(tr("find.next"))
        self._replace.setText(tr("find.replace"))
        self._replace_all.setText(tr("find.replace_all"))
        self.match_case.setText(tr("find.match_case"))
        self.whole_word.setText(tr("find.whole_word"))
        self.use_regex.setText(tr("find.regex"))
        self.wrap.setText(tr("find.wrap_around"))
        self._toggle_replace.setText(tr("action.replace"))
        self._close.setToolTip(tr("dialog.close"))
        if not self._close.icon().isNull():
            self._close.setIcon(themed_cross_icon(self, 10))

    def keyPressEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        if event.key() == Qt.Key.Key_Escape:
            self.hide_bar()
            return
        super().keyPressEvent(event)
