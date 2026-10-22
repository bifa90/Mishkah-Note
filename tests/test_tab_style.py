"""Sticky-note palette used to colour tabs."""

from __future__ import annotations

from mishkah.core import tab_style


def test_palette_is_complete_and_unique():
    codes = [colour.code for colour in tab_style.NOTE_COLOURS]
    assert len(codes) == len(set(codes))
    assert len(codes) >= 6
    for colour in tab_style.NOTE_COLOURS:
        assert colour.fill.startswith("#") and len(colour.fill) == 7
        assert colour.ink.startswith("#") and len(colour.ink) == 7


def test_lookup():
    assert tab_style.get("yellow").fill == "#FFF3B0"
    assert tab_style.get("") is None
    assert tab_style.get(None) is None
    assert tab_style.get("chartreuse") is None


def test_validation():
    assert tab_style.is_valid(None)
    assert tab_style.is_valid("")
    assert tab_style.is_valid("pink")
    assert not tab_style.is_valid("neon")


def test_cycle_covers_every_colour_and_none():
    seen = []
    code = ""
    for _ in range(len(tab_style.NOTE_COLOURS) + 1):
        code = tab_style.next_code(code)
        seen.append(code)
    assert set(seen) == set(tab_style.codes()) | {""}
    assert seen[0] == tab_style.NOTE_COLOURS[0].code


def test_cycle_from_unknown_value_starts_at_the_first_colour():
    assert tab_style.next_code("neon") == tab_style.NOTE_COLOURS[0].code


def test_dark_theme_uses_a_deeper_shade_of_the_same_hue():
    for note in tab_style.NOTE_COLOURS:
        dark = tab_style.get(note.code, "dark")
        assert dark.fill != note.fill
        # the dark fill must actually be darker, or a light label would vanish
        assert _luma(dark.fill) < _luma(note.fill)
        assert dark.ink == note.ink or _luma(dark.ink) > _luma(dark.fill)


def test_light_theme_is_unchanged():
    for note in tab_style.NOTE_COLOURS:
        assert tab_style.get(note.code).fill == note.fill
        assert tab_style.get(note.code, "light").fill == note.fill


def test_unknown_theme_falls_back_to_light():
    assert tab_style.get("blue", "solarized").fill == tab_style.get("blue").fill


def _luma(hex_colour: str) -> float:
    value = hex_colour.lstrip("#")
    r, g, b = (int(value[i:i + 2], 16) for i in (0, 2, 4))
    return 0.299 * r + 0.587 * g + 0.114 * b
