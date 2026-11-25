"""What kind of file is this, and may we write to it? (CD-05)

The decision is made from the **content**, not the name: an extension is a
hint, and a user who renames a script to ``.dat`` still deserves an editor,
while a file full of NUL bytes is a binary whatever it is called.  Nothing
here imports Qt, so the rule can be unit tested directly.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

#: Extensions where "open it as text and let me save" would destroy data.
BINARY_EXTENSIONS = frozenset({
    "7z", "a", "avi", "bin", "bmp", "bz2", "class", "db", "deb", "dll", "dmg",
    "doc", "docx", "dylib", "exe", "flac", "gif", "gz", "ico", "iso", "jar",
    "jpeg", "jpg", "m4a", "mkv", "mov", "mp3", "mp4", "o", "obj", "ods",
    "odt", "ogg", "otf", "pdf", "png", "ppt", "pptx", "pyc", "rar", "rpm",
    "so", "sqlite", "sqlite3", "tar", "tif", "tiff", "ttf", "wav", "webm",
    "webp", "woff", "woff2", "xls", "xlsx", "xz", "zip", "zst",
})

#: How much of the file is looked at.  Enough for any header, small enough to
#: read on the GUI thread without anyone noticing.
SNIFF_BYTES = 4096

#: Above this share of control bytes the file is treated as binary.  Real text
#: in any script stays far below it (UTF-8 multibyte sequences are 0x80+).
BINARY_CONTROL_RATIO = 0.30

TEXT = "text"
READ_ONLY = "read_only"


def sniff(sample: bytes) -> str:
    """``"text"`` or ``"read_only"`` for a slice of the file's first bytes."""
    if not sample:
        return TEXT
    if b"\x00" in sample:
        return READ_ONLY
    control = sum(1 for byte in sample
                  if byte < 9 or (13 < byte < 32) or byte == 127)
    return READ_ONLY if control / len(sample) > BINARY_CONTROL_RATIO else TEXT


def extension(path: Optional[Path | str]) -> str:
    return Path(path).suffix.lower().lstrip(".") if path else ""


def open_policy(path: Optional[Path | str], sample: bytes = b"") -> str:
    """Decide how *path* may be opened.

    A known-binary extension wins immediately; otherwise the content decides.
    Unknown extensions are **not** punished — ``.dat`` holding text opens as
    a normal document, because refusing it would be guessing about names.
    """
    if extension(path) in BINARY_EXTENSIONS:
        return READ_ONLY
    return sniff(sample)


def sample_of(path: Path, limit: int = SNIFF_BYTES) -> bytes:
    """The first *limit* bytes of *path*, or ``b""`` when unreadable."""
    try:
        with open(path, "rb") as handle:
            return handle.read(limit)
    except OSError:
        return b""


def policy_for_file(path: Path) -> str:
    return open_policy(path, sample_of(path))
