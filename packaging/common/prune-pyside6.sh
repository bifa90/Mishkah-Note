#!/usr/bin/env bash
# Trim unused Qt/PySide6 modules, dev tools, stubs, and QML from a PySide6
# installation directory.  Shared by the AppImage and Flatpak builds so both
# stay compact while preserving every module Mishkah Note needs at runtime
# (QtCore, QtGui, QtWidgets, QtNetwork, QtPrintSupport, QtSvg, QtDBus,
# QtOpenGL, XCB/Wayland platform plugins, TLS, imageformats, styles).
#
# Usage: packaging/common/prune-pyside6.sh <path/to/PySide6>
set -euo pipefail

PYSIDE_DIR="${1:-}"
if [ -z "$PYSIDE_DIR" ] || [ ! -d "$PYSIDE_DIR" ]; then
    echo "prune-pyside6.sh: directory not found: $PYSIDE_DIR" >&2
    exit 1
fi

echo "==> pruning unused Qt components from $PYSIDE_DIR"

# 1. Unused directories (QML, translations, metatypes, headers, dev scripts)
rm -rf \
    "$PYSIDE_DIR/Qt/qml" \
    "$PYSIDE_DIR/Qt/translations" \
    "$PYSIDE_DIR/Qt/libexec" \
    "$PYSIDE_DIR/Qt/metatypes" \
    "$PYSIDE_DIR/typesystems" \
    "$PYSIDE_DIR/include" \
    "$PYSIDE_DIR/examples" \
    "$PYSIDE_DIR/scripts"

# 2. Unused Qt developer CLI binaries
for tool in \
    assistant designer linguist lrelease lupdate \
    qmllint qmlformat qmlls qmltyperegistrar \
    balsam balsamui svgtoqml androiddeployqt qsb metaobjectdump; do
    rm -f "$PYSIDE_DIR/$tool" "$PYSIDE_DIR/Qt/bin/$tool"
done

# 3. Unused Python bindings for modules Mishkah Note never imports
for mod in \
    QtQml QtQmlCore QtQmlModels QtQmlWorkerScript \
    QtQuick QtQuickControls2 QtQuickWidgets QtQuick3D \
    QtSql QtTest QtConcurrent QtXml QtOpenGLWidgets QtUiTools; do
    rm -f "$PYSIDE_DIR/${mod}"*.so "$PYSIDE_DIR/${mod}"*.pyi
done

# 4. Matching unused Qt shared libraries
if [ -d "$PYSIDE_DIR/Qt/lib" ]; then
    for lib in \
        libQt6Qml libQt6Quick libQt6Sql libQt6Test libQt6Concurrent \
        libQt6Xml libQt6ShaderTools libQt6Labs libQt6OpenGLWidgets \
        libQt6VirtualKeyboard; do
        rm -f "$PYSIDE_DIR/Qt/lib/${lib}"*.so*
    done
fi

# 5. Unused Qt plugin families (keep platforms, wayland, xcb, tls, styles, etc.)
if [ -d "$PYSIDE_DIR/Qt/plugins" ]; then
    for plugin_dir in \
        qmltooling sqldrivers assetimporters sceneparsers \
        geometryloaders renderers renderplugins designer qmllint; do
        rm -rf "$PYSIDE_DIR/Qt/plugins/$plugin_dir"
    done
fi

# 6. Type stubs and bytecode caches
find "$PYSIDE_DIR" -name '*.pyi' -type f -delete
find "$PYSIDE_DIR" -name '__pycache__' -type d -prune -exec rm -rf {} +
