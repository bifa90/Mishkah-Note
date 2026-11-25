"""Single source of truth for the application version.

``pyproject.toml`` owns the number; this module only *reads* it.  The chain is:

1. the neighbouring ``pyproject.toml`` — a source checkout, where an uncommitted
   bump must win over whatever is installed in site-packages;
2. ``_version.txt`` next to this file — a staged tree (a .deb, an AppImage)
   that carries no metadata;
3. the installed distribution metadata — a wheel or a pip install;
4. ``"unknown"`` — never a plausible release number, so the gate notices.

Nothing else may hard-code a version.  ``tools/check_version.py`` enforces that
and ``tools/bump_version.py`` rewrites every derived place at once.
"""

from __future__ import annotations

import re
from importlib import metadata
from pathlib import Path
from typing import Optional

_VERSION_RE = re.compile(r'^version\s*=\s*"([^"]+)"', re.MULTILINE)

#: Distribution name declared in ``pyproject.toml``.
DISTRIBUTION = "mishkah-note"


def _from_pyproject() -> Optional[str]:
    """Version declared by the checkout that contains this file, if any."""
    candidate = Path(__file__).resolve().parents[2] / "pyproject.toml"
    try:
        text = candidate.read_text(encoding="utf-8")
    except OSError:
        return None
    match = _VERSION_RE.search(text)
    return match.group(1) if match else None


def _from_shipped_file() -> Optional[str]:
    """Version shipped beside the module, for trees without metadata."""
    try:
        return (Path(__file__).with_name("_version.txt")).read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def _from_metadata() -> Optional[str]:
    """Version of the installed distribution, if the package was installed."""
    try:
        return metadata.version(DISTRIBUTION)
    except metadata.PackageNotFoundError:  # pragma: no cover - installed wheels
        return None


__version__: str = _from_pyproject() or _from_shipped_file() or _from_metadata() or "unknown"
