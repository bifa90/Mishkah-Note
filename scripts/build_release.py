#!/usr/bin/env python3
"""Build Mishkah Note release packages with native, checked-in recipes.

This orchestrator does not emulate packaging tools or cross-compile MSI on Linux.
Run the relevant targets on their native platforms and collect their outputs.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGETS = ("python", "deb", "rpm", "arch", "appimage", "flatpak", "msi")
LINUX = ("python", "deb", "rpm", "arch", "appimage", "flatpak")


def version() -> str:
    return re.search(r'^version = "([^"]+)"', (ROOT / "pyproject.toml").read_text(), re.M)[1]


def commands(target: str, output: Path) -> list[list[str]]:
    recipes = {
        "python": [[sys.executable, "-m", "build", "--no-isolation", "--outdir", str(output)]],
        "deb": [["bash", "scripts/build-deb.sh"]],
        "rpm": [["bash", "scripts/build-rpm.sh"]],
        "arch": [["bash", "scripts/build-arch.sh"]],
        "appimage": [["bash", "packaging/appimage/build-appimage.sh"]],
        "flatpak": [
            ["flatpak-builder", "--user", "--force-clean", "--install-deps-from=flathub",
             "--repo=build/flatpak-repo", "--default-branch=stable", "build/flatpak-build",
             "packaging/flatpak/org.mishkahnote.Mishkah.json"],
            ["flatpak", "build-bundle", "build/flatpak-repo",
             str(output / "org.mishkahnote.Mishkah.flatpak"), "org.mishkahnote.Mishkah", "stable"],
        ],
        "msi": [[shutil.which("pwsh") or shutil.which("powershell") or "pwsh",
                 "-NoProfile", "-File", "scripts/build-msi.ps1", "-Version", version(),
                 "-OutputDirectory", str(output)]],
    }
    return recipes[target]


def missing_requirements(target: str) -> list[str]:
    missing = []
    host = platform.system()
    if target not in ("python", "msi") and host != "Linux":
        missing.append("requires Linux")
    if target == "msi" and host != "Windows":
        missing.append("requires Windows (MSI is not cross-compiled)")
    requirements = {
        "python": (), "deb": ("bash", "dpkg-deb"), "rpm": ("bash", "rpmbuild"),
        "arch": ("bash", "makepkg"),
        "appimage": ("bash", os.environ.get("APPIMAGETOOL", "appimagetool")),
        "flatpak": ("flatpak-builder", "flatpak"), "msi": ("dotnet",),
    }
    for tool in requirements[target]:
        if not shutil.which(tool):
            missing.append(f"missing executable: {tool}")
    if target == "msi" and not (shutil.which("pwsh") or shutil.which("powershell")):
        missing.append("missing PowerShell")
    if target == "python" and importlib.util.find_spec("build") is None:
        missing.append(f"install build tooling with: {sys.executable} -m pip install build setuptools wheel")
    return missing


def selected_targets(value: str) -> list[str]:
    if value == "all":
        return list(TARGETS)
    if value == "linux":
        return list(LINUX)
    result = list(dict.fromkeys(value.split(",")))
    if not result or any(t not in TARGETS for t in result):
        raise ValueError("Use all, linux, or comma-separated targets: " + ",".join(TARGETS))
    return result


def verify_bundle(directory: Path) -> int:
    result = subprocess.run([sys.executable, str(ROOT / "tools/check_release_assets.py"), str(directory)],
                            cwd=ROOT, check=False)
    if result.returncode:
        return result.returncode
    # Keep checksums outside the bundle so its eight-file validation is repeatable.
    lines = []
    for path in sorted(directory.iterdir()):
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1 << 20), b""):
                digest.update(chunk)
        lines.append(f"{digest.hexdigest()}  {path.name}")
    report = ROOT / "build/SHA256SUMS.txt"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(lines) + "\n")
    print(f"Complete bundle validated. Checksums: {report}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--formats", default="python", help="python,deb,rpm,arch,appimage,flatpak,msi; or linux/all")
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    parser.add_argument("--check", action="store_true", help="check prerequisites without building")
    parser.add_argument("--dry-run", action="store_true", help="print commands without executing")
    parser.add_argument("--keep-going", action="store_true", help="attempt all selected targets, still fail if any fail")
    parser.add_argument("--verify-bundle", type=Path, help="validate the collected eight packages, then write checksums")
    args = parser.parse_args()
    if args.verify_bundle:
        return verify_bundle(args.verify_bundle.resolve())
    try:
        targets = selected_targets(args.formats)
    except ValueError as exc:
        parser.error(str(exc))
    output = args.output.resolve()
    if args.dry_run:
        for target in targets:
            print(target + ": " + json.dumps(commands(target, output), ensure_ascii=False))
            for message in missing_requirements(target):
                print("  prerequisite: " + message)
        return 0
    issues = {t: missing_requirements(t) for t in targets}
    for target, messages in issues.items():
        print(f"{target}: " + ("; ".join(messages) if messages else "prerequisites available"))
    if args.check:
        return 2 if any(issues.values()) else 0
    if any(issues.values()) and not args.keep_going:
        print("No build started: fix prerequisites or select the appropriate platform targets.")
        return 2
    output.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, OUT=str(output))
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
    results = {}
    for target in targets:
        if issues[target]:
            results[target] = {"status": "unavailable", "detail": issues[target]}
            continue
        try:
            for command in commands(target, output):
                subprocess.run(command, cwd=ROOT, env=env, check=True)
            results[target] = {"status": "built"}
        except (OSError, subprocess.CalledProcessError) as exc:
            results[target] = {"status": "failed", "detail": str(exc)}
            if not args.keep_going:
                break
    for target in targets:
        results.setdefault(target, {"status": "not_attempted"})
    report = ROOT / "build/manual-release-report.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps({"version": version(), "platform": platform.platform(),
                                  "output": str(output), "results": results}, indent=2) + "\n")
    print(f"Build report: {report}")
    return 0 if all(item["status"] == "built" for item in results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
