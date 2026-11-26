"""The Settings dialog (View ▸ Settings, Ctrl+,).

Structure (CD-02, revised 23 Nov 2026): seven categories — appearance, editor,
typing and direction, files and saving, tabs and session, shortcuts, advanced —
shown as a side list with a stacked page each.  Every page scrolls on its own
and the buttons sit outside any scrolling, so no control can ever be pushed out
of reach on a short screen.

The dialog owns no state.  It reads the settings into widgets on open and writes
them back only when the user accepts or applies; Cancel touches nothing.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFontComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from mishkah.core.i18n import tr
from mishkah.core.settings import Settings
from mishkah.core.text_direction import AUTO, LTR, RTL
from mishkah.widgets.icons import CATEGORY_KEYS, category_icon

THEMES = ("system", "light", "dark")
DIRECTIONS = (AUTO, LTR, RTL)
EXTENSIONS = ("txt", "md", "auto")
SIDES = ("first_strong", "first_line")
SHORTCUT_STYLES = ("default", "platform")
LAST_TAB_ACTIONS = ("home", "quit")

#: The seven categories, in order.  Their icons are *drawn* (``icons.py``) and
#: inked for the active theme: the style's own pixmaps are coloured for the
#: system palette, and on a dark desktop with the light stylesheet they arrived
#: white on white.
CATEGORIES = CATEGORY_KEYS


class SettingsDialog(QDialog):
    """Category-per-page editor for :class:`Settings`."""

    #: The user pressed Apply: apply the values now and keep the dialog open.
    applied = Signal()

    def __init__(self, settings: Settings, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle(tr("settings.title"))
        self.setModal(True)
        self.setMinimumSize(720, 520)
        self._settings = settings
        #: ``key -> (read, write)``: one map for every widget on every page, so
        #: a page can never forget to read or write a key it shows.
        self._bindings: Dict[str, tuple[Callable[[], Any], Callable[[Any], None]]] = {}
        self._pages: List[QWidget] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 12)
        outer.setSpacing(10)

        body = QHBoxLayout()
        body.setSpacing(12)
        self.list_categories = QListWidget()
        self.list_categories.setObjectName("SettingsCategories")
        self.list_categories.setFixedWidth(200)
        self.list_categories.setIconSize(QSize(18, 18))
        self.list_categories.currentRowChanged.connect(self._on_category_changed)
        body.addWidget(self.list_categories, 0)

        self.stack = QStackedWidget()
        body.addWidget(self.stack, 1)
        outer.addLayout(body, 1)

        builders = (
            self._page_appearance,
            self._page_editor,
            self._page_typing,
            self._page_files,
            self._page_tabs,
            self._page_shortcuts,
            self._page_advanced,
        )
        dark = self._dark_chrome()
        for key, build in zip(CATEGORIES, builders):
            item = QListWidgetItem(category_icon(key, dark, 18),
                                   tr(f"settings.cat.{key}"))
            item.setData(Qt.ItemDataRole.UserRole, key)
            self.list_categories.addItem(item)
            page = build()
            # The stretch goes *last*: it used to be added first, which pushed
            # every control to the bottom of the page (reported as "the settings
            # sit at the bottom of the window").
            page.layout().addStretch(1)
            self._pages.append(page)
            self.stack.addWidget(self._scrollable(page))

        # --- buttons: fixed at the bottom, outside every scroll area ------
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Apply,
            parent=self,
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr("dialog.ok"))
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(
            tr("dialog.cancel"))
        self.apply_button = self.buttons.button(QDialogButtonBox.StandardButton.Apply)
        self.apply_button.setText(tr("dialog.apply"))
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.apply_button.clicked.connect(self._apply_without_closing)
        outer.addWidget(self.buttons, 0)

        # Ctrl+Tab walks the categories like the platform settings app.
        QShortcut(QKeySequence("Ctrl+Tab"), self,
                  activated=self._next_category)
        QShortcut(QKeySequence("Ctrl+Shift+Tab"), self,
                  activated=lambda: self._next_category(-1))

        self._load(settings)
        self.show_category(getattr(settings, "settings_page", "appearance"))

    @staticmethod
    def _dark_chrome() -> bool:
        """Which chrome the icons must match (see ``app.is_dark_chrome``)."""
        from mishkah.app import is_dark_chrome

        return is_dark_chrome()

    # ------------------------------------------------------------------
    # scaffolding
    # ------------------------------------------------------------------
    def _scrollable(self, page: QWidget) -> QScrollArea:
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QScrollArea.Shape.NoFrame)
        area.setWidget(page)
        return area

    @staticmethod
    def _page() -> tuple[QWidget, QVBoxLayout]:
        """An empty page, top-aligned: the caller adds the trailing stretch."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 4, 12, 8)
        layout.setSpacing(12)
        return page, layout

    @staticmethod
    def _form() -> QFormLayout:
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeading)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        return form

    @staticmethod
    def _group(title: str, layout: QVBoxLayout, *notes: QLabel) -> QGroupBox:
        """Group box with a form plus full-width notes underneath.

        A wrapping label inside a QFormLayout row keeps the height it had before
        wrapping and clips; a vertical layout below the form gives it room.
        """
        group = QGroupBox(title)
        inner = QVBoxLayout(group)
        inner.setContentsMargins(12, 6, 12, 10)
        inner.setSpacing(4)
        inner.addLayout(layout)
        for note in notes:
            inner.addWidget(note)
        return group

    @staticmethod
    def _note(key: str) -> QLabel:
        label = QLabel(tr(key))
        label.setWordWrap(True)
        label.setObjectName("settingsNote")
        return label

    def _bind(self, key: str, read: Callable[[], Any],
              write: Callable[[Any], None]) -> None:
        self._bindings[key] = (read, write)

    # -- widget factories (each registers its binding) -------------------
    def _combo(self, form: QFormLayout, key: str, label: str,
               options, texts: Optional[Callable[[Any], str]] = None) -> QComboBox:
        combo = QComboBox()
        combo.setObjectName(f"Cmb_{key}")
        for option in options:
            text = texts(option) if texts else tr(f"{label}.{option}")
            combo.addItem(text, option)
        form.addRow(tr(label), combo)
        self._bind(key, combo.currentData,
                   lambda value, c=combo: self._select(c, value))
        return combo

    def _check(self, form: QFormLayout, key: str, label: str) -> QCheckBox:
        box = QCheckBox(tr(label))
        box.setObjectName(f"Chk_{key}")
        form.addRow("", box)
        self._bind(key, box.isChecked, box.setChecked)
        return box

    def _spin(self, form: QFormLayout, key: str, label: str,
              low: int, high: int, suffix: str = "",
              special: str = "") -> QSpinBox:
        spin = QSpinBox()
        spin.setObjectName(f"Spin_{key}")
        spin.setRange(low, high)
        if suffix:
            spin.setSuffix(suffix)
        if special:
            spin.setSpecialValueText(special)
        form.addRow(tr(label), spin)
        self._bind(key, spin.value, spin.setValue)
        return spin

    # ------------------------------------------------------------------
    # the seven pages
    # ------------------------------------------------------------------
    def _page_appearance(self) -> QWidget:
        page, layout = self._page()
        form = self._form()

        self.cmb_language = QComboBox()
        self.cmb_language.setObjectName("Cmb_ui_language")
        from mishkah.core.languages import all_languages

        for lang in all_languages():
            label = (lang.native_name if lang.native_name == lang.english_name
                     else f"{lang.native_name} — {lang.english_name}")
            self.cmb_language.addItem(label, lang.code)
        form.addRow(tr("settings.language"), self.cmb_language)
        self._bind("ui_language", self.cmb_language.currentData,
                   lambda value, c=self.cmb_language: self._select(c, value))

        self.cmb_theme = self._combo(form, "theme", "settings.theme", THEMES)

        # "Automatic" keeps the per-script stack that suits the UI language.
        self.cmb_font = QFontComboBox()
        self.cmb_font.setObjectName("Cmb_font_family")
        self.cmb_font.setInsertPolicy(QFontComboBox.InsertPolicy.NoInsert)
        self.cmb_font.insertItem(0, tr("settings.auto_font"))  # 0 = automatic
        form.addRow(tr("settings.font"), self.cmb_font)
        self._bind("font_family", self._read_font, self._write_font)

        self.spin_font_size = self._spin(form, "font_size", "settings.font_size",
                                         6, 72, " pt")
        layout.addWidget(self._group(tr("settings.group.appearance"), form,
                                     self._note("settings.language.note")))
        return page

    def _page_editor(self) -> QWidget:
        page, layout = self._page()
        form = self._form()

        self.spin_tab = self._spin(form, "tab_width", "settings.tab_width", 1, 16)
        self.chk_word_wrap = self._check(form, "word_wrap", "action.word_wrap")
        self.chk_line_numbers = self._check(form, "line_numbers",
                                            "action.line_numbers")
        self.chk_status_bar = self._check(form, "show_status_bar",
                                          "action.status_bar")
        self.chk_completion = self._check(form, "word_completion",
                                          "settings.word_completion")
        self.chk_syntax = self._check(form, "syntax_highlighting", "action.syntax")
        self.chk_markdown = self._check(form, "live_markdown", "action.markdown")
        layout.addWidget(self._group(tr("settings.group.editor"), form,
                                     self._note("settings.syntax_note"),
                                     self._note("settings.markdown_note")))
        return page

    def _page_typing(self) -> QWidget:
        page, layout = self._page()
        form = self._form()

        self.chk_auto_close = self._check(form, "auto_close_brackets",
                                          "action.auto_close")
        self.chk_auto_indent = self._check(form, "auto_indent", "action.auto_indent")
        self.cmb_direction = self._combo(form, "default_direction",
                                         "settings.default_direction", DIRECTIONS,
                                         lambda value: {
                                             AUTO: tr("settings.auto"),
                                             LTR: tr("direction.ltr"),
                                             RTL: tr("direction.rtl"),
                                         }[value])
        self.cmb_side = self._combo(form, "document_side_source",
                                    "settings.document_side", SIDES,
                                    lambda value: tr(
                                        f"settings.document_side.{value}"))
        self.chk_invisible = self._check(form, "show_invisible_chars",
                                         "action.show_invisible")
        self.chk_invisible.setToolTip(tr("action.show_invisible_hint"))
        layout.addWidget(self._group(tr("settings.cat.typing"), form,
                                     self._note("settings.direction_note")))
        return page

    def _page_files(self) -> QWidget:
        page, layout = self._page()
        form = self._form()

        self.cmb_extension = self._combo(form, "default_extension",
                                         "settings.extension", EXTENSIONS,
                                         lambda value: tr(f"extension.{value}"))
        self.spin_idle = self._spin(form, "autosave_idle_ms",
                                    "settings.autosave_idle", 500, 60000, " ms")
        self.spin_ask_mb = self._spin(form, "ask_before_mb", "settings.hard_limit",
                                      0, 8192, " MB", tr("settings.auto"))
        self.chk_perf = self._check(form, "performance_mode",
                                    "settings.perf_mode")
        layout.addWidget(self._group(tr("settings.group.files"), form,
                                     self._note("settings.large_files.note"),
                                     self._note("settings.perf_mode.note")))
        return page

    def _page_tabs(self) -> QWidget:
        page, layout = self._page()
        form = self._form()

        self.chk_restore = self._check(form, "restore_session",
                                       "settings.restore_session")
        self.cmb_last_tab = self._combo(form, "last_tab_action",
                                        "settings.last_tab", LAST_TAB_ACTIONS,
                                        lambda value: tr(
                                            f"settings.last_tab.{value}"))
        layout.addWidget(self._group(tr("settings.cat.tabs"), form))
        return page

    def _page_shortcuts(self) -> QWidget:
        page, layout = self._page()
        form = self._form()

        self.cmb_redo = self._combo(form, "redo_shortcut",
                                    "settings.redo_shortcut", SHORTCUT_STYLES,
                                    lambda value: tr(
                                        f"settings.shortcut.{value}"))
        self.cmb_replace = self._combo(form, "replace_shortcut",
                                       "settings.replace_shortcut",
                                       SHORTCUT_STYLES,
                                       lambda value: tr(
                                           f"settings.shortcut.{value}"))
        # The actual keys are shown as a hint, so they never drift from the menu.
        self.lbl_keys = self._note("settings.cat.shortcuts")
        self.lbl_keys.setObjectName("settingsNote")
        self.lbl_keys.setText(self._shortcut_hint())
        for combo in (self.cmb_redo, self.cmb_replace):
            combo.currentIndexChanged.connect(
                lambda _index: self.lbl_keys.setText(self._shortcut_hint()))
        layout.addWidget(self._group(tr("settings.cat.shortcuts"), form,
                                     self.lbl_keys))
        return page

    def _page_advanced(self) -> QWidget:
        page, layout = self._page()
        form = self._form()

        self.spin_hard_cap = self._spin(form, "hard_limit_mb",
                                        "settings.hard_cap", 16, 8192, " MB")
        layout.addWidget(self._group(tr("settings.cat.advanced"), form))

        self.lbl_path = QLabel(tr("settings.path_label"))
        self.lbl_path.setWordWrap(True)
        self.lbl_path.setObjectName("settingsNote")
        layout.addWidget(self.lbl_path)

        row = QHBoxLayout()
        self.btn_reset = QPushButton(tr("settings.reset"))
        self.btn_reset.setObjectName("SettingsReset")
        self.btn_reset.clicked.connect(self.reset_to_defaults)
        row.addWidget(self.btn_reset)
        row.addStretch(1)
        layout.addLayout(row)
        return page

    # ------------------------------------------------------------------
    # behaviour
    # ------------------------------------------------------------------
    def _shortcut_hint(self) -> str:
        redo = "Ctrl+Y / Ctrl+Shift+Z" if self._selected(
            "redo_shortcut") == "default" else "Ctrl+Shift+Z"
        replace = "Ctrl+H" if self._selected("replace_shortcut") == "default" \
            else "Ctrl+R"
        return f"{tr('settings.redo_shortcut')}: {redo} · " \
               f"{tr('settings.replace_shortcut')}: {replace}"

    def _selected(self, key: str) -> Any:
        return self._bindings[key][0]()

    def category_keys(self) -> List[str]:
        return [self.list_categories.item(i).data(Qt.ItemDataRole.UserRole)
                for i in range(self.list_categories.count())]

    def current_category(self) -> str:
        item = self.list_categories.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else "appearance"

    def show_category(self, key: str) -> None:
        keys = self.category_keys()
        index = keys.index(key) if key in keys else 0
        self.list_categories.setCurrentRow(index)

    def _on_category_changed(self, row: int) -> None:
        if 0 <= row < self.stack.count():
            self.stack.setCurrentIndex(row)

    def _next_category(self, step: int = 1) -> None:
        count = self.list_categories.count()
        if not count:
            return
        self.list_categories.setCurrentRow(
            (self.list_categories.currentRow() + step) % count)

    def bound_keys(self) -> List[str]:
        """Every settings key a widget on some page reads and writes."""
        return sorted(self._bindings)

    def reset_to_defaults(self) -> None:
        """Fill the widgets with the built-in defaults (nothing is saved yet)."""
        for key, (_read, write) in self._bindings.items():
            write(getattr(Settings(), key, None))
        self._load_derived(Settings())

    def _apply_without_closing(self) -> None:
        """Apply keeps the dialog open: the controller applies, we stay."""
        self.applied.emit()

    # ------------------------------------------------------------------
    # data
    # ------------------------------------------------------------------
    def _read_font(self) -> str:
        if self.cmb_font.currentIndex() <= 0:
            return ""
        return self.cmb_font.currentFont().family()

    def _write_font(self, family: Any) -> None:
        if family:
            self.cmb_font.setCurrentFont(QFont(str(family)))
        else:
            self.cmb_font.setCurrentIndex(0)

    @staticmethod
    def _select(combo: QComboBox, value: Any) -> None:
        index = combo.findData(value)
        if index < 0:
            index = combo.findText(str(value))
        if index >= 0:
            combo.setCurrentIndex(index)

    def _load(self, settings: Settings) -> None:
        for key, (_read, write) in self._bindings.items():
            write(getattr(settings, key, None))
        self._load_derived(settings)

    def _load_derived(self, settings: Settings) -> None:
        path = getattr(settings, "path", None)
        self.lbl_path.setText(f"{tr('settings.path_label')}: {path}"
                              if path else tr("settings.path_label"))
        self.lbl_keys.setText(self._shortcut_hint())

    def values(self) -> Dict[str, Any]:
        """The edited settings as plain values (nothing is applied yet)."""
        values = {key: read() for key, (read, _write) in self._bindings.items()}
        values["hard_limit_mb"] = self.spin_hard_cap.value()
        values["settings_page"] = self.current_category()
        return values

    def apply_to(self, settings: Settings) -> Dict[str, Any]:
        """Copy the edited values onto *settings*; returns the old values."""
        new = self.values()
        old = {key: getattr(settings, key) for key in new}
        for key, value in new.items():
            setattr(settings, key, value)
        return old
