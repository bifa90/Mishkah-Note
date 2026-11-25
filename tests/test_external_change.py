"""CD-18 · a save must never replace a change made outside the editor."""

from __future__ import annotations

import os

from mishkah.core.disk_state import changed_on_disk, stat_signature
from mishkah.models.document import DocumentModel


def test_signature_of_a_file_is_mtime_and_size(tmp_path):
    path = tmp_path / "note.txt"
    path.write_text("hello", encoding="utf-8")
    signature = stat_signature(path)
    assert signature is not None
    assert signature[1] == 5
    assert stat_signature(tmp_path / "missing.txt") is None
    assert stat_signature(None) is None


def test_nothing_is_a_change_without_a_recorded_signature(tmp_path):
    path = tmp_path / "note.txt"
    path.write_text("hello", encoding="utf-8")
    assert changed_on_disk(path, None) is False
    assert changed_on_disk(None, stat_signature(path)) is False


def test_the_same_file_is_not_a_change(tmp_path):
    path = tmp_path / "note.txt"
    path.write_text("hello", encoding="utf-8")
    assert changed_on_disk(path, stat_signature(path)) is False


def test_a_different_size_or_time_is_a_change(tmp_path):
    path = tmp_path / "note.txt"
    path.write_text("hello", encoding="utf-8")
    signature = stat_signature(path)
    path.write_text("hello there", encoding="utf-8")
    assert signature is not None
    assert changed_on_disk(path, signature) is True


def test_a_deleted_file_counts_as_changed(tmp_path):
    path = tmp_path / "note.txt"
    path.write_text("hello", encoding="utf-8")
    signature = stat_signature(path)
    path.unlink()
    assert changed_on_disk(path, signature) is True


def test_touch_alone_is_a_change(tmp_path):
    """mtime moves even when the size does not: that is still an edit."""
    path = tmp_path / "note.txt"
    path.write_text("hello", encoding="utf-8")
    signature = stat_signature(path)
    stat = path.stat()
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))
    assert changed_on_disk(path, signature) is True


def test_mark_saved_records_the_signature(tmp_path):
    path = tmp_path / "note.txt"
    path.write_text("hello", encoding="utf-8")
    doc = DocumentModel(path=path, content="hello")
    assert doc.disk_signature is None
    doc.mark_saved(path, 5, signature=stat_signature(path))
    assert doc.disk_signature == stat_signature(path)
    assert changed_on_disk(path, doc.disk_signature) is False

