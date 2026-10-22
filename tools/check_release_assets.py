#!/usr/bin/env python3
"""Reject incomplete or ambiguous release bundles before publishing."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def expected_patterns(version: str) -> dict[str, str]:
    # PEP 440 normalizes numeric version components in Python artifact names.
    normalized = ".".join(str(int(part)) for part in version.split("."))
    return {
        "wheel": f"mishkah_note-{normalized}-*.whl",
        "sdist": f"mishkah_note-{normalized}.tar.gz",
        "deb": f"mishkah-note_{version}_all.deb",
        "rpm": f"mishkah-note-{version}-*.noarch.rpm",
        "arch": f"mishkah-note-{version}-*-any.pkg.tar.zst",
        "AppImage": f"Mishkah_Note-{version}-x86_64.AppImage",
        "Flatpak": "org.mishkahnote.Mishkah.flatpak",
        "MSI": f"Mishkah_Note_{version}_x64.msi",
    }


def validate(directory: Path, version: str) -> list[str]:
    errors = []
    accepted: set[Path] = set()
    for kind, pattern in expected_patterns(version).items():
        matches = list(directory.glob(pattern))
        if len(matches) != 1:
            errors.append(f"{kind}: expected one {pattern}, found {len(matches)}")
            continue
        path = matches[0]
        if path.is_symlink() or not path.is_file() or path.stat().st_size == 0:
            errors.append(f"{kind}: not a nonempty regular file: {path.name}")
        accepted.add(path)
    for path in directory.iterdir():
        if path not in accepted:
            errors.append(f"Unexpected release entry: {path.name}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    version = re.search(r'^version = "([^"]+)"',
                        (ROOT / "pyproject.toml").read_text(), re.M).group(1)
    if not args.directory.is_dir():
        parser.error("artifact directory does not exist")
    errors = validate(args.directory, version)
    if errors:
        print("\n".join(errors))
        return 1
    print(f"All eight release packages for {version} are present and nonempty.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
