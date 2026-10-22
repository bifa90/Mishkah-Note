"""Release publishing requires all formats, with no empty or ambiguous files."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("release_assets", REPO / "tools/check_release_assets.py")
assets = importlib.util.module_from_spec(spec)
spec.loader.exec_module(assets)


@pytest.fixture()
def bundle(tmp_path):
    for pattern in assets.expected_patterns("1.0.01").values():
        (tmp_path / pattern.replace("*", "1")).write_bytes(b"package")
    return tmp_path


def test_complete_bundle(bundle):
    assert assets.validate(bundle, "1.0.01") == []


@pytest.mark.parametrize("kind", list(assets.expected_patterns("1.0.01")))
def test_missing_format_blocks_publication(bundle, kind):
    pattern = assets.expected_patterns("1.0.01")[kind]
    next(bundle.glob(pattern)).unlink()
    assert any(e.startswith(kind + ":") for e in assets.validate(bundle, "1.0.01"))


def test_empty_package_blocks_publication(bundle):
    (bundle / "org.mishkahnote.Mishkah.flatpak").write_bytes(b"")
    assert assets.validate(bundle, "1.0.01")


def test_unexpected_entry_blocks_publication(bundle):
    (bundle / "screenshot.png").write_bytes(b"image")
    assert assets.validate(bundle, "1.0.01")


def test_ambiguous_wheel_blocks_publication(bundle):
    pattern = assets.expected_patterns("1.0.01")["wheel"]
    (bundle / pattern.replace("*", "2")).write_bytes(b"duplicate")
    assert assets.validate(bundle, "1.0.01")


def test_symlink_is_not_an_artifact(bundle):
    target = bundle / "org.mishkahnote.Mishkah.flatpak"
    target.unlink()
    target.symlink_to(next(bundle.glob("*.whl")))
    assert assets.validate(bundle, "1.0.01")
