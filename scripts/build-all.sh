#!/usr/bin/env bash
# Build every artifact that this machine is able to produce.
#
#   scripts/build-all.sh            → sdist + wheel + .deb
#   WITH_APPIMAGE=1 scripts/build-all.sh
#
# RPM, Arch and Flatpak need tooling that is not always installed; the script
# skips them with a clear message instead of failing.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

say() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }

say "cleaning"
rm -rf build/*.whl build/*.tar.gz
mkdir -p dist

say "python sdist + wheel"
python3 -m build

say "debian package"
bash scripts/build-deb.sh

if command -v rpmbuild >/dev/null 2>&1; then
    say "rpm package"
    rpmbuild -ba packaging/rpm/notepad-linux.spec --define "_topdir $ROOT/build/rpm"
else
    say "rpmbuild not found — skipping RPM (spec: packaging/rpm/notepad-linux.spec)"
fi

if command -v makepkg >/dev/null 2>&1; then
    say "arch package"
    ( cd packaging/arch && makepkg -f --noconfirm )
else
    say "makepkg not found — skipping Arch package (PKGBUILD: packaging/arch/PKGBUILD)"
fi

if [ "${WITH_APPIMAGE:-0}" = "1" ]; then
    say "appimage"
    bash packaging/appimage/build-appimage.sh
else
    say "AppImage skipped (set WITH_APPIMAGE=1 to build it)"
fi

say "done — artifacts in $ROOT/dist"
ls -lh dist
