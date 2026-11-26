"""Licensing side of the release: the notices exist and every package ships them.

Qt and PySide6 are LGPL v3.  Two of our artefacts (the AppImage and the MSI)
bundle those libraries, which obliges us to hand the user the licence text *and*
a way to replace the library.  A packaging recipe that quietly stops copying
``THIRD-PARTY-NOTICES.md`` breaks that obligation without breaking any build,
so the rule is asserted here as well as in ``scripts/verify-packaging.sh``.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
NOTICE = REPO / "THIRD-PARTY-NOTICES.md"

#: Every recipe that produces a package we publish.
RECIPES = {
    "deb": "scripts/build-deb.sh",
    "rpm": "packaging/rpm/mishkah-note.spec",
    "arch": "packaging/arch/PKGBUILD",
    "appimage": "packaging/appimage/build-appimage.sh",
    "flatpak": "packaging/flatpak/org.mishkahnote.Mishkah.json",
    "msi": "scripts/build-msi.ps1",
}


def test_notice_file_ships_with_the_source():
    assert NOTICE.is_file(), "THIRD-PARTY-NOTICES.md is missing from the repository"
    assert "include THIRD-PARTY-NOTICES.md" in (REPO / "MANIFEST.in").read_text(encoding="utf-8")


@pytest.mark.parametrize("licence", ["LGPL v3", "OFL", "MIT", "PSF License"])
def test_notice_names_every_licence_in_the_payload(licence):
    assert licence in NOTICE.read_text(encoding="utf-8")


def test_notice_explains_how_to_replace_qt():
    """LGPL v3 requires that the user can swap the bundled Qt libraries."""
    text = NOTICE.read_text(encoding="utf-8")
    assert "appimage-extract" in text
    assert "Replace" in text or "replace" in text
    assert "PySide6" in text and "Qt" in text


@pytest.mark.parametrize("recipe", sorted(RECIPES.values()))
def test_recipe_installs_the_notices(recipe):
    text = (REPO / recipe).read_text(encoding="utf-8")
    assert "THIRD-PARTY-NOTICES" in text, f"{recipe} does not ship the notices"


def test_bundled_components_are_documented_where_they_are_bundled():
    """The two artefacts that carry Qt must say so, and say where it lives."""
    text = NOTICE.read_text(encoding="utf-8")
    assert "AppImage" in text and "MSI" in text
    assert "python-packages/PySide6" in text      # AppImage layout
    assert "_internal" in text                     # PyInstaller layout


# ------------------------------------------------------------- P2: AppImage ---
def test_appimage_bundles_a_python_runtime():
    text = (REPO / "packaging/appimage/build-appimage.sh").read_text(encoding="utf-8")
    assert "python-build-standalone" in text
    assert "usr/python/bin/python3" in text
    # The host interpreter may only be used when the bundling is switched off.
    assert 'MISHKAH_APPIMAGE_SYSTEM_PYTHON:-0' in text


def test_appimage_pins_the_interpreter_it_downloads():
    text = (REPO / "packaging/appimage/build-appimage.sh").read_text(encoding="utf-8")
    assert "PBS_RELEASE=" in text and "PBS_PYTHON=" in text
    assert "install_only.tar.gz" in text


def test_appimage_offline_build_can_reuse_a_local_archive():
    """A machine with no network still has to be able to build the image."""
    text = (REPO / "packaging/appimage/build-appimage.sh").read_text(encoding="utf-8")
    assert "MISHKAH_PYTHON_STANDALONE_ARCHIVE" in text


# ------------------------------------------------------------------- scripts ---
@pytest.mark.parametrize("script", ["scripts/smoke-test.sh",
                                    "packaging/appimage/build-appimage.sh",
                                    "scripts/verify-packaging.sh"])
def test_shell_scripts_parse(script):
    result = subprocess.run(["bash", "-n", str(REPO / script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_smoke_test_checks_a_version_and_a_round_trip():
    text = (REPO / "scripts/smoke_check.py").read_text(encoding="utf-8")
    assert "--expect" in text
    assert "write_text_atomic" in text and "load_file" in text
    driver = (REPO / "scripts/smoke-test.sh").read_text(encoding="utf-8")
    for flag in ("--deb", "--appimage", "--build"):
        assert flag in driver


# ------------------------------------------------------------ version gate ---
def test_version_gate_passes():
    result = subprocess.run([sys.executable, "tools/check_version.py"],
                            cwd=REPO, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_gate_reads_untracked_files_too():
    """A brand-new file is invisible to ``git ls-files`` until it is added.

    A stale version string there used to pass locally and fail only in CI, which
    is the worst place to learn about it.
    """
    source = (REPO / "tools/check_version.py").read_text(encoding="utf-8")
    assert '"--others"' in source and '"--exclude-standard"' in source


def test_gate_keeps_release_history():
    """An older <release> entry or changelog line is history, not a mistake."""
    sys.path.insert(0, str(REPO / "tools"))
    import check_version

    assert "packaging/rpm/mishkah-note.spec" in check_version.HISTORY_FILES
    assert "packaging/common/org.mishkahnote.Mishkah.metainfo.xml" in check_version.HISTORY_FILES


def test_gate_allows_prose_about_a_different_version():
    """A decision record may quote the spelling we rejected, but only on purpose."""
    sys.path.insert(0, str(REPO / "tools"))
    import check_version

    assert check_version.ALLOW_MARKER == "version-gate: allow"
    text = (REPO / "docs/PRE_W4_ORDER.ar.md").read_text(encoding="utf-8")
    # The marker below keeps the *gate* from flagging this line's own token.
    quoted = [ln for ln in text.splitlines() if "`1.0.2`" in ln]  # version-gate: allow
    assert quoted, "the D3 decision should still quote the rejected spelling"
    assert all(check_version.ALLOW_MARKER in line for line in quoted)


def test_bump_moves_the_rpm_default_without_touching_the_changelog():
    sys.path.insert(0, str(REPO / "tools"))
    import bump_version

    before = (REPO / bump_version.SPEC).read_text(encoding="utf-8")
    sentinel, target = "0.0.1", "9.9.9"  # version-gate: allow
    assert bump_version.update_spec_version(sentinel, target, dry_run=True) is True
    assert (REPO / bump_version.SPEC).read_text(encoding="utf-8") == before
