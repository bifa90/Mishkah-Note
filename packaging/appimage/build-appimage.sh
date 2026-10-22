#!/usr/bin/env bash
# Build a portable AppImage (AppDir + appimagetool).
#
#   packaging/appimage/build-appimage.sh
#   APPIMAGETOOL=/path/to/appimagetool packaging/appimage/build-appimage.sh
#
# Requires: python3, pip and appimagetool (download it from
# https://github.com/AppImage/appimagetool/releases — a single static binary).
#
# The Python dependencies are bundled *inside* the AppDir, so the result runs on
# any glibc-compatible distribution without installing PySide6 system-wide.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

VERSION="$(python3 - <<'EOF'
import pathlib, re
print(re.search(r'^version = "([^"]+)"',
      pathlib.Path("pyproject.toml").read_text(encoding="utf-8"), re.M).group(1))
EOF
)"
ARCH="${ARCH:-$(uname -m)}"
APPDIR="$ROOT/build/Mishkah_Note.AppDir"
OUT="${OUT:-$ROOT/dist}"
TOOL="${APPIMAGETOOL:-appimagetool}"
TARGET="$OUT/Mishkah_Note-${VERSION}-${ARCH}.AppImage"

if ! command -v "$TOOL" >/dev/null 2>&1 && [ ! -x "$TOOL" ]; then
    cat >&2 <<EOF
appimagetool was not found.
  Download: https://github.com/AppImage/appimagetool/releases
  Then run: APPIMAGETOOL=/path/to/appimagetool packaging/appimage/build-appimage.sh
The AppDir is still assembled at $APPDIR, so the packaging can be inspected.
EOF
fi

rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/lib" \
         "$APPDIR/usr/share/applications" \
         "$APPDIR/usr/share/icons/hicolor/256x256/apps" \
         "$APPDIR/usr/share/metainfo" "$OUT"

echo "==> bundling python packages"
python3 -m pip install --quiet --no-compile --upgrade \
    --target "$APPDIR/usr/lib/python-packages" \
    "PySide6>=6.5" "charset-normalizer>=3.0"

echo "==> copying application"
cp -r src/mishkah "$APPDIR/usr/lib/python-packages/"
find "$APPDIR/usr/lib/python-packages" -name '__pycache__' -type d -prune -exec rm -rf {} +

cat > "$APPDIR/AppRun" <<'EOF'
#!/bin/sh
# AppRun: point Python at the bundled packages and hand over to the app.
HERE="$(dirname "$(readlink -f "$0")")"
export PYTHONPATH="$HERE/usr/lib/python-packages${PYTHONPATH:+:$PYTHONPATH}"
export QT_PLUGIN_PATH="$HERE/usr/lib/python-packages/PySide6/Qt/plugins"
export LD_LIBRARY_PATH="$HERE/usr/lib/python-packages/PySide6/Qt/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export QT_QPA_PLATFORMTHEME="${QT_QPA_PLATFORMTHEME:-}"
exec python3 -m mishkah "$@"
EOF
chmod 0755 "$APPDIR/AppRun"

install -m644 packaging/common/mishkah.desktop \
    "$APPDIR/mishkah-note.desktop"
install -m644 src/mishkah/resources/icons/app-256.png \
    "$APPDIR/mishkah-note.png"
install -m644 src/mishkah/resources/icons/app-256.png \
    "$APPDIR/usr/share/icons/hicolor/256x256/apps/mishkah-note.png"
install -m644 src/mishkah/resources/icons/app.svg \
    "$APPDIR/mishkah-note.svg"
install -m644 packaging/common/mishkah.desktop \
    "$APPDIR/usr/share/applications/mishkah-note.desktop"
install -m644 packaging/common/org.mishkahnote.Mishkah.metainfo.xml \
    "$APPDIR/usr/share/metainfo/org.mishkahnote.Mishkah.metainfo.xml"

if command -v "$TOOL" >/dev/null 2>&1 || [ -x "$TOOL" ]; then
    echo "==> packaging"
    ARCH="$ARCH" "$TOOL" --no-appstream "$APPDIR" "$TARGET"
    echo "==> $TARGET"
else
    echo "==> AppDir ready at $APPDIR (appimagetool missing: no .AppImage produced)" >&2
    exit 2
fi
