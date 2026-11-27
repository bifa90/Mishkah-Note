"""Glue between the window, the file service and the settings."""

from __future__ import annotations

import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import QFileSystemWatcher, QObject, Qt, QTimer
from PySide6.QtGui import QFont, QTextCursor
from PySide6.QtWidgets import QApplication, QMessageBox

from mishkah.core import i18n, syntax, tab_style, text_stats
from mishkah.core.disk_state import changed_on_disk, stat_signature
from mishkah.core.file_kinds import (
    READ_ONLY,
    ensure_extension,
    policy_for_file,
)
from mishkah.core.languages import editor_font_families, get_language
from mishkah.core.settings import Settings
from mishkah.core.text_direction import (
    AUTO,
    FIRST_LINE,
    FIRST_STRONG,
    LTR,
    dominant_direction,
)
from mishkah.models.document import DocumentModel
from mishkah.services.file_service import FileService
from mishkah.views.editor_view import EditorView
from mishkah.views.main_window import MainWindow
from mishkah.widgets.about_dialog import AboutDialog
from mishkah.widgets.home_page import HomePage
from mishkah.widgets.settings_dialog import SettingsDialog

logger = logging.getLogger(__name__)


class MainController(QObject):
    """One controller per window; owns its editors and settings copy."""

    def __init__(self, window: MainWindow, settings: Settings,
                 file_service: Optional[FileService] = None,
                 parent: Optional[QObject] = None):
        super().__init__(parent)
        self.window = window
        self.settings = settings
        self.files = file_service or FileService(self)
        self._docs: Dict[EditorView, DocumentModel] = {}
        #: True for the first window only (see app.build_window).
        self.owns_session = True
        self._invisible_banner = False
        #: CD-18: documents whose file changed on disk, waiting for a decision.
        #: A list, not a set: DocumentModel is a dataclass and unhashable.
        self._changed_docs: List[DocumentModel] = []
        #: CD-19/M1: reopened with another encoding, awaiting conversion.
        self._encoding_pending: List[DocumentModel] = []
        #: Monotonic time of our own last write per path.  The file watcher
        #: fires for that write too, and at that instant the recorded signature
        #: is still the old one — which used to raise a banner claiming an
        #: outside edit that never happened.
        self._writes: Dict[str, float] = {}
        #: The user asked for autosave on a document that has no path yet;
        #: it turns on by itself once the save dialog has given it one.
        self._autosave_after_save = False
        self._watcher: Optional[QFileSystemWatcher] = None
        #: CD-01: one idle timer, single shot, no background thread.
        self._autosave_timer: Optional[QTimer] = None
        self._last_editor: Optional[EditorView] = None
        self._pending_paths: Dict[int, str] = {}   # tab index -> path being loaded
        self._busy = False
        self._close_after_save: set[EditorView] = set()
        self._window_close_after_save = False

        self.active_theme = self._resolve_theme(settings.theme)
        i18n.set_language(settings.ui_language)
        self._wire()
        self._init_autosave()
        self._apply_appearance()

    # ==================================================================
    # wiring
    # ==================================================================
    def _wire(self) -> None:
        w = self.window
        w.file_new.connect(self.new_document)
        w.new_window_requested.connect(self.open_new_window)
        w.file_open.connect(self.open_document_dialog)
        w.file_save.connect(self.save_current)
        w.file_save_as.connect(lambda: self.save_current(as_copy=True))
        w.file_save_all.connect(self.save_all)
        w.file_print.connect(self.print_current)
        w.tab_close_requested.connect(self.close_tab)
        w.tab_changed.connect(self._on_tab_changed)
        w.direction_changed.connect(self.set_direction)
        w.language_changed.connect(self.set_ui_language)
        w.word_wrap_toggled.connect(self.set_word_wrap)
        w.line_numbers_toggled.connect(self.set_line_numbers)
        w.show_invisible_toggled.connect(self.set_show_invisible_chars)
        w.file_changed_action.connect(self.on_file_changed_action)
        w.autosave_toggled.connect(self.set_autosave)
        w.document_side_toggled.connect(self.set_document_side_first_line)
        w.status_bar_toggled.connect(w.status.setVisible)
        w.encoding_chosen.connect(self.reopen_with_encoding)
        w.line_ending_chosen.connect(self.set_line_ending)
        w.about_requested.connect(self.show_about)
        w.settings_requested.connect(self.show_settings)
        w.theme_changed.connect(self.set_theme)
        w.tab_pin_requested.connect(self.toggle_tab_pin)
        w.tab_color_requested.connect(self.set_tab_color)
        w.tab_color_current.connect(self.set_current_tab_color)
        w.tab_cycle_color_requested.connect(self.cycle_tab_color)
        w.tab_close_others_requested.connect(self.close_other_tabs)
        w.syntax_highlighting_toggled.connect(self.set_syntax_highlighting)
        w.live_markdown_toggled.connect(self.set_live_markdown)
        w.language_override_chosen.connect(self.set_tab_language)
        w.auto_close_toggled.connect(self.set_auto_close)
        w.auto_indent_toggled.connect(self.set_auto_indent)
        w.always_on_top_toggled.connect(self.set_always_on_top)
        w.recent_chosen.connect(self.open_path)
        w.recent_cleared.connect(self._clear_recent)

        w.new_tab_requested.connect(self.new_document)
        w.paths_dropped.connect(self._open_dropped_paths)
        w.paste_plain_requested.connect(self._paste_plain)
        # Every menu entry that is wired to an *action object* lives in
        # ``_bind_actions``: a language switch rebuilds the menu bar, so those
        # bindings have to be made again (see ``_bind_actions``).
        self._bind_actions()
        w.menus_rebuilt.connect(self._bind_actions)

        w.find_bar.find_requested.connect(self._on_find)
        w.find_bar.incremental_requested.connect(self._on_incremental_find)
        w.find_bar.replace_requested.connect(self._on_replace)
        w.find_bar.replace_all_requested.connect(self._on_replace_all)
        w.find_bar.closed.connect(lambda: self._focus_editor())

        w.status.direction_requested.connect(self.set_direction)
        w.status.encoding_clicked.connect(self._choose_encoding)
        w.status.line_ending_clicked.connect(self._cycle_line_ending)

        self.files.load_finished.connect(self._on_loaded)
        self.files.load_failed.connect(self._on_load_failed)
        self.files.save_finished.connect(self._on_saved)
        self.files.save_failed.connect(self._on_save_failed)
        self.files.load_progress.connect(self._on_progress)

    def _bind_actions(self) -> None:
        """Wire the menu actions, now and after every menu rebuild.

        A language switch calls ``menuBar().clear()`` and builds the menus again,
        which means fresh ``QAction`` objects while the controller still pointed
        at the old ones — deleted silently, with no error.  The user met it as
        "Ctrl+F does nothing after I changed the language": Find, Replace, Undo,
        Redo, Cut, Copy, Paste, Delete, Select all, Go to line, Date/time and
        the three zoom actions were all dead, and only those, because everything
        else is wired through the window's own signals, which survive.

        Safe to call repeatedly: each call binds the actions that exist *now*.
        """
        w = self.window
        w.act_undo.triggered.connect(lambda: self._editor_op("undo"))
        w.act_redo.triggered.connect(lambda: self._editor_op("redo"))
        w.act_cut.triggered.connect(lambda: self._editor_op("cut"))
        w.act_copy.triggered.connect(lambda: self._editor_op("copy"))
        w.act_paste.triggered.connect(lambda: self._editor_op("paste"))
        w.act_delete.triggered.connect(self._delete_selection)
        w.act_select_all.triggered.connect(lambda: self._editor_op("selectAll"))
        w.act_find.triggered.connect(lambda: self.show_find(False))
        w.act_replace.triggered.connect(lambda: self.show_find(True))
        w.act_goto.triggered.connect(self.goto_line)
        w.act_date_time.triggered.connect(self.insert_date_time)
        w.act_zoom_in.triggered.connect(lambda: self._zoom(+1))
        w.act_zoom_out.triggered.connect(lambda: self._zoom(-1))
        w.act_zoom_reset.triggered.connect(self._zoom_reset)

    # ==================================================================
    # appearance
    # ==================================================================
    def _apply_appearance(self) -> None:
        s = self.settings
        language = get_language(s.ui_language)

        ui_font = QFont()
        ui_font.setFamilies(list(language.ui_fonts))
        ui_font.setPointSize(max(8, s.font_size - 1))
        self.window.set_ui_font(ui_font, language.code)

        self.window.set_language_menu(s.ui_language)
        self.window.act_word_wrap.setChecked(s.word_wrap)
        self.window.act_line_numbers.setChecked(s.line_numbers)
        self.window.status.setVisible(s.show_status_bar)
        self.window.set_recent_files(s.recent_files)
        self.window.apply_shortcut_settings(s.redo_shortcut,
                                           s.replace_shortcut)

        direction = Qt.LayoutDirection.RightToLeft if language.rtl \
            else Qt.LayoutDirection.LeftToRight
        self.window.setLayoutDirection(direction)

    def editor_font(self) -> QFont:
        s = self.settings
        font = QFont()
        font.setFamilies(editor_font_families(s.ui_language, s.font_family))
        font.setPointSize(s.font_size)
        font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
        return font

    # ==================================================================
    # documents
    # ==================================================================
    def new_document(self) -> EditorView:
        doc = DocumentModel(direction_mode=self.settings.default_direction)
        editor = EditorView(doc, self.editor_font(), self.window)
        self._bind_editor(editor, doc)
        self.window.add_editor(editor, doc)
        self._sync_ui(editor)
        return editor

    # ==================================================================
    # welcome page (CD-06)
    # ==================================================================
    def show_home(self) -> HomePage:
        """Show the welcome page, creating it the first time (CD-06)."""
        page = self.window.home_page()
        if page is None:
            page = HomePage(self.window)
            page.setFont(self.window.ui_font())
            page.new_requested.connect(self._new_from_home)
            page.open_requested.connect(self._open_from_home)
            page.recent_requested.connect(self._open_recent_from_home)
            page.settings_requested.connect(self.show_settings)
            page.help_requested.connect(self.show_about)
            page.restore_requested.connect(self._restore_from_home)
            self.window.add_home_page(page)
        self._refresh_home(page)
        self.window.tabs.setCurrentWidget(page)
        self.window.hide_file_changed()
        self.window.hide_banner()
        self.window.setWindowTitle(i18n.tr("app.name"))
        return page

    def _drop_home(self) -> None:
        """The page did its job: a document is beside it, so it steps aside."""
        page = self.window.home_page()
        if page is not None and self.window.tabs.count() > 1:
            self.window.close_widget(page)
            self._sync_ui(self.window.current_editor())

    def _new_from_home(self) -> None:
        self.new_document()
        self._drop_home()

    def _open_from_home(self) -> None:
        self.open_document_dialog()
        self._drop_home()

    def _open_recent_from_home(self, path: str) -> None:
        self.open_path(path)
        self._drop_home()

    def _refresh_home(self, page: HomePage) -> None:
        page.set_recent_files(self.settings.recent_files)
        previous = [p for p in self.settings.open_files if Path(p).exists()]
        page.set_restore_available(bool(previous))

    def _restore_from_home(self) -> None:
        """Open the files the last session left behind, then drop the page."""
        opened = self.restore_session(list(self.settings.open_files)) or 0
        if opened and self.window.home_page() is not None:
            page = self.window.home_page()
            if self.window.tabs.count() > 1:
                self.window.close_widget(page)

    def _last_tab_closed(self) -> None:
        """Closing the last tab: the welcome page or the end (CD-06)."""
        if self.settings.last_tab_action == "quit":
            self.window.close()
            return
        self.show_home()

    def open_new_window(self) -> None:
        """CD-29/B2: ask the application for a second window.

        Without a factory (tests, embedding) the request becomes a new tab, so
        the menu item is never dead and never pretends to have opened a window.
        """
        factory = getattr(self.window, "new_window_factory", None)
        if callable(factory):
            factory()
            return
        self.new_document()

    def _bind_editor(self, editor: EditorView, doc: DocumentModel) -> None:
        self._docs[editor] = doc
        editor.set_word_wrap(self.settings.word_wrap)
        editor.set_line_numbers_visible(self.settings.line_numbers)
        editor.set_show_invisible_chars(self.settings.show_invisible_chars)
        editor.set_document_side_source(self.settings.document_side_source)
        self._apply_editing_options(editor)
        editor.cursor_moved.connect(
            lambda line, col, sel: self.window.status.set_position(line, col, sel))
        editor.zoom_changed.connect(self.window.status.set_zoom)
        editor.direction_changed.connect(self._on_editor_direction)
        editor.resolved_direction_changed.connect(self._on_resolved_direction)
        editor.stats_changed.connect(self._on_stats)
        editor.textChanged.connect(lambda e=editor: self._on_text_changed(e))
        # The right-click menu speaks through signals: the window owns the
        # search bars, so it opens them for whichever tab was clicked.
        editor.find_requested.connect(lambda e=editor: self._menu_find(e, False))
        editor.replace_requested.connect(lambda e=editor: self._menu_find(e, True))
        editor.goto_requested.connect(self.goto_line)
        editor.language_detected.connect(
            lambda _code, e=editor: self._on_language_detected(e))
        editor.files_dropped.connect(self._open_dropped_paths)

    @staticmethod
    def _resolve_theme(theme: str) -> str:
        """The concrete theme the highlighter should paint for.

        ``system`` used to be guessed as light, which painted dark-on-dark
        colours for anyone on a dark desktop.
        """
        if theme in ("light", "dark"):
            return theme
        app = QApplication.instance()
        if app is None:
            return "light"
        palette = app.palette()
        return ("dark"
                if palette.color(palette.ColorRole.Window).lightness() < 128
                else "light")

    def _apply_editing_options(self, editor: EditorView) -> None:
        """Push the typing/highlighting preferences onto one editor."""
        s = self.settings
        editor.set_auto_close(s.auto_close_brackets)
        editor.set_auto_indent(s.auto_indent)
        editor.set_word_completion(s.word_completion)
        editor.set_tab_width(s.tab_width)
        editor.set_language("auto")
        self._apply_highlighting(editor)
        editor.set_live_markdown(s.live_markdown, self.active_theme)

    def _apply_highlighting(self, editor: EditorView) -> None:
        editor.set_syntax_highlighting(
            self.settings.syntax_highlighting,
            language=self._language_for(editor),
            theme=self.active_theme,
        )

    def _language_for(self, editor: EditorView) -> str:
        doc = self._docs.get(editor)
        chosen = doc.language if doc is not None else "auto"
        if chosen and chosen != "auto":
            return chosen
        by_path = syntax.language_for_path(doc.path if doc is not None else None)
        if by_path != syntax.PLAIN.code:
            return by_path
        # Nothing in the name: ask the content (CD-12), so code pasted into an
        # untitled tab is highlighted without saving and reopening it.
        return editor.detected_language()

    def document_for(self, editor: Optional[EditorView]) -> Optional[DocumentModel]:
        if editor is None:
            return None
        return self._docs.get(editor)

    def current_document(self) -> Optional[DocumentModel]:
        return self.document_for(self.window.current_editor())

    def _paste_plain(self) -> None:
        """Edit ▸ Paste without formatting (CD-13)."""
        editor = self.window.current_editor()
        if editor is not None and not editor.isReadOnly():
            editor.paste_plain()

    def _open_dropped_paths(self, paths) -> None:
        """Open files dropped on the window, each in its own tab (CD-22).

        A refused file (binary, unreadable) is reported by the loader and
        leaves no empty tab behind, which is exactly the CD-05 rule.
        """
        for path in paths or []:
            self.open_path(str(path))

    def open_document_dialog(self) -> None:
        start = ""
        doc = self.current_document()
        if doc and doc.path:
            start = str(doc.path.parent)
        path = self.window.open_file_dialog(start)
        if path:
            self.open_path(path)

    def open_path(self, path: str | Path, encoding: Optional[str] = None) -> None:
        path = Path(path)
        if not path.exists():
            self.window.show_error(
                i18n.tr("dialog.error.open", path=path.name, detail="Not found"))
            return

        size = path.stat().st_size
        ask_mb = self.settings.ask_before_mb
        # The configured ceiling was never handed to the loader: any file at
        # all was read whole into memory.  Above the ceiling the tab now opens
        # as a preview and says so (CD-11 / M4).
        limit_mb = max(1, int(self.settings.hard_limit_mb or 0)) or None
        if ask_mb and size > ask_mb * 1024 * 1024:
            if not self.window.ask_big_file(
                    path.name, _human(size)):
                return
        self._begin_load(path, encoding=encoding, limit_mb=limit_mb)

    def _begin_load(self, path: Path, encoding: Optional[str] = None,
                    limit_mb: Optional[int] = None) -> None:
        doc = DocumentModel(path=path, encoding_override=encoding)
        editor = EditorView(doc, self.editor_font(), self.window)
        self._bind_editor(editor, doc)
        index = self.window.add_editor(editor, doc)
        self._pending_paths[index] = str(path)
        # No placeholder text is written here.  A new editor is already empty,
        # and clearing it would count as an edit: the document would be marked
        # modified before its content arrived, so closing a freshly opened file
        # would ask to save it.  (Blocking the widget's signals while clearing
        # corrupts QPlainTextEdit's state — it crashed a later paint.)
        self.window.set_tab_title(editor, path.name, False)
        self._start_load_progress(path)
        self.files.load(path, encoding=encoding, limit_mb=limit_mb)

    #: Files above this size get a progress dialog, not just a percentage in
    #: the window title (which is invisible on a maximised window).
    BIG_LOAD_BYTES = 4 * 1024 * 1024

    def _start_load_progress(self, path: Path) -> None:
        """Open the cancellable dialog before a large read starts (G3b #13).

        A 98 MB file froze the window for twenty seconds with nothing on screen
        but a title-bar percentage the user never saw.  The dialog is shown
        *before* the worker starts, so the wait is acknowledged instead of
        looking like a hang.
        """
        self._close_load_progress()
        try:
            if path.stat().st_size < self.BIG_LOAD_BYTES:
                return
        except OSError:
            return
        from mishkah.widgets.progress_dialog import ProgressDialog

        dialog = ProgressDialog(i18n.tr("progress.loading", name=path.name),
                                self.window, minimum_duration=0)
        dialog.report(0, 1000)
        dialog.cancelled.connect(self.files.cancel_all)
        dialog.show()
        self._load_dialog = dialog

    def _close_load_progress(self) -> None:
        dialog = getattr(self, "_load_dialog", None)
        self._load_dialog = None
        if dialog is not None:
            dialog.close()
            dialog.deleteLater()

    def _on_loaded(self, doc: DocumentModel) -> None:
        dialog = getattr(self, "_load_dialog", None)
        if dialog is not None and dialog.is_cancelled():
            self._close_load_progress()
            editor = self._editor_for_path(doc.path)
            if editor is not None:
                self.window.close_editor(editor)
                self._docs.pop(editor, None)
            if self.window.tab_count() == 0:
                self.new_document()
            return

        editor = self._editor_for_path(doc.path)
        if editor is None:
            editor = self.new_document()
        live = self._docs.get(editor)
        if live is not None:
            doc.direction_mode = live.direction_mode
        self._docs[editor] = doc

        def _populate_progress(done: int, total: int) -> bool:
            dlg = getattr(self, "_load_dialog", None)
            pct = 70 + (done * 30 // max(1, total))
            self.window.setWindowTitle(f"{i18n.tr('app.name')} — {pct}%")
            if dlg is not None:
                dlg.report(700 + (done * 300 // max(1, total)), 1000)
                QApplication.processEvents()
                if dlg.is_cancelled():
                    return False
            return True

        # Direction: "auto" keeps Qt's per-paragraph rule; an explicit mode
        # in settings is honoured, otherwise the content decides.
        if doc.direction_mode == AUTO:
            doc.direction_mode = AUTO
        blocked = editor.blockSignals(True)
        try:
            loaded = editor.set_document(doc, progress_cb=_populate_progress)
            if not loaded:
                self.window.close_editor(editor)
                self._docs.pop(editor, None)
                if self.window.tab_count() == 0:
                    self.new_document()
                return
            # The buffer now holds what is on disk; Qt's own flag must agree,
            # or a later format pass would look like an edit (B1).
            editor.document().setModified(False)
        finally:
            editor.blockSignals(blocked)
            self._close_load_progress()

        editor.set_font_size(self.settings.font_size)
        # Skip heavy whole-document highlighting on huge payloads so opening a
        # multi-megabyte log never stalls after the progress bar finishes.
        heavy_payload = (
            doc.uses_performance_mode
            or len(doc.content) > 2_000_000
        )
        if heavy_payload:
            editor.set_syntax_highlighting(
                False, language=syntax.PLAIN.code, theme=self.active_theme)
            editor.set_live_markdown(False, self.active_theme)
        else:
            # The content is in the buffer now: colour it with the grammar the
            # name or the text itself implies (CD-12), before the first paint.
            self._apply_highlighting(editor)

        large_doc = (
            doc.uses_performance_mode
            or len(doc.content) > EditorView.HUGE_CHAR_THRESHOLD
        )
        if large_doc and self.settings.performance_mode:
            editor.set_word_wrap(False)
            editor.set_line_numbers_visible(False)

        # CD-05: decide from the content whether this file may be written.
        if doc.path is not None and policy_for_file(doc.path) == READ_ONLY:
            doc.read_only = True
            self.window.show_banner(
                i18n.tr("banner.read_only", name=doc.path.name))
        self.window.set_tab_title(editor, self._doc_title(doc), False)
        self._watch(doc)
        if doc.truncated:
            from mishkah.core.large_file import PREVIEW_BYTES
            shown = min(PREVIEW_BYTES,
                        int(self.settings.hard_limit_mb or 0) * 1024 * 1024)
            self.window.show_preview(doc.title, _human(shown),
                                     _human(doc.size_on_disk))
        elif doc.read_only:
            self.window.show_banner(i18n.tr("banner.readonly"))
        else:
            self.window.hide_banner()

        self.settings.remember_file(str(doc.path))
        self.window.set_recent_files(self.settings.recent_files)
        self._sync_ui(editor)
        editor.setFocus()

    def _editor_for_path(self, path: Optional[Path]) -> Optional[EditorView]:
        if path is None:
            return None
        wanted = str(path)
        for index, pending in list(self._pending_paths.items()):
            if pending == wanted:
                editor = self.window.editor_at(index)
                if editor is not None:
                    self._pending_paths.pop(index, None)
                    return editor
        return None

    def _on_load_failed(self, path: str, title: str, detail: str) -> None:
        self._close_load_progress()
        if title == "cancelled":
            return
        editor = self._editor_for_path(Path(path)) if path else None
        if editor is not None:
            self.window.close_editor(editor)
            self._docs.pop(editor, None)
        if title == "BinaryFileError":
            self.window.show_error(i18n.tr("dialog.binary.text", path=path))
        else:
            self.window.show_error(
                i18n.tr("dialog.error.open", path=path, detail=detail or title))
        if self.window.tab_count() == 0:
            self.new_document()

    def _on_progress(self, done: int, total: int) -> None:
        if total <= 0:
            return
        # Disk reading accounts for 0–70%; editor population fills 70–100% so
        # the bar never sits frozen at 100% while Qt builds the document.
        pct = done * 70 // max(1, total)
        self.window.setWindowTitle(f"{i18n.tr('app.name')} — {pct}%")
        dialog = getattr(self, "_load_dialog", None)
        if dialog is not None:
            dialog.report(
                done * 700 // max(1, total),
                1000,
                f"{_human(done)} / {_human(total)}",
            )

    # ==================================================================
    # saving
    # ==================================================================
    @staticmethod
    def _sync_content(editor: EditorView, doc: DocumentModel) -> None:
        """Copy the widget's text into the model before it is written.

        The editor owns the live buffer; the model is the thing the file
        service serialises.  Forgetting this step wrote an empty file, so it
        runs on every save path.
        """
        if doc.truncated:
            return
        text = editor.toPlainText()
        if text != doc.content:
            doc.content = text
            doc.size_on_disk = 0        # recount from the buffer

    def save_current(self, as_copy: bool = False) -> bool:
        editor = self.window.current_editor()
        doc = self.current_document()
        if editor is None or doc is None:
            return False
        if doc.truncated:
            # An info bar, not a modal box: saving a preview is a harmless
            # mistake and the user should not have to dismiss a dialog for it.
            from mishkah.core.large_file import human_size

            self.window.show_banner(i18n.tr(
                "banner.preview",
                size=human_size(min(doc.size_on_disk, len(doc.content.encode("utf-8")))),
                total=human_size(doc.size_on_disk)))
            return False
        if doc.read_only and not as_copy:
            self.window.show_banner(
                i18n.tr("banner.read_only_save", name=self._doc_title(doc)))
            return False
        if doc.encoding_pending and not as_copy:
            self.window.show_encoding_pending(self._doc_title(doc), doc.encoding)
            if doc not in self._encoding_pending:
                self._encoding_pending.append(doc)
            return False
        self._sync_content(editor, doc)
        if not as_copy and self._file_changed(doc):
            return False
        target = doc.path
        if as_copy or target is None:
            start = str(target) if target else ""
            chosen = self.window.save_file_dialog(start)
            if not chosen:
                return False
            # A bare name would be written without an extension; the dialog's
            # filter is a hint, not something the file manager enforces.
            target = ensure_extension(Path(chosen), doc.content,
                                      self.settings.default_extension)
        self._save_doc(doc, target)
        return True

    def save_all(self) -> None:
        for editor in self.window.editors():
            doc = self._docs.get(editor)
            if doc and doc.is_modified and doc.path and not doc.truncated:
                self._sync_content(editor, doc)
                if self._file_changed(doc):
                    continue
                self._save_doc(doc, doc.path)

    # ==================================================================
    # CD-01 · autosave
    # ==================================================================
    def _init_autosave(self) -> None:
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.timeout.connect(self._autosave_now)
        self.window.set_autosave(False)      # per document, off until asked

    def set_autosave(self, enabled: bool) -> None:
        """The switch above the menus, for *this* document only (CD-01).

        Autosave is a property of the tab: turning it on for one file must not
        follow the user to the next one.  Autosave without a path is a promise
        the editor cannot keep, so asking for it on an unsaved document opens
        the save dialog instead of turning green: the switch only flips once
        the file exists.
        """
        editor = self.window.current_editor()
        doc = self.document_for(editor)
        if doc is None:
            self.window.set_autosave(False)
            return
        if enabled and doc.path is None:
            doc.autosave = False
            doc.autosave_pending = True
            self.window.set_autosave(False)
            self._autosave_after_save = True
            self.window.show_save_first(self._doc_title(doc))
            return
        doc.autosave = bool(enabled)
        self.window.set_autosave(bool(enabled))
        if not enabled and self._autosave_timer is not None:
            self._autosave_timer.stop()
        if enabled:
            self._arm_autosave()

    def _arm_autosave(self) -> None:
        doc = self.current_document()
        if (self._autosave_timer is None or doc is None
                or not doc.autosave):
            return
        self._autosave_timer.start(max(500, int(self.settings.autosave_idle_ms)))

    def _autosave_now(self, editor: Optional[EditorView] = None) -> None:
        """Write the buffer if — and only if — nothing else is in the way."""
        editor = editor or self.window.current_editor()
        doc = self.document_for(editor)
        if editor is None or doc is None or not doc.autosave:
            return
        if (doc.path is None or doc.read_only or doc.truncated
                or doc.encoding_pending or not doc.is_modified):
            return
        if self._changed_docs:
            return                       # the outside edit has not been answered
        self._sync_content(editor, doc)
        if self._file_changed(doc):
            return
        self._save_doc(doc, doc.path)

    def autosave_enabled(self) -> bool:
        """True when the document on screen has autosave on."""
        doc = self.current_document()
        return bool(doc is not None and doc.autosave)

    # ==================================================================
    # CD-18 · the file changed on disk
    # ==================================================================
    def _file_changed(self, doc: DocumentModel) -> bool:
        """True when the file changed since we read or wrote it.

        Called before *every* write: an autosave that fires two seconds after
        an outside edit must not silently replace it.
        """
        if doc is None or doc.path is None or doc.truncated:
            return False
        if not changed_on_disk(doc.path, doc.disk_signature):
            return False
        self._show_file_changed(doc)
        return True

    def _show_file_changed(self, doc: DocumentModel) -> None:
        if doc not in self._changed_docs:
            self._changed_docs.append(doc)
        editor = self._editor_for_document(doc)
        if editor is not None:
            index = self.window.index_of(editor)
            if index >= 0:
                self.window.tabs.setCurrentIndex(index)
        try:
            name = doc.path.name if doc.path else doc.title
        except AttributeError:          # pragma: no cover - defensive
            name = ""
        self.window.show_file_changed(name)

    def _watch(self, doc: DocumentModel) -> None:
        """Watch the file so an outside edit is noticed before the next save."""
        if doc.path is None:
            return
        if self._watcher is None:
            self._watcher = QFileSystemWatcher(self)
            self._watcher.fileChanged.connect(self._on_watched_file_changed)
        path = str(doc.path)
        if path not in self._watcher.files():
            self._watcher.addPath(path)

    def _unwatch(self, doc: DocumentModel) -> None:
        if self._watcher is None or doc.path is None:
            return
        path = str(doc.path)
        if path in self._watcher.files():
            self._watcher.removePath(path)

    #: How long after our own write the watcher is ignored.  Long enough for
    #: the worker to finish and the signature to be refreshed, short enough
    #: that a genuine outside edit right afterwards is still noticed.
    WRITE_QUIET_SECONDS = 2.0

    def _note_write(self, doc: DocumentModel) -> None:
        if doc is not None and doc.path is not None:
            self._writes[str(doc.path)] = time.monotonic()

    def _watcher_is_hearing_itself(self, path: str) -> bool:
        stamp = self._writes.get(path)
        return stamp is not None and (time.monotonic() - stamp) < self.WRITE_QUIET_SECONDS

    def _save_doc(self, doc: DocumentModel, target) -> None:
        """The one place that starts a write: notes it, then asks the service."""
        self._note_write(doc)
        self.files.save(doc, target)

    def _on_watched_file_changed(self, path: str) -> None:
        if self._watcher_is_hearing_itself(path):
            return                       # our own write, not an outside edit
        for doc in list(self._docs.values()):
            if doc.path is not None and str(doc.path) == path:
                if changed_on_disk(doc.path, doc.disk_signature):
                    self._show_file_changed(doc)
                else:
                    # our own atomic write: the signature already matches
                    self.window.hide_file_changed()
                break

    def on_file_changed_action(self, action: str) -> None:
        """Answer a banner: reload, overwrite, convert, save file, or dismiss."""
        doc = self._changed_docs[-1] if self._changed_docs else self.current_document()
        if doc is None:
            self.window.hide_file_changed()
            return
        editor = self._editor_for_document(doc)
        self.window.hide_file_changed()
        if doc in self._changed_docs:
            self._changed_docs.remove(doc)
        if action == "save_file":
            self.window.hide_file_changed()
            editor = self.window.current_editor()
            if editor is None or not self.save_current():
                self._autosave_after_save = False     # cancelled: stay off
                current = self.current_document()
                if current is not None:
                    current.autosave_pending = False
            return
        if action == "enable_markdown":
            self.set_live_markdown(True)
            self.window.set_typing_menu_state(
                self.settings.auto_close_brackets,
                self.settings.auto_indent,
                self.settings.syntax_highlighting,
                self.current_document().language if self.current_document() else "auto",
                True,
            )
            return
        if action == "open_full":
            self._open_preview_fully(doc)
            return
        if action == "convert":
            if editor is not None:
                self._convert_encoding(doc, editor)
            return
        if action == "dismiss" or editor is None:
            return
        if action == "overwrite":
            doc.disk_signature = stat_signature(doc.path)
            self._sync_content(editor, doc)
            self._save_doc(doc, doc.path)
            return
        if action == "reload":
            self._reload_from_disk(doc, editor)

    def _open_preview_fully(self, doc: DocumentModel) -> None:
        """Read the whole file into the preview tab the user is looking at."""
        if doc.path is None:
            return
        editor = self._editor_for_document(doc)
        if editor is None:
            return
        index = self.window.index_of(editor)
        self._pending_paths[index] = str(doc.path)
        self.files.load(doc.path, encoding=doc.encoding, limit_mb=None)

    def _convert_encoding(self, doc: DocumentModel, editor: EditorView) -> None:
        """Accept the new encoding, then save with it (the explicit step)."""
        doc.encoding_pending = False
        if doc in self._encoding_pending:
            self._encoding_pending.remove(doc)
        self.window.status.set_encoding(doc.encoding)
        self.window.set_encoding_menu(doc.encoding)
        self._sync_content(editor, doc)
        if self._file_changed(doc):
            return
        if doc.path is not None:
            self._save_doc(doc, doc.path)

    def _reload_from_disk(self, doc: DocumentModel, editor: EditorView) -> None:
        """Replace the buffer with what is on disk, dropping undo history."""
        if doc.path is None:
            return
        from mishkah.core import large_file

        try:
            result = large_file.read_text_chunked(
                doc.path, encoding=doc.encoding, limit=1 << 62)
        except Exception as exc:                    # noqa: BLE001 - reported
            self.window.show_error(i18n.tr("dialog.error.open",
                                           path=str(doc.path), detail=str(exc)))
            return
        text, fmt, truncated, size = result
        doc.content = text
        doc.fmt = fmt
        doc.size_on_disk = size
        doc.truncated = truncated
        doc.revision += 1
        doc.disk_signature = stat_signature(doc.path)
        # Loading the buffer emits textChanged; without this the fresh content
        # would be marked as an edit of itself.
        editor.blockSignals(True)
        try:
            editor.load_content(text)
            # Formatting signals travel as textChanged too, so the direction
            # pass belongs inside the quiet window.
            editor.apply_direction(doc.direction_mode or AUTO, announce=False)
        finally:
            editor.blockSignals(False)
        doc.is_modified = False
        editor.document().setModified(False)
        self.window.set_tab_title(editor, self._doc_title(doc), False)
        self._sync_ui(editor)
        doc.is_modified = False        # nothing above is an edit of the user's
        self.window.show_banner(i18n.tr("banner.reloaded", name=doc.path.name))

    def _on_saved(self, doc: DocumentModel, written: int) -> None:
        self._watch(doc)
        self._note_write(doc)
        if self._autosave_after_save and doc.path is not None:
            self._autosave_after_save = False
            doc.autosave_pending = False
            doc.autosave = True
            if self.document_for(self.window.current_editor()) is doc:
                self.window.set_autosave(True)
            self._arm_autosave()
        if doc in self._changed_docs:
            self._changed_docs.remove(doc)
        if not self._changed_docs:
            self.window.hide_file_changed()
        editor = self._editor_for_document(doc)
        if editor is not None:
            self.window.set_tab_title(editor, self._doc_title(doc), doc.is_modified)
            if not doc.is_modified:
                editor.document().setModified(False)
        self.settings.remember_file(str(doc.path))
        self.window.set_recent_files(self.settings.recent_files)
        self.window.setWindowTitle(i18n.tr("app.name"))
        self._sync_ui(editor)
        if editor in self._close_after_save:
            self._close_after_save.discard(editor)
            if not doc.is_modified:
                self.close_tab(self.window.index_of(editor))
        if self._window_close_after_save:
            self._window_close_after_save = False
            if not doc.is_modified:
                self.window.close()

    def _on_save_failed(self, path: str, title: str, detail: str) -> None:
        self._close_after_save.clear()
        self._window_close_after_save = False
        if title == "cancelled":
            return
        self.window.show_error(
            i18n.tr("dialog.error.save", path=path, detail=detail or title))

    def _editor_for_document(self, doc: DocumentModel) -> Optional[EditorView]:
        for editor, candidate in self._docs.items():
            if candidate is doc:
                return editor
        return None

    # ==================================================================
    # tabs
    # ==================================================================
    def close_tab(self, index: int) -> None:
        editor = self.window.editor_at(index)
        if editor is None:
            # The welcome page: closing it alone would leave a window without
            # tabs, so the X does nothing while it is the only one (CD-06).
            page = self.window.tabs.widget(index)
            if page is not None and self.window.tabs.count() > 1:
                self.window.close_widget(page)
                self._sync_ui(self.window.current_editor())
            return
        doc = self._docs.get(editor)
        if doc is not None:
            self._unwatch(doc)
            if doc in self._changed_docs:
                self._changed_docs.remove(doc)
        if doc and doc.is_modified:
            answer = self.window.confirm_unsaved(self._doc_title(doc))
            if answer == QMessageBox.StandardButton.Cancel:
                return
            if answer == QMessageBox.StandardButton.Save:
                self.window.tabs.setCurrentIndex(index)
                self._close_after_save.add(editor)
                if not self.save_current():
                    self._close_after_save.discard(editor)
                return
        self._docs.pop(editor, None)
        # Closing the pinned tab must release the "always on top" hint, or
        # the window would keep floating above everything with nothing pinned.
        self.window.set_tab_pinned(editor, False)
        self.window.set_always_on_top(False)
        self.window.close_editor(editor)
        if self.window.tab_count() == 0:
            self._last_tab_closed()
        else:
            self._sync_ui(self.window.current_editor())

    def _on_tab_changed(self, index: int) -> None:
        leaving = self._last_editor
        editor = self.window.editor_at(index)
        if leaving is not None and leaving is not editor:
            self._autosave_now(leaving)   # one of the three moments (CD-01)
        self._last_editor = editor
        doc = self.document_for(editor)
        # The pinned tab owns "always on top"; switching away from it drops
        # the hint so the window does not stay above everything silently.
        self.window.set_always_on_top(bool(doc and doc.pinned))
        self._sync_ui(editor)

    def _restore_banner(self, doc: Optional[DocumentModel]) -> None:
        """Show the banner that belongs to *doc*, or hide the one that does not.

        A message about one file must follow that file, not the window: the
        notice for "file 1.txt" used to vanish the moment another tab came to
        the front and only returned if the user went back to it.
        """
        if doc is None:
            self.window.hide_file_changed()
            return
        if doc in self._changed_docs:
            name = doc.path.name if doc.path is not None else doc.title
            self.window.show_file_changed(name)
            return
        if doc in self._encoding_pending:
            self.window.show_encoding_pending(self._doc_title(doc), doc.encoding)
            return
        if doc.autosave_pending:
            self.window.show_save_first(self._doc_title(doc))
            return
        if doc.truncated:
            from mishkah.core.large_file import PREVIEW_BYTES
            shown = min(PREVIEW_BYTES,
                        int(self.settings.hard_limit_mb or 0) * 1024 * 1024)
            self.window.show_preview(doc.title, _human(shown),
                                     _human(doc.size_on_disk))
            return
        self.window.hide_file_changed()

    def _sync_ui(self, editor: Optional[EditorView]) -> None:
        doc = self.document_for(editor)
        status = self.window.status
        if doc is None:
            # The welcome page has no document: nothing of the previous tab
            # may stay on screen (banner, file name in the title).
            self.window.hide_file_changed()
            self.window.hide_banner()
            self.window.setWindowTitle(i18n.tr("app.name"))
            return
        self._restore_banner(doc)
        self.refresh_invisible_banner()
        self.window.set_autosave(bool(doc.autosave))
        status.set_encoding(doc.encoding)
        status.set_line_ending(doc.line_ending)
        code = self._language_for(editor) if editor is not None else syntax.PLAIN.code
        # By *code*: the label is re-rendered on a language switch, so storing
        # the finished string left «بايثون» in an English window.
        status.set_language_code("" if code == syntax.PLAIN.code else code)
        status.set_size(doc.size_label)
        status.set_lines(doc.line_count)
        self.window.set_tab_menu_state(doc.pinned, doc.color)
        self.window.set_typing_menu_state(
            self.settings.auto_close_brackets,
            self.settings.auto_indent,
            self.settings.syntax_highlighting,
            doc.language,
            self.settings.live_markdown,
        )
        self.window.set_direction_menu(doc.direction_mode)
        self.window.set_encoding_menu(doc.encoding)
        self.window.set_line_ending_menu(doc.line_ending)
        self.window.setWindowTitle(
            i18n.tr("app.title", title=self._doc_title(doc), app=i18n.tr("app.name")))
        if editor is not None:
            status.set_zoom(editor.zoom_percent())
            status.set_direction(doc.direction_mode, editor.resolved_direction(),
                                 editor.document_side())

    def _on_language_detected(self, editor: EditorView) -> None:
        """The content revealed its language: recolour, silently (CD-12).

        No banner here on purpose: the colours are the message, and a strip
        pushing the first line down while someone types is noise.  Only the
        status bar names the language.
        """
        self._apply_highlighting(editor)
        code = editor.language_code()
        if code == syntax.PLAIN.code:
            self.window.status.set_language_code("")
            return
        self.window.status.set_language_code(code)
        doc = self._docs.get(editor)
        # Markdown has a different, more useful offer: turn the formatted view
        # on (CD-12 keeps it opt-in, so it is never switched silently).
        if (code == syntax.MARKDOWN_SPEC.code and doc is not None
                and not self.settings.live_markdown and not doc.language_banner_shown):
            doc.language_banner_shown = True
            if self.document_for(self.window.current_editor()) is doc:
                self.window.show_markdown_hint()

    def _menu_find(self, editor: EditorView, replace_mode: bool) -> None:
        """Open the find bar for the tab whose menu was used."""
        if self.window.current_editor() is not editor:
            return
        self.show_find(replace_mode)

    def _on_text_changed(self, editor: EditorView) -> None:
        doc = self._docs.get(editor)
        if doc is None or doc.truncated:
            return
        if editor.in_formatting_pass():
            # A direction change rewrites formats only; the file is untouched
            # and the tab must not claim otherwise (B1).
            return
        was_modified = doc.is_modified
        doc.mark_modified()
        self._arm_autosave()
        if not was_modified:
            self.window.set_tab_title(editor, self._doc_title(doc), True)
            self.window.setWindowTitle(i18n.tr(
                "app.title", title=self._doc_title(doc), app=i18n.tr("app.name")))

    @staticmethod
    def _doc_title(doc: DocumentModel) -> str:
        """A document's name for menus and message boxes (translated default)."""
        return i18n.tr("app.untitled") if doc.path is None else doc.title

    def _on_stats(self, lines: int, chars: int) -> None:
        self.window.status.set_lines(lines)
        doc = self.current_document()
        editor = self.window.current_editor()
        if doc is None or editor is None or doc.truncated:
            return
        text = editor.toPlainText()
        self.window.status.set_size(doc.live_size_label(text))
        self.window.status.set_words(text_stats.count_words(text))

    # ==================================================================
    # direction
    # ==================================================================
    def set_direction(self, mode: str) -> None:
        editor = self.window.current_editor()
        doc = self.current_document()
        if editor is None or doc is None:
            return
        if not doc.set_direction(mode):
            editor.apply_direction(mode, announce=False)
        else:
            editor.apply_direction(mode)
        self.window.set_direction_menu(mode)
        self.window.status.set_direction(mode, editor.resolved_direction(),
                                         editor.document_side())

    def _on_editor_direction(self, mode: str) -> None:
        doc = self.current_document()
        if doc is not None:
            doc.direction_mode = mode
        self.window.set_direction_menu(mode)
        editor = self.window.current_editor()
        self.window.status.set_direction(mode,
                                         editor.resolved_direction() if editor else LTR)

    def _on_resolved_direction(self, resolved: str) -> None:
        """The caret crossed into a paragraph of the other direction."""
        doc = self.current_document()
        if doc is None:
            return
        editor = self.window.current_editor()
        self.window.status.set_direction(
            doc.direction_mode, resolved,
            editor.document_side() if editor is not None else None)

    def auto_detect_direction(self) -> str:
        editor = self.window.current_editor()
        if editor is None:
            return LTR
        return dominant_direction(editor.toPlainText())

    # ==================================================================
    # edit helpers
    # ==================================================================
    def _editor_op(self, name: str) -> None:
        editor = self.window.current_editor()
        if editor is None:
            return
        getattr(editor, name)()

    def _delete_selection(self) -> None:
        editor = self.window.current_editor()
        if editor is not None:
            editor.textCursor().removeSelectedText()

    def _zoom(self, delta: int) -> None:
        editor = self.window.current_editor()
        if editor is None:
            return
        editor.zoom_in() if delta > 0 else editor.zoom_out()
        self.settings.font_size = editor.font().pointSize()

    def _zoom_reset(self) -> None:
        editor = self.window.current_editor()
        if editor is not None:
            editor.zoom_reset()
            self.settings.font_size = editor.font().pointSize()

    def goto_line(self) -> None:
        editor = self.window.current_editor()
        if editor is None:
            return
        line = self.window.goto_line_dialog(editor.blockCount())
        if line:
            editor.goto_line(line)

    def insert_date_time(self) -> None:
        editor = self.window.current_editor()
        if editor is None:
            return
        language = get_language(self.settings.ui_language)
        locale_format = "%d/%m/%Y %H:%M" if language.code != "en" else "%m/%d/%Y %H:%M"
        editor.insertPlainText(datetime.now().strftime(locale_format))

    # ==================================================================
    # find / replace
    # ==================================================================
    def show_find(self, replace_mode: bool) -> None:
        editor = self.window.current_editor()
        seed = editor.textCursor().selectedText() if editor else ""
        # Where the search starts from: incremental search always comes back
        # to this point, so refining a word does not walk down the document.
        self._find_anchor = editor.textCursor().position() if editor else 0
        self.window.find_bar.show_bar(replace_mode, seed)
        self._place_find_bar()

    def _place_find_bar(self) -> None:
        bar = self.window.find_bar
        bar.adjustSize()
        margin = 12
        x = self.window.width() - bar.width() - margin - 24
        bar.move(max(margin, x), 76)

    def _on_incremental_find(self, needle: str) -> None:
        """Search while the needle is being typed (CD-11).

        The caret keeps walking to the first match after the point where the
        bar was opened, so typing one more character refines the hit instead
        of skipping to the next one.  Nothing is marked modified: only the
        selection moves.
        """
        editor = self.window.current_editor()
        if editor is None or not needle:
            return
        anchor = getattr(self, "_find_anchor", None)
        if anchor is not None and 0 <= anchor <= editor.document().characterCount():
            cursor = editor.textCursor()
            cursor.setPosition(anchor)
            editor.setTextCursor(cursor)
        options = dict(self.window.find_bar.options())
        options["wrap"] = False          # incremental search never wraps
        found = editor.find_text(needle, backward=False, **options)
        self.window.find_bar.set_match_state(found)

    def _on_find(self, needle: str, backward: bool) -> None:
        editor = self.window.current_editor()
        if editor is None or not needle:
            return
        options = self.window.find_bar.options()
        found = editor.find_text(needle, backward=backward, **options)
        self.window.find_bar.set_match_state(found)
        if not found:
            self.window.status.set_position(
                *self._cursor_position(editor), 0)
            self.window.show_info(i18n.tr("find.not_found", text=needle))

    def _on_replace(self, needle: str, replacement: str) -> None:
        editor = self.window.current_editor()
        if editor is None or not needle:
            return
        options = self.window.find_bar.options()
        if editor.replace_current(needle, replacement,
                                  case_sensitive=options["case_sensitive"],
                                  whole_word=options["whole_word"],
                                  regex=options["regex"]):
            editor.find_text(needle, case_sensitive=options["case_sensitive"],
                             whole_word=options["whole_word"],
                             regex=options["regex"], wrap=options["wrap"])
        else:
            editor.find_text(needle, case_sensitive=options["case_sensitive"],
                             whole_word=options["whole_word"],
                             regex=options["regex"], wrap=options["wrap"])

    def _on_replace_all(self, needle: str, replacement: str) -> None:
        editor = self.window.current_editor()
        if editor is None or not needle:
            return
        options = self.window.find_bar.options()
        count = 0
        cursor = editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        editor.setTextCursor(cursor)
        while editor.find_text(needle, case_sensitive=options["case_sensitive"],
                               whole_word=options["whole_word"],
                               regex=options["regex"], wrap=False):
            editor.textCursor().insertText(replacement)
            count += 1
            if count > 1_000_000:      # safety valve
                break
        self.window.show_info(i18n.tr("find.replaced_count", count=count))

    def _cursor_position(self, editor: EditorView) -> tuple:
        cursor = editor.textCursor()
        return cursor.blockNumber() + 1, cursor.columnNumber() + 1

    def _focus_editor(self) -> None:
        editor = self.window.current_editor()
        if editor is not None:
            editor.setFocus()

    # ==================================================================
    # format / language
    # ==================================================================
    def set_ui_language(self, code: str) -> None:
        self.settings.ui_language = code
        i18n.set_language(code)
        self.window.retranslate()
        self._apply_appearance()
        for editor in self.window.editors():
            doc = self._docs.get(editor)
            if doc is not None:
                self.window.set_tab_title(editor, self._doc_title(doc), doc.is_modified)
            self.window.set_direction_menu(doc.direction_mode if doc else AUTO)
        self._sync_ui(self.window.current_editor())

    def set_word_wrap(self, enabled: bool) -> None:
        self.settings.word_wrap = enabled
        for editor in self.window.editors():
            editor.set_word_wrap(enabled)

    def set_line_numbers(self, enabled: bool) -> None:
        self.settings.line_numbers = enabled
        for editor in self.window.editors():
            editor.set_line_numbers_visible(enabled)

    def set_document_side_first_line(self, enabled: bool) -> None:
        """CD-20: let the first line pick the side a document is aligned to."""
        source = FIRST_LINE if enabled else FIRST_STRONG
        self.settings.document_side_source = source
        for editor in self.window.editors():
            editor.set_document_side_source(source)

    def set_show_invisible_chars(self, enabled: bool) -> None:
        """Diagnostic overlay: mark formatting characters, never edit them."""
        self.settings.show_invisible_chars = enabled
        for editor in self.window.editors():
            editor.set_show_invisible_chars(enabled)
        self._report_invisible_chars(enabled)

    def refresh_invisible_banner(self) -> None:
        """Keep the marker count in step with the document on screen."""
        if self.settings.show_invisible_chars:
            self._report_invisible_chars(True)

    def _report_invisible_chars(self, enabled: bool) -> None:
        """Say *how many* markers exist, so the toggle is never a silent no-op."""
        from mishkah.core.i18n import tr

        if not enabled:
            if self._invisible_banner:
                self.window.hide_banner()
                self._invisible_banner = False
            return
        editor = self.window.current_editor()
        count = editor.count_invisible_chars() if editor is not None else 0
        if count:
            self.window.show_banner(tr("banner.invisible_found", n=count))
        else:
            self.window.show_banner(tr("banner.invisible_none"))
        self._invisible_banner = True

    def set_line_ending(self, line_ending: str) -> None:
        doc = self.current_document()
        if doc is None:
            return
        doc.set_line_ending(line_ending)
        self.window.status.set_line_ending(line_ending)
        self.window.set_line_ending_menu(line_ending)

    def reopen_with_encoding(self, encoding: str) -> None:
        """Read the same file again with *encoding*, in this very tab (M1).

        Opening a second copy was the old behaviour: it silently forked the
        document and left the user with two tabs, one of them wrong.  The
        buffer is replaced in place, and saving stays blocked until the user
        accepts the conversion (see ``save_current``).
        """
        editor = self.window.current_editor()
        doc = self.current_document()
        if doc is None or editor is None:
            return
        if doc.path is None:
            doc.set_encoding(encoding)
            self.window.status.set_encoding(encoding)
            self.window.set_encoding_menu(encoding)
            return
        from mishkah.core import large_file

        try:
            text, fmt, truncated, size = large_file.read_text_chunked(
                doc.path, encoding=encoding, limit=1 << 62)
        except Exception as exc:                    # noqa: BLE001 - reported
            self.window.show_error(i18n.tr("dialog.error.open",
                                           path=str(doc.path), detail=str(exc)))
            return
        editor.blockSignals(True)
        try:
            doc.content = text
            doc.fmt = fmt
            doc.size_on_disk = size
            doc.truncated = truncated
            doc.disk_signature = stat_signature(doc.path)
            doc.revision += 1
            editor.load_content(text)
            editor.apply_direction(doc.direction_mode or AUTO, announce=False)
        finally:
            editor.blockSignals(False)
        doc.is_modified = False
        editor.document().setModified(False)
        doc.encoding_pending = True
        if doc not in self._encoding_pending:
            self._encoding_pending.append(doc)
        self.window.set_tab_title(editor, self._doc_title(doc), False)
        self._sync_ui(editor)
        self.window.show_encoding_pending(self._doc_title(doc), doc.encoding)

    def _choose_encoding(self) -> None:
        doc = self.current_document()
        if doc is None:
            return
        chosen = self.window.choose_encoding_dialog(doc.encoding)
        if chosen:
            if doc.path:
                self.reopen_with_encoding(chosen)
            else:
                doc.set_encoding(chosen)
                self.window.status.set_encoding(chosen)
                self.window.set_encoding_menu(chosen)

    def _cycle_line_ending(self) -> None:
        doc = self.current_document()
        if doc is None:
            return
        order = ("\r\n", "\n", "\r")
        nxt = order[(order.index(doc.line_ending) + 1) % 3]
        self.set_line_ending(nxt)

    # ==================================================================
    # misc
    # ==================================================================
    def print_current(self) -> None:
        editor = self.window.current_editor()
        if editor is None:
            return
        try:
            from PySide6.QtPrintSupport import QPrintDialog, QPrinter
        except ImportError:
            QMessageBox.warning(
                self.window,
                i18n.tr("menu.file.print"),
                "PySide6.QtPrintSupport is not installed on this system.",
            )
            return

        printer = QPrinter()
        dialog = QPrintDialog(printer, self.window)
        if dialog.exec():
            self.print_to(editor, printer)
            self.open_print_output(printer)

    @staticmethod
    def open_print_output(printer) -> Optional[str]:
        """Show the PDF that was just written, if the user printed to a file.

        "Print to File" is how everyone makes a PDF here — there is no export
        command — and until now the dialog closed on a file the user had to go
        hunting for.  Only a *file* is opened: a real printer has no path, and
        opening a shell on it would be nonsense.
        """
        try:
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices
            from PySide6.QtPrintSupport import QPrinter

            if printer.outputFormat() != QPrinter.OutputFormat.PdfFormat:
                return None
            path = printer.outputFileName()
            if not path or not Path(path).is_file():
                return None
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).resolve())))
            return str(Path(path).resolve())
        except Exception:      # pragma: no cover - desktop integration is optional
            return None

    @staticmethod
    def print_to(editor, printer) -> None:
        """Send *editor* to *printer*.

        Separated from the dialog so the printing path — including Arabic text
        and the bundled font — can be exercised without a human clicking
        "Print", and without a real printer: a ``QPrinter`` writing PDF is the
        same code with a different device.
        """
        editor.print_(printer)

    def show_about(self) -> None:
        AboutDialog(self.window).exec()

    # ==================================================================
    # tabs: pinned, coloured, closed together
    # ==================================================================
    def toggle_tab_pin(self, index: int) -> None:
        """Pin the tab at *index* on top of other windows while it is active.

        Only one tab can be pinned at a time; pinning a second one unpins the
        first, which keeps the behaviour predictable.
        """
        editor = self.window.editor_at(index)
        doc = self.document_for(editor)
        if doc is None:
            return
        pinned = not doc.pinned
        for other_editor, other_doc in self._docs.items():
            other_doc.pinned = False
            self.window.set_tab_pinned(other_editor, False)
        doc.pinned = pinned
        self.window.set_tab_pinned(editor, pinned)
        self.window.set_always_on_top(pinned)
        if pinned:
            self.window.tabs.setCurrentIndex(index)

    def set_tab_color(self, index: int, code: str) -> None:
        editor = self.window.editor_at(index)
        doc = self.document_for(editor)
        if doc is None or not tab_style.is_valid(code):
            return
        doc.color = code
        self.window.set_tab_color(editor, code)

    def set_current_tab_color(self, code: str) -> None:
        editor = self.window.current_editor()
        if editor is None:
            return
        self.set_tab_color(self.window.index_of(editor), code)

    def cycle_tab_color(self) -> None:
        editor = self.window.current_editor()
        doc = self.current_document()
        if doc is None or editor is None:
            return
        self.set_tab_color(self.window.index_of(editor),
                           tab_style.next_code(doc.color))

    def close_other_tabs(self, index: int) -> None:
        keep = self.window.editor_at(index)
        for editor in list(self.window.editors()):
            if editor is keep:
                continue
            self.close_tab(self.window.index_of(editor))

    # ==================================================================
    # syntax highlighting and typing assists
    # ==================================================================
    def set_syntax_highlighting(self, enabled: bool) -> None:
        self.settings.syntax_highlighting = enabled
        for editor in self.window.editors():
            self._apply_highlighting(editor)

    def set_live_markdown(self, enabled: bool) -> None:
        """Toggle the view-only Markdown layer on every open tab."""
        self.settings.live_markdown = enabled
        for editor in self.window.editors():
            editor.set_live_markdown(enabled, self.active_theme)
        current = self.window.current_editor()
        doc = self.document_for(current)
        if doc is not None:
            self.window.set_typing_menu_state(
                self.settings.auto_close_brackets,
                self.settings.auto_indent,
                self.settings.syntax_highlighting,
                doc.language,
                self.settings.live_markdown,
            )

    def set_tab_language(self, code: str) -> None:
        doc = self.current_document()
        editor = self.window.current_editor()
        if doc is None or editor is None:
            return
        doc.language = code or "auto"
        self._apply_highlighting(editor)

    def set_auto_close(self, enabled: bool) -> None:
        self.settings.auto_close_brackets = enabled
        for editor in self.window.editors():
            editor.set_auto_close(enabled)

    def set_auto_indent(self, enabled: bool) -> None:
        self.settings.auto_indent = enabled
        for editor in self.window.editors():
            editor.set_auto_indent(enabled)

    def set_always_on_top(self, enabled: bool) -> None:
        self.window.set_always_on_top(enabled)

    # ==================================================================
    # settings
    # ==================================================================
    def show_settings(self) -> None:
        """Open View ▸ Settings; Apply acts at once, OK acts and closes."""
        dialog = SettingsDialog(self.settings, self.window)
        # Apply must not close the window (CD-02), so it runs the same path.
        dialog.applied.connect(lambda: self._commit_settings(dialog))
        if dialog.exec() != SettingsDialog.DialogCode.Accepted:
            return
        self._commit_settings(dialog)

    def _commit_settings(self, dialog: SettingsDialog) -> None:
        """Write the dialog's values into settings and onto every open tab."""
        old = dialog.apply_to(self.settings)
        self.settings.save()
        self.window.apply_shortcut_settings(self.settings.redo_shortcut,
                                            self.settings.replace_shortcut)

        for editor in self.window.editors():
            self._apply_editing_options(editor)
            editor.set_tab_width(self.settings.tab_width)
            editor.set_font(self.editor_font())
            editor.set_word_wrap(self.settings.word_wrap)
            editor.set_line_numbers_visible(self.settings.line_numbers)
            editor.set_show_invisible_chars(self.settings.show_invisible_chars)
            editor.set_document_side_source(self.settings.document_side_source)

        self.window.act_word_wrap.setChecked(self.settings.word_wrap)
        self.window.act_line_numbers.setChecked(self.settings.line_numbers)
        self.window.status.setVisible(self.settings.show_status_bar)
        self.window.set_line_numbers_visible(self.settings.line_numbers)
        self.window.set_show_invisible_chars(self.settings.show_invisible_chars)
        self.window.set_document_side_first_line(
            self.settings.document_side_source == FIRST_LINE)
        doc_now = self.current_document()
        self.window.set_autosave(bool(doc_now and doc_now.autosave))
        if self._autosave_timer is not None:
            self._autosave_timer.setInterval(
                max(500, int(self.settings.autosave_idle_ms)))
        self.window.set_word_wrap_enabled(self.settings.word_wrap)

        self.window.set_typing_menu_state(
            self.settings.auto_close_brackets,
            self.settings.auto_indent,
            self.settings.syntax_highlighting,
            (self.current_document().language
             if self.current_document() is not None else "auto"),
            self.settings.live_markdown,
        )

        if old["ui_language"] != self.settings.ui_language:
            self.set_ui_language(self.settings.ui_language)
        else:
            self._apply_appearance()
        self.apply_theme()

    def set_theme(self, theme: str) -> None:
        self.settings.theme = theme
        self.settings.save()
        self.apply_theme()

    def apply_theme(self) -> None:
        """Re-apply the QSS for the configured theme (system/light/dark)."""
        from mishkah.app import apply_theme as _apply_theme

        app = QApplication.instance()
        if app is not None:
            self.active_theme = _apply_theme(app, self.settings.theme)
            self.window.tab_bar.set_theme_name(self.active_theme)
            for editor in self.window.editors():
                editor.set_theme_name(self.active_theme)

    def _clear_recent(self) -> None:
        self.settings.clear_recent()
        self.window.set_recent_files([])

    # ==================================================================
    # session
    # ==================================================================
    def restore_session(self, paths: Optional[List[str]] = None) -> None:
        if not self.settings.restore_session:
            return
        candidates = paths if paths is not None else self.settings.open_files
        opened = 0
        for raw in candidates or []:
            path = Path(raw)
            if path.exists():
                self.open_path(path)
                opened += 1
        return opened

    def save_session(self) -> None:
        # One window owns the session: a second window that wrote its own
        # ``open_files`` would erase the first one's list (B2 hazard).
        if not getattr(self, "owns_session", True):
            return
        self.settings.open_files = [
            str(doc.path) for doc in self._docs.values() if doc.path
        ]
        self.settings.word_wrap = self.window.act_word_wrap.isChecked()
        self.settings.line_numbers = self.window.act_line_numbers.isChecked()
        self.settings.save()

    def has_unsaved(self) -> bool:
        return any(doc.is_modified for doc in self._docs.values())

    def confirm_close(self) -> bool:
        """Ask about every dirty tab; True when the window may close."""
        for editor in self.window.editors():
            doc = self._docs.get(editor)
            if not doc or not doc.is_modified:
                continue
            self.window.tabs.setCurrentIndex(self.window.index_of(editor))
            answer = self.window.confirm_unsaved(self._doc_title(doc))
            if answer == QMessageBox.StandardButton.Cancel:
                return False
            if answer == QMessageBox.StandardButton.Save:
                self._window_close_after_save = True
                if not self.save_current():
                    self._window_close_after_save = False
                return False
        return True


def _human(num: float) -> str:
    for unit in ("B", "KiB", "MiB", "GiB"):
        if abs(num) < 1024 or unit == "GiB":
            return f"{num:.0f} {unit}" if unit == "B" else f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} GiB"
