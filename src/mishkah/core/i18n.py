"""Tiny Qt-free translation layer.

Ten languages are bundled (the world's ten most spoken).  Strings live in
:mod:`mishkah.core.i18n_data`; this module only resolves the active
language with a graceful ``lang → en → ar`` fallback chain, so a missing
entry degrades to English instead of showing a raw key.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional

from .i18n_data import STRINGS
from .languages import DEFAULT_LANGUAGE_CODE, get_language

FALLBACKS = (DEFAULT_LANGUAGE_CODE, "ar")

_current: str = DEFAULT_LANGUAGE_CODE
_subscribers: List[Callable[[str], None]] = []


def set_language(code: str) -> None:
    global _current
    _current = get_language(code).code
    for cb in list(_subscribers):
        try:
            cb(_current)
        except Exception:  # pragma: no cover - defensive
            pass


def current_language() -> str:
    return _current


def current_language_rtl() -> bool:
    return get_language(_current).rtl


def on_language_changed(callback: Callable[[str], None]) -> None:
    if callback not in _subscribers:
        _subscribers.append(callback)


def translate(key: str, **kwargs: object) -> str:
    table: Optional[Dict[str, str]] = STRINGS.get(key)
    if table is None:
        return key
    for code in (_current, *FALLBACKS):
        value = table.get(code)
        if value:
            break
    else:  # pragma: no cover - only when no fallback exists
        value = key
    if kwargs:
        try:
            return value.format(**kwargs)
        except (KeyError, IndexError, ValueError):  # pragma: no cover
            return value
    return value


tr = translate


def has(key: str) -> bool:
    return key in STRINGS
