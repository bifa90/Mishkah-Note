"""Base-direction detection.

The editor never forces a direction on the user any more: every document
starts in *Auto* mode, which resolves per paragraph from the first strong
character exactly like Windows 11 Notepad / the Unicode Bidi Algorithm.
This module implements that resolution in pure Python so it can be unit
tested without a GUI, and so the status bar can show a truthful label.

Strong RTL scripts (Unicode ``Bidi_Class`` R / AL):
    Hebrew, Arabic, Syriac, Thaana, N'Ko, Samaritan, Mandaic,
    Arabic Supplement/Extended, and the RTL presentation forms.
"""

from __future__ import annotations

from typing import Iterable

AUTO = "auto"
RTL = "rtl"
LTR = "ltr"

VALID_MODES = (AUTO, RTL, LTR)

# Inclusive (start, end) ranges of strong right-to-left code points.
RTL_RANGES: tuple[tuple[int, int], ...] = (
    (0x0590, 0x05FF),   # Hebrew
    (0x0600, 0x06FF),   # Arabic
    (0x0700, 0x074F),   # Syriac
    (0x0750, 0x077F),   # Arabic Supplement
    (0x0780, 0x07BF),   # Thaana
    (0x07C0, 0x07FF),   # NKo
    (0x0800, 0x083F),   # Samaritan
    (0x0840, 0x085F),   # Mandaic
    (0x0860, 0x086F),   # Syriac Supplement
    (0x0870, 0x089F),   # Arabic Extended-B
    (0x08A0, 0x08FF),   # Arabic Extended-A
    (0xFB1D, 0xFB4F),   # Hebrew presentation forms
    (0xFB50, 0xFDFF),   # Arabic presentation forms A
    (0xFE70, 0xFEFF),   # Arabic presentation forms B
    (0x10800, 0x10FFF), # Imperial Aramaic … Phoenician block group
    (0x1E800, 0x1E8DF), # Mende Kikakui
)

# Sample size used when guessing a whole document's default direction.
SNIFF_CHARS = 4096


def is_rtl_char(ch: str) -> bool:
    cp = ord(ch)
    for start, end in RTL_RANGES:
        if start <= cp <= end:
            return True
    return False


def is_strong_char(ch: str) -> bool:
    """True for characters that carry a strong direction (LTR or RTL)."""
    if is_rtl_char(ch):
        return True
    # Letters and digits are strong LTR in the bidi algorithm.
    return ch.isalnum() and ord(ch) < 0x0590


def first_strong_is_rtl(text: str) -> bool | None:
    """Direction of the first strong character, or ``None`` if neutral only."""
    for ch in text:
        if is_rtl_char(ch):
            return True
        if ch.isalnum() and ord(ch) < 0x0590:
            return False
    return None


def resolve_direction(text: str, mode: str = AUTO) -> str:
    """Concrete ``rtl``/``ltr`` answer for *text* under *mode*.

    ``auto`` inspects the first strong character (falling back to LTR for
    empty or purely neutral text, matching Qt's ``LayoutDirectionAuto``).
    """
    if mode == RTL:
        return RTL
    if mode == LTR:
        return LTR
    verdict = first_strong_is_rtl(text[:SNIFF_CHARS])
    return RTL if verdict else LTR


def dominant_direction(text: str, limit: int = SNIFF_CHARS) -> str:
    """Base direction of a *document* (used for the status-bar hint).

    Deliberately bidi-correct: the first **strong** character of the first
    non-empty line decides, exactly like the Unicode algorithm and Qt's
    ``LayoutDirectionAuto``.  ``"API: مرحبا"`` is therefore an LTR paragraph
    with an embedded RTL run — counting characters instead would flip such
    paragraphs depending on how long their Latin tail happens to be.

    Character counting is only used as a tie-breaker when the first line is
    purely neutral (punctuation, digits, quotes).
    """
    for line in text[:limit].splitlines():
        verdict = first_strong_is_rtl(line)
        if verdict is not None:
            return RTL if verdict else LTR

    rtl = ltr = 0
    for ch in text[:limit]:
        if is_rtl_char(ch):
            rtl += 1
        elif ch.isalnum() and ord(ch) < 0x0590:
            ltr += 1
    if rtl == 0 and ltr == 0:
        return LTR
    return RTL if rtl > ltr else LTR


def is_rtl_text(text: str) -> bool:
    return resolve_direction(text, AUTO) == RTL


def rtl_ratio(text: str, limit: int = SNIFF_CHARS) -> float:
    """Share of strong characters that are RTL (0.0 … 1.0)."""
    rtl = strong = 0
    for ch in text[:limit]:
        if is_rtl_char(ch):
            rtl += 1
            strong += 1
        elif ch.isalnum() and ord(ch) < 0x0590:
            strong += 1
    return (rtl / strong) if strong else 0.0


def iter_paragraphs(text: str) -> Iterable[str]:
    yield from text.splitlines()
