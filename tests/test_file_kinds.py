"""CD-05 · the open/write policy comes from the content, not the name."""

from __future__ import annotations

from mishkah.core.file_kinds import (
    READ_ONLY,
    TEXT,
    open_policy,
    policy_for_file,
    sniff,
)


def test_plain_text_is_text():
    assert sniff(b"hello\nworld\n") == TEXT
    assert sniff("مرحبا بالعالم".encode()) == TEXT
    assert sniff(b"") == TEXT


def test_a_single_nul_byte_is_enough():
    assert sniff(b"PK\x03\x04\x00\x00binary") == READ_ONLY


def test_a_high_share_of_control_bytes_is_binary():
    assert sniff(bytes(range(1, 30))) == READ_ONLY


def test_a_known_binary_extension_is_refused_even_with_text_inside():
    assert open_policy("photo.png", b"looks like text") == READ_ONLY
    assert open_policy("archive.zip") == READ_ONLY


def test_an_unknown_extension_is_not_punished():
    assert open_policy("notes.dat", b"real text\n") == TEXT
    assert open_policy("README", b"real text\n") == TEXT


def test_a_binary_smuggled_into_a_text_extension_is_caught():
    assert open_policy("script.py", b"\x00\x01\x02") == READ_ONLY


def test_policy_for_file_reads_the_disk(tmp_path):
    good = tmp_path / "good.txt"
    good.write_text("hello", encoding="utf-8")
    assert policy_for_file(good) == TEXT

    bad = tmp_path / "bad.txt"
    bad.write_bytes(b"\x00\x00\x00")
    assert policy_for_file(bad) == READ_ONLY

    assert policy_for_file(tmp_path / "missing.txt") == TEXT   # unreadable: no verdict
