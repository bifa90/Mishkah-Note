"""The welcome page: a tab that is not a document.

Closing the last tab shows this page instead of a blank document (CD-06),
and it is also what a fresh launch shows when there is nothing to restore.
It owns no state: it asks, the controller acts.

Two rules shape this file:

* **the brand block never translates.** The mark, the Arabic name, the English
  name and the version are the same in all ten interface languages — a product
  called *مفكرة مشكاة* does not become something else in Spanish.
* **everything else follows the reading direction.** Qt puts the buttons on the
  right in Arabic and Urdu by itself, but a ``QLabel`` defaults to a *physical*
  left alignment, so the title and the taglines used to stay pinned to the left
  edge of a right-to-left window. Labels are aligned from the layout direction
  and realigned whenever it changes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

from PySide6.QtCore import QEvent, Qt, Signal
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

from mishkah import APP_NAME, APP_NAME_AR, APP_VERSION
from mishkah.core import resources
from mishkah.core.i18n import tr

#: The bundled Arabic face: the brand is Arabic text, so it must not depend on
#: whichever interface font the active language selected.
BRAND_FACE = "IBM Plex Sans Arabic"


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

        # Two-column layout that mirrors automatically with layoutDirection:
        # in Arabic/Urdu (RTL) the brand & actions sit on the right and recent
        # files sit on the left; in English/LTR the two sides swap.
        outer = QHBoxLayout(self)
        outer.setContentsMargins(48, 36, 48, 32)
        outer.setSpacing(36)

        self.brand_pane = QWidget(self)
        self.brand_pane.setObjectName("HomeBrandPane")
        brand_layout = QVBoxLayout(self.brand_pane)
        brand_layout.setContentsMargins(0, 0, 0, 0)
        brand_layout.setSpacing(12)

        # --- the brand: logo, Arabic name, English name, version -----------
        # Deliberately untranslated; only its alignment follows the language.
        self.lbl_logo = QLabel()
        self.lbl_logo.setObjectName("HomeLogo")
        pixmap = resources.logo_pixmap(72)
        if not pixmap.isNull():
            # No fixed size: the label spans the column and its alignment puts
            # the mark on the reading edge, together with the names under it.
            self.lbl_logo.setPixmap(pixmap)
            self.lbl_logo.setMinimumHeight(pixmap.height())
        self.lbl_logo.setAccessibleName(APP_NAME_AR)

        self.lbl_name_ar = QLabel(APP_NAME_AR)
        self.lbl_name_ar.setObjectName("HomeNameAr")
        name_font = QFont(BRAND_FACE)
        name_font.setPointSize(max(22, self.font().pointSize() + 12))
        name_font.setBold(True)
        self.lbl_name_ar.setFont(name_font)

        self.lbl_name_en = QLabel(APP_NAME)
        self.lbl_name_en.setObjectName("HomeNameEn")
        english_font = QFont(self.font())
        english_font.setPointSize(max(11, self.font().pointSize() + 2))
        self.lbl_name_en.setFont(english_font)

        self.lbl_version = QLabel()
        self.lbl_version.setObjectName("HomeVersion")
        version_font = QFont(self.font())
        version_font.setPointSize(max(9, self.font().pointSize() - 1))
        self.lbl_version.setFont(version_font)

        for widget in (self.lbl_logo, self.lbl_name_ar, self.lbl_name_en,
                       self.lbl_version):
            brand_layout.addWidget(widget)
        brand_layout.addSpacing(6)

        self.lbl_tagline = QLabel()
        self.lbl_tagline.setObjectName("HomeTagline")
        self.lbl_tagline.setWordWrap(True)
        brand_layout.addWidget(self.lbl_tagline)
        brand_layout.addSpacing(10)

        # --- the two first steps --------------------------------------
        row = QHBoxLayout()
        row.setSpacing(10)
        self.btn_new = QPushButton()
        self.btn_new.setObjectName("HomeNew")
        self.btn_new.setDefault(True)
        self.btn_new.setMinimumHeight(38)
        self.btn_new.clicked.connect(self.new_requested.emit)

        self.btn_open = QPushButton()
        self.btn_open.setObjectName("HomeOpen")
        self.btn_open.setMinimumHeight(38)
        self.btn_open.clicked.connect(self.open_requested.emit)

        for button in (self.btn_new, self.btn_open):
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            row.addWidget(button)
        row.addStretch(1)
        brand_layout.addLayout(row)
        brand_layout.addStretch(1)

        # --- quick actions --------------------------------------------
        quick = QHBoxLayout()
        quick.setSpacing(8)
        self.btn_settings = QPushButton()
        self.btn_settings.setObjectName("HomeSettings")
        self.btn_settings.clicked.connect(self.settings_requested.emit)
        self.btn_help = QPushButton()
        self.btn_help.setObjectName("HomeHelp")
        self.btn_help.clicked.connect(self.help_requested.emit)
        self.btn_restore = QPushButton()
        self.btn_restore.setObjectName("HomeRestore")
        self.btn_restore.clicked.connect(self.restore_requested.emit)
        self.btn_restore.hide()
        for button in (self.btn_settings, self.btn_help, self.btn_restore):
            button.setFlat(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            quick.addWidget(button)
        quick.addStretch(1)
        brand_layout.addLayout(quick)

        # --- recent files (opposite side of the page) -----------------
        self.recent_pane = QFrame(self)
        self.recent_pane.setObjectName("HomeRecentPane")
        self.recent_pane.setFrameShape(QFrame.Shape.NoFrame)
        recent_layout = QVBoxLayout(self.recent_pane)
        recent_layout.setContentsMargins(20, 18, 20, 18)
        recent_layout.setSpacing(10)

        self.lbl_recent = QLabel()
        self.lbl_recent.setObjectName("HomeRecentLabel")
        recent_font = QFont(self.font())
        recent_font.setBold(True)
        self.lbl_recent.setFont(recent_font)
        recent_layout.addWidget(self.lbl_recent)

        self.list_recent = QListWidget()
        self.list_recent.setObjectName("HomeRecent")
        self.list_recent.setFrameShape(QFrame.Shape.NoFrame)
        self.list_recent.setAlternatingRowColors(False)
        self.list_recent.itemActivated.connect(self._open_item)
        self.list_recent.itemClicked.connect(self._open_item)
        recent_layout.addWidget(self.list_recent, 1)

        self.lbl_empty = QLabel()
        self.lbl_empty.setObjectName("HomeEmptyNote")
        self.lbl_empty.setWordWrap(True)
        recent_layout.addWidget(self.lbl_empty, 1)

        outer.addWidget(self.brand_pane, 5)
        outer.addWidget(self.recent_pane, 4)

        self.set_recent_files([])
        self.retranslate()

    # ---------------------------------------------------------------- api
    def retranslate(self) -> None:
        """Re-read every translatable string — the page lives across a switch."""
        self.lbl_version.setText(tr("about.version", version=APP_VERSION))
        self.lbl_tagline.setText(tr("home.tagline"))
        self.btn_new.setText(tr("home.new"))
        self.btn_open.setText(tr("home.open"))
        self.lbl_recent.setText(tr("home.recent"))
        self.lbl_empty.setText(tr("home.recent_empty"))
        self.btn_settings.setText(tr("home.settings"))
        self.btn_help.setText(tr("home.help"))
        self.btn_restore.setText(tr("home.restore"))
        self._align_to_direction()

    def brand(self) -> List[QLabel]:
        """The four untranslated widgets, in the order they are stacked."""
        return [self.lbl_logo, self.lbl_name_ar, self.lbl_name_en, self.lbl_version]

    def set_recent_files(self, paths: Iterable[str]) -> None:
        """Show the recent files that still exist, newest first."""
        seen: List[str] = []
        self.list_recent.clear()
        alignment = self._reading_alignment()
        for raw in paths:
            path = Path(raw)
            if not path.exists() or str(path) in seen:
                continue
            seen.append(str(path))
            item = QListWidgetItem(path.name)
            item.setToolTip(str(path))
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            item.setTextAlignment(alignment)
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
    def _reading_alignment(self, *, top: bool = False) -> Qt.AlignmentFlag:
        rtl = self.layoutDirection() == Qt.LayoutDirection.RightToLeft
        edge = Qt.AlignmentFlag.AlignRight if rtl else Qt.AlignmentFlag.AlignLeft
        vertical = Qt.AlignmentFlag.AlignTop if top else Qt.AlignmentFlag.AlignVCenter
        return edge | Qt.AlignmentFlag.AlignAbsolute | vertical

    def _align_to_direction(self) -> None:
        """Pin the text to the reading edge, physically.

        ``AlignAbsolute`` is the whole trick: in a right-to-left widget Qt
        *mirrors* ``AlignRight`` for right-to-left text, so an Arabic name
        labelled "right" was drawn on the left while the English name beside it
        stayed on the right.  Asking for an absolute edge removes the guesswork.
        """
        alignment = self._reading_alignment()
        top_alignment = self._reading_alignment(top=True)
        for widget in (self.lbl_logo, self.lbl_name_ar, self.lbl_name_en,
                       self.lbl_version, self.lbl_tagline, self.lbl_recent):
            widget.setAlignment(alignment)
        self.lbl_empty.setAlignment(top_alignment)
        for index in range(self.list_recent.count()):
            item = self.list_recent.item(index)
            if item is not None:
                item.setTextAlignment(alignment)

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt naming)
        # The window flips direction when the interface language changes; the
        # labels have to flip with it, without the controller remembering to ask.
        if event.type() == QEvent.Type.LayoutDirectionChange:
            self._align_to_direction()
        super().changeEvent(event)

    def _open_item(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.ItemDataRole.UserRole)
        if path:
            self.recent_requested.emit(str(path))
