"""Main window — Windows 11 Notepad layout.

    ┌──────────────────────────────────────────────────────────────┐
    │ File  Edit  View  …            (menubar, 32 px, no border)    │
    │ ┌ Untitled ●┐ ┌ notes.txt ┐ +                                 │
    │ ├───────────┴─┴───────────┴───────────────────────────────┤  │
    │ │                                                     [find]│  │
    │ │  text area                                              │  │
    │ ├───────────────────────────────────────────────────────────┤  │
    │ │ Ln 1, Col 1      100%  CRLF  UTF-8  → LTR                 │  │
    └──────────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QAction, QActionGroup, QDesktopServices, QFont, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QTabBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from mufakkira import PROJECT_URL
from mufakkira.core.i18n import tr
from mufakkira.core.languages import language_choices
from mufakkira.core.text_direction import AUTO, LTR, RTL
from mufakkira.models.document import DocumentModel
from mufakkira.views.editor_view import EditorView
from mufakkira.views.status_bar_widget import StatusBarWidget
from mufakkira.widgets.find_dialog import FindReplaceBar

ENCODINGS = (
    "utf-8", "utf-8-sig", "utf-16-le", "utf-16-be", "utf-32",
    "windows-1256", "windows-1252", "iso-8859-6", "iso-8859-1",
    "cp720", "ascii",
)


class TabBar(QTabBar):
    """Fluent-style tab bar: compact, closable, with a '+' button."""

    new_tab_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setExpanding(False)
        self.setDrawBase(False)
        self.setTabsClosable(True)
        self.setMovable(True)
        self.setDocumentMode(True)
        self.setElideMode(Qt.TextElideMode.ElideRight)
        self.setSelectionBehaviorOnRemove(
            QTabBar.SelectionBehavior.SelectPreviousTab)
        self.setUsesScrollButtons(True)


class MainWindow(QMainWindow):
    # ------------------------------------------------------------- signals
    file_new = Signal()
    file_open = Signal()
    file_save = Signal()
    file_save_as = Signal()
    file_save_all = Signal()
    file_print = Signal()
    tab_close_requested = Signal(int)
    tab_changed = Signal(int)
    direction_changed = Signal(str)
    language_changed = Signal(str)
    theme_changed = Signal(str)
    word_wrap_toggled = Signal(bool)
    line_numbers_toggled = Signal(bool)
    status_bar_toggled = Signal(bool)
    encoding_chosen = Signal(str)
    line_ending_chosen = Signal(str)
    zoom_changed_by_user = Signal(int)
    about_requested = Signal()
    settings_requested = Signal()
    recent_chosen = Signal(str)
    recent_cleared = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("MainWindow")
        self.setWindowTitle(tr("app.name"))
        self.resize(1080, 720)
        self.setUnifiedTitleAndToolBarOnMac(True)

        central = QWidget(self)
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---- tabs ----------------------------------------------------------
        self.tabs = QTabWidget(self)
        self.tabs.setTabBar(TabBar(self))
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.setDocumentMode(True)
        self.tabs.tabCloseRequested.connect(self.tab_close_requested)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        root.addWidget(self.tabs, 1)

        # ---- find/replace flyout ------------------------------------------
        self.find_bar = FindReplaceBar(self)
        self.find_bar.hide()
        root.addWidget(self.find_bar, 0)

        # ---- status bar ----------------------------------------------------
        self.status = StatusBarWidget(self)
        self.setStatusBar(None)
        root.addWidget(self.status, 0)

        # ---- banners -------------------------------------------------------
        self.banner = QLabel(self)
        self.banner.setObjectName("Banner")
        self.banner.setWordWrap(True)
        self.banner.hide()
        root.insertWidget(0, self.banner)

        self._build_menus()

    # ==================================================================
    # menus
    # ==================================================================
    def _build_menus(self) -> None:
        bar = self.menuBar()
        bar.setObjectName("MenuBar")

        # ---- File ----------------------------------------------------------
        m_file = bar.addMenu(tr("menu.file"))
        self.act_new = self._action(m_file, tr("menu.file.new"), self.file_new,
                                    QKeySequence.StandardKey.New)
        self.act_new_window = self._action(m_file, tr("menu.file.new_window"),
                                           self.file_new, "Ctrl+Shift+N")
        m_file.addSeparator()
        self.act_open = self._action(m_file, tr("menu.file.open"), self.file_open,
                                     QKeySequence.StandardKey.Open)
        self.menu_recent = m_file.addMenu(tr("menu.file.recent"))
        self.menu_recent.aboutToShow.connect(self._populate_recent)
        m_file.addSeparator()
        self.act_save = self._action(m_file, tr("menu.file.save"), self.file_save,
                                     QKeySequence.StandardKey.Save)
        self.act_save_as = self._action(m_file, tr("menu.file.save_as"),
                                        self.file_save_as,
                                        QKeySequence.StandardKey.SaveAs)
        self.act_save_all = self._action(m_file, tr("menu.file.save_all"),
                                         self.file_save_all, "Ctrl+Alt+S")
        m_file.addSeparator()
        self.act_print = self._action(m_file, tr("menu.file.print"),
                                      self.file_print, QKeySequence.StandardKey.Print)
        m_file.addSeparator()
        self.act_close_tab = self._action(m_file, tr("menu.file.close_tab"),
                                          lambda: self.tab_close_requested.emit(
                                              self.tabs.currentIndex()),
                                          QKeySequence.StandardKey.Close)

        # ---- Edit ----------------------------------------------------------
        m_edit = bar.addMenu(tr("menu.edit"))
        self.act_undo = self._action(m_edit, tr("action.undo"), None,
                                     QKeySequence.StandardKey.Undo)
        self.act_redo = self._action(m_edit, tr("action.redo"), None,
                                     QKeySequence.StandardKey.Redo)
        m_edit.addSeparator()
        self.act_cut = self._action(m_edit, tr("action.cut"), None,
                                    QKeySequence.StandardKey.Cut)
        self.act_copy = self._action(m_edit, tr("action.copy"), None,
                                     QKeySequence.StandardKey.Copy)
        self.act_paste = self._action(m_edit, tr("action.paste"), None,
                                      QKeySequence.StandardKey.Paste)
        self.act_delete = self._action(m_edit, tr("action.delete"), None, "Del")
        m_edit.addSeparator()
        self.act_find = self._action(m_edit, tr("action.find"), None,
                                     QKeySequence.StandardKey.Find)
        self.act_replace = self._action(m_edit, tr("action.replace"), None,
                                        QKeySequence.StandardKey.Replace)
        self.act_goto = self._action(m_edit, tr("action.goto"), None, "Ctrl+G")
        self.act_select_all = self._action(m_edit, tr("action.select_all"), None,
                                           QKeySequence.StandardKey.SelectAll)
        m_edit.addSeparator()
        self.act_date_time = self._action(m_edit, tr("action.date_time"), None, "F5")

        # ---- View ----------------------------------------------------------
        m_view = bar.addMenu(tr("menu.view"))
        self.act_zoom_in = self._action(m_view, tr("action.zoom_in"), None, "Ctrl++")
        self.act_zoom_out = self._action(m_view, tr("action.zoom_out"), None, "Ctrl+-")
        self.act_zoom_reset = self._action(m_view, tr("action.zoom_reset"), None,
                                           "Ctrl+0")
        m_view.addSeparator()
        self.act_status_bar = self._action(m_view, tr("action.status_bar"), None,
                                           checkable=True, checked=True)
        self.act_status_bar.toggled.connect(self.status_bar_toggled)
        self.act_word_wrap = self._action(m_view, tr("action.word_wrap"), None,
                                          checkable=True, checked=True)
        self.act_word_wrap.toggled.connect(self.word_wrap_toggled)
        self.act_line_numbers = self._action(m_view, tr("action.line_numbers"), None,
                                             checkable=True, checked=False)
        self.act_line_numbers.toggled.connect(self.line_numbers_toggled)
        m_view.addSeparator()
        self.act_settings = self._action(m_view, tr("settings.title"),
                                         self.settings_requested, "Ctrl+,")

        # ---- Format --------------------------------------------------------
        m_format = bar.addMenu(tr("menu.format"))
        self.menu_direction = m_format.addMenu(tr("menu.direction"))
        self.direction_group = QActionGroup(self)
        self.direction_group.setExclusive(True)
        self.act_dir_auto = self._action(self.menu_direction, tr("direction.auto"),
                                         lambda: self.direction_changed.emit(AUTO),
                                         "Ctrl+Shift+A", checkable=True, checked=True,
                                         group=self.direction_group)
        self.act_dir_rtl = self._action(self.menu_direction, tr("direction.rtl"),
                                        lambda: self.direction_changed.emit(RTL),
                                        "Ctrl+Shift+R", checkable=True,
                                        group=self.direction_group)
        self.act_dir_ltr = self._action(self.menu_direction, tr("direction.ltr"),
                                        lambda: self.direction_changed.emit(LTR),
                                        "Ctrl+Shift+L", checkable=True,
                                        group=self.direction_group)
        hint = self.menu_direction.addAction(tr("direction.hint"))
        hint.setEnabled(False)

        m_format.addSeparator()
        self.menu_language = m_format.addMenu(tr("menu.language"))
        self.language_group = QActionGroup(self)
        self.language_group.setExclusive(True)
        self._language_actions = {}
        for code, label in language_choices():
            action = self._action(self.menu_language, label,
                                  lambda _=False, c=code: self.language_changed.emit(c),
                                  checkable=True, group=self.language_group)
            self._language_actions[code] = action

        m_format.addSeparator()
        self.menu_encoding = m_format.addMenu(tr("action.encoding"))
        self.encoding_group = QActionGroup(self)
        self.encoding_group.setExclusive(True)
        for encoding in ENCODINGS:
            self._action(self.menu_encoding, encoding.upper(),
                         lambda _=False, e=encoding: self.encoding_chosen.emit(e),
                         checkable=True, group=self.encoding_group)

        self.menu_line_ending = m_format.addMenu(tr("menu.line_ending"))
        self.line_ending_group = QActionGroup(self)
        self.line_ending_group.setExclusive(True)
        for value, label in (("\r\n", "CRLF (Windows)"), ("\n", "LF (Unix)"),
                             ("\r", "CR (Macintosh)")):
            self._action(self.menu_line_ending, label,
                         lambda _=False, v=value: self.line_ending_chosen.emit(v),
                         checkable=True, group=self.line_ending_group)

        # ---- Help ----------------------------------------------------------
        m_help = bar.addMenu(tr("menu.help"))
        self.act_about = self._action(m_help, tr("action.about"), self.about_requested,
                                      "F1")
        source = self._action(m_help, tr("about.source"), None)
        source.triggered.connect(
            lambda: QDesktopServices.openUrl(QUrl(PROJECT_URL)))

    def _action(self, menu: QMenu, text: str, slot, shortcut=None,
                checkable: bool = False, checked: bool = False,
                group: Optional[QActionGroup] = None) -> QAction:
        action = QAction(text, self)
        if shortcut is not None:
            action.setShortcut(shortcut)
        if checkable:
            action.setCheckable(True)
            action.setChecked(checked)
        if group is not None:
            group.addAction(action)
        if slot is not None:
            action.triggered.connect(slot)
        menu.addAction(action)
        return action

    def _populate_recent(self) -> None:
        self.menu_recent.clear()
        for path in self._recent:
            action = self.menu_recent.addAction(path)
            action.triggered.connect(
                lambda _=False, p=path: self.recent_chosen.emit(p))
        self.menu_recent.addSeparator()
        clear = self.menu_recent.addAction(tr("menu.file.recent.clear"))
        clear.setEnabled(bool(self._recent))
        clear.triggered.connect(self.recent_cleared)

    # ==================================================================
    # tab helpers
    # ==================================================================
    _recent: List[str] = []

    def set_recent_files(self, paths: List[str]) -> None:
        self._recent = list(paths)

    def add_editor(self, editor: EditorView, document: DocumentModel) -> int:
        index = self.tabs.addTab(editor, document.display_title)
        self.tabs.setCurrentIndex(index)
        editor.setFocus()
        return index

    def tab_count(self) -> int:
        return self.tabs.count()

    def current_editor(self) -> Optional[EditorView]:
        widget = self.tabs.currentWidget()
        return widget if isinstance(widget, EditorView) else None

    def editors(self) -> List[EditorView]:
        return [self.tabs.widget(i) for i in range(self.tabs.count())
                if isinstance(self.tabs.widget(i), EditorView)]

    def editor_at(self, index: int) -> Optional[EditorView]:
        widget = self.tabs.widget(index) if 0 <= index < self.tabs.count() else None
        return widget if isinstance(widget, EditorView) else None

    def index_of(self, editor: EditorView) -> int:
        return self.tabs.indexOf(editor)

    def set_tab_title(self, editor: EditorView, title: str, modified: bool) -> None:
        index = self.tabs.indexOf(editor)
        if index >= 0:
            self.tabs.setTabText(index, f"● {title}" if modified else title)
            self.tabs.setTabToolTip(index, title)

    def close_editor(self, editor: EditorView) -> None:
        index = self.tabs.indexOf(editor)
        if index >= 0:
            self.tabs.removeTab(index)
            editor.deleteLater()

    def _on_tab_changed(self, index: int) -> None:
        self.tab_changed.emit(index)

    # ==================================================================
    # state helpers used by the controller
    # ==================================================================
    def set_direction_menu(self, mode: str) -> None:
        {AUTO: self.act_dir_auto, RTL: self.act_dir_rtl,
         LTR: self.act_dir_ltr}.get(mode, self.act_dir_auto).setChecked(True)

    def set_language_menu(self, code: str) -> None:
        action = self._language_actions.get(code)
        if action is not None:
            action.setChecked(True)

    def set_encoding_menu(self, encoding: str) -> None:
        for action in self.encoding_group.actions():
            if action.text().lower() == encoding.lower():
                action.setChecked(True)
                return

    def set_line_ending_menu(self, line_ending: str) -> None:
        wanted = {"\r\n": "CRLF", "\r": "CR"}.get(line_ending, "LF")
        for action in self.line_ending_group.actions():
            if action.text().startswith(wanted):
                action.setChecked(True)
                return

    def show_banner(self, text: str) -> None:
        self.banner.setText(text)
        self.banner.show()

    def hide_banner(self) -> None:
        self.banner.hide()

    def set_word_wrap_enabled(self, enabled: bool) -> None:
        """Keep the View ▸ Word wrap check state in sync with settings."""
        blocked = self.act_word_wrap.blockSignals(True)
        self.act_word_wrap.setChecked(enabled)
        self.act_word_wrap.blockSignals(blocked)

    def set_line_numbers_visible(self, visible: bool) -> None:
        blocked = self.act_line_numbers.blockSignals(True)
        self.act_line_numbers.setChecked(visible)
        self.act_line_numbers.blockSignals(blocked)

    def set_ui_font(self, font: QFont) -> None:
        self.menuBar().setFont(font)
        self.status.setFont(font)
        self.find_bar.setFont(font)

    def retranslate(self) -> None:
        """Rebuild every label after a UI-language switch."""
        self.menuBar().clear()
        self._build_menus()
        self.find_bar.retranslate()
        self.status.retranslate()

    # ==================================================================
    # dialogs
    # ==================================================================
    def open_file_dialog(self, start_dir: str = "") -> Optional[str]:
        filters = ";;".join([
            tr("filter.text"), tr("filter.markdown"), tr("filter.all"),
        ])
        path, _ = QFileDialog.getOpenFileName(
            self, tr("menu.file.open"), start_dir, filters)
        return path or None

    def save_file_dialog(self, start: str = "") -> Optional[str]:
        filters = ";;".join([tr("filter.text"), tr("filter.markdown"),
                             tr("filter.all")])
        path, _ = QFileDialog.getSaveFileName(
            self, tr("menu.file.save_as"), start, filters)
        return path or None

    def confirm_unsaved(self, title: str) -> QMessageBox.StandardButton:
        box = QMessageBox(self)
        box.setWindowTitle(tr("dialog.unsaved.title"))
        box.setText(tr("dialog.unsaved.text", title=title))
        box.setIcon(QMessageBox.Icon.Warning)
        save = box.addButton(tr("dialog.save"),
                             QMessageBox.ButtonRole.AcceptRole)
        discard = box.addButton(tr("dialog.discard"),
                                QMessageBox.ButtonRole.DestructiveRole)
        box.addButton(tr("dialog.cancel"), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(save)
        box.exec()
        clicked = box.clickedButton()
        if clicked is save:
            return QMessageBox.StandardButton.Save
        if clicked is discard:
            return QMessageBox.StandardButton.Discard
        return QMessageBox.StandardButton.Cancel

    def show_error(self, text: str) -> None:
        QMessageBox.critical(self, tr("dialog.error.title"), text)

    def show_info(self, text: str) -> None:
        QMessageBox.information(self, tr("dialog.error.title"), text)

    def ask_big_file(self, name: str, size: str) -> bool:
        box = QMessageBox(self)
        box.setWindowTitle(tr("dialog.bigfile.title"))
        box.setText(tr("dialog.bigfile.text", path=name, size=size))
        box.setIcon(QMessageBox.Icon.Question)
        load_all = box.addButton(tr("dialog.bigfile.load_all"),
                                 QMessageBox.ButtonRole.AcceptRole)
        box.addButton(tr("dialog.cancel"), QMessageBox.ButtonRole.RejectRole)
        box.exec()
        return box.clickedButton() is load_all

    def goto_line_dialog(self, maximum: int) -> Optional[int]:
        from PySide6.QtWidgets import QInputDialog

        value, ok = QInputDialog.getInt(
            self, tr("dialog.goto.title"), tr("dialog.goto.label", max=maximum),
            1, 1, max(1, maximum))
        return value if ok else None

    def choose_encoding_dialog(self, current: str) -> Optional[str]:
        from PySide6.QtWidgets import QInputDialog

        value, ok = QInputDialog.getItem(
            self, tr("action.encoding"), tr("action.encoding"),
            [e.upper() for e in ENCODINGS],
            max(0, [e.lower() for e in ENCODINGS].index(current.lower()))
            if current.lower() in [e.lower() for e in ENCODINGS] else 0,
            False)
        return value.lower() if ok else None
