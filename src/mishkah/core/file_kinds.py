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

#: How a name gets its extension when the user types none on the first save.
DEFAULT_EXTENSIONS = ("txt", "md", "auto")

#: Lines inspected when guessing a format from the content.
GUESS_LINES = 60


def guess_extension(text: str, mode: str = "auto") -> str:
    """The extension a nameless save should get (CD-05 · save).

    ``txt`` and ``md`` are the user's explicit choice; ``auto`` reads the
    opening lines and picks what they look like — a heading or a list is
    Markdown, ``def``/``import`` is Python, a leading brace is JSON, and
    everything else is plain text.
    """
    if mode in ("txt", "md"):
        return mode
    head = "\n".join(text.splitlines()[:GUESS_LINES]).strip()
    if not head:
        return "txt"
    lowered = head.lower()
    if lowered.startswith(("<!doctype", "<html", "<head", "<body")):
        return "html"
    if head[0] in "{[":
        return "json"
    lines = [line.strip() for line in head.splitlines() if line.strip()]
    if any(line.startswith(("```", "# ", "## ", "### ", "> ",
                            "- ", "* ", "+ ")) for line in lines):
        return "md"
    if any(line.startswith(("def ", "class ", "import ", "from "))
           or line.endswith(":") and line.split("(")[0].isidentifier()
           for line in lines):
        return "py"
    if any(line.startswith(("function ", "const ", "let ", "#!/usr/bin/env"))
           for line in lines):
        return "js" if not any("{" in line and ":" in line for line in lines) else "json"
    return "txt"


def ensure_extension(path: Path, text: str, mode: str = "txt") -> Path:
    """Give *path* an extension when it has none — never overwrite one."""
    path = Path(path)
    if path.suffix:
        return path
    return path.with_name(f"{path.name}.{guess_extension(text, mode)}")


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
