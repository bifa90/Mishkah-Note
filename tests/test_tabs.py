"""Pinned and coloured tabs, plus the always-on-top behaviour they trigger."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import Qt

from mufakkira.core import tab_style
from mufakkira.core.settings import Settings

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
    for editor in window.editors():
        doc = control.document_for(editor)
        if doc is not None:
            doc.is_modified = False
    window.close()


# ---------------------------------------------------------------------
# colours
# ---------------------------------------------------------------------
def test_colour_is_stored_on_the_document_and_the_tab(controller):
    editor = controller.new_document()
    controller.set_tab_color(0, "yellow")

    assert controller.current_document().color == "yellow"
    assert controller.window.tab_bar.tab_color(0) == "yellow"
    assert editor is controller.window.editor_at(0)


def test_invalid_colour_is_rejected(controller):
    controller.new_document()
    controller.set_tab_color(0, "neon")
    assert controller.current_document().color == ""


def test_colour_can_be_cleared(controller):
    controller.new_document()
    controller.set_tab_color(0, "blue")
    controller.set_tab_color(0, "")
    assert controller.window.tab_bar.tab_color(0) == ""


def test_cycle_walks_the_whole_palette(controller):
    controller.new_document()
    seen = []
    for _ in range(len(tab_style.NOTE_COLOURS) + 1):
        controller.cycle_tab_color()
        seen.append(controller.current_document().color)
    assert set(seen) == set(tab_style.codes()) | {""}


def test_colour_survives_a_tab_switch(controller):
    first = controller.new_document()
    controller.set_tab_color(0, "green")
    second = controller.new_document()
    controller.set_tab_color(1, "pink")
    controller.window.tabs.setCurrentIndex(0)

    assert controller.document_for(first).color == "green"
    assert controller.document_for(second).color == "pink"


# ---------------------------------------------------------------------
# pins
# ---------------------------------------------------------------------
def test_pinning_a_tab_raises_the_window(controller):
    controller.new_document()
    controller.toggle_tab_pin(0)

    assert controller.current_document().pinned is True
    assert controller.window.is_always_on_top() is True
    assert controller.window.pinned_index() == 0


def test_only_one_tab_can_be_pinned(controller):
    first = controller.new_document()
    controller.toggle_tab_pin(0)
    second = controller.new_document()
    controller.toggle_tab_pin(1)

    assert controller.document_for(first).pinned is False
    assert controller.document_for(second).pinned is True
    assert controller.window.pinned_index() == 1


def test_unpinning_drops_always_on_top(controller):
    controller.new_document()
    controller.toggle_tab_pin(0)
    controller.toggle_tab_pin(0)

    assert controller.current_document().pinned is False
    assert controller.window.is_always_on_top() is False
    assert controller.window.pinned_index() is None


def test_switching_to_an_unpinned_tab_drops_on_top(controller):
    controller.new_document()
    controller.toggle_tab_pin(0)
    controller.new_document()

    assert controller.window.is_always_on_top() is False
    controller.window.tabs.setCurrentIndex(0)
    assert controller.window.is_always_on_top() is True


def test_closing_the_pinned_tab_releases_on_top(controller):
    controller.new_document()
    controller.toggle_tab_pin(0)
    controller.close_tab(0)

    assert controller.window.is_always_on_top() is False
    assert controller.window.pinned_index() is None


def test_pin_shows_a_glyph_on_the_tab(controller):
    editor = controller.new_document()
    controller.toggle_tab_pin(0)
    assert controller.window.tab_bar.tabIcon(0).availableSizes()
    controller.window.set_tab_pinned(editor, False)
    assert not controller.window.tab_bar.tabIcon(0).availableSizes()


# ---------------------------------------------------------------------
# closing many tabs
# ---------------------------------------------------------------------
def test_close_other_tabs_keeps_one(controller):
    for _ in range(4):
        controller.new_document()
    controller.close_other_tabs(2)

    assert controller.window.tab_count() == 1
    assert controller.window.tabs.currentIndex() == 0


# ---------------------------------------------------------------------
# always-on-top window flag
# ---------------------------------------------------------------------
def test_always_on_top_flag_round_trip(controller):
    controller.window.set_always_on_top(True)
    assert controller.window.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
    controller.window.set_always_on_top(False)
    assert not controller.window.windowFlags() & Qt.WindowType.WindowStaysOnTopHint


def test_always_on_top_emits_once(controller):
    seen = []
    controller.window.always_on_top_changed.connect(seen.append)
    controller.window.set_always_on_top(True)
    controller.window.set_always_on_top(True)      # already on
    assert seen == [True]


def test_typing_preferences_reach_new_editors(controller):
    controller.settings.auto_close_brackets = False
    controller.settings.word_completion = False
    editor = controller.new_document()

    assert editor.auto_close_enabled() is False
    assert editor.word_completion_enabled() is False


def test_highlighting_setting_is_off_by_default(controller):
    editor = controller.new_document()
    assert controller.settings.syntax_highlighting is False
    assert editor.syntax_highlighting_enabled() is False


def test_language_override_is_per_tab(controller):
    first = controller.new_document()
    controller.set_tab_language("python")
    assert first.language_code() == "python"
    assert first.syntax_highlighting_enabled() is False   # toggling is separate

    second = controller.new_document()
    assert second.language_code() == "plain"
    controller.set_tab_language("auto")
    assert controller.current_document().language == "auto"


def test_path_drives_the_detected_language(controller):
    editor = controller.new_document()
    controller.current_document().path = Path("/tmp/example.rs")
    controller._apply_highlighting(editor)
    assert editor.language_code() == "rust"


def test_untitled_tab_follows_the_ui_language(controller, qapp):
    from mufakkira.core import i18n

    editor = controller.new_document()
    assert controller.window.tabs.tabText(0) == i18n.tr("app.untitled")

    i18n.set_language("ar")
    try:
        controller.window.set_tab_title(editor, controller._doc_title(
            controller.current_document()), False)
        assert controller.window.tabs.tabText(0) == "بدون عنوان"
    finally:
        i18n.set_language("en")


def test_modified_marker_is_added_once(controller):
    editor = controller.new_document()
    editor.setPlainText("changed")
    text = controller.window.tabs.tabText(0)
    assert text.count("●") == 1
