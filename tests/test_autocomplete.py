"""Rules behind auto-pairing, auto-indent and word completion."""

from __future__ import annotations

import pytest

from mishkah.core import autocomplete as ac


# ---------------------------------------------------------------------
# pairing
# ---------------------------------------------------------------------
@pytest.mark.parametrize("opener,closer", list(ac.PAIRS.items()))
def test_every_opener_has_a_closer(opener, closer):
    assert ac.closing_for(opener) == closer
    assert ac.is_closer(closer)


def test_pairs_when_next_character_is_empty():
    assert ac.should_pair("(", "", "") is True
    assert ac.should_pair("{", "    ", "") is True


def test_does_not_pair_before_a_word():
    assert ac.should_pair("(", "", "foo") is False


def test_wraps_a_selection_with_any_opener():
    assert ac.should_pair("(", "", "text", has_selection=True) is True
    assert ac.should_pair('"', "abc", "def", has_selection=True) is True


def test_no_apostrophe_pairing_inside_words():
    # "don" + "'" + "t" must stay don't, not don''t
    assert ac.should_pair("'", "don", "t") is False
    assert ac.should_pair("'", "it", "s") is False


def test_quote_pairs_at_a_word_boundary():
    assert ac.should_pair("'", "word ", "") is True
    assert ac.should_pair('"', "", "") is True


def test_skipping_an_existing_closer():
    assert ac.should_skip_closer(")", ")") is True
    assert ac.should_skip_closer("]", " ]") is False
    assert ac.should_skip_closer("x", "x") is False


def test_backspace_removes_both_halves_of_an_empty_pair():
    # caret sits between "(" and ")" → both halves go away
    assert ac.deletion_span("(", "(", ")") == 2
    assert ac.deletion_span("(", "(x", ")") == 0      # not empty, normal backspace
    assert ac.deletion_span("x", "a", "b") == 0


# ---------------------------------------------------------------------
# indentation
# ---------------------------------------------------------------------
def test_enter_keeps_the_current_indent():
    assert ac.indent_for_newline("    value = 1") == "    "


def test_enter_after_an_opening_bracket_indents_once_more():
    assert ac.indent_for_newline("    if x:") == "        "   # a block follows
    assert ac.indent_for_newline("    call(") == "        "
    assert ac.indent_for_newline("{") == "    "


def test_enter_ignores_trailing_spaces():
    assert ac.indent_for_newline("    func(   ") == "        "


def test_dedent_when_typing_a_closing_bracket():
    assert ac.dedent_for_closer("        ", "}") == "    "
    assert ac.dedent_for_closer("", "}") is None
    assert ac.dedent_for_closer("    ", "x") is None


def test_dedent_understands_tabs_and_two_space_files():
    assert ac.dedent_for_closer("\t\t", "}", unit="\t") == "\t"
    assert ac.dedent_for_closer("    ", "]", unit="  ") == "  "


def test_indent_unit_is_inferred_from_the_document():
    assert ac.indent_unit("def a():\n\treturn 1\n\ndef b():\n\treturn 2\n") == "\t"
    assert ac.indent_unit("if a:\n  pass\nif b:\n  pass\n") == "  "
    assert ac.indent_unit("if a:\n    pass\n") == "    "
    assert ac.indent_unit("") == "    "


def test_starts_with_closer():
    assert ac.starts_with_closer("  }") is True
    assert ac.starts_with_closer("x ]") is False


# ---------------------------------------------------------------------
# word completion
# ---------------------------------------------------------------------
SAMPLE = """
document = 1
for document in documents:
    document.write(document)
قيمة = document
"""


def test_complete_ranks_by_frequency_then_recency():
    result = ac.complete("docu", SAMPLE)
    assert result[0] == "document"
    assert "documents" in result


def test_complete_excludes_the_exact_prefix():
    # "document" is already typed in full; only longer words are useful
    assert ac.complete("document", SAMPLE) == ["documents"]


def test_complete_needs_a_prefix():
    assert ac.complete("", SAMPLE) == []


def test_complete_handles_arabic():
    assert "قيمة" in ac.complete("قي", "قيمة = 1\nقيمة + قيمة\n")


def test_complete_respects_the_limit():
    text = " ".join(f"word{i}" for i in range(50))
    assert len(ac.complete("word", text, limit=5)) == 5


def test_common_prefix_extends_the_word():
    assert ac.common_prefix(["document", "documents", "doc"]) == "doc"
    assert ac.common_prefix(["alpha", "beta"]) == ""
    assert ac.common_prefix([]) == ""


def test_document_words_are_unique():
    words = ac.document_words("a1 a1 a1 b2")
    assert words == ["a1", "b2"]


# ---------------------------------------------------------------------
# block indent / outdent
# ---------------------------------------------------------------------
def test_indent_block_adds_a_unit_to_every_non_empty_line():
    text, delta = ac.reindent_block("one\n\ntwo")
    assert text == "    one\n\n    two"
    assert delta == 4


def test_outdent_block_removes_one_unit():
    text, delta = ac.reindent_block("    one\n        two", outdent=True)
    assert text == "one\n    two"
    assert delta == -4


def test_outdent_never_goes_negative():
    text, _ = ac.reindent_block("one\ntwo", outdent=True)
    assert text == "one\ntwo"
