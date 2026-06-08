"""
tests/test_roundtrip.py
=======================

Guards the core invariant that makes git diffs trustworthy:
serializing a hymn is deterministic and a fixed point.

Run with either::

    python -m pytest
    python -m tests.test_roundtrip      # no pytest required
"""

from __future__ import annotations

from pathlib import Path

from build.model import Hymn, Section


# Canonical form: minimal necessary quoting (8.8.8.8 is unambiguous as a string).
SAMPLE = (
    "---\n"
    "number: 1\n"
    "title: All People That on Earth Do Dwell\n"
    "author: William Kethe\n"
    "meter: 8.8.8.8\n"
    "sp_category: Praise and Adoration\n"
    "subject: Worship \u2014 Adoration\n"
    "---\n"
    "\n"
    "[verse 1]\n"
    "All people that on earth do dwell,\n"
    "Sing to the Lord with cheerful voice;\n"
    "\n"
    "[chorus]\n"
    "Praise God, from whom all blessings flow;\n"
)


def test_roundtrip_is_a_fixed_point():
    once = Hymn.parse(SAMPLE).to_text()
    twice = Hymn.parse(once).to_text()
    assert once == twice


def test_sample_is_already_canonical():
    assert Hymn.parse(SAMPLE).to_text() == SAMPLE


def test_serialize_normalises_unneeded_quoting():
    # a hand-editor's redundant quotes collapse to the canonical form
    messy = SAMPLE.replace("meter: 8.8.8.8", 'meter: "8.8.8.8"')
    assert Hymn.parse(messy).to_text() == SAMPLE


def test_refrain_aliases_to_chorus():
    text = SAMPLE.replace("[chorus]", "[refrain]")
    hymn = Hymn.parse(text)
    assert [s.kind for s in hymn.choruses] == ["chorus"]


def test_required_fields_enforced():
    for missing in ("number", "title"):
        broken = "\n".join(
            ln for ln in SAMPLE.splitlines() if not ln.startswith(missing + ":")
        ) + "\n"
        try:
            Hymn.parse(broken)
        except ValueError:
            continue
        raise AssertionError(f"expected ValueError when {missing} is missing")


def test_meter_stays_a_string():
    hymn = Hymn.parse(SAMPLE)
    assert hymn.meter == "8.8.8.8"  # not parsed as a number


def test_custom_meta_survives_roundtrip():
    hymn = Hymn(number=7, title="Test", extra={"ccli": "12345"})
    reparsed = Hymn.parse(hymn.to_text())
    assert reparsed.extra.get("ccli") == "12345"


def test_lines_are_preserved_verbatim():
    hymn = Hymn(
        number=1,
        title="T",
        sections=[Section("verse", 1, ["Line one,", "Line two."])],
    )
    assert Hymn.parse(hymn.to_text()).sections[0].lines == ["Line one,", "Line two."]


def test_existing_source_files_roundtrip():
    src = Path("source")
    if not src.exists():
        return  # nothing extracted yet
    for path in sorted(src.glob("*.hymn")):
        text = path.read_text(encoding="utf-8")
        assert Hymn.parse(text).to_text() == text, f"{path} is not canonical"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all tests passed")
