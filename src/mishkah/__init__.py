"""مفكرة مشكاة / Mishkah Note — a Windows 11-style text editor for Linux.

The package exposes only stable metadata here; everything else lives in
:mod:`mishkah.core` (Qt-free logic), :mod:`mishkah.services`
(background I/O) and :mod:`mishkah.views` (the Qt widgets).
"""

from __future__ import annotations

__version__ = "1.0.01"
APP_VERSION = __version__

APP_NAME = "Mishkah Note"
APP_NAME_AR = "مفكرة مشكاة"
APP_ID = "mishkah-note"
ORGANIZATION = "Mishkah"
PROJECT_URL = "https://github.com/bifa90/Mishkah-Note"
LICENSE = "MIT"

__all__ = [
    "APP_ID",
    "APP_NAME",
    "APP_NAME_AR",
    "APP_VERSION",
    "LICENSE",
    "ORGANIZATION",
    "PROJECT_URL",
    "__version__",
]
