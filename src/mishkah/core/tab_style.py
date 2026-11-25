"""Sticky-note colours for tabs, plus helpers for pinned tabs.

The palette is deliberately small and muted — six recognisable note colours
in two shades each.  The light shade is the familiar pastel sticky note; the
dark shade keeps the same hue but drops the fill to a deep tone, because tab
labels are painted in the theme's text colour (the stylesheet wins over any
palette override), so a pastel tab in a dark window would be light grey on
near-white.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple


@dataclass(frozen=True)
class NoteColour:
    code: str
    label: str          # English label; the UI translates it
    fill: str           # tab background
    ink: str            # text and pin colour on that background
    accent: str         # selection/border accent
    dark_fill: str = ""     # tab background in the dark theme
    dark_ink: str = ""      # pin/text ink in the dark theme

    def for_theme(self, theme: str = "light") -> NoteColour:
        """The same note colour, shaded for the given theme."""
        if theme != "dark" or not self.dark_fill:
            return self
        return NoteColour(self.code, self.label, self.dark_fill,
                          self.dark_ink or self.ink, self.accent)


NOTE_COLOURS: Tuple[NoteColour, ...] = (
    NoteColour("yellow", "Yellow", "#FFF3B0", "#4A3B00", "#E8C547",
               "#5A4A08", "#FFF3B0"),
    NoteColour("green", "Green", "#C8F0C8", "#123B12", "#4CAF50",
               "#1E4A24", "#C8F0C8"),
    NoteColour("blue", "Blue", "#CBE6FA", "#0B3550", "#2E8BC0",
               "#12374F", "#CBE6FA"),
    NoteColour("pink", "Pink", "#FBD3E0", "#5A0F28", "#E36B95",
               "#5A2035", "#FBD3E0"),
    NoteColour("purple", "Purple", "#E4D6F7", "#331256", "#8E5BC8",
               "#3B2263", "#E4D6F7"),
    NoteColour("orange", "Orange", "#FFDFC0", "#4F2600", "#EE8B37",
               "#5A3210", "#FFDFC0"),
)

BY_CODE: Dict[str, NoteColour] = {colour.code: colour for colour in NOTE_COLOURS}

NO_COLOUR = ""


def get(code: Optional[str], theme: str = "light") -> Optional[NoteColour]:
    """Resolve a colour code for a theme, ``None`` for "no colour"."""
    if not code:
        return None
    colour = BY_CODE.get(code)
    return colour.for_theme(theme) if colour is not None else None


def codes() -> Tuple[str, ...]:
    return tuple(colour.code for colour in NOTE_COLOURS)


def is_valid(code: Optional[str]) -> bool:
    return code in (None, NO_COLOUR) or code in BY_CODE


def next_code(code: Optional[str]) -> str:
    """Cycle through the palette (used by the tab context menu shortcut)."""
    order = (NO_COLOUR,) + codes()
    try:
        index = order.index(code or NO_COLOUR)
    except ValueError:
        index = 0
    return order[(index + 1) % len(order)]


# ---------------------------------------------------------------------------
# contrast
# ---------------------------------------------------------------------------
def _channel(value: float) -> float:
    value /= 255.0
    return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4


def luminance(colour: str) -> float:
    """Relative luminance of ``#RRGGBB`` (WCAG definition)."""
    text = colour.lstrip("#")
    if len(text) != 6:
        return 0.0
    red, green, blue = (int(text[i:i + 2], 16) for i in (0, 2, 4))
    return (0.2126 * _channel(red) + 0.7152 * _channel(green)
            + 0.0722 * _channel(blue))


def contrast_ratio(first: str, second: str) -> float:
    """WCAG contrast between two colours (1.0 … 21.0)."""
    a, b = luminance(first), luminance(second)
    lighter, darker = max(a, b), min(a, b)
    return (lighter + 0.05) / (darker + 0.05)


def readable_ink(fill: str, preferred: str = "") -> str:
    """An ink that is actually readable on *fill*.

    A tab label is painted by the style with the window's text colour, which
    is why a pastel note colour in a dark window used to show a white name on
    a near-white fill.  The editor now paints the label itself and asks here
    for a colour that clears WCAG AA (4.5:1).
    """
    if preferred and contrast_ratio(preferred, fill) >= 4.5:
        return preferred
    return "#101010" if luminance(fill) > 0.5 else "#F5F5F5"
