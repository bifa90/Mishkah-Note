"""Counting words for the status bar (CD-23) — pure logic, no Qt."""

from __future__ import annotations

import re

#: A "word" is a run of letters or digits in any script.  Counting runs this
#: way makes Arabic, Persian, Hebrew and CJK behave as users expect, and stops
#: punctuation like ``—`` or ``«»`` from being counted as a word of its own.
WORD = re.compile(r"[\w\u0600-\u06FF\u0750-\u077F\u0590-\u05FF\u0900-\u097F"
                  r"\u3040-\u30FF\u4E00-\u9FFF]+", re.UNICODE)


def count_words(text: str) -> int:
    """Number of word-like runs in *text*."""
    if not text:
        return 0
    return len(WORD.findall(text))


def count_selection(text: str) -> int:
    """Words in a selection; the same rule, named for the caller's intent."""
    return count_words(text)
