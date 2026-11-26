"""The deferral of G3b #5 is a decision, so it is written down — and checked.

The owner's words: «٥ بالامكان تأجيله للنسخة الجديدة التي سنحدث فيه النواة،
حاليا بالشكل هذا هو مقبول».  A deferred item that lives only in a chat message is
an item that comes back as a surprise, so the archive file, the roadmap row and
the gate's own result page must all still say the same thing.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_the_mixed_direction_item_is_archived_for_the_next_core():
    archive = ROOT / "docs" / "DEFERRED_1.0.03.ar.md"
    assert archive.exists(), "the deferral must be archived, not remembered"

    text = archive.read_text(encoding="utf-8")
    assert "1.0.03" in text  # version-gate: allow
    assert "محاذاة لكل فقرة" in text
    assert "اختبار بكسل" in text, "the closure condition must be testable"


def test_the_roadmap_and_the_gate_point_at_the_archive():
    roadmap = (ROOT / "docs" / "ROADMAP.md").read_text(encoding="utf-8")
    assert "DEFERRED_1.0.03.ar.md" in roadmap
    assert "مؤجَّل بقرار المالك إلى 1.0.03" in roadmap  # version-gate: allow

    results = (ROOT / "docs" / "G3B_RESULTS.ar.md").read_text(encoding="utf-8")
    assert "مؤجَّل بقرار المالك" in results
    assert "أُغلقت بتحقّق المستخدم" in results, "item 14 was re-checked by the owner"
