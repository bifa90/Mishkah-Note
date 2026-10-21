"""Application bootstrap: Qt app, fonts, theme, icon, CLI files."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtGui import QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication

from mufakkira import APP_ID, APP_NAME, APP_VERSION, ORGANIZATION
from mufakkira.controllers.main_controller import MainController
from mufakkira.core import i18n, resources
from mufakkira.core.settings import Settings
from mufakkira.services.file_service import FileService
from mufakkira.views.main_window import MainWindow

logger = logging.getLogger("mufakkira")


def install_bundled_fonts() -> List[str]:
    """Register every font shipped inside the package; returns families."""
    families: List[str] = []
    for font_path in resources.available_fonts():
        font_id = QFontDatabase.addApplicationFont(str(font_path))
        if font_id < 0:
            logger.warning("could not load font: %s", font_path)
            continue
        families.extend(QFontDatabase.applicationFontFamilies(font_id))
        logger.info("loaded font %s", font_path.name)
    return families


def detect_system_theme(app: QApplication) -> str:
    try:
        scheme = app.styleHints().colorScheme()
        if scheme == Qt.ColorScheme.Dark:
            return "dark"
    except AttributeError:  # Qt < 6.5
        pass
    palette = app.palette()
    if palette.color(QPalette.ColorRole.Window).lightness() < 128:
        return "dark"
    return "light"


def apply_theme(app: QApplication, theme: str) -> str:
    """Apply light/dark QSS; returns the theme actually used."""
    resolved = detect_system_theme(app) if theme == "system" else theme
    qss = resources.stylesheet(resolved)
    if qss:
        app.setStyleSheet(qss)
    app.setProperty("mufakkira_theme", resolved)
    return resolved


def set_app_icon(app: QApplication) -> None:
    icon = resources.application_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)
        app.setApplicationDisplayName(APP_NAME)


def build_window(app: QApplication, settings: Settings,
                 service: FileService, paths: List[Path]) -> MainWindow:
    window = MainWindow()
    set_app_icon(app)
    icon = resources.application_icon()
    if not icon.isNull():
        window.setWindowIcon(icon)

    controller = MainController(window, settings, service, parent=app)
    window.setProperty("controller", controller)

    opened = controller.restore_session([str(p) for p in paths]) if paths else None
    if not opened:
        controller.restore_session()
    if window.tab_count() == 0:
        controller.new_document()
    return window


USAGE = """notepad — a Windows 11-style text editor with first-class RTL support

Usage:
  notepad [OPTION]... [FILE]...

Options:
  --safe-mode   ignore the saved configuration and the previous session
  --version     print the version and exit
  -h, --help    print this help and exit

Files are opened one per tab.  Text direction can be switched with
Ctrl+Shift+Right (RTL), Ctrl+Shift+Left (LTR) or Ctrl+Shift+A (automatic).
"""


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv if argv is None else argv)

    flags = {arg for arg in argv[1:] if arg.startswith("-")}
    if "--help" in flags or "-h" in flags:
        print(USAGE)
        return 0
    if "--version" in flags:
        print(f"notepad {APP_VERSION}")
        return 0
    safe_mode = "--safe-mode" in flags or "--safe" in flags

    logging.basicConfig(level=logging.INFO,
                        format="%(levelname)s %(name)s: %(message)s")

    # High-DPI + Wayland friendliness
    QApplication.setApplicationName(APP_NAME)
    QApplication.setOrganizationName(ORGANIZATION)
    QApplication.setApplicationVersion(APP_VERSION)
    QCoreApplication.setApplicationName(APP_NAME)

    app = QApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORGANIZATION)
    app.setApplicationVersion(APP_VERSION)
    app.setDesktopFileName(f"{APP_ID}.desktop")

    settings = Settings.load()
    if safe_mode:
        settings.path = None          # never persisted unless the user asks
        settings.restore_session = False
        settings.open_files = []
    i18n.set_language(settings.ui_language)

    install_bundled_fonts()
    resolved_theme = apply_theme(app, settings.theme)
    logger.info("theme=%s ui_language=%s", resolved_theme, settings.ui_language)

    service = FileService()
    paths = [Path(a) for a in argv[1:] if not a.startswith("-")]
    windows = [build_window(app, settings, service, paths)]
    for window in windows:
        window.show()

    def on_last_window_closed() -> None:
        controller = windows[-1].property("controller")
        if controller is not None and not safe_mode:
            controller.save_session()
        app.quit()

    app.lastWindowClosed.connect(on_last_window_closed)
    return app.exec()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
