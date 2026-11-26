"""Printing an Arabic document must produce a real, paginated PDF (S2).

The print path shipped with no test at all: the only way to know whether Arabic
survived it was to own a printer.  A ``QPrinter`` that writes PDF is the same
code with a different device, so the whole path — the editor's layout, the
bundled font, pagination — runs headlessly here.

What this proves: the output is a PDF, it has the expected number of pages, and
the font is embedded (a glyph run that silently fell back for every character
would leave the embedding to a system font, and on a machine without one the
Arabic would arrive as empty boxes).  What it cannot prove: that a specific
physical printer renders it the same way.
"""

from __future__ import annotations

import re

import pytest

pytestmark = pytest.mark.gui

ARABIC_LINE = "سطر عربي طويل للتجربة مع أرقام ١٢٣ وحروف لاتينية abc"


def _editor(lines: int = 200):
    from mishkah.models.document import DocumentModel
    from mishkah.views.editor_view import EditorView

    editor = EditorView(DocumentModel())
    editor.setPlainText("\n".join(ARABIC_LINE for _ in range(lines)))
    return editor


def _pdf_printer(path):
    from PySide6.QtPrintSupport import QPrinter

    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(str(path))
    return printer


def _pages(data: bytes) -> int:
    """Count ``/Type /Page`` objects — ``/Pages`` is the tree node, not a page."""
    return len(re.findall(rb"/Type\s*/Page[^s]", data))


def test_an_arabic_document_prints_to_a_paginated_pdf(qapp, tmp_path):
    from mishkah.controllers.main_controller import MainController

    target = tmp_path / "arabic.pdf"
    MainController.print_to(_editor(), _pdf_printer(target))

    assert target.is_file()
    data = target.read_bytes()
    assert data.startswith(b"%PDF"), data[:16]
    assert len(data) > 4000, "a 200-line document should not produce a stub"
    assert _pages(data) > 1, "200 lines did not paginate"
    assert b"/FontFile" in data, "no font was embedded"


def test_a_longer_document_gets_more_pages(qapp, tmp_path):
    from mishkah.controllers.main_controller import MainController

    short, long = tmp_path / "short.pdf", tmp_path / "long.pdf"
    MainController.print_to(_editor(40), _pdf_printer(short))
    MainController.print_to(_editor(600), _pdf_printer(long))
    assert _pages(long.read_bytes()) > _pages(short.read_bytes())


def test_an_empty_document_still_produces_a_valid_pdf(qapp, tmp_path):
    from mishkah.controllers.main_controller import MainController
    from mishkah.models.document import DocumentModel
    from mishkah.views.editor_view import EditorView

    target = tmp_path / "empty.pdf"
    MainController.print_to(EditorView(DocumentModel()), _pdf_printer(target))
    data = target.read_bytes()
    assert data.startswith(b"%PDF")
    assert _pages(data) == 1


def test_the_print_command_goes_through_the_dialog(qapp, tmp_path, monkeypatch):
    """File ▸ Print must reach the same code, not a parallel copy of it."""
    from PySide6 import QtPrintSupport
    from PySide6.QtPrintSupport import QPrinter

    from mishkah.controllers.main_controller import MainController
    from mishkah.core.settings import Settings
    from mishkah.services.file_service import FileService
    from mishkah.views.main_window import MainWindow

    target = tmp_path / "via-dialog.pdf"
    opened = []

    class FakeDialog:
        def __init__(self, printer, parent=None):
            printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            printer.setOutputFileName(str(target))
            opened.append(printer)

        def exec(self):  # noqa: A003 - Qt's name
            return 1

    monkeypatch.setattr(QtPrintSupport, "QPrintDialog", FakeDialog)

    window = MainWindow()
    controller = MainController(window, Settings(path=tmp_path / "s.json",
                                                 restore_session=False),
                                FileService())
    try:
        controller.new_document().setPlainText(ARABIC_LINE)
        controller.print_current()
    finally:
        window.close()

    assert opened, "the dialog was never opened"
    assert target.is_file() and target.read_bytes().startswith(b"%PDF")


def test_printing_a_window_with_no_document_is_a_no_op(qapp, tmp_path):
    from mishkah.controllers.main_controller import MainController
    from mishkah.core.settings import Settings
    from mishkah.services.file_service import FileService
    from mishkah.views.main_window import MainWindow

    window = MainWindow()
    controller = MainController(window, Settings(path=tmp_path / "s.json",
                                                 restore_session=False), FileService())
    try:
        controller.print_current()      # no editor: must not raise
    finally:
        window.close()
