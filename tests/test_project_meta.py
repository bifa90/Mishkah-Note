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
            if "github.com" in line or "githubusercontent.com" in line or "bifa90/Mishkah-Note" in line:
                # A repository (or raw-content) URL names the project, not the
                # person; only the About box may carry the developer's name.
                continue
            for marker in AUTHOR_MARKERS:
                if marker in line:
                    offenders.append(f"{path.relative_to(REPO)}:{number}: {line.strip()}")
    offenders = [line for line in offenders if "egg-info" not in line]
    assert offenders == [], offenders


def _require_qt():
    """Skip where Qt cannot load (a checkout without libGL)."""
    try:
        from PySide6.QtWidgets import QApplication  # noqa: F401
    except Exception as exc:  # pragma: no cover - depends on the host
        pytest.skip(f"Qt GUI libraries unavailable: {exc}")


def test_about_dialog_credits_author_and_general_ai_assistance():
    # The About text lives in a Qt module; skip where Qt cannot load.
    _require_qt()
    from mishkah.core.i18n import tr
    from mishkah.widgets.about_dialog import AUTHOR, about_html

    assert "بلال" in AUTHOR
    html = about_html()
    # the name is wrapped in bidi isolates, so compare the two halves
    assert "بلال فضل" in html
    assert "Bilal Fadl" in html
    assert tr("about.assistants") in html
    # individual model and platform names no longer appear in the About box
    lowered = html.lower()
    for forbidden in ("deepseek", "claude", "gpt-5", "gemini", "arena", "agent mode"):
        assert forbidden not in lowered, forbidden


def test_about_source_has_no_individual_model_list():
    """The About box credits AI in general rather than naming specific models."""
    from mishkah.core.i18n_data import STRINGS
    from mishkah.core.languages import all_languages

    source = (REPO / "src/mishkah/widgets/about_dialog.py").read_text(encoding="utf-8")
    for forbidden in ("DeepSeek", "Claude", "GPT-5", "Gemini", "AI_ASSISTANTS"):
        assert forbidden not in source, forbidden
    table = STRINGS["about.assistants"]
    for lang in all_languages():
        assert table.get(lang.code, "").strip(), lang.code


def test_stylesheets_define_compact_menu_rules_for_tall_scripts():
    """Both themes define per-language menu density rules and the Home recent card."""
    for name in ("light.qss", "dark.qss"):
        qss = (REPO / "src/mishkah/resources/styles" / name).read_text(encoding="utf-8")
        for density in ("tight", "snug", "compact"):
            assert f'QMenu[menuDensity="{density}"]::item' in qss, (name, density)
            assert f'QMenu[menuDensity="{density}"]::separator' in qss, (name, density)
        assert "QFrame#HomeRecentPane" in qss, name


def test_about_dialog_has_no_rtl_explanation():
    """The direction essay was removed from the About box on request."""
    _require_qt()
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
    assert 'mishkah = "mishkah.cli:main"' in pyproject
    assert "resources/icons/*.png" in pyproject
    assert "resources/fonts/*.ttf" in pyproject
    assert "resources/styles/*.qss" in pyproject
    assert "resources/branding/*" in pyproject


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
    """One declaration, and every derived place agrees with it."""
    import subprocess
    import sys
    import xml.etree.ElementTree as ET

    import mishkah

    text = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    version = re.search(r'^version = "([^"]+)"', text, re.M).group(1)
    assert mishkah.__version__ == version

    tree = ET.parse(REPO / "packaging/common/org.mishkahnote.Mishkah.metainfo.xml")
    assert [r.attrib["version"] for r in tree.findall("releases/release")][0] == version

    gate = subprocess.run([sys.executable, "tools/check_version.py"],
                          cwd=REPO, capture_output=True, text=True)
    assert gate.returncode == 0, gate.stderr


def test_version_gate_catches_a_stale_number():
    """The gate must fail when a derived place keeps the previous release."""
    import subprocess
    import sys

    script = (
        "import sys; sys.path.insert(0, 'tools'); import check_version as c; "
        "bad = c.check(c.project_version() + '9'); "
        "print(len(bad)); raise SystemExit(0 if bad else 1)"
    )
    result = subprocess.run([sys.executable, "-c", script], cwd=REPO,
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr



def test_every_screenshot_the_readme_shows_is_in_the_repository():
    """A dead image link is a broken front page, and nothing else notices."""
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    targets = re.findall(r"\]\((docs/screenshots/[^)\s]+\.png)\)", readme)
    assert targets, "the README lost its screenshots"
    missing = [name for name in targets if not (REPO / name).is_file()]
    assert not missing, f"README points at missing files: {missing}"


def test_the_screenshot_generator_can_rebuild_the_welcome_page():
    """Round 4 adds the page that shows the brand rule; keep it regenerable."""
    tool = (REPO / "tools/make_screenshots.py").read_text(encoding="utf-8")
    for name in ("home-arabic.png", "home-urdu.png"):
        assert name in tool, f"{name} is in the README but not reproducible"
    assert '"--only"' in tool or "'--only'" in tool


def test_the_clean_exit_hook_never_pumps_qt_events():
    """CI's one SIGSEGV (exit 139) came from pumping events at exit.

    PySide6 6.12 can abort while CPython finalises, so conftest exits with
    ``os._exit`` when ``MISHKAH_CLEAN_EXIT=1``.  Pumping the Qt event loop first
    woke widgets that were already closed, which is exactly how a clean exit
    became a 139.  Nothing waits on those events: the process is going away.
    """
    hook = (REPO / "tests" / "conftest.py").read_text(encoding="utf-8")
    hook = hook.split("def pytest_sessionfinish")[1]
    assert "processEvents" not in hook
    assert "os._exit" in hook
    assert "MISHKAH_CLEAN_EXIT" in hook
