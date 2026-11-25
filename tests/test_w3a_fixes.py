"""The small fixes of W3a: B1, B3, M5 and the missing label keys (CD-29)."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QMessageBox

pytestmark = pytest.mark.gui

LANGS = ("en", "ar", "zh-Hans", "hi", "es", "fr", "bn", "pt", "ru", "ur")


def _controller(tmp_path):
    from mishkah.controllers.main_controller import MainController
    from mishkah.core.settings import Settings
    from mishkah.services.file_service import FileService
    from mishkah.views.main_window import MainWindow

    window = MainWindow()
    settings = Settings(path=tmp_path / "settings.json", restore_session=False)
    return window, MainController(window, settings, FileService()), settings


def _editor(qapp, text: str = ""):
    from mishkah.models.document import DocumentModel
    from mishkah.views.editor_view import EditorView

    editor = EditorView(DocumentModel())
    editor.resize(500, 300)
    if text:
        editor.setPlainText(text)
    return editor


# --------------------------------------------------------------------- B1
def test_choosing_a_side_does_not_mark_the_document_modified(qapp, tmp_path):
    window, controller, _ = _controller(tmp_path)
    try:
        editor = controller.new_document()
        editor.setPlainText("hello world\n")
        doc = controller.document_for(editor)
        doc.mark_saved(None, 0)
        editor.document().setModified(False)

        controller.set_direction("rtl")
        assert editor.document().isModified() is False
        assert doc.is_modified is False

        controller.set_direction("auto")
        assert editor.document().isModified() is False
        assert doc.is_modified is False
    finally:
        window.close()


def test_closing_after_a_side_change_does_not_ask_to_save(qapp, tmp_path):
    """B1: closing a saved file after flipping its side asks nothing."""
    window, controller, _ = _controller(tmp_path)
    asked = []
    try:
        window.confirm_unsaved = lambda title: (
            asked.append(title), QMessageBox.StandardButton.Discard)[1]
        editor = controller.new_document()
        editor.setPlainText("مرحبا\n")
        doc = controller.document_for(editor)
        doc.mark_saved(None, 0)
        editor.document().setModified(False)

        controller.set_direction("ltr")
        index = window.index_of(editor)
        controller.close_tab(index)
        assert asked == [], "the side change is not an edit"
    finally:
        window.close()


# --------------------------------------------------------------------- B3
def test_replace_refuses_a_selection_that_is_not_a_match(qapp):
    editor = _editor(qapp, "concatenate this\n")
    cursor = editor.textCursor()
    cursor.setPosition(0)
    cursor.setPosition(len("concatenate"), cursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)

    assert editor.replace_current("cat", "dog", whole_word=True) is False
    assert editor.document().toPlainText().startswith("concatenate")


def test_replace_respects_case_whole_word_and_regex(qapp):
    editor = _editor(qapp, "Hello cat 123\n")
    cursor = editor.textCursor()
    cursor.setPosition(0)
    cursor.setPosition(len("Hello"), cursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)
    assert editor.replace_current("hello", "Hi") is True
    assert editor.document().toPlainText().startswith("Hi cat")

    cursor = editor.textCursor()
    cursor.setPosition(3)
    cursor.setPosition(6, cursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)
    assert editor.replace_current("cat", "dog", whole_word=True) is True

    cursor = editor.textCursor()
    cursor.setPosition(7)
    cursor.setPosition(10, cursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)
    assert editor.replace_current(r"\d+", "42", regex=True) is True
    assert editor.document().toPlainText().startswith("Hi dog 42")


def test_replace_all_never_touches_a_non_matching_word(qapp, tmp_path):
    window, controller, _ = _controller(tmp_path)
    try:
        window.show_info = lambda *a, **k: None      # no modal box in a test
        editor = controller.new_document()
        editor.setPlainText("cat concatenate cat\n")
        controller.show_find(True)
        window.find_bar.whole_word.setChecked(True)
        window.find_bar.find_edit.setText("cat")
        window.find_bar.replace_edit.setText("dog")
        controller._on_replace_all("cat", "dog")     # noqa: SLF001
        assert editor.document().toPlainText() == "dog concatenate dog\n"
    finally:
        window.close()


# --------------------------------------------------------------------- M5
def test_shift_tab_always_outdents(qapp):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    editor = _editor(qapp, "    indented\nsecond\n")
    cursor = editor.textCursor()
    cursor.setPosition(2)                     # inside the indented line
    editor.setTextCursor(cursor)
    editor.show()

    # Both spellings of the key must outdent; the old order inserted a tab.
    QTest.keyClick(editor, Qt.Key.Key_Tab, Qt.KeyboardModifier.ShiftModifier)
    assert editor.document().toPlainText().startswith("indented\n")

    editor.setPlainText("\tsecond\nnext\n")
    cursor = editor.textCursor()
    cursor.setPosition(1)
    editor.setTextCursor(cursor)
    QTest.keyClick(editor, Qt.Key.Key_Backtab)
    text = editor.document().toPlainText()
    assert text.startswith("second\n")
    assert "\t" not in text.split("\n")[0]


# --------------------------------------------------------------- M4 / L1
@pytest.mark.parametrize("key", ["dialog.progress", "settings.large_files.note",
                                 "action.open_full", "settings.large_files"])
def test_the_missing_keys_exist_in_every_language(key):
    from mishkah.core.i18n_data import STRINGS

    assert key in STRINGS, key
    for lang in LANGS:
        assert lang in STRINGS[key], f"{key} is missing {lang}"
        assert STRINGS[key][lang].strip(), f"{key}/{lang} is empty"


def test_the_progress_text_is_translated_not_raw():
    from mishkah.core import i18n

    for lang in LANGS:
        i18n.set_language(lang)
        text = i18n.tr("dialog.progress", done="1 MB", total="2 MB")
        assert "dialog.progress" not in text
        assert "1 MB" in text and "2 MB" in text
    i18n.set_language("en")
