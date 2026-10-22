"""The Settings dialog (View ▸ Settings, Ctrl+,).

Every widget here maps one-to-one onto a :class:`mufakkira.core.settings.Settings`
field, so the dialog never owns state: it reads the settings on open and writes
them back only when the user accepts.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFontComboBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from mufakkira.core.i18n import tr
from mufakkira.core.settings import Settings
from mufakkira.core.text_direction import AUTO, LTR, RTL

THEMES = ("system", "light", "dark")
DIRECTIONS = (AUTO, LTR, RTL)


class SettingsDialog(QDialog):
    """Modal editor for :class:`Settings`."""

    def __init__(self, settings: Settings, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle(tr("settings.title"))
        self.setModal(True)
        self.setMinimumWidth(520)
        self._settings = settings

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 18, 18, 14)
        outer.setSpacing(12)

        outer.addWidget(self._appearance_group())
        outer.addWidget(self._editor_group())
        outer.addWidget(self._typing_group())
        outer.addWidget(self._files_group())

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr("dialog.ok"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("dialog.cancel"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

        self._load(settings)

    # ------------------------------------------------------------------
    # construction
    # ------------------------------------------------------------------
    @staticmethod
    def _group(title: str, form: QFormLayout, *notes: QLabel) -> QGroupBox:
        """Group box with a form plus full-width notes underneath.

        A wrapping label placed *inside* a QFormLayout row keeps the height it
        had before wrapping and clips; a vertical layout below the form gives
        it the room it asks for.
        """
        group = QGroupBox(title)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(12, 6, 12, 10)
        layout.setSpacing(4)
        layout.addLayout(form)
        for note in notes:
            layout.addWidget(note)
        return group

    def _appearance_group(self) -> QGroupBox:
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeading)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        self.cmb_language = QComboBox()
        from mufakkira.core.languages import all_languages

        for lang in all_languages():
            label = (lang.native_name if lang.native_name == lang.english_name
                     else f"{lang.native_name} — {lang.english_name}")
            self.cmb_language.addItem(label, lang.code)
        form.addRow(tr("settings.language"), self.cmb_language)

        self.cmb_theme = QComboBox()
        for theme in THEMES:
            self.cmb_theme.addItem(tr(f"settings.theme.{theme}"), theme)
        form.addRow(tr("settings.theme"), self.cmb_theme)

        # "Automatic" keeps the per-script stack that suits the UI language.
        self.cmb_font = QFontComboBox()
        self.cmb_font.setInsertPolicy(QFontComboBox.InsertPolicy.NoInsert)
        self.cmb_font.insertItem(0, tr("settings.auto_font"))  # index 0 = automatic
        self.cmb_font.setCurrentIndex(0)
        form.addRow(tr("settings.font"), self.cmb_font)

        self.spin_font_size = QSpinBox()
        self.spin_font_size.setRange(8, 48)
        self.spin_font_size.setSuffix(" pt")
        form.addRow(tr("settings.font_size"), self.spin_font_size)

        note = QLabel(tr("settings.language.note"))
        note.setWordWrap(True)
        note.setObjectName("settingsNote")
        return self._group(tr("settings.group.appearance"), form, note)

    def _editor_group(self) -> QGroupBox:
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeading)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        self.spin_tab = QSpinBox()
        self.spin_tab.setRange(1, 16)
        form.addRow(tr("settings.tab_width"), self.spin_tab)

        self.cmb_direction = QComboBox()
        self.cmb_direction.addItem(tr("settings.auto"), AUTO)
        self.cmb_direction.addItem(tr("direction.ltr"), LTR)
        self.cmb_direction.addItem(tr("direction.rtl"), RTL)
        form.addRow(tr("settings.default_direction"), self.cmb_direction)

        self.chk_word_wrap = QCheckBox(tr("action.word_wrap"))
        self.chk_line_numbers = QCheckBox(tr("action.line_numbers"))
        self.chk_status_bar = QCheckBox(tr("action.status_bar"))
        for widget in (self.chk_word_wrap, self.chk_line_numbers, self.chk_status_bar):
            form.addRow("", widget)
        return self._group(tr("settings.group.editor"), form)

    def _typing_group(self) -> QGroupBox:
        """Auto-pairing, smart indentation and the opt-in highlighter."""
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeading)

        self.chk_auto_close = QCheckBox(tr("action.auto_close"))
        self.chk_auto_indent = QCheckBox(tr("action.auto_indent"))
        self.chk_syntax = QCheckBox(tr("action.syntax"))
        form.addRow(self.chk_auto_close)
        form.addRow(self.chk_auto_indent)
        form.addRow(self.chk_syntax)

        note = QLabel(tr("settings.syntax_note"))
        note.setWordWrap(True)
        note.setObjectName("settingsNote")
        return self._group(tr("settings.editing"), form, note)

    def _files_group(self) -> QGroupBox:
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeading)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        self.spin_ask_mb = QSpinBox()
        self.spin_ask_mb.setRange(0, 8192)
        self.spin_ask_mb.setSuffix(" MB")
        self.spin_ask_mb.setSpecialValueText(tr("settings.auto"))
        form.addRow(tr("settings.hard_limit"), self.spin_ask_mb)

        self.spin_limit_mb = QSpinBox()
        self.spin_limit_mb.setRange(16, 8192)
        self.spin_limit_mb.setSuffix(" MB")
        form.addRow(tr("settings.large_files"), self.spin_limit_mb)

        self.chk_restore = QCheckBox(tr("settings.restore_session"))
        form.addRow(self.chk_restore)

        self.chk_perf = QCheckBox(tr("settings.perf_mode"))
        note = QLabel(tr("settings.perf_mode.note"))
        note.setWordWrap(True)
        note.setObjectName("settingsNote")
        form.addRow(self.chk_perf)
        return self._group(tr("settings.group.files"), form, note)

    # ------------------------------------------------------------------
    # data
    # ------------------------------------------------------------------
    def _load(self, s: Settings) -> None:
        self._select(self.cmb_language, s.ui_language)
        self._select(self.cmb_theme, s.theme)
        self._select(self.cmb_direction, s.default_direction)

        if s.font_family:
            self.cmb_font.setCurrentFont(QFont(s.font_family))
        else:
            self.cmb_font.setCurrentIndex(0)
        self.spin_font_size.setValue(int(s.font_size))
        self.spin_tab.setValue(int(s.tab_width))

        self.chk_word_wrap.setChecked(s.word_wrap)
        self.chk_line_numbers.setChecked(s.line_numbers)
        self.chk_status_bar.setChecked(s.show_status_bar)

        self.spin_ask_mb.setValue(int(s.ask_before_mb))
        self.spin_limit_mb.setValue(int(s.hard_limit_mb))
        self.chk_perf.setChecked(s.performance_mode)
        self.chk_restore.setChecked(s.restore_session)
        self.chk_auto_close.setChecked(s.auto_close_brackets)
        self.chk_auto_indent.setChecked(s.auto_indent)
        self.chk_syntax.setChecked(s.syntax_highlighting)

    @staticmethod
    def _select(combo: QComboBox, value: Any) -> None:
        index = combo.findData(value)
        if index < 0:
            index = combo.findText(str(value))
        if index >= 0:
            combo.setCurrentIndex(index)

    def values(self) -> Dict[str, Any]:
        """The edited settings as plain values (nothing is applied yet)."""
        if self.cmb_font.currentIndex() <= 0:
            family = ""
        else:
            family = self.cmb_font.currentFont().family()
        return {
            "ui_language": self.cmb_language.currentData(),
            "theme": self.cmb_theme.currentData(),
            "font_family": family,
            "font_size": self.spin_font_size.value(),
            "tab_width": self.spin_tab.value(),
            "default_direction": self.cmb_direction.currentData(),
            "word_wrap": self.chk_word_wrap.isChecked(),
            "line_numbers": self.chk_line_numbers.isChecked(),
            "show_status_bar": self.chk_status_bar.isChecked(),
            "ask_before_mb": self.spin_ask_mb.value(),
            "hard_limit_mb": self.spin_limit_mb.value(),
            "performance_mode": self.chk_perf.isChecked(),
            "restore_session": self.chk_restore.isChecked(),
            "auto_close_brackets": self.chk_auto_close.isChecked(),
            "auto_indent": self.chk_auto_indent.isChecked(),
            "syntax_highlighting": self.chk_syntax.isChecked(),
        }

    def apply_to(self, settings: Settings) -> Dict[str, Any]:
        """Copy the edited values onto *settings*; returns the old values."""
        new = self.values()
        old = {key: getattr(settings, key) for key in new}
        for key, value in new.items():
            setattr(settings, key, value)
        return old
