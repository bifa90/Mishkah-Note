"""Encoding, BOM and line-ending detection.

Detection always runs on a *sample* (default 64 KiB) instead of the whole
file, so opening a 2 GiB log costs the same as opening a 2 KiB note.
"""

from __future__ import annotations

import codecs
from dataclasses import dataclass
from typing import Optional, Tuple

try:  # pragma: no cover - optional at runtime
    from charset_normalizer import from_bytes
except Exception:  # pragma: no cover
    from_bytes = None  # type: ignore

SAMPLE_BYTES = 64 * 1024

# Byte order marks, longest first so UTF-32 wins over UTF-16.
BOMS: Tuple[Tuple[bytes, str], ...] = (
    (codecs.BOM_UTF32_LE, "utf-32-le"),
    (codecs.BOM_UTF32_BE, "utf-32-be"),
    (codecs.BOM_UTF8, "utf-8-sig"),
    (codecs.BOM_UTF16_LE, "utf-16-le"),
    (codecs.BOM_UTF16_BE, "utf-16-be"),
)

LF = "\n"
CRLF = "\r\n"
CR = "\r"


@dataclass(frozen=True)
class TextFormat:
    encoding: str = "utf-8"
    line_ending: str = LF
    has_bom: bool = False
    confident: bool = True

    @property
    def label(self) -> str:
        enc = self.encoding.upper()
        if self.has_bom and "sig" not in self.encoding:
            enc += " BOM"
        return enc

    @property
    def line_ending_label(self) -> str:
        return {LF: "LF", CRLF: "CRLF", CR: "CR"}.get(self.line_ending, "LF")

    def with_encoding(self, encoding: str) -> TextFormat:
        return TextFormat(encoding, self.line_ending, self.has_bom, self.confident)

    def with_line_ending(self, line_ending: str) -> TextFormat:
        return TextFormat(self.encoding, line_ending, self.has_bom, self.confident)


def sniff_bom(head: bytes) -> Tuple[Optional[str], int]:
    for bom, encoding in BOMS:
        if head.startswith(bom):
            return encoding, len(bom)
    return None, 0


def detect_line_ending(sample: str, default: str = LF) -> str:
    crlf = sample.count(CRLF)
    if crlf:
        bare_lf = sample.count(LF) - crlf
        bare_cr = sample.count(CR) - crlf
        if crlf >= bare_lf and crlf >= bare_cr:
            return CRLF
    if sample.count(CR) > sample.count(LF):
        return CR
    return default


def looks_binary(head: bytes) -> bool:
    """Cheap binary heuristic: NUL byte in the first 8 KiB."""
    return b"\x00" in head[:8192]


def _charset_normalizer_guess(head: bytes) -> Optional[str]:
    if from_bytes is None:
        return None
    try:
        best = from_bytes(head).best()
    except Exception:
        return None
    if best is None:
        return None
    try:
        return str(best.encoding)
    except Exception:
        return None


def _utf8_or_ascii(head: bytes) -> Optional[str]:
    try:
        head.decode("ascii")
        return "utf-8"
    except UnicodeDecodeError:
        pass
    try:
        head.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        return None


def detect_format(head: bytes, default_line_ending: str = LF) -> TextFormat:
    """Decide encoding + line ending from the leading bytes of a file."""
    bom_encoding, bom_len = sniff_bom(head)
    body = head[bom_len:]

    if bom_encoding:
        encoding, confident = bom_encoding, True
    else:
        encoding = _utf8_or_ascii(body)
        confident = encoding is not None
        if encoding is None:
            guessed = _charset_normalizer_guess(body)
            encoding = guessed or "utf-8"
            confident = guessed is not None

    try:
        sample_text = body.decode(encoding, errors="replace")
    except (LookupError, UnicodeDecodeError):
        encoding, sample_text, confident = "utf-8", body.decode("utf-8", "replace"), False

    return TextFormat(
        encoding=encoding,
        line_ending=detect_line_ending(sample_text, default_line_ending),
        has_bom=bom_encoding is not None,
        confident=confident,
    )


def normalize_newlines(text: str) -> str:
    """Any mix of CRLF/CR/LF → LF (Qt stores LF internally)."""
    return text.replace(CRLF, LF).replace(CR, LF)


def apply_line_ending(text: str, line_ending: str) -> str:
    if line_ending == LF:
        return normalize_newlines(text)
    return normalize_newlines(text).replace(LF, line_ending)


def bom_for(encoding: str) -> bytes:
    table = {
        "utf-8-sig": codecs.BOM_UTF8,
        "utf-16-le": codecs.BOM_UTF16_LE,
        "utf-16-be": codecs.BOM_UTF16_BE,
        "utf-32-le": codecs.BOM_UTF32_LE,
        "utf-32-be": codecs.BOM_UTF32_BE,
    }
    return table.get(encoding.lower(), b"")


def incremental_decoder(encoding: str, errors: str = "replace"):
    try:
        return codecs.getincrementaldecoder(encoding)(errors=errors)
    except LookupError:
        return codecs.getincrementaldecoder("utf-8")(errors=errors)
