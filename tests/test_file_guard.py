"""GUI tests for CD-18: the outside edit must survive a save."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

pytestmark = [pytest.mark.gui, pytest.mark.usefixtures("qapp")]

PySide6 = pytest.importorskip("PySide6")

from mishkah.core.disk_state import stat_signature  # noqa: E402


@pytest.fixture(autouse=True)
def _dispose_widgets(qapp):
    yield
    from PySide6.QtCore import QEvent

    for widget in list(qapp.topLevelWidgets()):
        widget.close()
        widget.deleteLater()
    qapp.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def _controller(tmp_path):
    from mishkah.controllers.main_controller import MainController
    from mishkah.core.settings import Settings
    from mishkah.services.file_service import FileService
    from mishkah.views.main_window import MainWindow

    window = MainWindow()
    settings = Settings(path=tmp_path / "settings.json", restore_session=False)
    return window, MainController(window, settings, FileService())


def _open_doc(controller, path, text):
    """A tab whose model points at *path*, as if it had been opened."""
    editor = controller.new_document()
    doc = controller.document_for(editor)
    doc.path = path
    doc.content = text
    doc.size_on_disk = len(text.encode("utf-8"))
    doc.disk_signature = stat_signature(path)
    editor.setPlainText(text)
    doc.is_modified = False
    return editor, doc


def _pump(qapp, seconds=5.0):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.01)


def test_a_save_is_refused_when_the_file_changed_on_disk(qapp, tmp_path):
    path = tmp_path / "note.txt"
    path.write_text("original\n", encoding="utf-8")
    window, controller = _controller(tmp_path)
    try:
        editor, doc = _open_doc(controller, path, "original\n")
        path.write_text("someone else\n", encoding="utf-8")   # outside edit
        editor.setPlainText("my version\n")

        assert controller.save_current() is False, "the save must be refused"
        assert path.read_text(encoding="utf-8") == "someone else\n"
        assert not window.action_banner.isHidden()
    finally:
        window.close()


def test_overwriting_is_an_explicit_choice(qapp, tmp_path):
    path = tmp_path / "note.txt"
    path.write_text("original\n", encoding="utf-8")
    window, controller = _controller(tmp_path)
    try:
        editor, doc = _open_doc(controller, path, "original\n")
        path.write_text("someone else\n", encoding="utf-8")
        editor.setPlainText("my version\n")
        assert controller.save_current() is False
        assert window.action_banner.isHidden() is False

        controller.on_file_changed_action("overwrite")
        _pump(qapp)
        assert path.read_text(encoding="utf-8") == "my version\n"
        assert doc.disk_signature == stat_signature(path)
        assert window.action_banner.isHidden()
    finally:
        window.close()


def test_reloading_takes_the_disk_version(qapp, tmp_path):
    path = tmp_path / "note.txt"
    path.write_text("original\n", encoding="utf-8")
    window, controller = _controller(tmp_path)
    try:
        editor, doc = _open_doc(controller, path, "original\n")
        path.write_text("changed outside\n", encoding="utf-8")
        assert controller.save_current() is False, "the guard fires first"

        controller.on_file_changed_action("reload")
        assert editor.toPlainText() == "changed outside\n"
        assert doc.is_modified is False
        assert doc.disk_signature == stat_signature(path)
        assert controller.save_current() is True, "the guard is satisfied again"
    finally:
        window.close()


def test_a_clean_file_is_saved_without_a_banner(qapp, tmp_path):
    path = tmp_path / "note.txt"
    path.write_text("original\n", encoding="utf-8")
    window, controller = _controller(tmp_path)
    try:
        editor, doc = _open_doc(controller, path, "original\n")
        editor.setPlainText("edited\n")
        assert controller.save_current() is True
        assert window.action_banner.isHidden()
        _pump(qapp)
        assert path.read_text(encoding="utf-8") == "edited\n"
    finally:
        window.close()
