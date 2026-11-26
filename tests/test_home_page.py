"""The welcome page (CD-06): a tab that is not a document."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.gui


def _controller(tmp_path, **overrides):
    from mishkah.controllers.main_controller import MainController
    from mishkah.core.settings import Settings
    from mishkah.services.file_service import FileService
    from mishkah.views.main_window import MainWindow

    window = MainWindow()
    settings = Settings(path=tmp_path / "settings.json", restore_session=False)
    for key, value in overrides.items():
        setattr(settings, key, value)
    return window, MainController(window, settings, FileService()), settings


def test_the_welcome_page_appears_when_the_last_tab_closes(qapp, tmp_path):
    from mishkah.core.i18n import tr

    window, controller, _ = _controller(tmp_path)
    try:
        editor = controller.new_document()
        controller.close_tab(window.index_of(editor))

        page = window.home_page()
        assert page is not None, "the page replaces the blank document"
        assert window.tabs.count() == 1
        assert window.tabs.tabText(0) == tr("tab.home")
        assert window.current_editor() is None, "it is not a document"
    finally:
        window.close()


def test_the_page_offers_the_two_first_steps(qapp, tmp_path):
    from mishkah.core.i18n import tr

    window, controller, _ = _controller(tmp_path)
    try:
        page = controller.show_home()
        assert page.btn_new.text() == tr("home.new")
        assert page.btn_open.text() == tr("home.open")
        assert page.btn_settings.text() == tr("home.settings")
        assert page.btn_help.text() == tr("home.help")
    finally:
        window.close()


def test_the_lone_page_cannot_be_closed(qapp, tmp_path):
    window, controller, _ = _controller(tmp_path)
    try:
        controller.show_home()
        controller.close_tab(0)
        assert window.tabs.count() == 1
        assert window.home_page() is not None, "no window without tabs"
    finally:
        window.close()


def test_the_page_steps_aside_when_a_document_is_created(qapp, tmp_path):
    window, controller, _ = _controller(tmp_path)
    try:
        page = controller.show_home()
        page.btn_new.click()

        assert window.home_page() is None
        assert window.tabs.count() == 1
        assert window.current_editor() is not None
    finally:
        window.close()


def test_the_page_steps_aside_when_a_recent_file_is_chosen(qapp, tmp_path):
    window, controller, _ = _controller(tmp_path)
    try:
        target = tmp_path / "note.txt"
        target.write_text("hello", encoding="utf-8")
        page = controller.show_home()
        page.set_recent_files([str(target)])
        assert page.recent_paths() == [str(target)]

        page.recent_requested.emit(str(target))
        assert window.home_page() is None
        assert window.tabs.count() == 1
        assert window.current_editor() is not None
    finally:
        window.close()


def test_cd09_an_opened_file_never_replaces_the_page(qapp, tmp_path):
    """CD-09: the page is a tab, so the file gets its own and sits beside."""
    window, controller, _ = _controller(tmp_path)
    try:
        controller.show_home()
        target = tmp_path / "other.txt"
        target.write_text("x", encoding="utf-8")
        controller.open_path(target)

        assert window.tabs.count() == 2, "the page is not replaced"
        assert window.home_page() is not None
    finally:
        window.close()


def test_the_quit_policy_ends_instead_of_welcoming(qapp, tmp_path):
    window, controller, _ = _controller(tmp_path, last_tab_action="quit")
    try:
        editor = controller.new_document()
        window.show()
        controller.close_tab(window.index_of(editor))
        assert window.home_page() is None
        assert not window.isVisible(), "the window went away"
    finally:
        window.close()


def test_restore_is_offered_only_when_a_session_exists(qapp, tmp_path):
    window, controller, settings = _controller(tmp_path)
    try:
        gone = tmp_path / "gone.txt"
        page = controller.show_home()
        settings.open_files = [str(gone)]
        controller._refresh_home(page)          # noqa: SLF001
        assert page.btn_restore.isHidden(), "a stale path is not a session"

        real = tmp_path / "real.txt"
        real.write_text("y", encoding="utf-8")
        settings.open_files = [str(real)]
        controller._refresh_home(page)          # noqa: SLF001
        assert not page.btn_restore.isHidden()
    finally:
        window.close()


def test_the_recent_list_hides_vanished_files(qapp, tmp_path):
    window, controller, _ = _controller(tmp_path)
    try:
        page = controller.show_home()
        keep = tmp_path / "keep.txt"
        keep.write_text("k", encoding="utf-8")
        page.set_recent_files([str(tmp_path / "missing.txt"), str(keep)])

        assert page.recent_paths() == [str(keep)]
        assert not page.list_recent.isHidden()
        assert page.lbl_empty.isHidden()
    finally:
        window.close()


def test_the_page_clears_the_banner_of_the_previous_tab(qapp, tmp_path):
    from mishkah.core.i18n import tr

    window, controller, _ = _controller(tmp_path)
    try:
        editor = controller.new_document()
        window.show_banner(tr("banner.readonly"))
        assert not window.banner.isHidden()

        controller.close_tab(window.index_of(editor))
        assert window.banner.isHidden(), "nothing of the old tab may remain"
        assert window.windowTitle() == tr("app.name")
    finally:
        window.close()


def test_opening_a_new_window_without_a_factory_falls_back_to_a_tab(qapp, tmp_path):
    """B2: the menu item is never dead, even outside the real application."""
    window, controller, _ = _controller(tmp_path)
    try:
        controller.new_document()
        before = window.tabs.count()
        window.act_new_window.trigger()
        assert window.tabs.count() == before + 1
    finally:
        window.close()


def test_opening_a_new_window_uses_the_factory(qapp, tmp_path):
    window, controller, _ = _controller(tmp_path)
    calls = []
    try:
        window.new_window_factory = lambda: calls.append(True)
        window.act_new_window.trigger()
        assert calls == [True], "the application decides what a window is"
    finally:
        window.close()


# ---------------------------------------------------------------------------
# round 4: the brand block and the reading edge
# ---------------------------------------------------------------------------
BRAND_LANGS = ("en", "ar", "ur", "es", "ru", "zh-Hans", "hi", "bn", "fr", "pt")


def test_the_brand_is_logo_then_arabic_name_then_english_name_then_version(qapp, tmp_path):
    """The four brand lines are never translated and never reordered."""
    from mishkah import APP_NAME, APP_NAME_AR, APP_VERSION
    from mishkah.core import i18n
    from mishkah.core.i18n import tr

    window, controller, _ = _controller(tmp_path)
    try:
        page = controller.show_home()
        for code in BRAND_LANGS:
            i18n.set_language(code)
            page.retranslate()

            logo, name_ar, name_en, version = page.brand()
            assert not logo.pixmap().isNull(), f"{code}: the mark must be there"
            assert name_ar.text() == APP_NAME_AR, f"{code}: the Arabic name is fixed"
            assert name_en.text() == APP_NAME, f"{code}: the English name is fixed"
            assert version.text() == tr("about.version", version=APP_VERSION)
            assert APP_VERSION in version.text()
    finally:
        i18n.set_language("en")
        window.close()


def test_the_brand_stack_is_ordered_on_screen(qapp, tmp_path):
    """Order on the glass, not just in the list: mark, Arabic, English, version."""
    window, controller, _ = _controller(tmp_path)
    try:
        page = controller.show_home()
        page.resize(760, 620)
        page.show()
        qapp.processEvents()

        tops = [label.mapTo(page, label.rect().topLeft()).y() for label in page.brand()]
        assert tops == sorted(tops), f"out of order: {tops}"
        assert tops[0] < tops[1] < tops[2] < tops[3]
    finally:
        window.close()


def test_the_page_itself_still_translates(qapp, tmp_path):
    """The brand is fixed; the invitation around it is not."""
    from mishkah.core import i18n
    from mishkah.core.i18n import tr

    window, controller, _ = _controller(tmp_path)
    try:
        page = controller.show_home()
        i18n.set_language("en")
        page.retranslate()
        english = page.lbl_tagline.text()

        i18n.set_language("ar")
        page.retranslate()
        assert page.lbl_tagline.text() == tr("home.tagline")
        assert page.lbl_tagline.text() != english, "an untranslated page is a bug"
        assert page.btn_new.text() == tr("home.new")
        assert page.lbl_recent.text() == tr("home.recent")
    finally:
        i18n.set_language("en")
        window.close()


def _ink_columns(label):
    """Darkness per column of a rendered label — a side, not a flag."""
    from PySide6.QtGui import QImage

    image = label.grab().toImage().convertToFormat(QImage.Format.Format_Grayscale8)
    width, height = image.width(), image.height()
    columns = []
    for x in range(width):
        dark = sum(1 for y in range(0, height, 2)
                   if image.pixelColor(x, y).lightness() < 200)
        columns.append(dark)
    return columns


def _ink_side(label):
    columns = _ink_columns(label)
    third = max(1, len(columns) // 3)
    left, right = sum(columns[:third]), sum(columns[-third:])
    return left, right


def test_the_title_sits_on_the_reading_edge_of_the_window(qapp, tmp_path):
    """Defect 3: the name must move *with* the buttons, to the right in Arabic.

    A flag check is not enough — ``AlignRight`` in a right-to-left widget is
    mirrored by Qt and lands on the physical left.  So this reads the pixels.
    """
    from PySide6.QtCore import Qt

    window, controller, _ = _controller(tmp_path)
    try:
        page = controller.show_home()
        page.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        page.resize(760, 620)
        page.show()
        qapp.processEvents()

        left, right = _ink_side(page.lbl_name_ar)
        assert left + right, "the name did not render, so nothing was measured"
        assert right > left * 3, f"right-to-left ink {left} vs {right}: not at the right edge"

        page.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        qapp.processEvents()
        left, right = _ink_side(page.lbl_name_ar)
        assert left > right * 3, f"left-to-right ink {left} vs {right}: not at the left edge"
    finally:
        window.close()


def test_the_english_name_follows_the_arabic_name_to_the_same_edge(qapp, tmp_path):
    """One edge for the whole block — the bug left the English name behind."""
    from PySide6.QtCore import Qt

    window, controller, _ = _controller(tmp_path)
    try:
        page = controller.show_home()
        page.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        page.resize(760, 620)
        page.show()
        qapp.processEvents()

        for label in (page.lbl_name_en, page.lbl_version, page.lbl_recent,
                      page.lbl_tagline, page.lbl_logo):
            left, right = _ink_side(label)
            assert left + right, "nothing rendered"
            assert right > left, f"{label.objectName()} kept to the left"
    finally:
        window.close()


def test_the_urdu_chrome_uses_the_interface_face_not_nastaliq(qapp, tmp_path):
    """Round 4: Nastaliq clips in a 12 px menu, so the chrome asks for a sans."""
    from PySide6.QtGui import QFontInfo
    from PySide6.QtWidgets import QMenu

    from mishkah.app import install_bundled_fonts

    install_bundled_fonts()          # what the real entry point does first
    window, controller, _ = _controller(tmp_path, ui_language="ur")
    try:
        font = window.ui_font()
        assert font.families()[0] == "Noto Sans Arabic"
        assert QFontInfo(font).family() == "Noto Sans Arabic"
        page = controller.show_home()
        assert QFontInfo(page.font()).family() == "Noto Sans Arabic"
        for menu in window.menuBar().findChildren(QMenu):
            assert menu.font().families()[0] == "Noto Sans Arabic"
    finally:
        window.close()


def test_the_arabic_chrome_uses_ibm_plex_and_keeps_it_on_the_page(qapp, tmp_path):
    from PySide6.QtGui import QFontInfo

    from mishkah.app import install_bundled_fonts

    install_bundled_fonts()
    window, controller, _ = _controller(tmp_path, ui_language="ar")
    try:
        font = window.ui_font()
        assert font.families()[0] == "IBM Plex Sans Arabic"
        assert QFontInfo(font).family() == "IBM Plex Sans Arabic"
        page = controller.show_home()
        assert QFontInfo(page.font()).family() == "IBM Plex Sans Arabic"
    finally:
        window.close()


def test_recent_files_sit_opposite_the_brand_in_rtl_and_ltr(qapp, tmp_path):
    """Arabic/Urdu: brand right, recent files left; English/LTR: the opposite."""
    from PySide6.QtCore import Qt

    window, controller, _ = _controller(tmp_path)
    try:
        page = controller.show_home()
        page.resize(960, 620)
        page.show()

        page.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        qapp.processEvents()
        brand_x = page.brand_pane.mapTo(page, page.brand_pane.rect().center()).x()
        recent_x = page.recent_pane.mapTo(page, page.recent_pane.rect().center()).x()
        assert brand_x > recent_x, f"RTL: brand ({brand_x}) should be right of recent ({recent_x})"

        page.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        qapp.processEvents()
        brand_x = page.brand_pane.mapTo(page, page.brand_pane.rect().center()).x()
        recent_x = page.recent_pane.mapTo(page, page.recent_pane.rect().center()).x()
        assert brand_x < recent_x, f"LTR: brand ({brand_x}) should be left of recent ({recent_x})"
    finally:
        window.close()


def test_urdu_dropdown_menus_are_compact_and_fit_on_a_laptop_screen(qapp, tmp_path):
    """Per-language dropdown menu sizing and density stay balanced and on screen."""
    from PySide6.QtWidgets import QMenu

    from mishkah.app import apply_theme, install_bundled_fonts
    from mishkah.core import i18n

    previous_qss = qapp.styleSheet()
    previous_theme = qapp.property("mishkah_theme")
    previous_lang = i18n.current_language()
    install_bundled_fonts()
    apply_theme(qapp, "light")
    window, controller, _ = _controller(tmp_path, ui_language="ur")
    try:
        # Urdu: tight frame, ~10.5-11.5 pt font (~10-15% above the 9.5 pt floor)
        for menu in window.menuBar().findChildren(QMenu):
            assert menu.property("menuDensity") == "tight"
            assert 10.5 <= menu.font().pointSizeF() <= 11.5
        view_height = window.menu_view.sizeHint().height()
        assert view_height < 640, f"Urdu View menu too tall for a laptop screen: {view_height}px"

        # Arabic: keep font size untouched (== ui_font), tighten padding only
        controller.set_ui_language("ar")
        ar_ui_pt = window.ui_font().pointSizeF()
        for menu in window.menuBar().findChildren(QMenu):
            assert menu.property("menuDensity") == "snug"
            assert menu.font().pointSizeF() == ar_ui_pt

        # Hindi & Bengali: untouched font size and default padding
        for code in ("hi", "bn"):
            controller.set_ui_language(code)
            ui_pt = window.ui_font().pointSizeF()
            for menu in window.menuBar().findChildren(QMenu):
                assert (menu.property("menuDensity") or "") == ""
                assert menu.font().pointSizeF() == ui_pt

        # Remaining languages: slightly smaller font and tighter padding
        for code in ("en", "zh-Hans", "es", "fr", "pt", "ru"):
            controller.set_ui_language(code)
            ui_pt = window.ui_font().pointSizeF()
            for menu in window.menuBar().findChildren(QMenu):
                assert menu.property("menuDensity") == "compact"
                assert menu.font().pointSizeF() < ui_pt
    finally:
        window.close()
        qapp.setStyleSheet(previous_qss)
        qapp.setProperty("mishkah_theme", previous_theme)
        i18n.set_language(previous_lang)
