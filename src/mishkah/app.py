"""Application bootstrap: Qt app, fonts, theme, icon, CLI files."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtGui import QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication

from mishkah import APP_ID, APP_NAME, APP_VERSION, ORGANIZATION
from mishkah.cli import USAGE
from mishkah.controllers.main_controller import MainController
from mishkah.core import i18n, resources
from mishkah.core.settings import Settings
from mishkah.services.file_service import FileService
from mishkah.views.main_window import MainWindow

logger = logging.getLogger("mishkah")


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
    app.setProperty("mishkah_theme", resolved)
    return resolved


def is_dark_chrome() -> bool:
    """True when the *window* is dark, whatever the desktop theme says.

    The stylesheet decides the background, so it decides the ink too: asking the
    palette describes the desktop, and on a dark desktop the light stylesheet
    still needs dark glyphs.
    """
    app = QApplication.instance()
    theme = app.property("mishkah_theme") if app is not None else None
    if theme == "dark":
        return True
    if theme == "light":
        return False
    palette = app.palette() if app is not None else QPalette()
    return palette.color(QPalette.ColorRole.Window).lightness() < 128


def set_app_icon(app: QApplication) -> None:
    icon = resources.application_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)
        app.setApplicationDisplayName(APP_NAME)


def build_window(app: QApplication, settings: Settings, service: FileService,
                 paths: List[Path], restore: bool = True,
                 owns_session: bool = True) -> MainWindow:
    """Create one window and its controller.

    ``restore`` re-opens the previous session; ``owns_session`` decides which
    window writes ``open_files`` on exit.  Exactly one window — the first —
    owns the session, otherwise two windows would overwrite each other's list
    and the last one closed would win (the B2 hazard).
    """
    window = MainWindow()
    set_app_icon(app)
    icon = resources.application_icon()
    if not icon.isNull():
        window.setWindowIcon(icon)

    controller = MainController(window, settings, service, parent=app)
    controller.owns_session = bool(owns_session)
    window.setProperty("controller", controller)

    if restore:
        opened = controller.restore_session([str(p) for p in paths]) if paths else None
        if not opened:
            controller.restore_session()
    if window.tab_count() == 0:
        # Nothing to restore: welcome the user instead of handing them an
        # untitled buffer they must name (CD-06).
        controller.show_home()
    return window




def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv if argv is None else argv)

    flags = {arg for arg in argv[1:] if arg.startswith("-")}
    if "--help" in flags or "-h" in flags:
        print(USAGE)
        return 0
    if "--version" in flags:
        print(f"mishkah {APP_VERSION}")
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

    # A second launch hands its paths to the running window and exits (CD-09).
    paths = [Path(a) for a in argv[1:] if not a.startswith("-")]
    instance_server = None
    if not safe_mode:
        try:
            from mishkah.services import single_instance

            if single_instance.send_to_running_instance([str(p) for p in paths]):
                logger.info("handed %d path(s) to the running instance", len(paths))
                return 0
            instance_server = single_instance.start_server()
        except Exception as exc:  # pragma: no cover - never block startup on IPC
            logger.warning("single-instance channel unavailable: %s", exc)
            instance_server = None

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
    windows: List[MainWindow] = []

    def spawn(paths_: List[Path], restore: bool, owns_session: bool) -> MainWindow:
        """Open one more window in this process (CD-29/B2)."""
        window = build_window(app, settings, service, paths_,
                              restore=restore, owns_session=owns_session)
        # Every window can open another one; the factory is what makes the
        # File ▸ New window item real instead of a second "New tab".
        window.new_window_factory = lambda: spawn([], False, False)
        window.show()
        if windows:
            origin = windows[0]
            window.move(origin.x() + 28, origin.y() + 28)
        windows.append(window)
        return window

    primary = spawn(paths, True, True)

    def active_window() -> MainWindow:
        """The window a file from another launch should land in."""
        for window in reversed(windows):
            if window.isVisible():
                return window
        return primary

    def on_last_window_closed() -> None:
        controller = primary.property("controller")
        if controller is not None and not safe_mode:
            controller.save_session()
        app.quit()

    if instance_server is not None:
        def on_paths_received(received) -> None:
            target = active_window()
            controller = target.property("controller")
            if controller is not None:
                for path in received:
                    controller.open_path(path)
                if target.isMinimized():
                    target.showNormal()
                target.show()
                target.raise_()
                target.activateWindow()

        instance_server.paths_received.connect(on_paths_received)

    app.lastWindowClosed.connect(on_last_window_closed)
    try:
        return app.exec()
    finally:
        if instance_server is not None:
            instance_server.close()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
