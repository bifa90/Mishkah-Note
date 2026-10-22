# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller recipe for the Windows build (used by scripts/build-msi.ps1).

Kept in the repository instead of inline flags so the frozen build is
reproducible and reviewable: the Qt modules the application really imports are
listed, the bundled Arabic font travels with the package data, and test-only
modules are excluded.
"""

from pathlib import Path

ROOT = Path(SPECPATH).parent.parent          # …/packaging/windows -> repo root
SRC = ROOT / "src"
LAUNCHER = ROOT / "packaging" / "windows" / "launcher.py"

# The src-layout package need not be installed in the build interpreter.
# Copy the complete resource tree directly, including fonts and their license.
datas = [(str(SRC / "mishkah" / "resources"), "mishkah/resources")]

a = Analysis(
    [str(LAUNCHER)],
    pathex=[str(SRC)],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "PySide6.QtSvg",
        "PySide6.QtPrintSupport",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "unittest",
        "pytest",
        "test",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtQuick",
        "PySide6.QtQml",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Mishkah Note",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(ROOT / "src" / "mishkah" / "resources" / "icons" / "app.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="mishkah",
)
