"""Cheap "did this file change?" test (CD-18).

Kept free of Qt so the guard can be tested without a window, and so the
controller can call it before *every* write without caring about threads.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Tuple

#: ``(mtime_ns, size)`` — enough to notice an edit, cheap enough to take
#: before every save.  A pixel-perfect answer would hash the file; this is
#: the same test every editor uses, and the write path is atomic anyway.
Signature = Tuple[int, int]


def stat_signature(path: Optional[Path]) -> Optional[Signature]:
    """``(mtime_ns, size)`` of *path*, or ``None`` when it cannot be read."""
    if path is None:
        return None
    try:
        info = os.stat(path)
    except OSError:
        return None
    return (info.st_mtime_ns, info.st_size)


def changed_on_disk(path: Optional[Path], signature: Optional[Signature]) -> bool:
    """True when *path* no longer matches *signature*.

    ``signature is None`` means "we never recorded this file", so nothing can
    be called a change.  A file that vanished, or is now unreadable, counts as
    changed: overwriting it silently would be exactly the data loss CD-18 is
    there to prevent.
    """
    if path is None or signature is None:
        return False
    current = stat_signature(path)
    return current is None or current != signature
