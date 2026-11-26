"""What the owner reported after G3b closed: four small things, one decision.

* **Settings sat at the bottom.**  Every page started with ``addStretch(1)``, so
  the layout pushed its whole content down; the first control only showed up at
  the bottom of the window.
* **"المؤلف" in About.**  The box credits who *built* the program — "Developer"
  — not the author of the text someone is writing.
* **The colouring language's name stayed in the previous language.**  The status
  bar stored the finished, translated string and re-rendered it verbatim after a
  switch; it now stores the *code* and re-names it (same family as G3b #9).
* **Settings icons were white on a white background.**  They came from the Qt
  style, coloured for the desktop's palette rather than for the stylesheet the
  window is actually painted with.

And the decision this file also guards: the mixed-direction item (G3b #5) is
**deferred to 1.0.03** with the core update, archived in
``docs/DEFERRED_1.0.03.ar.md`` — not quietly forgotten.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.gui

ROOT = Path(__file__).resolve().parent.parent


def _settings_dialog(qapp):
    from mishkah.core.settings import Settings
    from mishkah.widgets.settings_dialog import SettingsDialog

    dialog = SettingsDialog(Settings(restore_session=False))
    dialog.resize(760, 560)
    dialog.show()
    qapp.processEvents()
    return dialog


# ------------------------------------------------- settings start at the top
def test_every_settings_page_starts_at_its_top_edge(qapp):
    """G3b follow-up: the controls were pushed to the bottom of the page."""
    dialog = _settings_dialog(qapp)
    try:
        for page in dialog._pages:
            layout = page.layout()
            assert layout.itemAt(layout.count() - 1).spacerItem() is not None, (
                "the trailing stretch is what keeps the content up")
            first = layout.itemAt(0)
            assert first.spacerItem() is None, "a page starts with a spacer again"
            assert first.geometry().top() < 48, (
                f"the first row sits at y={first.geometry().top()}, not near the top")
    finally:
        dialog.close()


def test_settings_pages_are_top_aligned_not_bottom_aligned(qapp):
    """A page whose content is shorter than the view keeps its content up."""
    dialog = _settings_dialog(qapp)
    try:
        page = dialog._pages[0]
        first = page.layout().itemAt(0)
        assert first.geometry().top() < page.height() / 2
    finally:
        dialog.close()


# ------------------------------------------------------ settings icons, inked
def _ink_range(pixmap):
    """(darkest, lightest) lightness among the drawn pixels of a pixmap."""
    image = pixmap.toImage()
    values = []
    for x in range(0, image.width(), 1):
        for y in range(0, image.height(), 1):
            colour = image.pixelColor(x, y)
            if colour.alpha() > 120:
                values.append(colour.lightness())
    assert values, "the icon drew nothing at all"
    return min(values), max(values)


def test_settings_icons_are_inked_for_the_chrome(qapp):
    """Light chrome → dark glyphs; dark chrome → light glyphs.  Never white on white."""
    from mishkah.widgets.icons import CATEGORY_KEYS, category_icon

    for key in CATEGORY_KEYS:
        light = category_icon(key, dark=False)
        dark = category_icon(key, dark=True)
        assert not light.isNull() and not dark.isNull(), key

        darkest, _ = _ink_range(light.pixmap(18, 18))
        _, lightest = _ink_range(dark.pixmap(18, 18))
        assert darkest < 140, f"{key}: light chrome needs dark ink, got {darkest}"
        assert lightest > 170, f"{key}: dark chrome needs light ink, got {lightest}"


def test_tinted_icon_takes_the_colour_it_is_given(qapp):
    """The style's glyph keeps its shape and loses its system colour."""
    from mishkah.widgets.icons import document_icon, tinted_icon

    source = document_icon("#FFFFFF", 16)
    tinted = tinted_icon(source, "#123456", 16)
    assert not tinted.isNull()
    image = tinted.pixmap(16, 16).toImage()
    painted = [image.pixelColor(x, y)
               for x in range(image.width()) for y in range(image.height())
               if image.pixelColor(x, y).alpha() > 200]
    assert painted, "tinting erased the icon"
    # ±4, not exact equality: a half-transparent edge pixel is stored
    # premultiplied and cannot come back with the same channels.
    expected = (0x12, 0x34, 0x56)
    for colour in painted:
        for channel, wanted in zip((colour.red(), colour.green(), colour.blue()),
                                   expected):
            assert abs(channel - wanted) <= 4, (
                f"tinted pixel {colour.name()} kept its old colour")


def test_the_autosave_icon_is_inked_too(qapp, tmp_path):
    from mishkah.controllers.main_controller import MainController
    from mishkah.core.settings import Settings
    from mishkah.services.file_service import FileService
    from mishkah.views.main_window import MainWindow

    window = MainWindow()
    try:
        MainController(window, Settings(path=tmp_path / "s.json",
                                        restore_session=False), FileService())
        image = window._autosave_icon().pixmap(16, 16).toImage()
        painted = [image.pixelColor(x, y) for x in range(image.width())
                   for y in range(image.height())
                   if image.pixelColor(x, y).alpha() > 120]
        assert painted, "the autosave button drew nothing"
        # Inked for the chrome, not white-on-white from the system palette.
        assert min(colour.lightness() for colour in painted) < 200
    finally:
        window.close()


# ------------------------------- the colouring language follows the interface
def test_the_language_segment_is_renamed_on_a_language_switch(qapp):
    """Reported: the grammar's name stayed Arabic after switching to English."""
    from mishkah.core import i18n
    from mishkah.core.syntax import display_name
    from mishkah.views.status_bar_widget import StatusBarWidget

    bar = StatusBarWidget()
    try:
        i18n.set_language("ar")
        bar.set_language_code("python")
        assert bar.language_text() == display_name("python", "ar")
        assert bar.language_text() != display_name("python", "en")

        i18n.set_language("en")
        bar.retranslate()
        assert bar.language_text() == "Python", bar.language_text()

        i18n.set_language("ar")
        bar.retranslate()
        assert bar.language_text() == display_name("python", "ar")
    finally:
        i18n.set_language("en")
        bar.deleteLater()


def test_plain_text_hides_the_language_segment(qapp):
    from mishkah.core import i18n
    from mishkah.views.status_bar_widget import StatusBarWidget

    bar = StatusBarWidget()
    try:
        bar.set_language_code("python")
        assert bar.language_text()
        bar.set_language_code("")
        assert bar.language_text() == ""
        i18n.set_language("ur")
        bar.retranslate()
        assert bar.language_text() == ""
    finally:
        i18n.set_language("en")
        bar.deleteLater()


# ---------------------------------------------------- About says "Developer"
LANGUAGES = ("en", "zh-Hans", "hi", "es", "fr", "ar", "bn", "pt", "ru", "ur")


def test_about_credits_a_developer_not_an_author(qapp):
    """"Author" read as the author of the text; every language had to change."""
    from mishkah.core import i18n

    previous = i18n.current_language()
    try:
        translated = {}
        for code in LANGUAGES:
            i18n.set_language(code)
            translated[code] = i18n.tr("about.author")
            assert translated[code].strip(), code
        assert translated["en"] == "Developer"
        assert translated["ar"] == "المطور"
        assert "المؤلف" not in translated.values()
        assert "Author" not in translated.values()
    finally:
        i18n.set_language(previous)


def test_the_about_box_shows_the_new_label(qapp):
    from mishkah.core import i18n
    from mishkah.widgets.about_dialog import about_html

    previous = i18n.current_language()
    try:
        i18n.set_language("ar")
        assert i18n.tr("about.author") in about_html()
        i18n.set_language("en")
        assert "Developer" in about_html()
    finally:
        i18n.set_language(previous)
