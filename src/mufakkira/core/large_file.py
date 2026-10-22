"""Chunked, cancellable file I/O for very large documents.

Why this module exists
----------------------
``Path.read_text()`` on a 3 GiB log allocates the whole buffer, decodes it
all at once and freezes the UI.  Everything here is incremental:

* the format is sniffed from the first 64 KiB only,
* the body is decoded through ``codecs`` incremental decoders in 1 MiB
  blocks, so memory stays roughly *file size + text size* instead of
  *2 × file size + intermediate bytes*,
* progress and cancellation are plain callbacks — the Qt layer turns them
  into signals, the test-suite drives them synchronously,
* files above ``HARD_LIMIT_BYTES`` are opened as a **preview** (first
  ``PREVIEW_BYTES`` only, read-only) instead of being loaded, and
* writes go to a temporary file that is atomically renamed, so a crash
  mid-save can never truncate the original.

The module is intentionally Qt-free.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterator, List, Optional, Tuple

from .encoding import (
    TextFormat,
    apply_line_ending,
    bom_for,
    detect_format,
    incremental_decoder,
    looks_binary,
    normalize_newlines,
    sniff_bom,
)

CHUNK_BYTES = 1 << 20            # 1 MiB
SNIFF_BYTES = 64 * 1024
PREVIEW_BYTES = 8 * 1024 * 1024  # what "preview mode" shows
HARD_LIMIT_BYTES = 512 * 1024 * 1024
MAX_SAFE_LINES_HINT = 2_000_000

ProgressFn = Callable[[int, int], None]


class FileTooLargeError(OSError):
    def __init__(self, size: int, limit: int):
        super().__init__(f"file is {size} bytes, above the {limit} byte limit")
        self.size = size
        self.limit = limit


class BinaryFileError(OSError):
    pass


class OperationCancelled(Exception):
    pass


@dataclass
class LoadResult:
    path: Path
    text: str
    fmt: TextFormat
    size: int
    truncated: bool = False        # preview mode
    line_count: int = 0
    elapsed_ms: float = 0.0
    warnings: List[str] = field(default_factory=list)

    @property
    def is_preview(self) -> bool:
        return self.truncated


def _report(progress: Optional[ProgressFn], done: int, total: int,
            cancel: Optional[Callable[[], bool]]) -> None:
    if cancel is not None and cancel():
        raise OperationCancelled()
    if progress is not None:
        progress(done, total)


def _iter_chunks(path: Path, start: int, end: Optional[int],
                 chunk: int = CHUNK_BYTES) -> Iterator[bytes]:
    with open(path, "rb") as fh:
        if start:
            fh.seek(start)
        remaining = None if end is None else max(0, end - start)
        while True:
            if remaining is not None and remaining <= 0:
                break
            block = fh.read(chunk if remaining is None else min(chunk, remaining))
            if not block:
                break
            if remaining is not None:
                remaining -= len(block)
            yield block


def read_text_chunked(
    path: Path,
    encoding: Optional[str] = None,
    limit: Optional[int] = None,
    progress: Optional[ProgressFn] = None,
    cancel: Optional[Callable[[], bool]] = None,
    chunk: int = CHUNK_BYTES,
) -> Tuple[str, TextFormat, bool, int]:
    """Stream-decode *path*.

    Returns ``(text, fmt, truncated, size)``.  ``encoding=None`` means
    "sniff it"; pass an explicit codec to honour *Reopen with encoding*.
    """
    path = Path(path)
    size = path.stat().st_size

    with open(path, "rb") as fh:
        head = fh.read(SNIFF_BYTES)
    if looks_binary(head):
        raise BinaryFileError(f"{path.name} looks like a binary file")

    fmt = detect_format(head)
    if encoding:
        fmt = fmt.with_encoding(encoding)

    bom_encoding, bom_len = sniff_bom(head)
    forced = encoding is not None and not bom_encoding
    parts: List[str] = []
    decoder = incremental_decoder(fmt.encoding)
    consumed = 0
    total = size
    start = 0

    if bom_len and not forced:
        start = bom_len
        consumed = bom_len

    limit_bytes = size if limit is None else min(size, start + limit)
    truncated = limit_bytes < size

    for block in _iter_chunks(path, start, limit_bytes, chunk):
        parts.append(decoder.decode(block))
        consumed += len(block)
        _report(progress, consumed, total, cancel)

    parts.append(decoder.decode(b"", True))  # flush trailing state
    text = "".join(parts)
    text = normalize_newlines(text)
    return text, fmt, truncated, size


def preview_text(path: Path, limit: int = PREVIEW_BYTES) -> Tuple[str, TextFormat, int]:
    """Read only the first *limit* bytes — used above ``HARD_LIMIT_BYTES``.

    The tail is cut back to the last complete line so the preview never ends
    with a half-finished sentence (``[:cut + 1]`` keeps that line's own
    terminator, which is what makes ``line_count`` honest too).
    """
    text, fmt, _, size = read_text_chunked(path, limit=limit)
    if not text.endswith("\n"):
        cut = text.rfind("\n")
        if cut > 0:
            text = text[:cut + 1]
    return text, fmt, size


def load_file(
    path: Path,
    encoding: Optional[str] = None,
    hard_limit: int = HARD_LIMIT_BYTES,
    preview_bytes: int = PREVIEW_BYTES,
    progress: Optional[ProgressFn] = None,
    cancel: Optional[Callable[[], bool]] = None,
) -> LoadResult:
    """High-level loader: full load, or preview + warning when huge."""
    path = Path(path)
    size = path.stat().st_size
    warnings: List[str] = []

    if size > hard_limit:
        text, fmt, real_size = preview_text(path, preview_bytes)
        warnings.append(
            f"File is {human_size(size)} — showing the first "
            f"{human_size(preview_bytes)} only (read-only)."
        )
        return LoadResult(path, text, fmt, real_size, truncated=True,
                          line_count=text.count("\n") + 1, warnings=warnings)

    text, fmt, truncated, real_size = read_text_chunked(
        path, encoding=encoding, progress=progress, cancel=cancel
    )
    line_count = text.count("\n") + (0 if text.endswith("\n") else 1) if text else 0
    if line_count > MAX_SAFE_LINES_HINT:
        warnings.append(
            f"{line_count:,} lines — undo history and word wrap are disabled "
            "to keep editing fast."
        )
    return LoadResult(path, text, fmt, real_size, truncated=truncated,
                      line_count=line_count, warnings=warnings)


def write_text_atomic(
    path: Path,
    text: str,
    fmt: TextFormat,
    progress: Optional[ProgressFn] = None,
    cancel: Optional[Callable[[], bool]] = None,
    chunk_chars: int = 1 << 20,
) -> int:
    """Write *text* atomically with *fmt*; returns bytes written."""
    path = Path(path)
    directory = path.parent
    directory.mkdir(parents=True, exist_ok=True)

    payload = apply_line_ending(text, fmt.line_ending)
    encoding = fmt.encoding
    prefix_bytes = bom_for(encoding) if fmt.has_bom else b""

    total = max(1, len(payload))
    written = 0
    fd, tmp_name = tempfile.mkstemp(dir=str(directory), prefix=f".{path.name}.",
                                    suffix=".part")
    try:
        with os.fdopen(fd, "wb") as fh:
            if prefix_bytes:
                fh.write(prefix_bytes)
                written += len(prefix_bytes)
            encoder = codecs_lookup_encoder(encoding)
            for start in range(0, len(payload), chunk_chars):
                piece = payload[start:start + chunk_chars]
                fh.write(encoder(piece))
                written += len(piece.encode(encoding, "replace")) if False else 0
                _report(progress, min(total, start + chunk_chars), total, cancel)
            fh.flush()
            os.fsync(fh.fileno())
        _copy_permissions(path, tmp_name)
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    return path.stat().st_size


def codecs_lookup_encoder(encoding: str) -> Callable[[str], bytes]:
    import codecs

    try:
        encode = codecs.getencoder(encoding)
    except LookupError:
        encode = codecs.getencoder("utf-8")

    def _encode(chunk: str) -> bytes:
        return encode(chunk, "replace")[0]

    return _encode


def _copy_permissions(src: Path, dst: str) -> None:
    try:
        st = src.stat()
    except FileNotFoundError:
        os.chmod(dst, 0o644)
        return
    os.chmod(dst, st.st_mode & 0o7777)


def human_size(num: float) -> str:
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(num) < 1024 or unit == "TiB":
            return f"{num:.0f} {unit}" if unit == "B" else f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} TiB"
