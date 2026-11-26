"""Bugs the 1.0.02 manual gate (G3b) found, each pinned so it cannot return.

Three of them shared one cause and looked like three different features:

* **#17 — Ctrl+F did nothing** after the language had been switched.  Changing
  language clears the menu bar and builds it again, so every ``QAction`` is a
  new object; the controller still held the old ones, deleted silently.  Find,
  Replace, Undo, Redo, Cut, Copy, Paste, Delete, Select all, Go to line,
  Date/time and the three zoom actions were dead — only those, because every
  other menu entry is wired through the window's own signals.
* **#9 — the status bar stayed in the previous language.**  Its labels are
  formatted with ``tr()`` when they are *set*, and ``retranslate()`` only
  refreshed tooltips, so "Ln 1, Col 1 · 4 lines · 100%" kept the old words.
* **#16 — printing to PDF left the user hunting for the file.**  Print to File
  is the only way to make a PDF here, so the page that was just written is now
  opened.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.gui


def _controller(tmp_path, **overrides):
    from mishkah.controllers.main_controller import MainController
    from mishkah.core.settings import Settings
    from mishkah.services.file_service import FileService
    from mishkah.views.main_window import MainWindow

    window = MainWindow()
    settings = Settings(path=tmp_path / "settings.json", restore_session=False)
    for key, value in overrides.items():
        setattr(settings, key, value)
    controller = MainController(window, settings, FileService())
    window.resize(900, 640)
    return window, controller, settings


# ------------------------------------------------------- #17: dead actions
def test_the_menu_actions_still_work_after_a_language_switch(qapp, tmp_path):
    """G3b #17: a language switch silently unbound every action-based command."""
    window, controller, _ = _controller(tmp_path)
    try:
        window.show()
        controller.new_document()
        qapp.processEvents()

        controller.set_ui_language("ur")
        qapp.processEvents()

        window.act_find.trigger()
        qapp.processEvents()
        assert window.find_bar.isVisible(), "Find died with the rebuild"

        window.find_bar.hide_bar()
        qapp.processEvents()
        assert not window.find_bar.isVisible()
    finally:
        window.close()


def test_every_action_wired_to_an_action_object_survives_the_rebuild(qapp, tmp_path):
    """The same defect would hide in the other twelve if only Find were tested."""
    window, controller, _ = _controller(tmp_path)
    try:
        window.show()
        editor = controller.new_document()
        editor.load_content("hello\n")
        qapp.processEvents()
        controller.set_ui_language("ur")
        qapp.processEvents()

        cursor = editor.textCursor()
        cursor.select(cursor.SelectionType.Document)
        editor.setTextCursor(cursor)
        window.act_copy.trigger()
        assert qapp.clipboard().text() == "hello\n", "Copy is dead after the switch"

        window.act_select_all.trigger()
        assert editor.textCursor().hasSelection(), "Select all is dead"

        size_before = editor.font().pointSizeF()
        window.act_zoom_in.trigger()
        assert editor.font().pointSizeF() > size_before, "Zoom is dead"
        window.act_zoom_reset.trigger()
    finally:
        window.close()


def test_the_rebuild_does_not_double_the_connections(qapp, tmp_path):
    """Re-binding must replace the binding, not add a second one."""
    window, controller, _ = _controller(tmp_path)
    try:
        window.show()
        editor = controller.new_document()
        editor.load_content("hello world\n")
        base = editor.font().pointSizeF()
        controller.set_ui_language("ar")
        controller.set_ui_language("ur")
        qapp.processEvents()

        window.act_zoom_in.trigger()
        assert editor.font().pointSizeF() == base + 1, "zoom ran more than once"
    finally:
        window.close()


# ------------------------------------------------- #9: the status bar word
def test_the_status_bar_speaks_the_new_language(qapp, tmp_path):
    """G3b #9: everything moved to Urdu except the strip at the bottom."""
    from mishkah.core import i18n
    from mishkah.core.i18n import tr

    window, controller, _ = _controller(tmp_path)
    try:
        window.show()
        editor = controller.new_document()
        text = "سطر\nثاني\nثالث\n"
        editor.insertPlainText(text)
        # Keep the model in step: the status bar reads the document, not the
        # widget, and a test that skips this measures its own scaffolding.
        controller.document_for(editor).content = text
        controller._sync_ui(editor)          # noqa: SLF001
        qapp.processEvents()

        status = window.status
        # The caret sits at the end after typing: four lines, column one.
        assert status._position.text() == tr("status.position", line=4, col=1)
        english = status._lines.text()
        lines, words = status._line_count, status._word_count
        assert lines, "the scaffold produced no line count to translate"

        controller.set_ui_language("ur")
        qapp.processEvents()

        assert status._lines.text() != english, "the line count stayed behind"
        assert status._lines.text() == tr("status.lines", count=f"{lines:,}")
        if words:
            assert status._words.text() == tr("status.words", count=words)
        assert status._position.text() == tr("status.position", line=4, col=1)
        i18n.set_language("en")
    finally:
        window.close()


def test_the_status_bar_keeps_its_values_across_the_switch(qapp, tmp_path):
    """Translating must not reset the numbers it is translating."""
    from mishkah.core import i18n
    from mishkah.core.i18n import tr

    window, controller, _ = _controller(tmp_path)
    try:
        window.show()
        controller.new_document()
        status = window.status
        status.set_position(12, 7, 3)
        status.set_zoom(125)
        status.set_line_ending("\r\n")
        status.set_encoding("cp1256")
        status.set_words(41)

        # The widget on its own: the window's own re-sync would overwrite the
        # zoom from the editor, and that is correct — this test is about
        # re-rendering, not about who owns the value.
        i18n.set_language("ar")
        status.retranslate()

        assert status._position.text() == tr("status.position", line=12, col=7)
        assert status._words.text() == tr("status.words", count=41)
        assert status._zoom.text() == "125%"
        assert status._line_ending.text() == "CRLF"
        assert status._encoding.text() == "CP1256"
        i18n.set_language("en")
    finally:
        window.close()


# ------------------------------------------- #16: open the PDF we just wrote
def test_printing_to_a_file_opens_it(qapp, tmp_path):
    """G3b #16: "Print to File" is the only way to a PDF, so show the PDF."""
    from PySide6.QtPrintSupport import QPrinter

    window, controller, _ = _controller(tmp_path)
    opened = []
    try:
        window.show()
        editor = controller.new_document()
        editor.load_content("نص عربي للطباعة\n")
        qapp.processEvents()

        target = tmp_path / "out.pdf"
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(str(target))
        controller.print_to(editor, printer)

        class _Spy:
            @staticmethod
            def openUrl(url):
                opened.append(url.toLocalFile())
                return True

        from PySide6.QtGui import QDesktopServices
        original = QDesktopServices.openUrl
        QDesktopServices.openUrl = _Spy.openUrl        # type: ignore[assignment]
        try:
            path = controller.open_print_output(printer)
        finally:
            QDesktopServices.openUrl = original        # type: ignore[assignment]

        assert path is not None and path.endswith("out.pdf")
        assert opened and opened[0].endswith("out.pdf")
    finally:
        window.close()


def test_a_real_printer_opens_nothing(qapp, tmp_path):
    """There is no file to open, and a shell on a printer is not a document."""
    from PySide6.QtPrintSupport import QPrinter

    window, controller, _ = _controller(tmp_path)
    try:
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        assert controller.open_print_output(printer) is None
    finally:
        window.close()


# ------------------------------------------- #13: a wait you can see
def test_a_large_file_shows_a_progress_dialog_and_closes_it(qapp, tmp_path):
    """G3b #13: 98 MB froze for twenty seconds with only a title-bar percentage."""
    import time

    window, controller, _ = _controller(tmp_path)
    try:
        window.show()
        big = tmp_path / "big.txt"
        big.write_text("سطر عربي للاختبار\n" * 250_000, encoding="utf-8")
        assert big.stat().st_size > controller.BIG_LOAD_BYTES

        controller.open_path(big)
        qapp.processEvents()
        dialog = getattr(controller, "_load_dialog", None)
        assert dialog is not None and dialog.isVisible(), "the wait was invisible"

        deadline = time.time() + 60
        while time.time() < deadline:
            qapp.processEvents()
            doc = controller.current_document()
            if doc is not None and doc.content:
                break
            time.sleep(0.02)
        assert controller.current_document().content, "the file never arrived"
        assert getattr(controller, "_load_dialog", None) is None, "dialog left behind"
    finally:
        window.close()


def test_a_small_file_does_not_show_the_dialog(qapp, tmp_path):
    """A dialog for every 20-byte file is worse than none at all."""
    window, controller, _ = _controller(tmp_path)
    try:
        window.show()
        small = tmp_path / "note.txt"
        small.write_text("مرحبا\n", encoding="utf-8")
        controller.open_path(small)
        qapp.processEvents()
        assert getattr(controller, "_load_dialog", None) is None
    finally:
        window.close()


# ------------------------------- #15: block data must not be Python-owned
def test_toggling_highlighting_over_markdown_does_not_crash(qapp, tmp_path):
    """The crash: Qt deletes block user data in C++; a Python wrapper died there.

    Seen as ``Fatal Python error: none_dealloc`` while measuring G3b #15, and as
    the SIGSEGV in CI during interpreter shutdown: both were the same mistake —
    a ``QTextBlockUserData`` owned by Qt but allocated in Python.
    """
    window, controller, _ = _controller(tmp_path)
    try:
        window.show()
        editor = controller.new_document()
        editor.load_content(("# عنوان\n\n- عنصر\n\n> اقتباس\n\n"
                             "فقرة **عريض** و `كود`.\n\n") * 400)
        qapp.processEvents()

        controller.set_live_markdown(True)
        qapp.processEvents()
        controller.set_syntax_highlighting(True)
        qapp.processEvents()
        controller.set_live_markdown(False)
        qapp.processEvents()
        controller.set_syntax_highlighting(False)
        qapp.processEvents()
        controller.set_live_markdown(True)
        qapp.processEvents()

        assert editor.live_markdown_enabled()
        decorator = editor.markdown_decorator()
        assert decorator is not None
        number = decorator.window()[0]
        assert decorator.parsed_line(number) is not None or number > 0
    finally:
        window.close()


def test_markdown_block_data_is_not_handed_to_qt(qapp, tmp_path):
    """A static rule: no Python-owned QTextBlockUserData anywhere in the widgets."""
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent / "src" / "mishkah"
    offenders = []
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if re.search(r"setCurrentBlockUserData\s*\(\s*[A-Za-z_]", text):
            offenders.append(f"{path.name}: setCurrentBlockUserData(python object)")
        if re.search(r"class\s+\w+\s*\(\s*QTextBlockUserData\s*\)", text):
            offenders.append(f"{path.name}: QTextBlockUserData subclass")
    assert not offenders, offenders
