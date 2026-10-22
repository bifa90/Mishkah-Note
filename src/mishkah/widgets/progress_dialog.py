"""A cancellable progress dialog for long file operations."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QProgressDialog, QWidget

from mishkah.core.i18n import tr


class ProgressDialog(QProgressDialog):
    """Thin wrapper that keeps the main window responsive during I/O.

    ``cancelled`` is emitted once when the user presses *Cancel* (or closes
    the dialog); the service layer polls :meth:`is_cancelled` to stop early.
    """

    cancelled = Signal()

    def __init__(self, title: str, parent: Optional[QWidget] = None,
                 minimum_duration: int = 400):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setLabelText(title)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setCancelButtonText(tr("dialog.cancel"))
        self.setAutoClose(True)
        self.setAutoReset(False)
        self.setMinimumDuration(minimum_duration)
        self.setMinimumWidth(420)
        self.setValue(0)
        self._cancelled = False
        self.canceled.connect(self._on_cancel)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)

    # ------------------------------------------------------------------
    def _on_cancel(self) -> None:
        if not self._cancelled:
            self._cancelled = True
            self.cancelled.emit()

    def is_cancelled(self) -> bool:
        return self._cancelled

    # ------------------------------------------------------------------
    def report(self, done: int, total: int, label: str = "") -> None:
        """Update the bar; returns nothing so callers can pass it directly."""
        if total > 0:
            self.setMaximum(total)
        self.setValue(min(done, max(total, done)))
        if label:
            self.setLabelText(label)

    def report_bytes(self, done: int, total: int) -> None:
        from mishkah.core.large_file import human_size

        self.report(done, total,
                    tr("dialog.progress", done=human_size(done),
                       total=human_size(total)))

    def finish(self) -> None:
        self.setAutoReset(True)
        self.setValue(self.maximum())
        self.close()
