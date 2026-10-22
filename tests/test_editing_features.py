"""GUI-level tests for auto-pairing, smart indent and syntax highlighting."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtTest import QTest

from mishkah.models.document import DocumentModel
from mishkah.views.editor_view import EditorView

pytestmark = pytest.mark.usefixtures("qapp")


def make_editor(text: str = "", path=None) -> EditorView:
    doc = DocumentModel(content=text, path=path)
    editor = EditorView(doc)
    editor.load_content(text)
    cursor = editor.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    editor.setTextCursor(cursor)
    return editor


def type_text(editor: EditorView, text: str) -> None:
    QTest.keyClicks(editor, text)


# ---------------------------------------------------------------------
# auto pairing
# ---------------------------------------------------------------------
def test_brackets_are_closed_automatically(qapp):
    editor = make_editor()
    type_text(editor, "(")
    assert editor.toPlainText() == "()"
    assert editor.textCursor().position() == 1          # caret stays inside


def test_quotes_are_closed_automatically(qapp):
    editor = make_editor()
    type_text(editor, '"hi')
    assert editor.toPlainText() == '"hi"'
    assert editor.textCursor().position() == 3


def test_typing_the_closing_bracket_steps_over_it(qapp):
    editor = make_editor()
    type_text(editor, "(a)")
    assert editor.toPlainText() == "(a)"                # not "(a))"
    assert editor.textCursor().position() == 3


def test_pairing_wraps_a_selection(qapp):
    editor = make_editor("word")
    cursor = editor.textCursor()
    cursor.select(QTextCursor.SelectionType.Document)
    editor.setTextCursor(cursor)
    type_text(editor, "(")
    assert editor.toPlainText() == "(word)"


def test_no_pairing_inside_a_word(qapp):
    editor = make_editor("don")
    type_text(editor, "'t")
    assert editor.toPlainText() == "don't"


def test_backspace_removes_empty_pair(qapp):
    editor = make_editor()
    type_text(editor, "(")
    QTest.keyClick(editor, Qt.Key.Key_Backspace)
    assert editor.toPlainText() == ""


def test_pairing_can_be_disabled(qapp):
    editor = make_editor()
    editor.set_auto_close(False)
    type_text(editor, "(")
    assert editor.toPlainText() == "("


def test_read_only_editor_never_pairs(qapp):
    editor = make_editor()
    editor.setReadOnly(True)
    type_text(editor, "(")
    assert editor.toPlainText() == ""


# ---------------------------------------------------------------------
# indentation
# ---------------------------------------------------------------------
def test_enter_keeps_indentation(qapp):
    editor = make_editor("    first")
    QTest.keyClick(editor, Qt.Key.Key_Return)
    type_text(editor, "second")
    assert editor.toPlainText() == "    first\n    second"


def test_enter_after_opening_bracket_adds_a_level(qapp):
    editor = make_editor("def f():")
    QTest.keyClick(editor, Qt.Key.Key_Return)
    type_text(editor, "pass")
    assert editor.toPlainText() == "def f():\n    pass"


def test_enter_inside_parentheses_indents(qapp):
    editor = make_editor("    call(")
    QTest.keyClick(editor, Qt.Key.Key_Return)
    assert editor.toPlainText() == "    call(\n        "


def test_tab_indents_a_selection(qapp):
    editor = make_editor("one\ntwo")
    cursor = editor.textCursor()
    cursor.select(QTextCursor.SelectionType.Document)
    editor.setTextCursor(cursor)
    QTest.keyClick(editor, Qt.Key.Key_Tab)
    assert editor.toPlainText() == "    one\n    two"


def test_shift_tab_outdents_a_selection(qapp):
    editor = make_editor("    one\n    two")
    cursor = editor.textCursor()
    cursor.select(QTextCursor.SelectionType.Document)
    editor.setTextCursor(cursor)
    QTest.keyClick(editor, Qt.Key.Key_Backtab, Qt.KeyboardModifier.ShiftModifier)
    assert editor.toPlainText() == "one\ntwo"


def test_indent_unit_follows_the_file_style(qapp):
    editor = make_editor()
    editor.set_indent_unit("\t")
    QTest.keyClick(editor, Qt.Key.Key_Tab)
    assert editor.toPlainText() == "\t"


# ---------------------------------------------------------------------
# syntax highlighting
# ---------------------------------------------------------------------
def test_highlighting_is_off_by_default(qapp):
    editor = make_editor("def f():\n    pass")
    assert editor.syntax_highlighting_enabled() is False


def test_language_is_detected_from_the_file_name(qapp):
    editor = make_editor("x = 1", path="/tmp/script.py")
    assert editor.language_code() == "python"
    editor.set_language("rust")
    assert editor.language_code() == "rust"


def test_highlighting_paints_keywords_and_strings(qapp):
    editor = make_editor("def f():\n    return 'x'\n", path="/tmp/a.py")
    editor.set_syntax_highlighting(True)
    editor.resize(500, 300)
    editor.show()
    qapp.processEvents()
    block = editor.document().findBlockByNumber(0)
    colours = {fmt.format.foreground().color().name()
               for fmt in block.layout().formats()}
    assert colours, "no syntax formats were applied"
    block = editor.document().findBlockByNumber(1)
    string_colours = {fmt.format.foreground().color().name()
                      for fmt in block.layout().formats()}
    assert string_colours


def test_highlighting_can_be_turned_off_again(qapp):
    editor = make_editor("x = 1", path="/tmp/a.py")
    editor.set_syntax_highlighting(True)
    assert editor.syntax_highlighting_enabled() is True
    editor.set_syntax_highlighting(False)
    assert editor.syntax_highlighting_enabled() is False


def test_dark_theme_uses_different_colours(qapp):
    editor = make_editor("def f(): pass", path="/tmp/a.py")
    editor.resize(500, 200)
    editor.show()
    editor.set_syntax_highlighting(True, theme="light")
    qapp.processEvents()
    light = {f.format.foreground().color().name() for f in
             editor.document().firstBlock().layout().formats()}
    editor.set_syntax_highlighting(True, theme="dark")
    qapp.processEvents()
    dark = {f.format.foreground().color().name() for f in
            editor.document().firstBlock().layout().formats()}
    assert light and dark and light != dark


# ---------------------------------------------------------------------
# word completion
# ---------------------------------------------------------------------
def test_completion_popup_lists_document_words(qapp):
    editor = make_editor("document documents documented\n")
    editor.show()
    type_text(editor, "docu")
    editor.show_completions()
    popup = editor._completion
    assert popup is not None
    words = {popup.item(i).text() for i in range(popup.count())}
    assert "document" in words
    editor.close_completions()


def test_accepting_a_completion_inserts_the_rest(qapp):
    editor = make_editor("document\n")
    cursor = editor.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    cursor.insertText("docu")
    editor.setTextCursor(cursor)
    editor.show_completions()
    editor.accept_completion()
    assert editor.toPlainText() == "document\ndocument"


def test_completion_needs_two_characters(qapp):
    editor = make_editor("document")
    type_text(editor, "d")
    editor.show_completions()
    assert editor._completion is None
