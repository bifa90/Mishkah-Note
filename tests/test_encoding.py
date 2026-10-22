"""Encoding / BOM / line-ending detection."""

from __future__ import annotations

import codecs
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mishkah.core.encoding import (  # noqa: E402
    CRLF,
    LF,
    apply_line_ending,
    bom_for,
    detect_format,
    detect_line_ending,
    looks_binary,
    normalize_newlines,
    sniff_bom,
)


def test_plain_utf8():
    fmt = detect_format("مرحبا\nhello\n".encode())
    assert fmt.encoding == "utf-8"
    assert fmt.has_bom is False
    assert fmt.line_ending == LF


def test_ascii_detected_as_utf8():
    fmt = detect_format(b"plain ascii\r\n")
    assert fmt.encoding == "utf-8"
    assert fmt.line_ending == CRLF


def test_utf8_bom():
    fmt = detect_format(codecs.BOM_UTF8 + "نص".encode())
    assert fmt.encoding == "utf-8-sig"
    assert fmt.has_bom is True


def test_utf16_le_bom():
    fmt = detect_format(codecs.BOM_UTF16_LE + "نص".encode("utf-16-le"))
    assert fmt.encoding == "utf-16-le"
    assert fmt.has_bom is True


def test_windows_1256_arabic():
    fmt = detect_format("مرحبا بالعالم".encode("cp1256"))
    assert fmt.encoding.lower().replace("-", "") in ("cp1256", "windows1256")
    assert fmt.confident is True


def test_crlf_wins_when_majority():
    assert detect_line_ending("a\r\nb\r\nc\nd") == CRLF
    assert detect_line_ending("a\nb\nc\r\nd") == LF


def test_bare_cr_old_mac():
    assert detect_line_ending("a\rb\rc") == "\r"


def test_binary_detection():
    assert looks_binary(b"\x00\x01\x02binary") is True
    assert looks_binary(b"just text") is False


def test_normalize_and_apply_line_ending():
    assert normalize_newlines("a\r\nb\rc\nd") == "a\nb\nc\nd"
    # apply_line_ending converts existing terminators; it never adds one.
    assert apply_line_ending("a\nb", CRLF) == "a\r\nb"
    assert apply_line_ending("a\nb\n", CRLF) == "a\r\nb\r\n"
    assert apply_line_ending("a\r\nb", LF) == "a\nb"


def test_bom_for():
    assert bom_for("utf-8-sig") == codecs.BOM_UTF8
    assert bom_for("utf-16-le") == codecs.BOM_UTF16_LE
    assert bom_for("utf-8") == b""


def test_sniff_bom_returns_length():
    encoding, length = sniff_bom(codecs.BOM_UTF8 + b"abc")
    assert encoding == "utf-8-sig"
    assert length == 3
