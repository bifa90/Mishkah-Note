#!/usr/bin/env python3
"""Eight lines of PySide6, no Mishkah code — and it aborts.

    python tools/repro_highlighter_crash.py            # aborts after ~4 rounds
    python tools/repro_highlighter_crash.py --rounds 2 # survives: it needs a few

Found while measuring G3b item 15 ("live Markdown feels heavy").  The crash is
not about Markdown: any Python ``QSyntaxHighlighter`` that calls ``setFormat``
on documents that are built and thrown away in the same process eventually dies
with ``Fatal Python error: none_dealloc`` (or ``bool_dealloc`` at shutdown).
No Python-side arrangement avoids it — not detaching the highlighter first, not
``shiboken6.delete``, not keeping every object alive, not a single highlighter
shared across documents.

That makes it an upstream fault in PySide6 6.12 / shiboken6, not in this
application.  What the application *can* do, it does:

* it no longer hands Qt a Python-owned ``QTextBlockUserData`` (that ownership
  mismatch belongs to the same family of refcount errors);
* the test session exits without interpreter finalisation when
  ``MISHKAH_CLEAN_EXIT=1``, which is how CI runs (``tests/conftest.py``).
"""

from __future__ import annotations

import argparse
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rounds", type=int, default=12)
    args = parser.parse_args(argv)

    from PySide6.QtGui import QSyntaxHighlighter, QTextCharFormat
    from PySide6.QtWidgets import QApplication, QPlainTextEdit

    app = QApplication([])

    class Highlighter(QSyntaxHighlighter):
        def highlightBlock(self, text):  # noqa: N802 - Qt naming
            fmt = QTextCharFormat()
            fmt.setFontPointSize(0.5)
            self.setFormat(0, len(text), fmt)

    for round_number in range(1, args.rounds + 1):
        editor = QPlainTextEdit()
        editor.setPlainText("نص عربي\n\n- عنصر **عريض**\n" * 200)
        highlighter = Highlighter(editor.document())
        highlighter.rehighlight()
        app.processEvents()
        editor.deleteLater()
        app.processEvents()
        del highlighter, editor
        print(f"round {round_number} survived", flush=True)

    print("no crash: this host's PySide6 is not affected", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
