"""Unit tests for base-direction detection."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mishkah.core.text_direction import (  # noqa: E402
    AUTO,
    LTR,
    RTL,
    dominant_direction,
    first_strong_is_rtl,
    is_rtl_char,
    resolve_direction,
    rtl_ratio,
)


def test_arabic_is_rtl():
    assert resolve_direction("مرحبا بالعالم", AUTO) == RTL


def test_hebrew_is_rtl():
    assert resolve_direction("שלום עולם", AUTO) == RTL


def test_urdu_is_rtl():
    assert resolve_direction("سلام دنیا", AUTO) == RTL


def test_latin_is_ltr():
    assert resolve_direction("Hello world", AUTO) == LTR


def test_chinese_is_ltr():
    assert resolve_direction("你好世界", AUTO) == LTR


def test_hindi_is_ltr():
    assert resolve_direction("नमस्ते दुनिया", AUTO) == LTR


def test_empty_defaults_to_ltr():
    assert resolve_direction("", AUTO) == LTR
    assert resolve_direction("   \n\t  ", AUTO) == LTR


def test_digits_and_punctuation_are_neutral():
    assert resolve_direction("123 --- ...", AUTO) == LTR


def test_explicit_mode_overrides_content():
    assert resolve_direction("مرحبا", LTR) == LTR
    assert resolve_direction("Hello", RTL) == RTL


def test_first_strong_wins_over_leading_punctuation():
    assert first_strong_is_rtl("«مرحبا»") is True
    assert first_strong_is_rtl("(hello)") is False


def test_dominant_direction_is_bidi_correct():
    # First *strong* character wins: an LTR paragraph with an RTL run stays LTR.
    assert dominant_direction("API: هذا نص عربي طويل enough to count") == LTR
    # …but a neutral prefix does not hide the Arabic that follows.
    assert dominant_direction("«» — هذا نص عربي") == RTL
    assert dominant_direction("This is plainly English text") == LTR


def test_dominant_direction_skips_blank_leading_lines():
    assert dominant_direction("\n\n   \nمرحبا بالعالم\n") == RTL
    assert dominant_direction("\n\nhello\n") == LTR


def test_dominant_direction_counts_when_every_line_is_neutral():
    # No strong character on any line → fall back to the character count.
    assert dominant_direction("١٢٣٤٥\n٦٧٨٩٠") == RTL
    assert dominant_direction("\n\n") == LTR


def test_rtl_ratio():
    assert rtl_ratio("مرحبا") == 1.0
    assert rtl_ratio("hello") == 0.0
    assert 0.0 < rtl_ratio("hello مرحبا") < 1.0


def test_is_rtl_char_covers_scripts():
    assert is_rtl_char("ا")
    assert is_rtl_char("ש")
    assert is_rtl_char("ދ")
    assert not is_rtl_char("a")
    assert not is_rtl_char("あ")
