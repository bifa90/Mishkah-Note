"""Base-direction detection, following the Unicode Bidi Algorithm (P2/P3).

The editor never forces a direction on the user: every document starts in
*Auto*, which resolves per paragraph from the **first strong character** —
exactly the rule the Unicode algorithm applies to a paragraph (P2) and the
fallback it uses when there is none (P3: left-to-right).

Only two kinds of character are strong:

* ``L``  — left to right (Latin, Greek, Cyrillic, CJK, Devanagari, …);
* ``R``/``AL`` — right to left (Hebrew, Arabic, Syriac, Thaana, Adlam, …).

Everything else is **neutral** for this purpose, and that is the point:
European and Arabic-Indic digits (``EN``/``AN``), punctuation (``،`` ``.``
``«``), whitespace and combining marks never decide a paragraph's direction.
A line that reads ``١٢٣٤٥`` is therefore laid out like any other neutral line
— left to right — rather than being mistaken for Arabic because its code
points happen to sit in the Arabic block.

The classification comes from :mod:`unicodedata`, not from hand-maintained
code-point ranges: one source of truth, correct for every Unicode version
Python ships, and impossible to leave a script out of.

Explicit formatting characters (LRM, RLM, ALM, LRI … PDI) are strong in
Unicode terms — ``RLM`` really does mean "this run is right-to-left" — so they
are respected here like any other strong character.  They are also invisible,
which is why :func:`invisible_spans` exists: the editor can reveal them on
request so a stuck direction is never a mystery.
"""

from __future__ import annotations

import unicodedata
from typing import Iterable, List, Optional, Tuple

AUTO = "auto"
RTL = "rtl"
LTR = "ltr"

VALID_MODES = (AUTO, RTL, LTR)

#: Bidi classes that carry a strong right-to-left direction.
STRONG_RTL = frozenset({"R", "AL"})

#: Bidi classes that carry a strong left-to-right direction.
STRONG_LTR = frozenset({"L"})

#: Sample size used when guessing a whole document's default direction.
SNIFF_CHARS = 4096

#: Characters that occupy no space on screen but change how text behaves.
#: Reported by :func:`invisible_spans` so the editor can reveal them.
INVISIBLE_CHARS = {
    "\u061c": "ALM",
    "\u200b": "ZWSP",
    "\u200c": "ZWNJ",
    "\u200d": "ZWJ",
    "\u200e": "LRM",
    "\u200f": "RLM",
    "\u202a": "LRE",
    "\u202b": "RLE",
    "\u202c": "PDF",
    "\u202d": "LRO",
    "\u202e": "RLO",
    "\u2066": "LRI",
    "\u2067": "RLI",
    "\u2068": "FSI",
    "\u2069": "PDI",
    "\ufeff": "BOM",
}


def bidi_class(ch: str) -> str:
    """The Unicode ``Bidi_Class`` of *ch* (``""`` for unassigned code points)."""
    return unicodedata.bidirectional(ch) if ch else ""


def is_rtl_char(ch: str) -> bool:
    """True for characters that are strong right-to-left (``R`` or ``AL``)."""
    return bidi_class(ch) in STRONG_RTL


def is_ltr_char(ch: str) -> bool:
    """True for characters that are strong left-to-right (``L``)."""
    return bidi_class(ch) in STRONG_LTR


def is_strong_char(ch: str) -> bool:
    """True for characters that carry a strong direction (LTR or RTL).

    Digits and punctuation are *not* strong; see the module docstring.
    """
    klass = bidi_class(ch)
    return klass in STRONG_RTL or klass in STRONG_LTR


def first_strong_is_rtl(text: str) -> Optional[bool]:
    """Direction of the first strong character, or ``None`` if there is none.

    This is rule P2 of the Unicode Bidi Algorithm.  ``None`` means "no strong
    character" — callers then apply P3 (left-to-right).
    """
    for ch in text:
        klass = bidi_class(ch)
        if klass in STRONG_RTL:
            return True
        if klass in STRONG_LTR:
            return False
    return None


def resolve_direction(text: str, mode: str = AUTO) -> str:
    """Concrete ``rtl``/``ltr`` answer for *text* under *mode*.

    ``auto`` applies P2 and falls back to P3 (left-to-right) for empty,
    neutral-only text — the same choice Qt makes for ``LayoutDirectionAuto``.
    """
    if mode == RTL:
        return RTL
    if mode == LTR:
        return LTR
    return RTL if first_strong_is_rtl(text[:SNIFF_CHARS]) else LTR


def dominant_direction(text: str, limit: int = SNIFF_CHARS) -> str:
    """Base direction of a *document*.

    Scans in reading order — blank and neutral lines contribute nothing — and
    returns the direction of the first strong character, or ``LTR`` when the
    sample holds none.  Identical to :func:`resolve_direction` by design: two
    functions, one rule, so the status bar and the layout can never disagree.
    """
    return RTL if first_strong_is_rtl(text[:limit]) else LTR


FIRST_STRONG = "first_strong"
FIRST_LINE = "first_line"

VALID_SIDE_SOURCES = (FIRST_STRONG, FIRST_LINE)


def document_side(text: str, source: str = FIRST_STRONG,
                  limit: int = SNIFF_CHARS * 16) -> str:
    """Which side a *document* is aligned to, decided once and left alone.

    Two rules, and the difference between them is the whole point of CD-20:

    ``first_strong`` (default, the 1.0.02 behaviour)
        the first strong character in the file, skipping numbers and
        punctuation.  Stable from the first keystroke of an empty buffer.

    ``first_line``
        the direction of the first *line* that reads in some direction.  A
        leading blank line, a bare date or a line of digits is skipped and the
        first line carrying letters decides.  In the editor this rule also
        keeps re-deciding while the buffer is still a single line, so the
        first line you are writing is the one that sets the side.

    Neither rule may be moved by the caret: a document gets one side, chosen
    from its beginning (see CD-17).  Paragraph order is always Qt's business.
    """
    sample = text[:limit]
    if source != FIRST_LINE:
        return RTL if first_strong_is_rtl(sample) else LTR
    for line in sample.splitlines():
        verdict = first_strong_is_rtl(line)
        if verdict is not None:
            return RTL if verdict else LTR
    return LTR


def is_rtl_text(text: str) -> bool:
    """True when *text* opens with a strong RTL character."""
    return resolve_direction(text, AUTO) == RTL


def rtl_ratio(text: str, limit: int = SNIFF_CHARS) -> float:
    """Share of *strong* characters that are RTL (0.0 … 1.0).

    Digits are excluded from both sides of the fraction, so a text of numbers
    with one Arabic letter is fully RTL rather than mostly neutral.
    """
    rtl = strong = 0
    for ch in text[:limit]:
        klass = bidi_class(ch)
        if klass in STRONG_RTL:
            rtl += 1
            strong += 1
        elif klass in STRONG_LTR:
            strong += 1
    return (rtl / strong) if strong else 0.0


def iter_paragraphs(text: str) -> Iterable[str]:
    yield from text.splitlines()


def invisible_name(ch: str) -> Optional[str]:
    """The short name of an invisible formatting character, else ``None``."""
    return INVISIBLE_CHARS.get(ch)


def invisible_spans(text: str) -> List[Tuple[int, int, str]]:
    """``(start, length, name)`` for every invisible character in *text*.

    ``length`` is kept for future multi-character markers; today every entry
    is a single code point.  Used by the editor's "show invisible characters"
    view and by the tests that keep that view honest.
    """
    return [(index, 1, INVISIBLE_CHARS[ch])
            for index, ch in enumerate(text) if ch in INVISIBLE_CHARS]


def describe_char(ch: str) -> str:
    """Human-readable identity of one character: ``U+200F RLM``.

    Shown in the status bar when the caret sits on a character that is either
    invisible or has a different direction from its paragraph — the two cases
    where "why is my cursor there?" has no obvious answer.
    """
    if not ch:
        return ""
    code = f"U+{ord(ch):04X}"
    name = INVISIBLE_CHARS.get(ch)
    if name:
        return f"{code} {name}"
    return f"{code} {unicodedata.name(ch, '?')}"
