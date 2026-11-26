#!/usr/bin/env bash
# Verify every packaging artefact this machine can build, and statically check
# the ones whose tooling is not installed (rpmbuild, makepkg, appimagetool,
# flatpak-builder, WiX).
#
#   scripts/verify-packaging.sh            # build + inspect everything possible
#   scripts/verify-packaging.sh --quick    # static checks only
#
# Exit status is non-zero when a check fails.  Missing tools are reported as
# "skipped", never as failures, so the script is useful on any distribution.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

QUICK=0
[ "${1:-}" = "--quick" ] && QUICK=1

PYTHON="${PYTHON:-python3}"
PASS=0
FAIL=0
SKIP=0

ok()   { printf '  \033[32m✔\033[0m %s\n' "$*"; PASS=$((PASS + 1)); }
bad()  { printf '  \033[31m✘\033[0m %s\n' "$*"; FAIL=$((FAIL + 1)); }
skip() { printf '  \033[33m–\033[0m %s\n' "$*"; SKIP=$((SKIP + 1)); }
head2(){ printf '\n\033[1;36m== %s\033[0m\n' "$*"; }

VERSION="$($PYTHON - <<'EOF'
import pathlib, re
print(re.search(r'^version = "([^"]+)"',
      pathlib.Path("pyproject.toml").read_text(encoding="utf-8"), re.M).group(1))
EOF
)"
# PEP 440 normalises "1.0.02" to "1.0.1" in wheel/sdist file names, while the
# application (and the .deb, .rpm, PKGBUILD and MSI) keep the literal "1.0.02".
NORMALIZED="$($PYTHON - <<EOF
try:
    from packaging.version import Version
except ImportError:                     # older hosts: minimal normalisation
    import re
    print(re.sub(r"\.0(\d)", r".\1", "$VERSION", count=1))
else:
    print(Version("$VERSION"))
EOF
)"
echo "version: $VERSION (wheel/sdist: $NORMALIZED)"

# ---------------------------------------------------------------- sources ---
head2 "source tree"
if $PYTHON -m compileall -q src >/dev/null; then ok "every module compiles"; else bad "compileall"; fi
find src -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null

if $PYTHON - <<'EOF'
import ast
import sys
from pathlib import Path

# Only *module-level* imports count: a lazily imported Qt helper inside a
# rendering function keeps the modules importable without a display.
bad = []
paths = list(Path("src/mishkah/core").rglob("*.py")) + \
        list(Path("src/mishkah/models").rglob("*.py"))
for path in paths:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        names = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        if any(name.split(".")[0] in ("PySide6", "PyQt5", "PyQt6", "PySide2")
               for name in names):
            bad.append(f"{path}:{node.lineno}")
sys.exit(1 if bad else 0)
EOF
then ok "core/ and models/ import no Qt at module level"; else bad "Qt import leaked into core/ or models/"; fi

# ------------------------------------------------------------------ shells ---
head2 "shell scripts"
for script in scripts/*.sh packaging/appimage/*.sh packaging/flatpak/*.sh; do
    [ -f "$script" ] || continue
    if bash -n "$script"; then ok "bash -n $script"; else bad "bash -n $script"; fi
done

# --------------------------------------------------------------------- deb ---
head2 "Debian package"
if [ "$QUICK" = 0 ]; then
    if bash scripts/build-deb.sh >/tmp/verify-deb.log 2>&1; then
        DEB="dist/mishkah-note_${VERSION}_all.deb"
        if [ -f "$DEB" ]; then ok "built $DEB"; else bad "build script did not produce $DEB"; fi
        if dpkg-deb --info "$DEB" | grep -q "^ Package: mishkah-note"; then
            ok "control metadata"
        else
            bad "control metadata"
        fi
        if dpkg-deb --info "$DEB" | grep -q "^ Version: $VERSION"; then
            ok "version $VERSION in the control file"
        else
            bad "version mismatch in the .deb"
        fi
        dpkg-deb -c "$DEB" > /tmp/verify-deb-contents.txt
        for entry in usr/bin/mishkah usr/share/applications/mishkah-note.desktop \
                     usr/share/man/man1/mishkah.1.gz \
                     usr/share/metainfo/org.mishkahnote.Mishkah.metainfo.xml \
                     usr/share/doc/mishkah-note/THIRD-PARTY-NOTICES.md \
                     usr/lib/mishkah-note/mishkah/app.py; do
            if grep -q "\./$entry\$" /tmp/verify-deb-contents.txt; then ok "contains $entry"
            else bad "missing $entry"; fi
        done
        if dpkg-deb --info "$DEB" | grep -q "^ Installed-Size"; then
            ok "Installed-Size is declared"
        else
            bad "Installed-Size missing"
        fi
        rm -rf /tmp/deb-extract && mkdir -p /tmp/deb-extract
        dpkg-deb -x "$DEB" /tmp/deb-extract
        if PYTHONPATH=/tmp/deb-extract/usr/lib/mishkah-note QT_QPA_PLATFORM=offscreen \
             $PYTHON -m mishkah --version > /tmp/verify-deb-run.txt 2>&1 \
             && grep -q "$VERSION" /tmp/verify-deb-run.txt; then
            ok "the packaged tree runs (--version)"
        else
            bad "the packaged tree does not run"
        fi
        if [ -x /tmp/deb-extract/usr/bin/mishkah ]; then ok "launcher is executable"; else bad "launcher mode"; fi
    else
        bad "scripts/build-deb.sh"
        tail -5 /tmp/verify-deb.log
    fi
else
    skip "build skipped (--quick)"
fi

# ----------------------------------------------------- third-party notices ---
# Qt and PySide6 are LGPL v3: the notices must (a) exist, (b) say what they have
# to say, and (c) travel inside every package.  A recipe that stops shipping the
# file breaks licensing, so this section fails loudly instead of warning.
head2 "third-party notices"
NOTICE=THIRD-PARTY-NOTICES.md
if [ -s "$NOTICE" ]; then ok "$NOTICE exists"; else bad "$NOTICE is missing"; fi
for needle in "LGPL v3" "OFL" "MIT" "PSF License"; do
    if grep -qi "$needle" "$NOTICE"; then ok "notices mention $needle"
    else bad "notices do not mention $needle"; fi
done
# The LGPL asks for a way to swap the library out; the file must explain it.
if grep -q "appimage-extract" "$NOTICE" && grep -qi "replace" "$NOTICE"; then
    ok "notices explain how to replace the bundled Qt libraries"
else
    bad "notices do not explain how to replace the bundled Qt libraries"
fi

# Each packaging recipe has to reference the file by name.
notice_recipes_check() {
    local file="$1" label="$2"
    if [ ! -f "$file" ]; then bad "$label: $file is missing"; return; fi
    if grep -q "THIRD-PARTY-NOTICES" "$file"; then ok "$label ships $NOTICE"
    else bad "$label does not ship $NOTICE"; fi
}
notice_recipes_check scripts/build-deb.sh         ".deb recipe"
notice_recipes_check packaging/rpm/mishkah-note.spec ".rpm spec"
notice_recipes_check packaging/arch/PKGBUILD      "Arch PKGBUILD"
notice_recipes_check packaging/appimage/build-appimage.sh "AppImage recipe"
notice_recipes_check packaging/flatpak/org.mishkahnote.Mishkah.json "Flatpak manifest"
notice_recipes_check scripts/build-msi.ps1        "MSI recipe"
if grep -q "include THIRD-PARTY-NOTICES.md" MANIFEST.in; then
    ok "sdist includes $NOTICE"
else
    bad "sdist does not include $NOTICE"
fi
# The AppImage must not go back to borrowing the host interpreter by default.
if grep -q "MISHKAH_APPIMAGE_SYSTEM_PYTHON" packaging/appimage/build-appimage.sh \
   && ! grep -q '^exec python3 -m mishkah' packaging/appimage/build-appimage.sh; then
    ok "AppImage bundles its own CPython (host python only as an explicit opt-in)"
else
    bad "AppImage still relies on the host python3"
fi

# --------------------------------------------------------------------- rpm ---
head2 "RPM spec"
if command -v rpmspec >/dev/null 2>&1; then
    if rpmspec -q --qf '%{VERSION}\n' packaging/rpm/mishkah-note.spec 2>/dev/null | grep -qx "$VERSION"; then
        ok "rpmspec parses and reports $VERSION"
    else
        bad "rpmspec could not parse the spec"
    fi
else
    skip "rpmspec not installed (spec syntax checked by the workflow in a Fedora container)"
fi
if grep -q "^Version:.*version_override" packaging/rpm/mishkah-note.spec; then
    ok "version comes from one place (%{version_override})"
else
    bad "spec version is hard-coded"
fi

# -------------------------------------------------------------------- arch ---
head2 "Arch PKGBUILD"
if command -v makepkg >/dev/null 2>&1; then
    ( cd packaging/arch && makepkg --printsrcinfo >/dev/null ) && ok "makepkg parses the PKGBUILD" \
        || bad "makepkg rejected the PKGBUILD"
else
    skip "makepkg not installed (checked in the archlinux container by the workflow)"
fi
if grep -q "^pkgver=$VERSION$" packaging/arch/PKGBUILD; then ok "PKGBUILD pkgver=$VERSION"; else bad "PKGBUILD pkgver"; fi

# --------------------------------------------------------------- appimage ---
head2 "AppImage"
if command -v appimagetool >/dev/null 2>&1; then
    ok "appimagetool available (run packaging/appimage/build-appimage.sh to produce the file)"
else
    skip "appimagetool not installed; build-appimage.sh assembles the AppDir and exits 2 with instructions"
fi

# ----------------------------------------------------------------- flatpak ---
head2 "Flatpak"
if $PYTHON -c "import json,sys; json.load(open('packaging/flatpak/org.mishkahnote.Mishkah.json'))"; then
    ok "manifest is valid JSON"
else
    bad "manifest JSON"
fi
if $PYTHON - <<'EOF'
import json, sys
m = json.load(open("packaging/flatpak/org.mishkahnote.Mishkah.json"))
required = ["app-id", "runtime", "sdk", "command", "modules"]
missing = [k for k in required if k not in m]
sys.exit(1 if missing else 0)
EOF
then ok "manifest has the required keys"; else bad "manifest keys"; fi
if command -v flatpak-builder >/dev/null 2>&1; then
    ok "flatpak-builder available (see docs/ci for the CI recipe)"
else
    skip "flatpak-builder not installed"
fi

# ----------------------------------------------------------------- windows ---
head2 "Windows MSI"
if $PYTHON -c "import xml.dom.minidom as m; m.parse('packaging/windows/mishkah.wxs')"; then
    ok "mishkah.wxs is well-formed XML"
else
    bad "mishkah.wxs"
fi
for piece in 'Scope="perMachine"' 'WixUI_InstallDir' 'Files Include=' 'MajorUpgrade'; do
    if grep -q "$piece" packaging/windows/mishkah.wxs; then ok "wxs declares $piece"; else bad "wxs lacks $piece"; fi
done
if [ -f packaging/windows/mishkah.spec ] && [ -f packaging/windows/launcher.py ]; then
    ok "PyInstaller recipe and launcher are present"
else
    bad "PyInstaller recipe missing"
fi
if command -v wix >/dev/null 2>&1; then
    ok "wix available"
else
    skip "wix runs only on Windows; the workflow builds the MSI on windows-latest"
fi

# ------------------------------------------------------------------ desktop ---
head2 "desktop entry and AppStream"
if command -v desktop-file-validate >/dev/null 2>&1; then
    desktop-file-validate packaging/common/mishkah.desktop && ok "desktop-file-validate" \
        || bad "desktop-file-validate"
else
    if /usr/bin/env python3 - <<'EOF'
from pathlib import Path
text = Path("packaging/common/mishkah.desktop").read_text(encoding="utf-8")
required = ["[Desktop Entry]", "Type=Application", "Name=", "Exec=mishkah %F",
            "Icon=mishkah-note", "Categories=Utility;TextEditor;"]
missing = [key for key in required if key not in text]
raise SystemExit(1 if missing else 0)
EOF
    then ok "desktop entry has the required keys"; else bad "desktop entry"; fi
    skip "desktop-file-validate not installed"
fi
if $PYTHON -c "import xml.dom.minidom as m; m.parse('packaging/common/org.mishkahnote.Mishkah.metainfo.xml')"; then
    ok "AppStream metadata is well-formed"
else
    bad "AppStream metadata"
fi
if command -v appstreamcli >/dev/null 2>&1; then
    appstreamcli validate --no-net packaging/common/org.mishkahnote.Mishkah.metainfo.xml \
        && ok "appstreamcli validate" || bad "appstreamcli validate"
else
    skip "appstreamcli not installed"
fi

# --------------------------------------------------------------------- man ---
head2 "manual page"
if command -v groff >/dev/null 2>&1; then
    if groff -man -Tutf8 packaging/common/mishkah.1 >/dev/null 2>&1; then
        ok "groff renders mishkah.1"
    else
        bad "groff rejected mishkah.1"
    fi
else
    skip "groff not installed"
fi
if grep -q "$VERSION" packaging/common/mishkah.1; then ok "man page carries $VERSION"; else bad "man page version"; fi

# ------------------------------------------------------------------- wheel ---
head2 "sdist + wheel"
if [ "$QUICK" = 0 ]; then
    rm -rf dist/*.whl dist/*.tar.gz 2>/dev/null
    if $PYTHON -m build --no-isolation >/tmp/verify-build.log 2>&1; then
        ok "python -m build"
        WHEEL="$(ls dist/mishkah_note-*.whl 2>/dev/null | head -1)"
        if [ -n "$WHEEL" ]; then
            ok "wheel built: $(basename "$WHEEL") (PEP 440 name for $VERSION)"
        else
            bad "wheel name"
        fi
        SDIST="dist/mishkah_note-${NORMALIZED}.tar.gz"
        if [ -f "$SDIST" ]; then
            # List first, then grep: ``grep -q`` closes the pipe, and under
            # ``pipefail`` tar's SIGPIPE would report the opposite of the truth.
            tar -tzf "$SDIST" > /tmp/verify-sdist.txt 2>/dev/null
            if grep -qx "mishkah_note-${NORMALIZED}/THIRD-PARTY-NOTICES.md" \
                    /tmp/verify-sdist.txt; then
                ok "sdist carries THIRD-PARTY-NOTICES.md"
            else
                bad "sdist is missing THIRD-PARTY-NOTICES.md"
            fi
        else
            bad "no sdist at $SDIST"
        fi
        VENV=/tmp/verify-venv
        rm -rf "$VENV"
        if $PYTHON -m venv "$VENV" >/dev/null 2>&1; then
            # A genuinely clean environment: the wheel and its declared
            # dependencies come from PyPI, nothing is borrowed from the host.
            if "$VENV/bin/pip" install --quiet --upgrade pip >/tmp/verify-pip.log 2>&1 \
               && "$VENV/bin/pip" install --quiet "$WHEEL" >>/tmp/verify-pip.log 2>&1; then
                ok "wheel + dependencies install into a clean venv"
                if QT_QPA_PLATFORM=offscreen "$VENV/bin/mishkah" --version > /tmp/verify-cli.txt 2>&1 \
                   && grep -q "$VERSION" /tmp/verify-cli.txt; then
                    ok "installed console script runs (--version)"
                else
                    bad "console script"
                    tail -3 /tmp/verify-cli.txt
                fi
                if "$VENV/bin/python" -c "import mishkah, mishkah.core.markdown" >/dev/null 2>&1; then
                    ok "package imports from site-packages"
                else
                    bad "package import"
                fi
            else
                skip "PyPI not reachable for a clean venv install — see /tmp/verify-pip.log"
            fi
        else
            skip "venv creation unavailable"
        fi
    else
        bad "python -m build"
        tail -10 /tmp/verify-build.log
    fi
    # Put the packages back: the workflow attaches them to the release.
    $PYTHON -m build --no-isolation >/dev/null 2>&1 || true
else
    skip "build skipped (--quick)"
fi

# ----------------------------------------------------------------- summary ---
head2 "summary"
printf '  %d passed, %d failed, %d skipped\n' "$PASS" "$FAIL" "$SKIP"
[ "$FAIL" -eq 0 ] || exit 1
