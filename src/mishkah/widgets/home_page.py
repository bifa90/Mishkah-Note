"""The welcome page: a tab that is not a document.

Closing the last tab shows this page instead of a blank document (CD-06),
and it is also what a fresh launch shows when there is nothing to restore.
It owns no state: it asks, the controller acts.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from mishkah import APP_NAME
from mishkah.core.i18n import tr


class HomePage(QWidget):
    """Welcome page with the two first steps, recent files and shortcuts."""

    new_requested = Signal()
    open_requested = Signal()
    recent_requested = Signal(str)      # absolute path
    settings_requested = Signal()
    help_requested = Signal()
    restore_requested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("HomePage")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(48, 40, 48, 32)
        outer.setSpacing(14)

        title = QLabel(APP_NAME)
        title.setObjectName("HomeTitle")
        title_font = QFont(title.font())
        title_font.setPointSize(max(20, title_font.pointSize() + 12))
        title_font.setBold(True)
        title.setFont(title_font)
        outer.addWidget(title)

        tagline = QLabel(tr("home.tagline"))
        tagline.setObjectName("HomeTagline")
        tagline.setWordWrap(True)
        outer.addWidget(tagline)
        outer.addSpacing(10)

        # --- the two first steps --------------------------------------
        row = QHBoxLayout()
        row.setSpacing(10)
        self.btn_new = QPushButton(tr("home.new"))
        self.btn_new.setObjectName("HomeNew")
        self.btn_new.setDefault(True)
        self.btn_new.setMinimumHeight(38)
        self.btn_new.clicked.connect(self.new_requested.emit)

        self.btn_open = QPushButton(tr("home.open"))
        self.btn_open.setObjectName("HomeOpen")
        self.btn_open.setMinimumHeight(38)
        self.btn_open.clicked.connect(self.open_requested.emit)

        for button in (self.btn_new, self.btn_open):
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            row.addWidget(button)
        row.addStretch(1)
        outer.addLayout(row)
        outer.addSpacing(12)

        # --- recent files ---------------------------------------------
        self.lbl_recent = QLabel(tr("home.recent"))
        self.lbl_recent.setObjectName("HomeRecentLabel")
        recent_font = QFont(self.lbl_recent.font())
        recent_font.setBold(True)
        self.lbl_recent.setFont(recent_font)
        outer.addWidget(self.lbl_recent)

        self.list_recent = QListWidget()
        self.list_recent.setObjectName("HomeRecent")
        self.list_recent.setFrameShape(QFrame.Shape.NoFrame)
        self.list_recent.setAlternatingRowColors(False)
        self.list_recent.itemActivated.connect(self._open_item)
        self.list_recent.itemClicked.connect(self._open_item)
        outer.addWidget(self.list_recent, 1)

        self.lbl_empty = QLabel(tr("home.recent_empty"))
        self.lbl_empty.setObjectName("HomeEmptyNote")
        self.lbl_empty.setWordWrap(True)
        outer.addWidget(self.lbl_empty)

        # --- quick actions --------------------------------------------
        quick = QHBoxLayout()
        quick.setSpacing(8)
        self.btn_settings = QPushButton(tr("home.settings"))
        self.btn_settings.setObjectName("HomeSettings")
        self.btn_settings.clicked.connect(self.settings_requested.emit)
        self.btn_help = QPushButton(tr("home.help"))
        self.btn_help.setObjectName("HomeHelp")
        self.btn_help.clicked.connect(self.help_requested.emit)
        self.btn_restore = QPushButton(tr("home.restore"))
        self.btn_restore.setObjectName("HomeRestore")
        self.btn_restore.clicked.connect(self.restore_requested.emit)
        self.btn_restore.hide()
        for button in (self.btn_settings, self.btn_help, self.btn_restore):
            button.setFlat(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            quick.addWidget(button)
        quick.addStretch(1)
        outer.addLayout(quick)

        self.set_recent_files([])

    # ---------------------------------------------------------------- api
    def set_recent_files(self, paths: Iterable[str]) -> None:
        """Show the recent files that still exist, newest first."""
        seen: List[str] = []
        self.list_recent.clear()
        for raw in paths:
            path = Path(raw)
            if not path.exists() or str(path) in seen:
                continue
            seen.append(str(path))
            item = QListWidgetItem(path.name)
            item.setToolTip(str(path))
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            self.list_recent.addItem(item)
        has_any = bool(seen)
        self.list_recent.setVisible(has_any)
        self.lbl_empty.setVisible(not has_any)

    def set_restore_available(self, available: bool) -> None:
        """Offer session restore only when there is a session to restore."""
        self.btn_restore.setVisible(bool(available))

    def recent_paths(self) -> List[str]:
        return [self.list_recent.item(i).data(Qt.ItemDataRole.UserRole)
                for i in range(self.list_recent.count())]

    # ------------------------------------------------------------ private
    def _open_item(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.ItemDataRole.UserRole)
        if path:
            self.recent_requested.emit(str(path))
