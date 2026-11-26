#!/usr/bin/env python3
"""Measure how long Mishkah Note takes to show a window, and print it.

Run headless (``QT_QPA_PLATFORM=offscreen``) so it works on any machine:

    QT_QPA_PLATFORM=offscreen python3 tools/measure_startup.py
    QT_QPA_PLATFORM=offscreen python3 tools/measure_startup.py --budget 3000

Three numbers, because they fail for different reasons:

``import``   Qt and the package modules — the PySide6 import dominates and is the
             first thing a Qt upgrade moves.
``window``   building the window, its controller, its menus and the bundled fonts.
``total``    what a user waits for until a window is on screen.

``--budget`` turns the total into a gate (exit 1 above it).  The default is no
budget: startup time drifts with the machine and CI load, so the workflow prints
the numbers and only the regression *tests* assert hard limits.
"""

from __future__ import annotations

import argparse
import os
import sys
import time

T0 = time.perf_counter()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--budget", type=float, default=0.0,
                        help="fail when the total exceeds this many milliseconds")
    parser.add_argument("--json", action="store_true", help="one machine-readable line")
    args = parser.parse_args(argv)

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    from mishkah.app import build_window
    from mishkah.core.settings import Settings
    from mishkah.services.file_service import FileService

    imported = time.perf_counter()

    app = QApplication.instance() or QApplication([])
    # A throwaway settings file: the measurement must not read or write the
    # user's configuration, and restoring a session would measure something else.
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory(prefix="mishkah-startup-") as tmp:
        settings = Settings(path=Path(tmp) / "settings.json", restore_session=False)
        window = build_window(app, settings, FileService(), [],
                              restore=False, owns_session=False)
        window.show()
        app.processEvents()
        shown = time.perf_counter()
        window.close()
        app.processEvents()

    timings = {
        "import_ms": round((imported - T0) * 1000, 1),
        "window_ms": round((shown - imported) * 1000, 1),
        "total_ms": round((shown - T0) * 1000, 1),
    }
    if args.json:
        print(f"startup: {timings}")
    else:
        print(f"startup: import {timings['import_ms']} ms · "
              f"window {timings['window_ms']} ms · "
              f"total {timings['total_ms']} ms")

    if args.budget and timings["total_ms"] > args.budget:
        print(f"startup budget exceeded: {timings['total_ms']} ms > {args.budget} ms",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
