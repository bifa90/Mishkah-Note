#!/usr/bin/env python3
"""Move the whole project to a new version in one atomic, verifiable step.

The version lives in ``pyproject.toml`` only.  Everything else is *derived*:
packaging files, workflow env blocks and the documentation that names the
release.  Editing those by hand is how ``1.0.0x`` strings survive a bump, so
this tool does all of them and then runs the gate.

Usage::

    python3 tools/bump_version.py 1.0.02 --dry-run   # show what would change
    python3 tools/bump_version.py 1.0.02             # apply, then verify

Two files are treated specially and never blind-replaced:

* the AppStream metainfo keeps *history*: a new ``<release>`` is prepended;
* the RPM spec keeps *history*: a new ``%changelog`` entry is prepended.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
import sys
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

import check_version  # noqa: E402  (local tool, path set above)

METAINFO = Path("packaging/common/org.mishkahnote.Mishkah.metainfo.xml")
SPEC = Path("packaging/rpm/mishkah-note.spec")
MIRRORS = {
    Path(".github/workflows/release.yml"): Path("docs/ci/release.yml"),
    Path(".github/workflows/installers.yml"): Path("docs/ci/installers.yml"),
    Path(".github/workflows/ci.yml"): Path("docs/ci/ci.yml"),
}
SKIP_PREFIXES = ("tests/", "build/", "dist/", ".venv/")


def tracked_text_files() -> List[Path]:
    try:
        out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT,
                             capture_output=True, check=True).stdout
        names = [n for n in out.decode("utf-8", "replace").split("\0") if n]
    except (OSError, subprocess.SubprocessError):  # pragma: no cover
        names = [p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*") if p.is_file()]
    return [ROOT / name for name in names if (ROOT / name).is_file()]


def replace_static(old: str, new: str, dry_run: bool) -> List[str]:
    """Rewrite every tracked text file that still names *old*, except history."""
    changed: List[str] = []
    special = {METAINFO.as_posix(), SPEC.as_posix()}
    for path in tracked_text_files():
        relative = path.relative_to(ROOT).as_posix()
        if relative in check_version.FROZEN or relative in special:
            continue
        if relative.startswith(SKIP_PREFIXES):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if old not in text:
            continue
        changed.append(relative)
        if not dry_run:
            path.write_text(text.replace(old, new), encoding="utf-8")
    return changed


def add_metainfo_release(old: str, new: str, date: str, dry_run: bool) -> bool:
    text = (ROOT / METAINFO).read_text(encoding="utf-8")
    if f'version="{new}"' in text:
        return False
    entry = (
        f'    <release version="{new}" date="{date}">\n'
        f"      <description>\n"
        f"        <p>Correctness and data-safety release.</p>\n"
        f'        <p xml:lang="ar">إصدار تصحيحات وسلامة بيانات.</p>\n'
        f"      </description>\n"
        f"    </release>\n"
    )
    assert "  <releases>\n" in text
    updated = text.replace("  <releases>\n", "  <releases>\n" + entry, 1)
    if not dry_run:
        (ROOT / METAINFO).write_text(updated, encoding="utf-8")
    return True


def add_spec_changelog(new: str, dry_run: bool) -> bool:
    text = (ROOT / SPEC).read_text(encoding="utf-8")
    head, _, changelog = text.partition("%changelog\n")
    stamp = dt.date.today().strftime("%a %b %d %Y")
    if f"- {new}-1" in changelog.splitlines()[0] if changelog.splitlines() else False:
        return False
    entry = (
        f"* {stamp} Mishkah-Note contributors <noreply@github.com> - {new}-1\n"
        f"- Mishkah Note {new}.\n"
    )
    if not dry_run:
        (ROOT / SPEC).write_text(head + "%changelog\n" + entry + changelog, encoding="utf-8")
    return True


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bump every derived version.")
    parser.add_argument("version", help="new version, e.g. 1.0.02")
    parser.add_argument("--date", default=dt.date.today().isoformat(), help="release date")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if not re.fullmatch(r"\d+\.\d+\.\d+", args.version):
        print("version must look like 1.0.02 (three numeric parts)", file=sys.stderr)
        return 2

    old = check_version.project_version()
    if old == args.version:
        print(f"already at {old}; nothing to do")
        return 0

    changed = replace_static(old, args.version, args.dry_run)
    meta = add_metainfo_release(old, args.version, args.date, args.dry_run)
    spec = add_spec_changelog(args.version, args.dry_run)

    for live, mirror in MIRRORS.items():
        if not (ROOT / live).exists() or not (ROOT / mirror).exists():
            continue
        if not args.dry_run:
            (ROOT / mirror).write_text((ROOT / live).read_text(encoding="utf-8"),
                                       encoding="utf-8")

    print(f"{old} -> {args.version}{' (dry run)' if args.dry_run else ''}")
    for relative in changed:
        print(f"  rewrote {relative}")
    print(f"  metainfo release entry: {'added' if meta else 'already present'}")
    print(f"  spec changelog: {'prepended' if spec else 'already present'}")

    if args.dry_run:
        return 0
    problems = check_version.check(args.version)
    if problems:
        print("\npost-bump check failed:", file=sys.stderr)
        for where, problem in problems:
            print(f"  - {where}: {problem}", file=sys.stderr)
        return 1
    print("\npost-bump check: every derived place agrees")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
