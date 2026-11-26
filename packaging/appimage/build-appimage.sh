#!/usr/bin/env bash
# Build a portable AppImage (AppDir + appimagetool).
#
#   packaging/appimage/build-appimage.sh
#   APPIMAGETOOL=/path/to/appimagetool packaging/appimage/build-appimage.sh
#
# What ends up inside
# -------------------
# * the application and its Python dependencies (PySide6, charset-normalizer),
# * **a portable CPython** (python-build-standalone), so the image runs on a
#   machine that has never seen Python — the previous build called the host's
#   `python3` and died instantly where none was installed,
# * the third-party notices, which the LGPL requires next to the Qt libraries
#   we bundle.
#
# Environment
# -----------
#   APPIMAGETOOL                     path to appimagetool (default: from PATH)
#   ARCH                             target architecture (default: uname -m)
#   OUT                              output directory (default: dist/)
#   MISHKAH_PYTHON_STANDALONE_ARCHIVE
#                                    reuse a local install_only tarball instead
#                                    of downloading one (offline builds)
#   MISHKAH_APPIMAGE_SYSTEM_PYTHON=1 do not bundle an interpreter; AppRun then
#                                    requires the host's python3 and says so in
#                                    Arabic and English.  Development only.
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
BUNDLE_PYTHON=1
[ "${MISHKAH_APPIMAGE_SYSTEM_PYTHON:-0}" = "1" ] && BUNDLE_PYTHON=0

# Pinned so a rebuild produces the same runtime; both values are printed below
# and can be overridden without editing this file.
PBS_RELEASE="${PBS_RELEASE:-20261124}"
PBS_PYTHON="${PBS_PYTHON:-3.11.18}"
PBS_TRIPLE="unknown-linux-gnu"
case "$ARCH" in
    x86_64|amd64)   PBS_ARCH="x86_64" ;;
    aarch64|arm64)  PBS_ARCH="aarch64" ;;
    *) echo "unsupported architecture for a bundled Python: $ARCH" >&2; exit 2 ;;
esac
PBS_NAME="cpython-${PBS_PYTHON}+${PBS_RELEASE}-${PBS_ARCH}-${PBS_TRIPLE}-install_only.tar.gz"
PBS_URL="https://github.com/astral-sh/python-build-standalone/releases/download/${PBS_RELEASE}/${PBS_NAME}"

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
         "$APPDIR/usr/share/doc/mishkah-note" \
         "$APPDIR/usr/share/icons/hicolor/256x256/apps" \
         "$APPDIR/usr/share/metainfo" "$OUT"

# ---------------------------------------------------------------- python ---
if [ "$BUNDLE_PYTHON" = "1" ]; then
    PYTHON_BIN="$APPDIR/usr/python/bin/python3"
    echo "==> bundling CPython ${PBS_PYTHON} (python-build-standalone ${PBS_RELEASE})"
    TARBALL="${MISHKAH_PYTHON_STANDALONE_ARCHIVE:-}"
    if [ -z "$TARBALL" ]; then
        TARBALL="$ROOT/build/$PBS_NAME"
        if [ ! -f "$TARBALL" ]; then
            echo "    fetching $PBS_URL"
            curl -fsSL --retry 3 --retry-delay 2 -o "$TARBALL.part" "$PBS_URL"
            mv "$TARBALL.part" "$TARBALL"
        fi
    fi
    [ -f "$TARBALL" ] || { echo "no Python archive at $TARBALL" >&2; exit 2; }
    mkdir -p "$APPDIR/usr/python"
    tar -xzf "$TARBALL" -C "$APPDIR/usr/python" --strip-components=1
    [ -x "$PYTHON_BIN" ] || { echo "the archive has no bin/python3" >&2; exit 2; }
    "$PYTHON_BIN" -c 'import sys; print("    bundled:", sys.version.split()[0])'
else
    echo "==> MISHKAH_APPIMAGE_SYSTEM_PYTHON=1: the image will need the host's python3"
    PYTHON_BIN="python3"
fi

# ------------------------------------------------------------- libraries ---
echo "==> installing python packages for the image"
"$PYTHON_BIN" -m pip install --quiet --no-compile --upgrade \
    --target "$APPDIR/usr/lib/python-packages" \
    "PySide6>=6.5,<7" "charset-normalizer>=3.0"

echo "==> copying application"
cp -r src/mishkah "$APPDIR/usr/lib/python-packages/"
find "$APPDIR/usr/lib/python-packages" -name '__pycache__' -type d -prune \
    -exec rm -rf {} +

# --------------------------------------------------------------- AppRun ---
if [ "$BUNDLE_PYTHON" = "1" ]; then
    PY_LAUNCH='exec "$HERE/usr/python/bin/python3" -m mishkah "$@"'
    PY_GUARD=''
else
    PY_LAUNCH='exec python3 -m mishkah "$@"'
    PY_GUARD='if ! command -v python3 >/dev/null 2>&1; then
    echo "mishkah: this AppImage was built without a bundled Python." >&2
    echo "مشكاة: هذه النسخة تحتاج python3 على نظامك، ولم تُحزم معها مفسّرًا." >&2
    echo "  Install python3 (with PySide6) or use the .deb / Flatpak build." >&2
    exit 1
fi'
fi

cat > "$APPDIR/AppRun" <<EOF
#!/bin/sh
# AppRun: point Python at the bundled packages and hand over to the app.
HERE="\$(dirname "\$(readlink -f "\$0")")"
$PY_GUARD
export PYTHONPATH="\$HERE/usr/lib/python-packages\${PYTHONPATH:+:\$PYTHONPATH}"
export QT_PLUGIN_PATH="\$HERE/usr/lib/python-packages/PySide6/Qt/plugins"
export LD_LIBRARY_PATH="\$HERE/usr/lib/python-packages/PySide6/Qt/lib\${LD_LIBRARY_PATH:+:\$LD_LIBRARY_PATH}"
export QT_QPA_PLATFORMTHEME="\${QT_QPA_PLATFORMTHEME:-}"
$PY_LAUNCH
EOF
chmod 0755 "$APPDIR/AppRun"

# Fail here rather than in front of a user if the launcher does not parse.
sh -n "$APPDIR/AppRun" || { echo "generated AppRun is not valid sh" >&2; exit 2; }

# --------------------------------------------------- metadata and notices ---
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
# LGPL v3: the notices travel with the Qt libraries we bundle.
install -m644 THIRD-PARTY-NOTICES.md \
    "$APPDIR/usr/share/doc/mishkah-note/THIRD-PARTY-NOTICES.md"
install -m644 LICENSE "$APPDIR/usr/share/doc/mishkah-note/LICENSE"
install -m644 CHANGELOG.md "$APPDIR/usr/share/doc/mishkah-note/CHANGELOG.md"

if command -v "$TOOL" >/dev/null 2>&1 || [ -x "$TOOL" ]; then
    echo "==> packaging"
    ARCH="$ARCH" "$TOOL" --no-appstream "$APPDIR" "$TARGET"
    echo "==> $TARGET"
else
    echo "==> AppDir ready at $APPDIR (appimagetool missing: no .AppImage produced)" >&2
    exit 2
fi
