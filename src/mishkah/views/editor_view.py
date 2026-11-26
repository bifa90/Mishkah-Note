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

import re
import time
from pathlib import Path
from typing import Optional, Tuple

from PySide6.QtCore import QMargins, QPoint, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QKeySequence,
    QPainter,
    QTextBlockFormat,
    QTextCursor,
    QTextDocument,
)
from PySide6.QtWidgets import (
    QApplication,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPlainTextEdit,
)

from mishkah.core import autocomplete, syntax
from mishkah.core.i18n import tr
from mishkah.core.text_direction import (
    AUTO,
    FIRST_LINE,
    FIRST_STRONG,
    LTR,
    RTL,
    SNIFF_CHARS,
    document_side,
    dominant_direction,
    first_strong_is_rtl,
    invisible_spans,
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
#: A single paragraph can be an entire 300 MB preview (large files open as one
#: block).  The diagnostic overlay walks only visible blocks, and this cap
#: stops it from copying one enormous block on every keystroke.
MAX_INVISIBLE_SCAN = 20000
#: Width of one invisible-character marker, in pixels.
MARKER_WIDTH = 3
#: Extra pixels kept free on the right edge so a caret at the start of a
#: right-aligned line is never clipped away.
CARET_GUARD = 8

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

#: How long typing has to pause before the counters and the document side are
#: worked out again (CD-07).  One pass per burst instead of one per keystroke.
STATS_IDLE_MS = 150

#: Extra lines the live Markdown layer decorates above and below the viewport
#: (CD-07).  Anything further away cannot be seen, so it is not parsed.
MARKDOWN_WINDOW_LINES = 400

#: A dropped file larger than this opens in its own tab instead of being
#: pasted into the buffer (CD-22).
DROP_PASTE_LIMIT = 2 * 1024 * 1024

#: How long typing has to pause before the content sniffs its own language.
LANGUAGE_DETECT_MS = 400

#: Longest paragraph prefix inspected when pairing a bracket (CD-03).
PAIR_SCAN_LIMIT = 4096

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
    direction_changed = Signal(str)          # auto | rtl | ltr (mode changed)
    resolved_direction_changed = Signal(str)  # the caret moved to another direction
    stats_changed = Signal(int, int)
    language_detected = Signal(str)      # CD-12: guessed from the content
    files_dropped = Signal(list)         # CD-22: too big/binary to paste         # lines, chars
    find_requested = Signal()            # the context menu asks the window
    replace_requested = Signal()
    goto_requested = Signal()

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
        # Document margin (not viewport margin) is what insets the *text*:
        # right-aligned text ends on the document's inner edge, so without it
        # a caret at the start of an RTL line lands exactly on the viewport's
        # right edge and Qt clips it away.
        self.document().setDocumentMargin(TEXT_MARGIN + CARET_GUARD)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(" ") * self._tab_width)
        self.setMouseTracking(True)

        # --- direction state -------------------------------------------------
        self._direction_mode = document.direction_mode or AUTO
        self._last_resolved = ""
        self._document_side = None
        self._top_inset = 0                   # room reserved for a banner
        self._side_source = FIRST_STRONG      # CD-20, set from the settings
        self._side_locked = False             # "first_line" keeps re-deciding
        self._side_updating = False           # guards against re-entry
        self._chord = _ChordState()
        #: True while only formats are being changed (direction pass).  A
        #: format-only change must never mark the document as edited (B1).
        self._formatting = False

        # --- deferred work (CD-07) -------------------------------------------
        # Counting the buffer and re-deciding the document side on every
        # keystroke is what made a big paste feel sticky.  Both are now one
        # pass per typing burst instead of one per character.
        self._stats_timer = QTimer(self)
        self._stats_timer.setSingleShot(True)
        self._stats_timer.setInterval(STATS_IDLE_MS)
        self._stats_timer.timeout.connect(self._emit_stats)
        self._alignment_timer = QTimer(self)
        self._alignment_timer.setSingleShot(True)
        self._alignment_timer.setInterval(STATS_IDLE_MS)
        self._alignment_timer.timeout.connect(self._sync_auto_alignment)
        self._markdown_window = None

        # --- editing conveniences -------------------------------------------
        self._auto_close = True
        self._auto_indent = True
        self._word_completion = True
        self._indent_unit = autocomplete.DEFAULT_INDENT
        self._highlighter: Optional[SyntaxHighlighter] = None
        self._language = "auto"
        self._content_language = syntax.PLAIN.code
        #: Guessing the language is debounced: a paste or a burst of typing
        #: ends with one sniff, not one per character (CD-12).
        self._detect_timer = QTimer(self)
        self._detect_timer.setSingleShot(True)
        self._detect_timer.setInterval(LANGUAGE_DETECT_MS)
        self._detect_timer.timeout.connect(self.detect_language)
        self._completion: Optional[QListWidget] = None

        # --- live Markdown (view-only decoration) ---------------------------
        self._markdown: Optional[MarkdownDecorator] = None
        self._theme_name = "light"

        # --- gutter ----------------------------------------------------------
        # Created lazily: Windows 11 Mishkah Note shows no gutter by default, so
        # most editors never need the extra child widget at all.
        self._gutter: Optional[LineNumberArea] = None
        self._gutter_visible = False
        self._show_invisible = False
        self.blockCountChanged.connect(self._update_gutter_width)
        self.updateRequest.connect(self._update_gutter)

        self.cursorPositionChanged.connect(self._emit_cursor)
        self.cursorPositionChanged.connect(self._sync_markdown_caret)
        self.verticalScrollBar().valueChanged.connect(self._update_markdown_window)
        self.selectionChanged.connect(self._emit_cursor)
        self.document().contentsChanged.connect(self._schedule_stats)
        self.document().contentsChanged.connect(self._schedule_language_detection)
        self.document().contentsChanged.connect(self._schedule_alignment)

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
        self._document_side = None          # a new buffer gets a new decision
        self._side_locked = True            # a loaded file is not "one line"
        # The buffer knows its language the moment it is loaded: no waiting
        # for the debounce, so a file opens with the right grammar.
        self._content_language = syntax.language_for_text(
            text[:syntax.SNIFF_TEXT_LIMIT])
        self._sync_auto_alignment()
        self._emit_stats()

    # ==================================================================
    # text direction
    # ==================================================================
    def in_formatting_pass(self) -> bool:
        """True while the direction pass is rewriting formats, not text."""
        return self._formatting

    def apply_direction(self, mode: str, announce: bool = True) -> None:
        """Set the base direction of *every* paragraph (the real fix)."""
        was_modified = self.document().isModified()
        self._formatting = True
        try:
            self._apply_direction(mode, announce)
        finally:
            self._formatting = False
            # Choosing a side is a view decision: the file on disk did not
            # change, so the tab must not show as modified (B1).
            self.document().setModified(was_modified)

    def _apply_direction(self, mode: str, announce: bool = True) -> None:
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

        # An explicit mode owns the widget direction, so the gutter and the
        # scrollbar move to the matching side.  "auto" deliberately leaves the
        # widget alone: see _sync_auto_alignment for why.
        if mode == AUTO:
            self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
            self._document_side = None
            self._sync_auto_alignment()     # decides from the text, once
        else:
            self._document_side = mode
            self.setLayoutDirection(_TO_QT_DIRECTION[mode])
            self._apply_alignment(mode)
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
        """Decide the document's side once, then leave it alone.

        Reported after the second hands-on test: following the caret flipped
        the whole document every time the caret crossed a paragraph, which is
        far worse than a minority line sitting on the "wrong" side.  So the
        side is chosen from the document's beginning (``document_side``), and
        never while the caret moves.

        With ``first_line`` (CD-20) the choice stays open *while the buffer is
        a single line*: the first line you are typing is the one that decides,
        so starting a paragraph in another script flips the side until a
        second line exists.  From then on the document is committed.
        """
        if self._direction_mode != AUTO or self._side_updating:
            return
        if self.document().isEmpty():
            # An emptied buffer is a new document: nothing is committed yet.
            self._document_side = None
            self._side_locked = False
            return
        if (self._document_side is not None and not self._side_locked
                and self._side_source == FIRST_LINE
                and self.document().blockCount() <= 1):
            self._document_side = None      # still on the first line: re-decide
        if self._document_side is None:
            self._lock_document_side()

    def set_document_side_source(self, source: str) -> None:
        """Switch between the two ways of choosing a document's side (CD-20)."""
        source = source if source in (FIRST_LINE, FIRST_STRONG) else FIRST_STRONG
        if source == self._side_source:
            return
        self._side_source = source
        self._document_side = None
        self._side_locked = False
        self._sync_auto_alignment()

    def document_side_source(self) -> str:
        return self._side_source

    def _lock_document_side(self) -> None:
        """Choose the side for this document (only called when unlocked)."""
        if self._side_source == FIRST_LINE:
            # The ``first_line`` rule only ever looks at the first line: an
            # unlocked (still being written) document used to read 64 kB per
            # keystroke just to decide which side that one line is on (CD-07).
            text = self.document().firstBlock().text()
        else:
            text = self._leading_text(limit=SNIFF_CHARS * 16)
        if first_strong_is_rtl(text) is None:
            return                          # still neutral: nothing to decide
        side = document_side(text, self._side_source)
        self._side_locked = not (self._side_source == FIRST_LINE
                                 and self.document().blockCount() <= 1)
        self._side_updating = True
        try:
            self._document_side = side
            self._apply_alignment(side)
            self._update_gutter_width(0)
            self._place_gutter()
            self.viewport().update()
        finally:
            self._side_updating = False

    def document_side(self) -> str:
        """The side this document is laid out on (``rtl`` or ``ltr``)."""
        return self._document_side or LTR

    def _widget_direction(self) -> Qt.LayoutDirection:
        return _TO_QT_DIRECTION[self.document_direction()]

    def resolved_direction(self) -> str:
        """Direction of the paragraph the caret is in (``auto`` mode).

        Three rules, in this order:

        1. the caret's own paragraph, from its first strong character;
        2. a blank paragraph inherits the direction of the paragraph above it,
           which is what happens when you press Enter at the end of an English
           line — the new line keeps writing English instead of snapping back
           to whatever the file happens to start with;
        3. a document that is still neutral everywhere falls back to its
           opening text, so an Arabic file says RTL even on an empty line.
        """
        if self._direction_mode != AUTO:
            return self._direction_mode
        block = self.textCursor().block()
        text = block.text()
        verdict = first_strong_is_rtl(text)
        if verdict is not None:
            return RTL if verdict else LTR
        if not text.strip():
            previous = block.previous()
            hops = 0
            while previous.isValid() and hops < 50:
                verdict = first_strong_is_rtl(previous.text())
                if verdict is not None:
                    return RTL if verdict else LTR
                previous = previous.previous()
                hops += 1
        return self._document_side or dominant_direction(self._leading_text())

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

        # Shift+Tab first: some platforms report it as Tab with the shift
        # modifier rather than as Backtab, and the old order inserted a tab
        # where the user asked to outdent (M5).
        if (key == Qt.Key.Key_Backtab
                or (key == Qt.Key.Key_Tab
                    and modifiers & Qt.KeyboardModifier.ShiftModifier)):
            self.indent_selection(outdent=True)
            return True
        if key == Qt.Key.Key_Tab:
            if self.textCursor().hasSelection():
                self.indent_selection()
            else:
                self.textCursor().insertText(self._indent_unit)
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
    def neighbour_chars(self) -> Tuple[str, str]:
        """The characters either side of the caret, read without a copy.

        ``self.toPlainText()`` copies the whole buffer; at 5 MB that was the
        expensive part of typing ``(`` or pressing Backspace (CD-07).
        """
        cursor = self.textCursor()
        before = after = ""
        back = QTextCursor(cursor)
        if back.movePosition(QTextCursor.MoveOperation.PreviousCharacter,
                             QTextCursor.MoveMode.KeepAnchor):
            before = back.selectedText().replace("\u2029", "\n")[-1:]
        ahead = QTextCursor(cursor)
        if ahead.movePosition(QTextCursor.MoveOperation.NextCharacter,
                              QTextCursor.MoveMode.KeepAnchor):
            after = ahead.selectedText().replace("\u2029", "\n")[:1]
        return before, after

    def paragraph_prefix(self, limit: int = PAIR_SCAN_LIMIT) -> str:
        """The current paragraph's text up to the caret, capped at *limit*."""
        cursor = QTextCursor(self.textCursor())
        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock,
                            QTextCursor.MoveMode.KeepAnchor)
        text = cursor.selectedText().replace("\u2029", "\n")
        return text[-limit:] if limit and len(text) > limit else text

    def _apply_pairing(self, char: str) -> bool:
        cursor = self.textCursor()
        selected = cursor.hasSelection()
        if selected:
            before, after = "", ""
        else:
            before, after = self.neighbour_chars()

        if autocomplete.should_skip_closer(char, after):
            cursor.movePosition(QTextCursor.MoveOperation.Right)
            self.setTextCursor(cursor)
            return True

        if not autocomplete.should_pair(char, before, after, has_selection=selected):
            return False
        if (not selected and autocomplete.has_unclosed_opener(
                self.paragraph_prefix(), char)):
            # CD-03: an opener of this kind is still open in this paragraph,
            # so the user is typing around it — no second closing bracket.
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
        before, after = self.neighbour_chars()
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
    def insertFromMimeData(self, source) -> None:  # noqa: N802 - Qt naming
        """Dropping a file on the text pastes its content (CD-22).

        The default handler writes the file's *path* into the buffer, which is
        never what someone dragging a note onto the page wants.  Text files up
        to :data:`DROP_PASTE_LIMIT` are inserted; anything else (binary, huge)
        is handed to the controller, which opens it in a tab instead.
        """
        paths = []
        if source is not None and source.hasUrls():
            paths = [url.toLocalFile() for url in source.urls()
                     if url.isLocalFile() and url.toLocalFile()]
        if not paths:
            super().insertFromMimeData(source)
            return

        from mishkah.core import large_file

        texts = []
        refused = []
        for path in paths:
            try:
                target = Path(path)
                if not target.is_file() or target.stat().st_size > DROP_PASTE_LIMIT:
                    refused.append(path)
                    continue
                with open(target, "rb") as handle:
                    head = handle.read(8192)
                if large_file.looks_binary(head):
                    refused.append(path)
                    continue
                texts.append(target.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                refused.append(path)
        if texts:
            body = "\n".join(text.rstrip("\n") for text in texts)
            cursor = self.textCursor()
            cursor.beginEditBlock()
            if self.document().characterCount() > 1:
                cursor.insertText("\n" + body + "\n")
            else:
                cursor.insertText(body)
            cursor.endEditBlock()
            self.setTextCursor(cursor)
        if refused:
            self.files_dropped.emit(refused)

    def build_context_menu(self):
        """The right-click menu, built here so it speaks the UI language.

        ``createStandardContextMenu()`` fills the menu from Qt's own
        translations, which we do not ship: it stayed English however the
        interface was set.  Building it ourselves keeps every label in
        ``tr()`` — Arabic included — and gives a stable, grouped order:
        history, then clipboard, then selection, then search.

        The actions carry an object name and are dispatched by
        :meth:`apply_menu_action` on the chosen one instead of holding Python
        callbacks: a menu with connected lambdas keeps reference cycles that
        outlive the tab, and PySide trips over them at shutdown.
        """
        menu = QMenu(self)
        cursor = self.textCursor()
        has_selection = cursor.hasSelection()
        clipboard_text = QApplication.clipboard().text()

        def add(text_key: str, shortcuts, enabled: bool = True):
            action = menu.addAction(tr(text_key))
            if shortcuts:
                action.setShortcuts([QKeySequence(key) for key in shortcuts])
            action.setEnabled(enabled)
            action.setObjectName(text_key)
            return action

        # 1. history
        add("action.undo", ["Ctrl+Z"], self.document().isUndoAvailable())
        add("action.redo", ["Ctrl+Y", "Ctrl+Shift+Z"],
            self.document().isRedoAvailable())
        menu.addSeparator()
        # 2. clipboard — plain paste right after paste, so it is easy to reach
        add("action.cut", ["Ctrl+X"], has_selection)
        add("action.copy", ["Ctrl+C"], has_selection)
        add("action.paste", ["Ctrl+V"], bool(clipboard_text))
        add("action.paste_plain", ["Ctrl+Shift+V"], bool(clipboard_text))
        add("action.delete", ["Del"], not self.isReadOnly())
        menu.addSeparator()
        # 3. selection
        add("action.select_all", ["Ctrl+A"], not self.document().isEmpty())
        menu.addSeparator()
        # 4. search — the window owns the bars, so these are signals
        add("action.find", ["Ctrl+F"])
        add("action.replace", ["Ctrl+H"])
        add("action.goto", ["Ctrl+G"])
        return menu

    def apply_menu_action(self, name: str) -> bool:
        """Run one entry of the right-click menu by its object name."""
        actions = {
            "action.undo": self.undo,
            "action.redo": self.redo,
            "action.cut": self.cut,
            "action.copy": self.copy,
            "action.paste": self.paste,
            "action.paste_plain": self.paste_plain,
            "action.delete": self._delete_forward,
            "action.select_all": self.selectAll,
            "action.find": lambda: self.find_requested.emit(),
            "action.replace": lambda: self.replace_requested.emit(),
            "action.goto": lambda: self.goto_requested.emit(),
        }
        handler = actions.get(name)
        if handler is None:
            return False
        handler()
        return True

    def _delete_forward(self) -> None:
        """Delete the selection, or the character after the caret (Del)."""
        cursor = self.textCursor()
        if cursor.hasSelection():
            cursor.removeSelectedText()
        else:
            cursor.deleteChar()
        self.setTextCursor(cursor)

    def contextMenuEvent(self, event) -> None:  # noqa: N802 - Qt naming
        menu = self.build_context_menu()
        chosen = menu.exec(event.globalPos())
        menu.deleteLater()
        if chosen is not None:
            self.apply_menu_action(chosen.objectName())

    def paste_plain(self) -> bool:
        """Paste the clipboard as text only (CD-13).

        Rich text from a browser would arrive with fonts and colours that the
        buffer cannot keep anyway; taking the plain flavour is what users
        mean by "paste without formatting".
        """
        from PySide6.QtGui import QGuiApplication

        clipboard = QGuiApplication.clipboard()
        mime = clipboard.mimeData() if clipboard is not None else None
        text = clipboard.text() if clipboard is not None else ""
        if mime is not None and not text and mime.hasUrls():
            text = "\n".join(url.toLocalFile() or url.toString()
                              for url in mime.urls())
        if not text:
            return False
        cursor = self.textCursor()
        cursor.beginEditBlock()
        cursor.insertText(text)
        cursor.endEditBlock()
        self.setTextCursor(cursor)
        return True

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
        was_modified = self.document().isModified()
        self._formatting = True
        if self._markdown is None:
            self._markdown = MarkdownDecorator(self.document(),
                                               self._theme_name, self.font())
            self._markdown.set_window(*self._markdown_window_range())
            self._markdown.invalidate_cache()
            self._markdown.set_active_block(self.textCursor().blockNumber())
        else:
            self._markdown.set_theme(self._theme_name)
        self._formatting = False
        self.document().setModified(was_modified)
        self.viewport().update()

    def live_markdown_enabled(self) -> bool:
        return self._markdown is not None

    def markdown_decorator(self) -> Optional[MarkdownDecorator]:
        return self._markdown

    def _sync_markdown_caret(self) -> None:
        if self._markdown is not None:
            self._update_markdown_window()
            self._markdown.set_active_block(self.textCursor().blockNumber())

    def _markdown_window_range(self) -> Tuple[int, int]:
        """Blocks worth decorating: the visible ones plus a margin (CD-07)."""
        first = self.cursorForPosition(QPoint(0, 0)).blockNumber()
        height = max(1, self.viewport().height())
        last = self.cursorForPosition(QPoint(0, height - 1)).blockNumber()
        if last < first:
            last = first
        last_block = max(0, self.document().blockCount() - 1)
        return (max(0, first - MARKDOWN_WINDOW_LINES),
                min(last_block, last + MARKDOWN_WINDOW_LINES))

    def _update_markdown_window(self, _value: int = 0) -> None:
        """Re-highlight only when the viewport moved past the margin."""
        decorator = self._markdown
        if decorator is None:
            return
        if decorator.set_window(*self._markdown_window_range()):
            decorator.invalidate_cache()
            decorator.rehighlight()

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        super().paintEvent(event)
        decorator = self._markdown
        if decorator is None:
            if self._show_invisible:
                painter = QPainter(self.viewport())
                self._paint_invisible_marks(painter)
                painter.end()
            return
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        decorator.paint(painter, self, self.firstVisibleBlock(),
                        self.contentOffset(),
                        QRectF(0, 0, self.viewport().width(),
                               self.viewport().height()))
        if self._show_invisible:
            self._paint_invisible_marks(painter)
        painter.end()

    # ==================================================================
    # syntax highlighting
    # ==================================================================
    def set_syntax_highlighting(self, enabled: bool,
                                language: Optional[str] = None,
                                theme: str = "light") -> None:
        """Colour the buffer with *language* (or the language we infer).

        The language passed in is applied to the highlighter only — it is not
        remembered as a user choice, otherwise the first guess would freeze
        and later content detection could never correct it (CD-12).
        """
        was_modified = self.document().isModified()
        self._formatting = True                 # formats only, not an edit
        try:
            if not enabled:
                if self._highlighter is not None:
                    self._highlighter.setDocument(None)
                    self._highlighter.deleteLater()
                    self._highlighter = None
                return
            code = language or self.language_code()
            if self._highlighter is None:
                self._highlighter = SyntaxHighlighter(self.document(), code, theme)
            else:
                self._highlighter.set_theme(theme)
                self._highlighter.set_language(code)
        finally:
            self._formatting = False
            self.document().setModified(was_modified)

    def syntax_highlighting_enabled(self) -> bool:
        return self._highlighter is not None

    def set_theme_name(self, theme: str) -> None:
        self._theme_name = "dark" if theme == "dark" else "light"
        if self._highlighter is not None:
            self._highlighter.set_theme(theme)
        if self._markdown is not None:
            self._markdown.set_theme(theme)

    def language_code(self) -> str:
        """Concrete language: override, file name, then the content itself.

        The third step is what makes pasted code light up in an untitled
        buffer: until it is saved, a file name says nothing (CD-12).
        """
        if self._language and self._language != "auto":
            return self._language
        # The tab's own choice (View ▸ Language) lives on the document, so it
        # survives a reload and is not tied to this widget.
        chosen = getattr(self._doc, "language", "auto") if self._doc else "auto"
        if chosen and chosen != "auto":
            return chosen
        path = self._doc.path if self._doc is not None else None
        by_path = syntax.language_for_path(path)
        if by_path != syntax.PLAIN.code:
            return by_path
        return self._content_language or syntax.PLAIN.code

    def detected_language(self) -> str:
        """The language the content looks like, ``plain`` when unsure."""
        return self._content_language

    def _schedule_language_detection(self) -> None:
        if not self._detect_timer.isActive():
            self._detect_timer.start()

    def detect_language(self) -> str:
        """Sniff the buffer and report a newly guessed language (CD-12)."""
        self._detect_timer.stop()
        text = self._leading_text(limit=syntax.SNIFF_TEXT_LIMIT)
        guess = syntax.language_for_text(text)
        if guess == self._content_language:
            return guess
        self._content_language = guess
        self.language_detected.emit(guess)
        return guess

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

    # -- diagnostics: show invisible characters (CD-16) -----------------
    def set_top_inset(self, pixels: int) -> None:
        """Reserve room at the top so a banner never covers the first line."""
        pixels = max(0, int(pixels))
        if pixels == self._top_inset:
            return
        self._top_inset = pixels
        self._update_gutter_width(0)

    def top_inset(self) -> int:
        return self._top_inset

    def set_show_invisible_chars(self, enabled: bool) -> None:
        """Draw a marker where a zero-width character sits.

        The characters this reveals (RLM, ZWNJ, BOM, …) have **no width**, so
        tinting their background paints nothing at all — the first version of
        this feature did exactly that and showed nothing.  The marks are drawn
        in paintEvent instead, one thin bar per character, and the document is
        never modified.
        """
        enabled = bool(enabled)
        if enabled == self._show_invisible:
            return
        self._show_invisible = enabled
        self.viewport().update()

    def show_invisible_chars(self) -> bool:
        return self._show_invisible

    def _visible_blocks(self):
        """Blocks that intersect the viewport, top to bottom.

        A widget that has not been shown yet (tests, the moment before the
        first paint) reports a zero-height viewport; treat that as "a screen
        worth of text" rather than as "nothing to mark".
        """
        offset = self.contentOffset()
        bottom_limit = self.viewport().height()
        if bottom_limit <= 0:
            bottom_limit = self.fontMetrics().lineSpacing() * 200
        block = self.firstVisibleBlock()
        while block.isValid():
            top = self.blockBoundingGeometry(block).translated(offset).top()
            if top > bottom_limit:
                break
            if block.isVisible():
                yield block
            block = block.next()

    def count_invisible_chars(self, limit: int = 4_000_000) -> int:
        """How many invisible characters this document holds (for the banner)."""
        text = self.toPlainText()[:limit]
        return len(invisible_spans(text))

    def invisible_mark_rects(self) -> list:
        """Viewport rectangles where a marker must be drawn (empty when off)."""
        rects = []
        if not self._show_invisible:
            return rects
        for block in self._visible_blocks():
            if block.length() - 1 > MAX_INVISIBLE_SCAN:
                continue                      # a whole-file paragraph: skip
            text = block.text()
            if not text:
                continue
            for start, _length, _name in invisible_spans(text):
                cursor = QTextCursor(block)
                cursor.setPosition(block.position() + start)
                rect = self.cursorRect(cursor)
                rects.append(QRect(rect.x(), rect.y(),
                                   MARKER_WIDTH, max(1, rect.height())))
        return rects

    def _paint_invisible_marks(self, painter: QPainter) -> None:
        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 102, 0))
        for rect in self.invisible_mark_rects():
            painter.drawRect(rect)
        painter.restore()

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

    def _gutter_on_the_right(self) -> bool:
        """Which side the gutter belongs to.

        In auto mode the widget itself stays left-to-right (so Qt resolves
        every paragraph from its own text), but the *document* still has a
        side — and the numbers must sit on that side, as they would in a
        right-to-left editor.  An explicit mode decides it outright.
        """
        if self._direction_mode == AUTO:
            return self.document_side() == RTL
        return self.layoutDirection() == Qt.LayoutDirection.RightToLeft

    def _update_gutter_width(self, _=0) -> None:
        """Reserve the gutter's side plus equal breathing room on both edges.

        Both margins are always ``TEXT_MARGIN`` or larger, so the first
        character of a line — and the caret sitting on it — is never clipped
        against the viewport, in either direction, with or without a gutter.
        """
        edge = self.gutter_width() + TEXT_MARGIN
        if self._gutter_on_the_right():
            wanted = QMargins(TEXT_MARGIN, self._top_inset, edge, 0)
        else:
            wanted = QMargins(edge, self._top_inset, TEXT_MARGIN, 0)
        # Setting the same margins again re-triggers the viewport update that
        # asked for them in the first place; bail out while they already match.
        if self.viewportMargins() == wanted:
            return
        self.setViewportMargins(wanted.left(), wanted.top(), wanted.right(), 0)

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
        self._update_markdown_window()

    def _place_gutter(self) -> None:
        """Position the gutter on the side matching the text direction."""
        gutter = self._gutter
        if gutter is None:
            return
        cr = self.contentsRect()
        width = self.gutter_width()
        if self._gutter_on_the_right():
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
        align = (Qt.AlignmentFlag.AlignLeft if self._gutter_on_the_right()
                 else Qt.AlignmentFlag.AlignRight)
        gutter_width = self._gutter.width()
        offset = self.contentOffset()
        block = self.firstVisibleBlock()
        # Each block is measured from its own geometry.  Accumulating rounded
        # heights drifts by a pixel every few hundred paragraphs (CD-11), and
        # a wrapped or Markdown-spaced paragraph is taller than the font box.
        while block.isValid():
            top = round(self.blockBoundingGeometry(block).translated(offset).top())
            if top > event.rect().bottom():
                break
            height = round(self.blockBoundingRect(block).height())
            if block.isVisible() and top + height >= event.rect().top():
                layout = block.layout()
                if layout is not None and layout.lineCount():
                    line = layout.lineAt(0)
                    line_top = top + round(line.y())
                    line_height = max(1, round(line.height()))
                else:                      # pragma: no cover - layout not ready
                    line_top, line_height = top, self.fontMetrics().height()
                # One number per paragraph, on its first visual line: wrapping
                # adds lines but never a second number.
                painter.drawText(QRect(4, line_top, gutter_width - 8, line_height),
                                 align | Qt.AlignmentFlag.AlignTop,
                                 str(block.blockNumber() + 1))
            block = block.next()
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
            # A committed side is never re-decided while the caret moves; only
            # a document whose side can still change (an unlocked first line)
            # is decided here, and that read is one line long (CD-07).
            if not self._side_locked:
                self._sync_auto_alignment()
            resolved = self.resolved_direction()
            if resolved != self._last_resolved:
                self._last_resolved = resolved
                # Visible proof that detection is per paragraph even where Qt
                # cannot align per paragraph: the status chip follows the caret.
                self.resolved_direction_changed.emit(resolved)

    def _schedule_stats(self) -> None:
        """Count once the typing stops (CD-07)."""
        if not self._stats_timer.isActive():
            self._stats_timer.start()

    def _emit_stats(self) -> None:
        self._stats_timer.stop()
        doc = self.document()
        self.stats_changed.emit(doc.blockCount(), doc.characterCount())

    def _schedule_alignment(self) -> None:
        """Re-decide the document side after the burst, not during it."""
        if self.document().isEmpty():
            # An emptied buffer is a new document: forget the old side now,
            # so the very next character decides it again.
            self._sync_auto_alignment()
            return
        if not self._alignment_timer.isActive():
            self._alignment_timer.start()

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

    @staticmethod
    def selection_matches(selected: str, needle: str, case_sensitive: bool = False,
                          whole_word: bool = False, regex: bool = False) -> bool:
        """Does *selected* really match *needle* under these options? (B3)"""
        if not needle:
            return False
        pattern = needle if regex else re.escape(needle)
        if whole_word:
            pattern = rf"(?<!\w)(?:{pattern})(?!\w)"
        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            compiled = re.compile(pattern, flags)
        except re.error:
            return False
        # fullmatch, so a selection that merely *contains* the needle (the
        # replaced-all-the-wrong-text bug) is refused.
        return compiled.fullmatch(selected) is not None

    def replace_current(self, needle: str, replacement: str,
                        case_sensitive: bool = False, whole_word: bool = False,
                        regex: bool = False) -> bool:
        """Replace the selection, but only when it is a real match (B3).

        The old code replaced whatever was selected: with *whole word* on, a
        hit was found inside ``concatenate`` and the whole word was wiped.
        """
        cursor = self.textCursor()
        if not cursor.hasSelection():
            return False
        selected = cursor.selectedText().replace("\u2029", "\n")
        if not self.selection_matches(selected, needle, case_sensitive,
                                      whole_word, regex):
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
