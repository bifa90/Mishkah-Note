#!/usr/bin/env python3
"""Render every README screenshot from the real application.

Nothing here is a mock-up: the script boots the same :class:`MainController`
the ``mishkah`` entry point builds, loads sample documents through the normal
document model, and grabs the widget with ``QWidget.grab()``.  Run it after a
visual change so the README never shows an older interface::

    QT_QPA_PLATFORM=offscreen python tools/make_screenshots.py

It needs the runtime dependencies only (PySide6).  The output lands in
``docs/screenshots/`` at 2× device pixel ratio, which stays sharp on HiDPI
screens without bloating the repository.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QFont  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from mishkah.app import apply_theme, install_bundled_fonts  # noqa: E402
from mishkah.controllers.main_controller import MainController  # noqa: E402
from mishkah.core import i18n  # noqa: E402
from mishkah.core.settings import Settings  # noqa: E402
from mishkah.services.file_service import FileService  # noqa: E402
from mishkah.views.main_window import MainWindow  # noqa: E402

OUT = ROOT / "docs" / "screenshots"
WIDTH, HEIGHT = 1000, 640
#: Grab at this device pixel ratio when a real screen is present.
SCALE = int(os.environ.get("MISHKAH_SHOT_SCALE", "2"))

ARABIC_NOTE = """# خطة الأسبوع

- [x] مراجعة مفكرة مشكاة على **لينكس**
- [x] ضبط اتجاه النص تلقائيًا
- [ ] كتابة ملاحظات الاجتماع

> الخطة قابلة للتعديل دائمًا.

| المهمة | الموعد |
|--------|--------|
| المراجعة | الاثنين |
| التسليم | الجمعة |
"""

MARKDOWN_NOTE = """# مفكرة مشكاة · Mishkah Note

نص **عربي** و *إنجليزي* في المستند نفسه، مع `كود` مضمَّن و~~نص محذوف~~.

## لماذا Markdown حيّ؟

- يقرأ المستند منسّقًا **دون حذف حرف واحد**.
- `Ctrl+Shift+M` يبدّل العرض، والملف يبقى كما هو.
- [رابط إلى المشروع](https://github.com/bifa90/Mishkah-Note)
- خط فاصل، جداول، واقتباسات:

> ما تراه هو ما كتبته — لا أكثر ولا أقل.

| الصيغة | الأمر |
|--------|-------|
| DEB | `build-deb.sh` |
| RPM | `rpmbuild` |

---

```python
def greet(name: str) -> str:
    return f"مرحبًا {name}"
```
"""

ENGLISH_NOTE = """# Mishkah Note

Write **Arabic** and English in one buffer, with `inline code`, ~~strikethrough~~
and [links](https://github.com/bifa90/Mishkah-Note) — all of it unedited.

## Live Markdown is a view, not an edit

- The file keeps every `#`, `*` and backtick.
- `Ctrl+Shift+M` toggles the rendering, the bytes never move.
- Bullets, quotes, rules and tables are painted over the syntax.

> What you see is what you typed — no more, no less.

| Package | Command |
|---------|---------|
| DEB     | `build-deb.sh` |
| RPM     | `rpmbuild` |
| Flatpak | `flatpak-builder` |

---

```python
def greet(name: str) -> str:
    return f"مرحبًا {name}"
```
"""

CODE_NOTE = '''"""Direction-aware helpers used by the editor."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Span:
    start: int
    end: int
    style: str


def resolve(mode: str, text: str) -> str:
    if mode != "auto":
        return mode
    return "rtl" if text[:1] in RTL_RANGES else "ltr"
'''


def build_app() -> QApplication:
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("Mishkah Note")
    install_bundled_fonts()
    return app


def make_window(theme: str, language: str = "ar") -> MainController:
    settings = Settings(theme=theme, ui_language=language, font_size=13,
                        word_wrap=True, restore_session=False,
                        path=Path("/tmp/mishkah-shot-settings.json"))
    i18n.set_language(language)          # menus are built in this language
    window = MainWindow()
    controller = MainController(window, settings, FileService())
    controller.active_theme = apply_theme(QApplication.instance(), theme)
    for editor in window.editors():
        editor.set_theme_name(controller.active_theme)
    window.resize(WIDTH, HEIGHT)
    return controller


def add_document(controller: MainController, text: str, name: str,
                 path: Path | None = None):
    editor = controller.new_document()
    doc = controller.document_for(editor)
    doc.path = path or Path("/tmp") / name
    editor.load_content(text)
    doc.content = text
    doc.mark_saved(size=len(text.encode("utf-8")))
    editor.set_theme_name(controller.active_theme)
    controller.window.set_tab_title(editor, doc.title, False)
    controller._sync_ui(editor)
    cursor = editor.textCursor()
    cursor.movePosition(cursor.MoveOperation.End)
    editor.setTextCursor(cursor)
    return editor


def grab(widget, name: str) -> Path:
    widget.repaint()
    QApplication.processEvents()
    ratio = max(1, min(SCALE, int(widget.devicePixelRatioF() or 1)))
    image = widget.grab().toImage()
    if ratio > 1 and image.width() < widget.width() * 1.5:
        image = image.scaled(image.width() * ratio, image.height() * ratio,
                             Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)
    target = OUT / name
    image.save(str(target), "PNG")
    print(f"wrote {target.relative_to(ROOT)}  ({image.width()}×{image.height()})")
    return target


def scale_ui(controller: MainController) -> None:
    """Pick the same faces the application resolves on a normal desktop."""
    families = ["Segoe UI Variable Text", "Roboto", "IBM Plex Sans Arabic",
                "DejaVu Sans"]
    font = QFont()
    font.setFamilies(families)
    font.setPointSize(11)
    app = QApplication.instance()
    app.setFont(font)
    controller.window.set_ui_font(font)
    for editor in controller.window.editors():
        editor.set_font(controller.editor_font())
    return None


def shot_light(app: QApplication) -> None:
    controller = make_window("light", "ar")
    scale_ui(controller)
    controller.set_live_markdown(True)
    add_document(controller, ARABIC_NOTE, "خطة.md")
    add_document(controller, CODE_NOTE, "direction.py")
    editor = add_document(controller, ENGLISH_NOTE, "README.md")
    editor.set_language("markdown")
    controller.window.tabs.setCurrentWidget(editor)
    controller._sync_ui(editor)
    window = controller.window
    window.show()
    app.processEvents()
    grab(window, "light.png")


def shot_dark_arabic(app: QApplication) -> None:
    controller = make_window("dark", "ar")
    scale_ui(controller)
    controller.set_live_markdown(True)
    editor = add_document(controller, ARABIC_NOTE, "خطة.md")
    add_document(controller, "ملاحظة سريعة\n", "ملاحظة.txt")
    controller.window.tabs.setCurrentWidget(editor)
    controller._sync_ui(editor)
    window = controller.window
    window.set_tab_color(editor, "yellow")
    window.show()
    app.processEvents()
    grab(window, "dark-arabic.png")


def shot_markdown(app: QApplication) -> None:
    for theme, name, note in (("light", "markdown.png", ARABIC_NOTE),
                              ("dark", "markdown-dark.png", MARKDOWN_NOTE)):
        controller = make_window(theme, "ar")
        scale_ui(controller)
        controller.set_live_markdown(True)
        editor = add_document(controller, note, "README.md")
        controller.window.tabs.setCurrentWidget(editor)
        controller._sync_ui(editor)
        window = controller.window
        window.show()
        app.processEvents()
        grab(window, name)


def shot_tabs(app: QApplication) -> None:
    controller = make_window("light", "en")
    scale_ui(controller)
    first = add_document(controller, "# Ideas\n\n- ship it\n", "ideas.md")
    second = add_document(controller, "shopping\n", "notes.txt")
    third = add_document(controller, "def main():\n    pass\n", "script.py")
    window = controller.window
    window.set_tab_color(first, "yellow")
    window.set_tab_color(second, "green")
    window.set_tab_color(third, "blue")
    controller.set_tab_color(0, "yellow")
    controller.set_tab_color(1, "green")
    controller.set_tab_color(2, "blue")
    controller.toggle_tab_pin(0)
    window.tabs.setCurrentWidget(second)
    controller._sync_ui(second)
    window.show()
    app.processEvents()
    grab(window, "tabs.png")


def shot_settings(app: QApplication) -> None:
    from mishkah.widgets.settings_dialog import SettingsDialog

    controller = make_window("light", "ar")
    scale_ui(controller)
    controller.settings.live_markdown = True
    dialog = SettingsDialog(controller.settings, controller.window)
    dialog.show()
    app.processEvents()
    grab(dialog, "settings.png")
    dialog.close()


def shot_about(app: QApplication) -> None:
    from mishkah.widgets.about_dialog import AboutDialog

    i18n.set_language("ar")
    dialog = AboutDialog()
    dialog.show()
    app.processEvents()
    grab(dialog, "about.png")
    dialog.close()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    app = build_app()
    app.setStyle("Fusion")
    app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
    # QT_SCALE_FACTOR must be set before the QApplication exists; when the
    # caller did not, and no screen is attached (offscreen), paint at 1×.
    shot_light(app)
    shot_dark_arabic(app)
    shot_markdown(app)
    shot_tabs(app)
    shot_settings(app)
    shot_about(app)


if __name__ == "__main__":
    main()
