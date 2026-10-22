"""Live Markdown rendering — decoration only, never an edit.

The mode is a *view*: it paints the buffer that is already there.  Nothing in
this module writes to the document, so

* ``QPlainTextEdit.toPlainText()`` is byte-for-byte what it was before the
  mode was switched on,
* the undo stack is untouched, and
* turning the mode off leaves the file exactly as the user typed it.

How the Markdown syntax disappears
----------------------------------
``QSyntaxHighlighter`` can only change *formats*, so the decorator exploits two
font properties:

``collapse``
    The run is painted in the editor's own background colour and its letter
    spacing is set to ``-advance / length``.  Qt then gives the run zero
    advance width, so ``**bold**`` lays out exactly like ``bold`` (verified
    against ``QFontMetricsF``: both lines report the same width).  Used for
    ``**``, ``_``, ``#``, ```` ` ````, ``[``, ``](url)``…
``keep width``
    The run is hidden but keeps its advance, so a glyph can be painted on
    top: the ``-`` of a bullet becomes ``•`` and ``>`` becomes a quote bar.
    Text does not move, and nothing is inserted into the buffer.

Block-level furniture (bullets, quote bars, horizontal rules, table rules) is
painted by the editor through :meth:`MarkdownDecorator.paint`, which reads the
parse result cached on each ``QTextBlock`` as user data.
"""

from __future__ import annotations

from typing import Dict, Optional

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QPainter,
    QPen,
    QSyntaxHighlighter,
    QTextBlock,
    QTextBlockUserData,
    QTextCharFormat,
    QTextDocument,
)

from mishkah.core import markdown

#: Palette per theme: ``colour`` is used for text, ``muted`` for syntax when a
#: block is being edited, ``accent`` for links/bullets and ``surface`` for the
#: background of code spans and quotes.
THEMES: Dict[str, Dict[str, str]] = {
    "light": {
        "surface": "#FFFFFF",
        "text": "#1A1A1A",
        "muted": "#B0B0B0",
        "accent": "#0F6CBD",
        "heading": "#1A1A1A",
        "code_bg": "#F2F4F7",
        "code_text": "#8B1E3F",
        "quote": "#7A7A7A",
        "rule": "#D6D6D6",
        "table": "#444444",
        "table_pipe": "#BBBBBB",
    },
    "dark": {
        "surface": "#1B1B1B",
        "text": "#F2F2F2",
        "muted": "#5A5A5A",
        "accent": "#69B4F5",
        "heading": "#F7F7F7",
        "code_bg": "#262626",
        "code_text": "#F0A0B8",
        "quote": "#9A9A9A",
        "rule": "#4A4A4A",
        "table": "#DADADA",
        "table_pipe": "#5E5E5E",
    },
}

#: Heading sizes relative to the body text.
HEADING_SCALE = (1.55, 1.35, 1.2, 1.1, 1.05, 1.0)
#: Smallest point size that still hides reliably (Qt clamps tiny sizes).
_HIDDEN_POINT_SIZE = 0.75


def _is_block_marker(line: markdown.Line, span: markdown.Span) -> bool:
    """Bullet and quote glyphs stay hidden while the caret is in the line.

    They are painted over by :meth:`MarkdownDecorator.paint`, so revealing
    the raw ``-`` or ``>`` would print two glyphs on top of each other.
    """
    return (line.kind in (markdown.LIST_ITEM, markdown.QUOTE)
            and span.style in (markdown.MARKER, markdown.LIST_MARKER,
                               markdown.TASK_MARKER)
            and span.hidden)


class MarkdownBlockData(QTextBlockUserData):
    """Parse result for one block, cached for the painter."""

    __slots__ = ("line",)

    def __init__(self, line: markdown.Line):
        super().__init__()
        self.line = line


class MarkdownDecorator(QSyntaxHighlighter):
    """Applies the visual Markdown layer to one document."""

    def __init__(self, document: QTextDocument, theme: str = "light",
                 base_font: Optional[QFont] = None):
        super().__init__(document)
        self._theme = "dark" if theme == "dark" else "light"
        self._base_font = QFont(base_font) if base_font is not None else QFont(document.defaultFont())
        self._active_block = -1

    # ------------------------------------------------------------------
    # configuration
    # ------------------------------------------------------------------
    def set_theme(self, theme: str) -> None:
        theme = "dark" if theme == "dark" else "light"
        if theme == self._theme:
            return
        self._theme = theme
        self.rehighlight()

    def theme(self) -> str:
        return self._theme

    def set_base_font(self, font: QFont) -> None:
        """Recompute hidden widths when the editor font changes."""
        self._base_font = QFont(font)
        self.rehighlight()

    def set_active_block(self, number: int) -> None:
        """Reveal the Markdown source of the paragraph under the caret."""
        if number == self._active_block:
            return
        previous, self._active_block = self._active_block, number
        for candidate in (previous, number):
            block = self.document().findBlockByNumber(candidate)
            if block.isValid():
                self.rehighlightBlock(block)

    def active_block(self) -> int:
        return self._active_block

    # ------------------------------------------------------------------
    # highlighting
    # ------------------------------------------------------------------
    def highlightBlock(self, text: str) -> None:  # noqa: N802 (Qt naming)
        block = self.currentBlock()
        if block.blockNumber() > MAX_MARKDOWN_BLOCKS:
            self.setCurrentBlockUserData(None)
            return
        line, _ = self._parse(block)
        self.setCurrentBlockUserData(MarkdownBlockData(line))

        active = block.blockNumber() == self._active_block
        for span in line.spans:
            reveal = active and not _is_block_marker(line, span)
            fmt = self._format(line, span, reveal)
            if fmt is not None:
                self.setFormat(span.start, span.length, fmt)

    def _parse(self, block: QTextBlock):
        """Parse *block*, recovering the fence state from the lines above it.

        ``QSyntaxHighlighter`` may call ``highlightBlock`` for a single block
        (the caret moved), so the streaming state of a full pass cannot be
        trusted.  Replaying a bounded window above the block is cheap and
        keeps fenced code correct after any edit.
        """
        window = min(block.blockNumber(), _STATE_WINDOW)
        start = block.blockNumber() - window
        state = markdown._State()  # noqa: SLF001 - module-internal state object
        current = self.document().findBlockByNumber(start)
        for _ in range(window):
            _, state = markdown.parse_line(current.text(), current.next().text()
                                           if current.next().isValid() else None,
                                           state)
            current = current.next()
        following = block.next().text() if block.next().isValid() else None
        return markdown.parse_line(block.text(), following, state)

    # ------------------------------------------------------------------
    # formats
    # ------------------------------------------------------------------
    def _colour(self, name: str) -> QColor:
        return QColor(THEMES[self._theme][name])

    def _format(self, line: markdown.Line, span: markdown.Span,
                reveal: bool) -> Optional[QTextCharFormat]:
        if span.hidden:
            return self._hidden_format(line, span, reveal)

        fmt = QTextCharFormat()
        base = self._base_font
        style = span.style

        if style == markdown.CODE and line.kind == markdown.FENCE:
            fmt.setBackground(self._colour("code_bg"))
            return fmt
        if style == markdown.HEADING_TEXT:
            scaled = QFont(base)
            scale = HEADING_SCALE[min(max(line.level, 1), 6) - 1]
            size = (base.pointSizeF() if base.pointSizeF() > 0
                    else float(base.pixelSize()))
            if size > 0:
                scaled.setPointSizeF(max(1.0, size * scale))
            fmt.setFont(scaled, QTextCharFormat.FontPropertiesSpecifiedOnly)
            fmt.setFontWeight(QFont.Weight.DemiBold)
            fmt.setForeground(self._colour("heading"))
            return fmt
        if style == markdown.BOLD:
            fmt.setFontWeight(QFont.Weight.Bold)
        elif style == markdown.ITALIC:
            fmt.setFontItalic(True)
        elif style == markdown.STRIKE:
            fmt.setFontStrikeOut(True)
            fmt.setForeground(self._colour("quote"))
        elif style == markdown.CODE:
            mono = QFont(base)
            mono.setFamilies(["JetBrains Mono", "DejaVu Sans Mono", "Consolas",
                              "Liberation Mono", "monospace"])
            fmt.setFontFamilies(mono.families())
            fmt.setForeground(self._colour("code_text"))
            fmt.setBackground(self._colour("code_bg"))
        elif style == markdown.LINK:
            fmt.setForeground(self._colour("accent"))
            fmt.setFontUnderline(True)
        elif style == markdown.QUOTE_TEXT:
            fmt.setForeground(self._colour("quote"))
            fmt.setFontItalic(True)
        elif style == markdown.TABLE_TEXT:
            fmt.setForeground(self._colour("table"))
        elif style == markdown.TABLE_PIPE:
            fmt.setForeground(self._colour("table_pipe"))
        elif style == markdown.LIST_MARKER:
            # Ordered markers (``1.``) are meaningful: keep them, tint them.
            fmt.setForeground(self._colour("accent"))
            fmt.setFontWeight(QFont.Weight.DemiBold)
        return fmt

    def _hidden_format(self, line: markdown.Line, span: markdown.Span,
                       reveal: bool) -> QTextCharFormat:
        fmt = QTextCharFormat()
        if reveal:
            # Editing this paragraph: show the syntax again, greyed out.
            fmt.setForeground(self._colour("muted"))
            if line.kind == markdown.FENCE:
                fmt.setBackground(self._colour("code_bg"))
            return fmt

        if line.kind == markdown.FENCE:
            # The ``` line keeps its height (the block still reads as a
            # panel) but its markers take no width at all.
            surface = self._colour("code_bg")
            fmt.setForeground(surface)
            carry = QFont(self._base_font)
            carry.setPointSizeF(_HIDDEN_POINT_SIZE)
            fmt.setFontPointSize(_HIDDEN_POINT_SIZE)
            fmt.setFontLetterSpacingType(QFont.SpacingType.AbsoluteSpacing)
            fmt.setFontLetterSpacing(-QFontMetricsF(carry).horizontalAdvance(
                line.text) / max(1, len(line.text)))
            return fmt
        if line.kind == markdown.TABLE_DELIMITER:
            # The |---|---| row is layout, not content: empty it out.
            fmt.setForeground(self._colour("surface"))
            return fmt

        surface = (self._colour("code_bg") if line.fenced
                   else self._colour("surface"))
        fmt.setForeground(surface)
        if not span.collapse:
            return fmt

        run = line.text[span.start:span.end]
        tiny = QFont(self._base_font)
        tiny.setPointSizeF(_HIDDEN_POINT_SIZE)
        advance = QFontMetricsF(tiny).horizontalAdvance(run)
        fmt.setFontPointSize(_HIDDEN_POINT_SIZE)
        fmt.setFontLetterSpacingType(QFont.SpacingType.AbsoluteSpacing)
        fmt.setFontLetterSpacing(-advance / max(1, len(run)))
        return fmt

    # ------------------------------------------------------------------
    # block furniture (called by the editor's painter)
    # ------------------------------------------------------------------
    def paint(self, painter: QPainter, editor, first: QTextBlock,
              offset: QPointF, viewport: QRectF) -> None:
        """Draw bullets, quote bars, rules and table rules for visible blocks."""
        block = first
        top = editor.blockBoundingGeometry(block).translated(offset).top()
        height = editor.blockBoundingRect(block).height()
        while block.isValid() and top <= viewport.bottom():
            data = block.userData()
            if (block.isVisible() and isinstance(data, MarkdownBlockData)
                    and not (block.blockNumber() == self._active_block
                             and data.line.kind == markdown.RULE)):
                self._paint_block(painter, editor, block, data.line,
                                  top, height, offset)
            block = block.next()
            top += height
            height = editor.blockBoundingRect(block).height()

    def _paint_block(self, painter: QPainter, editor, block: QTextBlock,
                     line: markdown.Line, top: float, height: float,
                     offset: QPointF) -> None:
        layout = block.layout()
        width = max(1.0, float(editor.viewport().width()))
        if line.kind == markdown.RULE:
            y = top + height / 2.0
            painter.setPen(QPen(self._colour("rule"), 1))
            painter.drawLine(QPointF(offset.x(), y),
                             QPointF(offset.x() + width, y))
            return
        if line.kind == markdown.LIST_ITEM and line.task is not None:
            for span in line.hidden_spans:
                if span.style == markdown.TASK_MARKER:
                    x = layout.lineAt(0).cursorToX(span.start)[0]
                    self._checkbox(painter, offset.x() + x + 1.0,
                                   top + height / 2.0, bool(line.task))
                    return
        if line.kind == markdown.LIST_ITEM and not line.ordered:
            for span in line.hidden_spans:
                if not span.collapse:      # the bullet glyph, width preserved
                    x = layout.lineAt(0).cursorToX(span.start)[0]
                    self._dot(painter, offset.x() + x + 1.0,
                              top + height / 2.0)
                    return
        if line.kind == markdown.QUOTE:
            for span in line.hidden_spans:
                x = layout.lineAt(0).cursorToX(span.start)[0]
                pen = QPen(self._colour("rule"), 3)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                painter.setPen(pen)
                painter.drawLine(QPointF(offset.x() + x + 1.5, top + 2.0),
                                 QPointF(offset.x() + x + 1.5, top + height - 2.0))
                return

    def _checkbox(self, painter: QPainter, x: float, centre: float,
                  checked: bool) -> None:
        side = 10.0
        box = QRectF(x, centre - side / 2.0, side, side)
        accent = self._colour("accent")
        painter.setPen(QPen(accent, 1.4))
        if checked:
            painter.setBrush(accent)
        else:
            painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(box, 2.5, 2.5)
        if checked:
            pen = QPen(self._colour("surface"), 1.6)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawLine(QPointF(box.left() + 2.4, box.center().y()),
                             QPointF(box.left() + 4.2, box.bottom() - 2.6))
            painter.drawLine(QPointF(box.left() + 4.2, box.bottom() - 2.6),
                             QPointF(box.right() - 2.2, box.top() + 2.8))
        painter.setBrush(Qt.BrushStyle.NoBrush)

    def _dot(self, painter: QPainter, x: float, centre: float) -> None:
        radius = 2.6
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._colour("accent"))
        painter.drawEllipse(QRectF(x, centre - radius, radius * 2, radius * 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)


#: Stop decorating past this many blocks (a 2-million-line file stays usable).
MAX_MARKDOWN_BLOCKS = 20_000
#: How far above a block the fence state is replayed (cost bounded per edit).
_STATE_WINDOW = 400
