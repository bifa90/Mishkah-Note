"""Tests for the settings/progress dialogs, the icon set and the translations."""

from __future__ import annotations

from pathlib import Path

import pytest

from mishkah.core import i18n, resources
from mishkah.core.i18n_data import STRINGS
from mishkah.core.languages import all_languages
from mishkah.core.settings import Settings

pytestmark = pytest.mark.usefixtures("qapp")


# ---------------------------------------------------------------------------
# translations
# ---------------------------------------------------------------------------
def test_every_string_exists_in_every_language():
    codes = {lang.code for lang in all_languages()}
    gaps = {key: sorted(codes - set(table)) for key, table in STRINGS.items()
            if codes - set(table)}
    assert gaps == {}


def test_translation_is_not_the_key_itself():
    for lang in all_languages():
        i18n.set_language(lang.code)
        assert i18n.tr("settings.title") != "settings.title"
        assert i18n.tr("app.title", title="x.txt", app="A") == \
            i18n.tr("app.title", title="x.txt", app="A")


def test_ten_most_spoken_languages_are_offered():
    codes = [lang.code for lang in all_languages()]
    assert codes[:10] == ["en", "zh-Hans", "hi", "es", "fr", "ar", "bn", "pt", "ru", "ur"]
    assert all(lang.fonts for lang in all_languages())


def test_rtl_languages_flagged():
    rtl = {lang.code for lang in all_languages() if lang.rtl}
    assert rtl == {"ar", "ur"}


# ---------------------------------------------------------------------------
# resources / icon
# ---------------------------------------------------------------------------
def test_application_icon_has_every_size():
    icon = resources.application_icon()
    assert not icon.isNull()
    sizes = {(s.width(), s.height()) for s in icon.availableSizes()}
    for expected in (16, 32, 48, 256, 512):
        assert (expected, expected) in sizes


def test_icon_assets_are_bundled():
    for name in ("app.svg", "app.ico", "app.png", "app-256.png"):
        assert (resources.ICONS_DIR / name).exists(), name


def test_bundled_arabic_font_exists():
    assert resources.BUNDLED_FONT.exists()
    assert resources.BUNDLED_FONT.suffix == ".ttf"


# ---------------------------------------------------------------------------
# dialogs
# ---------------------------------------------------------------------------
def test_settings_dialog_round_trip(qapp):

    from mishkah.widgets.settings_dialog import SettingsDialog

    settings = Settings(path=Path("/tmp/does-not-exist.json"))
    dialog = SettingsDialog(settings)
    dialog.cmb_language.setCurrentIndex(dialog.cmb_language.findData("ar"))
    dialog.cmb_theme.setCurrentIndex(dialog.cmb_theme.findData("dark"))
    dialog.cmb_direction.setCurrentIndex(dialog.cmb_direction.findData("rtl"))
    dialog.spin_font_size.setValue(18)
    dialog.spin_tab.setValue(8)
    dialog.chk_word_wrap.setChecked(False)
    dialog.chk_line_numbers.setChecked(True)

    old = dialog.apply_to(settings)
    dialog.close()

    assert old["ui_language"] == "en"
    assert settings.ui_language == "ar"
    assert settings.theme == "dark"
    assert settings.default_direction == "rtl"
    assert settings.font_size == 18
    assert settings.tab_width == 8
    assert settings.word_wrap is False
    assert settings.line_numbers is True


def test_settings_dialog_has_ok_and_cancel(qapp):
    from PySide6.QtWidgets import QDialogButtonBox

    from mishkah.widgets.settings_dialog import SettingsDialog

    dialog = SettingsDialog(Settings())
    box = dialog.findChild(QDialogButtonBox)
    assert box is not None
    assert box.button(QDialogButtonBox.StandardButton.Ok) is not None
    assert box.button(QDialogButtonBox.StandardButton.Cancel) is not None
    dialog.close()


def test_progress_dialog_cancel_emits_once(qapp):
    from mishkah.widgets.progress_dialog import ProgressDialog

    dialog = ProgressDialog("loading")
    hits = []
    dialog.cancelled.connect(lambda: hits.append(1))
    dialog.report(10, 100)
    dialog.report_bytes(2048, 8192)
    dialog._on_cancel()
    dialog._on_cancel()
    dialog.close()
    assert hits == [1]
    assert dialog.is_cancelled()


def test_progress_dialog_counts_bytes(qapp):
    from mishkah.widgets.progress_dialog import ProgressDialog

    dialog = ProgressDialog("loading")
    dialog.report_bytes(1024 * 1024, 4 * 1024 * 1024)
    assert dialog.value() == 1024 * 1024
    assert dialog.maximum() == 4 * 1024 * 1024
    dialog.close()


def test_direction_chip_icon(qapp):
    """The chip must never show an ambiguous glyph such as "@"."""
    from mishkah.core.text_direction import AUTO, LTR, RTL
    from mishkah.views import status_bar_widget

    widget = status_bar_widget.StatusBarWidget()
    widget.set_direction(AUTO, resolved=LTR)
    assert "@" not in widget._direction.text()
    widget.set_direction(RTL)
    assert widget._direction.text() == f"{status_bar_widget._DIRECTION_ICONS[RTL]} RTL"
    widget.set_direction(AUTO, resolved=RTL)
    assert "RTL" in widget._direction.text()
