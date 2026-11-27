"""Native installers must include resources and fail on unsuccessful tooling."""
from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_windows_resources_do_not_require_an_installed_source_package():
    text = (ROOT / "packaging/windows/mishkah.spec").read_text()
    ast.parse(text)
    assert 'datas = [(str(SRC / "mishkah" / "resources"), "mishkah/resources")]' in text
    assert "collect_data_files" not in text


def test_native_windows_failures_are_not_ignored():
    text = (ROOT / "scripts/build-msi.ps1").read_text()
    for stage in ("PyInstaller", "MSI compilation", "WiX UI extension", "Python dependencies"):
        assert f'Assert-NativeExit "{stage}"' in text


def test_build_reporter_exposes_the_final_error_first(tmp_path, monkeypatch, capsys):
    spec = importlib.util.spec_from_file_location("reporter", ROOT / "tools/report_build_failure.py")
    reporter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reporter)
    log = tmp_path / "native.log"
    log.write_text(("verbose output " * 60 + "\n") * 100 + "FINAL BUILD ERROR\n")
    monkeypatch.setattr(reporter.sys, "argv", ["reporter", str(log)])
    assert reporter.main() == 0
    annotations = capsys.readouterr().out.splitlines()
    assert "FINAL BUILD ERROR" in annotations[0]
    assert all(line.startswith("::error::") and len(line) < 4096 for line in annotations)


def test_msi_harvested_files_belong_to_a_feature():
    from xml.etree import ElementTree as ET

    root = ET.parse(ROOT / "packaging/windows/mishkah.wxs").getroot()
    ns = {"w": "http://wixtoolset.org/schemas/v4/wxs"}
    group = root.find("w:Fragment/w:ComponentGroup[@Id='ApplicationFiles']", ns)
    assert group is not None
    assert group.attrib["Directory"] == "INSTALLFOLDER"
    assert group.find("w:Files", ns) is not None
    assert root.find("w:Package/w:Feature/w:ComponentGroupRef[@Id='ApplicationFiles']", ns) is not None
    assert not root.findall(".//w:Directory/w:Files", ns)


def test_flatpak_native_debug_tools_are_installed():
    for name in ("installers.yml", "release.yml"):
        for folder in (".github/workflows", "docs/ci"):
            text = (ROOT / folder / name).read_text()
            assert "flatpak flatpak-builder elfutils librsvg2-common" in text
            assert "--print-report=full --hints-dir=" in text


def test_the_installer_checks_both_bundled_typefaces():
    """Round 4 bundles Noto Sans Arabic for the Urdu chrome.

    The Windows installers already refused to pass without the Arabic face; a
    second bundled font without the same check could vanish from a payload and
    leave the Urdu menus on whatever the system happens to have.
    """
    for folder in (".github/workflows", "docs/ci"):
        for name in ("installers.yml", "release.yml"):
            text = (ROOT / folder / name).read_text(encoding="utf-8")
            for font in ("IBMPlexSansArabic-Regular.ttf", "NotoSansArabic-Regular.ttf"):
                assert f"-Filter {font}" in text, f"{folder}/{name} does not check {font}"


def test_deb_declares_qtnetwork_and_does_not_bypass_pyside6_with_pip():
    text = (ROOT / "scripts/build-deb.sh").read_text(encoding="utf-8")
    depends_line = next(line for line in text.splitlines() if line.startswith("Depends:"))
    assert "python3-pyside6.qtwidgets" in depends_line
    assert "python3-pyside6.qtnetwork" in depends_line
    assert "python3-charset-normalizer" in depends_line
    assert "python3-pip" not in depends_line


def test_windows_spec_bundles_qtnetwork_for_single_instance():
    text = (ROOT / "packaging/windows/mishkah.spec").read_text(encoding="utf-8")
    for mod in ("PySide6.QtNetwork", "PySide6.QtSvg", "PySide6.QtPrintSupport"):
        assert f'"{mod}"' in text, f"mishkah.spec missing hiddenimport {mod}"


def test_appimage_isolates_user_site_packages():
    text = (ROOT / "packaging/appimage/build-appimage.sh").read_text(encoding="utf-8")
    assert "export PYTHONNOUSERSITE=1" in text


def test_appimage_and_flatpak_use_pyside6_essentials_and_prune_unused_qt():
    """Avoid bundling QtWebEngine/QtPdf/QtAddons into Linux portable packages."""
    appimage = (ROOT / "packaging/appimage/build-appimage.sh").read_text(encoding="utf-8")
    flatpak = (ROOT / "packaging/flatpak/org.mishkahnote.Mishkah.json").read_text(encoding="utf-8")
    prune = (ROOT / "packaging/common/prune-pyside6.sh").read_text(encoding="utf-8")

    assert '"PySide6-Essentials>=6.5,<7"' in appimage
    assert '"PySide6>=6.5,<7"' not in appimage
    assert "prune-pyside6.sh" in appimage

    assert 'PySide6-Essentials>=6.5,<7' in flatpak
    assert 'PySide6>=6.5,<7' not in flatpak
    assert "prune-pyside6.sh" in flatpak

    assert "Qt/qml" in prune
    assert "libQt6Qml" in prune
