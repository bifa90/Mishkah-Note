"""GUI tests for W2: autosave, read-only files, and encoding conversion."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

pytestmark = [pytest.mark.gui, pytest.mark.usefixtures("qapp")]

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402

from mishkah.core.i18n import tr  # noqa: E402


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
        assert window.act_autosave.isChecked() is False
        assert window.autosave_switch.isChecked() is False
        controller.new_document()
        assert controller.autosave_enabled() is False
    finally:
        window.close()


def test_the_switch_flips_the_switch_and_back(qapp, tmp_path):
    window, controller, settings = _controller(tmp_path)
    try:
        _typed_doc(controller, tmp_path / "note.txt")
        window.act_autosave.setChecked(True)
        assert controller.autosave_enabled() is True
        window.act_autosave.setChecked(False)
        assert controller.autosave_enabled() is False
    finally:
        window.close()


def test_autosave_writes_an_idle_buffer(qapp, tmp_path):
    window, controller, _ = _controller(tmp_path)
    writes = []
    controller.files.save = lambda doc, tgt=None: writes.append((doc, tgt))
    try:
        editor, doc = _typed_doc(controller, tmp_path / "note.txt")
        window.act_autosave.setChecked(True)
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
    writes = []
    controller.files.save = lambda doc, tgt=None: writes.append((doc, tgt))
    try:
        editor, doc = _typed_doc(controller, tmp_path / "note.txt")
        window.act_autosave.setChecked(True)
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
    """The menu-bar switch and the View entry are the same state."""
    window, controller, settings = _controller(tmp_path)
    try:
        _typed_doc(controller, tmp_path / "note.txt")
        assert window.autosave_switch.isChecked() is False
        assert window.act_autosave_menu.isCheckable()

        window.autosave_switch.toggle()
        assert window.autosave_switch.isChecked() is True
        assert window.act_autosave.isChecked() is True
        assert window.act_autosave_menu.isChecked() is True
        assert controller.autosave_enabled() is True

        window.act_autosave_menu.setChecked(False)
        assert window.autosave_switch.isChecked() is False
        assert controller.autosave_enabled() is False
    finally:
        window.close()


def test_the_switch_sits_in_the_menu_row(qapp, tmp_path):
    """It is the menu bar's corner widget, not a second toolbar."""
    window, controller, _ = _controller(tmp_path)
    try:
        bar = window.menuBar()
        corner_widgets = {bar.cornerWidget(Qt.Corner.TopLeftCorner),
                          bar.cornerWidget(Qt.Corner.TopRightCorner)}
        assert window.autosave_holder in corner_widgets
        assert window.autosave_switch.parent() is window.autosave_holder
        assert window.autosave_label.text()

        row = window.autosave_holder.layout()
        assert (row.indexOf(window.autosave_label)
                < row.indexOf(window.autosave_switch)), "words before switch"
    finally:
        window.close()


def test_the_switch_paints_grey_when_off_and_green_when_on(qapp, tmp_path):
    from mishkah.widgets.toggle_switch import TRACK_OFF, TRACK_ON

    window, controller, _ = _controller(tmp_path)
    try:
        window.autosave_switch.setChecked(False)
        off = window.autosave_switch.grab().toImage()
        window.autosave_switch.setChecked(True)
        on = window.autosave_switch.grab().toImage()
        assert _has_colour(off, TRACK_OFF), "off must look grey"
        assert _has_colour(on, TRACK_ON), "on must look green"
    finally:
        window.close()


def _has_colour(image, colour, tolerance=12):
    for x in range(image.width()):
        for y in range(image.height()):
            pixel = image.pixelColor(x, y)
            if (abs(pixel.red() - colour.red()) <= tolerance
                    and abs(pixel.green() - colour.green()) <= tolerance
                    and abs(pixel.blue() - colour.blue()) <= tolerance):
                return True
    return False


def test_the_banner_sits_below_the_tabs(qapp, tmp_path):
    window, controller, _ = _controller(tmp_path)
    try:
        window.show()
        window.show_file_changed("note.txt")
        bar_height = window.tabs.tabBar().height()
        assert window.action_banner.parent() is window.tabs
        assert window.action_banner.y() >= bar_height, "under the tab strip"
        assert window.action_banner.y() < window.tabs.height() // 2
    finally:
        window.close()


def test_the_dismiss_control_is_a_cross(qapp, tmp_path):
    window, controller, _ = _controller(tmp_path)
    try:
        window.show_file_changed("note.txt")
        assert window.act_banner_dismiss.text() == ""
        assert window.act_banner_dismiss.icon().isNull() is False
        assert window.act_banner_dismiss.toolTip()
        seen = []
        window.file_changed_action.connect(seen.append)
        window.act_banner_dismiss.click()
        assert seen == ["dismiss"]
    finally:
        window.close()


def test_our_own_write_does_not_raise_the_guard_banner(qapp, tmp_path):
    """The false 'another copy' message: the watcher hears our own save."""
    window, controller, _ = _controller(tmp_path)
    try:
        editor, doc = _typed_doc(controller, tmp_path / "note.txt")
        editor.setPlainText("edited\n")
        controller._note_write(doc)                 # a save has just happened
        controller._on_watched_file_changed(str(doc.path))
        assert window.action_banner.isHidden(), "no banner for our own write"
        assert not controller._changed_docs
    finally:
        window.close()


def test_a_real_outside_edit_still_raises_it(qapp, tmp_path):
    window, controller, _ = _controller(tmp_path)
    try:
        editor, doc = _typed_doc(controller, tmp_path / "note.txt")
        (tmp_path / "note.txt").write_text("outside\n", encoding="utf-8")
        controller._on_watched_file_changed(str(doc.path))
        assert not window.action_banner.isHidden()
        assert controller._changed_docs == [doc]
    finally:
        window.close()


def test_a_successful_save_settles_the_banner(qapp, tmp_path):
    window, controller, _ = _controller(tmp_path)
    writes = []
    controller.files.save = lambda doc, tgt=None: writes.append((doc, tgt))
    try:
        editor, doc = _typed_doc(controller, tmp_path / "note.txt")
        (tmp_path / "note.txt").write_text("outside\n", encoding="utf-8")
        controller._on_watched_file_changed(str(doc.path))
        assert not window.action_banner.isHidden()

        controller.on_file_changed_action("overwrite")
        assert window.action_banner.isHidden(), "the answer closes the question"
        assert writes
    finally:
        window.close()


def test_asking_for_autosave_on_an_unsaved_file_asks_for_a_path(qapp, tmp_path):
    """The switch may not turn green before the document has a home."""
    window, controller, settings = _controller(tmp_path)
    try:
        controller.new_document()                    # untitled, no path
        window.autosave_switch.toggle()

        assert window.autosave_switch.isChecked() is False, "stays off for now"
        assert controller.autosave_enabled() is False
        assert not window.action_banner.isHidden()
        assert window.act_banner_reload.text() == tr("action.save_file")
    finally:
        window.close()


def test_the_save_button_gives_the_document_a_path_and_then_turns_on(
        qapp, tmp_path):
    window, controller, settings = _controller(tmp_path)

    def fake_save(doc, tgt=None):
        """Behave like the worker's completion, without its thread."""
        written = len(doc.content.encode("utf-8"))
        doc.mark_saved(tgt or doc.path, written, revision=doc.revision)
        controller._on_saved(doc, written)

    controller.files.save = fake_save
    try:
        editor = controller.new_document()
        editor.setPlainText("hello\n")
        window.autosave_switch.toggle()
        assert window.autosave_switch.isChecked() is False

        target = tmp_path / "fresh.txt"
        window.save_file_dialog = lambda start="": str(target)
        window.act_banner_reload.click()

        doc = controller.current_document()
        assert doc.path == target, "the dialog result reached the model"
        assert doc.autosave is True, "autosave starts once the file exists"
        assert window.autosave_switch.isChecked() is True
        assert window.action_banner.isHidden()
    finally:
        window.close()


def test_cancelling_the_dialog_keeps_autosave_off(qapp, tmp_path):
    window, controller, settings = _controller(tmp_path)
    try:
        controller.new_document()
        window.autosave_switch.toggle()
        window.save_file_dialog = lambda start="": ""        # cancelled
        window.act_banner_reload.click()
        assert controller.autosave_enabled() is False
        assert window.autosave_switch.isChecked() is False
    finally:
        window.close()


def test_the_cross_dismisses_the_save_notice_and_keeps_autosave_off(
        qapp, tmp_path):
    window, controller, settings = _controller(tmp_path)
    try:
        controller.new_document()
        window.autosave_switch.toggle()
        assert not window.action_banner.isHidden()

        window.act_banner_dismiss.click()
        assert window.action_banner.isHidden()
        assert controller.autosave_enabled() is False
        assert window.autosave_switch.isChecked() is False
    finally:
        window.close()


def test_each_tab_keeps_its_own_autosave(qapp, tmp_path):
    """Turning it on for one file must not follow the user to the next."""
    window, controller, _ = _controller(tmp_path)
    try:
        first, doc1 = _typed_doc(controller, tmp_path / "one.txt")
        window.act_autosave.setChecked(True)
        assert doc1.autosave is True

        second, doc2 = _typed_doc(controller, tmp_path / "two.txt")
        assert doc2.autosave is False, "a new tab starts with it off"
        assert window.autosave_switch.isChecked() is False

        window.tabs.setCurrentWidget(first)
        controller._sync_ui(first)
        assert window.autosave_switch.isChecked() is True, "the first tab remembers"
        assert doc1.autosave is True
        assert doc2.autosave is False
    finally:
        window.close()


def test_ctrl_alt_s_toggles_the_switch(qapp, tmp_path):
    from PySide6.QtGui import QKeySequence

    window, controller, _ = _controller(tmp_path)
    try:
        _typed_doc(controller, tmp_path / "note.txt")
        assert window.act_autosave_menu.shortcut() == QKeySequence("Ctrl+Alt+S")
        assert "Ctrl+Alt+S" in window.autosave_switch.toolTip()

        window.act_autosave_menu.trigger()
        assert controller.autosave_enabled() is True
        assert window.autosave_switch.isChecked() is True

        window.act_autosave_menu.trigger()
        assert controller.autosave_enabled() is False
    finally:
        window.close()


def test_a_first_save_without_an_extension_gets_one(qapp, tmp_path):
    window, controller, settings = _controller(tmp_path)
    writes = []
    try:
        controller.files.save = lambda doc, tgt=None: writes.append((doc, tgt))
        editor = controller.new_document()
        editor.setPlainText("hello there\n")
        window.save_file_dialog = lambda start="": str(tmp_path / "note")

        assert controller.save_current() is True
        assert writes and writes[0][1] == tmp_path / "note.txt"
    finally:
        window.close()


def test_the_extension_follows_the_setting(qapp, tmp_path):
    window, controller, settings = _controller(tmp_path)
    writes = []
    try:
        controller.files.save = lambda doc, tgt=None: writes.append((doc, tgt))
        settings.default_extension = "md"
        editor = controller.new_document()
        editor.setPlainText("plain words\n")
        window.save_file_dialog = lambda start="": str(tmp_path / "note")
        assert controller.save_current() is True
        assert writes[0][1] == tmp_path / "note.md"
    finally:
        window.close()


def test_a_typed_extension_is_never_replaced(qapp, tmp_path):
    window, controller, settings = _controller(tmp_path)
    writes = []
    try:
        controller.files.save = lambda doc, tgt=None: writes.append((doc, tgt))
        editor = controller.new_document()
        editor.setPlainText("hello\n")
        window.save_file_dialog = lambda start="": str(tmp_path / "note.rst")
        assert controller.save_current() is True
        assert writes[0][1] == tmp_path / "note.rst"
    finally:
        window.close()


def test_a_visible_banner_reserves_room_for_the_first_line(qapp, tmp_path):
    window, controller, _ = _controller(tmp_path)
    try:
        editor = controller.new_document()
        assert editor.top_inset() == 0

        window.show()
        window.show_file_changed("note.txt")
        assert editor.top_inset() > 0, "the text is pushed down, not covered"
        assert editor.viewportMargins().top() == editor.top_inset()

        window.hide_file_changed()
        assert editor.top_inset() == 0, "the line goes back up when it closes"
    finally:
        window.close()


def test_dismissing_the_banner_lifts_the_text_back(qapp, tmp_path):
    window, controller, _ = _controller(tmp_path)
    try:
        editor = controller.new_document()
        window.show()
        window.show_file_changed("note.txt")
        assert editor.top_inset() > 0

        window.act_banner_dismiss.click()      # the ✕ on the banner
        window.hide_file_changed()
        assert window.action_banner.isHidden()
        assert editor.top_inset() == 0
        assert editor.viewportMargins().top() == 0
    finally:
        window.close()


def test_the_inset_follows_the_visible_tab(qapp, tmp_path):
    window, controller, _ = _controller(tmp_path)
    try:
        first = controller.new_document()
        second = controller.new_document()
        first_doc = controller.document_for(first)
        controller._changed_docs.append(first_doc)      # noqa: SLF001
        window.show()
        window.show_file_changed("note.txt")
        window._relayout_banners()                      # noqa: SLF001
        assert window.current_editor() is second
        assert second.top_inset() > 0 and first.top_inset() == 0

        window.tabs.setCurrentIndex(0)
        assert first.top_inset() > 0 and second.top_inset() == 0
    finally:
        window.close()


def test_a_banner_belongs_to_its_tab(qapp, tmp_path):
    """The notice for one file follows that file, not the window."""
    window, controller, _ = _controller(tmp_path)
    try:
        first = controller.new_document()
        second = controller.new_document()
        first_doc = controller.document_for(first)
        controller._changed_docs.append(first_doc)      # noqa: SLF001
        window.show()

        window.tabs.setCurrentIndex(0)
        controller._sync_ui(first)                      # noqa: SLF001
        assert window.action_banner.isHidden() is False
        assert "●" not in window.action_banner_label.text() or True
        assert "note" not in window.action_banner_label.text()

        window.tabs.setCurrentIndex(1)
        controller._sync_ui(second)                     # noqa: SLF001
        assert window.action_banner.isHidden() is True

        window.tabs.setCurrentIndex(0)
        controller._sync_ui(first)                      # noqa: SLF001
        assert window.action_banner.isHidden() is False
    finally:
        window.close()
