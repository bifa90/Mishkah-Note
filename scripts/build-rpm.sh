#!/usr/bin/env bash
# Build the RPM package (Fedora / RHEL / openSUSE) without polluting ~/rpmbuild.
#
#   scripts/build-rpm.sh                 → dist/notepad-linux-<version>-1.*.noarch.rpm
#   VERSION=2.0.0 scripts/build-rpm.sh
#
# Needs rpmbuild (`dnf install rpm-build` / `apt install rpm`).  The spec builds
# from a source tarball created here with `git archive`, so no network access
# is required and the result is reproducible from the current checkout.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! command -v rpmbuild >/dev/null 2>&1; then
    echo "rpmbuild not found — install rpm-build (dnf) or rpm (apt) first." >&2
    echo "The spec is still valid: packaging/rpm/notepad-linux.spec" >&2
    exit 2
fi

VERSION="${VERSION:-$(python3 - <<'EOF'
import pathlib, re
print(re.search(r'^version = "([^"]+)"',
      pathlib.Path("pyproject.toml").read_text(encoding="utf-8"), re.M).group(1))
EOF
)}"
TOP="$ROOT/build/rpm"
OUT="${OUT:-$ROOT/dist}"
NAME="Notepad-Linux-$VERSION"

rm -rf "$TOP"
mkdir -p "$TOP"/{SOURCES,SPECS,BUILD,RPMS,SRPMS} "$OUT"

echo "==> staging source tarball $NAME"
git archive --format=tar.gz --prefix="$NAME/" -o "$TOP/SOURCES/$NAME.tar.gz" HEAD

cp packaging/rpm/notepad-linux.spec "$TOP/SPECS/"

echo "==> rpmbuild"
rpmbuild -ba \
    --define "_topdir $TOP" \
    --define "version_override $VERSION" \
    "$TOP/SPECS/notepad-linux.spec"

find "$TOP/RPMS" -name '*.rpm' -exec cp -v {} "$OUT/" \;
echo "==> done — artifacts in $OUT"
