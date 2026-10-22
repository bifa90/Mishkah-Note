"""The text area.

Text direction — what changed and why
-------------------------------------
The previous build called ``QWidget.setLayoutDirection()`` only.  That
flips the *widget's* layout (gutter, scrollbars, alignment) but it does
**not** set the base direction of the paragraphs inside a
``QPlainTextEdit``: Qt keeps them on ``LayoutDirectionAuto`` and every new
paragraph re-guesses.  The result was the reported bug — text that jumped
back and forth, and ``Ctrl+Shift`` appearing to do nothing.

This editor stores an explicit per-document mode (``auto`` / ``rtl`` /
``ltr``) and applies it to the *block format* of every paragraph with
``QTextBlockFormat.setLayoutDirection`` — the real bidi switch in Qt.
The widget direction is derived from it, so gutters and scrollbars move
too.  ``auto`` means Qt's Unicode rule (first strong character of each
paragraph), which is also what Windows 11 Mishkah Note does.

``Ctrl+Shift`` is kept as the shortcut (right → RTL, left → LTR) and is
detected from the hardware scan code with a full X11 / evdev / Windows /
macOS table, so it works on Xorg *and* Wayland.  A single tap of the
chord changes direction; using it together with another key (e.g.
``Ctrl+Shift+N``) or as the desktop's layout switcher does not.
"""

from __future__ import annotations

import time
from typing import Optional

from PySide6.QtCore import QRect, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QPainter,
    QTextBlockFormat,
    QTextCursor,
    QTextDocument,
)
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QPlainTextEdit

from mishkah.core import autocomplete, syntax
from mishkah.core.text_direction import (
    AUTO,
    LTR,
    RTL,
    SNIFF_CHARS,
    dominant_direction,
    first_strong_is_rtl,
    resolve_direction,
)
from mishkah.models.document import DocumentModel
from mishkah.widgets.line_number_area import LineNumberArea
from mishkah.widgets.markdown_decorator import MarkdownDecorator
from mishkah.widgets.syntax_highlighter import SyntaxHighlighter

MIN_FONT_SIZE = 6
MAX_FONT_SIZE = 72
DEFAULT_FONT_SIZE = 13
#: In *auto* mode alignment is resolved per paragraph; stop after this many
#: blocks so that a 300 MB preview never pays for a full document walk.
AUTO_DETECT_BLOCKS = 200
#: Breathing room between the text and the viewport edge, in pixels.
TEXT_MARGIN = 4

# Hardware scan codes for the modifier keys.
#   Linux/X11 and Wayland (evdev + 8)      : LCtrl 37, LShift 50, RShift 62, RCtrl 105
#   Windows (virtual key codes)            : LCtrl 29, LShift 42, RShift 54, RCtrl 97
#   macOS (virtual key codes)              : LCtrl 59, LShift 56, RShift 60, RCtrl 62
LEFT_CTRL_CODES = frozenset({37, 29, 59})
RIGHT_CTRL_CODES = frozenset({105, 97, 62})
LEFT_SHIFT_CODES = frozenset({50, 42, 56})
RIGHT_SHIFT_CODES = frozenset({62, 54, 60})

# The chord must be completed quickly to count as a direction switch.
CHORD_TIMEOUT_S = 1.5

_ALIGNMENT = {
    LTR: Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignAbsolute,
    RTL: Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignAbsolute,
}

_TO_QT_DIRECTION = {
    AUTO: Qt.LayoutDirection.LayoutDirectionAuto,
    LTR: Qt.LayoutDirection.LeftToRight,
    RTL: Qt.LayoutDirection.RightToLeft,
}
_FROM_QT_DIRECTION = {v: k for k, v in _TO_QT_DIRECTION.items()}


class EditorView(QPlainTextEdit):
    """A ``QPlainTextEdit`` tuned for very large, mixed-direction files."""

    cursor_moved = Signal(int, int, int)     # line, column, selection length
    zoom_changed = Signal(int)               # percent
    direction_changed = Signal(str)          # auto | rtl | ltr
    stats_changed = Signal(int, int)         # lines, chars

    def __init__(self, document: DocumentModel, font: Optional[QFont] = None,
                 parent=None):
        super().__init__(parent)
        self._doc = document
        self._base_font_size = (font.pointSize() if font and font.pointSize() > 0
                                else DEFAULT_FONT_SIZE)
        self._base_font_uses_pixels = bool(font is not None and font.pointSize() <= 0
                                           and font.pixelSize() > 0)
        self._base_font_pixels = (font.pixelSize() if font is not None
                                  and font.pixelSize() > 0 else DEFAULT_FONT_SIZE)
        self._tab_width = 4
        if font is not None:
            self.setFont(font)

        self.setUndoRedoEnabled(True)
        # The document margin is direction-agnostic in Qt (it is always added
        # on the left), which leaves RTL text glued to the right edge.  The
        # margin is therefore applied as a *viewport* margin, mirrored for RTL.
        self.document().setDocumentMargin(0)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(" ") * self._tab_width)
        self.setMouseTracking(True)

        # --- direction state -------------------------------------------------
        self._direction_mode = document.direction_mode or AUTO
        self._chord = _ChordState()

        # --- editing conveniences -------------------------------------------
        self._auto_close = True
        self._auto_indent = True
        self._word_completion = True
        self._indent_unit = autocomplete.DEFAULT_INDENT
        self._highlighter: Optional[SyntaxHighlighter] = None
        self._language = "auto"
        self._completion: Optional[QListWidget] = None

        # --- live Markdown (view-only decoration) ---------------------------
        self._markdown: Optional[MarkdownDecorator] = None
        self._theme_name = "light"

        # --- gutter ----------------------------------------------------------
        # Created lazily: Windows 11 Mishkah Note shows no gutter by default, so
        # most editors never need the extra child widget at all.
        self._gutter: Optional[LineNumberArea] = None
        self._gutter_visible = False
        self.blockCountChanged.connect(self._update_gutter_width)
        self.updateRequest.connect(self._update_gutter)

        self.cursorPositionChanged.connect(self._emit_cursor)
        self.cursorPositionChanged.connect(self._sync_markdown_caret)
        self.selectionChanged.connect(self._emit_cursor)
        self.document().contentsChanged.connect(self._emit_stats)
        self.document().contentsChanged.connect(self._sync_auto_alignment)

        self.apply_direction(self._direction_mode, announce=False)
        self._update_gutter_width(0)
        self._emit_stats()

    # ==================================================================
    # document plumbing
    # ==================================================================
    @property
    def doc(self) -> DocumentModel:
        return self._doc

    @property
    def direction_mode(self) -> str:
        return self._direction_mode

    def set_document(self, document: DocumentModel) -> None:
        self._doc = document
        self.load_content(document.content)
        self.apply_direction(document.direction_mode or AUTO, announce=False)

    def load_content(self, text: str) -> None:
        """Fast path for big payloads: no undo history, no per-block churn."""
        huge = len(text) > 4_000_000
        perf = self._doc.uses_performance_mode if self._doc else huge
        if perf:
            self.setUndoRedoEnabled(False)
            self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        else:
            self.setUndoRedoEnabled(True)

        self.setPlainText(text)
        self.document().setModified(False)
        self._emit_stats()

    # ==================================================================
    # text direction
    # ==================================================================
    def apply_direction(self, mode: str, announce: bool = True) -> None:
        """Set the base direction of *every* paragraph (the real fix)."""
        if mode not in (AUTO, LTR, RTL):
            mode = AUTO
        changed = mode != self._direction_mode
        self._direction_mode = mode
        qt_dir = _TO_QT_DIRECTION[mode]

        if mode == AUTO:
            block_fmt = QTextBlockFormat()
            block_fmt.setLayoutDirection(Qt.LayoutDirection.LayoutDirectionAuto)
            cursor = QTextCursor(self.document())
            cursor.beginEditBlock()
            cursor.select(QTextCursor.SelectionType.Document)
            cursor.setBlockFormat(block_fmt)
            cursor.endEditBlock()
        else:
            block_fmt = QTextBlockFormat()
            block_fmt.setLayoutDirection(qt_dir)
            # Qt keeps the *bidi order* from the direction but leaves the
            # alignment alone, so an RTL paragraph would still hug the left
            # margin.  Windows Notepad right-aligns it — do the same.
            block_fmt.setAlignment(_ALIGNMENT[mode])

            cursor = QTextCursor(self.document())
            cursor.beginEditBlock()
            cursor.select(QTextCursor.SelectionType.Document)
            cursor.setBlockFormat(block_fmt)
            cursor.endEditBlock()

        # Widget-level direction moves the gutter/scrollbar to the matching
        # side; for "auto" we follow whatever the caret's paragraph resolved to.
        direction = self.document_direction()
        self._apply_alignment(direction)
        self.setLayoutDirection(_TO_QT_DIRECTION[direction])
        self._update_gutter_width(0)
        self._place_gutter()
        self.viewport().update()

        if announce:
            self.direction_changed.emit(mode)
        elif changed:
            self.direction_changed.emit(mode)

    def _apply_alignment(self, direction: str) -> None:
        """Align the whole viewport left or right.

        ``QPlainTextEdit`` ignores per-block alignment (it shares one
        ``QTextDocument`` option for the view), so the only alignment that
        actually renders is the document's default text option.  Verified on
        Qt 6.12: block-level ``setAlignment`` is stored but never painted.
        """
        option = self.document().defaultTextOption()
        if option.alignment() != _ALIGNMENT[direction]:
            option.setAlignment(_ALIGNMENT[direction])
            self.document().setDefaultTextOption(option)
        self._aligned_direction = direction

    def document_direction(self) -> str:
        """Direction used for layout: explicit mode, or auto-detected."""
        if self._direction_mode != AUTO:
            return self._direction_mode
        block = self.document().begin()
        scanned = 0
        while block.isValid() and scanned < AUTO_DETECT_BLOCKS:
            text = block.text()
            if text.strip():
                return dominant_direction(text) or LTR
            block = block.next()
            scanned += 1
        return LTR

    def _sync_auto_alignment(self) -> None:
        """Follow the document's direction when it changes in auto mode."""
        if self._direction_mode != AUTO:
            return
        resolved = self.document_direction()
        if resolved != getattr(self, "_aligned_direction", None):
            self._apply_alignment(resolved)
            self.setLayoutDirection(_TO_QT_DIRECTION[resolved])
            self._place_gutter()
            self.viewport().update()

    def _widget_direction(self) -> Qt.LayoutDirection:
        return _TO_QT_DIRECTION[self.document_direction()]

    def resolved_direction(self) -> str:
        """What the status bar shows in ``auto`` mode.

        The caret's own paragraph wins; when that paragraph holds no strong
        character (an empty line at the end of a file, a line of punctuation)
        the document's opening text decides, so an Arabic file keeps saying
        RTL instead of flipping to LTR just because the caret is on a blank
        line.
        """
        if self._direction_mode != AUTO:
            return self._direction_mode
        text = self.textCursor().block().text()
        if first_strong_is_rtl(text) is not None:
            return resolve_direction(text, AUTO)
        return dominant_direction(self._leading_text())

    def _leading_text(self, limit: int = SNIFF_CHARS) -> str:
        """The first *limit* characters of the document, block by block."""
        chunks, used = [], 0
        block = self.document().begin()
        while block.isValid() and used < limit:
            chunks.append(block.text())
            used += len(block.text()) + 1
            block = block.next()
        return "\n".join(chunks)[:limit]

    def apply_direction_to_new_blocks(self) -> None:
        """Keep the caret's paragraph on the active mode (used after Enter)."""
        fmt = QTextBlockFormat()
        if self._direction_mode == AUTO:
            resolved = resolve_direction(self.textCursor().block().text(), AUTO)
            fmt.setLayoutDirection(Qt.LayoutDirection.LayoutDirectionAuto)
            fmt.setAlignment(_ALIGNMENT[resolved])
        else:
            fmt.setLayoutDirection(_TO_QT_DIRECTION[self._direction_mode])
            fmt.setAlignment(_ALIGNMENT[self._direction_mode])
        self.textCursor().setBlockFormat(fmt)

    # ==================================================================
    # Ctrl+Shift chord
    # ==================================================================
    def keyPressEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        self.handle_chord_press(_scan_code(event), event.key())

        if self._completion is not None and self._completion_key(event):
            return
        if self._handle_edit_key(event):
            return

        super().keyPressEvent(event)
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.apply_direction_to_new_blocks()

    # ==================================================================
    # editing conveniences (auto-pair, auto-indent, word completion)
    # ==================================================================
    def _handle_edit_key(self, event) -> bool:
        """Run the typing helpers; return True when the event is consumed."""
        if self.isReadOnly():
            return False
        key = event.key()
        modifiers = event.modifiers()
        plain = not (modifiers & (Qt.KeyboardModifier.ControlModifier
                                  | Qt.KeyboardModifier.AltModifier
                                  | Qt.KeyboardModifier.MetaModifier))

        if key == Qt.Key.Key_Space and modifiers & Qt.KeyboardModifier.ControlModifier:
            self.show_completions()
            return True

        if not plain:
            return False

        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self._auto_indent:
            return self._enter_with_indent()

        if key == Qt.Key.Key_Tab:
            if self.textCursor().hasSelection():
                self.indent_selection()
            else:
                self.textCursor().insertText(self._indent_unit)
            return True
        if (key == Qt.Key.Key_Backtab
                or (key == Qt.Key.Key_Tab and modifiers & Qt.KeyboardModifier.ShiftModifier)):
            self.indent_selection(outdent=True)
            return True

        if key == Qt.Key.Key_Backspace:
            return self._backspace_pair()

        text = event.text()
        if len(text) == 1 and self._auto_close:
            return self._apply_pairing(text)
        return False

    # -- indentation ----------------------------------------------------
    def _enter_with_indent(self) -> bool:
        cursor = self.textCursor()
        line = cursor.block().text()
        indent = autocomplete.indent_for_newline(line, self._indent_unit)
        start = cursor.position()
        cursor.insertText("\n" + indent)
        # Only claim the event when something was actually added; otherwise
        # let Qt insert the plain newline and keep undo identical.
        if start != cursor.position():
            self.setTextCursor(cursor)
            self.apply_direction_to_new_blocks()
            return True
        return False

    def indent_selection(self, outdent: bool = False) -> None:
        """Tab / Shift+Tab on a selection (or the current line)."""
        cursor = self.textCursor()
        if not cursor.hasSelection():
            cursor.select(QTextCursor.SelectionType.LineUnderCursor)
        text = cursor.selectedText().replace("\u2029", "\n")
        indented, _delta = autocomplete.reindent_block(
            text, outdent=outdent, unit=self._indent_unit)
        if indented == text:
            return
        start = cursor.selectionStart()
        cursor.beginEditBlock()
        cursor.insertText(indented)
        cursor.endEditBlock()
        cursor.setPosition(start)
        cursor.setPosition(start + len(indented),
                           QTextCursor.MoveMode.KeepAnchor)
        self.setTextCursor(cursor)

    # -- pairing ---------------------------------------------------------
    def _apply_pairing(self, char: str) -> bool:
        cursor = self.textCursor()
        selected = cursor.hasSelection()
        if selected:
            before, after = "", ""
        else:
            position = cursor.position()
            text = self.toPlainText()
            before = text[max(0, position - 1):position]
            after = text[position:position + 1]

        if autocomplete.should_skip_closer(char, after):
            cursor.movePosition(QTextCursor.MoveOperation.Right)
            self.setTextCursor(cursor)
            return True

        if not autocomplete.should_pair(char, before, after, has_selection=selected):
            return False

        closer = autocomplete.closing_for(char)
        if closer is None:
            return False

        cursor.beginEditBlock()
        if selected:
            chosen = cursor.selectedText()
            # Nested-newline selections: close the pair on its own line so the
            # indentation of the body survives.
            cursor.insertText(f"{char}{chosen}{closer}")
        else:
            cursor.insertText(char + closer)
            cursor.movePosition(QTextCursor.MoveOperation.Left)
        cursor.endEditBlock()
        self.setTextCursor(cursor)
        return True

    def _backspace_pair(self) -> bool:
        if not self._auto_close or self.textCursor().hasSelection():
            return False
        cursor = self.textCursor()
        position = cursor.position()
        text = self.toPlainText()
        before = text[max(0, position - 1):position]
        after = text[position:position + 1]
        if autocomplete.deletion_span(before or " ", before, after) != 2:
            return False
        cursor.beginEditBlock()
        cursor.deletePreviousChar()
        cursor.deleteChar()
        cursor.endEditBlock()
        self.setTextCursor(cursor)
        return True

    # ==================================================================
    # word completion popup
    # ==================================================================
    def show_completions(self) -> None:
        """Suggest words already typed in this document (Ctrl+Space)."""
        if not self._word_completion:
            return
        prefix = self._word_prefix()
        if len(prefix) < 2:
            return
        words = autocomplete.complete(prefix, self.toPlainText())
        if not words:
            return
        self.close_completions()
        popup = QListWidget(self)
        popup.setObjectName("CompletionPopup")
        popup.setWindowFlag(Qt.WindowType.Popup, True)
        popup.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        popup.setUniformItemSizes(True)
        for word in words:
            item = QListWidgetItem(word, popup)
            item.setData(Qt.ItemDataRole.UserRole, word)
        popup.setCurrentRow(0)
        rect = self.cursorRect()
        popup.move(self.mapToGlobal(rect.bottomLeft()))
        popup.setFixedWidth(max(160, rect.width() + 220))
        popup.show()
        self._completion = popup

    def _word_prefix(self) -> str:
        text = self.toPlainText()
        position = self.textCursor().position()
        start = position
        while start > 0 and (text[start - 1].isalnum() or text[start - 1] == "_"):
            start -= 1
        return text[start:position]

    def _completion_key(self, event) -> bool:
        popup = self._completion
        if popup is None:
            return False
        key = event.key()
        if key in (Qt.Key.Key_Escape,):
            self.close_completions()
            return True
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Tab):
            self.accept_completion()
            return True
        if key in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            row = popup.currentRow() + (-1 if key == Qt.Key.Key_Up else 1)
            popup.setCurrentRow(max(0, min(row, popup.count() - 1)))
            return True
        return False

    def accept_completion(self) -> None:
        popup = self._completion
        if popup is None:
            return
        item = popup.currentItem()
        if item is not None:
            word = item.data(Qt.ItemDataRole.UserRole)
            prefix = self._word_prefix()
            cursor = self.textCursor()
            cursor.insertText(word[len(prefix):])
            self.setTextCursor(cursor)
        self.close_completions()

    def close_completions(self) -> None:
        if self._completion is not None:
            self._completion.close()
            self._completion.deleteLater()
            self._completion = None

    def focusOutEvent(self, event) -> None:  # noqa: N802
        self.close_completions()
        self._chord.reset()
        super().focusOutEvent(event)

    # ==================================================================
    # configuration seams used by the controller and the tests
    # ==================================================================
    def set_auto_close(self, enabled: bool) -> None:
        self._auto_close = enabled

    def auto_close_enabled(self) -> bool:
        return self._auto_close

    def set_auto_indent(self, enabled: bool) -> None:
        self._auto_indent = enabled

    def auto_indent_enabled(self) -> bool:
        return self._auto_indent

    def set_word_completion(self, enabled: bool) -> None:
        self._word_completion = enabled

    def word_completion_enabled(self) -> bool:
        return self._word_completion

    def set_indent_unit(self, unit: str) -> None:
        self._indent_unit = unit or autocomplete.DEFAULT_INDENT

    def indent_unit(self) -> str:
        return self._indent_unit

    # ==================================================================
    # live Markdown (a view, never an edit)
    # ==================================================================
    def set_live_markdown(self, enabled: bool,
                          theme: Optional[str] = None) -> None:
        """Show Markdown formatted, without touching a single character.

        The decorator is a ``QSyntaxHighlighter``: it sets character formats
        only, so the buffer, the file on disk and the undo stack are exactly
        what they were before the switch was flipped.
        """
        if theme is not None:
            self._theme_name = "dark" if theme == "dark" else "light"
        if not enabled:
            if self._markdown is not None:
                self._markdown.setDocument(None)
                self._markdown.deleteLater()
                self._markdown = None
                self.viewport().update()
            return
        if self._markdown is None:
            self._markdown = MarkdownDecorator(self.document(),
                                               self._theme_name, self.font())
            self._markdown.set_active_block(self.textCursor().blockNumber())
        else:
            self._markdown.set_theme(self._theme_name)
        self.viewport().update()

    def live_markdown_enabled(self) -> bool:
        return self._markdown is not None

    def markdown_decorator(self) -> Optional[MarkdownDecorator]:
        return self._markdown

    def _sync_markdown_caret(self) -> None:
        if self._markdown is not None:
            self._markdown.set_active_block(self.textCursor().blockNumber())

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        super().paintEvent(event)
        decorator = self._markdown
        if decorator is None:
            return
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        decorator.paint(painter, self, self.firstVisibleBlock(),
                        self.contentOffset(),
                        QRectF(0, 0, self.viewport().width(),
                               self.viewport().height()))
        painter.end()

    # ==================================================================
    # syntax highlighting
    # ==================================================================
    def set_syntax_highlighting(self, enabled: bool,
                                language: Optional[str] = None,
                                theme: str = "light") -> None:
        if language:
            self._language = language
        if not enabled:
            if self._highlighter is not None:
                self._highlighter.setDocument(None)
                self._highlighter.deleteLater()
                self._highlighter = None
            return
        code = self.language_code()
        if self._highlighter is None:
            self._highlighter = SyntaxHighlighter(self.document(), code, theme)
        else:
            self._highlighter.set_theme(theme)
            self._highlighter.set_language(code)

    def syntax_highlighting_enabled(self) -> bool:
        return self._highlighter is not None

    def set_theme_name(self, theme: str) -> None:
        self._theme_name = "dark" if theme == "dark" else "light"
        if self._highlighter is not None:
            self._highlighter.set_theme(theme)
        if self._markdown is not None:
            self._markdown.set_theme(theme)

    def language_code(self) -> str:
        """Concrete language: the override, or guessed from the file name."""
        if self._language and self._language != "auto":
            return self._language
        path = self._doc.path if self._doc is not None else None
        return syntax.language_for_path(path)

    def set_language(self, code: str) -> None:
        self._language = code
        if self._highlighter is not None:
            self._highlighter.set_language(self.language_code())

    def keyReleaseEvent(self, event) -> None:  # noqa: N802
        self.handle_chord_release(_scan_code(event), event.key())
        super().keyReleaseEvent(event)

    # -- seams: tests drive the chord with (scan code, key) directly --------
    def handle_chord_press(self, scan: int, key) -> None:
        self._chord.on_press_codes(scan, key)

    def handle_chord_release(self, scan: int, key) -> Optional[str]:
        mode = self._chord.on_release_codes(scan, key)
        if mode is not None:
            self.apply_direction(mode)
        return mode

    # ==================================================================
    # zoom / font
    # ==================================================================
    def set_font_size(self, size: int) -> None:
        size = max(MIN_FONT_SIZE, min(MAX_FONT_SIZE, size))
        font = self.font()
        if font.pointSize() == size:
            return
        font.setPointSize(size)
        self.setFont(font)
        self._refresh_tab_stop()
        self._update_gutter_width(0)
        self.zoom_changed.emit(self.zoom_percent())

    def _refresh_tab_stop(self) -> None:
        self.setTabStopDistance(
            self.fontMetrics().horizontalAdvance(" ") * self._tab_width)

    def set_tab_width(self, width: int) -> None:
        """Tab stop in characters (1–16)."""
        self._tab_width = max(1, min(16, int(width)))
        self._refresh_tab_stop()

    def tab_width(self) -> int:
        return self._tab_width

    def set_font(self, font: QFont) -> None:
        """Switch typeface/size and keep the zoom baseline in sync."""
        if font.pointSize() > 0:
            self._base_font_size = font.pointSize()
            self._base_font_uses_pixels = False
        elif font.pixelSize() > 0:
            self._base_font_pixels = font.pixelSize()
            self._base_font_uses_pixels = True
        super().setFont(font)
        self._refresh_tab_stop()
        self._update_gutter_width(0)
        if self._markdown is not None:
            self._markdown.set_base_font(font)
        self.zoom_changed.emit(self.zoom_percent())

    def zoom_percent(self) -> int:
        current = self.font().pointSize()
        if current <= 0:                     # a pixel-size font (QSS, DPI scaling)
            current = self.font().pixelSize()
        base = self._base_font_size
        if self._base_font_uses_pixels:
            base = self._base_font_pixels
        if current <= 0 or base <= 0:
            return 100
        return int(round(current / base * 100))

    def zoom_in(self) -> None:
        self.set_font_size((self.font().pointSize() or self._base_font_size) + 1)

    def zoom_out(self) -> None:
        self.set_font_size((self.font().pointSize() or self._base_font_size) - 1)

    def zoom_reset(self) -> None:
        self.set_font_size(self._base_font_size)

    def wheelEvent(self, event) -> None:  # noqa: N802
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self.zoom_in()
            elif delta < 0:
                self.zoom_out()
            event.accept()
            return
        super().wheelEvent(event)

    # ==================================================================
    # view options
    # ==================================================================
    def set_word_wrap(self, enabled: bool) -> None:
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth if enabled
                             else QPlainTextEdit.LineWrapMode.NoWrap)

    def set_line_numbers_visible(self, visible: bool) -> None:
        self._gutter_visible = visible
        if visible and self._gutter is None:
            self._gutter = LineNumberArea(self)
        if self._gutter is not None:
            self._gutter.setVisible(visible)
        self._update_gutter_width(0)
        self._place_gutter()

    def line_numbers_visible(self) -> bool:
        return self._gutter_visible

    def goto_line(self, line: int) -> None:
        line = max(1, min(line, max(1, self.blockCount())))
        block = self.document().findBlockByNumber(line - 1)
        if not block.isValid():
            return
        cursor = QTextCursor(block)
        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
        self.setTextCursor(cursor)
        self.centerCursor()

    # ==================================================================
    # gutter
    # ==================================================================
    def gutter_width(self) -> int:
        if not self._gutter_visible:
            return 0
        digits = max(2, len(str(max(1, self.blockCount()))))
        return 14 + self.fontMetrics().horizontalAdvance("9") * digits

    def _update_gutter_width(self, _=0) -> None:
        start = self.gutter_width() + TEXT_MARGIN
        if self.layoutDirection() == Qt.LayoutDirection.RightToLeft:
            self.setViewportMargins(TEXT_MARGIN, 0, start, 0)
        else:
            self.setViewportMargins(start, 0, TEXT_MARGIN, 0)

    def _update_gutter(self, rect: QRect, dy: int) -> None:
        gutter = self._gutter
        if gutter is None:
            return
        if dy:
            gutter.scroll(0, dy)
        else:
            gutter.update(0, rect.y(), gutter.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_gutter_width(0)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._place_gutter()

    def _place_gutter(self) -> None:
        """Position the gutter on the side matching the text direction."""
        gutter = self._gutter
        if gutter is None:
            return
        cr = self.contentsRect()
        width = self.gutter_width()
        if self.layoutDirection() == Qt.LayoutDirection.RightToLeft:
            x = cr.right() - width + 1
        else:
            x = cr.left()
        gutter.setGeometry(QRect(x, cr.top(), width, cr.height()))

    def paint_gutter(self, event) -> None:
        if not self._gutter_visible or self._gutter is None:
            return
        painter = QPainter(self._gutter)
        painter.fillRect(event.rect(), QColor(0, 0, 0, 0))
        painter.setPen(QColor("#8a8a8a"))
        align = (Qt.AlignmentFlag.AlignLeft if
                 self.layoutDirection() == Qt.LayoutDirection.RightToLeft
                 else Qt.AlignmentFlag.AlignRight)
        gutter_width = self._gutter.width()
        block = self.firstVisibleBlock()
        number = block.blockNumber()
        top = round(self.blockBoundingGeometry(block)
                    .translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        height = self.fontMetrics().height()
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.drawText(4, top, gutter_width - 8, height,
                                 align, str(number + 1))
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            number += 1
        painter.end()

    # ==================================================================
    # status reporting
    # ==================================================================
    def _emit_cursor(self) -> None:
        cursor = self.textCursor()
        self.cursor_moved.emit(cursor.blockNumber() + 1,
                               cursor.columnNumber() + 1,
                               len(cursor.selectedText()))
        if self._direction_mode == AUTO:
            self.setLayoutDirection(self._widget_direction())

    def _emit_stats(self) -> None:
        doc = self.document()
        self.stats_changed.emit(doc.blockCount(), doc.characterCount())

    # ==================================================================
    # find helpers
    # ==================================================================
    def find_text(self, needle: str, backward: bool = False,
                  case_sensitive: bool = False, whole_word: bool = False,
                  regex: bool = False, wrap: bool = True) -> bool:
        if not needle:
            return False
        flags = QTextDocument.FindFlag(0)
        if backward:
            flags |= QTextDocument.FindFlag.FindBackward
        if case_sensitive:
            flags |= QTextDocument.FindFlag.FindCaseSensitively
        if whole_word:
            flags |= QTextDocument.FindFlag.FindWholeWords

        if regex:
            from PySide6.QtCore import QRegularExpression
            options = QRegularExpression.PatternOption(0)
            if not case_sensitive:
                options |= QRegularExpression.PatternOption.CaseInsensitiveOption
            target: object = QRegularExpression(needle, options)
        else:
            target = needle

        if self.find(target, flags):        # type: ignore[arg-type]
            return True
        if not wrap:
            return False
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End if backward
                            else QTextCursor.MoveOperation.Start)
        self.setTextCursor(cursor)
        return bool(self.find(target, flags))  # type: ignore[arg-type]

    def replace_current(self, needle: str, replacement: str,
                        case_sensitive: bool = False) -> bool:
        cursor = self.textCursor()
        if not cursor.hasSelection() or cursor.selectedText() != needle:
            if case_sensitive and cursor.selectedText().lower() != needle.lower():
                return False
        cursor.insertText(replacement)
        return True

    def cursor_rect(self) -> QRect:
        return self.cursorRect()


def _scan_code(event) -> int:
    """Hardware scan code of *event* (0 when the platform gives none)."""
    try:
        return int(event.nativeScanCode())
    except Exception:  # pragma: no cover - platform dependent
        return 0


class _ChordState:
    """Tracks a ``Ctrl+Shift`` tap and reports the direction it means.

    ``None`` is returned unless a *clean* chord finished: both modifiers of
    one side went down, nothing else was pressed in between, and the pair
    came back up inside :data:`CHORD_TIMEOUT_S`.  Right pair → RTL,
    left pair → LTR.  Any other key (``Ctrl+Shift+N``, plain typing, a
    mouse click) marks the chord dirty so the desktop's own use of
    ``Ctrl+Shift`` for keyboard-layout switching never touches the text.
    """

    MODIFIER_KEYS = (Qt.Key.Key_Control, Qt.Key.Key_Shift)

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.down = {  # currently-held modifier keys, by side
            "ctrl_left": False, "ctrl_right": False,
            "shift_left": False, "shift_right": False,
        }
        self.armed = {"left": False, "right": False}
        self.dirty = False
        self.armed_at = 0.0

    # ---------------------------------------------------------- helpers
    @staticmethod
    def _scan(event) -> int:
        try:
            return int(event.nativeScanCode())
        except Exception:  # pragma: no cover - platform dependent
            return 0

    @staticmethod
    def _side_of(code: int, key) -> Optional[str]:
        """Map an event to ``ctrl_left`` / ``shift_right`` / … or ``None``.

        The *type* comes from ``event.key()`` (reliable everywhere) and only
        the *side* comes from the scan code.  That matters because scan codes
        are not unique across platforms on their own: ``62`` is Right Shift on
        X11/evdev but Right Control on macOS.  Asking "which side is this
        Control/Shift key?" is unambiguous; asking "what is code 62?" is not.
        """
        if key == Qt.Key.Key_Control:
            if code in LEFT_CTRL_CODES:
                return "ctrl_left"
            if code in RIGHT_CTRL_CODES:
                return "ctrl_right"
            return None
        if key == Qt.Key.Key_Shift:
            if code in LEFT_SHIFT_CODES:
                return "shift_left"
            if code in RIGHT_SHIFT_CODES:
                return "shift_right"
            return None
        return None

    def _expired(self) -> bool:
        return bool(self.armed_at) and (time.monotonic() - self.armed_at) > CHORD_TIMEOUT_S

    def _arm_if_ready(self) -> None:
        if self._expired():
            self.armed["left"] = self.armed["right"] = False
            self.dirty = False
            self.armed_at = 0.0
        if self.down["ctrl_left"] and self.down["shift_left"] and not self.armed["left"]:
            self.armed["left"], self.dirty = True, False
            self.armed_at = self.armed_at or time.monotonic()
        if self.down["ctrl_right"] and self.down["shift_right"] and not self.armed["right"]:
            self.armed["right"], self.dirty = True, False
            self.armed_at = self.armed_at or time.monotonic()

    # ---------------------------------------------------------- events
    def on_press(self, event) -> None:
        self.on_press_codes(self._scan(event), event.key())

    def on_release(self, event) -> Optional[str]:
        return self.on_release_codes(self._scan(event), event.key())

    def on_press_codes(self, code: int, key) -> None:
        side = self._side_of(code, key)
        if side is None:
            # Any non-modifier key invalidates the chord (Ctrl+Shift+N, …).
            if key not in self.MODIFIER_KEYS:
                self.dirty = True
            return
        self.down[side] = True
        self._arm_if_ready()

    def on_release_codes(self, code: int, key) -> Optional[str]:
        side = self._side_of(code, key)
        if side is None:
            if key not in self.MODIFIER_KEYS:
                self.dirty = True
            return None

        self.down[side] = False
        result: Optional[str] = None
        for which in ("left", "right"):
            ctrl, shift = f"ctrl_{which}", f"shift_{which}"
            # Fire when the *second* key of an armed pair is released and the
            # first one is still considered held by the OS at that instant.
            if self.armed[which] and not self.dirty and not self._expired():
                if (not self.down[ctrl] and not self.down[shift]):
                    result = LTR if which == "left" else RTL
                    self.armed[which] = False

        if not any(self.down.values()):
            self.reset()
        elif result is not None:
            self.dirty = False
        return result
