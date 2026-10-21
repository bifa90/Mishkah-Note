"""Project-level guarantees: branding, packaging metadata and the About box."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
AUTHOR_MARKERS = ("بلال", "Bilal", "bifa90")


def _tracked_text_files() -> list[Path]:
    """Every source file that ships in the repository (no build dirs)."""
    skip = {".git", "build", "dist", ".pytest_cache", "__pycache__", ".venv",
            ".qtstub", "node_modules"}
    out: list[Path] = []
    for path in REPO.rglob("*"):
        if not path.is_file():
            continue
        if any(part in skip for part in path.parts):
            continue
        if path.suffix.lower() in {".png", ".ico", ".ttf", ".otf", ".deb",
                                   ".whl", ".gz", ".zst", ".AppImage"}:
            continue
        if "egg-info" in path.parts:
            continue
        out.append(path)
    return out


def test_author_appears_only_in_the_about_box():
    """The developer's name lives in the About dialog and nowhere else."""
    offenders = []
    for path in _tracked_text_files():
        if path.name == "about_dialog.py":
            continue
        # The suite itself asserts the *absence* of the name, so it is skipped.
        if "tests" in path.relative_to(REPO).parts:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            if "github.com" in line:
                continue          # the repository URL is the project, not a credit
            for marker in AUTHOR_MARKERS:
                if marker in line:
                    offenders.append(f"{path.relative_to(REPO)}:{number}: {line.strip()}")
    offenders = [line for line in offenders if "egg-info" not in line]
    assert offenders == [], offenders


def test_about_dialog_credits_author_and_assistants():
    from mufakkira.widgets.about_dialog import AI_ASSISTANTS, AUTHOR, about_html

    assert "بلال" in AUTHOR
    html = about_html()
    # the name is wrapped in bidi isolates, so compare the two halves
    assert "بلال فضل" in html
    assert "Bilal Fadl" in html
    for name in AI_ASSISTANTS:
        assert name in html
    assert "DeepSeek" in html


def test_about_dialog_has_no_rtl_explanation():
    """The direction essay was removed from the About box on request."""
    from mufakkira.widgets.about_dialog import about_html

    html = about_html().lower()
    for forbidden in ("rtl", "right-to-left", "اتجاه", "ctrl+shift"):
        assert forbidden not in html, forbidden


def test_window_title_has_no_author():
    from mufakkira.core import i18n

    i18n.set_language("en")
    title = i18n.tr("app.title", title="notes.txt", app=i18n.tr("app.name"))
    assert title == "notes.txt - Notepad"
    assert not any(marker in title for marker in AUTHOR_MARKERS)


def test_version_is_consistent_everywhere():
    import mufakkira

    pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    version = re.search(r'^version = "([^"]+)"', pyproject, re.M).group(1)
    assert version == mufakkira.__version__
    assert version == mufakkira.APP_VERSION

    changelog = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    assert f"## [{version}]" in changelog


def test_pyproject_declares_entry_points_and_assets():
    pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    assert 'notepad = "mufakkira.app:main"' in pyproject
    assert "resources/icons/*.png" in pyproject
    assert "resources/fonts/*.ttf" in pyproject
    assert "resources/styles/*.qss" in pyproject


def test_packaging_files_exist():
    for relative in (
        "packaging/common/notepad.desktop",
        "packaging/common/notepad.1",
        "packaging/rpm/notepad-linux.spec",
        "packaging/arch/PKGBUILD",
        "packaging/flatpak/org.notepadlinux.Notepad.json",
        "packaging/appimage/build-appimage.sh",
        "scripts/build-deb.sh",
        "scripts/build-all.sh",
        "tools/make_icon.py",
    ):
        assert (REPO / relative).exists(), relative


def test_desktop_entry_is_valid():
    text = (REPO / "packaging/common/notepad.desktop").read_text(encoding="utf-8")
    assert text.startswith("[Desktop Entry]")
    for key in ("Type=Application", "Exec=notepad %F", "Icon=notepad-linux",
                "Categories=Utility;TextEditor;", "Name[ar]="):
        assert key in text, key
    assert "bifa90" not in text or "github.com" in text


def test_legacy_files_are_gone():
    assert not (REPO / "p.py").exists()
    assert not (REPO / "Notepad_Linux_1.0.0.deb").exists()


@pytest.mark.parametrize("size", [16, 24, 32, 48, 64, 128, 256, 512])
def test_every_icon_size_exists(size):
    from mufakkira.core import resources

    assert (resources.ICONS_DIR / f"app-{size}.png").exists()
