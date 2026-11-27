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

    # Parse results live in the decorator's own dict now, not in Qt-owned block
    # user data (that ownership mismatch was the crash).
    decorated = sum(1 for number in range(0, 6000)
                    if decorator.parsed_line(number) is not None)
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


# --------------------------------------------------------------------------
# S4: one measured gate, deliberately generous
# --------------------------------------------------------------------------
def test_pasting_100_kib_stays_under_100_ms(qapp):
    """Inserting 100 KiB must not become an accidental copy of the buffer.

    The recorded benchmark on a quiet machine is ~7.5 ms, so the ceiling carries
    more than ten times the headroom: this catches an O(n) regression, not a
    busy runner.  The number is printed so a slow drift is visible in the log
    before it becomes a failure.
    """
    import time

    editor = _editor(qapp, lines=5)
    payload = ("مفكرة مشكاة نصٌّ عربي مع أرقام ١٢٣ " * 4000)[: 100 * 1024]

    cursor = editor.textCursor()
    cursor.movePosition(cursor.MoveOperation.End)
    started = time.perf_counter()
    cursor.insertText(payload)
    elapsed = (time.perf_counter() - started) * 1000

    print(f"\n    100 KiB insert: {elapsed:.1f} ms")
    assert editor.document().characterCount() > len(payload)
    assert elapsed < 100, f"100 KiB insert took {elapsed:.1f} ms"


def test_large_file_chunked_load_reports_progress_and_supports_cancel(qapp):
    """Payloads above CHUNK_LOAD_THRESHOLD load in chunks with progress & cancel."""
    from mishkah.models.document import DocumentModel
    from mishkah.views.editor_view import EditorView

    payload = ("line of sample text for chunked loading\n" * 35_000)
    assert len(payload) > EditorView.CHUNK_LOAD_THRESHOLD

    editor = EditorView(DocumentModel())
    progress: list[tuple[int, int]] = []
    ok = editor.load_content(
        payload, progress_cb=lambda done, total: progress.append((done, total)) or True
    )
    assert ok is True
    assert len(progress) >= 2, "chunked load must report incremental progress"
    assert progress[-1] == (len(payload), len(payload))
    assert editor.toPlainText() == payload

    # Cancellation mid-load returns False and clears partial buffer.
    cancelled_editor = EditorView(DocumentModel())
    calls = 0

    def cancel_after_first(done: int, total: int) -> bool:
        nonlocal calls
        calls += 1
        return False

    assert cancelled_editor.load_content(payload, progress_cb=cancel_after_first) is False
    assert calls == 1
    assert cancelled_editor.toPlainText() == ""


def test_huge_file_enters_performance_mode_even_with_few_lines(qapp):
    """A >4 MB file with <2M lines must still disable wrap and undo history."""
    from PySide6.QtWidgets import QPlainTextEdit

    from mishkah.models.document import DocumentModel
    from mishkah.views.editor_view import EditorView

    payload = ("0123456789abcdef" * 32 + "\n") * 8_500  # ~4.36 MB, 8,500 lines
    assert len(payload) > EditorView.HUGE_CHAR_THRESHOLD
    doc = DocumentModel(content=payload)
    assert doc.uses_performance_mode is False

    editor = EditorView()
    assert editor.set_document(doc) is True
    assert editor.isUndoRedoEnabled() is False
    assert editor.lineWrapMode() == QPlainTextEdit.LineWrapMode.NoWrap
