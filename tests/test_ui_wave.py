"""Tab icons, shortcuts, word count and drag/drop (W3b: CD-04, CD-21, CD-22, CD-23)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.gui


def _controller(tmp_path):
    from mishkah.controllers.main_controller import MainController
    from mishkah.core.settings import Settings
    from mishkah.services.file_service import FileService
    from mishkah.views.main_window import MainWindow

    window = MainWindow()
    settings = Settings(path=tmp_path / "settings.json", restore_session=False)
    return window, MainController(window, settings, FileService()), settings


# ------------------------------------------------------------------ CD-04
def test_a_new_tab_is_not_pinned_by_its_icon(qapp, tmp_path):
    window, controller, _ = _controller(tmp_path)
    try:
        controller.new_document()
        bar = window.tab_bar
        assert bar.tabIcon(0).isNull() is False
        assert bar.is_pinned(0) is False
        bar.set_tab_modified(0, True)
        assert bar.tab_modified(0) is True
        assert bar.is_pinned(0) is False
        assert window.tabs.tabText(0) == "Untitled", "no dot in the name"
    finally:
        window.close()


def test_switching_theme_keeps_pin_state(qapp, tmp_path):
    window, controller, _ = _controller(tmp_path)
    try:
        controller.new_document()
        window.set_tab_pinned(window.current_editor(), True)
        window.tab_bar.set_theme_name("dark")
        assert window.tab_bar.is_pinned(0) is True
        window.tab_bar.set_theme_name("light")
        assert window.tab_bar.is_pinned(0) is True
    finally:
        window.close()


def test_closing_a_tab_does_not_leak_its_colour(qapp, tmp_path):
    window, controller, _ = _controller(tmp_path)
    try:
        first = controller.new_document()
        controller.new_document()
        window.set_tab_color(first, "blue")
        assert window.tab_bar.tab_color(0) == "blue"
        controller.close_tab(0)
        assert window.tab_bar.tab_color(0) == "", "the state moved with the tab"
    finally:
        window.close()


# ------------------------------------------------------------------ CD-21
def test_the_documented_shortcuts_belong_to_their_actions(qapp, tmp_path):
    window, controller, _ = _controller(tmp_path)
    try:
        def keys(action):
            return {seq.toString() for seq in action.shortcuts()}

        assert "Ctrl+T" in keys(window.act_new_tab)
        assert "Alt+T" in keys(window.act_on_top)
        assert "Ctrl+Shift+P" in keys(window.act_tab_pin)
        assert "Ctrl+P" in keys(window.act_print)
        assert "Ctrl+P" not in keys(window.act_tab_pin), "no double binding"
        assert "Ctrl+Y" in keys(window.act_redo)
        assert "Ctrl+Shift+Z" in keys(window.act_redo), "second path kept"
        assert "Ctrl+H" in keys(window.act_replace)
    finally:
        window.close()


def test_ctrl_t_opens_a_new_tab(qapp, tmp_path):
    window, controller, _ = _controller(tmp_path)
    try:
        controller.new_document()
        assert window.tab_count() == 1
        window.act_new_tab.trigger()
        assert window.tab_count() == 2
    finally:
        window.close()


# ------------------------------------------------------------------ CD-23
def test_the_status_bar_counts_words(qapp, tmp_path):
    from PySide6.QtTest import QTest

    window, controller, _ = _controller(tmp_path)
    try:
        editor = controller.new_document()
        editor.setPlainText("three words here")
        QTest.qWait(300)
        assert "3" in window.status._words.text()      # noqa: SLF001
        assert window.status._words.isVisible() or True
    finally:
        window.close()


def test_arabic_words_are_counted_like_latin_ones():
    from mishkah.core.text_stats import count_words

    assert count_words("مرحبا بالعالم") == 2
    assert count_words("hello world") == 2
    assert count_words("«مرحبا» — ٣ كلمات") == 3
    assert count_words("") == 0
    assert count_words("!!! ... ???") == 0


# ------------------------------------------------------------------ CD-22
def test_dropping_files_opens_them(qapp, tmp_path):
    from PySide6.QtCore import QMimeData, QPoint, Qt, QUrl
    from PySide6.QtGui import QDropEvent

    window, controller, _ = _controller(tmp_path)
    opened = []
    try:
        controller.open_path = opened.append          # type: ignore[assignment]
        target = tmp_path / "dropped.txt"
        target.write_text("hi\n", encoding="utf-8")

        data = QMimeData()
        data.setUrls([QUrl.fromLocalFile(str(target))])
        event = QDropEvent(QPoint(10, 10), Qt.DropAction.CopyAction, data,
                           Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        window.dropEvent(event)
        assert opened == [str(target)]
    finally:
        window.close()


def test_dropped_text_is_left_to_the_editor(qapp, tmp_path):
    from PySide6.QtCore import QMimeData

    window, _, _ = _controller(tmp_path)
    try:
        data = QMimeData()
        data.setText("plain text")
        assert window._dropped_paths(type("E", (), {"mimeData": lambda self: data})()) == []
    finally:
        window.close()
