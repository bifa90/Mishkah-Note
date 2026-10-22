"""Async file I/O built on the chunked engine in :mod:`mufakkira.core.large_file`.

Everything blocking runs on a ``QThread`` worker, so the window keeps
repainting while a multi-gigabyte log streams in.  Progress and
cancellation are wired through signals; the pure-Python engine stays
testable without Qt.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QThread, Signal

from mufakkira.core import large_file
from mufakkira.core.large_file import (
    BinaryFileError,
    FileTooLargeError,
    LoadResult,
    OperationCancelled,
)
from mufakkira.models.document import DocumentModel

logger = logging.getLogger(__name__)


class _ProgressEmitter:
    """Throttles chunk callbacks into Qt signals (≈20 Hz max)."""

    def __init__(self, signal: Signal, interval: float = 0.05):
        self._signal = signal
        self._interval = interval
        self._last = 0.0

    def __call__(self, done: int, total: int) -> None:
        now = time.monotonic()
        if now - self._last >= self._interval or done >= total:
            self._last = now
            self._signal.emit(done, total)


class LoadWorker(QThread):
    """Loads a document in the background."""

    loaded = Signal(object)                 # DocumentModel
    failed = Signal(str, str)               # title, detail
    progress = Signal(int, int)             # done, total
    warning = Signal(str)

    def __init__(self, path: Path, encoding: Optional[str] = None,
                 limit_mb: Optional[int] = None, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.path = Path(path)
        self.encoding = encoding
        self.limit_mb = limit_mb
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:  # pragma: no cover - executed on a worker thread
        started = time.monotonic()
        try:
            kwargs = dict(
                progress=_ProgressEmitter(self.progress),
                cancel=lambda: self._cancelled,
            )
            if self.limit_mb is None:
                result: LoadResult = large_file.load_file(
                    self.path,
                    encoding=self.encoding,
                    hard_limit=1 << 62,      # caller decided already
                    **kwargs,
                )
            else:
                result = large_file.read_text_chunked(
                    self.path, encoding=self.encoding,
                    limit=self.limit_mb * 1024 * 1024, **kwargs,
                )
                text, fmt, truncated, size = result
                result = LoadResult(self.path, text, fmt, size,
                                    truncated=truncated,
                                    line_count=text.count("\n") + 1)
        except OperationCancelled:
            self.failed.emit("cancelled", "")
            return
        except (FileNotFoundError, PermissionError, IsADirectoryError) as exc:
            self.failed.emit(type(exc).__name__, str(exc))
            return
        except (BinaryFileError, FileTooLargeError, OSError, UnicodeError) as exc:
            self.failed.emit(type(exc).__name__, str(exc))
            return

        elapsed = (time.monotonic() - started) * 1000
        result.elapsed_ms = elapsed
        doc = DocumentModel(
            path=result.path,
            content=result.text,
            fmt=result.fmt,
            size_on_disk=result.size,
            truncated=result.is_preview,
            read_only=result.is_preview or not _writable(result.path),
            warnings=list(result.warnings),
        )
        logger.info("loaded %s (%s, %s) in %.0f ms", result.path.name,
                    doc.size_label, doc.encoding, elapsed)
        self.loaded.emit(doc)


class SaveWorker(QThread):
    """Writes a document atomically in the background."""

    saved = Signal(object, int)             # DocumentModel, bytes written
    failed = Signal(str, str)
    progress = Signal(int, int)

    def __init__(self, doc: DocumentModel, target: Optional[Path] = None,
                 parent: Optional[QObject] = None):
        super().__init__(parent)
        self.doc = doc
        self.target = Path(target) if target else (doc.path or Path(""))
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:  # pragma: no cover - executed on a worker thread
        try:
            written = large_file.write_text_atomic(
                self.target,
                self.doc.content,
                self.doc.fmt,
                progress=_ProgressEmitter(self.progress),
                cancel=lambda: self._cancelled,
            )
        except OperationCancelled:
            self.failed.emit("cancelled", "")
            return
        except (PermissionError, OSError) as exc:
            self.failed.emit(type(exc).__name__, str(exc))
            return
        self.doc.mark_saved(self.target, written)
        self.saved.emit(self.doc, written)


def _writable(path: Path) -> bool:
    import os

    try:
        return os.access(path, os.W_OK)
    except OSError:  # pragma: no cover
        return False


class FileService(QObject):
    """Thin façade the controller talks to (keeps worker lifetimes sane)."""

    load_started = Signal(str)
    load_progress = Signal(int, int)
    load_finished = Signal(object)
    load_failed = Signal(str, str, str)     # path, title, detail

    save_started = Signal(str)
    save_progress = Signal(int, int)
    save_finished = Signal(object, int)
    save_failed = Signal(str, str, str)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._workers: list = []

    # ------------------------------------------------------------ load
    def load(self, path: Path, encoding: Optional[str] = None,
             limit_mb: Optional[int] = None) -> None:
        path = Path(path)
        worker = LoadWorker(path, encoding=encoding, limit_mb=limit_mb, parent=self)
        self._track(worker)
        worker.progress.connect(self.load_progress)
        worker.loaded.connect(lambda doc: self.load_finished.emit(doc))
        worker.failed.connect(lambda title, detail: self.load_failed.emit(
            str(path), title, detail))
        self.load_started.emit(str(path))
        worker.start()

    # ------------------------------------------------------------ save
    def save(self, doc: DocumentModel, target: Optional[Path] = None) -> None:
        worker = SaveWorker(doc, target=target, parent=self)
        self._track(worker)
        worker.progress.connect(self.save_progress)
        worker.saved.connect(lambda d, n: self.save_finished.emit(d, n))
        worker.failed.connect(lambda title, detail: self.save_failed.emit(
            str(self_target(doc, target)), title, detail))
        self.save_started.emit(str(target or doc.path or ""))
        worker.start()

    def _track(self, worker: QThread) -> None:
        self._workers.append(worker)
        worker.finished.connect(lambda w=worker: self._workers.remove(w)
                                if w in self._workers else None)

    def cancel_all(self) -> None:
        for worker in list(self._workers):
            if hasattr(worker, "cancel"):
                worker.cancel()


def self_target(doc: DocumentModel, target: Optional[Path]) -> Path:
    return Path(target) if target else (doc.path or Path(""))
