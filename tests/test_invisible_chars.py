"""The "show invisible characters" overlay (CD-16) and the settings behind it.

The overlay must be a *view*: it may mark LRM/RLM/ALM/ZWNJ, but it must never
touch the document bytes, the undo history or the saved file.
"""

from __future__ import annotations

import pytest

from mishkah.core.settings import Settings
from mishkah.core.text_direction import INVISIBLE_CHARS

pytestmark = [pytest.mark.gui, pytest.mark.usefixtures("qapp")]


def make_editor(qapp, text: str = ""):
    from mishkah.models.document import DocumentModel
    from mishkah.views.editor_view import EditorView

    editor = EditorView(document=DocumentModel())
    if text:
        editor.setPlainText(text)
    return editor


def test_off_by_default_and_moving_no_selection(qapp):
    editor = make_editor(qapp, "a\u200fb")
    assert editor.show_invisible_chars() is False
    assert editor.extraSelections() == []


def test_overlay_marks_each_invisible_character(qapp):
    secret = "\u200f"      # RLM
    editor = make_editor(qapp, f"abc{secret}def\u200e")
    editor.set_show_invisible_chars(True)

    selections = editor.extraSelections()
    assert len(selections) == 2
    assert [sel.cursor.selectedText() for sel in selections] == [secret, "\u200e"]
    assert selections[0].cursor.selectionStart() == 3


def test_overlay_does_not_change_the_document(qapp):
    text = "سطر\u200fعربي\nenglish\u200e line\n"
    editor = make_editor(qapp, text)
    before = editor.toPlainText()
    editor.set_show_invisible_chars(True)
    assert editor.toPlainText() == before
    assert editor.document().isUndoAvailable() is False   # not an edit
    editor.set_show_invisible_chars(False)
    assert editor.toPlainText() == before


def test_turning_the_overlay_off_clears_every_mark(qapp):
    editor = make_editor(qapp, "\u200f\u200e\u200c")
    editor.set_show_invisible_chars(True)
    assert editor.extraSelections()
    editor.set_show_invisible_chars(False)
    assert editor.extraSelections() == []


def test_typing_under_the_overlay_keeps_marks_in_step(qapp):
    editor = make_editor(qapp, "abc")
    editor.set_show_invisible_chars(True)
    assert editor.extraSelections() == []
    cursor = editor.textCursor()
    cursor.movePosition(cursor.MoveOperation.End)
    cursor.insertText("\u061c")          # ALM
    assert len(editor.extraSelections()) == 1


def test_every_marker_in_the_table_can_be_displayed(qapp):
    # One line per marker keeps the block count small and the test honest:
    # if a name is added to the table above it must render here too.
    text = "".join(INVISIBLE_CHARS)
    editor = make_editor(qapp, text)
    editor.set_show_invisible_chars(True)
    assert len(editor.extraSelections()) == len(INVISIBLE_CHARS)


def test_setting_defaults_to_off_and_round_trips(qapp):
    assert Settings().show_invisible_chars is False
    assert Settings(show_invisible_chars=True).show_invisible_chars is True


def test_controller_wires_the_view_menu_to_every_editor(qapp, tmp_path):
    from mishkah.controllers.main_controller import MainController
    from mishkah.services.file_service import FileService
    from mishkah.views.main_window import MainWindow

    settings = Settings(path=tmp_path / "settings.json", restore_session=False)
    window = MainWindow()
    controller = MainController(window, settings, FileService())
    try:
        editor = controller.new_document()
        window.act_show_invisible.trigger()          # what the user clicks
        assert editor.show_invisible_chars() is True
        assert settings.show_invisible_chars is True
        window.act_show_invisible.trigger()
        assert editor.show_invisible_chars() is False
    finally:
        window.close()
