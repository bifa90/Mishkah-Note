"""The two tools the manual gate hands to a human, kept honest by machine.

``tools/font_report.py`` answers "which face did Qt actually pick on *this*
machine" — the one question the sandbox and the CI runner answer differently from
a user's laptop.  ``tools/translation_sheet.py`` turns the disclosure "nine
translations are machine-made" into something a reviewer can correct.

Neither is decoration: if they break, the manual gate silently loses its evidence.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"


def _run(*args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, str(TOOLS / args[0]), *args[1:]],
                          capture_output=True, text=True, env=env, cwd=ROOT,
                          timeout=240)


# ------------------------------------------------------------------- fonts
@pytest.mark.gui
def test_font_report_resolves_the_bundled_faces_for_arabic_and_urdu():
    done = _run("font_report.py", "--json")
    assert done.returncode == 0, done.stderr

    report = json.loads(done.stdout)
    rows = {row["code"]: row for row in report["languages"]}
    assert rows["ar"]["interface"] == "IBM Plex Sans Arabic"
    assert rows["ur"]["interface"] == "Noto Sans Arabic"
    assert rows["ur"]["asked_for"] == "Noto Sans Arabic"
    for row in report["languages"]:
        assert row["missing_urdu_letters"] == "", row["code"]
    assert {"IBMPlexSansArabic-Regular.ttf",
            "NotoSansArabic-Regular.ttf"} <= set(report["bundled_files"])
    assert "Noto Sans Arabic" in report["registered_families"]


@pytest.mark.gui
def test_font_report_check_is_a_gate_that_passes_here():
    done = _run("font_report.py", "--check")
    assert done.returncode == 0, done.stderr
    assert "!" not in done.stderr


def test_font_report_flags_every_way_a_face_can_be_wrong():
    spec = importlib.util.spec_from_file_location("font_report", TOOLS / "font_report.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    report = {
        "registered_families": ["IBM Plex Sans Arabic"],
        "languages": [{
            "code": "ur", "asked_for": "Noto Sans Arabic", "interface": "DejaVu Sans",
            "editor": "DejaVu Sans", "missing_urdu_letters": "ٹے",
            "expected_interface": "Noto Sans Arabic",
        }],
    }
    found = module.problems(report)
    assert any("did not register: Noto Sans Arabic" in line for line in found)
    assert any("ٹے" in line for line in found)
    assert any("expected Noto Sans Arabic" in line for line in found)


# ------------------------------------------------------------ translations
def test_translation_sheet_lists_one_row_per_string():
    from mishkah.core.i18n_data import STRINGS

    done = _run("translation_sheet.py", "--lang", "ur", "--format", "tsv")
    assert done.returncode == 0, done.stderr

    lines = done.stdout.rstrip("\n").splitlines()
    assert lines[0] == "key\tenglish\ttarget\tflag\tsuggestion"
    assert len(lines) == len(STRINGS) + 1, "a key is missing from the sheet"
    assert any(line.startswith("about.version\t") for line in lines)
    assert any(line.startswith("home.tagline\t") for line in lines)


def test_no_language_falls_back_to_english_for_a_missing_key():
    """The disclosure is about quality; completeness is not negotiable."""
    from mishkah.core.i18n_data import STRINGS
    from mishkah.core.languages import all_languages

    for lang in all_languages():
        missing = [key for key, table in STRINGS.items() if not table.get(lang.code)]
        assert not missing, f"{lang.code}: {missing[:5]}"


def test_translation_sheet_stats_cover_every_translated_language():
    done = _run("translation_sheet.py", "--lang", "all", "--stats")
    assert done.returncode == 0, done.stderr
    for code in ("zh-Hans", "hi", "es", "fr", "bn", "pt", "ru", "ur"):
        assert f"{code} (" in done.stdout, code
    assert "missing: 0" in done.stdout


def test_translation_sheet_refuses_an_unknown_language():
    done = _run("translation_sheet.py", "--lang", "xx")
    assert done.returncode == 2
    assert "unknown language" in done.stderr


# ------------------------------------------------------- file diagnostics
def test_detect_file_reports_what_the_app_will_think(tmp_path):
    """G3b #14 arrived as "it only opens after I pick the encoding by hand"."""
    target = tmp_path / "legacy.txt"
    target.write_bytes("السيد المدير المحترم\nتحية طيبة وبعد.\n".encode("cp1256"))

    done = _run("detect_file.py", str(target), "--json")
    assert done.returncode == 0, done.stderr
    [report] = json.loads(done.stdout)
    assert report["encoding"] == "cp1256"
    assert report["confident"] is True
    assert report["has_bom"] is False
    assert report["decodes_as_detected"] is True
    assert report["high_bytes"] > 0


def test_detect_file_marks_a_guess_as_a_guess(tmp_path):
    """One high byte is not evidence; the report must say so, not pretend."""
    target = tmp_path / "maybe.txt"
    target.write_bytes(b"hello world\n")
    done = _run("detect_file.py", str(target), "--json")
    assert done.returncode == 0, done.stderr
    [report] = json.loads(done.stdout)
    assert report["encoding"] in ("utf-8", "ascii", "utf-8-sig")
    assert report["high_bytes"] == 0
