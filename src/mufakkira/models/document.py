"""Document model — plain data, no Qt widgets involved."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from mufakkira.core.encoding import TextFormat
from mufakkira.core.large_file import human_size
from mufakkira.core.text_direction import AUTO

UNTITLED = "Untitled"

# Above this many lines the editor switches to performance mode
# (no wrap, no undo stack, no line-number gutter).
PERFORMANCE_LINE_THRESHOLD = 2_000_000


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
