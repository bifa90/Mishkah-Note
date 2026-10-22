"""Controller behaviour: the buffer reaches the disk, and the chrome follows."""

from __future__ import annotations

from pathlib import Path

import pytest

from mishkah.core.settings import Settings
from mishkah.core.text_direction import AUTO, LTR, RTL

pytestmark = pytest.mark.usefixtures("qapp")


@pytest.fixture()
def controller(qapp, tmp_path):
    from mishkah.controllers.main_controller import MainController
    from mishkah.services.file_service import FileService
    from mishkah.views.main_window import MainWindow

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
    controller.window.setWindowTitle("notes.txt - Mishkah Note")
    controller._sync_ui(controller.window.current_editor())
    title = controller.window.windowTitle()
    assert title.endswith("Mishkah Note")
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


@pytest.mark.parametrize("code", ["en", "zh-Hans", "hi", "es", "fr", "ar", "bn", "pt", "ru", "ur"])
def test_editor_font_respects_language_and_user_choice(controller, code):
    from mishkah.core.languages import editor_font_families

    controller.settings.ui_language = code
    controller.settings.font_family = ""
    assert controller.editor_font().families() == editor_font_families(code)
    controller.settings.font_family = "DejaVu Sans Mono"
    assert controller.editor_font().families()[0] == "DejaVu Sans Mono"


def test_close_with_save_waits_for_success(controller, tmp_path):
    from PySide6.QtWidgets import QMessageBox

    editor = controller.new_document()
    editor.setPlainText("keep me")
    doc = controller.current_document()
    doc.path = tmp_path / "note.txt"
    controller.window.confirm_unsaved = lambda _: QMessageBox.StandardButton.Save
    controller.files.save = lambda *_: None
    controller.close_tab(controller.window.index_of(editor))
    assert editor in controller._docs
    controller.window.show_error = lambda *_: None
    controller._on_save_failed(str(doc.path), "OSError", "disk full")
    assert editor in controller._docs
    doc.is_modified = False


def test_save_worker_captures_text_and_format(controller, tmp_path):
    from mishkah.services.file_service import SaveWorker

    controller.new_document()
    doc = controller.current_document()
    doc.content = "snapshot"
    worker = SaveWorker(doc, tmp_path / "snapshot.txt")
    doc.content = "later edit"
    doc.set_encoding("utf-16-le")
    assert worker.content == "snapshot"
    assert worker.fmt.encoding == "utf-8"


def test_loaded_document_is_not_marked_modified(controller, tmp_path):
    from mishkah.models.document import DocumentModel

    path = tmp_path / "loaded.txt"
    doc = DocumentModel(path=path, content="loaded text")
    controller._on_loaded(doc)
    assert not doc.is_modified
    assert doc.revision == 0


def test_close_event_obeys_cancel(qapp):
    from mishkah.services.file_service import FileService
    from mishkah.views.main_window import MainWindow

    class CloseGuard:
        files = FileService()

        @staticmethod
        def confirm_close():
            return False

    window = MainWindow()
    window.setProperty("controller", CloseGuard())
    window.show()
    assert window.close() is False
    window.setProperty("controller", None)
    window.close()


def test_window_save_intent_defers_close(controller, tmp_path):
    from PySide6.QtWidgets import QMessageBox

    editor = controller.new_document()
    editor.setPlainText("save before exit")
    doc = controller.current_document()
    doc.path = tmp_path / "exit.txt"
    controller.window.confirm_unsaved = lambda _: QMessageBox.StandardButton.Save
    controller.files.save = lambda *_: None
    assert controller.confirm_close() is False
    assert controller._window_close_after_save
    controller._window_close_after_save = False
    doc.is_modified = False


def test_save_completion_keeps_new_edits_dirty(controller, tmp_path):
    editor = controller.new_document()
    editor.setPlainText("snapshot")
    doc = controller.current_document()
    snapshot_revision = doc.revision
    editor.insertPlainText("later")
    doc.mark_saved(tmp_path / "saved.txt", 8, revision=snapshot_revision)
    controller._on_saved(doc, 8)
    assert doc.is_modified
    doc.is_modified = False
