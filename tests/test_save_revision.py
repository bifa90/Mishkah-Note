"""An asynchronous save can only clear the revision it actually captured."""

from mishkah.core.encoding import CRLF
from mishkah.models.document import DocumentModel


def test_snapshot_revision_does_not_clear_new_edits(tmp_path):
    doc = DocumentModel(content="first")
    doc.mark_modified()
    snapshot = doc.revision
    doc.mark_modified()
    doc.mark_saved(tmp_path / "note.txt", 5, revision=snapshot)
    assert doc.is_modified
    assert doc.path == tmp_path / "note.txt"
    doc.mark_saved(size=6, revision=doc.revision)
    assert not doc.is_modified


def test_format_changes_advance_revision():
    doc = DocumentModel()
    doc.set_encoding("utf-16-le")
    assert doc.revision == 1
    doc.set_line_ending(CRLF)
    assert doc.revision == 2
    doc.set_line_ending(CRLF)
    assert doc.revision == 2
