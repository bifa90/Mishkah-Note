#!/usr/bin/env bash
# Build a portable AppImage (AppDir + appimagetool).
#
#   packaging/appimage/build-appimage.sh
#
# Requires: python3, and appimagetool on PATH (or set APPIMAGETOOL=/path/to/it).
# The Python dependencies are bundled with pip so the result runs on any
# glibc-compatible distribution without installing PySide6 system-wide.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

VERSION="$(python3 - <<'EOF'
import re, pathlib
print(re.search(r'^version = "([^"]+)"',
      pathlib.Path("pyproject.toml").read_text(encoding="utf-8"), re.M).group(1))
EOF
)"
APPDIR="$ROOT/build/Notepad.AppDir"
OUT="$ROOT/dist"
TOOL="${APPIMAGETOOL:-appimagetool}"

rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/lib" \
         "$APPDIR/usr/share/applications" \
         "$APPDIR/usr/share/icons/hicolor/256x256/apps" \
         "$APPDIR/usr/share/metainfo" "$OUT"

echo "==> bundling python packages"
python3 -m pip install --quiet --no-compile \
    --target "$APPDIR/usr/lib/python-packages" \
    "PySide6>=6.5" "charset-normalizer>=3.0"

echo "==> copying application"
cp -r src/mufakkira "$APPDIR/usr/lib/python-packages/"
find "$APPDIR/usr/lib/python-packages" -name '__pycache__' -type d -prune -exec rm -rf {} +

cat > "$APPDIR/AppRun" <<'EOF'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
export PYTHONPATH="$HERE/usr/lib/python-packages${PYTHONPATH:+:$PYTHONPATH}"
export QT_PLUGIN_PATH="$HERE/usr/lib/python-packages/PySide6/Qt/plugins"
export LD_LIBRARY_PATH="$HERE/usr/lib/python-packages/PySide6/Qt/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec python3 -m mufakkira "$@"
EOF
chmod 0755 "$APPDIR/AppRun"

install -m644 packaging/common/notepad.desktop \
    "$APPDIR/usr/share/applications/notepad-linux.desktop"
install -m644 src/mufakkira/resources/icons/app-256.png \
    "$APPDIR/usr/share/icons/hicolor/256x256/apps/notepad-linux.png"
install -m644 src/mufakkira/resources/icons/app.svg \
    "$APPDIR/notepad-linux.svg"

cat > "$APPDIR/org.notepadlinux.Notepad.metainfo.xml" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<component type="desktop-application">
  <id>org.notepadlinux.Notepad</id>
  <name>Notepad</name>
  <summary>Text editor with first-class Arabic and RTL support</summary>
  <metadata_license>MIT</metadata_license>
  <project_license>MIT</project_license>
  <url type="homepage">https://github.com/bifa90/Notepad-Linux</url>
  <launchable type="desktop-id">notepad-linux.desktop</launchable>
  <releases>
    <release version="$VERSION" date="2026-10-21"/>
  </releases>
</component>
EOF

echo "==> packaging"
ARCH="${ARCH:-x86_64}" "$TOOL" "$APPDIR" "$OUT/Notepad-${VERSION}-${ARCH}.AppImage"
echo "==> $OUT/Notepad-${VERSION}-${ARCH}.AppImage"
