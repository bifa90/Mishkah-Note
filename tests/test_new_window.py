"""File ▸ New window opens a real window (CD-29 / B2)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.gui


def _window(tmp_path, name="settings.json", owns_session=True):
    from PySide6.QtWidgets import QApplication

    from mishkah.app import build_window
    from mishkah.core.settings import Settings
    from mishkah.services.file_service import FileService

    settings = Settings(path=tmp_path / name, restore_session=False)
    window = build_window(QApplication.instance(), settings, FileService(), [],
                          restore=False, owns_session=owns_session)
    return window, settings


def test_a_new_window_starts_on_the_welcome_page(qapp, tmp_path):
    window, _ = _window(tmp_path)
    try:
        assert window.tab_count() == 1
        assert window.home_page() is not None
        assert window.current_editor() is None
    finally:
        window.close()


def test_the_item_calls_the_factory_instead_of_opening_a_tab(qapp, tmp_path):
    window, settings = _window(tmp_path)
    windows = []
    try:
        def factory():
            second, _ = _window(tmp_path, "second.json", owns_session=False)
            second.show()
            windows.append(second)
            return second

        window.new_window_factory = factory
        before = window.tab_count()
        window.act_new_window.trigger()

        assert len(windows) == 1, "a window was opened"
        assert window.tab_count() == before, "and no tab was opened here"
        assert windows[0] is not window
    finally:
        for created in windows:
            created.close()
        window.close()


def test_the_two_windows_have_independent_tabs(qapp, tmp_path):
    first, settings = _window(tmp_path)
    created = []
    try:
        def factory():
            second, _ = _window(tmp_path, "second.json", owns_session=False)
            second.show()
            created.append(second)
            return second

        first.new_window_factory = factory
        first.act_new_window.trigger()
        second = created[0]
        assert second.property("controller") is not first.property("controller")

        controller_second = second.property("controller")
        controller_second.new_document()
        assert second.tabs.count() == 2
        assert first.tabs.count() == 1, "the first window did not change"
    finally:
        for window in created:
            window.close()
        first.close()


def test_only_one_window_owns_the_session(qapp, tmp_path):
    first, settings = _window(tmp_path)
    second, _ = _window(tmp_path, "second.json", owns_session=False)
    try:
        primary = first.property("controller")
        other = second.property("controller")
        assert primary.owns_session is True
        assert other.owns_session is False

        settings.open_files = ["/tmp/from-the-first-window.txt"]
        other.save_session()
        assert settings.open_files == ["/tmp/from-the-first-window.txt"]

        controller_file = tmp_path / "mine.txt"
        controller_file.write_text("x", encoding="utf-8")
        primary.open_path(controller_file)
        # The loader is asynchronous; give it a turn and check the list.
        from PySide6.QtTest import QTest

        for _ in range(40):
            QTest.qWait(25)
            if primary._docs and any(d.path for d in primary._docs.values()):
                break
        primary.save_session()
        assert settings.open_files == [str(controller_file)]
    finally:
        second.close()
        first.close()


def test_closing_one_window_keeps_the_other(qapp, tmp_path):
    first, _ = _window(tmp_path)
    second, _ = _window(tmp_path, "second.json", owns_session=False)
    try:
        first.show()
        second.show()
        first.close()
        assert not first.isVisible()
        assert second.isVisible(), "the other window stays open"
    finally:
        second.close()
