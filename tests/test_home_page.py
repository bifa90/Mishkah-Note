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
