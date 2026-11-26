#!/usr/bin/env python3
"""Smoke-test one *installed* copy of Mishkah Note.

Run it from ``scripts/smoke-test.sh``, which unpacks a package and points
``PYTHONPATH`` at the copy inside it.  The point is to catch the failures a
build can hide — a missing ``_version.txt``, a font that did not travel, a Qt
plugin that is not where ``LD_LIBRARY_PATH`` says, a wheel that imports but
cannot save a file — by exercising the real, packaged code headlessly.

    python3 scripts/smoke_check.py --expect 1.0.02 --label "deb payload"

Exit status: 0 all good · 1 a check failed · 77 Qt is unavailable (skipped).
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

ARABIC = "مفكرة مشكاة — الاختبار السريع\n"
SAMPLES = ARABIC + "\n".join(
    f"{index}: صفٌّ عربيّ مع أرقام ١٢٣ ولاتينيّة abc"
    for index in range(1, 201)
) + "\n"


class Report:
    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0

    def check(self, problem: str, condition: bool, detail: str = "") -> None:
        mark = "\033[32m✔\033[0m" if condition else "\033[31m✘\033[0m"
        print(f"    {mark} {problem}" + (f" — {detail}" if detail and not condition else ""))
        if condition:
            self.passed += 1
        else:
            self.failed += 1


def round_trip(report: Report, workdir: Path) -> None:
    """Write Arabic text atomically, read it back, and compare byte for byte."""
    from mishkah.core.large_file import load_file, write_text_atomic

    target = workdir / "اختبار.txt"
    write_text_atomic(target, SAMPLES, _utf8())
    report.check("writes a new file atomically", target.exists())
    loaded = load_file(target)
    report.check("reads back what it wrote", loaded.text == SAMPLES,
                 f"{len(loaded.text)} of {len(SAMPLES)} characters")
    report.check("counts the lines", loaded.line_count == SAMPLES.count("\n"),
                 str(loaded.line_count))
    # A second write over an existing file exercises the replace path.
    write_text_atomic(target, SAMPLES.replace("١٢٣", "٤٥٦"), _utf8())
    again = load_file(target)
    report.check("overwrites an existing file", "٤٥٦" in again.text)
    # The document the editor builds on top of it must open the same text.
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        return
    if QApplication.instance() is None:
        return
    from mishkah.models.document import DocumentModel

    model = DocumentModel(content=SAMPLES)
    report.check("DocumentModel holds the text", model.content == SAMPLES,
                 str(len(model.content)))


def _utf8():
    from mishkah.core.encoding import TextFormat

    return TextFormat()


def graphical(report: Report) -> int:
    """Import Qt, register the bundled fonts, and build a window offscreen."""
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError as exc:  # pragma: no cover - reported as a skip
        print(f"    – Qt is not importable from this copy ({exc}); GUI checks skipped")
        return 77

    from mishkah import APP_VERSION
    from mishkah.app import install_bundled_fonts

    app = QApplication.instance() or QApplication([])
    families = install_bundled_fonts()
    report.check("bundled fonts load", bool(families), ", ".join(families))
    report.check("application version is importable", bool(APP_VERSION), APP_VERSION)

    from mishkah.views.main_window import MainWindow

    window = MainWindow()
    try:
        report.check("a window can be constructed", window.tab_count() == 0)
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expect", required=True, help="expected version string")
    parser.add_argument("--label", default="payload")
    parser.add_argument("--no-gui", action="store_true",
                        help="skip the Qt checks (for copies without PySide6)")
    args = parser.parse_args(argv)

    print(f"  {args.label}: {sys.executable}")
    report = Report()

    from mishkah import APP_VERSION

    report.check("version is the released one", APP_VERSION == args.expect,
                 f"{APP_VERSION} != {args.expect}")

    with tempfile.TemporaryDirectory(prefix="mishkah-smoke-") as tmp:
        round_trip(report, Path(tmp))

    status = 0
    if not args.no_gui:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        status = graphical(report)

    print(f"    {report.passed} passed, {report.failed} failed")
    if report.failed:
        return 1
    return 77 if status == 77 else 0


if __name__ == "__main__":
    raise SystemExit(main())
