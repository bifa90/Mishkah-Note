#!/usr/bin/env python3
"""Print one language's interface strings as a sheet a native speaker can mark up.

Nine of the ten translations are machine-made and we say so in the release
notes; that disclosure is only honest if a reviewer *can* act on it.  This turns
``core/i18n_data.py`` into a table with the English source beside the target, so
a reviewer with no Python knowledge can read, correct, and return it.

    python tools/translation_sheet.py --lang ur              # markdown sheet
    python tools/translation_sheet.py --lang ur --stats      # coverage numbers
    python tools/translation_sheet.py --lang ur --format tsv # for a spreadsheet
    python tools/translation_sheet.py --lang ur --out ur.md

Keys whose text is byte-identical to the English are flagged ``=en``: for a
translation that is usually a sign it was never translated, and for a handful of
keys (``C``, ``JSON``, ``SQL``) it is correct — the reviewer decides.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from mishkah.core.i18n_data import STRINGS  # noqa: E402
from mishkah.core.languages import all_languages  # noqa: E402

CODES = tuple(lang.code for lang in all_languages())
NAMES = {lang.code: lang.native_name for lang in all_languages()}


def _flat(text: str) -> str:
    """One line per cell: a newline inside a string would break the table."""
    return (text.replace("\r\n", "\n").replace("\n", " ⏎ ")
                .replace("\r", " ⏎ ").replace("\t", " ").strip())


def rows(code: str) -> list:
    """(key, english, target, flag) in file order — the order a reader expects."""
    out = []
    for key, table in STRINGS.items():
        english = _flat(table.get("en", ""))
        target = _flat(table.get(code, ""))
        if not target:
            flag = "missing"
        elif target == english or target.strip() == english.strip():
            flag = "=en"
        else:
            flag = ""
        out.append((key, english, target, flag))
    return out


def stats(code: str) -> str:
    items = rows(code)
    missing = [key for key, _, _, flag in items if flag == "missing"]
    same = [key for key, _, _, flag in items if flag == "=en"]
    lines = [f"{code} ({NAMES.get(code, code)}): {len(items)} keys",
             f"  translated: {len(items) - len(missing)}",
             f"  missing: {len(missing)}"]
    if missing:
        lines.append("  " + ", ".join(missing[:12]) + (" …" if len(missing) > 12 else ""))
    lines.append(f"  identical to English (=en): {len(same)}")
    if same:
        lines.append("  " + ", ".join(same[:12]) + (" …" if len(same) > 12 else ""))
    return "\n".join(lines)


def as_markdown(code: str) -> str:
    title = f"# مراجعة ترجمة الواجهة · {NAMES.get(code, code)} (`{code}`)"
    head = ("\nعدّل عمود «المقترح» فقط، واتركه فارغًا إن كانت الترجمة الحالية صحيحة. "
            "`=en` تعني أن النص مطابق للإنجليزية.\n\n"
            "| المفتاح | English | الحالي | علم | المقترح |\n|---|---|---|---|---|")
    body = []
    for key, english, target, flag in rows(code):
        body.append(f"| `{key}` | {english} | {target} | {flag} |  |")
    return "\n".join([title, head, *body, ""])


def as_tsv(code: str) -> str:
    body = ["key\tenglish\ttarget\tflag\tsuggestion"]
    for key, english, target, flag in rows(code):
        body.append("\t".join([key, english, target, flag, ""]))
    return "\n".join(body)


def main(argv: list | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)

    def value(flag: str, default: str | None = None) -> str | None:
        if flag in args:
            at = args.index(flag)
            return args[at + 1] if at + 1 < len(args) else default
        return default

    code = value("--lang")
    if not code:
        print(f"usage: {Path(sys.argv[0]).name} --lang CODE "
              f"[--stats|--format md|tsv|--out FILE]\n"
              f"codes: {', '.join(CODES)}", file=sys.stderr)
        return 2
    if code != "all" and code not in CODES:
        print(f"unknown language {code!r}; expected one of: {', '.join(CODES)}",
              file=sys.stderr)
        return 2

    if "--stats" in args:
        wanted = [c for c in CODES if c not in ("en", "ar")] if code == "all" else [code]
        text = "\n\n".join(stats(item) for item in wanted)
    elif value("--format") == "tsv":
        text = as_tsv(code)
    else:
        text = as_markdown(code)

    target = value("--out")
    if target:
        Path(target).write_text(text + "\n", encoding="utf-8")
        print(f"wrote {target}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
