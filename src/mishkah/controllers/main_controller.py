"""Glue between the window, the file service and the settings."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import QObject, Qt
from PySide6.QtGui import QFont, QTextCursor
from PySide6.QtWidgets import QApplication, QMessageBox

from mishkah.core import i18n, syntax, tab_style
from mishkah.core.languages import editor_font_families, get_language
from mishkah.core.settings import Settings
from mishkah.core.text_direction import AUTO, LTR, dominant_direction
from mishkah.models.document import DocumentModel
from mishkah.services.file_service import FileService
from mishkah.views.editor_view import EditorView
from mishkah.views.main_window import MainWindow
from mishkah.widgets.about_dialog import AboutDialog
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
        self._pending_paths: Dict[int, str] = {}   # tab index -> path being loaded
        self._busy = False

        self.active_theme = self._resolve_theme(settings.theme)
        i18n.set_language(settings.ui_language)
        self._wire()
        self._apply_appearance()

    # ==================================================================
    # wiring
    # ==================================================================
    def _wire(self) -> None:
        w = self.window
        w.file_new.connect(self.new_document)
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

        w.find_bar.find_requested.connect(self._on_find)
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

    # ==================================================================
    # appearance
    # ==================================================================
    def _apply_appearance(self) -> None:
        s = self.settings
        language = get_language(s.ui_language)

        ui_font = QFont()
        ui_font.setFamilies(list(language.ui_fonts))
        ui_font.setPointSize(max(8, s.font_size - 1))
        self.window.set_ui_font(ui_font)

        self.window.set_language_menu(s.ui_language)
        self.window.act_word_wrap.setChecked(s.word_wrap)
        self.window.act_line_numbers.setChecked(s.line_numbers)
        self.window.status.setVisible(s.show_status_bar)
        self.window.set_recent_files(s.recent_files)

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

    def _bind_editor(self, editor: EditorView, doc: DocumentModel) -> None:
        self._docs[editor] = doc
        editor.set_word_wrap(self.settings.word_wrap)
        editor.set_line_numbers_visible(self.settings.line_numbers)
        self._apply_editing_options(editor)
        editor.cursor_moved.connect(
            lambda line, col, sel: self.window.status.set_position(line, col, sel))
        editor.zoom_changed.connect(self.window.status.set_zoom)
        editor.direction_changed.connect(self._on_editor_direction)
        editor.stats_changed.connect(self._on_stats)
        editor.textChanged.connect(lambda e=editor: self._on_text_changed(e))

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
        return syntax.language_for_path(doc.path if doc is not None else None)

    def document_for(self, editor: Optional[EditorView]) -> Optional[DocumentModel]:
        if editor is None:
            return None
        return self._docs.get(editor)

    def current_document(self) -> Optional[DocumentModel]:
        return self.document_for(self.window.current_editor())

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
        limit_mb = None
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
        editor.setPlainText("")
        self.window.set_tab_title(editor, path.name, False)
        self.files.load(path, encoding=encoding, limit_mb=limit_mb)

    def _on_loaded(self, doc: DocumentModel) -> None:
        editor = self._editor_for_path(doc.path)
        if editor is None:
            editor = self.new_document()
        live = self._docs.get(editor)
        if live is not None:
            doc.direction_mode = live.direction_mode
        self._docs[editor] = doc

        # Direction: "auto" keeps Qt's per-paragraph rule; an explicit mode
        # in settings is honoured, otherwise the content decides.
        if doc.direction_mode == AUTO:
            doc.direction_mode = AUTO
        editor.set_document(doc)
        editor.set_font_size(self.settings.font_size)

        if doc.uses_performance_mode and self.settings.performance_mode:
            editor.set_word_wrap(False)
            editor.set_line_numbers_visible(False)

        self.window.set_tab_title(editor, self._doc_title(doc), False)
        if doc.truncated:
            self.window.show_banner(i18n.tr(
                "banner.preview", size=_human(8 * 1024 * 1024),
                total=_human(doc.size_on_disk)))
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
        self.window.setWindowTitle(
            f"{i18n.tr('app.name')} — {done * 100 // max(1, total)}%")

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
        self._sync_content(editor, doc)
        target = doc.path
        if as_copy or target is None:
            start = str(target) if target else ""
            chosen = self.window.save_file_dialog(start)
            if not chosen:
                return False
            target = Path(chosen)
        self.files.save(doc, target)
        return True

    def save_all(self) -> None:
        for editor in self.window.editors():
            doc = self._docs.get(editor)
            if doc and doc.is_modified and doc.path and not doc.truncated:
                self._sync_content(editor, doc)
                self.files.save(doc, doc.path)

    def _on_saved(self, doc: DocumentModel, written: int) -> None:
        editor = self._editor_for_document(doc)
        if editor is not None:
            self.window.set_tab_title(editor, self._doc_title(doc), False)
        self.settings.remember_file(str(doc.path))
        self.window.set_recent_files(self.settings.recent_files)
        self.window.setWindowTitle(i18n.tr("app.name"))
        self._sync_ui(editor)

    def _on_save_failed(self, path: str, title: str, detail: str) -> None:
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
            return
        doc = self._docs.get(editor)
        if doc and doc.is_modified:
            answer = self.window.confirm_unsaved(self._doc_title(doc))
            if answer == QMessageBox.StandardButton.Cancel:
                return
            if answer == QMessageBox.StandardButton.Save:
                self.window.tabs.setCurrentIndex(index)
                if not self.save_current():
                    return
        self._docs.pop(editor, None)
        # Closing the pinned tab must release the "always on top" hint, or
        # the window would keep floating above everything with nothing pinned.
        self.window.set_tab_pinned(editor, False)
        self.window.set_always_on_top(False)
        self.window.close_editor(editor)
        if self.window.tab_count() == 0:
            self.new_document()
        else:
            self._sync_ui(self.window.current_editor())

    def _on_tab_changed(self, index: int) -> None:
        editor = self.window.editor_at(index)
        doc = self.document_for(editor)
        # The pinned tab owns "always on top"; switching away from it drops
        # the hint so the window does not stay above everything silently.
        self.window.set_always_on_top(bool(doc and doc.pinned))
        self._sync_ui(editor)

    def _sync_ui(self, editor: Optional[EditorView]) -> None:
        doc = self.document_for(editor)
        status = self.window.status
        if doc is None:
            return
        status.set_encoding(doc.encoding)
        status.set_line_ending(doc.line_ending)
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
            status.set_direction(doc.direction_mode, editor.resolved_direction())

    def _on_text_changed(self, editor: EditorView) -> None:
        doc = self._docs.get(editor)
        if doc is None or doc.truncated:
            return
        if not doc.is_modified:
            doc.mark_modified()
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
        self.window.status.set_size(doc.live_size_label(editor.toPlainText()))

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
        self.window.status.set_direction(mode, editor.resolved_direction())

    def _on_editor_direction(self, mode: str) -> None:
        doc = self.current_document()
        if doc is not None:
            doc.direction_mode = mode
        self.window.set_direction_menu(mode)
        editor = self.window.current_editor()
        self.window.status.set_direction(mode,
                                         editor.resolved_direction() if editor else LTR)

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
        self.window.find_bar.show_bar(replace_mode, seed)
        self._place_find_bar()

    def _place_find_bar(self) -> None:
        bar = self.window.find_bar
        bar.adjustSize()
        margin = 12
        x = self.window.width() - bar.width() - margin - 24
        bar.move(max(margin, x), 76)

    def _on_find(self, needle: str, backward: bool) -> None:
        editor = self.window.current_editor()
        if editor is None or not needle:
            return
        options = self.window.find_bar.options()
        found = editor.find_text(needle, backward=backward, **options)
        if not found:
            self.window.status.set_position(
                *self._cursor_position(editor), 0)
            self.window.show_info(i18n.tr("find.not_found", text=needle))

    def _on_replace(self, needle: str, replacement: str) -> None:
        editor = self.window.current_editor()
        if editor is None or not needle:
            return
        options = self.window.find_bar.options()
        if editor.replace_current(needle, replacement, options["case_sensitive"]):
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

    def set_line_ending(self, line_ending: str) -> None:
        doc = self.current_document()
        if doc is None:
            return
        doc.set_line_ending(line_ending)
        self.window.status.set_line_ending(line_ending)
        self.window.set_line_ending_menu(line_ending)

    def reopen_with_encoding(self, encoding: str) -> None:
        doc = self.current_document()
        if doc is None or doc.path is None:
            return
        self._begin_load(doc.path, encoding=encoding)

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
        from PySide6.QtPrintSupport import QPrintDialog, QPrinter

        printer = QPrinter()
        dialog = QPrintDialog(printer, self.window)
        if dialog.exec():
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
        """Open View ▸ Settings and apply whatever the user accepted."""
        dialog = SettingsDialog(self.settings, self.window)
        if dialog.exec() != SettingsDialog.DialogCode.Accepted:
            return

        old = dialog.apply_to(self.settings)
        self.settings.save()

        for editor in self.window.editors():
            self._apply_editing_options(editor)
            editor.set_tab_width(self.settings.tab_width)
            editor.set_font(self.editor_font())
            editor.set_word_wrap(self.settings.word_wrap)
            editor.set_line_numbers_visible(self.settings.line_numbers)

        self.window.act_word_wrap.setChecked(self.settings.word_wrap)
        self.window.act_line_numbers.setChecked(self.settings.line_numbers)
        self.window.status.setVisible(self.settings.show_status_bar)
        self.window.set_line_numbers_visible(self.settings.line_numbers)
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
            if answer == QMessageBox.StandardButton.Save and not self.save_current():
                return False
        return True


def _human(num: float) -> str:
    for unit in ("B", "KiB", "MiB", "GiB"):
        if abs(num) < 1024 or unit == "GiB":
            return f"{num:.0f} {unit}" if unit == "B" else f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} GiB"
