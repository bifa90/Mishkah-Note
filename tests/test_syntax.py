"""Language detection and the syntax rule tables."""

from __future__ import annotations

from pathlib import Path

import pytest

from mishkah.core import syntax


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


# ---------------------------------------------------------------------------
# CD-12: the content knows its own language
# ---------------------------------------------------------------------------
SAMPLES = {
    "python": "def run(a, b):\n    return a + b\n",
    "javascript": "const x = 1;\nfunction go() { return x; }\n",
    "typescript": "interface User { name: string; }\n",
    "rust": "fn main() {\n    let mut x = 1;\n}\n",
    "go": "package main\nfunc main2() {}\n",
    "java": "public class A { public static void main() {} }\n",
    "sql": "SELECT id FROM users;",
    "cpp": "#include <iostream>\nint main(){ std::cout << 1; }",
    "c": "#include <stdio.h>\nint main(void){ return 0; }",
    "css": ".card { color: #fff; padding: 4px; }",
    "html": "<!doctype html>\n<html><body><p>hi</p></body></html>",
    "json": '{"a": 1, "b": [2, 3]}',
    "markdown": "# Title\n\n- one\n- two\n",
    "shell": "#!/bin/bash\nexport A=1\nif [ -f x ]; then echo hi; fi\n",
    "yaml": "---\nname: mishkah\nversion: 1\n",
}


def test_the_content_is_sniffed_for_every_language():
    from mishkah.core.syntax import language_for_text

    wrong = {code: language_for_text(text)
             for code, text in SAMPLES.items()
             if language_for_text(text) != code}
    assert wrong == {}


def test_plain_prose_stays_plain():
    from mishkah.core.syntax import language_for_text

    assert language_for_text("") == "plain"
    assert language_for_text("فقط نص عادي بلا شيفرة\nسطر آخر\n") == "plain"
    assert language_for_text("hello world\nthis is a note\n") == "plain"


def test_a_markdown_fence_does_not_masquerade_as_code():
    from mishkah.core.syntax import language_for_text

    text = "# Notes\n\n```python\ndef f():\n    pass\n```\n"
    assert language_for_text(text) == "markdown"
