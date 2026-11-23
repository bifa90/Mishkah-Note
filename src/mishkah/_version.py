"""Single source of truth for the application version.

``pyproject.toml`` owns the number; this module only *reads* it.  When the
package is installed the distribution metadata is authoritative; when the code
runs from a source checkout (developers, packaging scripts, CI before install)
the neighbouring ``pyproject.toml`` is read instead.  That ordering matters: an
installed 1.0.01 must never mask an uncommitted 1.0.02 working tree.

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


def _from_metadata() -> Optional[str]:
    """Version of the installed distribution, if the package was installed."""
    try:
        return metadata.version(DISTRIBUTION)
    except metadata.PackageNotFoundError:  # pragma: no cover - installed wheels
        return None


__version__: str = _from_pyproject() or _from_metadata() or "0.0.0+unknown"
