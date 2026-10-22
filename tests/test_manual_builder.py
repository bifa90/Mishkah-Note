"""The manual builder reports missing targets honestly and uses native recipes."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("manual_builder", ROOT / "scripts/build_release.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def test_target_profiles():
    assert builder.selected_targets("all") == list(builder.TARGETS)
    assert "msi" not in builder.selected_targets("linux")
    assert builder.selected_targets("python,deb,python") == ["python", "deb"]
    with pytest.raises(ValueError):
        builder.selected_targets("unknown")


def test_windows_cannot_be_built_on_linux(monkeypatch):
    monkeypatch.setattr(builder.platform, "system", lambda: "Linux")
    monkeypatch.setattr(builder.shutil, "which", lambda tool: "/usr/bin/" + tool)
    assert any("requires Windows" in issue for issue in builder.missing_requirements("msi"))


def test_missing_tools_are_explicit(monkeypatch):
    monkeypatch.setattr(builder.platform, "system", lambda: "Linux")
    monkeypatch.setattr(builder.shutil, "which", lambda _: None)
    assert "missing executable: rpmbuild" in builder.missing_requirements("rpm")


def test_commands_preserve_output_and_flatpak_branch(tmp_path):
    assert str(tmp_path) in builder.commands("python", tmp_path)[0]
    assert "--default-branch=stable" in builder.commands("flatpak", tmp_path)[0]
    assert str(tmp_path / "org.mishkahnote.Mishkah.flatpak") in builder.commands("flatpak", tmp_path)[1]


def test_version():
    assert builder.version() == "1.0.01"


def test_failed_preflight_does_not_start_build(monkeypatch):
    monkeypatch.setattr(builder.sys, "argv", ["builder", "--formats", "rpm"])
    monkeypatch.setattr(builder, "missing_requirements", lambda _: ["missing tool"])
    monkeypatch.setattr(builder.subprocess, "run", lambda *a, **k: pytest.fail("must not start"))
    assert builder.main() == 2
