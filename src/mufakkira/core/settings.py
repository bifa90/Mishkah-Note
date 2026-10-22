"""Persistent settings (JSON in the XDG config dir, Qt-free)."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any, Dict, List, Optional

from .languages import DEFAULT_LANGUAGE_CODE
from .text_direction import AUTO

APP_ORG = "Mufakkira"
APP_ID = "notepad-linux"


def config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / APP_ORG


@dataclass
class Settings:
    # appearance
    ui_language: str = DEFAULT_LANGUAGE_CODE
    theme: str = "system"            # system | light | dark
    font_family: str = ""            # empty = per-language stack
    font_size: int = 13
    tab_width: int = 4
    word_wrap: bool = True
    line_numbers: bool = False       # Windows 11 Notepad has no gutter
    show_status_bar: bool = True

    # text direction: "auto" keeps Qt's per-paragraph resolution
    default_direction: str = AUTO

    # editing conveniences
    auto_close_brackets: bool = True
    auto_indent: bool = True
    word_completion: bool = True
    #: Off by default: a plain notepad should not colour code unprompted.
    syntax_highlighting: bool = False

    # large files
    ask_before_mb: int = 64
    hard_limit_mb: int = 512
    performance_mode: bool = True

    # session
    restore_session: bool = True
    open_files: List[str] = field(default_factory=list)
    recent_files: List[str] = field(default_factory=list)
    window_geometry: Optional[str] = None
    window_state: Optional[str] = None

    path: Optional[Path] = field(default=None, repr=False, compare=False)

    # ------------------------------------------------------------ io
    @staticmethod
    def default_path() -> Path:
        return config_dir() / "settings.json"

    @classmethod
    def load(cls, path: Optional[Path] = None) -> Settings:
        path = Path(path) if path else cls.default_path()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls(path=path)
        known = {f.name for f in fields(cls)}
        kwargs = {k: v for k, v in raw.items() if k in known}
        settings = cls(**kwargs)
        settings.path = path
        return settings

    def save(self, path: Optional[Path] = None) -> Path:
        path = Path(path) if path else (self.path or self.default_path())
        path.parent.mkdir(parents=True, exist_ok=True)
        data = asdict(self)
        data.pop("path", None)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        os.replace(tmp, path)
        self.path = path
        return path

    # ------------------------------------------------------- helpers
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data.pop("path", None)
        return data

    def remember_file(self, file_path: str, max_items: int = 12) -> None:
        file_path = str(file_path)
        if file_path in self.recent_files:
            self.recent_files.remove(file_path)
        self.recent_files.insert(0, file_path)
        self.recent_files = self.recent_files[:max_items]

    def clear_recent(self) -> None:
        self.recent_files = []
