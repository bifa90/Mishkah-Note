"""The large-file engine: chunked read, preview mode, atomic write."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mufakkira.core import large_file  # noqa: E402
from mufakkira.core.encoding import CRLF, LF, TextFormat  # noqa: E402
from mufakkira.core.large_file import (  # noqa: E402
    BinaryFileError,
    OperationCancelled,
    human_size,
    load_file,
    read_text_chunked,
    write_text_atomic,
)


def test_round_trip_utf8(tmp_path: Path):
    path = tmp_path / "a.txt"
    path.write_text("مرحبا\nhello\n", encoding="utf-8")
    result = load_file(path)
    assert result.text == "مرحبا\nhello\n"
    assert result.fmt.encoding == "utf-8"
    assert result.truncated is False
    assert result.line_count == 2


def test_chunked_read_matches_whole_read(tmp_path: Path):
    payload = "".join(f"line {i} سطر عربي\n" for i in range(5000))
    path = tmp_path / "big.txt"
    path.write_text(payload, encoding="utf-8")

    # Force many chunks with a tiny block size.
    text, fmt, truncated, size = read_text_chunked(path, chunk=1024)
    assert text == payload
    assert truncated is False
    assert size == len(payload.encode("utf-8"))
    assert fmt.encoding == "utf-8"


def test_progress_callback_reaches_100_percent(tmp_path: Path):
    path = tmp_path / "p.txt"
    path.write_text("x" * 200_000, encoding="utf-8")
    seen = []
    read_text_chunked(path, chunk=8192, progress=lambda d, t: seen.append((d, t)))
    assert seen, "progress was never reported"
    assert seen[-1][0] == seen[-1][1], "last report must be 100%"


def test_cancellation_stops_the_read(tmp_path: Path):
    path = tmp_path / "c.txt"
    path.write_text("y" * 500_000, encoding="utf-8")
    with pytest.raises(OperationCancelled):
        read_text_chunked(path, chunk=1024, cancel=lambda: True)


def test_preview_mode_for_huge_files(tmp_path: Path):
    path = tmp_path / "huge.txt"
    path.write_text("line\n" * 4000, encoding="utf-8")
    result = load_file(path, hard_limit=1024, preview_bytes=512)
    assert result.truncated is True
    assert result.is_preview is True
    assert result.warnings
    assert len(result.text) < 4000 * 5
    assert not result.text.endswith("line") or result.text.endswith("\n")


def test_binary_file_rejected(tmp_path: Path):
    path = tmp_path / "b.bin"
    path.write_bytes(b"\x00\x01\x02\x03binary payload")
    with pytest.raises(BinaryFileError):
        load_file(path)


def test_atomic_write_replaces_content(tmp_path: Path):
    path = tmp_path / "out.txt"
    path.write_text("old", encoding="utf-8")
    written = write_text_atomic(path, "جديد\nnew\n", TextFormat("utf-8", LF, False))
    assert path.read_text(encoding="utf-8") == "جديد\nnew\n"
    assert written == path.stat().st_size
    assert not list(tmp_path.glob("*.part")), "temp file must be cleaned up"


def test_atomic_write_honours_crlf_and_bom(tmp_path: Path):
    path = tmp_path / "crlf.txt"
    write_text_atomic(path, "a\nb\n", TextFormat("utf-8-sig", CRLF, True))
    raw = path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    assert b"a\r\nb\r\n" in raw


def test_atomic_write_preserves_permissions(tmp_path: Path):
    path = tmp_path / "perm.txt"
    path.write_text("x", encoding="utf-8")
    path.chmod(0o640)
    write_text_atomic(path, "y", TextFormat("utf-8", LF, False))
    assert path.stat().st_mode & 0o777 == 0o640


def test_failed_write_leaves_original_intact(tmp_path: Path, monkeypatch):
    path = tmp_path / "keep.txt"
    path.write_text("original", encoding="utf-8")

    def boom(*_args, **_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(large_file.os, "replace", boom)
    with pytest.raises(OSError):
        write_text_atomic(path, "replacement", TextFormat("utf-8", LF, False))
    assert path.read_text(encoding="utf-8") == "original"
    assert not list(tmp_path.glob("*.part"))


def test_large_line_count_hint(tmp_path: Path):
    path = tmp_path / "many.txt"
    path.write_text("l\n" * 1000, encoding="utf-8")
    monkey_limit = large_file.MAX_SAFE_LINES_HINT
    large_file.MAX_SAFE_LINES_HINT = 500
    try:
        result = load_file(path)
    finally:
        large_file.MAX_SAFE_LINES_HINT = monkey_limit
    assert result.warnings, "expected a performance hint above the threshold"


def test_human_size():
    assert human_size(512) == "512 B"
    assert human_size(2048) == "2.0 KiB"
    assert human_size(5 * 1024 * 1024) == "5.0 MiB"
