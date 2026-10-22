"""Language definitions for syntax highlighting — data only, no Qt.

The editor ships a deliberately small, dependency-free highlighter instead of
pulling in Pygments: a text editor should start instantly, and a rule table
covers the constructs people actually read (comments, strings, numbers,
keywords).

A :class:`LanguageSpec` is a list of :class:`Rule` objects; ``group`` selects
how the highlighter paints a match.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Sequence, Tuple

# Highlight groups.  The highlighter maps them to colours per theme.
KEYWORD = "keyword"
BUILTIN = "builtin"
STRING = "string"
COMMENT = "comment"
NUMBER = "number"
TAG = "tag"
ATTRIBUTE = "attribute"
HEADING = "heading"
LITERAL = "literal"


@dataclass(frozen=True)
class Rule:
    pattern: str
    group: str
    flags: int = 0


@dataclass(frozen=True)
class LanguageSpec:
    code: str
    name: str
    extensions: Tuple[str, ...]
    rules: Tuple[Rule, ...] = ()
    #: (start, end) for block comments, e.g. ``("/*", "*/")``
    block_comment: Optional[Tuple[str, str]] = None
    #: line comment prefix, used by the "toggle comment" action
    line_comment: Optional[str] = None

    def compiled(self) -> Tuple[Tuple[re.Pattern, str], ...]:
        """Return the rules as compiled patterns (cached by callers)."""
        return tuple((re.compile(rule.pattern, rule.flags), rule.group)
                     for rule in self.rules)


def _kw(words: Sequence[str]) -> Rule:
    return Rule(r"\b(?:" + "|".join(words) + r")\b", KEYWORD)


def _words(words: Sequence[str], group: str) -> Rule:
    return Rule(r"\b(?:" + "|".join(words) + r")\b", group)


_C_STYLE_NUMBERS = Rule(
    r"\b(?:0[xX][0-9a-fA-F]+|0[bB][01]+|\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)[uUlLfF]*\b",
    NUMBER)

PLAIN = LanguageSpec("plain", "Plain text", (), ())

PYTHON = LanguageSpec(
    "python", "Python", (".py", ".pyw", ".pyi"),
    (
        Rule(r"#[^\n]*", COMMENT),
        Rule(r'(?:[rRbBuUfF]{0,2})(?:"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\')', STRING),
        Rule(r'(?:[rRbBuUfF]{0,2})"(?:[^"\\\n]|\\.)*"', STRING),
        Rule(r"(?:[rRbBuUfF]{0,2})'(?:[^'\\\n]|\\.)*'", STRING),
        Rule(r"@[\w.]+", BUILTIN),
        _kw(("and", "as", "assert", "async", "await", "break", "class", "continue",
             "def", "del", "elif", "else", "except", "finally", "for", "from",
             "global", "if", "import", "in", "is", "lambda", "nonlocal", "not",
             "or", "pass", "raise", "return", "try", "while", "with", "yield",
             "match", "case")),
        _words(("True", "False", "None", "self", "cls"), LITERAL),
        _words(("print", "len", "range", "int", "str", "float", "list", "dict",
                "set", "tuple", "open", "super", "isinstance", "enumerate", "zip",
                "sorted", "sum", "min", "max", "abs", "type", "repr"), BUILTIN),
        _C_STYLE_NUMBERS,
    ),
    line_comment="#",
)

JAVASCRIPT = LanguageSpec(
    "javascript", "JavaScript", (".js", ".mjs", ".cjs", ".jsx"),
    (
        Rule(r"//[^\n]*", COMMENT),
        Rule(r"/\*[\s\S]*?\*/", COMMENT),
        Rule(r"`(?:[^`\\]|\\.)*`", STRING),
        Rule(r'"(?:[^"\\\n]|\\.)*"', STRING),
        Rule(r"'(?:[^'\\\n]|\\.)*'", STRING),
        _kw(("async", "await", "break", "case", "catch", "class", "const",
             "continue", "debugger", "default", "delete", "do", "else", "export",
             "extends", "finally", "for", "from", "function", "get", "if",
             "import", "in", "instanceof", "let", "new", "of", "return", "set",
             "static", "super", "switch", "this", "throw", "try", "typeof", "var",
             "void", "while", "yield")),
        _words(("true", "false", "null", "undefined", "NaN", "Infinity"), LITERAL),
        _C_STYLE_NUMBERS,
    ),
    block_comment=("/*", "*/"),
    line_comment="//",
)

TYPESCRIPT = LanguageSpec(
    "typescript", "TypeScript", (".ts", ".tsx", ".mts", ".cts"),
    JAVASCRIPT.rules + (
        _kw(("interface", "implements", "type", "enum", "namespace", "declare",
             "readonly", "public", "private", "protected", "abstract", "as",
             "satisfies", "keyof", "infer", "is")),
    ),
    block_comment=("/*", "*/"),
    line_comment="//",
)

JSON_SPEC = LanguageSpec(
    "json", "JSON", (".json", ".jsonc", ".webmanifest"),
    (
        Rule(r'"(?:[^"\\\n]|\\.)*"(?=\s*:)', ATTRIBUTE),
        Rule(r'"(?:[^"\\\n]|\\.)*"', STRING),
        _words(("true", "false", "null"), LITERAL),
        Rule(r"-?\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b", NUMBER),
    ),
    line_comment="//",
)

HTML_SPEC = LanguageSpec(
    "html", "HTML", (".html", ".htm", ".xhtml", ".xml", ".svg", ".vue"),
    (
        Rule(r"<!--[\s\S]*?-->", COMMENT),
        Rule(r"<!\[CDATA\[[\s\S]*?\]\]>", COMMENT),
        Rule(r"</?[\w:.-]+", TAG),
        Rule(r"[\w:.-]+(?==)", ATTRIBUTE),
        Rule(r'"[^"\n]*"', STRING),
        Rule(r"'[^'\n]*'", STRING),
    ),
    block_comment=("<!--", "-->"),
)

CSS_SPEC = LanguageSpec(
    "css", "CSS", (".css", ".scss", ".sass", ".less"),
    (
        Rule(r"/\*[\s\S]*?\*/", COMMENT),
        Rule(r"@[\w-]+", KEYWORD),
        Rule(r'"[^"\n]*"', STRING),
        Rule(r"'[^'\n]*'", STRING),
        Rule(r"[.#][\w-]+(?=[^{]*\{)", TAG),
        Rule(r"[\w-]+(?=\s*:)", ATTRIBUTE),
        Rule(r"#[0-9a-fA-F]{3,8}\b", NUMBER),
        Rule(r"\b\d+(?:\.\d+)?(?:px|em|rem|%|vh|vw|s|ms|deg)?\b", NUMBER),
    ),
    block_comment=("/*", "*/"),
)

C_LANG = LanguageSpec(
    "c", "C", (".c", ".h"),
    (
        Rule(r"//[^\n]*", COMMENT),
        Rule(r"/\*[\s\S]*?\*/", COMMENT),
        Rule(r"^[ \t]*#[ \t]*\w+", BUILTIN, re.MULTILINE),
        Rule(r'"(?:[^"\\\n]|\\.)*"', STRING),
        Rule(r"'(?:[^'\\\n]|\\.)*'", STRING),
        _kw(("auto", "break", "case", "const", "continue", "default", "do",
             "else", "enum", "extern", "for", "goto", "if", "inline", "register",
             "restrict", "return", "sizeof", "static", "struct", "switch",
             "typedef", "union", "volatile", "while", "_Bool", "_Static_assert")),
        _words(("int", "char", "float", "double", "void", "long", "short",
                "signed", "unsigned", "size_t", "NULL"), LITERAL),
        _C_STYLE_NUMBERS,
    ),
    block_comment=("/*", "*/"),
    line_comment="//",
)

CPP_LANG = LanguageSpec(
    "cpp", "C++", (".cpp", ".cc", ".cxx", ".hpp", ".hh", ".hxx", ".ipp"),
    C_LANG.rules + (
        _kw(("class", "namespace", "template", "typename", "public", "private",
             "protected", "virtual", "override", "final", "new", "delete",
             "this", "using", "try", "catch", "throw", "constexpr", "consteval",
             "noexcept", "nullptr", "auto", "co_await", "co_return", "co_yield",
             "static_cast", "dynamic_cast", "reinterpret_cast", "const_cast")),
        _words(("std", "string", "vector", "map", "set", "unique_ptr",
                "shared_ptr", "optional", "size_t"), BUILTIN),
    ),
    block_comment=("/*", "*/"),
    line_comment="//",
)

RUST_SPEC = LanguageSpec(
    "rust", "Rust", (".rs",),
    (
        Rule(r"//[^\n]*", COMMENT),
        Rule(r"/\*[\s\S]*?\*/", COMMENT),
        Rule(r'r#*"[\s\S]*?"#*', STRING),
        Rule(r'"(?:[^"\\\n]|\\.)*"', STRING),
        Rule(r"'(?:\\.|[^'\\\n])'", STRING),
        Rule(r"#!?\[[^\]]*\]", BUILTIN),
        _kw(("as", "async", "await", "break", "const", "continue", "crate", "dyn",
             "else", "enum", "extern", "fn", "for", "if", "impl", "in", "let",
             "loop", "match", "mod", "move", "mut", "pub", "ref", "return",
             "self", "static", "struct", "super", "trait", "type", "unsafe",
             "use", "where", "while", "yield")),
        _words(("true", "false", "None", "Some", "Ok", "Err"), LITERAL),
        _words(("String", "Vec", "Option", "Result", "Box", "Rc", "Arc",
                "HashMap", "i8", "i16", "i32", "i64", "i128", "isize", "u8",
                "u16", "u32", "u64", "u128", "usize", "f32", "f64", "bool",
                "char", "str"), BUILTIN),
        _C_STYLE_NUMBERS,
    ),
    block_comment=("/*", "*/"),
    line_comment="//",
)

GO_SPEC = LanguageSpec(
    "go", "Go", (".go",),
    (
        Rule(r"//[^\n]*", COMMENT),
        Rule(r"/\*[\s\S]*?\*/", COMMENT),
        Rule(r"`[^`]*`", STRING),
        Rule(r'"(?:[^"\\\n]|\\.)*"', STRING),
        _kw(("break", "case", "chan", "const", "continue", "default", "defer",
             "else", "fallthrough", "for", "func", "go", "goto", "if", "import",
             "interface", "map", "package", "range", "return", "select", "struct",
             "switch", "type", "var")),
        _words(("true", "false", "nil", "iota"), LITERAL),
        _words(("string", "int", "int64", "float64", "byte", "rune", "error",
                "bool", "any"), BUILTIN),
        _C_STYLE_NUMBERS,
    ),
    block_comment=("/*", "*/"),
    line_comment="//",
)

JAVA_SPEC = LanguageSpec(
    "java", "Java", (".java", ".kt", ".kts", ".gradle"),
    (
        Rule(r"//[^\n]*", COMMENT),
        Rule(r"/\*[\s\S]*?\*/", COMMENT),
        Rule(r'"""[\s\S]*?"""', STRING),
        Rule(r'"(?:[^"\\\n]|\\.)*"', STRING),
        Rule(r"@\w+", BUILTIN),
        _kw(("abstract", "assert", "boolean", "break", "case", "catch", "class",
             "const", "continue", "default", "do", "else", "enum", "extends",
             "final", "finally", "for", "fun", "if", "implements", "import",
             "instanceof", "interface", "native", "new", "package", "private",
             "protected", "public", "return", "static", "strictfp", "super",
             "switch", "synchronized", "this", "throw", "throws", "transient",
             "try", "val", "var", "void", "volatile", "while")),
        _words(("true", "false", "null"), LITERAL),
        _C_STYLE_NUMBERS,
    ),
    block_comment=("/*", "*/"),
    line_comment="//",
)

SHELL_SPEC = LanguageSpec(
    "shell", "Shell", (".sh", ".bash", ".zsh", ".fish", ".ksh"),
    (
        Rule(r"#[^\n]*", COMMENT),
        Rule(r'"(?:[^"\\]|\\.)*"', STRING),
        Rule(r"'[^']*'", STRING),
        Rule(r"\$\{[^}]*\}|\$[\w@*#?$!-]+", BUILTIN),
        Rule(r"^[ \t]*[\w.-]+(?=\s*\(\)\s*\{)", BUILTIN, re.MULTILINE),
        _kw(("if", "then", "else", "elif", "fi", "for", "while", "until", "do",
             "done", "case", "esac", "function", "in", "select", "return", "local",
             "export", "readonly", "declare", "source", "shift", "break",
             "continue", "exit", "trap", "set", "unset", "eval")),
        Rule(r"\b\d+\b", NUMBER),
    ),
    line_comment="#",
)

SQL_SPEC = LanguageSpec(
    "sql", "SQL", (".sql",),
    (
        Rule(r"--[^\n]*", COMMENT),
        Rule(r"/\*[\s\S]*?\*/", COMMENT),
        Rule(r"'(?:[^'\\]|\\.|'')*'", STRING),
        Rule(r'"[^"\n]*"', STRING),
        Rule(r"\b(?:SELECT|FROM|WHERE|INSERT|INTO|VALUES|UPDATE|SET|DELETE|CREATE|"
             r"TABLE|ALTER|DROP|INDEX|JOIN|LEFT|RIGHT|INNER|OUTER|ON|GROUP|BY|"
             r"ORDER|HAVING|LIMIT|OFFSET|DISTINCT|AS|AND|OR|NOT|NULL|IS|IN|"
             r"BETWEEN|LIKE|EXISTS|UNION|ALL|CASE|WHEN|THEN|ELSE|END|PRIMARY|"
             r"KEY|FOREIGN|REFERENCES|DEFAULT|CONSTRAINT|VIEW|TRIGGER|BEGIN|"
             r"COMMIT|ROLLBACK|TRANSACTION)\b", KEYWORD, re.IGNORECASE),
        Rule(r"\b\d+(?:\.\d+)?\b", NUMBER),
    ),
    block_comment=("/*", "*/"),
    line_comment="--",
)

YAML_SPEC = LanguageSpec(
    "yaml", "YAML", (".yml", ".yaml"),
    (
        Rule(r"#[^\n]*", COMMENT),
        Rule(r"^\s*[\w.-]+(?=\s*:)", ATTRIBUTE, re.MULTILINE),
        Rule(r'"(?:[^"\\\n]|\\.)*"', STRING),
        Rule(r"'[^'\n]*'", STRING),
        Rule(r"^\s*-", TAG, re.MULTILINE),
        _words(("true", "false", "null", "yes", "no", "on", "off"), LITERAL),
    ),
    line_comment="#",
)

MARKDOWN_SPEC = LanguageSpec(
    "markdown", "Markdown", (".md", ".markdown", ".mdown"),
    (
        Rule(r"^#{1,6} [^\n]*", HEADING, re.MULTILINE),
        Rule(r"^```[\s\S]*?^```", STRING, re.MULTILINE),
        Rule(r"`[^`\n]+`", STRING),
        Rule(r"^\s*>[^\n]*", COMMENT, re.MULTILINE),
        Rule(r"\*\*[^*\n]+\*\*|__[^_\n]+__", KEYWORD),
        Rule(r"\[[^\]\n]*\]\([^)\n]*\)", TAG),
        Rule(r"^\s*[-*+] ", TAG, re.MULTILINE),
    ),
    line_comment=None,
)

LANGUAGES: Tuple[LanguageSpec, ...] = (
    PLAIN, PYTHON, JAVASCRIPT, TYPESCRIPT, JSON_SPEC, HTML_SPEC, CSS_SPEC,
    C_LANG, CPP_LANG, RUST_SPEC, GO_SPEC, JAVA_SPEC, SHELL_SPEC, SQL_SPEC,
    YAML_SPEC, MARKDOWN_SPEC,
)

BY_CODE: Dict[str, LanguageSpec] = {spec.code: spec for spec in LANGUAGES}

#: file name (lower case) → language, for extension-less files we know
BY_FILENAME: Dict[str, str] = {
    "makefile": "shell", "gnumakefile": "shell", "dockerfile": "shell",
    "cmakelists.txt": "shell", ".bashrc": "shell", ".zshrc": "shell",
    "pkgbuild": "shell", "apkbuild": "shell", ".gitconfig": "shell",
    "requirements.txt": "plain", "npmrc": "shell", "pipfile": "shell",
}

_EXTENSION_INDEX: Dict[str, str] = {}
for _spec in LANGUAGES:
    for _ext in _spec.extensions:
        _EXTENSION_INDEX[_ext.lower()] = _spec.code


def language_for_path(path: Optional[Path | str]) -> str:
    """Best guess for a document's language, ``"plain"`` when unknown."""
    if not path:
        return PLAIN.code
    path = Path(path)
    name = path.name.lower()
    if name in BY_FILENAME:
        return BY_FILENAME[name]
    return _EXTENSION_INDEX.get(path.suffix.lower(), PLAIN.code)


def get_language(code: Optional[str]) -> LanguageSpec:
    return BY_CODE.get(code or "", PLAIN)


def language_choices() -> Tuple[Tuple[str, str], ...]:
    """(code, label) pairs for the manual override menu."""
    return tuple((spec.code, spec.name) for spec in LANGUAGES)


def line_comment_for(path_or_code: Optional[str]) -> Optional[str]:
    """The line-comment prefix, for a "toggle comment" command."""
    code = path_or_code if path_or_code in BY_CODE else language_for_path(path_or_code)
    return get_language(code).line_comment
