#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_mufakkira.py — سكريبت بناء شامل لتطبيق "مفكرتي"
تصميم وتطوير: م. بلال فضل

يقوم بالخطوات التالية:
1. تثبيت المكتبات اللازمة (PySide6, charset-normalizer, pytest, pytest-qt).
2. تحميل خط IBM Plex Sans Arabic من الإنترنت.
3. إنشاء هيكل المشروع كاملاً وفق خطة التنفيذ.
4. كتابة جميع ملفات الكود المصدري (الموديلات، الخدمات، الواجهات، المتحكم).
5. كتابة ملفات الاختبار.
6. إنشاء ملفات حزمة .deb وبناء Notepad_Linux_1.0.0.deb.
7. توليد تقرير شامل (build_report.txt).

الاستخدام:
    python3 build_mufakkira.py

المتطلبات المسبقة:
    - Python 3.10+
    - صلاحيات الجذر (sudo) لتثبيت الحزم وبناء .deb
"""

import os
import sys
import shutil
import subprocess
import textwrap
import traceback
from pathlib import Path
from datetime import datetime

# ------------------------------------------------------------
# 1. ثوابت المشروع
# ------------------------------------------------------------
PROJECT_ROOT = Path.cwd() / "mufakkira_build"
SRC_DIR = PROJECT_ROOT / "src" / "mufakkira"
DEB_BUILD_ROOT = PROJECT_ROOT / "deb_build"
FINAL_DEB_NAME = "Notepad_Linux_1.0.0.deb"
REPORT_FILE = PROJECT_ROOT / "build_report.txt"

# معلومات المؤلف
AUTHOR_AR = "م. بلال فضل"
AUTHOR_EN = "Eng. Bilal Fadl"

# روابط تحميل الخط (بترتيب الأولوية)
# قائمة الحزم المطلوبة
PYTHON_PACKAGES = [
    "PySide6>=6.5",
    "charset-normalizer",
    "pytest",
    "pytest-qt",
]
APT_PACKAGES = [
    "python3-pip",
    "dpkg-dev",
    "fakeroot",
    "fontconfig",
]

# ------------------------------------------------------------
# 2. دوال مساعدة
# ------------------------------------------------------------
def log(msg: str, level: str = "INFO", report_lines: list = None):
    line = f"[{level}] {msg}"
    print(line)
    if report_lines is not None:
        report_lines.append(line)


def run_cmd(cmd: list, check: bool = True, report_lines: list = None) -> subprocess.CompletedProcess:
    cmd_str = " ".join(cmd)
    log(f"تشغيل: {cmd_str}", "CMD", report_lines)
    try:
        result = subprocess.run(cmd, check=check, capture_output=True, text=True, timeout=600)
        if result.stdout:
            log(f"stdout: {result.stdout[:500]}...", "OUT", report_lines)
        if result.stderr:
            log(f"stderr: {result.stderr[:500]}...", "ERR", report_lines)
        return result
    except subprocess.CalledProcessError as e:
        log(f"فشل الأمر (رمز {e.returncode}): {e.stderr[:500]}", "ERROR", report_lines)
        raise
    except Exception as e:
        log(f"استثناء أثناء تنفيذ الأمر: {e}", "ERROR", report_lines)
        raise


def write_file(path: Path, content: str, report_lines: list = None):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content), encoding="utf-8")
    log(f"كُتب الملف: {path}", "FILE", report_lines)


def install_python_packages(report_lines: list):
    log("بدء تثبيت حزم Python...", "STEP", report_lines)
    for pkg in PYTHON_PACKAGES:
        try:
            run_cmd([sys.executable, "-m", "pip", "install", pkg], report_lines=report_lines)
        except subprocess.CalledProcessError:
            log(f"فشل تثبيت {pkg}، سنحاول المتابعة.", "WARN", report_lines)


def install_apt_packages(report_lines: list):
    log("بدء تثبيت الحزم النظامية (قد يتطلب sudo)...", "STEP", report_lines)
    missing = []
    if not shutil.which("dpkg-deb"):
        missing.append("dpkg-dev")
    if not shutil.which("fc-cache"):
        missing.append("fontconfig")
    if missing:
        try:
            run_cmd(["sudo", "apt-get", "update"], report_lines=report_lines)
            run_cmd(["sudo", "apt-get", "install", "-y"] + missing, report_lines=report_lines)
        except subprocess.CalledProcessError:
            log("فشل تثبيت الحزم النظامية. قد تحتاج إلى تشغيل السكريبت بصلاحيات sudo.",
                "ERROR", report_lines)
    else:
        log("جميع الحزم النظامية موجودة.", "INFO", report_lines)


def locate_and_copy_font(report_lines: list) -> bool:
    """البحث عن ملف الخط بجانب السكريبت ونسخه إلى هيكل المشروع."""
    log("بدء البحث عن ملف الخط بجانب السكريبت...", "STEP", report_lines)

    font_dir = SRC_DIR / "resources" / "fonts"
    font_dir.mkdir(parents=True, exist_ok=True)
    dest = font_dir / "IBMPlexSansArabic-Light.ttf"

    # المجلدات التي نبحث فيها: مجلد السكريبت + المجلد الحالي
    search_dirs = []
    try:
        script_dir = Path(__file__).resolve().parent
        search_dirs.append(script_dir)
    except NameError:
        pass
    cwd = Path.cwd().resolve()
    if cwd not in search_dirs:
        search_dirs.append(cwd)

    log(f"مجلدات البحث: {', '.join(str(d) for d in search_dirs)}", "INFO", report_lines)

    # 1) البحث بالاسم الدقيق أولاً
    for d in search_dirs:
        candidate = d / "IBMPlexSansArabic-Light.ttf"
        if candidate.exists() and candidate.stat().st_size > 10000:
            shutil.copy(candidate, dest)
            size = dest.stat().st_size
            log(f"✅ وُجد الخط بالاسم الدقيق: {candidate} ({size} بايت)", "SUCCESS", report_lines)
            return True

    # 2) البحث عن أي *.ttf / *.otf صالح بجانب السكريبت
    for d in search_dirs:
        for ext in ("*.ttf", "*.otf", "*.TTF", "*.OTF"):
            for f in sorted(d.glob(ext)):
                if not f.is_file() or f.stat().st_size < 10000:
                    continue
                try:
                    with open(f, "rb") as fh:
                        magic = fh.read(4)
                except Exception:
                    continue
                if magic not in (b"\x00\x01\x00\x00", b"true", b"OTTO", b"ttcf"):
                    continue
                shutil.copy(f, dest)
                log(f"✅ وُجد ملف خط بديل: {f.name} → نُسخ كـ {dest.name}", "SUCCESS", report_lines)
                log("   (إن لم يكن الخط الصحيح، أعد تسميته إلى IBMPlexSansArabic-Light.ttf)",
                    "INFO", report_lines)
                return True

    # لم يوجد أي خط
    log("⚠️ لم يُعثر على أي ملف .ttf/.otf صالح بجانب السكريبت.", "WARN", report_lines)
    log("   ابحث في المجلدات:", "WARN", report_lines)
    for d in search_dirs:
        log(f"     - {d}", "WARN", report_lines)
    log("   ضع ملف الخط بجانب build_mufakkira.py ثم أعد تشغيل السكريبت:", "WARN", report_lines)
    log("     IBMPlexSansArabic-Light.ttf", "WARN", report_lines)
    log("   سيُستخدم خط النظام مؤقتاً — التطبيق سيعمل لكن بمظهر أقل جودة.",
        "WARN", report_lines)
    return False

# ------------------------------------------------------------
# 3. كتابة ملفات المشروع
# ------------------------------------------------------------
def create_project_structure(report_lines: list):
    log("بدء إنشاء هيكل المشروع وكتابة الملفات...", "STEP", report_lines)

    # --- pyproject.toml ---
    write_file(PROJECT_ROOT / "pyproject.toml", f'''
        [build-system]
        requires = ["setuptools>=61.0", "wheel"]
        build-backend = "setuptools.build_meta"

        [project]
        name = "mufakkira"
        version = "1.0.0"
        description = "المفكرة العربية الأولى على لينكس"
        readme = "README.md"
        requires-python = ">=3.10"
        license = {{text = "MIT"}}
        authors = [
            {{name = "{AUTHOR_AR}", email = "bilalfadl@mufakkira.app"}}
        ]
        dependencies = [
            "PySide6>=6.5",
            "charset-normalizer",
        ]

        [project.scripts]
        mufakkira = "mufakkira.app:main"

        [tool.setuptools.packages.find]
        where = ["src"]

        [tool.setuptools.package-data]
        mufakkira = ["resources/fonts/*.ttf", "resources/styles/*.qss", "resources/icons/*"]

        [tool.pytest.ini_options]
        testpaths = ["tests"]
        python_files = ["test_*.py"]
    ''', report_lines)

    # --- README.md ---
    write_file(PROJECT_ROOT / "README.md", f'''
        # مفكرتي — المفكرة العربية الأولى على لينكس

        > **تصميم وتطوير: {AUTHOR_AR}** ({AUTHOR_EN})

        محرر نصوص بسيط مصمم للعربية أولاً، بخط IBM Plex Sans Arabic،
        مع دعم كامل RTL، تبويبات، وضع داكن، وأرقام أسطر.

        ## الميزات
        - دعم كامل للعربية و RTL.
        - تبويبات متعددة.
        - وضع داكن/فاتح.
        - أرقام أسطر.
        - تكبير/تصغير بـ Ctrl+Wheel.
        - تبديل اتجاه الكتابة:
          - `Left Ctrl + Left Shift` → LTR
          - `Right Ctrl + Right Shift` → RTL

        ## التشغيل من المصدر
        ```bash
        python -m mufakkira
        ```

        ## الاختبارات
        ```bash
        pytest tests/ -v
        ```

        ## بناء الحزمة
        ```bash
        python3 build_mufakkira.py
        sudo dpkg -i Notepad_Linux_1.0.0.deb
        sudo apt install -f
        ```

        ## الترخيص
        MIT — © 2025 {AUTHOR_AR}
    ''', report_lines)

    # --- LICENSE ---
    write_file(PROJECT_ROOT / "LICENSE", f'''
        MIT License

        Copyright (c) 2025 {AUTHOR_AR} ({AUTHOR_EN})

        Permission is hereby granted, free of charge, to any person obtaining a copy
        of this software and associated documentation files (the "Software"), to deal
        in the Software without restriction, including without limitation the rights
        to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
        copies of the Software, and to permit persons to whom the Software is
        furnished to do so, subject to the following conditions:

        The above copyright notice and this permission notice shall be included in all
        copies or substantial portions of the Software.

        THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
        IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
        FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
        AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
        LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
        OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
        SOFTWARE.
    ''', report_lines)

    # --- .gitignore ---
    write_file(PROJECT_ROOT / ".gitignore", '''
        __pycache__/
        *.py[cod]
        *.egg-info/
        build/
        dist/
        *.deb
        .pytest_cache/
        deb_build/
        mufakkira_build/
    ''', report_lines)

    # --- src/mufakkira/__init__.py ---
    write_file(SRC_DIR / "__init__.py", f'''
        __version__ = "1.0.0"
        __author__ = "{AUTHOR_AR}"
        __author_en__ = "{AUTHOR_EN}"
        __description__ = "المفكرة العربية الأولى على لينكس"
    ''', report_lines)

    # --- src/mufakkira/__main__.py ---
    write_file(SRC_DIR / "__main__.py", '''
        from mufakkira.app import main
        import sys

        if __name__ == "__main__":
            sys.exit(main())
    ''', report_lines)

    # --- src/mufakkira/app.py ---
    write_file(SRC_DIR / "app.py", f'''
        import sys
        import logging
        from pathlib import Path

        from PySide6.QtWidgets import QApplication
        from PySide6.QtGui import QFont, QFontDatabase
        from PySide6.QtCore import Qt

        from mufakkira.services.file_service import FileService
        from mufakkira.services.session_service import SessionService
        from mufakkira.views.main_window import MainWindow
        from mufakkira.controllers.main_controller import MainController

        logging.basicConfig(level=logging.INFO)
        logger = logging.getLogger(__name__)

        def _load_font(resources_dir: Path) -> str:
            font_path = resources_dir / "fonts" / "IBMPlexSansArabic-Light.ttf"
            if not font_path.exists():
                logger.warning("ملف الخط غير موجود: %s — سيُستخدم خط النظام", font_path)
                return "Sans"
            font_id = QFontDatabase.addApplicationFont(str(font_path))
            if font_id < 0:
                logger.warning("فشل تحميل الخط: %s", font_path)
                return "Sans"
            families = QFontDatabase.applicationFontFamilies(font_id)
            if not families:
                return "Sans"
            logger.info("تم تحميل الخط: %s", families[0])
            return families[0]

        def _detect_theme() -> str:
            try:
                from PySide6.QtGui import QGuiApplication
                hints = QGuiApplication.styleHints()
                if hasattr(hints, "colorScheme"):
                    scheme = hints.colorScheme()
                    if scheme == Qt.ColorScheme.Dark:
                        return "dark"
            except Exception:
                pass
            return "light"

        def _apply_theme(app: QApplication, theme: str):
            resources = Path(__file__).parent / "resources" / "styles"
            qss_file = resources / f"{{theme}}.qss"
            if qss_file.exists():
                app.setStyleSheet(qss_file.read_text(encoding="utf-8"))

        def main() -> int:
            app = QApplication(sys.argv)
            app.setApplicationName("مفكرتي")
            app.setApplicationDisplayName("مفكرتي — م. بلال فضل")
            app.setOrganizationName("Mufakkira")
            app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

            resources_dir = Path(__file__).parent / "resources"
            font_family = _load_font(resources_dir)
            app_font = QFont(font_family, 12)
            app_font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
            app.setFont(app_font)

            theme = _detect_theme()
            _apply_theme(app, theme)

            file_service = FileService()
            session = SessionService()
            window = MainWindow()
            controller = MainController(window, file_service, session)

            controller.restore_session()
            if window.tab_count() == 0:
                controller.new_document()

            window.show()
            return app.exec()

        if __name__ == "__main__":
            sys.exit(main())
    ''', report_lines)

    # --- models/document.py ---
    write_file(SRC_DIR / "models" / "__init__.py", "", report_lines)
    write_file(SRC_DIR / "models" / "document.py", '''
        from dataclasses import dataclass
        from pathlib import Path
        from typing import Optional

        @dataclass
        class DocumentModel:
            path: Optional[Path] = None
            content: str = ""
            encoding: str = "utf-8"
            line_ending: str = "\\n"
            is_modified: bool = False
            cursor_position: int = 0
            scroll_position: int = 0

            @property
            def title(self) -> str:
                return self.path.name if self.path else "بدون عنوان"

            @property
            def display_title(self) -> str:
                suffix = " •" if self.is_modified else ""
                return f"{self.title}{suffix}"

            def mark_modified(self) -> None:
                self.is_modified = True

            def mark_saved(self) -> None:
                self.is_modified = False
    ''', report_lines)

    # --- services/file_service.py ---
    write_file(SRC_DIR / "services" / "__init__.py", "", report_lines)
    write_file(SRC_DIR / "services" / "file_service.py", '''
        import os
        import logging
        from pathlib import Path
        from typing import Optional, Tuple

        from PySide6.QtCore import QObject, Signal, QThread
        from charset_normalizer import from_bytes

        from mufakkira.models.document import DocumentModel

        logger = logging.getLogger(__name__)

        class _LoadWorker(QThread):
            finished = Signal(object)
            error = Signal(str, str)

            def __init__(self, path: Path):
                super().__init__()
                self.path = path

            def run(self):
                try:
                    content, encoding, line_ending = FileService._read_file(self.path)
                    doc = DocumentModel(path=self.path, content=content,
                                        encoding=encoding, line_ending=line_ending)
                    self.finished.emit(doc)
                except Exception as e:
                    self.error.emit("خطأ في القراءة", str(e))

        class _SaveWorker(QThread):
            finished = Signal(object)
            error = Signal(str, str)

            def __init__(self, doc: DocumentModel):
                super().__init__()
                self.doc = doc

            def run(self):
                try:
                    FileService._write_file(self.doc.path, self.doc.content,
                                            self.doc.encoding, self.doc.line_ending)
                    self.finished.emit(self.doc)
                except Exception as e:
                    self.error.emit("خطأ في الحفظ", str(e))

        class FileService(QObject):
            file_loaded = Signal(object)
            file_saved = Signal(object)
            error_occurred = Signal(str, str)

            def __init__(self, parent=None):
                super().__init__(parent)
                self._load_worker: Optional[_LoadWorker] = None
                self._save_worker: Optional[_SaveWorker] = None

            def load_async(self, path: Path) -> None:
                self._load_worker = _LoadWorker(path)
                self._load_worker.finished.connect(self.file_loaded)
                self._load_worker.error.connect(self.error_occurred)
                self._load_worker.start()

            def save_async(self, doc: DocumentModel) -> None:
                self._save_worker = _SaveWorker(doc)
                self._save_worker.finished.connect(self.file_saved)
                self._save_worker.error.connect(self.error_occurred)
                self._save_worker.start()

            @staticmethod
            def _detect_encoding(raw: bytes) -> str:
                if raw.startswith(b"\\xef\\xbb\\xbf"):
                    return "utf-8-sig"
                try:
                    raw.decode("utf-8")
                    return "utf-8"
                except UnicodeDecodeError:
                    pass
                best = from_bytes(raw).best()
                if best and best.encoding:
                    return best.encoding
                return "windows-1256"

            @staticmethod
            def _detect_line_ending(text: str) -> str:
                crlf = text.count("\\r\\n")
                lf = text.count("\\n") - crlf
                return "\\r\\n" if crlf > lf else "\\n"

            @staticmethod
            def _read_file(path: Path) -> Tuple[str, str, str]:
                raw = path.read_bytes()
                encoding = FileService._detect_encoding(raw)
                content = raw.decode(encoding)
                line_ending = FileService._detect_line_ending(content)
                content = content.replace("\\r\\n", "\\n").replace("\\r", "\\n")
                return content, encoding, line_ending

            @staticmethod
            def _write_file(path: Path, content: str, encoding: str, line_ending: str) -> None:
                if line_ending == "\\r\\n":
                    content = content.replace("\\n", "\\r\\n")
                tmp_path = path.with_suffix(path.suffix + ".tmp")
                try:
                    with open(tmp_path, "w", encoding=encoding, newline="") as f:
                        f.write(content)
                        f.flush()
                        os.fsync(f.fileno())
                    os.replace(tmp_path, path)
                except Exception:
                    if tmp_path.exists():
                        tmp_path.unlink()
                    raise
    ''', report_lines)

    # --- services/session_service.py ---
    write_file(SRC_DIR / "services" / "session_service.py", '''
        from typing import List
        from dataclasses import dataclass, field

        from PySide6.QtCore import QSettings
        from mufakkira.models.document import DocumentModel

        @dataclass
        class SessionState:
            paths: List[str] = field(default_factory=list)
            cursor_positions: List[int] = field(default_factory=list)
            scroll_positions: List[int] = field(default_factory=list)
            geometry: bytes = b""
            theme: str = "light"
            font_size: int = 12
            active_index: int = 0

        class SessionService:
            ORG = "Mufakkira"
            APP = "Notepad"

            def __init__(self):
                self._settings = QSettings(self.ORG, self.APP)

            def save(self, docs: List[DocumentModel], geometry: bytes,
                     theme: str, font_size: int, active_index: int) -> None:
                self._settings.clear()
                paths = [str(d.path) for d in docs if d.path]
                self._settings.setValue("session/paths", paths)
                self._settings.setValue("session/cursors", [d.cursor_position for d in docs if d.path])
                self._settings.setValue("session/scrolling", [d.scroll_position for d in docs if d.path])
                self._settings.setValue("window/geometry", geometry)
                self._settings.setValue("app/theme", theme)
                self._settings.setValue("app/font_size", font_size)
                self._settings.setValue("session/active_index", active_index)

            def load(self) -> SessionState:
                state = SessionState()
                state.paths = self._settings.value("session/paths", [], type=list)
                state.cursor_positions = self._settings.value("session/cursors", [], type=list)
                state.scroll_positions = self._settings.value("session/scrolling", [], type=list)
                state.geometry = self._settings.value("window/geometry", b"", type=bytes)
                state.theme = self._settings.value("app/theme", "light", type=str)
                state.font_size = self._settings.value("app/font_size", 12, type=int)
                state.active_index = self._settings.value("session/active_index", 0, type=int)
                return state

            def clear(self) -> None:
                self._settings.clear()
    ''', report_lines)

    # --- widgets/line_number_area.py ---
    write_file(SRC_DIR / "widgets" / "__init__.py", "", report_lines)
    write_file(SRC_DIR / "widgets" / "line_number_area.py", '''
        from PySide6.QtWidgets import QWidget
        from PySide6.QtCore import QSize

        class LineNumberArea(QWidget):
            def __init__(self, editor):
                super().__init__(editor)
                self._editor = editor

            def sizeHint(self) -> QSize:
                return QSize(self._editor.line_number_area_width(), 0)

            def paintEvent(self, event):
                self._editor.line_number_area_paint_event(event)
    ''', report_lines)

    # --- widgets/find_dialog.py ---
    write_file(SRC_DIR / "widgets" / "find_dialog.py", '''
        from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout,
                                       QLineEdit, QPushButton, QLabel)
        from PySide6.QtCore import Qt

        class FindDialog(QDialog):
            def __init__(self, editor, parent=None):
                super().__init__(parent)
                self._editor = editor
                self.setWindowTitle("بحث")
                self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
                self.setMinimumWidth(360)

                layout = QVBoxLayout(self)
                row = QHBoxLayout()
                row.addWidget(QLabel("بحث:"))
                self._input = QLineEdit()
                row.addWidget(self._input)
                layout.addLayout(row)

                btn_row = QHBoxLayout()
                self._find_btn = QPushButton("بحث")
                self._close_btn = QPushButton("إغلاق")
                btn_row.addWidget(self._find_btn)
                btn_row.addWidget(self._close_btn)
                layout.addLayout(btn_row)

                self._find_btn.clicked.connect(self._find)
                self._close_btn.clicked.connect(self.close)

            def _find(self):
                text = self._input.text()
                if not text:
                    return
                if not self._editor.find(text):
                    cursor = self._editor.textCursor()
                    cursor.movePosition(cursor.MoveOperation.Start)
                    self._editor.setTextCursor(cursor)
                    self._editor.find(text)
    ''', report_lines)

    # --- views/editor_view.py (مع خاصية تبديل الاتجاه) ---
    write_file(SRC_DIR / "views" / "__init__.py", "", report_lines)
    write_file(SRC_DIR / "views" / "editor_view.py", '''
        from PySide6.QtWidgets import QPlainTextEdit
        from PySide6.QtCore import Qt, Signal, QRect
        from PySide6.QtGui import QFont, QPainter, QColor

        from mufakkira.models.document import DocumentModel
        from mufakkira.widgets.line_number_area import LineNumberArea


        # رموز المفاتيح (X11 keycodes = evdev + 8)
        # ندعم كلا المجموعتين (X11 و evdev) للعمل على X11 و Wayland
        LEFT_SHIFT_CODES = {50, 42}
        RIGHT_SHIFT_CODES = {62, 54}
        LEFT_CTRL_CODES = {37, 29}
        RIGHT_CTRL_CODES = {105, 97}


        class EditorView(QPlainTextEdit):
            cursor_info_changed = Signal(int, int)
            zoom_changed = Signal(int)
            modified_changed = Signal(bool)
            direction_changed = Signal(str)  # "RTL" أو "LTR"

            def __init__(self, document: DocumentModel, font: QFont, parent=None):
                super().__init__(parent)
                self._doc = document
                self._base_font_size = font.pointSize()
                self.setFont(font)
                self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
                self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
                self.document().setModified(False)

                # تتبع المفاتيح للتحكم في اتجاه الكتابة
                self._left_shift = False
                self._right_shift = False
                self._left_ctrl = False
                self._right_ctrl = False
                self._left_pair_active = False
                self._right_pair_active = False
                self._other_key_pressed = False

                self._line_number_area = LineNumberArea(self)
                self.blockCountChanged.connect(self._update_line_number_area_width)
                self.updateRequest.connect(self._update_line_number_area)
                self.cursorPositionChanged.connect(self._on_cursor_moved)
                self.document().modificationChanged.connect(self.modified_changed)
                self._update_line_number_area_width(0)

            # --- إدارة المستند ---
            def load_document(self) -> None:
                self.setPlainText(self._doc.content)
                self.document().setModified(False)

            def line_number_area_width(self) -> int:
                digits = 1
                max_val = max(1, self.blockCount())
                while max_val >= 10:
                    max_val //= 10
                    digits += 1
                return 10 + self.fontMetrics().horizontalAdvance("9") * digits

            def _update_line_number_area_width(self, _):
                self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

            def _update_line_number_area(self, rect: QRect, dy: int):
                if dy:
                    self._line_number_area.scroll(0, dy)
                else:
                    self._line_number_area.update(0, rect.y(),
                                                  self._line_number_area.width(), rect.height())
                if rect.contains(self.viewport().rect()):
                    self._update_line_number_area_width(0)

            def resizeEvent(self, event):
                super().resizeEvent(event)
                cr = self.contentsRect()
                self._line_number_area.setGeometry(
                    QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height())
                )

            def line_number_area_paint_event(self, event):
                painter = QPainter(self._line_number_area)
                painter.fillRect(event.rect(), QColor("#f0f0f0"))
                block = self.firstVisibleBlock()
                block_number = block.blockNumber()
                top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
                bottom = top + self.blockBoundingRect(block).height()
                while block.isValid() and top <= event.rect().bottom():
                    if block.isVisible() and bottom >= event.rect().top():
                        painter.setPen(QColor("#808080"))
                        painter.drawText(
                            0, int(top),
                            self._line_number_area.width() - 5,
                            self.fontMetrics().height(),
                            Qt.AlignmentFlag.AlignRight, str(block_number + 1)
                        )
                    block = block.next()
                    top = bottom
                    bottom = top + self.blockBoundingRect(block).height()
                    block_number += 1

            def _on_cursor_moved(self):
                cursor = self.textCursor()
                line = cursor.blockNumber() + 1
                col = cursor.columnNumber() + 1
                self.cursor_info_changed.emit(line, col)

            # --- التحكم في الاتجاه عبر لوحة المفاتيح ---
            def _set_direction(self, direction: Qt.LayoutDirection, label: str):
                if self.layoutDirection() != direction:
                    self.setLayoutDirection(direction)
                    self.direction_changed.emit(label)

            def keyPressEvent(self, event):
                sc = event.nativeScanCode()
                if sc in LEFT_SHIFT_CODES:
                    self._left_shift = True
                    if self._left_ctrl:
                        self._left_pair_active = True
                        self._other_key_pressed = False
                elif sc in RIGHT_SHIFT_CODES:
                    self._right_shift = True
                    if self._right_ctrl:
                        self._right_pair_active = True
                        self._other_key_pressed = False
                elif sc in LEFT_CTRL_CODES:
                    self._left_ctrl = True
                    if self._left_shift:
                        self._left_pair_active = True
                        self._other_key_pressed = False
                elif sc in RIGHT_CTRL_CODES:
                    self._right_ctrl = True
                    if self._right_shift:
                        self._right_pair_active = True
                        self._other_key_pressed = False
                else:
                    if self._left_pair_active or self._right_pair_active:
                        self._other_key_pressed = True
                super().keyPressEvent(event)

            def keyReleaseEvent(self, event):
                sc = event.nativeScanCode()

                if sc in LEFT_SHIFT_CODES:
                    self._left_shift = False
                    if self._left_pair_active and not self._left_ctrl and not self._other_key_pressed:
                        self._set_direction(Qt.LayoutDirection.LeftToRight, "LTR")
                    if not (self._left_ctrl or self._left_shift):
                        self._left_pair_active = False
                        self._other_key_pressed = False

                elif sc in RIGHT_SHIFT_CODES:
                    self._right_shift = False
                    if self._right_pair_active and not self._right_ctrl and not self._other_key_pressed:
                        self._set_direction(Qt.LayoutDirection.RightToLeft, "RTL")
                    if not (self._right_ctrl or self._right_shift):
                        self._right_pair_active = False
                        self._other_key_pressed = False

                elif sc in LEFT_CTRL_CODES:
                    self._left_ctrl = False
                    if self._left_pair_active and not self._left_shift and not self._other_key_pressed:
                        self._set_direction(Qt.LayoutDirection.LeftToRight, "LTR")
                    if not (self._left_ctrl or self._left_shift):
                        self._left_pair_active = False
                        self._other_key_pressed = False

                elif sc in RIGHT_CTRL_CODES:
                    self._right_ctrl = False
                    if self._right_pair_active and not self._right_shift and not self._other_key_pressed:
                        self._set_direction(Qt.LayoutDirection.RightToLeft, "RTL")
                    if not (self._right_ctrl or self._right_shift):
                        self._right_pair_active = False
                        self._other_key_pressed = False

                super().keyReleaseEvent(event)

            # --- API عامة ---
            def set_layout_direction(self, direction: Qt.LayoutDirection):
                label = "RTL" if direction == Qt.LayoutDirection.RightToLeft else "LTR"
                self._set_direction(direction, label)

            def set_font_size(self, size: int):
                size = max(8, min(72, size))
                font = self.font()
                font.setPointSize(size)
                self.setFont(font)
                self._update_line_number_area_width(0)
                percent = int(round(size / self._base_font_size * 100))
                self.zoom_changed.emit(percent)

            def wheelEvent(self, event):
                if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                    delta = event.angleDelta().y()
                    if delta > 0:
                        self.set_font_size(self.font().pointSize() + 1)
                    elif delta < 0:
                        self.set_font_size(self.font().pointSize() - 1)
                    event.accept()
                else:
                    super().wheelEvent(event)

            def toggle_line_numbers(self, visible: bool):
                self._line_number_area.setVisible(visible)
                self.setViewportMargins(self.line_number_area_width() if visible else 0, 0, 0, 0)

            def apply_theme(self, theme: str):
                pass
    ''', report_lines)

    # --- views/status_bar_widget.py (مع مؤشر الاتجاه) ---
    write_file(SRC_DIR / "views" / "status_bar_widget.py", '''
        from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel

        class StatusBarWidget(QWidget):
            def __init__(self, parent=None):
                super().__init__(parent)
                layout = QHBoxLayout(self)
                layout.setContentsMargins(5, 0, 5, 0)
                self._line_col = QLabel("السطر: 1، العمود: 1")
                self._encoding = QLabel("الترميز: UTF-8")
                self._line_ending = QLabel("نهاية السطر: LF")
                self._zoom = QLabel("التكبير: 100%")
                self._direction = QLabel("الاتجاه: RTL")
                for w in (self._line_col, self._encoding, self._line_ending,
                          self._zoom, self._direction):
                    layout.addWidget(w)
                layout.addStretch()

            def update_cursor(self, line: int, col: int):
                self._line_col.setText(f"السطر: {line}، العمود: {col}")

            def update_encoding(self, enc: str):
                self._encoding.setText(f"الترميز: {enc.upper()}")

            def update_line_ending(self, le: str):
                label = "CRLF" if le == "\\r\\n" else "LF"
                self._line_ending.setText(f"نهاية السطر: {label}")

            def update_zoom(self, percent: int):
                self._zoom.setText(f"التكبير: {percent}%")

            def update_direction(self, direction: str):
                self._direction.setText(f"الاتجاه: {direction}")
    ''', report_lines)

    # --- views/main_window.py ---
    write_file(SRC_DIR / "views" / "main_window.py", '''
        from PySide6.QtWidgets import QMainWindow, QTabWidget
        from PySide6.QtGui import QAction, QKeySequence
        from PySide6.QtCore import Qt, Signal

        from mufakkira.views.editor_view import EditorView
        from mufakkira.views.status_bar_widget import StatusBarWidget


        class MainWindow(QMainWindow):
            new_requested = Signal()
            open_requested = Signal()
            save_requested = Signal()
            save_as_requested = Signal()
            close_tab_requested = Signal(int)
            find_requested = Signal()
            zoom_in_requested = Signal()
            zoom_out_requested = Signal()
            zoom_reset_requested = Signal()
            toggle_line_numbers_requested = Signal(bool)
            toggle_dark_mode_requested = Signal(bool)
            toggle_status_bar_requested = Signal(bool)
            set_rtl_requested = Signal()
            set_ltr_requested = Signal()
            about_requested = Signal()

            def __init__(self):
                super().__init__()
                self.setWindowTitle("مفكرتي — م. بلال فضل")
                self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
                self.resize(1000, 700)

                self._tab_widget = QTabWidget()
                self._tab_widget.setTabsClosable(True)
                self._tab_widget.setMovable(True)
                self._tab_widget.tabCloseRequested.connect(self.close_tab_requested)
                self.setCentralWidget(self._tab_widget)

                self._status_widget = StatusBarWidget()
                self.statusBar().addPermanentWidget(self._status_widget)

                self._create_menus()

            def _create_menus(self):
                menubar = self.menuBar()

                file_menu = menubar.addMenu("ملف")
                self._add_action(file_menu, "جديد", "Ctrl+N", self.new_requested)
                self._add_action(file_menu, "فتح", "Ctrl+O", self.open_requested)
                self._add_action(file_menu, "حفظ", "Ctrl+S", self.save_requested)
                self._add_action(file_menu, "حفظ باسم", "Ctrl+Shift+S", self.save_as_requested)
                self._add_action(file_menu, "إغلاق التبويب", "Ctrl+W",
                                 lambda: self.close_tab_requested.emit(self._tab_widget.currentIndex()))
                file_menu.addSeparator()
                self._add_action(file_menu, "خروج", "Ctrl+Q", self.close)

                edit_menu = menubar.addMenu("تحرير")
                self._add_action(edit_menu, "تراجع", "Ctrl+Z", lambda: self._call_editor("undo"))
                self._add_action(edit_menu, "إعادة", "Ctrl+Y", lambda: self._call_editor("redo"))
                edit_menu.addSeparator()
                self._add_action(edit_menu, "قص", "Ctrl+X", lambda: self._call_editor("cut"))
                self._add_action(edit_menu, "نسخ", "Ctrl+C", lambda: self._call_editor("copy"))
                self._add_action(edit_menu, "لصق", "Ctrl+V", lambda: self._call_editor("paste"))
                self._add_action(edit_menu, "تحديد الكل", "Ctrl+A", lambda: self._call_editor("selectAll"))
                edit_menu.addSeparator()
                self._add_action(edit_menu, "بحث", "Ctrl+F", self.find_requested)

                view_menu = menubar.addMenu("عرض")
                self._add_action(view_menu, "تكبير", "Ctrl++", self.zoom_in_requested)
                self._add_action(view_menu, "تصغير", "Ctrl+-", self.zoom_out_requested)
                self._add_action(view_menu, "الحجم الافتراضي", "Ctrl+0", self.zoom_reset_requested)
                view_menu.addSeparator()
                self._add_checkable_action(view_menu, "أرقام الأسطر", True,
                                           self.toggle_line_numbers_requested)
                self._add_checkable_action(view_menu, "الوضع الداكن", False,
                                           self.toggle_dark_mode_requested)
                self._add_checkable_action(view_menu, "شريط الحالة", True,
                                           self.toggle_status_bar_requested)
                view_menu.addSeparator()

                # قائمة فرعية لاتجاه النص
                dir_menu = view_menu.addMenu("اتجاه النص")
                self._add_action(dir_menu, "من اليمين إلى اليسار (RTL)  —  RightCtrl+RightShift",
                                 None, self.set_rtl_requested)
                self._add_action(dir_menu, "من اليسار إلى اليمين (LTR)  —  LeftCtrl+LeftShift",
                                 None, self.set_ltr_requested)

                help_menu = menubar.addMenu("مساعدة")
                self._add_action(help_menu, "حول", None, self.about_requested)

            def _add_action(self, menu, text, shortcut, signal):
                action = QAction(text, self)
                if shortcut:
                    action.setShortcut(QKeySequence(shortcut))
                action.triggered.connect(signal)
                menu.addAction(action)
                return action

            def _add_checkable_action(self, menu, text, checked, signal):
                action = QAction(text, self)
                action.setCheckable(True)
                action.setChecked(checked)
                action.toggled.connect(signal)
                menu.addAction(action)
                return action

            def _call_editor(self, method: str):
                editor = self.current_editor()
                if editor:
                    getattr(editor, method)()

            def add_tab(self, editor: EditorView, title: str):
                index = self._tab_widget.addTab(editor, title)
                self._tab_widget.setCurrentIndex(index)
                editor.cursor_info_changed.connect(self._status_widget.update_cursor)
                editor.zoom_changed.connect(self._status_widget.update_zoom)
                editor.direction_changed.connect(self._status_widget.update_direction)
                return index

            def current_editor(self):
                return self._tab_widget.currentWidget()

            def tab_count(self) -> int:
                return self._tab_widget.count()

            def remove_tab(self, index: int):
                self._tab_widget.removeTab(index)

            def set_tab_title(self, index: int, title: str):
                self._tab_widget.setTabText(index, title)

            def set_current_index(self, index: int):
                self._tab_widget.setCurrentIndex(index)

            def current_index(self) -> int:
                return self._tab_widget.currentIndex()

            def status_widget(self) -> StatusBarWidget:
                return self._status_widget

            def tab_widget(self) -> QTabWidget:
                return self._tab_widget
    ''', report_lines)

    # --- controllers/main_controller.py ---
    write_file(SRC_DIR / "controllers" / "__init__.py", "", report_lines)
    write_file(SRC_DIR / "controllers" / "main_controller.py", f'''
        from pathlib import Path
        from typing import Optional, List

        from PySide6.QtWidgets import QFileDialog, QMessageBox
        from PySide6.QtCore import QObject, Qt

        from mufakkira.models.document import DocumentModel
        from mufakkira.services.file_service import FileService
        from mufakkira.services.session_service import SessionService
        from mufakkira.views.main_window import MainWindow
        from mufakkira.views.editor_view import EditorView
        from mufakkira.widgets.find_dialog import FindDialog


        AUTHOR_AR = "{AUTHOR_AR}"
        AUTHOR_EN = "{AUTHOR_EN}"


        class MainController(QObject):
            def __init__(self, window: MainWindow, file_service: FileService,
                         session: SessionService):
                super().__init__()
                self._window = window
                self._file_service = file_service
                self._session = session
                self._docs: List[DocumentModel] = []
                self._connect_signals()

            def _connect_signals(self):
                w = self._window
                w.new_requested.connect(self.new_document)
                w.open_requested.connect(lambda: self.open_document(None))
                w.save_requested.connect(self.save_current)
                w.save_as_requested.connect(self.save_current_as)
                w.close_tab_requested.connect(self.close_tab)
                w.find_requested.connect(self._show_find_dialog)
                w.zoom_in_requested.connect(self._zoom_in)
                w.zoom_out_requested.connect(self._zoom_out)
                w.zoom_reset_requested.connect(self._zoom_reset)
                w.toggle_line_numbers_requested.connect(self._toggle_line_numbers)
                w.toggle_dark_mode_requested.connect(self._toggle_dark_mode)
                w.toggle_status_bar_requested.connect(self._toggle_status_bar)
                w.set_rtl_requested.connect(lambda: self._set_direction(Qt.LayoutDirection.RightToLeft))
                w.set_ltr_requested.connect(lambda: self._set_direction(Qt.LayoutDirection.LeftToRight))
                w.about_requested.connect(self._show_about)
                self._file_service.file_loaded.connect(self._on_file_loaded)
                self._file_service.file_saved.connect(self._on_file_saved)
                self._file_service.error_occurred.connect(self._on_error)
                self._window.tab_widget().currentChanged.connect(self._on_tab_changed)

            # --- إدارة المستندات ---
            def new_document(self):
                doc = DocumentModel()
                self._docs.append(doc)
                editor = EditorView(doc, self._window.font())
                index = self._window.add_tab(editor, doc.display_title)
                editor.modified_changed.connect(lambda m, d=doc, i=index: self._on_modified(d, i))
                editor.cursor_info_changed.connect(
                    lambda l, c, d=doc: self._update_status(d, l, c)
                )
                self._update_status(doc, 1, 1)
                return doc

            def open_document(self, path: Optional[Path] = None):
                if path is None:
                    file_str, _ = QFileDialog.getOpenFileName(
                        self._window, "فتح ملف", "", "نصوص (*.txt);;كل الملفات (*)"
                    )
                    if not file_str:
                        return
                    path = Path(file_str)
                self._file_service.load_async(path)

            def _on_file_loaded(self, doc: DocumentModel):
                for existing in self._docs:
                    if existing.path == doc.path:
                        idx = self._docs.index(existing)
                        self._window.set_current_index(idx)
                        return
                self._docs.append(doc)
                editor = EditorView(doc, self._window.font())
                index = self._window.add_tab(editor, doc.display_title)
                editor.load_document()
                editor.modified_changed.connect(lambda m, d=doc, i=index: self._on_modified(d, i))
                editor.cursor_info_changed.connect(
                    lambda l, c, d=doc: self._update_status(d, l, c)
                )
                self._update_status(doc, 1, 1)

            def save_current(self) -> bool:
                doc = self._current_doc()
                if not doc:
                    return False
                if not doc.path:
                    return self.save_current_as()
                self._save_doc(doc)
                return True

            def save_current_as(self) -> bool:
                doc = self._current_doc()
                if not doc:
                    return False
                file_str, _ = QFileDialog.getSaveFileName(
                    self._window, "حفظ باسم", "", "نصوص (*.txt);;كل الملفات (*)"
                )
                if not file_str:
                    return False
                doc.path = Path(file_str)
                self._save_doc(doc)
                return True

            def _save_doc(self, doc: DocumentModel):
                doc.content = self._editor_for(doc).toPlainText()
                self._file_service.save_async(doc)

            def _on_file_saved(self, doc: DocumentModel):
                doc.mark_saved()
                idx = self._docs.index(doc)
                self._window.set_tab_title(idx, doc.display_title)

            def close_tab(self, index: int) -> bool:
                if index < 0 or index >= len(self._docs):
                    return False
                doc = self._docs[index]
                if doc.is_modified:
                    reply = QMessageBox.question(
                        self._window, "حفظ التغييرات؟",
                        f"هل تريد حفظ التغييرات في '{{doc.title}}'؟",
                        QMessageBox.StandardButton.Save |
                        QMessageBox.StandardButton.Discard |
                        QMessageBox.StandardButton.Cancel
                    )
                    if reply == QMessageBox.StandardButton.Save:
                        self._window.set_current_index(index)
                        if not self.save_current():
                            return False
                    elif reply == QMessageBox.StandardButton.Cancel:
                        return False
                self._docs.pop(index)
                self._window.remove_tab(index)
                return True

            def on_close(self) -> bool:
                for i in range(len(self._docs) - 1, -1, -1):
                    if not self.close_tab(i):
                        return False
                self._save_session()
                return True

            # --- الجلسة ---
            def restore_session(self):
                state = self._session.load()
                for path_str in state.paths:
                    path = Path(path_str)
                    if path.exists():
                        self._file_service.load_async(path)
                if state.geometry:
                    self._window.restoreGeometry(state.geometry)
                self._window.status_widget().update_encoding("utf-8")
                self._window.status_widget().update_line_ending("\\n")
                self._window.status_widget().update_direction("RTL")

            def _save_session(self):
                geometry = self._window.saveGeometry()
                theme = "dark" if self._window.styleSheet() else "light"
                font_size = self._window.font().pointSize()
                self._session.save(self._docs, geometry, theme, font_size,
                                   self._window.current_index())

            # --- أدوات مساعدة ---
            def _current_doc(self) -> Optional[DocumentModel]:
                idx = self._window.current_index()
                if 0 <= idx < len(self._docs):
                    return self._docs[idx]
                return None

            def _editor_for(self, doc: DocumentModel) -> Optional[EditorView]:
                idx = self._docs.index(doc) if doc in self._docs else -1
                if idx >= 0:
                    return self._window.tab_widget().widget(idx)
                return None

            def _on_modified(self, doc: DocumentModel, index: int):
                doc.mark_modified()
                self._window.set_tab_title(index, doc.display_title)

            def _update_status(self, doc: DocumentModel, line: int, col: int):
                sw = self._window.status_widget()
                sw.update_cursor(line, col)
                sw.update_encoding(doc.encoding)
                sw.update_line_ending(doc.line_ending)

            def _on_tab_changed(self, index: int):
                if 0 <= index < len(self._docs):
                    doc = self._docs[index]
                    self._update_status(doc, 1, 1)

            # --- الاتجاه ---
            def _set_direction(self, direction: Qt.LayoutDirection):
                editor = self._window.current_editor()
                if editor:
                    editor.set_layout_direction(direction)
                    label = "RTL" if direction == Qt.LayoutDirection.RightToLeft else "LTR"
                    self._window.status_widget().update_direction(label)

            # --- الحوارات والأوامر ---
            def _show_find_dialog(self):
                editor = self._window.current_editor()
                if editor:
                    dlg = FindDialog(editor, self._window)
                    dlg.show()

            def _zoom_in(self):
                e = self._window.current_editor()
                if e:
                    e.set_font_size(e.font().pointSize() + 1)

            def _zoom_out(self):
                e = self._window.current_editor()
                if e:
                    e.set_font_size(e.font().pointSize() - 1)

            def _zoom_reset(self):
                e = self._window.current_editor()
                if e:
                    e.set_font_size(12)

            def _toggle_line_numbers(self, checked: bool):
                e = self._window.current_editor()
                if e:
                    e.toggle_line_numbers(checked)

            def _toggle_dark_mode(self, checked: bool):
                resources = Path(__file__).parent.parent / "resources" / "styles"
                theme = "dark" if checked else "light"
                qss_file = resources / f"{{theme}}.qss"
                if qss_file.exists():
                    self._window.setStyleSheet(qss_file.read_text(encoding="utf-8"))

            def _toggle_status_bar(self, checked: bool):
                self._window.statusBar().setVisible(checked)

            def _show_about(self):
                QMessageBox.about(
                    self._window, "حول مفكرتي",
                    "<h2>مفكرتي 1.0.0</h2>"
                    "<p>المفكرة العربية الأولى على لينكس.</p>"
                    "<p>مصممة للعربية أولاً بخط IBM Plex Sans Arabic.</p>"
                    f"<hr><p><b>تصميم وتطوير:</b> {AUTHOR_AR} ({AUTHOR_EN})</p>"
                    "<p><b>اختصارات تبديل الاتجاه:</b><br>"
                    "• Left Ctrl + Left Shift ← LTR<br>"
                    "• Right Ctrl + Right Shift ← RTL</p>"
                    "<p>الترخيص: MIT</p>"
                )

            def _on_error(self, title: str, message: str):
                QMessageBox.critical(self._window, title, message)
    ''', report_lines)

    # --- i18n/strings.py ---
    write_file(SRC_DIR / "i18n" / "__init__.py", "", report_lines)
    write_file(SRC_DIR / "i18n" / "strings.py", f'''
        APP_NAME = "مفكرتي"
        AUTHOR = "{AUTHOR_AR}"
        UNTITLED = "بدون عنوان"
        MODIFIED_SUFFIX = " •"
    ''', report_lines)

    # --- الثيمات ---
    write_file(SRC_DIR / "resources" / "styles" / "light.qss", '''
        QPlainTextEdit {
            background: #ffffff;
            color: #1a1a1a;
            selection-background-color: #cfe4ff;
        }
        QTabWidget::pane { border: 1px solid #d0d0d0; }
        QTabBar::tab { padding: 6px 12px; }
        QStatusBar { background: #f5f5f5; color: #333; }
    ''', report_lines)
    write_file(SRC_DIR / "resources" / "styles" / "dark.qss", '''
        QPlainTextEdit {
            background: #1e1e1e;
            color: #e0e0e0;
            selection-background-color: #264f78;
        }
        QTabWidget::pane { border: 1px solid #3c3c3c; }
        QTabBar::tab { padding: 6px 12px; background: #2d2d2d; color: #e0e0e0; }
        QStatusBar { background: #252525; color: #ccc; }
    ''', report_lines)

    # --- الأيقونة ---
    write_file(SRC_DIR / "resources" / "icons" / "app.svg", f'''
        <svg xmlns="http://www.w3.org/2000/svg" width="256" height="256">
          <rect width="256" height="256" rx="40" fill="#4a90d9"/>
          <text x="128" y="150" font-size="110" text-anchor="middle"
                fill="white" font-family="sans-serif">م</text>
          <text x="128" y="210" font-size="14" text-anchor="middle"
                fill="#e0e0e0" font-family="sans-serif">{AUTHOR_EN}</text>
        </svg>
    ''', report_lines)

    # --- الاختبارات ---
    write_file(PROJECT_ROOT / "tests" / "__init__.py", "", report_lines)
    write_file(PROJECT_ROOT / "tests" / "conftest.py", '''
        import pytest
        from pathlib import Path

        @pytest.fixture
        def sample_utf8_file(tmp_path: Path) -> Path:
            p = tmp_path / "sample_utf8.txt"
            p.write_text("مرحباً بالعالم\\nهذا ملف تجريبي.", encoding="utf-8")
            return p

        @pytest.fixture
        def sample_utf8_bom_file(tmp_path: Path) -> Path:
            p = tmp_path / "sample_bom.txt"
            p.write_bytes(b"\\xef\\xbb\\xbf" + "مرحباً".encode("utf-8"))
            return p

        @pytest.fixture
        def sample_cp1256_file(tmp_path: Path) -> Path:
            p = tmp_path / "sample_cp1256.txt"
            p.write_bytes("مرحباً".encode("windows-1256"))
            return p

        @pytest.fixture
        def sample_crlf_file(tmp_path: Path) -> Path:
            p = tmp_path / "sample_crlf.txt"
            p.write_text("line1\\r\\nline2\\r\\nline3", encoding="utf-8")
            return p

        @pytest.fixture
        def empty_file(tmp_path: Path) -> Path:
            p = tmp_path / "empty.txt"
            p.write_text("", encoding="utf-8")
            return p

        @pytest.fixture
        def binary_file(tmp_path: Path) -> Path:
            p = tmp_path / "binary.bin"
            p.write_bytes(b"\\x00\\x01\\x02\\x03")
            return p
    ''', report_lines)
    write_file(PROJECT_ROOT / "tests" / "test_document.py", '''
        from mufakkira.models.document import DocumentModel
        from pathlib import Path

        def test_default_document():
            doc = DocumentModel()
            assert doc.title == "بدون عنوان"
            assert not doc.is_modified

        def test_modified_title():
            doc = DocumentModel()
            doc.mark_modified()
            assert doc.display_title.endswith(" •")
            doc.mark_saved()
            assert not doc.display_title.endswith(" •")

        def test_title_with_path():
            doc = DocumentModel(path=Path("/tmp/test.txt"))
            assert doc.title == "test.txt"
    ''', report_lines)
    write_file(PROJECT_ROOT / "tests" / "test_file_service.py", '''
        from mufakkira.services.file_service import FileService

        def test_detect_utf8(sample_utf8_file):
            content, enc, le = FileService._read_file(sample_utf8_file)
            assert enc == "utf-8"
            assert "مرحباً" in content

        def test_detect_utf8_bom(sample_utf8_bom_file):
            content, enc, le = FileService._read_file(sample_utf8_bom_file)
            assert enc == "utf-8-sig"
            assert "مرحباً" in content

        def test_detect_cp1256(sample_cp1256_file):
            content, enc, le = FileService._read_file(sample_cp1256_file)
            assert enc == "windows-1256"
            assert "مرحباً" in content

        def test_detect_crlf(sample_crlf_file):
            content, enc, le = FileService._read_file(sample_crlf_file)
            assert le == "\\r\\n"
            assert "\\r\\n" not in content

        def test_empty_file(empty_file):
            content, enc, le = FileService._read_file(empty_file)
            assert content == ""

        def test_write_file(tmp_path):
            path = tmp_path / "written.txt"
            FileService._write_file(path, "مرحباً\\nعالم", "utf-8", "\\n")
            assert path.read_text(encoding="utf-8") == "مرحباً\\nعالم"

        def test_write_crlf(tmp_path):
            path = tmp_path / "written_crlf.txt"
            FileService._write_file(path, "سطر1\\nسطر2", "utf-8", "\\r\\n")
            assert b"\\r\\n" in path.read_bytes()
    ''', report_lines)
    write_file(PROJECT_ROOT / "tests" / "test_editor_view.py", '''
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QFont
        from mufakkira.models.document import DocumentModel
        from mufakkira.views.editor_view import EditorView

        def test_editor_load(qtbot):
            doc = DocumentModel(content="مرحباً\\nعالم")
            editor = EditorView(doc, QFont())
            qtbot.addWidget(editor)
            editor.load_document()
            assert editor.toPlainText() == "مرحباً\\nعالم"
            assert editor.blockCount() == 2

        def test_zoom(qtbot):
            doc = DocumentModel()
            editor = EditorView(doc, QFont())
            qtbot.addWidget(editor)
            original = editor.font().pointSize()
            editor.set_font_size(original + 2)
            assert editor.font().pointSize() == original + 2

        def test_direction_toggle(qtbot):
            doc = DocumentModel()
            editor = EditorView(doc, QFont())
            qtbot.addWidget(editor)
            assert editor.layoutDirection() == Qt.LayoutDirection.RightToLeft
            editor.set_layout_direction(Qt.LayoutDirection.LeftToRight)
            assert editor.layoutDirection() == Qt.LayoutDirection.LeftToRight
            editor.set_layout_direction(Qt.LayoutDirection.RightToLeft)
            assert editor.layoutDirection() == Qt.LayoutDirection.RightToLeft
    ''', report_lines)

    log("اكتمل إنشاء جميع ملفات المشروع.", "DONE", report_lines)


# ------------------------------------------------------------
# 4. بناء حزمة .deb
# ------------------------------------------------------------
def build_deb_package(report_lines: list):
    log("بدء بناء حزمة .deb...", "STEP", report_lines)

    if DEB_BUILD_ROOT.exists():
        shutil.rmtree(DEB_BUILD_ROOT)
    DEB_BUILD_ROOT.mkdir(parents=True, exist_ok=True)

    pkg_name = "notepad-linux"
    pkg_version = "1.0.0"
    pkg_root = DEB_BUILD_ROOT / f"{pkg_name}_{pkg_version}"
    debian_dir = pkg_root / "DEBIAN"
    usr_bin = pkg_root / "usr" / "bin"
    usr_lib = pkg_root / "usr" / "lib" / "python3" / "dist-packages" / "mufakkira"
    usr_share = pkg_root / "usr" / "share"

    for d in [debian_dir, usr_bin, usr_lib, usr_share]:
        d.mkdir(parents=True, exist_ok=True)

    # نسخ الكود المصدري
    src_pkg = PROJECT_ROOT / "src" / "mufakkira"
    if not src_pkg.exists():
        raise FileNotFoundError(f"مجلد المصدر غير موجود: {src_pkg}")
    shutil.copytree(src_pkg, usr_lib, dirs_exist_ok=True)
    log(f"نُسخ الكود المصدري إلى {usr_lib}", "FILE", report_lines)

    # سكربت التشغيل
    launcher = usr_bin / "mufakkira"
    launcher.write_text('''#!/usr/bin/python3
import sys
sys.path.insert(0, "/usr/lib/python3/dist-packages")
from mufakkira.app import main
sys.exit(main())
''', encoding="utf-8")
    launcher.chmod(0o755)
    log(f"أُنشئ سكربت التشغيل: {launcher}", "FILE", report_lines)

    # ملف .desktop
    desktop_dir = usr_share / "applications"
    desktop_dir.mkdir(parents=True, exist_ok=True)
    (desktop_dir / "mufakkira.desktop").write_text(f'''[Desktop Entry]
Type=Application
Name=مفكرتي
Name[en]=Mufakkira
GenericName=Text Editor
Comment=محرر نصوص عربي بسيط — تصميم {AUTHOR_AR}
Comment[en]=Simple Arabic-first text editor — by {AUTHOR_EN}
Exec=mufakkira %F
Icon=mufakkira
Terminal=false
Categories=Utility;TextEditor;Qt;
MimeType=text/plain;
StartupWMClass=mufakkira
''', encoding="utf-8")
    log("أُنشئ ملف .desktop", "FILE", report_lines)

    # نسخ الخط إلى /usr/share/fonts
    font_src = src_pkg / "resources" / "fonts" / "IBMPlexSansArabic-Light.ttf"
    if font_src.exists():
        font_dst = usr_share / "fonts" / "truetype" / "ibm-plex"
        font_dst.mkdir(parents=True, exist_ok=True)
        shutil.copy(font_src, font_dst / "IBMPlexSansArabic-Light.ttf")
        log(f"نُسخ الخط إلى {font_dst}", "FILE", report_lines)

    # نسخ الأيقونة
    icon_src = src_pkg / "resources" / "icons" / "app.svg"
    if icon_src.exists():
        icon_dir = usr_share / "icons" / "hicolor" / "scalable" / "apps"
        icon_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(icon_src, icon_dir / "mufakkira.svg")
        log("نُسخت الأيقونة.", "FILE", report_lines)

    # ملف control
    control_content = f'''Package: {pkg_name}
Version: {pkg_version}
Section: editors
Priority: optional
Architecture: all
Depends: python3 (>= 3.10),
         python3-pyside6.qtcore,
         python3-pyside6.qtgui,
         python3-pyside6.qtwidgets,
         python3-charset-normalizer,
         fontconfig
Maintainer: {AUTHOR_EN} <bilalfadl@mufakkira.app>
Homepage: https://github.com/bilalfadl/mufakkira
Description: المفكرة العربية الأولى على لينكس
 محرر نصوص بسيط مصمم للعربية أولاً، بخط IBM Plex Sans Arabic،
 مع دعم كامل RTL، تبويبات، وضع داكن، وأرقام أسطر.
 .
 تصميم وتطوير: {AUTHOR_AR}
'''
    (debian_dir / "control").write_text(control_content, encoding="utf-8")
    log("أُنشئ ملف control", "FILE", report_lines)

    # postinst
    postinst = debian_dir / "postinst"
    postinst.write_text('''#!/bin/sh
set -e
if [ -x /usr/bin/fc-cache ]; then
    fc-cache -f > /dev/null 2>&1 || true
fi
if command -v update-desktop-database > /dev/null 2>&1; then
    update-desktop-database -q /usr/share/applications > /dev/null 2>&1 || true
fi
exit 0
''', encoding="utf-8")
    postinst.chmod(0o755)

    # copyright
    (debian_dir / "copyright").write_text(f'''Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: Mufakkira
Upstream-Contact: {AUTHOR_EN} <bilalfadl@mufakkira.app>

Files: *
Copyright: 2025 {AUTHOR_AR} ({AUTHOR_EN})
License: MIT
''', encoding="utf-8")

    # بناء الحزمة
    final_deb_path = PROJECT_ROOT / FINAL_DEB_NAME
    cmd = ["dpkg-deb", "--build", "--root-owner-group", str(pkg_root), str(final_deb_path)]
    try:
        run_cmd(cmd, report_lines=report_lines)
        size_mb = final_deb_path.stat().st_size / (1024 * 1024)
        log(f"✅ تم بناء الحزمة: {final_deb_path} ({size_mb:.2f} MB)", "SUCCESS", report_lines)
    except subprocess.CalledProcessError:
        log("❌ فشل بناء الحزمة.", "ERROR", report_lines)
        raise


# ------------------------------------------------------------
# 5. الدالة الرئيسية
# ------------------------------------------------------------
def main():
    report_lines = []
    start_time = datetime.now()
    log("=" * 60, "INFO", report_lines)
    log("بدء بناء مشروع مفكرتي", "INFO", report_lines)
    log(f"تصميم وتطوير: {AUTHOR_AR}", "INFO", report_lines)
    log(f"وقت البدء: {start_time}", "INFO", report_lines)
    log("=" * 60, "INFO", report_lines)

    try:
        install_python_packages(report_lines)
        install_apt_packages(report_lines)
        locate_and_copy_font(report_lines)
        create_project_structure(report_lines)
        build_deb_package(report_lines)

        log("=" * 60, "INFO", report_lines)
        log("🎉 اكتمل البناء بنجاح!", "SUCCESS", report_lines)
        log(f"الحزمة: {PROJECT_ROOT / FINAL_DEB_NAME}", "SUCCESS", report_lines)
        log(f"للتثبيت:", "INFO", report_lines)
        log(f"  sudo dpkg -i {FINAL_DEB_NAME}", "INFO", report_lines)
        log(f"  sudo apt install -f", "INFO", report_lines)
        log(f"  mufakkira    # لتشغيل التطبيق", "INFO", report_lines)

    except Exception as e:
        log(f"💥 فشل البناء: {e}", "CRITICAL", report_lines)
        log(traceback.format_exc(), "TRACEBACK", report_lines)
        sys.exit(1)

    finally:
        end_time = datetime.now()
        duration = end_time - start_time
        report_lines.append("=" * 60)
        report_lines.append(f"وقت الانتهاء: {end_time}")
        report_lines.append(f"المدة: {duration}")
        report_lines.append("=" * 60)
        REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
        REPORT_FILE.write_text("\n".join(report_lines), encoding="utf-8")
        print(f"\n📄 التقرير الشامل: {REPORT_FILE}")


if __name__ == "__main__":
    main()
