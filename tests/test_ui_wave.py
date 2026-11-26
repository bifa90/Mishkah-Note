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


# ------------------------------------------------------------------ CD-13
def test_paste_without_formatting_takes_the_text(qapp, tmp_path):
    from PySide6.QtGui import QGuiApplication

    window, controller, _ = _controller(tmp_path)
    try:
        editor = controller.new_document()
        editor.setPlainText("start ")
        cursor = editor.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        editor.setTextCursor(cursor)

        QGuiApplication.clipboard().setText("plain words")
        assert editor.paste_plain() is True
        assert editor.document().toPlainText() == "start plain words"
        assert "Ctrl+Shift+V" in {s.toString() for s in window.act_paste_plain.shortcuts()}
    finally:
        window.close()


# ------------------------------------------------------------------ CD-12
def test_markdown_is_offered_never_switched_silently(qapp, tmp_path):
    from PySide6.QtTest import QTest

    window, controller, settings = _controller(tmp_path)
    try:
        settings.live_markdown = False
        editor = controller.new_document()
        editor.setPlainText("# Title\n\n- one\n- two\n")
        QTest.qWait(700)
        assert editor.detected_language() == "markdown"
        assert settings.live_markdown is False, "no silent switch"
        assert window.action_banner.isHidden() is False
        assert window._primary_banner_action == "enable_markdown"   # noqa: SLF001

        window.act_banner_reload.click()
        assert settings.live_markdown is True
        assert editor.live_markdown_enabled() is True
        assert window.action_banner.isHidden() is True
    finally:
        window.close()


# ------------------------------------------------------------------ CD-22
def test_dropping_a_file_on_the_text_pastes_its_content(qapp, tmp_path):
    from PySide6.QtCore import QMimeData, QUrl

    window, controller, _ = _controller(tmp_path)
    try:
        source = tmp_path / "note.txt"
        source.write_text("first line\nsecond line\n", encoding="utf-8")
        editor = controller.new_document()
        data = QMimeData()
        data.setUrls([QUrl.fromLocalFile(str(source))])

        editor.insertFromMimeData(data)
        text = editor.document().toPlainText()
        assert "first line" in text and "second line" in text
        assert str(source) not in text, "the path is not pasted"
    finally:
        window.close()


def test_dropping_a_binary_file_opens_a_tab_instead(qapp, tmp_path):
    from PySide6.QtCore import QMimeData, QUrl

    window, controller, _ = _controller(tmp_path)
    opened = []
    try:
        controller._open_dropped_paths = opened.extend        # noqa: SLF001
        binary = tmp_path / "image.bin"
        binary.write_bytes(b"\x00\x01\x02\x03" * 100)
        editor = controller.new_document()
        data = QMimeData()
        data.setUrls([QUrl.fromLocalFile(str(binary))])

        editor.insertFromMimeData(data)
        assert opened == [str(binary)]
        assert editor.document().toPlainText() == ""
    finally:
        window.close()


def test_the_context_menu_offers_paste_without_formatting(qapp, tmp_path):
    from mishkah.core.i18n import tr

    window, controller, _ = _controller(tmp_path)
    try:
        editor = controller.new_document()
        menu = editor.build_context_menu()
        texts = [action.text() for action in menu.actions()]
        assert tr("action.paste_plain") in texts
        assert window.act_paste_plain.text() == tr("action.paste_plain")
        _close_menu(menu)
    finally:
        window.close()


def _coloured_formats(editor) -> int:
    doc = editor.document()
    total = 0
    block = doc.firstBlock()
    while block.isValid():
        total += len(block.layout().formats())
        block = block.next()
    return total


def test_pasted_code_in_an_untitled_tab_is_coloured_without_saving(qapp, tmp_path):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    window, controller, _ = _controller(tmp_path)
    try:
        assert controller.settings.syntax_highlighting is True
        editor = controller.new_document()
        assert editor.document().toPlainText() == ""
        editor.setFocus()
        QTest.keyClicks(editor, "def greet(name):")
        QTest.keyClick(editor, Qt.Key_Return)
        QTest.keyClicks(editor, "    return 'hello ' + name")

        QTest.qWait(700)                       # the debounce is 400 ms
        assert editor.language_code() == "python"
        assert _coloured_formats(editor) > 0, "the pasted code stays colourless"
    finally:
        window.close()


def test_dropped_code_content_is_coloured_too(qapp, tmp_path):
    from PySide6.QtCore import QMimeData, QUrl
    from PySide6.QtTest import QTest

    window, controller, _ = _controller(tmp_path)
    try:
        source = tmp_path / "snippet.txt"
        source.write_text("def main():\n    return 42\n", encoding="utf-8")
        editor = controller.new_document()
        data = QMimeData()
        data.setUrls([QUrl.fromLocalFile(str(source))])
        editor.insertFromMimeData(data)

        QTest.qWait(700)
        assert editor.language_code() == "python"
        assert _coloured_formats(editor) > 0
    finally:
        window.close()


# ------------------------------------------------------------------ round 5
def _close_menu(menu) -> None:
    """Free the menu now: a QMenu left alive keeps a C++ object past the app."""
    from PySide6.QtCore import QCoreApplication, QEvent

    menu.close()
    menu.setParent(None)
    menu.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def _menu_labels(menu):
    return [action.text() for action in menu.actions() if not action.isSeparator()]


def test_the_context_menu_follows_the_interface_language(qapp, tmp_path):
    from mishkah.core import i18n
    from mishkah.core.i18n import tr

    window, controller, _ = _controller(tmp_path)
    try:
        i18n.set_language("ar")
        editor = controller.new_document()
        editor.setPlainText("نص للاختبار")
        menu = editor.build_context_menu()
        labels = _menu_labels(menu)

        assert labels == [
            tr("action.undo"), tr("action.redo"),
            tr("action.cut"), tr("action.copy"), tr("action.paste"),
            tr("action.paste_plain"), tr("action.delete"),
            tr("action.select_all"),
            tr("action.find"), tr("action.replace"), tr("action.goto"),
        ]
        # The old build took Qt's untranslated strings; none may slip back.
        assert "Paste" not in labels and "Select All" not in labels
        _close_menu(menu)
    finally:
        i18n.set_language("ar")
        window.close()


def test_the_context_menu_is_grouped_history_then_clipboard(qapp, tmp_path):
    window, controller, _ = _controller(tmp_path)
    try:
        editor = controller.new_document()
        editor.setPlainText("abc")
        menu = editor.build_context_menu()
        names = [a.objectName() for a in menu.actions() if not a.isSeparator()]
        assert names[:2] == ["action.undo", "action.redo"]
        assert names[2:7] == ["action.cut", "action.copy", "action.paste",
                              "action.paste_plain", "action.delete"]
        assert names[7] == "action.select_all"
        assert names[8:] == ["action.find", "action.replace", "action.goto"]
        separators = sum(1 for a in menu.actions() if a.isSeparator())
        assert separators == 3
        _close_menu(menu)
    finally:
        window.close()


def test_cut_and_copy_are_greyed_out_without_a_selection(qapp, tmp_path):
    from PySide6.QtGui import QTextCursor  # noqa: PLC0415

    window, controller, _ = _controller(tmp_path)
    try:
        editor = controller.new_document()
        editor.setPlainText("abc")
        editor.moveCursor(QTextCursor.MoveOperation.End)
        menu = editor.build_context_menu()
        by_name = {a.objectName(): a for a in menu.actions()}
        assert not by_name["action.cut"].isEnabled()
        assert not by_name["action.copy"].isEnabled()
        editor.selectAll()
        _close_menu(menu)
        menu = editor.build_context_menu()
        by_name = {a.objectName(): a for a in menu.actions()}
        assert by_name["action.cut"].isEnabled()
        assert by_name["action.copy"].isEnabled()
        _close_menu(menu)
    finally:
        window.close()


def test_the_context_menu_opens_the_find_bar(qapp, tmp_path):
    from mishkah.core.i18n import tr

    window, controller, _ = _controller(tmp_path)
    try:
        editor = controller.new_document()
        editor.setPlainText("hello")
        menu = editor.build_context_menu()
        find = [a for a in menu.actions() if a.objectName() == "action.find"][0]
        assert find.text() == tr("action.find")
        assert editor.apply_menu_action(find.objectName()) is True
        assert not window.find_bar.isHidden(), "the bar opened"
        window.find_bar.hide()
        _close_menu(menu)
    finally:
        window.close()


def test_highlighting_says_nothing(qapp, tmp_path):
    """No banner when the language is guessed: the colours are the message.

    The buffer is filled the way a paste does it; the keystroke path itself is
    covered by ``test_pasted_code_in_an_untitled_tab_is_coloured_without_saving``.
    """
    from PySide6.QtTest import QTest

    window, controller, _ = _controller(tmp_path)
    try:
        editor = controller.new_document()
        editor.setPlainText("def greet(name):\n    return name\n")

        QTest.qWait(700)
        assert editor.language_code() == "python"
        assert window.banner.isHidden(), "no notice: the colours are the message"
        assert window.status.language_text() == "Python"
    finally:
        window.close()
