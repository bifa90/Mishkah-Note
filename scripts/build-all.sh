#!/usr/bin/env bash
# Build every artefact this machine is able to produce.
#
#   scripts/build-all.sh                     → sdist + wheel + .deb (+ rpm/arch if installed)
#   WITH_APPIMAGE=1 scripts/build-all.sh     → … plus the AppImage
#   WITH_FLATPAK=1 scripts/build-all.sh      → … plus the Flatpak bundle
#
# RPM, Arch, AppImage, Flatpak and MSI need tooling that is not installed
# everywhere; each is skipped with an explicit message instead of failing the
# run.  Use scripts/verify-packaging.sh to check the results.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

say() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }

PYTHON="${PYTHON:-python3}"

say "cleaning"
rm -rf build/*.whl build/*.tar.gz
mkdir -p dist

say "python sdist + wheel"
"$PYTHON" -m build

say "debian package"
bash scripts/build-deb.sh

if command -v rpmbuild >/dev/null 2>&1; then
    say "rpm package"
    bash scripts/build-rpm.sh
else
    say "rpmbuild not found — skipping RPM (spec: packaging/rpm/mishkah-note.spec)"
fi

if command -v makepkg >/dev/null 2>&1; then
    say "arch package"
    bash scripts/build-arch.sh
else
    say "makepkg not found — skipping Arch package (PKGBUILD: packaging/arch/PKGBUILD)"
fi

if [ "${WITH_APPIMAGE:-0}" = "1" ]; then
    say "appimage"
    bash packaging/appimage/build-appimage.sh
else
    say "AppImage skipped (set WITH_APPIMAGE=1 to build it)"
fi

if [ "${WITH_FLATPAK:-0}" = "1" ]; then
    if command -v flatpak-builder >/dev/null 2>&1; then
        say "flatpak"
        flatpak-builder --user --force-clean --install-deps-from=flathub \
            --repo=build/flatpak-repo --default-branch=stable build/flatpak-build \
            packaging/flatpak/org.mishkahnote.Mishkah.json
        flatpak build-bundle build/flatpak-repo \
            "dist/org.mishkahnote.Mishkah.flatpak" \
            org.mishkahnote.Mishkah stable
    else
        say "flatpak-builder not found — skipping Flatpak"
    fi
else
    say "Flatpak skipped (set WITH_FLATPAK=1 to build it)"
fi

if command -v pwsh >/dev/null 2>&1 && command -v wix >/dev/null 2>&1; then
    say "windows MSI"
    pwsh scripts/build-msi.ps1
else
    say "MSI needs Windows + WiX — built by the release workflow on windows-latest"
fi

say "done — artifacts in $ROOT/dist"
ls -lh dist
