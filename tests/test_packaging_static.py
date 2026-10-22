"""Release recipes must preserve the current source, identity and resources."""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def test_dark_theme_does_not_override_application_font():
    for theme in ("light", "dark"):
        text = (REPO / f"src/mishkah/resources/styles/{theme}.qss").read_text()
        text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
        block = re.search(r"(?m)^QWidget\s*\{([^}]+)\}", text)
        if block:
            assert "font-size" not in block[1]
            assert "font-family" not in block[1]


def test_appimage_version_snippet_reads_project_version():
    import subprocess
    import sys

    text = (REPO / "packaging/appimage/build-appimage.sh").read_text()
    snippet = text.split("<<'EOF'\n", 1)[1].split("\nEOF", 1)[0]
    result = subprocess.run([sys.executable, "-c", snippet], cwd=REPO,
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "1.0.01"


def test_sdist_includes_windows_build_inputs():
    manifest = (REPO / "MANIFEST.in").read_text()
    packaging = next(line for line in manifest.splitlines() if line.startswith("recursive-include packaging "))
    scripts = next(line for line in manifest.splitlines() if line.startswith("recursive-include scripts "))
    assert "*.wxs" in packaging and "*.py" in packaging
    assert "*.ps1" in scripts


def test_arch_build_uses_checkout_archive():
    script = (REPO / "scripts/build-arch.sh").read_text()
    recipe = (REPO / "packaging/arch/PKGBUILD").read_text()
    assert "git archive" in script
    assert "export MISHKAH_SOURCE_ARCHIVE=" in script
    assert 'source=("${MISHKAH_SOURCE_ARCHIVE##*/}")' in recipe


def test_pyinstaller_spec_not_given_makespec_flags():
    text = (REPO / "scripts/build-msi.ps1").read_text()
    command = text.split("python -m PyInstaller", 1)[1].split('"packaging/windows/mishkah.spec"', 1)[0]
    assert "--onedir" not in command
    assert "--onefile" not in command
