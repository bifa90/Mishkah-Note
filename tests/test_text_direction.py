"""Unit tests for base-direction detection (Unicode Bidi rules P2/P3).

The matrix below is the contract from CD-16.  Every row that used to pass for
the wrong reason is marked, because a test that pins a wrong answer is worse
than no test at all.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mishkah.core.text_direction import (  # noqa: E402
    AUTO,
    LTR,
    RTL,
    bidi_class,
    describe_char,
    document_side,
    dominant_direction,
    first_strong_is_rtl,
    invisible_name,
    invisible_spans,
    is_ltr_char,
    is_rtl_char,
    is_rtl_text,
    is_strong_char,
    resolve_direction,
    rtl_ratio,
)

START = "مرحبا"          # Arabic letters
HEBREW = "שלום"
PERSIAN = "سلام"


# --------------------------------------------------------------- strong letters


@pytest.mark.parametrize("sample", [START, HEBREW, PERSIAN, "ދިވެހި", "𞤀𞤁"])
def test_rtl_scripts_open_right_to_left(sample):
    assert resolve_direction(sample, AUTO) == RTL


@pytest.mark.parametrize("sample", ["Hello world", "你好世界", "नमस्ते दुनिया", "Γειά σου"])
def test_ltr_scripts_open_left_to_right(sample):
    assert resolve_direction(sample, AUTO) == LTR


def test_explicit_mode_wins_over_content():
    assert resolve_direction("مرحبا", LTR) == LTR
    assert resolve_direction("Hello", RTL) == RTL


# ------------------------------------------------------------------ P2 and P3


def test_empty_and_neutral_text_falls_back_to_ltr():
    # P3: with no strong character the paragraph is laid out left-to-right.
    assert resolve_direction("", AUTO) == LTR
    assert resolve_direction("   \n\t  ", AUTO) == LTR
    assert resolve_direction("123 --- ... «»", AUTO) == LTR


def test_first_strong_character_decides_not_the_majority():
    text = "API: هذا نص عربي طويل جدًا لدرجة أن الحروف العربية أكثر بكثير"
    assert first_strong_is_rtl(text) is False
    assert resolve_direction(text, AUTO) == LTR


def test_first_strong_finds_none_in_neutral_text():
    assert first_strong_is_rtl("١٢٣٤٥ ٦٧٨٩٠ ...") is None


# --------------------------------------------------------------- digits & marks


@pytest.mark.parametrize("text, expected", [
    ("123 مرحبا", RTL),          # digits are neutral; the first letter decides
    ("١٢٣ hello", LTR),          # Arabic-Indic digits do not make text Arabic
    ("، hello", LTR),            # Arabic comma (CS) is neutral
    ("مرحبا 123", RTL),
    ("1234567890", LTR),         # P3 default, not "RTL because digits are Arabic"
    ("١٢٣٤٥\n٦٧٨٩٠", LTR),      # was pinned as RTL by the old range table
    ("«123»", LTR),
    ("٪٥٠ مرحبا", RTL),          # percent/first letter
    ("\u064eمرحبا", RTL),        # a bare diacritic (NSM) is neutral
])
def test_digits_and_punctuation_never_decide(text, expected):
    assert resolve_direction(text, AUTO) == expected
    assert dominant_direction(text) == expected


def test_digits_are_not_strong_and_not_rtl_chars():
    assert bidi_class("١") == "AN"
    assert bidi_class("1") == "EN"
    for ch in ("١", "1", "،", ".", "«", " "):
        assert not is_strong_char(ch), ch
        assert not is_rtl_char(ch), ch
        assert not is_ltr_char(ch), ch


def test_directional_marks_are_respected():
    # LRM is bidi class L, RLM is R: they are strong and therefore legitimate
    # paragraph openers, which is exactly how they are used in practice.
    assert resolve_direction("\u200fhello", AUTO) == RTL
    assert resolve_direction("\u200eمرحبا", AUTO) == LTR
    assert resolve_direction("\u061chello", AUTO) == RTL    # ALM = AL
    assert resolve_direction("\u2066hello\u2069", AUTO) == LTR  # isolate = neutral


# ------------------------------------------------------------------ documents


def test_dominant_direction_skips_blank_leading_lines():
    assert dominant_direction("\n\n   \nمرحبا بالعالم\n") == RTL
    assert dominant_direction("\n\nhello\n") == LTR


def test_dominant_direction_of_an_empty_document_is_ltr():
    assert dominant_direction("") == LTR
    assert dominant_direction("\n\n") == LTR


def test_dominant_direction_matches_resolve_direction():
    # One rule behind both APIs: the status bar cannot disagree with layout.
    for text in ("مرحبا", "hello", "123 مرحبا", "١٢٣", "", "\n\nمرحبا"):
        assert dominant_direction(text) == resolve_direction(text, AUTO), text


def test_sniff_limit_is_respected():
    # A leading neutral block bigger than the limit hides the Arabic that
    # follows: the sample says "no strong character", so P3 applies.
    padding = " " * 32
    assert dominant_direction(padding + "مرحبا", limit=16) == LTR
    assert dominant_direction(padding + "مرحبا", limit=64) == RTL


# -------------------------------------------------------------------- helpers


def test_is_rtl_text():
    assert is_rtl_text("مرحبا")
    assert not is_rtl_text("hello")
    assert not is_rtl_text("123")


def test_rtl_ratio_ignores_digits():
    assert rtl_ratio("مرحبا") == 1.0
    assert rtl_ratio("hello") == 0.0
    assert 0.0 < rtl_ratio("hello مرحبا") < 1.0
    assert rtl_ratio("١٢٣٤٥") == 0.0        # old code called this fully RTL
    assert rtl_ratio("مرحبا ١٢٣٤٥") == 1.0


def test_is_rtl_char_covers_scripts():
    for ch in ("ا", "ש", "ދ", "ܐ", "𞤀", "\u200f"):
        assert is_rtl_char(ch), hex(ord(ch))
    for ch in ("a", "あ", "١", "1", "\u200e"):
        assert not is_rtl_char(ch), hex(ord(ch))


# ------------------------------------------------------------ invisible chars


def test_invisible_spans_finds_every_marker():
    text = "a\u200fb\u200ec\u200cd\u061ce"
    names = [name for _, _, name in invisible_spans(text)]
    assert names == ["RLM", "LRM", "ZWNJ", "ALM"]
    assert [start for start, _, _ in invisible_spans(text)] == [1, 3, 5, 7]


def test_invisible_spans_ignores_ordinary_text():
    assert invisible_spans("مرحبا hello 123") == []
    assert invisible_name("a") is None
    assert invisible_name("\u200f") == "RLM"


def test_describe_char_names_the_code_point():
    assert describe_char("\u200f") == "U+200F RLM"
    assert describe_char("ا").startswith("U+0627")
    assert describe_char("") == ""


# ------------------------------------------------------- document side (CD-17)


def test_document_side_follows_the_first_strong_character():
    """A file is aligned the way it starts, whatever comes after it."""
    assert document_side("hello\nمرحبا بالعالم\nمرحبا بالعالم") == LTR
    assert document_side("مرحبا\nhello world foo") == RTL
    assert document_side("مرحبا\nhello") == RTL
    assert document_side("hello\nمرحبا") == LTR
    assert document_side("\n\n   hello") == LTR


def test_document_side_ignores_digits_and_punctuation():
    assert document_side("١٢٣٤٥ 67890 ...") == LTR
    assert document_side("مرحبا 12345") == RTL
    assert document_side("") == LTR
