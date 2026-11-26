"""Pytest fixtures: a Qt app that runs headless on any machine."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("XDG_CONFIG_HOME", "/tmp/mishkah-test-config")

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

qt_available = True
try:  # pragma: no cover - depends on the host having Qt system libs
    from PySide6.QtWidgets import QApplication  # noqa: F401
except Exception as exc:  # pragma: no cover
    qt_available = False
    _QT_IMPORT_ERROR = exc


requires_qt = pytest.mark.skipif(
    not qt_available,
    reason=f"PySide6/Qt system libraries unavailable: {globals().get('_QT_IMPORT_ERROR', '')}",
)

#: Modules that build real widgets.  They are marked ``gui`` and skipped
#: entirely when Qt cannot load (a bare checkout without libGL), so a failure
#: here always means a real regression rather than a missing system package.
QT_ONLY_MODULES = (
    "test_controller.py",
    "test_editing_features.py",
    "test_editor_direction.py",
    "test_invisible_chars.py",
    "test_markdown.py",
    "test_performance.py",
    "test_preview_and_search.py",
    "test_w3a_fixes.py",
    "test_language_detection.py",
    "test_ui_wave.py",
    "test_home_page.py",
    "test_settings_dialog.py",
    "test_new_window.py",
    "test_single_instance.py",
    "test_tabs.py",
    "test_widgets.py",
    "test_review_tools.py",
    "test_g3b_checklist.py",
    "test_g3b_findings.py",
    "test_w4_findings.py",
)
if not qt_available:
    collect_ignore = list(QT_ONLY_MODULES)


@pytest.fixture(scope="session")
def qapp():
    if not qt_available:  # pragma: no cover
        pytest.skip("Qt not importable on this host")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture()
def tmp_text(tmp_path: Path) -> Path:
    path = tmp_path / "sample.txt"
    path.write_text("first line\nsecond line\n", encoding="utf-8")
    return path


@pytest.fixture()
def tmp_arabic(tmp_path: Path) -> Path:
    path = tmp_path / "arabic.txt"
    path.write_text("مرحبا بالعالم\nسطر ثانٍ\n", encoding="utf-8")
    return path


_exit_status = {"status": 0}


def pytest_sessionfinish(session, exitstatus):  # noqa: ARG001
    """Remember the verdict; the exit itself happens in ``pytest_unconfigure``.

    PySide6 6.12 aborts inside CPython's final GC on some hosts (the traceback
    is ``Fatal Python error: bool_dealloc`` / ``none_dealloc``) *after* every
    test has run.  The crash is in the Qt binding's teardown, not in the
    application, so CI can opt into a clean, deterministic exit with
    ``MISHKAH_CLEAN_EXIT=1``.

    Leaving from ``pytest_sessionfinish`` itself was wrong: the terminal
    reporter prints the passed/failed summary in the same hook, so a red run
    went silent.  Unconfigure runs after the report and before interpreter
    finalisation, which is exactly the window between the two problems.
    """
    _exit_status["status"] = int(exitstatus)


def pytest_unconfigure(config):  # noqa: ARG001
    if os.environ.get("MISHKAH_CLEAN_EXIT") != "1":
        return
    # Deliberately dumb: flush and go.  Pumping the Qt event loop here was the
    # one part that could still segfault (SIGSEGV, exit 139, seen on Python 3.9
    # in CI) because the widgets the loop wakes up have already been closed and
    # are half-destroyed by then.  Nothing is waiting on those events.
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(_exit_status["status"])
