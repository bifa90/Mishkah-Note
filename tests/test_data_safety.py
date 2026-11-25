"""GUI tests for W2: autosave, read-only files, and encoding conversion."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

pytestmark = [pytest.mark.gui, pytest.mark.usefixtures("qapp")]

pytest.importorskip("PySide6")


@pytest.fixture(autouse=True)
def _dispose_widgets(qapp):
    yield
    from PySide6.QtCore import QEvent

    for widget in list(qapp.topLevelWidgets()):
        widget.close()
        widget.deleteLater()
    qapp.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def _controller(tmp_path, **settings_kwargs):
    from mishkah.controllers.main_controller import MainController
    from mishkah.core.settings import Settings
    from mishkah.services.file_service import FileService
    from mishkah.views.main_window import MainWindow

    window = MainWindow()
    settings = Settings(path=tmp_path / "settings.json", restore_session=False,
                        **settings_kwargs)
    return window, MainController(window, settings, FileService()), settings


def _typed_doc(controller, path, text="hello\n"):
    from pathlib import Path as _Path

    from mishkah.core.disk_state import stat_signature

    editor = controller.new_document()
    doc = controller.document_for(editor)
    path.write_text(text, encoding="utf-8")
    doc.path = path
    doc.content = text
    doc.disk_signature = stat_signature(_Path(path))
    editor.setPlainText(text)
    doc.is_modified = False
    return editor, doc


# ------------------------------------------------------------- CD-01
def test_autosave_is_off_until_asked(qapp, tmp_path):
    window, controller, settings = _controller(tmp_path)
    try:
        assert settings.autosave is False
        assert window.act_autosave.isChecked() is False
        assert controller.autosave_enabled() is False
    finally:
        window.close()


def test_the_toolbar_switch_flips_the_setting_and_back(qapp, tmp_path):
    window, controller, settings = _controller(tmp_path)
    try:
        window.act_autosave.setChecked(True)
        assert settings.autosave is True
        assert controller.autosave_enabled() is True
        window.act_autosave.setChecked(False)
        assert settings.autosave is False
    finally:
        window.close()


def test_autosave_writes_an_idle_buffer(qapp, tmp_path):
    window, controller, _ = _controller(tmp_path)
    window.act_autosave.setChecked(True)
    writes = []
    controller.files.save = lambda doc, tgt=None: writes.append((doc, tgt))
    try:
        editor, doc = _typed_doc(controller, tmp_path / "note.txt")
        editor.setPlainText("edited\n")
        assert doc.is_modified

        controller._autosave_now()
        assert len(writes) == 1
        assert writes[0][0].content == "edited\n"
    finally:
        window.close()


def test_autosave_is_deaf_when_it_is_off(qapp, tmp_path):
    window, controller, _ = _controller(tmp_path)
    writes = []
    controller.files.save = lambda doc, tgt=None: writes.append((doc, tgt))
    try:
        editor, doc = _typed_doc(controller, tmp_path / "note.txt")
        editor.setPlainText("edited\n")
        controller._autosave_now()
        assert writes == []
    finally:
        window.close()


def test_autosave_is_silenced_by_an_unanswered_conflict(qapp, tmp_path):
    window, controller, _ = _controller(tmp_path)
    window.act_autosave.setChecked(True)
    writes = []
    controller.files.save = lambda doc, tgt=None: writes.append((doc, tgt))
    try:
        editor, doc = _typed_doc(controller, tmp_path / "note.txt")
        editor.setPlainText("edited\n")
        (tmp_path / "note.txt").write_text("outside\n", encoding="utf-8")

        controller._autosave_now()
        assert writes == [], "the outside edit wins until it is answered"
        assert not window.action_banner.isHidden()
    finally:
        window.close()


# ------------------------------------------------------------- CD-05
def test_a_read_only_document_refuses_to_save(qapp, tmp_path):
    window, controller, _ = _controller(tmp_path)
    writes = []
    controller.files.save = lambda doc, tgt=None: writes.append((doc, tgt))
    try:
        editor, doc = _typed_doc(controller, tmp_path / "blob.bin")
        doc.read_only = True
        editor.setPlainText("edited\n")
        assert controller.save_current() is False
        assert writes == []
        assert not window.banner.isHidden(), "the reason is on screen"
    finally:
        window.close()


def test_save_as_is_still_possible_for_read_only(qapp, tmp_path):
    window, controller, _ = _controller(tmp_path)
    writes = []
    controller.files.save = lambda doc, tgt=None: writes.append((doc, tgt))
    try:
        editor, doc = _typed_doc(controller, tmp_path / "blob.bin")
        doc.read_only = True
        editor.setPlainText("edited\n")
        window.save_file_dialog = lambda start="": str(tmp_path / "copy.txt")
        assert controller.save_current(as_copy=True) is True
        assert writes and writes[0][1] == tmp_path / "copy.txt"
    finally:
        window.close()


# ------------------------------------------------------------- CD-19 / M1
def test_a_save_after_reopen_is_blocked_until_conversion(qapp, tmp_path):
    from mishkah.core.disk_state import stat_signature

    path = tmp_path / "legacy.txt"
    path.write_text("hello\n", encoding="utf-8")
    window, controller, _ = _controller(tmp_path)
    writes = []
    controller.files.save = lambda doc, tgt=None: writes.append((doc, tgt))
    try:
        editor, doc = _typed_doc(controller, path)
        doc.encoding_pending = True
        doc.disk_signature = stat_signature(path)
        editor.setPlainText("edited\n")

        assert controller.save_current() is False, "conversion must be explicit"
        assert writes == []

        window.file_changed_action.emit("convert")
        assert writes and writes[0][0].content == "edited\n"
        assert doc.encoding_pending is False
    finally:
        window.close()


def test_reopen_with_another_encoding_stays_in_the_same_tab(qapp, tmp_path):
    path = tmp_path / "arabic.txt"
    window, controller, _ = _controller(tmp_path)
    try:
        editor, doc = _typed_doc(controller, path, "????\n")
        # The tab was opened on a mis-decoded file; now put the real bytes in
        # place and read them again with the right encoding.
        path.write_bytes("مرحبا\n".encode("cp1256"))
        tabs_before = window.tab_count()

        controller.reopen_with_encoding("cp1256")
        assert window.tab_count() == tabs_before, "no second copy of the file"
        assert editor.toPlainText() == "مرحبا\n"
        assert doc.encoding == "cp1256"
        assert doc.encoding_pending is True
        assert not window.action_banner.isHidden()
    finally:
        window.close()


def test_the_switch_is_reachable_twice(qapp, tmp_path):
    """Toolbar and View menu must agree, and both must exist."""
    window, controller, settings = _controller(tmp_path)
    try:
        assert window.quick_bar.isVisible() is not None
        assert window.act_autosave.icon().isNull() is False, "the button has an icon"
        assert window.act_autosave_menu.isCheckable()

        window.act_autosave.setChecked(True)
        assert window.act_autosave_menu.isChecked() is True
        assert settings.autosave is True

        window.act_autosave_menu.setChecked(False)
        assert window.act_autosave.isChecked() is False
        assert settings.autosave is False
    finally:
        window.close()
