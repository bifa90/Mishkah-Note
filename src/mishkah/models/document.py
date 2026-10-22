"""Document model — plain data, no Qt widgets involved."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from mishkah.core.encoding import TextFormat
from mishkah.core.large_file import human_size
from mishkah.core.text_direction import AUTO

UNTITLED = "Untitled"

# Above this many lines the editor switches to performance mode
# (no wrap, no undo stack, no line-number gutter).
PERFORMANCE_LINE_THRESHOLD = 2_000_000

# Buffers up to this many characters are UTF-8 encoded for an exact status-bar
# size; above it the character count is used so typing never stalls.
LIVE_SIZE_EXACT_LIMIT = 100_000


@dataclass
class DocumentModel:
    path: Optional[Path] = None
    content: str = ""
    fmt: TextFormat = field(default_factory=TextFormat)
    is_modified: bool = False
    read_only: bool = False
    truncated: bool = False           # preview mode for huge files
    size_on_disk: int = 0
    direction_mode: str = AUTO        # auto | rtl | ltr
    warnings: List[str] = field(default_factory=list)
    encoding_override: Optional[str] = None
    # Tab presentation: a sticky-note colour ("" = none) and whether the tab
    # is pinned on top of other applications while it is active.
    color: str = ""
    pinned: bool = False
    # Syntax highlighting: "auto" follows the file extension, or a language
    # code from mishkah.core.syntax, "plain" disables it for this tab.
    language: str = "auto"

    # ------------------------------------------------------------- titles
    @property
    def title(self) -> str:
        return self.path.name if self.path else UNTITLED

    @property
    def display_title(self) -> str:
        return f"● {self.title}" if self.is_modified else self.title

    @property
    def location(self) -> str:
        return str(self.path) if self.path else ""

    # ------------------------------------------------------------- facts
    @property
    def line_count(self) -> int:
        if not self.content:
            return 0
        return self.content.count("\n") + (0 if self.content.endswith("\n") else 1)

    @property
    def char_count(self) -> int:
        return len(self.content)

    @property
    def size_label(self) -> str:
        return human_size(self.size_on_disk or len(self.content.encode("utf-8", "replace")))

    def live_size_label(self, text: str) -> str:
        """Size of the buffer the user is looking at, not of the file.

        An untouched document reports the real file size; once edited the
        status bar must follow the editor, otherwise it keeps claiming the
        size the file had when it was opened.  Very large buffers are
        estimated from their length instead of being re-encoded on every
        keystroke.
        """
        if not self.is_modified and self.size_on_disk:
            return human_size(self.size_on_disk)
        if len(text) <= LIVE_SIZE_EXACT_LIMIT:
            return human_size(len(text.encode("utf-8", "replace")))
        return human_size(len(text))

    @property
    def encoding(self) -> str:
        return self.fmt.encoding

    @property
    def line_ending(self) -> str:
        return self.fmt.line_ending

    @property
    def line_ending_label(self) -> str:
        return self.fmt.line_ending_label

    @property
    def uses_performance_mode(self) -> bool:
        return self.line_count > PERFORMANCE_LINE_THRESHOLD

    # ------------------------------------------------------------- state
    def mark_modified(self) -> None:
        if not self.read_only:
            self.is_modified = True

    def mark_saved(self, path: Optional[Path] = None, size: Optional[int] = None) -> None:
        if path is not None:
            self.path = Path(path)
        if size is not None:
            self.size_on_disk = size
        self.is_modified = False

    def set_line_ending(self, line_ending: str) -> None:
        if line_ending != self.fmt.line_ending:
            self.fmt = self.fmt.with_line_ending(line_ending)
            self.is_modified = True

    def set_encoding(self, encoding: str) -> None:
        if encoding != self.fmt.encoding:
            self.fmt = self.fmt.with_encoding(encoding)
            self.encoding_override = encoding
            self.is_modified = True

    def set_direction(self, mode: str) -> bool:
        if mode == self.direction_mode:
            return False
        self.direction_mode = mode
        return True
