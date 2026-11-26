#!/usr/bin/env python3
"""Say which face each language's chrome and editor actually get on *this* machine.

Why this exists: "the Urdu menu is legible now" is a claim about a machine, not
about the source.  The Ubuntu runner has system Noto fonts, the Windows runner
has Segoe UI, and a user's laptop has neither — yet all three run the same code.
So instead of guessing, this prints what Qt resolved here, whether the bundled
faces are the ones doing the work, and whether the Urdu letters exist at all.

    QT_QPA_PLATFORM=offscreen python tools/font_report.py           # readable
    python tools/font_report.py --json                              # to paste
    python tools/font_report.py --check                             # exit 1 if broken

``--check`` is what a test (or a curious maintainer) runs: it fails unless both
bundled faces registered and Arabic/Urdu resolve to them.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtCore import qVersion  # noqa: E402
from PySide6.QtGui import QFont, QFontInfo, QFontMetrics  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

#: Letters that exist in Urdu and not in plain Arabic: the ones a wrong face
#: silently drops, leaving a menu that reads almost right.
URDU_LETTERS = "ٹڈڑںےھ"

#: The faces the wheels and packages carry; if they did not register, the
#: interface is borrowing from the system and the result differs per user.
BUNDLED_FAMILIES = ("IBM Plex Sans Arabic", "Noto Sans Arabic")

#: What each of these languages must resolve to when the bundle is in place.
EXPECTED = {"ar": "IBM Plex Sans Arabic", "ur": "Noto Sans Arabic"}


def resolved_family(families, point_size: int = 11) -> str:
    """The family Qt picks for a stack — the same question the UI asks."""
    font = QFont()
    font.setFamilies(list(families))
    font.setPointSize(point_size)
    return QFontInfo(font).family()


def missing_letters(family: str, letters: str = URDU_LETTERS) -> str:
    """Which of ``letters`` the resolved face cannot draw ('' when all are there)."""
    font = QFont()
    font.setFamilies([family])
    font.setPointSize(11)
    metrics = QFontMetrics(font)
    return "".join(ch for ch in letters if not metrics.inFontUcs4(ord(ch)))


def collect() -> dict:
    from mishkah.app import install_bundled_fonts
    from mishkah.core import resources
    from mishkah.core.languages import all_languages

    app = QApplication.instance() or QApplication([])   # noqa: F841 (needed for Qt)
    registered = install_bundled_fonts()

    rows = []
    for lang in all_languages():
        chrome = resolved_family(lang.ui_fonts)
        rows.append({
            "code": lang.code,
            "asked_for": lang.ui_fonts[0],
            "interface": chrome,
            "editor": resolved_family(lang.editor_fonts, 13),
            "missing_urdu_letters": missing_letters(chrome),
            "expected_interface": EXPECTED.get(lang.code, ""),
        })

    return {
        "qt": qVersion(),
        "platform": app.platformName(),
        "bundled_files": [p.name for p in resources.available_fonts()],
        "registered_families": list(registered),
        "languages": rows,
    }


def problems(report: dict) -> list:
    """Everything that would make the interface differ from the reviewed one."""
    found = []
    for family in BUNDLED_FAMILIES:
        if family not in report["registered_families"]:
            found.append(f"bundled face did not register: {family}")
    for row in report["languages"]:
        if row["missing_urdu_letters"]:
            found.append(f"{row['code']}: {row['interface']} lacks "
                         f"{row['missing_urdu_letters']}")
        expected = row["expected_interface"]
        if expected and row["interface"] != expected:
            found.append(f"{row['code']}: interface is {row['interface']}, "
                         f"expected {expected}")
    return found


def render(report: dict) -> str:
    lines = [
        f"Qt {report['qt']} · platform {report['platform']}",
        f"bundled files: {', '.join(report['bundled_files']) or 'none'}",
        f"registered families: {', '.join(report['registered_families']) or 'none'}",
        "",
        f"{'lang':8}{'asked for':26}{'interface face':26}{'editor face':26}urdu",
    ]
    for row in report["languages"]:
        absent = row["missing_urdu_letters"] or "ok"
        lines.append(f"{row['code']:8}{row['asked_for']:26}"
                     f"{row['interface']:26}{row['editor']:26}{absent}")
    return "\n".join(lines)


def main(argv: list | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    report = collect()

    if "--json" in args:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render(report))

    found = problems(report)
    if found:
        print("\n" + "\n".join(f"  ! {line}" for line in found), file=sys.stderr)
    if "--check" in args:
        return 1 if found else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
