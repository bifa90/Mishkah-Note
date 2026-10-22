#!/usr/bin/env bash
# Build the Arch package (.pkg.tar.zst) from packaging/arch/PKGBUILD.
#
#   scripts/build-arch.sh                 → dist/mishkah-note-<version>-1-any.pkg.tar.zst
#   VERSION=1.0.01 scripts/build-arch.sh
#
# Needs `makepkg` (base-devel) on an Arch host.  On Debian/Ubuntu run it inside
# the official image instead:
#
#   docker run --rm -v "$PWD:/src" -w /src archlinux:latest \
#       bash -c 'pacman -Syu --noconfirm base-devel python python-pyside6 \
#                python-charset-normalizer python-build python-installer \
#                python-wheel git && useradd -m b && chown -R b /src && \
#                su b -c "scripts/build-arch.sh"'
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! command -v makepkg >/dev/null 2>&1; then
    echo "makepkg not found — this needs an Arch host (or the archlinux image)." >&2
    echo "The PKGBUILD is still valid: packaging/arch/PKGBUILD" >&2
    exit 2
fi

OUT="${OUT:-$ROOT/dist}"
mkdir -p "$OUT"

VERSION="$(python3 - <<'EOF'
import pathlib, re
print(re.search(r'^version = "([^"]+)"', pathlib.Path("pyproject.toml").read_text(), re.M).group(1))
EOF
)"
# Use the exact checkout that CI is building, not a potentially different tag.
ARCHIVE="$ROOT/packaging/arch/mishkah-note-$VERSION.tar.gz"
mkdir -p "$(dirname "$ARCHIVE")"
git archive --format=tar.gz --prefix="Mishkah-Note-$VERSION/" -o "$ARCHIVE" HEAD
export MISHKAH_SOURCE_ARCHIVE="$ARCHIVE"

echo "==> makepkg in packaging/arch"
( cd packaging/arch && makepkg -f --noconfirm --nodeps )

find packaging/arch -maxdepth 1 -name '*.pkg.tar.*' -exec mv -v {} "$OUT/" \;
echo "==> done — artifacts in $OUT"
