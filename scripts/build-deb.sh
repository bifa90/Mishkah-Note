#!/usr/bin/env bash
# Build a Debian package for Notepad-Linux using dpkg-deb alone (no debhelper,
# no fakeroot, no root):
#
#   scripts/build-deb.sh                 → dist/notepad-linux_<version>_all.deb
#   VERSION=2.0.0 scripts/build-deb.sh   → override the version
#
# The package is architecture-independent: the Python sources live in
# /usr/lib/notepad-linux, /usr/bin/notepad is a two-line launcher, and the
# system interpreter (python3 + python3-pyside6) does the rest.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

VERSION="${VERSION:-$(python3 - <<'EOF'
import pathlib, re
text = pathlib.Path("pyproject.toml").read_text(encoding="utf-8")
print(re.search(r'^version = "([^"]+)"', text, re.M).group(1))
EOF
)}"
PKG=notepad-linux
ARCH=all
STAGE="$ROOT/build/deb/${PKG}_${VERSION}_${ARCH}"
OUT="${OUT:-$ROOT/dist}"
LIBDIR=/usr/lib/notepad-linux
APPDIR=/usr/share/applications
ICONDIR=/usr/share/icons/hicolor
MANDIR=/usr/share/man/man1
METAINFO=/usr/share/metainfo

rm -rf "$STAGE"
mkdir -p "$STAGE/DEBIAN" \
         "$STAGE$LIBDIR" \
         "$STAGE/usr/bin" \
         "$STAGE$APPDIR" \
         "$STAGE$MANDIR" \
         "$STAGE$METAINFO" \
         "$STAGE/usr/share/doc/$PKG"
mkdir -p "$OUT"

echo "==> staging $PKG $VERSION ($ARCH)"

# ---------------------------------------------------------------- payload ---
cp -r src/mufakkira "$STAGE$LIBDIR/"
find "$STAGE$LIBDIR" -name '__pycache__' -type d -prune -exec rm -rf {} +
find "$STAGE$LIBDIR" -name '*.pyc' -delete
find "$STAGE$LIBDIR" -name '*.pyo' -delete

for size in 16 24 32 48 64 128 256 512; do
    install -Dm644 "src/mufakkira/resources/icons/app-${size}.png" \
        "$STAGE$ICONDIR/${size}x${size}/apps/${PKG}.png"
done
install -Dm644 src/mufakkira/resources/icons/app.svg \
    "$STAGE$ICONDIR/scalable/apps/${PKG}.svg"

install -Dm644 packaging/common/notepad.desktop \
    "$STAGE$APPDIR/${PKG}.desktop"
install -Dm644 packaging/common/org.notepadlinux.Notepad.metainfo.xml \
    "$STAGE$METAINFO/org.notepadlinux.Notepad.metainfo.xml"
install -Dm644 packaging/common/notepad.1 \
    "$STAGE$MANDIR/notepad.1"

cat > "$STAGE/usr/bin/notepad" <<'LAUNCHER'
#!/bin/sh
# Notepad-Linux launcher: the sources live in /usr/lib/notepad-linux so the
# application never fights with a pip-installed copy in site-packages.
set -e
LIBDIR=/usr/lib/notepad-linux
PY=${NOTEPAD_PYTHON:-python3}
PYTHONPATH="$LIBDIR${PYTHONPATH:+:$PYTHONPATH}" exec "$PY" -m mufakkira "$@"
LAUNCHER
chmod 0755 "$STAGE/usr/bin/notepad"

install -Dm644 LICENSE "$STAGE/usr/share/doc/$PKG/copyright"
install -Dm644 README.md "$STAGE/usr/share/doc/$PKG/README.md"
install -Dm644 CHANGELOG.md "$STAGE/usr/share/doc/$PKG/CHANGELOG.md"
gzip -9n -c packaging/common/notepad.1 > "$STAGE$MANDIR/notepad.1.gz"
chmod 0644 "$STAGE$MANDIR/notepad.1.gz"

# ------------------------------------------------------------- control ---
INSTALLED_KB="$(du -sk --exclude=DEBIAN "$STAGE" | cut -f1)"
cat > "$STAGE/DEBIAN/control" <<EOF
Package: $PKG
Version: $VERSION
Section: editors
Priority: optional
Architecture: $ARCH
Depends: python3 (>= 3.9), python3-pyside6.qtwidgets | python3-pyside6 | python3-pip, python3-charset-normalizer | python3-pip
Recommends: fonts-noto-core, fonts-liberation, python3-pyside6.qtprintsupport | python3-pyside6
Suggests: fonts-noto-cjk
Installed-Size: $INSTALLED_KB
Maintainer: Notepad-Linux contributors <noreply@github.com>
Homepage: https://github.com/bifa90/Notepad-Linux
Description: Windows 11-style text editor with first-class RTL support
 A fast, minimal text editor for the Linux desktop, styled after the
 Windows 11 Notepad.  It resolves the writing direction per document
 (automatic, right-to-left or left-to-right), ships an Arabic typeface,
 offers ten interface languages, renders Markdown as an optional live
 view without touching the file, and opens very large files in chunks
 with progress and cancellation.
EOF

cat > "$STAGE/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
if [ "$1" = configure ]; then
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database -q /usr/share/applications || true
    fi
    if command -v gtk-update-icon-cache >/dev/null 2>&1; then
        gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true
    fi
fi
exit 0
EOF

cat > "$STAGE/DEBIAN/prerm" <<'EOF'
#!/bin/sh
set -e
exit 0
EOF

cat > "$STAGE/DEBIAN/postrm" <<'EOF'
#!/bin/sh
set -e
if [ "$1" = remove ] || [ "$1" = purge ]; then
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database -q /usr/share/applications || true
    fi
fi
if [ "$1" = purge ]; then
    rm -rf /var/lib/notepad-linux 2>/dev/null || true
fi
exit 0
EOF

chmod 0755 "$STAGE/DEBIAN/postinst" "$STAGE/DEBIAN/prerm" "$STAGE/DEBIAN/postrm"
(cd "$STAGE" && find usr -type f -print0 | sort -z | xargs -0 md5sum > DEBIAN/md5sums)

# ----------------------------------------------------------------- build ---
DEB="$OUT/${PKG}_${VERSION}_${ARCH}.deb"
dpkg-deb --build --root-owner-group "$STAGE" "$DEB" >/dev/null
echo "==> $DEB"
dpkg-deb --info "$DEB" | sed -n '1,14p'
echo "==> contents: $(dpkg-deb -c "$DEB" | wc -l) entries"
