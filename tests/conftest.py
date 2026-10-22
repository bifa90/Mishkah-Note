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


def pytest_sessionfinish(session, exitstatus):  # noqa: ARG001
    """Leave without running interpreter finalisation when asked to.

    PySide6 6.12 aborts inside CPython's final GC on some hosts (the traceback
    is ``Fatal Python error: bool_dealloc``) *after* every test has run.  The
    crash is in the Qt binding's teardown, not in the application, so CI can
    opt into a clean, deterministic exit with ``MISHKAH_CLEAN_EXIT=1``.
    """
    if os.environ.get("MISHKAH_CLEAN_EXIT") != "1":
        return
    try:
        from PySide6.QtCore import QCoreApplication

        app = QCoreApplication.instance()
        if app is not None:
            app.processEvents()
    except Exception:  # pragma: no cover - Qt optional at this point
        pass
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(int(exitstatus))
