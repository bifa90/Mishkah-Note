"""Language-aware editor typography and persistent, universal font overrides."""

from __future__ import annotations

import pytest

from mishkah.core.languages import all_languages, editor_font_families
from mishkah.core.settings import Settings

PREFERRED = {
    "ar": "IBM Plex Sans Arabic",
    "en": "Noto Sans", "es": "Noto Sans", "fr": "Noto Sans",
    "pt": "Noto Sans", "ru": "Noto Sans",
    "zh-Hans": "Noto Sans CJK SC",
    "hi": "Noto Sans Devanagari",
    "bn": "Noto Sans Bengali",
    "ur": "Noto Nastaliq Urdu",
}


@pytest.mark.parametrize("code,preferred", PREFERRED.items())
def test_automatic_reading_face(code, preferred):
    settings = Settings(ui_language=code)
    families = editor_font_families(settings.ui_language, settings.font_family)
    assert families[0] == preferred
    assert "IBM Plex Sans Arabic" in families
    assert len(families) == len(set(families))


@pytest.mark.parametrize("code", PREFERRED)
def test_custom_font_is_first_and_persists_for_every_language(code, tmp_path):
    settings = Settings(ui_language=code, font_family="DejaVu Sans Mono")
    settings.save(tmp_path / "settings.json")
    loaded = Settings.load(tmp_path / "settings.json")
    families = editor_font_families(loaded.ui_language, loaded.font_family)
    assert families[0] == "DejaVu Sans Mono"
    assert PREFERRED[code] in families
    loaded.font_family = ""
    assert editor_font_families(code, loaded.font_family)[0] == PREFERRED[code]


def test_language_regions_and_fallback():
    assert editor_font_families("ar-YE")[0] == PREFERRED["ar"]
    assert editor_font_families(None)[0] == PREFERRED["en"]
    assert editor_font_families("unknown")[0] == PREFERRED["en"]
    assert set(PREFERRED) == {lang.code for lang in all_languages()}


def test_bundled_regular_font_and_license():
    from mishkah.core.resources import BUNDLED_FONT

    assert BUNDLED_FONT.name == "IBMPlexSansArabic-Regular.ttf"
    assert BUNDLED_FONT.read_bytes()[:4] == b"\x00\x01\x00\x00"
    assert "SIL OPEN FONT LICENSE" in (BUNDLED_FONT.parent / "OFL.txt").read_text()


def test_arabic_font_resolves_to_bundled_family(qapp):
    from PySide6.QtGui import QFont, QFontInfo

    from mishkah.app import install_bundled_fonts

    families = install_bundled_fonts()
    assert "IBM Plex Sans Arabic" in families
    font = QFont()
    font.setFamilies(editor_font_families("ar"))
    font.setPointSize(13)
    font.setWeight(QFont.Weight.Normal)
    assert QFontInfo(font).family() == "IBM Plex Sans Arabic"


@pytest.mark.parametrize("code", PREFERRED)
def test_font_picker_supports_manual_and_automatic_for_every_language(qapp, code):
    from PySide6.QtGui import QFontDatabase

    from mishkah.core import i18n
    from mishkah.widgets.settings_dialog import SettingsDialog

    i18n.set_language(code)
    dialog = SettingsDialog(Settings(ui_language=code))
    try:
        assert dialog.values()["font_family"] == ""
        # Pick any actual installed face, distinct from the automatic entry.
        assert dialog.cmb_font.count() > 1
        family = next(f for f in QFontDatabase.families()
                      if dialog.cmb_font.findText(f) > 0)
        dialog.cmb_font.setCurrentIndex(dialog.cmb_font.findText(family))
        assert dialog.values()["font_family"] == family
        dialog._load(Settings(ui_language=code, font_family=family))
        assert dialog.cmb_font.currentFont().family() == family
        dialog.cmb_font.setCurrentIndex(0)
        assert dialog.values()["font_family"] == ""
    finally:
        dialog.close()
        i18n.set_language("en")
