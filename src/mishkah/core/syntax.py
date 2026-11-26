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


#: How much of a document the content sniffer looks at.
SNIFF_TEXT_LIMIT = 8000

#: Tie-break order when two languages score the same (more specific first).
_ORDER = ("python", "typescript", "javascript", "rust", "go", "java", "cpp",
          "c", "shell", "sql", "yaml", "css", "html", "markdown", "json",
          "plain")

#: Ordered (language, pattern, weight) markers.  The first language whose
#: strong marker matches wins; weak markers only break ties between two
#: candidates that are both plausible.
_CONTENT_MARKERS: Tuple[Tuple[str, str, int], ...] = (
    ("python", r"^#!.*\bpython[0-9.]*\b", 3),
    ("shell", r"^#!.*\b(?:ba|z|k)?sh\b", 3),
    ("javascript", r"^#!.*\bnode\b", 3),
    ("python", r"^\s*(?:async\s+)?def\s+\w+\s*\(", 3),
    ("python", r"^\s*class\s+\w+\s*[:(]", 2),
    ("python", r"^\s*(?:from\s+[\w.]+\s+)?import\s+[\w.]+", 2),
    ("python", r"^if\s+__name__\s*==", 3),
    ("rust", r"^\s*fn\s+\w+\s*\(", 3),
    ("rust", r"^\s*(?:let\s+mut|use\s+std::|impl\s+\w+|pub\s+fn)\b", 2),
    ("go", r"^\s*package\s+\w+\s*$", 3),
    ("go", r"^\s*func\s+\w+\s*\(", 2),
    ("java", r"^\s*public\s+(?:final\s+)?class\s+\w+", 2),
    ("java", r"^\s*public\s+static\s+void\s+main\s*\(", 3),
    ("typescript", r"^\s*(?:export\s+)?interface\s+\w+\s*\{", 3),
    ("typescript", r"^\s*(?:export\s+)?type\s+\w+\s*=", 2),
    ("typescript", r"\w+\s*:\s*(?:string|number|boolean|void)\b", 2),
    ("javascript", r"^\s*(?:export\s+)?(?:async\s+)?function\s+\w+\s*\(", 3),
    ("javascript", r"^\s*(?:const|let|var)\s+\w+\s*=", 2),
    ("javascript", r"=>|console\.log\(|document\.\w+", 2),
    ("sql", r"(?i)^\s*(?:select\s+[\s\S]{0,200}?\bfrom|insert\s+into|update\s+\w+\s+set|"
            r"create\s+(?:table|index|view)|delete\s+from)\b", 3),
    ("cpp", r"^\s*#include\s*<(?:iostream|vector|string|map|memory)>", 3),
    ("cpp", r"\bstd::\w+", 2),
    ("c", r"^\s*#include\s*<\w+\.h>", 3),
    ("c", r"^\s*(?:int|void)\s+main\s*\(", 2),
    ("css", r"^\s*[.#]?[\w-]+(?:\s*[,>]\s*[.#]?[\w-]+)*\s*\{[\s\S]*?"
            r"(?:color|margin|padding|display|font-size)\s*:", 3),
    ("html", r"(?i)^\s*(?:<!doctype\s+html|<html|<head|<body|<!--)", 3),
    ("html", r"(?i)</(?:div|p|span|a|ul|li|table|section|article)>", 2),
    ("yaml", r"^---\s*$", 2),
    ("yaml", r"^[\w.-]+:\s*(?:$|[^/{\[])", 1),
    ("shell", r"^\s*(?:if\s+\[|fi\b|done\b|esac\b|export\s+\w+=)", 2),
    ("markdown", r"^#{1,6}\s+\S", 3),
    ("markdown", r"^```", 3),
    ("markdown", r"^\s*(?:[-*+]\s+\S|\d+\.\s+\S)", 1),
    ("json", r"^\s*[\[{]", 1),
)


def language_for_text(text: str) -> str:
    """Guess the language of *text* from its content (CD-12 · paste).

    Highlighting used to follow the file name only, so code pasted into an
    untitled buffer stayed grey until the file was saved and opened again.
    The rules are deliberately conservative: a language is reported only when
    a *strong* marker is present, otherwise ``"plain"``.
    """
    if not text or not text.strip():
        return PLAIN.code
    head = text[:SNIFF_TEXT_LIMIT]
    sample = head.replace("\r\n", "\n").replace("\r", "\n")

    if sample.lstrip().startswith(("{", "[")):
        try:
            import json as _json
            _json.loads(sample.strip())
            return JSON_SPEC.code
        except ValueError:
            pass

    scores: Dict[str, int] = {}
    for code, pattern, weight in _CONTENT_MARKERS:
        if re.search(pattern, sample, re.MULTILINE):
            scores[code] = scores.get(code, 0) + weight
    if not scores:
        return PLAIN.code
    best = max(scores, key=lambda code: (scores[code], -_ORDER.index(code)
                                         if code in _ORDER else 0))
    if scores[best] < 2:
        return PLAIN.code
    # A Markdown fence around the sample means the buffer is Markdown, even
    # if the fenced body looks like another language.
    if scores.get("markdown", 0) >= 3 and scores[best] <= scores["markdown"]:
        return MARKDOWN_SPEC.code
    return best


def get_language(code: Optional[str]) -> LanguageSpec:
    return BY_CODE.get(code or "", PLAIN)


#: What each language is called in Arabic.  A program's name is a proper noun,
#: so the entries that are letters or acronyms (``C``, ``JSON``, ``SQL``) stay
#: as they are — transliterating them is how Arabic menus end up unreadable —
#: while the names that are ordinary words (``Plain text``, ``Shell``) are
#: translated.  The status bar and the language menu read this table.
ARABIC_NAMES: Dict[str, str] = {
    "plain": "نص عادي",
    "python": "بايثون",
    "javascript": "جافاسكربت",
    "typescript": "تايبسكربت",
    "json": "JSON",
    "html": "HTML",
    "css": "CSS",
    "c": "C",
    "cpp": "C++",
    "rust": "رست",
    "go": "جو",
    "java": "جافا",
    "shell": "شل",
    "sql": "SQL",
    "yaml": "YAML",
    "markdown": "ماركداون",
}


def display_name(code: Optional[str], language: str = "en") -> str:
    """The language's name as the *user* should see it.

    Arabic readers get the Arabic table above; every other interface language
    keeps the Latin name, which is correct rather than half-translated.  An
    unknown code degrades to ``Plain text`` instead of an empty label.
    """
    spec = get_language(code)
    if (language or "").split("-")[0].lower() == "ar":
        return ARABIC_NAMES.get(spec.code, spec.name)
    return spec.name


def language_choices(language: str = "en") -> Tuple[Tuple[str, str], ...]:
    """(code, label) pairs for the manual override menu, in *language*."""
    return tuple((spec.code, display_name(spec.code, language)) for spec in LANGUAGES)


def line_comment_for(path_or_code: Optional[str]) -> Optional[str]:
    """The line-comment prefix, for a "toggle comment" command."""
    code = path_or_code if path_or_code in BY_CODE else language_for_path(path_or_code)
    return get_language(code).line_comment
