"""The settings file is untrusted input: it must never stop the app starting.

Each case here was reproduced against the pre-schema loader, where a JSON list
raised ``AttributeError`` and wrong types were accepted verbatim.
"""

from __future__ import annotations

import json

import pytest

from mishkah.core.settings import SCHEMA, Settings


def write(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_missing_file_yields_defaults_without_complaint(tmp_path):
    settings, repairs = Settings.load_detailed(tmp_path / "settings.json")
    assert settings.font_size == 13
    assert settings.recent_files == []
    assert repairs == []
    assert settings.path == tmp_path / "settings.json"


def test_json_list_is_backed_up_and_ignored(tmp_path):
    target = tmp_path / "settings.json"
    target.write_text("[]", encoding="utf-8")

    settings, repairs = Settings.load_detailed(target)

    assert settings.theme == "system"
    assert repairs and "does not contain a JSON object" in repairs[0]
    assert (tmp_path / "settings.json.bak").read_text(encoding="utf-8") == "[]"


def test_broken_json_is_backed_up_and_ignored(tmp_path):
    target = tmp_path / "settings.json"
    target.write_text("{not json", encoding="utf-8")

    settings, repairs = Settings.load_detailed(target)

    assert settings.font_size == 13
    assert repairs and "not valid JSON" in repairs[0]
    assert (tmp_path / "settings.json.bak").exists()


def test_wrong_types_fall_back_to_defaults(tmp_path):
    target = write(tmp_path / "settings.json", {
        "font_size": "abc",
        "tab_width": -5,
        "theme": 3,
        "word_wrap": "yes",
    })

    settings, repairs = Settings.load_detailed(target)

    assert settings.font_size == 13
    assert settings.tab_width == 4
    assert settings.theme == "system"
    assert settings.word_wrap is True
    assert len(repairs) == 4


def test_out_of_range_values_are_rejected(tmp_path):
    target = write(tmp_path / "settings.json", {"font_size": 400, "tab_width": 0})
    settings, repairs = Settings.load_detailed(target)
    assert settings.font_size == 13
    assert settings.tab_width == 4
    assert any("outside" in repair for repair in repairs)


def test_unknown_keys_are_dropped(tmp_path):
    target = write(tmp_path / "settings.json", {"font_size": 15, "evil": "x"})
    settings = Settings.load(target)
    assert settings.font_size == 15
    assert not hasattr(settings, "evil")
    assert "evil" not in settings.sanitised()


def test_valid_values_are_preserved(tmp_path):
    target = write(tmp_path / "settings.json", {
        "theme": "dark",
        "font_size": 18,
        "default_direction": "rtl",
        "syntax_highlighting": True,
    })
    settings, repairs = Settings.load_detailed(target)
    assert (settings.theme, settings.font_size) == ("dark", 18)
    assert settings.default_direction == "rtl"
    assert settings.syntax_highlighting is True
    assert repairs == []


def test_path_lists_are_sanitised_and_capped(tmp_path):
    payload = {"recent_files": ["/a.txt", 7, "", "/a.txt"] + [f"/f{i}.txt" for i in range(80)]}
    settings, repairs = Settings.load_detailed(write(tmp_path / "settings.json", payload))
    assert settings.recent_files[:2] == ["/a.txt", "/f0.txt"]
    assert len(settings.recent_files) == 50
    assert any("dropped" in repair for repair in repairs)
    assert any("kept the newest" in repair for repair in repairs)


def test_hard_limit_is_never_below_the_confirm_threshold(tmp_path):
    settings, repairs = Settings.load_detailed(
        write(tmp_path / "settings.json", {"ask_before_mb": 200, "hard_limit_mb": 10})
    )
    assert settings.hard_limit_mb == 200
    assert any("hard_limit_mb" in repair for repair in repairs)


def test_unknown_language_falls_back(tmp_path):
    settings, repairs = Settings.load_detailed(
        write(tmp_path / "settings.json", {"ui_language": "klingon"})
    )
    assert settings.ui_language == "en"
    assert any("ui_language" in repair for repair in repairs)


def test_save_refuses_to_write_invalid_runtime_values(tmp_path):
    target = tmp_path / "settings.json"
    settings = Settings()
    settings.tab_width = 0          # a future UI bug, not a user edit
    settings.font_size = "large"    # type: ignore[assignment]
    settings.save(target)

    stored = json.loads(target.read_text(encoding="utf-8"))
    assert stored["tab_width"] == 4
    assert stored["font_size"] == 13


def test_save_load_round_trip(tmp_path):
    target = tmp_path / "settings.json"
    original = Settings(theme="light", font_size=16, recent_files=["/notes.txt"])
    original.save(target)

    loaded = Settings.load(target)

    assert loaded.theme == "light"
    assert loaded.font_size == 16
    assert loaded.recent_files == ["/notes.txt"]
    assert loaded.repairs == []


@pytest.mark.parametrize("name", sorted(SCHEMA))
def test_schema_defaults_are_valid(name):
    """Every persisted field survives its own coercion unchanged."""
    defaults = Settings._defaults()
    value = Settings._coerce(name, defaults[name], defaults[name], [])
    assert value == defaults[name]
