#!/usr/bin/env python3
"""Verify that every place naming a release version agrees with pyproject.toml.

The version lives in exactly one file (``pyproject.toml``); everything else is
derived.  This script is the gate that refuses a release when a derived place
was forgotten, which used to be the way 1.0.0x strings survived a bump.

Usage::

    python3 tools/check_version.py            # human readable report
    python3 tools/check_version.py --quiet    # exit code only (CI)

Exit code 0 means "all derived places agree"; 1 lists every disagreement.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List, Tuple

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"

#: Frozen historical records: they keep the version they were written against.
FROZEN = {
    "CHANGELOG.md",
    "docs/ANALYSIS_1.0.02.ar.md",
    "docs/ANSWERS_1.0.02.ar.md",
    "docs/CONFLICT_AUDIT_1.0.02.ar.md",
    "docs/DECISIONS_1.0.02.ar.md",
    "docs/PLAN_1.0.02.ar.md",
    "docs/W0_REPORT_1.0.02.ar.md",
    "docs/decisions-1.0.02.html",
}

#: A line may opt out of the scan when it names a *different* version on
#: purpose — prose about the rejected spelling of a version, for instance:
#:
#:     | ب) `1.0.2` | ... |   <!-- version-gate: allow -->
ALLOW_MARKER = "version-gate: allow"

#: ``1.0.02``, ``v1.0.02`` — three numeric components, not part of a longer word.
VERSION_TOKEN = re.compile(r"(?<![\w.])v?(\d+\.\d+\.\d+)(?![\w.])")

#: Third-party versions that legitimately look like ours and must not be flagged.
#: ``5.0.2`` is the WiX Toolset version pinned by scripts/build-msi.ps1;
#: ``3.11.18`` is the CPython that packaging/appimage/build-appimage.sh bundles.
THIRD_PARTY_VERSIONS = {"5.0.2", "3.11.18"}

#: Files that *keep history*: an older release entry there is correct, so they
#: are checked by their own rule above instead of by the line-by-line scan
#: (which would flag the previous release for ever).
HISTORY_FILES = {
    "packaging/common/org.mishkahnote.Mishkah.metainfo.xml",
    "packaging/rpm/mishkah-note.spec",
}

#: ``relative path -> regex with one capture group`` for static packaging files.
DECLARATIONS = {
    "src/mishkah/_version.txt": r"^(\S+)$",
    "packaging/arch/PKGBUILD": r"^pkgver=(\S+)",
    "packaging/common/mishkah.1": r'"Mishkah Note ([^"]+)"',
    "packaging/windows/mishkah.wxs": r'define Version="([^"]+)"',
    "packaging/rpm/mishkah-note.spec": r"version_override\s+([\d.]+)",
}

METAINFO = "packaging/common/org.mishkahnote.Mishkah.metainfo.xml"
WORKFLOWS = (".github/workflows/release.yml", ".github/workflows/installers.yml")
MIRRORS = {
    ".github/workflows/release.yml": "docs/ci/release.yml",
    ".github/workflows/installers.yml": "docs/ci/installers.yml",
    ".github/workflows/ci.yml": "docs/ci/ci.yml",
}


def project_version() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not match:
        raise SystemExit("pyproject.toml has no static version line")
    return match.group(1)


def code_version() -> str:
    sys.path.insert(0, str(SRC))
    import mishkah  # noqa: PLC0415 - imported after sys.path tweak by design

    return mishkah.__version__


def tracked_text_files() -> Iterable[Path]:
    """Tracked files (or a directory walk when git is unavailable)."""
    try:
        out = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=ROOT, capture_output=True, check=True,
        ).stdout
        names = [n for n in out.decode("utf-8", "replace").split("\0") if n]
    except (OSError, subprocess.SubprocessError):  # pragma: no cover - no git
        skip = {".git", ".venv", "build", "dist", "__pycache__", "node_modules"}
        names = [
            p.relative_to(ROOT).as_posix()
            for p in ROOT.rglob("*")
            if p.is_file() and not skip & set(p.parts)
        ]
    for name in names:
        path = ROOT / name
        if path.is_file():
            yield path


def _comment_only(line: str) -> bool:
    head = line.strip()
    return head.startswith(("#", "//", "<!--", "*", ";"))


def check(
    version: str,
    declarations: dict = DECLARATIONS,
    frozen: set = FROZEN,
) -> List[Tuple[str, str]]:
    """Return ``(where, problem)`` pairs; empty means everything agrees."""
    problems: List[Tuple[str, str]] = []

    if code_version() != version:
        problems.append(
            ("src/mishkah", f"mishkah.__version__ = {code_version()} but pyproject says {version}")
        )

    for relative, pattern in declarations.items():
        text = (ROOT / relative).read_text(encoding="utf-8")
        found = re.findall(pattern, text, re.MULTILINE)
        if not found:
            problems.append((relative, f"no version found with /{pattern}/"))
            continue
        for value in found:
            if value != version:
                problems.append((relative, f"{value} != {version}"))

    metainfo = (ROOT / METAINFO).read_text(encoding="utf-8")
    releases = re.findall(r'<release\s+version="([^"]+)"', metainfo)
    if not releases:
        problems.append((METAINFO, "no <release> entries"))
    elif releases[0] != version:
        problems.append((METAINFO, f"newest release is {releases[0]}, expected {version}"))

    tag = f"v{version}"
    for relative in WORKFLOWS:
        text = (ROOT / relative).read_text(encoding="utf-8")
        env = re.search(r'^\s*RELEASE_VERSION:\s*"([^"]+)"', text, re.MULTILINE)
        if not env:
            problems.append((relative, "missing env RELEASE_VERSION"))
        elif env.group(1) != version:
            problems.append((relative, f"RELEASE_VERSION = {env.group(1)} != {version}"))
        tag_env = re.search(r'^\s*RELEASE_TAG:\s*"([^"]+)"', text, re.MULTILINE)
        if tag_env and tag_env.group(1) != tag:
            problems.append((relative, f"RELEASE_TAG = {tag_env.group(1)} != {tag}"))
        if tag_env is None and relative.endswith("release.yml"):
            problems.append((relative, "missing env RELEASE_TAG"))

    release = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    trigger = re.search(r"tags:\s*\[\"([^\"]+)\"\]", release)
    if not trigger:
        problems.append((".github/workflows/release.yml", "no tag trigger"))
    elif trigger.group(1) != tag:
        problems.append((".github/workflows/release.yml", f"tag trigger {trigger.group(1)} != {tag}"))
    sample = re.search(r'default:\s*"(v[^"]+)"', release)
    if not sample:
        problems.append((".github/workflows/release.yml", "no workflow_dispatch default"))
    elif sample.group(1) != tag:
        problems.append((".github/workflows/release.yml", f"dispatch default {sample.group(1)} != {tag}"))

    for live, mirror in MIRRORS.items():
        if not (ROOT / mirror).exists():
            continue
        if (ROOT / live).read_text(encoding="utf-8") != (ROOT / mirror).read_text(encoding="utf-8"):
            problems.append((mirror, f"differs from {live}"))

    for path in tracked_text_files():
        relative = path.relative_to(ROOT).as_posix()
        if relative in frozen or relative in HISTORY_FILES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for number, line in enumerate(text.splitlines(), 1):
            if _comment_only(line) or ALLOW_MARKER in line:
                continue
            for match in VERSION_TOKEN.finditer(line):
                found_version = match.group(1)
                if found_version in THIRD_PARTY_VERSIONS:
                    continue
                if found_version != version:
                    problems.append((relative, f"line {number}: {found_version} (expected {version})"))
    return problems


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__ or "")
    parser.add_argument("--quiet", action="store_true", help="print nothing when clean")
    args = parser.parse_args(argv)

    version = project_version()
    problems = check(version)
    if not problems:
        if not args.quiet:
            print(f"version {version}: every derived place agrees")
        return 0
    print(f"version {version}: {len(problems)} disagreement(s)", file=sys.stderr)
    for where, problem in problems:
        print(f"  - {where}: {problem}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
