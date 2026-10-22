"""Project-level guarantees: branding, packaging metadata and the About box."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
AUTHOR_MARKERS = ("بلال", "Bilal", "bifa90")


def _tracked_text_files() -> list[Path]:
    """Every source file that ships in the repository (no build dirs)."""
    import subprocess

    names = subprocess.check_output(["git", "ls-files", "-z"], cwd=REPO).decode().split("\0")
    return [REPO / name for name in names if name and (REPO / name).is_file()]


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
            if "github.com" in line or "githubusercontent.com" in line:
                # A repository (or raw-content) URL names the project, not the
                # person; only the About box may carry the developer's name.
                continue
            for marker in AUTHOR_MARKERS:
                if marker in line:
                    offenders.append(f"{path.relative_to(REPO)}:{number}: {line.strip()}")
    offenders = [line for line in offenders if "egg-info" not in line]
    assert offenders == [], offenders


def test_about_dialog_credits_author_and_assistants():
    from mishkah.widgets.about_dialog import AI_ASSISTANTS, AUTHOR, about_html

    assert "بلال" in AUTHOR
    html = about_html()
    # the name is wrapped in bidi isolates, so compare the two halves
    assert "بلال فضل" in html
    assert "Bilal Fadl" in html
    for name in AI_ASSISTANTS:
        assert name in html
    assert "DeepSeek-V4.1-Flash" in html
    # assistants are named by model, never by the platform they run on
    assert "arena" not in html.lower()
    assert "agent mode" not in html.lower()


def test_about_dialog_has_no_rtl_explanation():
    """The direction essay was removed from the About box on request."""
    from mishkah.widgets.about_dialog import about_html

    html = about_html().lower()
    for forbidden in ("rtl", "right-to-left", "اتجاه", "ctrl+shift"):
        assert forbidden not in html, forbidden


def test_window_title_has_no_author():
    from mishkah.core import i18n

    i18n.set_language("en")
    title = i18n.tr("app.title", title="notes.txt", app=i18n.tr("app.name"))
    assert title == "notes.txt - Mishkah Note"
    assert not any(marker in title for marker in AUTHOR_MARKERS)


def test_version_is_consistent_everywhere():
    import mishkah

    pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    version = re.search(r'^version = "([^"]+)"', pyproject, re.M).group(1)
    assert version == mishkah.__version__
    assert version == mishkah.APP_VERSION

    changelog = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    assert f"## [{version}]" in changelog


def test_pyproject_declares_entry_points_and_assets():
    pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    assert 'mishkah = "mishkah.app:main"' in pyproject
    assert "resources/icons/*.png" in pyproject
    assert "resources/fonts/*.ttf" in pyproject
    assert "resources/styles/*.qss" in pyproject


def test_packaging_files_exist():
    for relative in (
        "packaging/common/mishkah.desktop",
        "packaging/common/mishkah.1",
        "packaging/rpm/mishkah-note.spec",
        "packaging/arch/PKGBUILD",
        "packaging/flatpak/org.mishkahnote.Mishkah.json",
        "packaging/appimage/build-appimage.sh",
        "scripts/build-deb.sh",
        "scripts/build-all.sh",
        "tools/make_icon.py",
    ):
        assert (REPO / relative).exists(), relative


def test_desktop_entry_is_valid():
    text = (REPO / "packaging/common/mishkah.desktop").read_text(encoding="utf-8")
    assert text.startswith("[Desktop Entry]")
    for key in ("Type=Application", "Exec=mishkah %F", "Icon=mishkah-note",
                "Categories=Utility;TextEditor;", "Name[ar]="):
        assert key in text, key
    assert "bifa90" not in text or "github.com" in text


@pytest.mark.parametrize("size", [16, 24, 32, 48, 64, 128, 256, 512])
def test_every_icon_size_exists(size):
    from mishkah.core import resources

    assert (resources.ICONS_DIR / f"app-{size}.png").exists()

def test_single_identity():
    """Source, configuration and documentation share one identity."""
    forbidden = ("muf" + "akkira", "MUF" + "AKKIRA", "Muf" + "akkira",
                 "notepad" + "-linux", "Notepad" + "-Linux", "org." + "notepadlinux")
    for path in _tracked_text_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        assert not any(word in text for word in forbidden), str(path)


def test_single_release():
    """All release metadata carries the literal application version."""
    import xml.etree.ElementTree as ET

    import mishkah

    assert mishkah.__version__ == "1.0.01"
    declarations = {
        "pyproject.toml": r'^version = "([^"]+)"',
        "src/mishkah/__init__.py": r'^__version__ = "([^"]+)"',
        "packaging/arch/PKGBUILD": r'^pkgver=(\S+)',
        "packaging/common/mishkah.1": r'"Mishkah Note ([^"]+)"',
        "packaging/windows/mishkah.wxs": r'<\?define Version="([^"]+)"',
        "packaging/rpm/mishkah-note.spec": r'version_override ([\d.]+)',
    }
    for relative, pattern in declarations.items():
        text = (REPO / relative).read_text()
        matches = re.findall(pattern, text, re.M)
        assert matches and all(v == "1.0.01" for v in matches), (relative, matches)
    tree = ET.parse(REPO / "packaging/common/org.mishkahnote.Mishkah.metainfo.xml")
    assert [r.attrib["version"] for r in tree.findall("releases/release")] == ["1.0.01"]
    spec = (REPO / "packaging/rpm/mishkah-note.spec").read_text().split("%changelog")[1]
    assert len(re.findall(r'^\* ', spec, re.M)) == 1
    assert "1.0.01" in spec
    for path in _tracked_text_files():
        try:
            text = path.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        for line in text.splitlines():
            if "PEP 440" in line:
                continue
            assert not re.search(r'(?<!\d)1\.0\.(?:0|1)(?!\d)', line), (str(path), line)
