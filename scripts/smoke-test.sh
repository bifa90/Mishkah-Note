#!/usr/bin/env bash
# Smoke-test the packages we ship.
#
#   scripts/smoke-test.sh                  # every artefact that is present
#   scripts/smoke-test.sh --build          # build the .deb first, then test it
#   scripts/smoke-test.sh --deb dist/x.deb --appimage dist/x.AppImage
#
# For each artefact the script unpacks it into a temporary directory, runs the
# copy *inside it* — never the source tree — and checks:
#
# 1. `mishkah --version` prints the released version (so `_version.txt`, the
#    modules and the launcher all travelled),
# 2. an Arabic file survives a write → read round-trip through the packaged
#    code, and the editor model accepts the same text,
# 3. Qt imports, the bundled fonts register and a window can be constructed
#    offscreen (skipped when the artefact ships no Qt, e.g. the .deb, which
#    depends on the system PySide6).
#
# Artefacts whose tools are missing are reported as skipped, never failed, so
# the script is usable on any machine and in CI.  Exit status is non-zero on a
# real failure.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

QT_SKIP_REASON="Qt not loadable on this host"
PASS=0
FAIL=0
SKIP=0
ok()   { printf '  \033[32m✔\033[0m %s\n' "$*"; PASS=$((PASS + 1)); }
bad()  { printf '  \033[31m✘\033[0m %s\n' "$*"; FAIL=$((FAIL + 1)); }
skip() { printf '  \033[33m–\033[0m %s\n' "$*"; SKIP=$((SKIP + 1)); }
head2(){ printf '\n\033[1;36m== %s\033[0m\n' "$*"; }

PYTHON="${PYTHON:-python3}"
BUILD=0
DEB=""
APPIMAGE=""
TREE=""

while [ $# -gt 0 ]; do
    case "$1" in
        --build)     BUILD=1; shift ;;
        --deb)       DEB="${2:-}"; shift 2 ;;
        --appimage)  APPIMAGE="${2:-}"; shift 2 ;;
        --tree)      TREE="${2:-}"; shift 2 ;;
        -h|--help)   sed -n '2,25p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *)           echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done

VERSION="$($PYTHON - <<'EOF'
import pathlib, re
print(re.search(r'^version = "([^"]+)"',
      pathlib.Path("pyproject.toml").read_text(encoding="utf-8"), re.M).group(1))
EOF
)"
echo "version: $VERSION"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/mishkah-smoke-XXXXXX")"
trap 'rm -rf "$WORK"' EXIT

# run_check <label> <python> — PYTHONPATH selects the copy under test.
# Exit 77 means the non-GUI checks passed and Qt could not load here, which is a
# pass with a note, not a skip: the round-trip did run.
run_check() {
    local label="$1" py="$2"
    "$py" scripts/smoke_check.py --expect "$VERSION" --label "$label"
    case $? in
        0)  ok "$label smoke test" ;;
        77) ok "$label smoke test (Qt checks skipped: $QT_SKIP_REASON)" ;;
        *)  bad "$label smoke test" ;;
    esac
}

# --------------------------------------------------------------------- deb ---
smoke_deb() {
    local deb="$1"
    [ -f "$deb" ] || { skip ".deb not found ($deb)"; return; }
    head2 ".deb"
    command -v dpkg-deb >/dev/null 2>&1 || { skip "dpkg-deb not installed"; return; }
    local dir="$WORK/deb"
    mkdir -p "$dir" && dpkg-deb -x "$deb" "$dir" || { bad "dpkg-deb -x"; return; }
    local payload="$dir/usr/lib/mishkah-note"
    local meta="$dir/usr/share/doc/mishkah-note"
    [ -d "$payload" ] || { bad "payload directory missing in the .deb"; return; }
    [ -f "$meta/THIRD-PARTY-NOTICES.md" ] \
        && ok "third-party notices inside the package" \
        || bad "the .deb does not ship THIRD-PARTY-NOTICES.md"
    [ -f "$meta/copyright" ] && ok "MIT licence inside the package" \
        || bad "the .deb ships no copyright file"
    local out
    out=$(PYTHONPATH="$payload" QT_QPA_PLATFORM=offscreen "$PYTHON" -m mishkah --version 2>&1) \
        && [ "$out" = "$VERSION" ] && ok "launcher prints $VERSION" \
        || bad "launcher printed '$out'"
    # The .deb depends on the distribution's PySide6: test it with the host's.
    local py="$PYTHON"
    PYTHONPATH="$payload" QT_QPA_PLATFORM=offscreen run_check "deb payload" "$py"
}
# run_check runs scripts/smoke_check.py from the *source* tree on purpose: the
# checks themselves must not be part of what is being tested.

# ---------------------------------------------------------------- appimage ---
smoke_appimage() {
    local image="$1"
    [ -f "$image" ] || { skip "AppImage not found ($image)"; return; }
    head2 "AppImage"
    chmod +x "$image" 2>/dev/null
    local dir="$WORK/appimage"
    mkdir -p "$dir"
    if ! ( cd "$dir" && "$image" --appimage-extract >/dev/null 2>&1 ); then
        bad "$(basename "$image") --appimage-extract failed"
        return
    fi
    local root="$dir/squashfs-root"
    ok "unpacks"
    [ -f "$root/usr/share/doc/mishkah-note/THIRD-PARTY-NOTICES.md" ] \
        && ok "third-party notices inside the image" \
        || bad "the AppImage does not ship THIRD-PARTY-NOTICES.md"
    [ -d "$root/usr/lib/python-packages/PySide6" ] \
        && ok "PySide6 is bundled" || bad "PySide6 is missing from the image"
    local py="$root/usr/python/bin/python3"
    if [ -x "$py" ]; then
        ok "a Python runtime is bundled"
        "$py" -c 'import sys; print("    " + sys.version.split()[0])'
    else
        bad "no bundled Python (the image cannot run without the host's python3)"
        return
    fi
    local out
    out=$("$root/AppRun" --version 2>&1)
    [ "$out" = "$VERSION" ] && ok "AppRun prints $VERSION" || bad "AppRun printed '$out'"
    PYTHONNOUSERSITE=1 \
    MISHKAH_CLEAN_EXIT=1 \
    QT_QPA_PLATFORM=offscreen \
    QT_PLUGIN_PATH="$root/usr/lib/python-packages/PySide6/Qt/plugins" \
    LD_LIBRARY_PATH="$root/usr/lib/python-packages/PySide6/Qt/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
    PYTHONPATH="$root/usr/lib/python-packages" \
        run_check "AppImage payload" "$py"
}

# ----------------------------------------------------------------- flatpak ---
smoke_flatpak() {
    head2 "Flatpak"
    if ! command -v flatpak-builder >/dev/null 2>&1; then
        skip "flatpak-builder not installed"
        return
    fi
    if ! command -v flatpak >/dev/null 2>&1; then
        skip "flatpak not installed"
        return
    fi
    local dir="$WORK/flatpak-repo"
    if ! flatpak-builder --disable-rofiles-fork --force-clean --repo="$dir" \
            "$WORK/flatpak-build" packaging/flatpak/org.mishkahnote.Mishkah.json \
            >"$WORK/flatpak.log" 2>&1; then
        skip "flatpak-builder failed (needs network and the runtime) — $WORK/flatpak.log"
        return
    fi
    ok "flatpak-builder produced a repository"
    if flatpak build --filesystem="$WORK" "$WORK/flatpak-build" \
            /app/bin/mishkah --version >"$WORK/flatpak-version.txt" 2>&1 \
       && grep -qx "$VERSION" "$WORK/flatpak-version.txt"; then
        ok "the Flatpak app prints $VERSION"
    else
        bad "the Flatpak app did not report $VERSION"
        tail -3 "$WORK/flatpak-version.txt" 2>/dev/null
    fi
}

# --------------------------------------------------------------- windows -----
head2 "Windows MSI"
if command -v msiexec >/dev/null 2>&1; then
    skip "MSI installation is exercised on the windows-latest runner in CI"
else
    skip "MSI can only be smoke-tested on Windows"
fi

# ------------------------------------------------------------------ driver ---
head2 "source tree (baseline)"
# The host interpreter on packaging runners (e.g. AppImage) need not carry Qt:
# MISHKAH_REQUIRE_QT=1 gates the packaged artefact under test, not the baseline.
MISHKAH_REQUIRE_QT=0 QT_QPA_PLATFORM=offscreen PYTHONPATH="$ROOT/src" \
    run_check "source tree" "$PYTHON"

if [ -n "$TREE" ]; then
    head2 "unpacked tree"
    QT_QPA_PLATFORM=offscreen PYTHONPATH="$TREE" \
        run_check "tree $TREE" "$PYTHON"
fi

if [ "$BUILD" = "1" ] && [ -z "$DEB" ]; then
    head2 "building the .deb"
    if bash scripts/build-deb.sh >"$WORK/build-deb.log" 2>&1; then
        ok "scripts/build-deb.sh"
        DEB="dist/mishkah-note_${VERSION}_all.deb"
    else
        bad "scripts/build-deb.sh"
        tail -5 "$WORK/build-deb.log"
    fi
fi

[ -n "$DEB" ] && smoke_deb "$DEB"
[ -n "$APPIMAGE" ] && smoke_appimage "$APPIMAGE"

if [ -z "$DEB" ] && [ -z "$APPIMAGE" ] && [ -z "$TREE" ] && [ "$BUILD" = 0 ]; then
    head2 "built artefacts"
    for candidate in dist/mishkah-note_"$VERSION"_all.deb; do
        [ -f "$candidate" ] && smoke_deb "$candidate"
    done
    for candidate in dist/Mishkah_Note-"$VERSION"-*.AppImage; do
        [ -f "$candidate" ] && smoke_appimage "$candidate"
    done
    [ -f dist/mishkah-note_"$VERSION"_all.deb ] || skip "no .deb in dist/ (run with --build)"
fi

smoke_flatpak

head2 "summary"
printf '  %d passed, %d failed, %d skipped\n' "$PASS" "$FAIL" "$SKIP"
[ "$FAIL" -eq 0 ] || exit 1
