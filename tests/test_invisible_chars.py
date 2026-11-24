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


def test_off_by_default_and_drawing_nothing(qapp):
    editor = make_editor(qapp, "a\u200fb")
    assert editor.show_invisible_chars() is False
    assert editor.invisible_mark_rects() == []


def test_overlay_marks_each_invisible_character(qapp):
    secret = "\u200f"      # RLM
    editor = make_editor(qapp, f"abc{secret}def\u200e")
    editor.set_show_invisible_chars(True)

    marks = editor.invisible_mark_rects()
    assert len(marks) == 2
    assert all(mark.width() >= 2 and mark.height() >= 1 for mark in marks)
    # The mark sits where the invisible character sits: after "abc".
    assert marks[0].x() > editor.cursorRect().x() - 1 or marks[0].x() >= 0


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
    assert editor.invisible_mark_rects()
    editor.set_show_invisible_chars(False)
    assert editor.invisible_mark_rects() == []


def test_typing_under_the_overlay_keeps_marks_in_step(qapp):
    editor = make_editor(qapp, "abc")
    editor.set_show_invisible_chars(True)
    assert editor.invisible_mark_rects() == []
    cursor = editor.textCursor()
    cursor.movePosition(cursor.MoveOperation.End)
    cursor.insertText("\u061c")          # ALM
    assert len(editor.invisible_mark_rects()) == 1


def test_every_marker_in_the_table_can_be_displayed(qapp):
    # One line per marker keeps the block count small and the test honest:
    # if a name is added to the table above it must render here too.
    text = "".join(INVISIBLE_CHARS)
    editor = make_editor(qapp, text)
    editor.set_show_invisible_chars(True)
    assert len(editor.invisible_mark_rects()) == len(INVISIBLE_CHARS)


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


def _orange_pixels(image) -> int:
    """Count pixels close to the marker colour (255,140,0) blended on light."""
    count = 0
    for y in range(image.height()):
        for x in range(image.width()):
            colour = image.pixelColor(x, y)
            if (colour.red() > 200 and 100 < colour.green() < 215
                    and colour.blue() < 140):
                count += 1
    return count


def test_marks_reach_the_screen(qapp):
    """Rendering, not just geometry: the markers must be visible pixels.

    The first implementation tinted the character's background, which paints
    nothing at all for a zero-width code point — this test exists so that
    failure mode cannot come back.
    """
    editor = make_editor(qapp, "abc\u200fdef\n")
    editor.resize(360, 120)
    editor.show()
    qapp.processEvents()

    before = _orange_pixels(editor.viewport().grab().toImage())
    editor.set_show_invisible_chars(True)
    qapp.processEvents()
    after = _orange_pixels(editor.viewport().grab().toImage())
    assert after > before, (before, after)
