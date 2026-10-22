"""Text completion helpers — pure logic, no Qt.

Three behaviours are implemented here because they are the ones every serious
editor ships and users notice immediately when they are missing:

* **Bracket and quote pairing.**  Typing ``(`` inserts ``()`` and leaves the
  caret inside; typing the closing character when it is already there steps
  over it instead of duplicating it; wrapping a selection is supported.
* **Smart indentation.**  ``Enter`` keeps the current indentation, adds one
  level after an opening bracket and removes one level when the next line
  starts with a closing bracket.
* **Word completion.**  Words already present in the document, ranked by
  frequency and recency, so ``Ctrl+Space`` suggests what the user already
  wrote instead of a dictionary nobody configured.

Nothing here depends on a widget, which keeps the rules testable and lets the
tests run without a display.
"""

from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional, Tuple

#: Opening character → closing character.  Quotes are included because the
#: same "type once, get a pair" expectation applies to them.
PAIRS: Dict[str, str] = {
    "(": ")",
    "[": "]",
    "{": "}",
    '"': '"',
    "'": "'",
    "`": "`",
    "«": "»",
    "‹": "›",
    "“": "”",
    "‘": "’",
}

#: The reverse map, used to decide whether a typed key closes a pair.
CLOSERS = frozenset(PAIRS.values())

#: A character after which pairing a quote would be wrong (``don't``).
WORD_CHARS = re.compile(r"[\w\u0600-\u06FF\u0750-\u077F]", re.UNICODE)

_TRAILING_OPEN = re.compile(r"[\(\[\{:>]\s*$")
_LEADING_CLOSE = re.compile(r"^\s*[\)\]\}]")

WORD_PATTERN = re.compile(r"[\w\u0600-\u06FF\u0750-\u077F]{2,}", re.UNICODE)

DEFAULT_INDENT = "    "


# ---------------------------------------------------------------------------
# pairing
# ---------------------------------------------------------------------------
def closing_for(char: str) -> Optional[str]:
    """The character that completes *char*, if it is an opener."""
    return PAIRS.get(char)


def is_opener(char: str) -> bool:
    return char in PAIRS


def is_closer(char: str) -> bool:
    return char in CLOSERS


def should_pair(char: str, before: str, after: str, has_selection: bool = False) -> bool:
    """Decide whether typing *char* should insert the pair.

    ``before`` is the text right before the caret (may be empty) and ``after``
    the text right after it.  The rules follow what VS Code and Sublime do,
    which is what users expect:

    * with a selection, any opener wraps it;
    * a quote is not paired right after a word character (``don't``,
      ``it's``) nor inside an existing word;
    * an opener is not paired when the next character is a word character
      (typing ``(`` before ``foo`` almost always means the user is fixing
      something, not opening a group).
    """
    if char not in PAIRS:
        return False
    if has_selection:
        return True
    if after and WORD_CHARS.match(after[0]):
        return False
    if char in "\"'`":
        if before and WORD_CHARS.match(before[-1]):
            return False
        if after == char:
            return False
    return True


def should_skip_closer(char: str, after: str) -> bool:
    """Typing a closer that is already the next character should step over it."""
    return bool(after) and after[0] == char and char in CLOSERS


def deletion_span(char: str, before: str, after: str) -> int:
    """Characters to delete when pressing Backspace between an empty pair.

    0 means "normal backspace", 2 deletes both halves of ``()``.
    """
    if before and after and PAIRS.get(before[-1]) == after[0]:
        return 2
    return 0


# ---------------------------------------------------------------------------
# indentation
# ---------------------------------------------------------------------------
def leading_whitespace(line: str) -> str:
    """The indentation prefix of *line* (spaces and tabs only)."""
    stripped = line[: len(line) - len(line.lstrip(" \t"))]
    return stripped


def indent_unit(sample: Optional[str] = None) -> str:
    """Infer the indent unit from a document sample, defaulting to 4 spaces.

    A file indented with tabs should stay tab-indented; a 2-space file should
    not be re-indented with 4 spaces by the editor.
    """
    if not sample:
        return DEFAULT_INDENT
    tab_lines = space_wide = space_narrow = 0
    for line in sample.splitlines():
        if not line.strip():
            continue
        prefix = leading_whitespace(line)
        if not prefix:
            continue
        if prefix.startswith("\t"):
            tab_lines += 1
        elif len(prefix) % 4 == 0:
            space_wide += 1
        elif len(prefix) % 2 == 0:
            space_narrow += 1
    if tab_lines and tab_lines >= space_wide + space_narrow:
        return "\t"
    if space_narrow > space_wide:
        return "  "
    return DEFAULT_INDENT


def indent_for_newline(line: str, unit: str = DEFAULT_INDENT) -> str:
    """Indentation for the line created by pressing Enter inside *line*.

    Keeps the current level, and adds one more when the line opens a block —
    a trailing ``(``, ``[``, ``{``, ``:`` (Python, YAML, C++ labels) or the
    ``>`` of a shell heredoc — so the caret lands where the body belongs.
    """
    base = leading_whitespace(line)
    body = line[len(base):].rstrip()
    if _TRAILING_OPEN.search(body):
        return base + unit
    return base


def dedent_for_closer(indent: str, char: str, unit: str = DEFAULT_INDENT) -> Optional[str]:
    """Indentation to use when *char* closes a block at the start of a line.

    Returns ``None`` when the character is not a closing bracket or the line
    is already at column zero.
    """
    if char not in (")", "]", "}"):
        return None
    if not indent:
        return None
    if unit == "\t":
        return indent[:-1] if indent.endswith("\t") else indent
    if indent.endswith(unit):
        return indent[: -len(unit)]
    width = len(unit) or 1
    removable = min(width, len(indent) - len(indent.rstrip(" ")))
    return indent[: len(indent) - removable] if removable else indent


def starts_with_closer(line: str) -> bool:
    return bool(_LEADING_CLOSE.match(line))


# ---------------------------------------------------------------------------
# word completion
# ---------------------------------------------------------------------------
def document_words(text: str, limit: int = 4000) -> List[str]:
    """Unique words of *text*, most recently used last.

    Ranking is done by :func:`complete`; here we only keep the order of
    appearance (cheap, and enough to bias towards recent words).
    """
    seen: Dict[str, None] = {}
    for match in WORD_PATTERN.finditer(text):
        word = match.group(0)
        seen[word] = None
        if len(seen) >= limit:
            break
    return list(seen)


def complete(prefix: str, text: str, limit: int = 20) -> List[str]:
    """Words starting with *prefix*, best first.

    Ranking: more frequent wins, then later appearance (recency), then
    shortest — which mirrors the usual "most useful suggestion first" rule.
    The exact prefix itself is excluded (nothing to complete).
    """
    if not prefix:
        return []
    counts: Dict[str, int] = {}
    positions: Dict[str, int] = {}
    for index, match in enumerate(WORD_PATTERN.finditer(text)):
        word = match.group(0)
        if not word.startswith(prefix) or word == prefix:
            continue
        counts[word] = counts.get(word, 0) + 1
        positions[word] = index
    ordered = sorted(counts, key=lambda w: (-counts[w], -positions[w], len(w), w))
    return ordered[:limit]


def common_prefix(words: Iterable[str]) -> str:
    """Longest shared prefix, used to extend the word in place."""
    words = list(words)
    if not words:
        return ""
    prefix = words[0]
    for word in words[1:]:
        while not word.startswith(prefix):
            prefix = prefix[:-1]
            if not prefix:
                return ""
    return prefix


# ---------------------------------------------------------------------------
# block indentation of a selection
# ---------------------------------------------------------------------------
def reindent_block(block: str, outdent: bool = False,
                   unit: str = DEFAULT_INDENT) -> Tuple[str, int]:
    """Indent (or outdent) every line of *block*.

    Returns the new text and how many characters the first line grew (or
    shrank), so the caller can keep the selection aligned.
    """
    lines = block.split("\n")
    if outdent:
        changed_first = 0
        out: List[str] = []
        for index, line in enumerate(lines):
            if line.startswith("\t"):
                new = line[1:]
            else:
                strip = 0
                while strip < len(unit) and strip < len(line) and line[strip] == " ":
                    strip += 1
                new = line[strip:]
            if index == 0:
                changed_first = len(new) - len(line)
            out.append(new)
        return "\n".join(out), changed_first
    out = [unit + line if line.strip() else line for line in lines]
    return "\n".join(out), len(unit)
