"""مفكرتي / Notepad — a Windows 11-style text editor for Linux.

The package exposes only stable metadata here; everything else lives in
:mod:`mufakkira.core` (Qt-free logic), :mod:`mufakkira.services`
(background I/O) and :mod:`mufakkira.views` (the Qt widgets).
"""

from __future__ import annotations

__version__ = "1.0.1"
APP_VERSION = __version__

APP_NAME = "Notepad"
APP_NAME_AR = "المفكرة"
APP_ID = "notepad-linux"
ORGANIZATION = "Mufakkira"
PROJECT_URL = "https://github.com/bifa90/Notepad-Linux"
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
