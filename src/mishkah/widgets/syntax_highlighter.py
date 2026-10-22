"""Syntax highlighting built on the rule tables in :mod:`mishkah.core.syntax`.

Design notes
------------
* The highlighter is *opt-in* (``View ▸ Syntax highlighting``), because a
  plain mishkah should never colour text the user did not ask to colour.
* Colours come from the active theme, so the same rules work in light and
  dark mode.
* Above a configurable line count the highlighter detaches itself: repainting
  a 2-million-line block document would defeat the large-file work.
"""

from __future__ import annotations

from typing import Dict, Optional

from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import (
    QColor,
    QFont,
    QSyntaxHighlighter,
    QTextBlockUserData,
    QTextCharFormat,
    QTextDocument,
)

from mishkah.core import syntax

#: (light, dark) colour per highlight group
PALETTE: Dict[str, tuple] = {
    syntax.KEYWORD: ("#0000C0", "#7FB3FF"),
    syntax.BUILTIN: ("#795E26", "#DCDCAA"),
    syntax.STRING: ("#A31515", "#CE9178"),
    syntax.COMMENT: ("#008000", "#6A9955"),
    syntax.NUMBER: ("#098658", "#B5CEA8"),
    syntax.TAG: ("#267F99", "#4EC9B0"),
    syntax.ATTRIBUTE: ("#0070C1", "#9CDCFE"),
    syntax.HEADING: ("#0451A5", "#569CD6"),
    syntax.LITERAL: ("#AF00DB", "#C586C0"),
}

#: Stop highlighting past this many blocks (≈ lines).
MAX_HIGHLIGHT_BLOCKS = 50_000


class _BlockState(QTextBlockUserData):
    """Remembers "this block ends inside a block comment"."""

    __slots__ = ("in_comment",)

    def __init__(self, in_comment: bool = False):
        super().__init__()
        self.in_comment = in_comment


class SyntaxHighlighter(QSyntaxHighlighter):
    def __init__(self, document: QTextDocument, language: str = "plain",
                 theme: str = "light"):
        super().__init__(document)
        self._language = syntax.get_language(language)
        self._theme = theme
        self._rules = self._build_rules()
        self._comment_start: Optional[QRegularExpression] = None
        self._comment_end: Optional[QRegularExpression] = None
        if self._language.block_comment:
            start, end = self._language.block_comment
            self._comment_start = QRegularExpression(QRegularExpression.escape(start))
            self._comment_end = QRegularExpression(QRegularExpression.escape(end))

    # ------------------------------------------------------------------
    def _format(self, group: str) -> QTextCharFormat:
        light, dark = PALETTE[group]
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(dark if self._theme == "dark" else light))
        if group in (syntax.KEYWORD, syntax.HEADING):
            fmt.setFontWeight(QFont.Weight.DemiBold)
        if group == syntax.COMMENT:
            fmt.setFontItalic(True)
        return fmt

    def _build_rules(self):
        return [(QRegularExpression(rule.pattern,
                                    QRegularExpression.PatternOption.UseUnicodePropertiesOption
                                    if rule.flags else QRegularExpression.PatternOption.NoPatternOption),
                 self._format(rule.group))
                for rule in self._language.rules]

    # ------------------------------------------------------------------
    def set_language(self, language: str) -> None:
        self._language = syntax.get_language(language)
        self._build_comment_markers()
        self._rules = self._build_rules()
        self.rehighlight()

    def set_theme(self, theme: str) -> None:
        if theme == self._theme:
            return
        self._theme = theme
        self._rules = self._build_rules()
        self.rehighlight()

    def _build_comment_markers(self) -> None:
        self._comment_start = self._comment_end = None
        if self._language.block_comment:
            start, end = self._language.block_comment
            self._comment_start = QRegularExpression(QRegularExpression.escape(start))
            self._comment_end = QRegularExpression(QRegularExpression.escape(end))

    # ------------------------------------------------------------------
    def highlightBlock(self, text: str) -> None:  # noqa: N802 (Qt naming)
        if self.currentBlock().blockNumber() > MAX_HIGHLIGHT_BLOCKS:
            return

        for expression, fmt in self._rules:
            iterator = expression.globalMatch(text)
            while iterator.hasNext():
                match = iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), fmt)

        if not self._comment_start or not self._comment_end:
            return

        # --- block comments, carried across lines via block user data -----
        comment_format = self._format(syntax.COMMENT)
        previous = self.currentBlock().previous()
        in_comment = False
        if previous.isValid():
            data = previous.userData()
            if isinstance(data, _BlockState):
                in_comment = data.in_comment

        start = 0
        if in_comment:
            end_match = self._comment_end.match(text)
            if end_match.hasMatch():
                length = end_match.capturedEnd()
                self.setFormat(0, length, comment_format)
                start = length
            else:
                self.setFormat(0, len(text), comment_format)
                self.setCurrentBlockUserData(_BlockState(True))
                return

        while True:
            open_match = self._comment_start.match(text, start)
            if not open_match.hasMatch():
                break
            open_at = open_match.capturedStart()
            close_match = self._comment_end.match(text, open_at + open_match.capturedLength())
            if close_match.hasMatch():
                end_at = close_match.capturedEnd()
                self.setFormat(open_at, end_at - open_at, comment_format)
                start = end_at
            else:
                self.setFormat(open_at, len(text) - open_at, comment_format)
                self.setCurrentBlockUserData(_BlockState(True))
                return

        self.setCurrentBlockUserData(_BlockState(False))

    # ------------------------------------------------------------------
    def language_code(self) -> str:
        return self._language.code
