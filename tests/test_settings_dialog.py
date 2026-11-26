"""The seven-category settings dialog (CD-02, revised)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.gui


def _dialog(settings=None):
    from mishkah.core.settings import Settings
    from mishkah.widgets.settings_dialog import SettingsDialog

    return SettingsDialog(settings or Settings())


def test_the_dialog_has_the_seven_categories(qapp):
    dialog = _dialog()
    try:
        assert dialog.category_keys() == [
            "appearance", "editor", "typing", "files", "tabs",
            "shortcuts", "advanced",
        ]
        assert dialog.stack.count() == 7
        assert dialog.list_categories.count() == 7
    finally:
        dialog.close()


def test_every_setting_has_a_widget(qapp):
    """A key with no page would be a setting nobody can reach."""
    from mishkah.core.settings import HIDDEN_FIELDS, SCHEMA

    dialog = _dialog()
    try:
        bound = set(dialog.bound_keys()) | {"settings_page"}
        editable = set(SCHEMA) - HIDDEN_FIELDS
        assert editable - bound == set(), "settings with no control"
        assert bound - editable == set(), "controls for settings not stored"
    finally:
        dialog.close()


def test_the_dialog_reopens_on_the_last_category(qapp):
    from mishkah.core.settings import Settings

    dialog = _dialog(Settings(settings_page="files"))
    try:
        assert dialog.current_category() == "files"
    finally:
        dialog.close()


def test_the_chosen_category_is_saved(qapp):
    from mishkah.core.settings import Settings

    settings = Settings()
    dialog = _dialog(settings)
    try:
        dialog.show_category("shortcuts")
        dialog.apply_to(settings)
        assert settings.settings_page == "shortcuts"
    finally:
        dialog.close()


def test_cancel_changes_nothing(qapp):
    from mishkah.core.settings import Settings

    settings = Settings()
    dialog = _dialog(settings)
    try:
        dialog.chk_word_wrap.setChecked(not settings.word_wrap)
        dialog.spin_tab.setValue(9)
        dialog.reject()
        assert settings.word_wrap is True
        assert settings.tab_width == 4
    finally:
        dialog.close()


def test_apply_keeps_the_dialog_open(qapp):
    dialog = _dialog()
    calls = []
    try:
        dialog.applied.connect(lambda: calls.append(True))
        dialog.apply_button.click()
        assert calls == [True], "the controller is told to apply now"
        assert dialog.result() == 0, "Apply does not accept the dialog"
    finally:
        dialog.close()


def test_each_page_scrolls_on_its_own(qapp):
    from PySide6.QtWidgets import QScrollArea

    dialog = _dialog()
    try:
        for index in range(dialog.stack.count()):
            assert isinstance(dialog.stack.widget(index), QScrollArea)
    finally:
        dialog.close()


def test_the_buttons_are_outside_the_scrolling(qapp):
    dialog = _dialog()
    try:
        assert dialog.buttons.parent() is dialog
        for index in range(dialog.stack.count()):
            assert not dialog.stack.widget(index).isAncestorOf(dialog.buttons)
            assert not dialog.stack.widget(index).widget().isAncestorOf(
                dialog.buttons)
    finally:
        dialog.close()


def test_the_buttons_stay_visible_on_a_short_screen(qapp):
    dialog = _dialog()
    try:
        dialog.resize(720, 560)
        dialog.show()
        rect = dialog.rect()
        geometry = dialog.buttons.geometry()
        assert rect.contains(geometry), "the buttons never leave the window"
        assert geometry.top() > dialog.stack.geometry().top() + 40
    finally:
        dialog.close()


def test_ctrl_tab_walks_the_categories(qapp):
    dialog = _dialog()
    try:
        assert dialog.current_category() == "appearance"
        dialog._next_category()                      # noqa: SLF001
        assert dialog.current_category() == "editor"
        dialog._next_category(-1)                    # noqa: SLF001
        assert dialog.current_category() == "appearance"
        dialog._next_category(-1)                    # noqa: SLF001
        assert dialog.current_category() == "advanced", "wraps around"
    finally:
        dialog.close()


def test_the_new_session_settings_round_trip(qapp):
    from mishkah.core.settings import Settings

    settings = Settings()
    dialog = _dialog(settings)
    try:
        dialog.cmb_last_tab.setCurrentIndex(
            dialog.cmb_last_tab.findData("quit"))
        dialog.cmb_redo.setCurrentIndex(dialog.cmb_redo.findData("platform"))
        dialog.cmb_replace.setCurrentIndex(
            dialog.cmb_replace.findData("platform"))
        dialog.apply_to(settings)

        assert settings.last_tab_action == "quit"
        assert settings.redo_shortcut == "platform"
        assert settings.replace_shortcut == "platform"
    finally:
        dialog.close()


def test_the_shortcut_hint_follows_the_choice(qapp):
    dialog = _dialog()
    try:
        assert "Ctrl+H" in dialog.lbl_keys.text()
        dialog.cmb_replace.setCurrentIndex(
            dialog.cmb_replace.findData("platform"))
        assert "Ctrl+R" in dialog.lbl_keys.text(), "the hint follows the choice"
        dialog.cmb_redo.setCurrentIndex(dialog.cmb_redo.findData("platform"))
        assert "Ctrl+Y" not in dialog.lbl_keys.text()
    finally:
        dialog.close()


def test_reset_restores_the_defaults_without_saving(qapp):
    from mishkah.core.settings import Settings

    settings = Settings(word_wrap=False, tab_width=8)
    dialog = _dialog(settings)
    try:
        dialog.btn_reset.click()
        assert dialog.chk_word_wrap.isChecked() is True
        assert dialog.spin_tab.value() == 4
        assert settings.word_wrap is False, "reset only touches the widgets"
    finally:
        dialog.close()


def test_the_advanced_page_shows_the_settings_file(qapp, tmp_path):
    from mishkah.core.settings import Settings

    path = tmp_path / "settings.json"
    dialog = _dialog(Settings(path=path))
    try:
        assert str(path) in dialog.lbl_path.text()
    finally:
        dialog.close()


def test_the_hard_cap_is_reachable_from_advanced(qapp):
    from mishkah.core.settings import Settings

    settings = Settings(hard_limit_mb=512)
    dialog = _dialog(settings)
    try:
        assert dialog.spin_hard_cap.value() == 512
        dialog.spin_hard_cap.setValue(256)
        assert dialog.values()["hard_limit_mb"] == 256
    finally:
        dialog.close()


def test_applying_updates_the_window_shortcuts(qapp, tmp_path):
    from mishkah.controllers.main_controller import MainController
    from mishkah.core.settings import Settings
    from mishkah.services.file_service import FileService
    from mishkah.views.main_window import MainWindow
    from mishkah.widgets.settings_dialog import SettingsDialog

    window = MainWindow()
    settings = Settings(path=tmp_path / "settings.json", restore_session=False)
    controller = MainController(window, settings, FileService())
    try:
        assert "Ctrl+Y" in [k.toString() for k in window.act_redo.shortcuts()]

        dialog = SettingsDialog(settings, window)
        dialog.cmb_redo.setCurrentIndex(dialog.cmb_redo.findData("platform"))
        dialog.cmb_replace.setCurrentIndex(
            dialog.cmb_replace.findData("platform"))
        controller._commit_settings(dialog)          # noqa: SLF001

        assert [k.toString() for k in window.act_redo.shortcuts()] == [
            "Ctrl+Shift+Z"]
        assert window.act_replace.shortcut().toString() == "Ctrl+R"
        dialog.close()
    finally:
        window.close()
