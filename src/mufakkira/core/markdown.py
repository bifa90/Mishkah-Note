"""Markdown parsing for the *live* (visual) Markdown mode — no Qt.

The editor never rewrites the buffer when the mode is on: the document keeps
exactly the bytes the user typed, with every ``#``, ``*`` and backtick in
place.  This module turns a line of source into **spans** — ``(start, end)``
ranges tagged with a visual role — and :mod:`mufakkira.widgets.markdown_decorator`
paints them.  That separation keeps the parser testable without a display and
makes it impossible for a rendering bug to corrupt a file.

Vocabulary
----------
* A :class:`Line` describes one block of the document: its ``kind``
  (heading, list item, quote, fence, table row…), its ``level`` and the spans
  that decorate it.
* A :class:`Span` is a half-open ``[start, end)`` character range with a
  ``style``.  Spans flagged ``hidden=True`` are Markdown syntax (``**``,
  ``#``, ``[``, the URL of a link, ``>``…) that the view renders invisible
  and zero-width, so the text reads as formatted prose while the buffer keeps
  the source.

Supported syntax
----------------
ATX headings (``#`` … ``######``), bold, italic, strikethrough, inline code,
fenced code blocks, ordered and bullet lists, block quotes, links and images,
horizontal rules and simple pipe tables.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

# ---------------------------------------------------------------- block kinds
PARAGRAPH = "paragraph"
HEADING = "heading"
LIST_ITEM = "list-item"
QUOTE = "quote"
FENCE = "fence"                 # the ``` line itself (markers hidden)
CODE_BLOCK = "code-block"       # a line inside a fence
RULE = "rule"                   # --- / *** / ___
TABLE_ROW = "table-row"
TABLE_DELIMITER = "table-delimiter"
BLANK = "blank"

# ------------------------------------------------------------------- styles
TEXT = "text"
BOLD = "bold"
ITALIC = "italic"
STRIKE = "strike"
CODE = "code"
LINK = "link"
HEADING_TEXT = "heading-text"
QUOTE_TEXT = "quote-text"
TABLE_TEXT = "table-text"
TABLE_PIPE = "table-pipe"
LIST_MARKER = "list-marker"
TASK_MARKER = "task-marker"     # the ``[x]`` of a GitHub-style task item
MARKER = "marker"               # generic hidden syntax

#: Styles that mean "this run is Markdown syntax, do not show it".
HIDDEN_STYLES = frozenset({MARKER})


@dataclass(frozen=True)
class Span:
    """A styled character range inside one line.

    ``hidden`` spans are Markdown syntax.  ``collapse`` decides how the view
    takes the space away:

    * ``True`` — the run is invisible *and* occupies no width (``**``, ``#``,
      ```` ``` ````, ``[``, ``](url)``).  The text closes up around it.
    * ``False`` — the run is invisible but keeps its advance width, so a
      glyph can be painted in its place without moving the text (``-``
      becomes a bullet, ``>`` becomes a quote bar).
    """

    start: int
    end: int
    style: str
    hidden: bool = False
    collapse: bool = True

    def __post_init__(self) -> None:  # pragma: no cover - defensive
        if self.end < self.start:
            raise ValueError("span end before start")

    @property
    def length(self) -> int:
        return self.end - self.start


@dataclass(frozen=True)
class Line:
    """One decorated block of Markdown source."""

    text: str
    kind: str = PARAGRAPH
    level: int = 0
    ordered: bool = False
    spans: Tuple[Span, ...] = ()
    #: True when the block sits inside a fenced code block (including fences).
    fenced: bool = False
    #: ``None`` for a normal item, else whether the task box is ticked.
    task: Optional[bool] = None

    @property
    def hidden_spans(self) -> Tuple[Span, ...]:
        return tuple(s for s in self.spans if s.hidden)

    def span_at(self, index: int) -> Optional[Span]:
        for span in self.spans:
            if span.start <= index < span.end:
                return span
        return None

    @property
    def visible_text(self) -> str:
        """The line as the reader sees it (syntax removed)."""
        out = []
        hidden = sorted(self.hidden_spans, key=lambda s: s.start)
        index = 0
        for span in hidden:
            if span.start > index:
                out.append(self.text[index:span.start])
            index = max(index, span.end)
        out.append(self.text[index:])
        return "".join(out)


# ===========================================================================
# patterns
# ===========================================================================
_HEADING = re.compile(r"^( {0,3})(#{1,6})([ \t]+)(.*)$")
_SETEXT = re.compile(r"^ {0,3}(=+|-{2,})[ \t]*$")
_RULE = re.compile(r"^ {0,3}(?:(?:\*[ \t]*){3,}|(?:-[ \t]*){3,}|(?:_[ \t]*){3,})$")
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
_BULLET = re.compile(r"^(\s*)([-*+])([ \t]+)(.*)$")
_ORDERED = re.compile(r"^(\s*)(\d{1,9})([.)])([ \t]+)(.*)$")
_QUOTE = re.compile(r"^(\s*)((?:>[ \t]?)+)(.*)$")
_TASK = re.compile(r"^\[([ xX])\](?=[ \t]|$)")
_TABLE_DELIM = re.compile(
    r"^\s*\|?\s*:?-{2,}:?\s*(?:\|\s*:?-{2,}:?\s*)+\|?\s*$")

_INLINE_CODE = re.compile(r"(`+)([^`].*?[^`]?)\1(?!`)")
_IMAGE = re.compile(r"!\[([^\]\n]*)\]\(\s*([^)\s]*)(?:\s+\"[^\"]*\")?\s*\)")
_LINK = re.compile(r"\[([^\]\n]+)\]\(\s*([^)\s]*)(?:\s+\"[^\"]*\")?\s*\)")
_AUTOLINK = re.compile(r"<((?:https?|mailto):[^>\s]+)>")
_BOLD = re.compile(r"(\*\*|__)(?=\S)(.+?)(?<=\S)\1")
_STRIKE = re.compile(r"~~(?=\S)(.+?)(?<=\S)~~")
_ITALIC = re.compile(r"(?<![\w*])\*(?=\S)([^*\n]+?)(?<=\S)\*(?![\w*])")
_ITALIC_UNDER = re.compile(r"(?<![\w_])_(?=\S)([^_\n]+?)(?<=\S)_(?![\w_])")

_ESCAPE = re.compile(r"\\([\\`*_{}\[\]()#+\-.!>~|])")


# ===========================================================================
# public API
# ===========================================================================
def parse_document(text: str) -> List[Line]:
    """Parse a whole document (tests, previews, exports)."""
    lines = text.split("\n")
    state = _State()
    out: List[Line] = []
    for index, raw in enumerate(lines):
        following = lines[index + 1] if index + 1 < len(lines) else None
        line, state = parse_line(raw, following, state)
        out.append(line)
    return out


@dataclass
class _State:
    fence: Optional[str] = None      # the opening fence run, e.g. "```"
    previous_kind: str = BLANK

    def copy(self) -> _State:
        return _State(self.fence, self.previous_kind)


def parse_line(text: str, following: Optional[str] = None,
               state: Optional[_State] = None) -> Tuple[Line, _State]:
    """Decorate one line; returns the line and the state for the next one."""
    state = (state or _State()).copy()
    if state.fence is not None:
        return _fenced_line(text, state), state

    if not text.strip():
        state.previous_kind = BLANK
        return Line(text=text, kind=BLANK), state

    match = _FENCE.match(text)
    if match:
        run, info = match.group(1), match.group(2)
        if run[0] == "`" and "`" in info:      # not a fence: an inline span
            match = None
        else:
            state.fence = run
            state.previous_kind = FENCE
            return Line(
                text=text,
                kind=FENCE,
                fenced=True,
                spans=(Span(0, len(text), CODE),
                       Span(0, len(text), MARKER, True)),
            ), state

    match = _RULE.match(text)
    if match:
        state.previous_kind = RULE
        return Line(
            text=text,
            kind=RULE,
            spans=tuple(Span(m.start(), m.end(), MARKER, True)
                        for m in re.finditer(r"[^\s]", text)),
        ), state

    match = _HEADING.match(text)
    if match:
        indent, hashes, gap, body = match.groups()
        start = len(indent)
        body_start = len(indent) + len(hashes) + len(gap)
        spans = [Span(start, body_start, MARKER, True),
                 Span(body_start, len(text), HEADING_TEXT)]
        spans.extend(_inline(text, body_start))
        state.previous_kind = HEADING
        return Line(text=text, kind=HEADING, level=len(hashes),
                    spans=_merge(spans)), state

    match = _QUOTE.match(text)
    if match:
        indent, marks, body = match.groups()
        start = len(indent)
        body_start = len(indent) + len(marks)
        # Only the ``>`` glyphs are hidden (keeping their width so the bar can
        # be painted over them); the space after them belongs to the text.
        glyphs = marks.count(">")
        spans: List[Span] = [Span(start, start + glyphs, MARKER, True,
                                  collapse=False)]
        if body:
            spans.append(Span(body_start, len(text), QUOTE_TEXT))
        spans.extend(_inline(text, body_start))
        state.previous_kind = QUOTE
        return Line(text=text, kind=QUOTE, spans=_merge(spans)), state

    match = _ORDERED.match(text)
    if match:
        indent, number, dot, gap, body = match.groups()
        body_start = len(indent) + len(number) + len(dot) + len(gap)
        spans = [Span(len(indent), len(indent) + len(number), LIST_MARKER)]
        task = _task_span(body, body_start, spans)
        spans.extend(_inline(text, body_start))
        state.previous_kind = LIST_ITEM
        return Line(text=text, kind=LIST_ITEM, level=_indent_level(indent),
                    ordered=True, spans=_merge(spans), task=task), state

    match = _BULLET.match(text)
    if match:
        indent, bullet, gap, body = match.groups()
        body_start = len(indent) + len(bullet) + len(gap)
        # Only the glyph is hidden; the space after it stays, so the painted
        # bullet sits exactly where the dash used to be.
        spans = [Span(len(indent), len(indent) + len(bullet), MARKER,
                      True, collapse=False)]
        task = _task_span(body, body_start, spans)
        spans.extend(_inline(text, body_start))
        state.previous_kind = LIST_ITEM
        return Line(text=text, kind=LIST_ITEM, level=_indent_level(indent),
                    spans=_merge(spans), task=task), state

    if _TABLE_DELIM.match(text):
        state.previous_kind = TABLE_DELIMITER
        return Line(
            text=text,
            kind=TABLE_DELIMITER,
            spans=tuple(Span(m.start(), m.end(), MARKER, True)
                        for m in re.finditer(r"[^\s]", text)),
        ), state

    if _looks_like_table(text):
        state.previous_kind = TABLE_ROW
        cells = _table(text, header=_is_header(following))
        return Line(text=text, kind=TABLE_ROW, level=0,
                    spans=_merge(list(cells) + _inline(text))), state

    spans = _inline(text, 0)
    state.previous_kind = PARAGRAPH
    return Line(text=text, kind=PARAGRAPH, spans=_merge(spans)), state


# ===========================================================================
# helpers
# ===========================================================================
def _task_span(body: str, body_start: int, spans: List[Span]) -> Optional[bool]:
    """Recognise ``[ ]`` / ``[x]`` at the start of a list item.

    The brackets are hidden but keep their advance so a painted checkbox can
    sit exactly where they were.
    """
    match = _TASK.match(body)
    if match is None:
        return None
    spans.append(Span(body_start, body_start + match.end(), TASK_MARKER,
                      True, collapse=False))
    return match.group(1) in "xX"


def _indent_level(indent: str) -> int:
    return min(6, len(indent.expandtabs(4)) // 2)


def _fenced_line(text: str, state: _State) -> Line:
    opening = state.fence or ""
    stripped = text.strip()
    if stripped.startswith(opening[0] * len(opening)):
        state.fence = None
        state.previous_kind = FENCE
        return Line(text=text, kind=FENCE, fenced=True,
                    spans=(Span(0, len(text), CODE),
                           Span(0, len(text), MARKER, True)))
    state.previous_kind = CODE_BLOCK
    spans = (Span(0, len(text), CODE),) if text else ()
    return Line(text=text, kind=CODE_BLOCK, fenced=True, spans=spans)


def _looks_like_table(text: str) -> bool:
    return text.count("|") >= 2 and not _FENCE.match(text)


def _is_header(following: Optional[str]) -> bool:
    """The row above a ``|---|`` delimiter is the header; else keep literal."""
    return bool(following is not None and _TABLE_DELIM.match(following))


def _table(text: str, header: bool = False) -> Tuple[Span, ...]:
    spans: List[Span] = [Span(m.start(), m.end(), TABLE_PIPE)
                         for m in re.finditer(r"\|", text)]
    style = BOLD if header else TABLE_TEXT
    for match in re.finditer(r"[^|\s][^|]*", text):
        start, end = match.start(), match.end()
        while end > start and text[end - 1].isspace():
            end -= 1
        if end > start:
            spans.append(Span(start, end, style))
    return _merge(spans)


def _inline(text: str, offset: int = 0) -> List[Span]:
    """Find inline styling in ``text`` (optionally starting at *offset*)."""
    spans: List[Span] = []
    taken: List[Tuple[int, int]] = []
    if offset >= len(text):
        return spans

    def place(start: int, end: int, style: str) -> bool:
        if start < 0 or end > len(text) or start >= end:
            return False
        for used_start, used_end in taken:
            if start < used_end and used_start < end:
                return False
        taken.append((start, end))
        spans.append(Span(start, end, style))
        return True

    def hide(start: int, end: int) -> None:
        if start < end:
            spans.append(Span(start, end, MARKER, True))

    for start, end in escapes(text):
        if start >= offset:
            spans.append(Span(start, end, MARKER, True))

    # Order matters: code, then images/links/autolinks, then strong/em.
    for match in _INLINE_CODE.finditer(text):
        if match.start() < offset:
            continue
        if place(match.start(), match.end(), CODE):
            run = len(match.group(1))
            hide(match.start(), match.start() + run)
            hide(match.end() - run, match.end())

    for pattern in (_IMAGE, _LINK):
        for match in pattern.finditer(text):
            if match.start() < offset:
                continue
            start, end = match.start(), match.end()
            if not place(start, end, LINK):
                continue
            open_bracket = text.index("[", start)
            close_bracket = text.index("]", open_bracket)
            hide(start, open_bracket + 1)
            hide(close_bracket, end)

    for match in _AUTOLINK.finditer(text):
        if match.start() < offset:
            continue
        if place(match.start(), match.end(), LINK):
            hide(match.start(), match.start() + 1)
            hide(match.end() - 1, match.end())

    for match in _BOLD.finditer(text):
        if match.start() < offset:
            continue
        start, end = match.start(), match.end()
        token = len(match.group(1))
        if place(start + token, end - token, BOLD):
            hide(start, start + token)
            hide(end - token, end)

    for match in _STRIKE.finditer(text):
        if match.start() < offset:
            continue
        start, end = match.start(), match.end()
        if place(start + 2, end - 2, STRIKE):
            hide(start, start + 2)
            hide(end - 2, end)

    for pattern in (_ITALIC, _ITALIC_UNDER):
        for match in pattern.finditer(text):
            if match.start() < offset:
                continue
            start, end = match.start(), match.end()
            if place(start + 1, end - 1, ITALIC):
                hide(start, start + 1)
                hide(end - 1, end)

    return spans


def _merge(spans: Sequence[Span]) -> Tuple[Span, ...]:
    """Drop empty spans, sort by position and add escaped characters."""
    cleaned = [s for s in spans if s.length > 0]
    cleaned.sort(key=lambda s: (s.hidden, s.start, s.end))
    return tuple(cleaned)


def escapes(text: str) -> List[Tuple[int, int]]:
    """Offsets of the backslashes in ``\\*`` style escapes."""
    return [(m.start(), m.start() + 1) for m in _ESCAPE.finditer(text)]


def is_markdown_path(path: object) -> bool:
    """True for the file names where live Markdown is worth offering."""
    name = str(path or "").lower()
    return name.endswith((".md", ".markdown", ".mdown", ".mkd", ".mdx"))
