"""Informational CLI flags work without importing Qt or opening a display."""

from __future__ import annotations

import subprocess
import sys

import pytest


@pytest.mark.parametrize("flag", ["--version", "--help", "-h"])
def test_metadata_flags_do_not_load_qt(flag):
    script = (
        "import sys; from mishkah.cli import main; "
        f"assert main(['mishkah', {flag!r}]) == 0; "
        "assert not any(n.startswith('PySide6') for n in sys.modules)"
    )
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert ("1.0.01" if flag == "--version" else "Usage:") in result.stdout


def test_python_module_version():
    result = subprocess.run([sys.executable, "-m", "mishkah", "--version"],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "1.0.01"
