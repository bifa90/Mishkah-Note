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
