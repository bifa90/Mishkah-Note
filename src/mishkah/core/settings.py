"""Persistent settings (JSON in the XDG config dir, Qt-free).

The file on disk is untrusted input: it can be truncated, hand-edited, written
by an older release, or kept in sync by a tool.  Loading therefore goes through
a typed schema — every persisted field has a type, an optional range and a
default — and a structurally corrupt file is backed up before defaults are
used.  A settings file must never be able to stop the application from starting.
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import MISSING, asdict, dataclass, field, fields
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .languages import DEFAULT_LANGUAGE_CODE
from .text_direction import AUTO, LTR, RTL

APP_ORG = "Mishkah"
APP_ID = "mishkah-note"

#: Sentinels used by the schema below.
_BOOL = "bool"
_INT = "int"
_ENUM = "enum"
_TEXT = "text"
_PATH_LIST = "path-list"
_OPTIONAL_TEXT = "optional-text"


def config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / APP_ORG


#: ``field -> (kind, spec)``; anything absent from this table is not persisted.
SCHEMA: Dict[str, Tuple[str, Any]] = {
    # appearance
    "ui_language": (_ENUM, None),          # validated against the language registry
    "theme": (_ENUM, ("system", "light", "dark")),
    "font_family": (_TEXT, 120),
    "font_size": (_INT, (6, 72)),
    "tab_width": (_INT, (1, 16)),
    "word_wrap": (_BOOL, None),
    "line_numbers": (_BOOL, None),
    "show_status_bar": (_BOOL, None),
    # diagnostics: reveal LRM/RLM/ALM/ZWNJ and friends
    "show_invisible_chars": (_BOOL, None),
    # direction
    "default_direction": (_ENUM, (AUTO, RTL, LTR)),
    #: How a whole document's alignment is decided (CD-20).  "first_strong"
    #: is the 1.0.01 behaviour and stays the default; "first_line" is opt-in.
    "document_side_source": (_ENUM, ("first_strong", "first_line")),
    # data safety: autosave is off until the user asks for it (CD-01)
    "autosave": (_BOOL, None),
    "autosave_idle_ms": (_INT, (500, 60000)),
    # editing conveniences
    "auto_close_brackets": (_BOOL, None),
    "auto_indent": (_BOOL, None),
    "word_completion": (_BOOL, None),
    "syntax_highlighting": (_BOOL, None),
    "live_markdown": (_BOOL, None),
    # large files
    "ask_before_mb": (_INT, (1, 4096)),
    "hard_limit_mb": (_INT, (1, 65536)),
    "performance_mode": (_BOOL, None),
    # session
    "restore_session": (_BOOL, None),
    "open_files": (_PATH_LIST, 50),
    "recent_files": (_PATH_LIST, 50),
    "window_geometry": (_OPTIONAL_TEXT, 4096),
    "window_state": (_OPTIONAL_TEXT, 4096),
}

#: Fields that are runtime-only and never written to disk.
_TRANSIENT = {"path", "repairs"}


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _known_language_codes() -> set:
    from .languages import all_languages  # local import: keeps module import cheap

    return {language.code for language in all_languages()}


@dataclass
class Settings:
    # appearance
    ui_language: str = DEFAULT_LANGUAGE_CODE
    theme: str = "system"            # system | light | dark
    font_family: str = ""            # empty = per-language stack
    font_size: int = 13
    tab_width: int = 4
    word_wrap: bool = True
    line_numbers: bool = False       # Windows 11 Mishkah Note has no gutter
    show_status_bar: bool = True
    #: Diagnostic view, off by default: it marks formatting characters
    #: that are otherwise completely invisible (CD-16).
    show_invisible_chars: bool = False

    # text direction: "auto" keeps Qt's per-paragraph resolution
    default_direction: str = AUTO
    #: Which rule decides the side a whole document is aligned to (CD-20):
    #: "first_strong" = the first strong character anywhere (the previous
    #: behaviour, kept as the default), "first_line" = the first line that
    #: reads in either direction, re-decided while the first line is the only
    #: line.  Neither touches Qt's per-paragraph ordering.
    document_side_source: str = "first_strong"

    #: CD-01: off by default; the View toolbar has a one-click switch.
    autosave: bool = False
    #: How long the typing has to stop before an autosave fires.
    autosave_idle_ms: int = 2000

    # editing conveniences
    auto_close_brackets: bool = True
    auto_indent: bool = True
    word_completion: bool = True
    #: Off by default: a plain mishkah should not colour code unprompted.
    syntax_highlighting: bool = False
    #: Off by default: live Markdown is a view, opt-in like highlighting.
    live_markdown: bool = False

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
    #: Human readable reasons why the loaded file was repaired; runtime only.
    repairs: List[str] = field(default_factory=list, init=False, repr=False, compare=False)

    # ------------------------------------------------------------ defaults
    @staticmethod
    def default_path() -> Path:
        return config_dir() / "settings.json"

    @classmethod
    def _defaults(cls) -> Dict[str, Any]:
        values: Dict[str, Any] = {}
        for item in fields(cls):
            if item.name in _TRANSIENT:
                continue
            if item.default is not MISSING:
                values[item.name] = item.default
            elif item.default_factory is not MISSING:
                values[item.name] = item.default_factory()  # type: ignore[misc]
        return values

    # ---------------------------------------------------------------- io
    @classmethod
    def load(cls, path: Optional[Path] = None) -> Settings:
        """Load settings, repairing anything invalid.  Never raises."""
        settings, _ = cls.load_detailed(path)
        return settings

    @classmethod
    def load_detailed(cls, path: Optional[Path] = None) -> Tuple[Settings, List[str]]:
        """Like :meth:`load` but also returns the list of repairs applied."""
        target = Path(path) if path else cls.default_path()
        try:
            text = target.read_text(encoding="utf-8")
        except OSError:
            return cls(path=target), []
        except UnicodeDecodeError:
            backup = cls._backup(target)
            return cls(path=target), [
                f"{target.name} is not UTF-8; defaults used"
                + (f" (backup: {backup.name})" if backup else ""),
            ]

        try:
            raw = json.loads(text)
        except ValueError:
            backup = cls._backup(target)
            return cls(path=target), [
                f"{target.name} is not valid JSON; defaults used"
                + (f" (backup: {backup.name})" if backup else ""),
            ]

        if not isinstance(raw, dict):
            backup = cls._backup(target)
            return cls(path=target), [
                f"{target.name} does not contain a JSON object; defaults used"
                + (f" (backup: {backup.name})" if backup else ""),
            ]

        defaults = cls._defaults()
        repairs: List[str] = []
        values: Dict[str, Any] = {}
        for name in SCHEMA:
            if name not in raw:
                continue
            values[name] = cls._coerce(name, raw[name], defaults[name], repairs)

        settings = cls(**values)
        settings.path = target
        if "open_files" in values and not isinstance(values["open_files"], list):
            settings.open_files = []
        if settings.hard_limit_mb < settings.ask_before_mb:
            repairs.append(
                "hard_limit_mb was smaller than ask_before_mb; raised to match it"
            )
            settings.hard_limit_mb = settings.ask_before_mb
        settings.repairs = repairs
        return settings, repairs

    @classmethod
    def _coerce(cls, name: str, value: Any, default: Any, repairs: List[str]) -> Any:
        kind, spec = SCHEMA[name]
        if kind is _BOOL:
            if isinstance(value, bool):
                return value
            repairs.append(f"{name}: expected a boolean, got {type(value).__name__}; default used")
            return default
        if kind is _INT:
            low, high = spec
            if not _is_int(value):
                repairs.append(f"{name}: expected an integer, got {type(value).__name__}; default used")
                return default
            if not low <= value <= high:
                repairs.append(f"{name}: {value} is outside {low}..{high}; default used")
                return default
            return value
        if kind is _ENUM:
            allowed = spec
            if name == "ui_language":
                allowed = tuple(sorted(_known_language_codes()))
            if isinstance(value, str) and value in allowed:
                return value
            repairs.append(f"{name}: {value!r} is not one of {sorted(allowed)}; default used")
            return default
        if kind is _TEXT:
            if isinstance(value, str):
                return value[:spec]
            repairs.append(f"{name}: expected text, got {type(value).__name__}; default used")
            return default
        if kind is _OPTIONAL_TEXT:
            if value is None:
                return None
            if isinstance(value, str):
                return value[:spec]
            repairs.append(f"{name}: expected text or null, got {type(value).__name__}; default used")
            return default
        if kind is _PATH_LIST:
            if value is None:
                return []
            if not isinstance(value, list):
                repairs.append(f"{name}: expected a list, got {type(value).__name__}; default used")
                return list(default)
            cleaned: List[str] = []
            for item in value:
                if isinstance(item, str) and item and item not in cleaned:
                    cleaned.append(item[:4096])
                else:
                    repairs.append(f"{name}: dropped an entry that is not a usable path")
            if len(cleaned) > spec:
                repairs.append(f"{name}: kept the newest {spec} entries")
                cleaned = cleaned[:spec]
            return cleaned
        raise AssertionError(f"unhandled schema kind {kind!r}")  # pragma: no cover

    @staticmethod
    def _backup(path: Path) -> Optional[Path]:
        """Copy an unusable settings file aside so the user can inspect it."""
        backup = path.with_name(path.name + ".bak")
        try:
            shutil.copy2(path, backup)
        except OSError:  # pragma: no cover - read-only directories
            return None
        return backup

    # -------------------------------------------------------------- save
    def save(self, path: Optional[Path] = None) -> Path:
        target = Path(path) if path else (self.path or self.default_path())
        target.parent.mkdir(parents=True, exist_ok=True)
        data = self.sanitised()
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, target)
        self.path = target
        return target

    def sanitised(self) -> Dict[str, Any]:
        """Persisted keys only, each one validated (never write a bad value)."""
        defaults = self._defaults()
        repairs: List[str] = []
        data: Dict[str, Any] = {}
        for name in SCHEMA:
            current = getattr(self, name)
            data[name] = self._coerce(name, current, defaults[name], repairs)
        return data

    # ----------------------------------------------------------- helpers
    def to_dict(self) -> Dict[str, Any]:
        return self.sanitised()

    def remember_file(self, file_path: str, max_items: int = 12) -> None:
        file_path = str(file_path)
        if file_path in self.recent_files:
            self.recent_files.remove(file_path)
        self.recent_files.insert(0, file_path)
        self.recent_files = self.recent_files[:max_items]

    def clear_recent(self) -> None:
        self.recent_files = []


# ``asdict`` is re-exported for callers that build their own payloads.
__all__ = ["APP_ID", "APP_ORG", "SCHEMA", "Settings", "asdict", "config_dir"]
