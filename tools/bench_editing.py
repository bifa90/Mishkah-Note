#!/usr/bin/env python3
"""Micro-benchmarks for the editing hot paths (CD-07).

Run it on the machine you care about::

    python tools/bench_editing.py            # table on stdout
    python tools/bench_editing.py --markdown # also time the Markdown layer

The numbers this script prints are the ones recorded in
``docs/DEVELOPMENT.md``.  Nothing here needs a display: the offscreen
platform plugin is used, so the same command works in CI and over SSH.
"""

from __future__ import annotations

import argparse
import os
import statistics
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from PySide6.QtWidgets import QApplication  # noqa: E402

from mishkah.models.document import DocumentModel  # noqa: E402
from mishkah.views.editor_view import EditorView  # noqa: E402

PASTE_BYTES = 100 * 1024
BIG_LINES = 20_000          # real paragraphs, one word each
HUGE_LINES = 200_000        # ~1.2 MB — the copy cost shows here
KEYSTROKES = 40


def _bulk(lines: int) -> str:
    """*lines* real paragraphs, so the widget lays out many blocks."""
    return "\n".join("word" for _ in range(lines))


def _editor() -> EditorView:
    editor = EditorView(DocumentModel())
    editor.resize(900, 700)
    editor.show()
    QApplication.processEvents()
    return editor


def _ms(seconds: float) -> float:
    return round(seconds * 1000.0, 2)


def bench_paste() -> dict:
    """One 100 KiB paste, the gate value of W3a."""
    text = ("line of sample text for the paste benchmark\n" * 3000)[:PASTE_BYTES]
    editor = _editor()
    cursor = editor.textCursor()
    started = time.perf_counter()
    cursor.insertText(text)
    elapsed = time.perf_counter() - started
    chars = editor.document().characterCount()
    editor.deleteLater()
    return {"paste_100k_ms": _ms(elapsed), "chars": chars}


def bench_neighbours(lines: int = HUGE_LINES) -> dict:
    """Reading the two characters around the caret, old way vs new way."""
    editor = _editor()
    editor.setPlainText(_bulk(lines))
    cursor = editor.textCursor()
    cursor.movePosition(cursor.MoveOperation.End)
    editor.setTextCursor(cursor)
    QApplication.processEvents()

    started = time.perf_counter()
    text = editor.toPlainText()
    _ = text[-1:], text[:1]
    old_ms = _ms(time.perf_counter() - started)

    samples = []
    for _ in range(20):
        started = time.perf_counter()
        _ = editor.neighbour_chars()
        samples.append(time.perf_counter() - started)
    blocks = editor.document().blockCount()
    editor.deleteLater()
    return {
        "neighbours_old_ms": old_ms,
        "neighbours_new_ms": _ms(statistics.mean(samples)),
        "lines": lines,
        "buffer_blocks": blocks,
    }


def bench_typing(lines: int = BIG_LINES) -> dict:
    """Cost of one keystroke in a large buffer (stats + pairing path)."""
    editor = _editor()
    editor.setPlainText(_bulk(lines))
    cursor = editor.textCursor()
    cursor.movePosition(cursor.MoveOperation.End)
    editor.setTextCursor(cursor)
    QApplication.processEvents()

    samples = []
    for index in range(KEYSTROKES):
        started = time.perf_counter()
        cursor = editor.textCursor()
        cursor.insertText("x" if index % 2 else "(")
        editor.setTextCursor(cursor)
        QApplication.processEvents()
        samples.append(time.perf_counter() - started)
    editor.deleteLater()
    samples.sort()
    return {
        "keystroke_mean_ms": _ms(statistics.mean(samples)),
        "keystroke_p95_ms": _ms(samples[int(len(samples) * 0.95) - 1]),
    }


def bench_stats_deferral(lines: int = BIG_LINES) -> dict:
    """How many stat passes a burst of typing triggers."""
    editor = _editor()
    editor.setPlainText(_bulk(lines))
    QApplication.processEvents()
    emitted = {"count": 0}

    def count(_lines: int, _chars: int) -> None:
        emitted["count"] += 1

    editor.stats_changed.connect(count)
    cursor = editor.textCursor()
    cursor.movePosition(cursor.MoveOperation.End)
    editor.setTextCursor(cursor)
    for _ in range(KEYSTROKES):
        editor.textCursor().insertText("y")

    deadline = time.perf_counter() + 2.0
    while time.perf_counter() < deadline and emitted["count"] == 0:
        QApplication.processEvents()
        time.sleep(0.01)
    final = emitted["count"]
    editor.deleteLater()
    return {"stats_passes_for_burst": final, "keystrokes": KEYSTROKES}


def bench_markdown(lines: int = 4_000) -> dict:
    """Enabling the Markdown layer, with the 400-line window in place."""
    editor = _editor()
    sample = "\n".join(f"## Heading {n}\n- item **bold** with `code`" for n in range(lines))
    editor.setPlainText(sample)
    QApplication.processEvents()
    started = time.perf_counter()
    editor.set_live_markdown(True)
    QApplication.processEvents()
    decorated = time.perf_counter() - started
    window = editor._markdown.window()          # noqa: SLF001 - benchmarking seam
    editor.deleteLater()
    return {
        "markdown_enable_ms": _ms(decorated),
        "markdown_window": f"{window[0]}..{window[1]}",
        "markdown_blocks": lines * 2,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--markdown", action="store_true",
                        help="also time the live Markdown layer")
    parsed = parser.parse_args()

    app = QApplication.instance() or QApplication([])
    results = {}
    results.update(bench_paste())
    results.update(bench_neighbours())
    results.update(bench_typing())
    results.update(bench_stats_deferral())
    if parsed.markdown:
        results.update(bench_markdown())

    width = max(len(key) for key in results)
    print(f"{'metric'.ljust(width)}  value")
    print("-" * (width + 12))
    for key, value in results.items():
        print(f"{key.ljust(width)}  {value}")
    del app
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
