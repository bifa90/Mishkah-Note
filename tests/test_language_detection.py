"""Pasted code must colour itself (CD-12).

The reported bug: pasting code into an unsaved tab stayed grey until the file
was saved, closed and opened again — the language came from the file name only.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.gui

PYTHON_CODE = "def run(a, b):\n    return a + b\n"


def _controller(tmp_path):
    from mishkah.controllers.main_controller import MainController
    from mishkah.core.settings import Settings
    from mishkah.services.file_service import FileService
    from mishkah.views.main_window import MainWindow

    window = MainWindow()
    settings = Settings(path=tmp_path / "settings.json", restore_session=False)
    return window, MainController(window, settings, FileService()), settings


def _wait_for_load(controller, window, timeout_ms: int = 4000):
    """Wait until the background loader has actually filled the tab."""
    from PySide6.QtTest import QTest

    waited = 0
    while waited < timeout_ms:
        editor = window.current_editor()
        doc = controller.document_for(editor) if editor is not None else None
        if doc is not None and doc.content:
            return editor
        QTest.qWait(50)
        waited += 50
    return window.current_editor()


def _paste(editor, text: str) -> None:
    from PySide6.QtCore import QMimeData
    from PySide6.QtGui import QTextCursor

    data = QMimeData()
    data.setText(text)
    cursor = editor.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    editor.setTextCursor(cursor)
    editor.insertFromMimeData(data)


def test_pasting_code_into_an_untitled_tab_colours_it(qapp, tmp_path):
    from PySide6.QtTest import QTest

    window, controller, _ = _controller(tmp_path)
    asked = []
    try:
        window.show_info = lambda *a, **k: None
        editor = controller.new_document()
        before = editor.detected_language()
        assert before == "plain"

        _paste(editor, PYTHON_CODE)
        QTest.qWait(600)                      # the sniff is debounced
        assert editor.detected_language() == "python"
        assert controller._language_for(editor) == "python"   # noqa: SLF001
        assert editor.language_code() == "python"
        assert asked == []
    finally:
        window.close()


def test_typing_code_without_pasting_also_colours_it(qapp, tmp_path):
    from PySide6.QtTest import QTest

    window, controller, _ = _controller(tmp_path)
    try:
        editor = controller.new_document()
        QTest.keyClicks(editor, "def f():")
        QTest.qWait(600)
        assert editor.detected_language() == "python"
    finally:
        window.close()


def test_a_txt_file_still_asks_the_content(qapp, tmp_path):
    """".txt" says nothing about the language, so the code inside decides."""

    window, controller, _ = _controller(tmp_path)
    try:
        target = tmp_path / "notes.txt"
        target.write_text(PYTHON_CODE, encoding="utf-8")
        controller._begin_load(target)          # noqa: SLF001
        editor = _wait_for_load(controller, window)
        assert editor is not None
        controller._apply_highlighting(editor)   # noqa: SLF001
        assert controller._language_for(editor) == "python"   # noqa: SLF001
    finally:
        window.close()


def test_a_named_extension_still_wins(qapp, tmp_path):

    window, controller, _ = _controller(tmp_path)
    try:
        target = tmp_path / "notes.md"
        target.write_text(PYTHON_CODE, encoding="utf-8")
        controller._begin_load(target)          # noqa: SLF001
        editor = _wait_for_load(controller, window)
        assert controller._language_for(editor) == "markdown"   # noqa: SLF001
    finally:
        window.close()


def test_a_python_file_is_python_from_the_start(qapp, tmp_path):

    window, controller, _ = _controller(tmp_path)
    try:
        target = tmp_path / "script.py"
        target.write_text(PYTHON_CODE, encoding="utf-8")
        controller._begin_load(target)          # noqa: SLF001
        editor = _wait_for_load(controller, window)
        assert controller._language_for(editor) == "python"   # noqa: SLF001
    finally:
        window.close()


def test_a_manual_choice_beats_the_guess(qapp, tmp_path):
    from PySide6.QtTest import QTest

    window, controller, _ = _controller(tmp_path)
    try:
        editor = controller.new_document()
        _paste(editor, PYTHON_CODE)
        QTest.qWait(600)
        controller.set_tab_language("json")
        assert controller._language_for(editor) == "json"     # noqa: SLF001
        assert editor.language_code() == "json"
    finally:
        window.close()


def test_the_status_bar_names_the_detected_language(qapp, tmp_path):
    from PySide6.QtTest import QTest

    window, controller, _ = _controller(tmp_path)
    try:
        editor = controller.new_document()
        _paste(editor, "const x = 1;\nfunction go() { return x; }\n")
        QTest.qWait(600)
        assert editor.detected_language() == "javascript"
        assert "JavaScript" in window.status._language.text()   # noqa: SLF001
    finally:
        window.close()
