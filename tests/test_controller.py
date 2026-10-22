"""Controller behaviour: the buffer reaches the disk, and the chrome follows."""

from __future__ import annotations

from pathlib import Path

import pytest

from mufakkira.core.settings import Settings
from mufakkira.core.text_direction import AUTO, LTR, RTL

pytestmark = pytest.mark.usefixtures("qapp")


@pytest.fixture()
def controller(qapp, tmp_path):
    from mufakkira.controllers.main_controller import MainController
    from mufakkira.services.file_service import FileService
    from mufakkira.views.main_window import MainWindow

    settings = Settings(path=tmp_path / "settings.json", restore_session=False)
    window = MainWindow()
    control = MainController(window, settings, FileService())
    yield control
    window.close()


# ---------------------------------------------------------------------
# regression: saving used to write an empty file because the widget's text
# was never copied into the model
# ---------------------------------------------------------------------
def test_save_writes_the_editor_buffer(controller, tmp_path):
    editor = controller.new_document()
    editor.setPlainText("سطر عربي\nenglish line\n")
    target = tmp_path / "saved.txt"

    controller.current_document().path = target
    captured = {}
    controller.files.save = lambda doc, tgt=None: captured.update(
        text=doc.content, target=tgt or doc.path)

    assert controller.save_current() is True
    assert captured["text"] == "سطر عربي\nenglish line\n"
    assert Path(captured["target"]) == target


def test_sync_content_marks_size_unknown(controller):
    editor = controller.new_document()
    doc = controller.current_document()
    doc.size_on_disk = 1024
    editor.setPlainText("abc")
    controller._sync_content(editor, doc)
    assert doc.content == "abc"
    assert doc.size_on_disk == 0


def test_sync_content_skips_preview_documents(controller):
    editor = controller.new_document()
    doc = controller.current_document()
    doc.truncated = True
    editor.setPlainText("only a preview")
    controller._sync_content(editor, doc)
    assert doc.content == ""


def test_save_refuses_read_only_preview(controller):
    editor = controller.new_document()
    doc = controller.current_document()
    doc.truncated = True
    editor.setPlainText("preview")
    assert controller.save_current() is False


# ---------------------------------------------------------------------
# chrome
# ---------------------------------------------------------------------
def test_window_title_uses_the_document_title(controller):
    controller.new_document()
    controller.window.setWindowTitle("notes.txt - Notepad")
    controller._sync_ui(controller.window.current_editor())
    title = controller.window.windowTitle()
    assert title.endswith("Notepad")
    assert "بلال" not in title and "Bilal" not in title


def test_set_direction_updates_every_layer(controller):
    editor = controller.new_document()
    editor.setPlainText("hello")
    controller.set_direction(RTL)

    assert controller.current_document().direction_mode == RTL
    assert editor.layoutDirection().name.endswith("RightToLeft")
    assert controller.window.status.direction_mode() == RTL

    controller.set_direction(LTR)
    assert editor.layoutDirection().name.endswith("LeftToRight")


def test_auto_direction_detects_arabic(controller):
    editor = controller.new_document()
    editor.setPlainText("مرحبا بالعالم")
    assert controller.auto_detect_direction() == RTL
    editor.setPlainText("hello world")
    assert controller.auto_detect_direction() == LTR


def test_new_document_uses_the_configured_default(controller):
    controller.settings.default_direction = AUTO
    editor = controller.new_document()
    assert editor.direction_mode == AUTO


def test_tab_titles_track_modification(controller):
    editor = controller.new_document()
    controller.current_document().path = Path("/tmp/example.txt")
    controller.window.set_tab_title(editor, "example.txt", False)
    editor.setPlainText("changed")
    controller._on_text_changed(editor)
    assert controller.current_document().is_modified is True
