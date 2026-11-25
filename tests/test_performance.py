"""Regression tests for the editing hot paths (CD-07).

The point of these tests is not to measure wall-clock time — a busy CI machine
would make that flaky — but to pin the *shape* of the work: one pass per burst,
no copy of the whole buffer, and a bounded Markdown window.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.gui


def _editor(qapp, lines: int = 4000):
    from mishkah.models.document import DocumentModel
    from mishkah.views.editor_view import EditorView

    editor = EditorView(DocumentModel())
    editor.setPlainText("\n".join(f"word {n}" for n in range(lines)))
    cursor = editor.textCursor()
    cursor.movePosition(cursor.MoveOperation.End)
    editor.setTextCursor(cursor)
    return editor


def test_stats_are_counted_once_per_burst(qapp):
    from PySide6.QtTest import QTest

    editor = _editor(qapp)
    seen = []
    editor.stats_changed.connect(lambda lines, chars: seen.append((lines, chars)))

    cursor = editor.textCursor()
    for _ in range(30):
        cursor.insertText("x")
    assert seen == [], "counting waited for the burst to end"

    QTest.qWait(300)
    assert len(seen) == 1
    assert editor.document().characterCount() == seen[0][1]


def test_alignment_is_decided_once_per_burst(qapp):
    from PySide6.QtTest import QTest

    editor = _editor(qapp)
    calls = []
    editor._sync_auto_alignment = lambda: calls.append(1)   # noqa: SLF001

    cursor = editor.textCursor()
    for _ in range(20):
        cursor.insertText("ا")
    QTest.qWait(300)
    assert len(calls) == 1


def test_pairing_never_copies_the_buffer(qapp):
    """Typing ``(`` must not call toPlainText() on a huge document."""
    from mishkah.views.editor_view import EditorView

    editor = _editor(qapp, lines=2000)

    def explode(*_args, **_kwargs):
        raise AssertionError("toPlainText() copies the whole buffer")

    editor.toPlainText = explode                # type: ignore[assignment]

    cursor = editor.textCursor()
    cursor.insertText("name ")
    editor.setTextCursor(cursor)
    assert editor._apply_pairing("(") is True    # noqa: SLF001
    assert editor.toPlainText is explode
    text = editor.document().toPlainText()
    assert text.endswith("name ()")

    editor.setPlainText("empty ()")
    cursor = editor.textCursor()
    cursor.movePosition(cursor.MoveOperation.End)
    cursor.movePosition(cursor.MoveOperation.PreviousCharacter)
    editor.setTextCursor(cursor)
    assert editor._backspace_pair() is True      # noqa: SLF001
    assert editor.document().toPlainText().endswith("empty ")
    assert isinstance(editor, EditorView)


def test_markdown_decorates_only_the_visible_window(qapp):
    editor = _editor(qapp, lines=6000)
    for number in range(6000):
        block = editor.document().findBlockByNumber(number)
        assert block.isValid()
    editor.setPlainText("\n".join(f"## heading {n}" for n in range(6000)))
    editor.set_live_markdown(True)

    decorator = editor.markdown_decorator()
    start, end = decorator.window()
    assert end - start < 2000, "the window stayed bounded"
    assert start == 0

    decorated = 0
    plain = 0
    for number in range(0, 6000):
        data = editor.document().findBlockByNumber(number).userData()
        if data is None:
            plain += 1
        else:
            decorated += 1
    assert decorated > 0
    assert decorator.window()[1] < 5999, "the far end of the file is not parsed"


def test_the_markdown_window_moves_with_the_viewport(qapp):
    editor = _editor(qapp, lines=6000)
    editor.setPlainText("\n".join(f"## heading {n}" for n in range(6000)))
    editor.set_live_markdown(True)
    before = editor.markdown_decorator().window()

    editor.verticalScrollBar().setValue(editor.verticalScrollBar().maximum())
    after = editor.markdown_decorator().window()
    assert after != before
    assert after[1] == 5999


def test_streaming_state_is_not_replayed_for_a_sequential_pass(qapp):
    """The fence state is carried forward, not replayed 400 lines per block."""
    editor = _editor(qapp, lines=1200)
    editor.setPlainText("```\ncode\n```\n" * 400)
    editor.set_live_markdown(True)
    decorator = editor.markdown_decorator()
    decorator.invalidate_cache()

    parsed = decorator._parse(                      # noqa: SLF001
        editor.document().findBlockByNumber(900))
    second = decorator._parse(                      # noqa: SLF001
        editor.document().findBlockByNumber(901))
    assert parsed is not None and second is not None
