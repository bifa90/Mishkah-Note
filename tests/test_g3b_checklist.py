"""The manual gate page: seventeen cards, three verdicts each, never stale.

``docs/G3B_CHECKLIST.html`` is the page a human fills in during G3b.  It is
generated from ``tools/build_g3b_checklist.py``, so it can drift from the
checklist it claims to contain — which would be the worst possible failure for a
document whose whole job is to be trusted.  These tests hold both ends: the page
has every card and every control, and it is byte-for-byte what the generator
writes today.
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "docs" / "G3B_CHECKLIST.html"
BUILDER = ROOT / "tools" / "build_g3b_checklist.py"


def _builder():
    spec = importlib.util.spec_from_file_location("build_g3b_checklist", BUILDER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _cards() -> list[str]:
    html = PAGE.read_text(encoding="utf-8")
    return html.split('<article class="item"')[1:]


def test_the_page_exists_and_is_arabic_right_to_left():
    html = PAGE.read_text(encoding="utf-8")
    assert html.startswith("<!DOCTYPE html>")
    assert '<html lang="ar" dir="rtl">' in html
    assert "<title>" in html


def test_there_are_exactly_seventeen_numbered_cards():
    numbers = re.findall(r'data-item="(\d+)"', PAGE.read_text(encoding="utf-8"))
    assert numbers == [str(n) for n in range(1, 18)]


def test_every_card_offers_three_verdicts_plus_a_free_note():
    for index, card in enumerate(_cards(), start=1):
        values = re.findall(r'<input type="radio" name="v(\d+)" value="(\w+)"', card)
        assert [name for name, _ in values] == [str(index)] * 3, f"card {index}"
        assert [value for _, value in values] == ["ok", "bad", "later"], f"card {index}"
        assert card.count("<textarea") == 1, f"card {index}: no empty note field"


def test_every_card_explains_itself_and_carries_a_recommendation():
    for index, card in enumerate(_cards(), start=1):
        for marker in ("ما تفعله", "ما تتوقعه", "شكل مبسط", "التأثير إن فشل",
                       "توصيتي", "إن فشل، أبدأ بـ"):
            assert marker in card, f"card {index} lost «{marker}»"
        assert '<svg class="shape"' in card, f"card {index} has no diagram"


def test_the_recommendation_levels_are_the_two_we_use():
    html = PAGE.read_text(encoding="utf-8")
    levels = set(re.findall(r'class="rec" data-level="(\w+)"', html))
    assert levels <= {"high", "medium"}, levels
    assert "high" in levels and "medium" in levels


def test_the_items_are_numbered_and_grouped_without_gaps():
    module = _builder()
    assert [item["n"] for item in module.ITEMS] == list(range(1, 18))
    assert {item["group"] for item in module.ITEMS} <= set(module.GROUPS)
    shapes = {item["shape"] for item in module.ITEMS}
    assert shapes <= set(module.SHAPES), shapes - set(module.SHAPES)


def test_the_page_is_what_the_generator_writes_today():
    done = subprocess.run([sys.executable, str(BUILDER), "--check"],
                          capture_output=True, text=True, cwd=ROOT, timeout=120)
    assert done.returncode == 0, done.stderr
    assert "up to date (17 items)" in done.stdout


def test_the_walkthrough_points_at_the_page():
    text = (ROOT / "docs" / "G3B_WALKTHROUGH.ar.md").read_text(encoding="utf-8")
    assert "G3B_CHECKLIST.html" in text, "a lost link is a lost checklist"


@pytest.mark.gui
def test_every_diagram_draws_something_visible():
    """An SVG typo ships as an empty box; Qt can draw it and say so."""
    done = subprocess.run([sys.executable, str(ROOT / "tools" / "check_checklist_shapes.py"),
                           "--check"], capture_output=True, text=True, cwd=ROOT, timeout=240)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "17 diagrams rendered" in done.stdout


def test_the_page_survives_a_browser_that_refuses_local_storage():
    """file:// visits may block storage; the page must not go dead."""
    html = PAGE.read_text(encoding="utf-8")
    assert "try { return JSON.parse(localStorage" in html
    assert "read-only visit" in html
