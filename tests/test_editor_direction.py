"""GUI tests: the text-direction fix, verified inside real Qt widgets."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

pytestmark = [pytest.mark.gui, pytest.mark.usefixtures("qapp")]

Qt = pytest.importorskip("PySide6.QtCore").Qt


@pytest.fixture(autouse=True)
def _dispose_widgets(qapp):
    """Destroy every widget while Qt is still alive.

    Leaving editors to the interpreter's final GC collects them after the Qt
    libraries are gone, which PySide6 reports as a refcount abort.  Closing
    them and flushing deferred deletes keeps teardown deterministic.
    """
    yield
    from PySide6.QtCore import QEvent

    for widget in list(qapp.topLevelWidgets()):
        widget.close()
        widget.deleteLater()
    qapp.sendPostedEvents(None, QEvent.Type.DeferredDelete)

from mishkah.core.text_direction import AUTO, FIRST_LINE, FIRST_STRONG, LTR, RTL  # noqa: E402
from mishkah.models.document import DocumentModel  # noqa: E402
from mishkah.views.editor_view import (  # noqa: E402
    EditorView,
    _ChordState,
)


def make_editor(qapp, text: str = "", mode: str = AUTO) -> EditorView:
    doc = DocumentModel(content=text, direction_mode=mode)
    editor = EditorView(doc)
    editor.load_content(text)
    editor.apply_direction(mode, announce=False)
    return editor


def block_direction(editor: EditorView, index: int = 0):
    block = editor.document().findBlockByNumber(index)
    return block.blockFormat().layoutDirection()


# ---------------------------------------------------------------------
# the regression: direction must reach the *block format*, not just the widget
# ---------------------------------------------------------------------
def test_default_document_is_auto_not_forced_rtl(qapp):
    editor = make_editor(qapp, "hello")
    assert editor.direction_mode == AUTO
    assert block_direction(editor) == Qt.LayoutDirection.LayoutDirectionAuto


def test_rtl_mode_writes_block_format(qapp):
    editor = make_editor(qapp, "hello world")
    editor.apply_direction(RTL)
    assert block_direction(editor) == Qt.LayoutDirection.RightToLeft
    # …and the widget chrome follows, so the gutter sits on the right
    assert editor.layoutDirection() == Qt.LayoutDirection.RightToLeft


def test_ltr_mode_writes_block_format(qapp):
    editor = make_editor(qapp, "مرحبا بالعالم", mode=RTL)
    editor.apply_direction(LTR)
    assert block_direction(editor) == Qt.LayoutDirection.LeftToRight
    assert editor.layoutDirection() == Qt.LayoutDirection.LeftToRight


def test_direction_applies_to_every_existing_paragraph(qapp):
    editor = make_editor(qapp, "one\ntwo\nthree\nfour")
    editor.apply_direction(RTL)
    for index in range(editor.blockCount()):
        assert block_direction(editor, index) == Qt.LayoutDirection.RightToLeft


def test_mixed_document_keeps_one_mode(qapp):
    editor = make_editor(qapp, "English line\nسطر عربي\nthird")
    editor.apply_direction(RTL)
    for index in range(editor.blockCount()):
        assert block_direction(editor, index) == Qt.LayoutDirection.RightToLeft


def test_new_paragraph_inherits_explicit_direction(qapp):
    editor = make_editor(qapp, "first", mode=RTL)
    editor.apply_direction(RTL)
    cursor = editor.textCursor()
    cursor.movePosition(cursor.MoveOperation.End)
    editor.setTextCursor(cursor)
    editor.keyPressEvent(_key_event(Qt.Key.Key_Return, qapp))
    editor.insertPlainText("second")
    assert block_direction(editor, 1) == Qt.LayoutDirection.RightToLeft


def test_auto_mode_resolves_per_paragraph(qapp):
    editor = make_editor(qapp, "مرحبا بالعالم", mode=AUTO)
    assert editor.resolved_direction() == RTL
    editor.setPlainText("hello world")
    cursor = editor.textCursor()
    cursor.movePosition(cursor.MoveOperation.Start)
    editor.setTextCursor(cursor)
    assert editor.resolved_direction() == LTR


def test_direction_changed_signal(qapp):
    editor = make_editor(qapp, "text")
    seen = []
    editor.direction_changed.connect(seen.append)
    editor.apply_direction(RTL)
    editor.apply_direction(LTR)
    assert seen == [RTL, LTR]


def test_set_document_restores_mode(qapp):
    editor = make_editor(qapp, "x")
    doc = DocumentModel(content="مرحبا", direction_mode=RTL)
    editor.set_document(doc)
    assert editor.direction_mode == RTL
    assert block_direction(editor) == Qt.LayoutDirection.RightToLeft


# ---------------------------------------------------------------------
# the Ctrl+Shift chord
# ---------------------------------------------------------------------
def _chord_press(state: _ChordState, code: int, key):
    state.on_press_codes(code, key)


def _chord_release(state: _ChordState, code: int, key):
    return state.on_release_codes(code, key)


CTRL = Qt.Key.Key_Control
SHIFT = Qt.Key.Key_Shift


class _any_key_event:
    """Stand-in for a non-modifier QKeyEvent (only scan code + key are read)."""

    def __init__(self, key):
        self._key = key

    def nativeScanCode(self):  # noqa: N802 (Qt naming)
        return 0

    def key(self):
        return self._key


def _key_event(key, qapp):
    from PySide6.QtGui import QKeyEvent

    return QKeyEvent(QKeyEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier)


def test_ctrl_shift_right_means_rtl():
    """X11/evdev codes: RCtrl=105, RShift=62."""
    state = _ChordState()
    _chord_press(state, 105, CTRL)
    _chord_press(state, 62, SHIFT)
    assert _chord_release(state, 62, SHIFT) is None      # still holding Ctrl
    assert _chord_release(state, 105, CTRL) == RTL


def test_ctrl_shift_left_means_ltr():
    """X11/evdev codes: LCtrl=37, LShift=50."""
    state = _ChordState()
    _chord_press(state, 37, CTRL)
    _chord_press(state, 50, SHIFT)
    assert _chord_release(state, 50, SHIFT) is None
    assert _chord_release(state, 37, CTRL) == LTR


def test_windows_scan_codes_also_work():
    """Windows: LCtrl=29, RCtrl=97, LShift=42, RShift=54."""
    state = _ChordState()
    _chord_press(state, 97, CTRL)
    _chord_press(state, 54, SHIFT)
    _chord_release(state, 54, SHIFT)
    assert _chord_release(state, 97, CTRL) == RTL

    state = _ChordState()
    _chord_press(state, 29, CTRL)
    _chord_press(state, 42, SHIFT)
    _chord_release(state, 42, SHIFT)
    assert _chord_release(state, 29, CTRL) == LTR


def test_macos_scan_codes_also_work():
    """macOS: LCtrl=59, RCtrl=62, LShift=56, RShift=60.

    62 is Right *Control* here but Right *Shift* on X11 — the key type
    disambiguates it, which is exactly what the fix relies on.
    """
    state = _ChordState()
    _chord_press(state, 62, CTRL)
    _chord_press(state, 60, SHIFT)
    _chord_release(state, 60, SHIFT)
    assert _chord_release(state, 62, CTRL) == RTL


def test_scan_code_62_is_shift_on_x11_but_ctrl_on_macos():
    assert _ChordState._side_of(62, SHIFT) == "shift_right"
    assert _ChordState._side_of(62, CTRL) == "ctrl_right"


def test_chord_with_another_key_does_nothing():
    state = _ChordState()
    _chord_press(state, 105, CTRL)
    _chord_press(state, 62, SHIFT)
    state.on_press_codes(0, Qt.Key.Key_N)                # Ctrl+Shift+N
    assert _chord_release(state, 62, SHIFT) is None
    assert _chord_release(state, 105, CTRL) is None


def test_plain_typing_does_not_change_direction():
    state = _ChordState()
    for key in (Qt.Key.Key_H, Qt.Key.Key_E, Qt.Key.Key_L):
        state.on_press_codes(0, key)
        assert state.on_release_codes(0, key) is None


def test_shift_alone_does_nothing():
    state = _ChordState()
    _chord_press(state, 50, SHIFT)
    assert _chord_release(state, 50, SHIFT) is None


def test_ctrl_alone_does_nothing():
    state = _ChordState()
    _chord_press(state, 37, CTRL)
    assert _chord_release(state, 37, CTRL) is None


def test_mixed_sides_do_not_fire():
    """Left Ctrl + Right Shift is not a direction chord."""
    state = _ChordState()
    _chord_press(state, 37, CTRL)
    _chord_press(state, 62, SHIFT)
    assert _chord_release(state, 62, SHIFT) is None
    assert _chord_release(state, 37, CTRL) is None


def test_chord_fires_only_once_per_tap():
    state = _ChordState()
    _chord_press(state, 105, CTRL)
    _chord_press(state, 62, SHIFT)
    results = [_chord_release(state, 62, SHIFT), _chord_release(state, 105, CTRL)]
    assert results.count(RTL) == 1


def test_repeated_taps_fire_each_time():
    state = _ChordState()
    fired = []
    for _ in range(3):
        _chord_press(state, 105, CTRL)
        _chord_press(state, 62, SHIFT)
        _chord_release(state, 62, SHIFT)
        result = _chord_release(state, 105, CTRL)
        if result:
            fired.append(result)
    assert fired == [RTL, RTL, RTL]


def test_unknown_scan_code_does_not_crash():
    state = _ChordState()
    state.on_press_codes(0, Qt.Key.Key_Control)
    assert state.on_release_codes(0, Qt.Key.Key_Control) is None


def test_editor_applies_chord_and_reports_it(qapp):
    """End-to-end through the editor seam: chord → mode → block format."""
    editor = make_editor(qapp, "hello world")
    seen = []
    editor.direction_changed.connect(seen.append)

    editor.handle_chord_press(105, CTRL)
    editor.handle_chord_press(62, SHIFT)
    editor.handle_chord_release(62, SHIFT)
    editor.handle_chord_release(105, CTRL)

    assert editor.direction_mode == RTL
    assert seen == [RTL]
    assert block_direction(editor) == Qt.LayoutDirection.RightToLeft

    editor.handle_chord_press(37, CTRL)
    editor.handle_chord_press(50, SHIFT)
    editor.handle_chord_release(50, SHIFT)
    editor.handle_chord_release(37, CTRL)
    assert editor.direction_mode == LTR
    assert block_direction(editor) == Qt.LayoutDirection.LeftToRight


# ---------------------------------------------------------------------
# zoom / options
# ---------------------------------------------------------------------
def test_zoom_reports_percentage(qapp):
    editor = make_editor(qapp, "text")
    editor._base_font_size = 10
    editor.set_font_size(10)
    assert editor.zoom_percent() == 100
    editor.zoom_in()
    assert editor.zoom_percent() == 110
    editor.zoom_reset()
    assert editor.zoom_percent() == 100


def test_zoom_is_clamped(qapp):
    editor = make_editor(qapp, "text")
    editor.set_font_size(1000)
    assert editor.font().pointSize() <= 72
    editor.set_font_size(-5)
    assert editor.font().pointSize() >= 6


def test_goto_line(qapp):
    editor = make_editor(qapp, "one\ntwo\nthree\nfour\nfive")
    editor.goto_line(3)
    assert editor.textCursor().blockNumber() == 2
    editor.goto_line(999)                     # clamped, must not crash
    assert editor.textCursor().blockNumber() == editor.blockCount() - 1


def test_line_numbers_toggle_changes_margins(qapp):
    editor = make_editor(qapp, "a\nb")
    editor.resize(400, 200)
    editor.set_line_numbers_visible(False)
    assert editor.gutter_width() == 0
    editor.set_line_numbers_visible(True)
    assert editor.gutter_width() > 0


def test_find_and_wrap_around(qapp):
    editor = make_editor(qapp, "alpha beta gamma")
    assert editor.find_text("beta") is True
    assert editor.textCursor().selectedText() == "beta"
    assert editor.find_text("alpha", wrap=True) is True
    assert editor.find_text("zzz", wrap=True) is False


def test_word_wrap_toggle(qapp):
    from PySide6.QtWidgets import QPlainTextEdit

    editor = make_editor(qapp, "text")
    editor.set_word_wrap(False)
    assert editor.lineWrapMode() == QPlainTextEdit.LineWrapMode.NoWrap
    editor.set_word_wrap(True)
    assert editor.lineWrapMode() == QPlainTextEdit.LineWrapMode.WidgetWidth


def test_status_direction_on_a_blank_line_follows_the_document(qapp):
    """An empty last line must not report LTR for an Arabic file."""
    editor = make_editor(qapp, "خطة الأسبوع\n- مراجعة\n\n", mode=AUTO)
    cursor = editor.textCursor()
    cursor.movePosition(cursor.MoveOperation.End)   # the blank trailing block
    editor.setTextCursor(cursor)
    assert editor.resolved_direction() == RTL

    editor.setPlainText("notes\n\n")
    cursor = editor.textCursor()
    cursor.movePosition(cursor.MoveOperation.End)
    editor.setTextCursor(cursor)
    assert editor.resolved_direction() == LTR


# ---------------------------------------------------------------------
# CD-11 / CD-16: the document's side is decided once and never moves with
# the caret; the status chip still reports the caret's paragraph.
# ---------------------------------------------------------------------
def _move_to_block(editor, index):
    cursor = editor.textCursor()
    cursor.movePosition(cursor.MoveOperation.Start)
    for _ in range(index):
        cursor.movePosition(cursor.MoveOperation.Down)
    editor.setTextCursor(cursor)


def _alignment(editor):
    return editor.document().defaultTextOption().alignment()


def test_mixed_document_keeps_one_side_while_the_caret_moves(qapp):
    """Following the caret flipped the whole view; a fixed side does not."""
    editor = make_editor(qapp, "مرحبا بالعالم\n123 hello", mode=AUTO)
    _move_to_block(editor, 0)
    assert _alignment(editor) & Qt.AlignmentFlag.AlignRight
    _move_to_block(editor, 1)
    assert _alignment(editor) & Qt.AlignmentFlag.AlignRight, "the side must not move"


def test_document_side_comes_from_the_first_line(qapp):
    """An English file that turns Arabic half-way is still an English file."""
    editor = make_editor(qapp, "hello\nمرحبا بالعالم\nمرحبا بالعالم", mode=AUTO)
    assert editor.document_side() == LTR
    assert _alignment(editor) & Qt.AlignmentFlag.AlignLeft


def test_new_empty_document_takes_the_side_of_the_first_word(qapp):
    editor = make_editor(qapp, "", mode=AUTO)
    assert editor.document_side() == LTR
    editor.setPlainText("مرحبا")
    editor._sync_auto_alignment()
    assert editor.document_side() == RTL
    assert _alignment(editor) & Qt.AlignmentFlag.AlignRight
    editor.setPlainText("مرحبا\nhello world")     # a minority line changes nothing
    editor._sync_auto_alignment()
    assert editor.document_side() == RTL


def test_auto_mode_keeps_the_widget_ltr_but_moves_the_gutter(qapp):
    """The document's side decides where the numbers go; the widget stays LTR.

    A left-to-right widget keeps Qt's per-paragraph resolution intact, so the
    gutter has to follow the document's side by itself instead of following
    the widget's direction.
    """
    editor = make_editor(qapp, "مرحبا بالعالم\n123 hello", mode=AUTO)
    editor.set_line_numbers_visible(True)
    assert editor.layoutDirection() == Qt.LayoutDirection.LeftToRight
    margins = editor.viewportMargins()
    assert margins.right() > margins.left(), "RTL document: numbers on the right"
    _move_to_block(editor, 1)
    assert editor.viewportMargins() == margins          # and they never jump


def test_gutter_follows_the_document_side_in_auto_mode(qapp):
    editor = make_editor(qapp, "hello world\nمرحبا", mode=AUTO)   # opens English
    editor.set_line_numbers_visible(True)
    margins = editor.viewportMargins()
    assert margins.left() > margins.right(), "LTR document: numbers on the left"


def test_explicit_rtl_moves_the_gutter_to_the_right(qapp):
    editor = make_editor(qapp, "hello", mode=RTL)
    editor.apply_direction(RTL, announce=False)
    editor.set_line_numbers_visible(True)
    margins = editor.viewportMargins()
    assert editor.layoutDirection() == Qt.LayoutDirection.RightToLeft
    assert margins.right() > margins.left()


def test_both_edges_keep_breathing_room(qapp):
    editor = make_editor(qapp, "مرحبا", mode=AUTO)
    editor.set_line_numbers_visible(False)
    margins = editor.viewportMargins()
    assert margins.left() >= 4 and margins.right() >= 4


def test_status_chip_follows_the_caret_across_directions(qapp):
    editor = make_editor(qapp, "مرحبا\n123 hello", mode=AUTO)
    seen = []
    editor.resolved_direction_changed.connect(seen.append)
    _move_to_block(editor, 0)
    _move_to_block(editor, 1)
    assert LTR in seen


def test_blank_paragraph_inherits_the_paragraph_above(qapp):
    """Pressing Enter at the end of an English line keeps writing English."""
    editor = make_editor(qapp, "hello\n", mode=AUTO)
    _move_to_block(editor, 1)
    assert editor.resolved_direction() == LTR
    editor.setPlainText("مرحبا\n")
    _move_to_block(editor, 1)
    assert editor.resolved_direction() == RTL


# ---------------------------------------------------------------------
# CD-11: a caret sitting at the start of a right-aligned line must stay
# inside the viewport (it used to be clipped away on the right edge)
# ---------------------------------------------------------------------
def test_caret_at_the_start_of_an_rtl_line_stays_visible(qapp):
    editor = make_editor(qapp, "مرحبا بالعالم\n", mode=AUTO)
    editor.resize(600, 160)
    editor.show()
    qapp.processEvents()
    cursor = editor.textCursor()
    cursor.movePosition(cursor.MoveOperation.Start)
    editor.setTextCursor(cursor)
    qapp.processEvents()

    rect = editor.cursorRect()
    width = editor.viewport().width()
    assert 0 <= rect.left() < width
    assert rect.right() <= width - 4, (rect, width)
    assert width - rect.right() >= 4, "no room on the right: the caret is clipped"



def test_first_line_mode_re_decides_while_the_first_line_is_being_written(qapp):
    """CD-20: the first line picks the side, until a second line exists."""
    editor = make_editor(qapp, "", mode=AUTO)
    editor.set_document_side_source(FIRST_LINE)
    editor.insertPlainText("hello")
    assert editor.document_side() == LTR
    editor.selectAll()
    editor.insertPlainText("مرحبا")
    assert editor.document_side() == RTL
    assert _alignment(editor) & Qt.AlignmentFlag.AlignRight


def test_first_line_mode_commits_once_the_document_has_two_lines(qapp):
    editor = make_editor(qapp, "", mode=AUTO)
    editor.set_document_side_source(FIRST_LINE)
    editor.insertPlainText("مرحبا\nhello world")
    assert editor.document_side() == RTL        # second line changes nothing
    assert _alignment(editor) & Qt.AlignmentFlag.AlignRight


def test_the_previous_rule_commits_on_the_first_character(qapp):
    """Default (first_strong): the first character decides for good."""
    editor = make_editor(qapp, "", mode=AUTO)
    assert editor.document_side_source() == FIRST_STRONG
    editor.insertPlainText("hello")
    editor.selectAll()
    editor.insertPlainText("مرحبا")
    assert editor.document_side() == LTR


def test_replacing_everything_follows_the_rule_in_force(qapp):
    """Committed text keeps its side; a first line still being written does not."""
    committed = make_editor(qapp, "", mode=AUTO)          # first_strong default
    committed.insertPlainText("hello world")
    committed.selectAll()
    committed.insertPlainText("مرحبا بالعالم")
    assert committed.document_side() == LTR

    live = make_editor(qapp, "", mode=AUTO)
    live.set_document_side_source(FIRST_LINE)
    live.insertPlainText("hello world")
    live.selectAll()
    live.insertPlainText("مرحبا بالعالم")
    assert live.document_side() == RTL, "the first line is still being written"


def test_emptying_the_buffer_makes_it_a_new_document(qapp):
    for source in (FIRST_STRONG, FIRST_LINE):
        editor = make_editor(qapp, "", mode=AUTO)
        editor.set_document_side_source(source)
        editor.insertPlainText("hello world")
        assert editor.document_side() == LTR
        editor.clear()
        editor.insertPlainText("مرحبا")
        assert editor.document_side() == RTL, "an empty buffer is a new document"


def test_the_view_menu_switches_the_rule(qapp, tmp_path):
    from mishkah.controllers.main_controller import MainController
    from mishkah.core.settings import Settings
    from mishkah.services.file_service import FileService
    from mishkah.views.main_window import MainWindow

    settings = Settings(path=tmp_path / "settings.json", restore_session=False)
    window = MainWindow()
    controller = MainController(window, settings, FileService())
    try:
        editor = controller.new_document()
        editor.insertPlainText("hello")
        window.act_document_side.setChecked(True)
        assert settings.document_side_source == FIRST_LINE
        assert editor.document_side_source() == FIRST_LINE
        window.act_document_side.setChecked(False)
        assert settings.document_side_source == FIRST_STRONG
    finally:
        window.close()
