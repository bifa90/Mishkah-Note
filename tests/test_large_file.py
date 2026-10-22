"""The large-file engine: chunked read, preview mode, atomic write."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mishkah.core import large_file  # noqa: E402
from mishkah.core.encoding import CRLF, LF, TextFormat  # noqa: E402
from mishkah.core.large_file import (  # noqa: E402
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


@pytest.mark.parametrize("codec", ["utf-8-sig", "utf-16-le", "utf-16-be", "utf-32-le", "utf-32-be"])
def test_unicode_bom_round_trip_is_byte_exact(tmp_path, codec):
    from mishkah.core.encoding import bom_for

    text = "عربي English\nسطر آخر\n"
    body_codec = "utf-8" if codec == "utf-8-sig" else codec
    expected = bom_for(codec) + text.encode(body_codec)
    source = tmp_path / "source.txt"
    source.write_bytes(expected)
    loaded = load_file(source)
    assert loaded.text == text
    target = tmp_path / "target.txt"
    write_text_atomic(target, loaded.text, loaded.fmt, chunk_chars=2)
    assert target.read_bytes() == expected


@pytest.mark.parametrize("codec", ["utf-16-le", "utf-16-be", "utf-32-le", "utf-32-be"])
def test_explicit_wide_encoding_without_bom(tmp_path, codec):
    text = "نص عربي English\n"
    path = tmp_path / "unicode.txt"
    path.write_bytes(text.encode(codec))
    actual, fmt, _, _ = read_text_chunked(path, encoding=codec, chunk=3)
    assert actual == text
    assert not fmt.has_bom


@pytest.mark.parametrize("codec", ["utf-16", "utf-32", "iso2022_jp"])
def test_stateful_encoding_across_chunks(tmp_path, codec):
    text = "日本語\nabc\n"
    path = tmp_path / "stateful.txt"
    write_text_atomic(path, text, TextFormat(codec), chunk_chars=1)
    assert path.read_bytes().decode(codec) == text


def test_cancel_empty_write_preserves_destination(tmp_path):
    path = tmp_path / "keep.txt"
    path.write_text("keep")
    with pytest.raises(OperationCancelled):
        write_text_atomic(path, "", TextFormat(), cancel=lambda: True)
    assert path.read_text() == "keep"
    assert not list(tmp_path.glob(".*.part"))


def test_unrepresentable_text_does_not_replace_destination(tmp_path):
    path = tmp_path / "keep.txt"
    path.write_text("keep")
    with pytest.raises(UnicodeEncodeError):
        write_text_atomic(path, "نص عربي", TextFormat("ascii"))
    assert path.read_text() == "keep"
    assert not list(tmp_path.glob(".*.part"))
