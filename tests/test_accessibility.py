"""Minimum accessibility: every control can be named, and Tab visits them all.

S1 is deliberately a floor, not a full audit — nothing here proves the app is
usable with Orca, and the release notes say so.  What it does prove is that no
*icon-only* button is silent, the clickable status chips can be reached without
a mouse, and the Tab chain is one explicit order rather than the accident of
widget construction order.

The GUI half skips itself on a checkout where Qt cannot load.
"""

from __future__ import annotations

import pytest

from mishkah.core import i18n, syntax


def _window(qapp, tmp_path, **settings_kwargs):
    from mishkah.controllers.main_controller import MainController
    from mishkah.core.settings import Settings
    from mishkah.services.file_service import FileService
    from mishkah.views.main_window import MainWindow

    settings = Settings(path=tmp_path / "settings.json", restore_session=False,
                        **settings_kwargs)
    window = MainWindow()
    controller = MainController(window, settings, FileService())
    return window, controller


# --------------------------------------------------------------------------
# labels: a name for everything a screen reader would otherwise skip
# --------------------------------------------------------------------------
def test_icon_only_buttons_have_a_name(qapp, tmp_path):
    window, _ = _window(qapp, tmp_path)
    try:
        # The banner's ✕ is drawn, has no text and is 22 px wide: without a
        # name it is completely silent for assistive technology.
        assert window.act_banner_dismiss.text() == ""
        assert window.act_banner_dismiss.accessibleName().strip()
    finally:
        window.close()


def test_the_search_bar_names_its_fields_and_its_close_button(qapp, tmp_path):
    window, _ = _window(qapp, tmp_path)
    try:
        bar = window.find_bar
        assert bar.find_edit.accessibleName() == i18n.tr("find.what")
        assert bar.replace_edit.accessibleName() == i18n.tr("find.replace_with")
        assert bar._close.text() == ""
        assert bar._close.accessibleName() == i18n.tr("dialog.close")
    finally:
        window.close()


def test_the_editor_says_what_it_edits(qapp, tmp_path):
    window, controller = _window(qapp, tmp_path)
    try:
        editor = controller.new_document()
        assert editor.accessibleName() == i18n.tr("a11y.editor")
    finally:
        window.close()


def test_status_chips_are_named_and_announce_their_value(qapp, tmp_path):
    window, _ = _window(qapp, tmp_path)
    try:
        status = window.status
        assert status._encoding.accessibleName() == i18n.tr("action.encoding")
        assert status._line_ending.accessibleName() == i18n.tr("menu.line_ending")
        assert status._direction.accessibleName() == i18n.tr("menu.direction")
        # The name says what the chip is; the description says what it shows.
        status.set_encoding("utf-8")
        assert status._encoding.accessibleDescription() == "UTF-8"
        status.set_line_ending("\r\n")
        assert status._line_ending.accessibleDescription() == "CRLF"
        status.set_zoom(125)
        assert status._zoom.accessibleDescription() == "125%"
    finally:
        window.close()


def test_the_autosave_switch_is_named(qapp, tmp_path):
    window, _ = _window(qapp, tmp_path)
    try:
        assert window.autosave_switch.accessibleName() == i18n.tr("action.autosave_label")
    finally:
        window.close()


@pytest.mark.parametrize("language", ["ar", "en", "ru"])
def test_names_follow_the_interface_language(qapp, tmp_path, language):
    previous = i18n.current_language()
    window, _ = _window(qapp, tmp_path)
    try:
        i18n.set_language(language)
        window.retranslate()
        assert window.act_banner_dismiss.accessibleName() == i18n.tr("dialog.close")
        assert window.status._encoding.accessibleName() == i18n.tr("action.encoding")
        assert not syntax.display_name("python", language).strip() == ""
    finally:
        i18n.set_language(previous)
        window.close()


# --------------------------------------------------------------------------
# tab order: one chain, not a side effect of construction order
# --------------------------------------------------------------------------
def _focusable(widget) -> bool:
    from PySide6.QtCore import Qt

    if not widget.isVisibleTo(widget.window()):
        # Hidden containers are legitimate (the search bar and the banner are
        # hidden until needed) but their children must still be in the chain.
        pass
    policy = widget.focusPolicy()
    return bool(policy & Qt.FocusPolicy.TabFocus)


def _chain_from(start, limit=200):
    """Walk the widget focus chain, which is what Tab follows."""
    seen = []
    widget = start
    for _ in range(limit):
        widget = widget.nextInFocusChain()
        if widget is start:
            break
        seen.append(widget)
    return seen


def test_tab_visits_the_search_bar_banner_and_chips_in_order(qapp, tmp_path):
    window, _ = _window(qapp, tmp_path)
    try:
        order = _chain_from(window.tabs)
        wanted = [
            window.find_bar.find_edit,
            window.find_bar._find_next,
            window.find_bar._close,
            window.find_bar.replace_edit,
            window.act_banner_reload,
            window.act_banner_overwrite,
            window.act_banner_dismiss,
            window.status._encoding,
            window.status._line_ending,
            window.status._direction,
        ]
        positions = []
        for widget in wanted:
            assert widget in order, f"{widget.__class__.__name__} is not in the Tab chain"
            positions.append(order.index(widget))
        assert positions == sorted(positions), "the Tab chain is not in the declared order"
    finally:
        window.close()


def test_the_clickable_chips_take_tab_focus(qapp, tmp_path):
    from PySide6.QtCore import Qt

    window, _ = _window(qapp, tmp_path)
    try:
        for chip in window.status.tab_order():
            assert chip.focusPolicy() == Qt.FocusPolicy.TabFocus
        # Click focus would steal the caret from the text while typing.
        assert not (window.status._encoding.focusPolicy()
                    & Qt.FocusPolicy.ClickFocus)
    finally:
        window.close()


def test_no_button_in_the_window_is_silent(qapp, tmp_path):
    """A button the user can see must say something — text or a name.

    Only *visible* buttons are judged: the banner's two text buttons are filled
    when the banner appears, and its ✕ carries a name (asserted above).  Qt's own
    internals — a tab's close button, a line edit's clear button, the menu-bar
    overflow — are excluded; they belong to another widget's contract.
    """
    from PySide6.QtWidgets import QAbstractButton, QLineEdit, QTabBar

    window, _ = _window(qapp, tmp_path)
    try:
        window.show()
        qapp.processEvents()
        silent = []
        for button in window.findChildren(QAbstractButton):
            if isinstance(button.parent(), (QTabBar, QLineEdit)):
                continue
            if button.objectName().startswith("qt_"):
                continue
            if not button.isVisible():
                continue
            if button.text().strip() or button.accessibleName().strip():
                continue
            silent.append(button.objectName() or button.__class__.__name__)
        assert silent == []
    finally:
        window.close()


def test_every_focusable_button_in_the_window_can_be_reached(qapp, tmp_path):
    """Nothing focusable may sit outside the chain (an unreachable button)."""
    from PySide6.QtWidgets import QPushButton

    window, _ = _window(qapp, tmp_path)
    try:
        order = set(_chain_from(window.tabs))
        stranded = [
            button.objectName() or button.text() or button.__class__.__name__
            for button in window.findChildren(QPushButton)
            if _focusable(button) and button not in order and button.window() is window
        ]
        assert stranded == []
    finally:
        window.close()
