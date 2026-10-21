"""Line-number gutter (off by default, like Windows 11 Notepad).

The editor is reached through ``self.parent()`` rather than a stored Python
attribute: a strong child→parent reference combined with the parent's
``self._gutter`` creates a cycle that the interpreter tears down *after* Qt
is gone, which PySide6 reports as a refcount abort at exit.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QWidget


class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def _editor(self):
        return self.parent()

    def sizeHint(self):  # noqa: N802 (Qt naming)
        editor = self.parent()
        width = editor.gutter_width() if editor is not None else 0
        return QSize(width, 0)

    def paintEvent(self, event):  # noqa: N802 (Qt naming)
        editor = self.parent()
        if editor is not None:
            editor.paint_gutter(event)
