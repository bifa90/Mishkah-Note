"""Language detection and the syntax rule tables."""

from __future__ import annotations

from pathlib import Path

import pytest

from mufakkira.core import syntax


@pytest.mark.parametrize("name,expected", [
    ("main.py", "python"),
    ("App.tsx", "typescript"),
    ("index.js", "javascript"),
    ("data.json", "json"),
    ("page.html", "html"),
    ("styles.scss", "css"),
    ("kernel.c", "c"),
    ("engine.cpp", "cpp"),
    ("lib.rs", "rust"),
    ("server.go", "go"),
    ("Main.java", "java"),
    ("deploy.sh", "shell"),
    ("queries.sql", "sql"),
    ("config.yml", "yaml"),
    ("README.md", "markdown"),
    ("notes.txt", "plain"),
    ("Makefile", "shell"),
    ("Dockerfile", "shell"),
    ("PKGBUILD", "shell"),
    ("unknown.xyz", "plain"),
])
def test_language_from_file_name(name, expected):
    assert syntax.language_for_path(Path("/tmp") / name) == expected


def test_language_for_missing_path():
    assert syntax.language_for_path(None) == "plain"
    assert syntax.language_for_path("") == "plain"


def test_unknown_code_falls_back_to_plain():
    assert syntax.get_language("brainfuck").code == "plain"
    assert syntax.get_language(None).code == "plain"


def test_every_language_has_unique_code_and_extensions():
    codes = [spec.code for spec in syntax.LANGUAGES]
    assert len(codes) == len(set(codes))
    extensions = [ext for spec in syntax.LANGUAGES for ext in spec.extensions]
    assert len(extensions) == len(set(extensions))


def test_every_rule_compiles():
    for spec in syntax.LANGUAGES:
        for pattern, group in spec.compiled():
            assert pattern.pattern
            assert group in {
                syntax.KEYWORD, syntax.BUILTIN, syntax.STRING, syntax.COMMENT,
                syntax.NUMBER, syntax.TAG, syntax.ATTRIBUTE, syntax.HEADING,
                syntax.LITERAL,
            }, group


@pytest.mark.parametrize("code,sample,group", [
    ("python", "def f():  # hi", syntax.KEYWORD),
    ("python", "x = 'text'", syntax.STRING),
    ("python", "return 42", syntax.NUMBER),
    ("javascript", "const a = `b`", syntax.KEYWORD),
    ("rust", "fn main() {}", syntax.KEYWORD),
    ("sql", "SELECT * FROM t", syntax.KEYWORD),
    ("markdown", "# Title", syntax.HEADING),
])
def test_rules_match_typical_lines(code, sample, group):
    spec = syntax.get_language(code)
    hits = {(rule_group) for pattern, rule_group in spec.compiled()
            if pattern.search(sample)}
    assert group in hits


def test_line_comment_helper():
    assert syntax.line_comment_for("script.py") == "#"
    assert syntax.line_comment_for("main.cpp") == "//"
    assert syntax.line_comment_for("schema.sql") == "--"
    assert syntax.line_comment_for("python") == "#"
    assert syntax.line_comment_for("notes.txt") is None


def test_choices_are_stable_for_the_menu():
    choices = syntax.language_choices()
    assert choices[0][0] == "plain"
    assert ("python", "Python") in choices
