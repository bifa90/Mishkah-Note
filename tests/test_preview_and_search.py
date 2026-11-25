"""Preview mode and incremental search (CD-11 / M4)."""

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
    controller = MainController(window, settings, FileService())
    return window, controller, settings


def test_the_configured_ceiling_reaches_the_loader(qapp, tmp_path):
    window, controller, settings = _controller(tmp_path)
    seen = {}
    try:
        settings.hard_limit_mb = 100
        controller.window.ask_big_file = lambda *a, **k: True
        controller._begin_load = lambda path, encoding=None, limit_mb=None: seen.update(
            limit_mb=limit_mb, path=path)                      # noqa: SLF001
        target = tmp_path / "big.txt"
        target.write_text("x\n", encoding="utf-8")
        controller.open_path(target)
        assert seen["limit_mb"] == 100
    finally:
        window.close()


def test_a_preview_offers_a_way_to_open_the_whole_file(qapp, tmp_path):
    window, controller, settings = _controller(tmp_path)
    calls = []
    try:
        settings.hard_limit_mb = 1
        controller.files.load = lambda path, encoding=None, limit_mb=None: calls.append(
            dict(path=path, limit_mb=limit_mb))
        editor = controller.new_document()
        doc = controller.document_for(editor)
        doc.path = tmp_path / "huge.log"

        window.show_preview("huge.log", "1.0 MB", "900.0 MB")
        assert window._primary_banner_action == "open_full"   # noqa: SLF001
        window.act_banner_reload.click()
        assert calls and calls[0]["limit_mb"] is None, "the whole file is read"
        assert window.action_banner.isHidden()
    finally:
        window.close()


def test_incremental_search_moves_to_the_first_match(qapp, tmp_path):
    from PySide6.QtTest import QTest

    window, controller, _ = _controller(tmp_path)
    try:
        editor = controller.new_document()
        editor.setPlainText("alpha beta gamma\nalpha again\n")
        cursor = editor.textCursor()
        cursor.movePosition(cursor.MoveOperation.Start)
        editor.setTextCursor(cursor)

        controller.show_find(False)
        window.find_bar.find_edit.setText("gamma")
        QTest.qWait(300)
        assert editor.textCursor().selectedText() == "gamma"

        # Refining the needle comes back to the anchor instead of walking on.
        window.find_bar.find_edit.setText("alph")
        QTest.qWait(300)
        assert editor.textCursor().selectedText().lower() == "alph"
        assert editor.document().isModified() is False
    finally:
        window.close()


def test_incremental_search_marks_a_missing_needle(qapp, tmp_path):
    from PySide6.QtTest import QTest

    window, controller, _ = _controller(tmp_path)
    try:
        editor = controller.new_document()
        editor.setPlainText("alpha beta\n")
        controller.show_find(False)
        window.find_bar.find_edit.setText("zzz")
        QTest.qWait(300)
        assert window.find_bar.find_edit.property("noMatch") == "true"

        window.find_bar.find_edit.setText("beta")
        QTest.qWait(300)
        assert window.find_bar.find_edit.property("noMatch") == "false"
    finally:
        window.close()


def test_the_find_bar_close_button_is_drawn_not_typed(qapp):
    from mishkah.widgets.find_dialog import FindReplaceBar

    bar = FindReplaceBar()
    try:
        assert bar._close.text() == ""                    # noqa: SLF001
        assert bar._close.icon().isNull() is False        # noqa: SLF001
    finally:
        bar.deleteLater()


def test_a_cross_is_never_an_empty_box(qapp):
    from mishkah.widgets.icons import cross_icon, cross_pixmap

    pixmap = cross_pixmap(10)
    assert pixmap.isNull() is False
    assert pixmap.width() >= 10
    assert cross_icon(10).isNull() is False


def test_both_margin_sides_are_equal_and_the_caret_fits(qapp):
    """CD-11: the first character is never clipped, with or without a gutter."""
    from mishkah.models.document import DocumentModel
    from mishkah.views.editor_view import EditorView

    for mode in ("ltr", "rtl"):
        editor = EditorView(DocumentModel())
        editor.resize(600, 400)
        editor.setPlainText("مرحبا بالعالم hello world\nsecond line")
        editor.apply_direction(mode, announce=False)
        editor.show()
        qapp.processEvents()
        margins = editor.viewportMargins()
        assert margins.left() == margins.right() >= 4
        cursor = editor.textCursor()
        cursor.movePosition(cursor.MoveOperation.Start)
        editor.setTextCursor(cursor)
        rect = editor.cursorRect()
        assert rect.left() >= 0
        assert rect.top() >= 0
        editor.deleteLater()
