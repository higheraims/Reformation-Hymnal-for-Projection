"""
build/model.py
==============

The single source of truth for the ``.hymn`` file format.

A ``.hymn`` file is:

    ---
    <YAML front matter: scalar metadata>
    ---

    [verse 1]
    line one
    line two

    [chorus]
    line one
    line two

Design goals
------------
* **Lossless, deterministic round-trip.** ``parse -> serialize -> parse`` is a
  fixed point, and ``serialize`` produces canonical formatting regardless of how
  a human hand-edited the input. This is what keeps git diffs meaningful: a
  rewrite only changes bytes when the *content* changed.
* **Newlines are data.** Inside a section, every line break is a deliberate
  sung/printed line. We never reflow.
* **Curly quotes are stored literally** (``" " ' '``). This module does not touch
  quote characters; that is the cleanup pass's job (build/clean.py).

The YAML front matter is *parsed* with PyYAML (robust against hand edits) but
*written* by our own emitter (so output formatting is fully under our control).

Canonical metadata key order is fixed (KNOWN_META_ORDER); any unrecognised keys
are preserved and emitted afterwards in sorted order, so custom fields survive.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:
    import yaml
except ImportError:  # pragma: no cover - PyYAML is a declared dependency
    yaml = None


# ---------------------------------------------------------------------------
# Format constants
# ---------------------------------------------------------------------------

#: Metadata keys emitted (when present) in this exact order.
KNOWN_META_ORDER = [
    "number",
    "title",
    "common_title",  # official/popular title where it differs from the first-line title
    "author",
    "composer",
    "tune",
    "meter",
    "sp_category",   # SoftProjector's built-in category
    "topic",         # topical category (from online hymnal index)
    "subject",       # the printed Reformation Hymnal's own subject index
    "copyright",
    "notes",         # editorial notes, never projected
]

#: Section kinds we understand. ``refrain`` is normalised to ``chorus``.
SECTION_ALIASES = {"refrain": "chorus"}
KNOWN_SECTION_KINDS = {"verse", "chorus", "bridge", "ending", "intro", "tag"}

_FRONT_MATTER_RE = re.compile(r"^---\n(?P<body>.*?)\n---\n?", re.DOTALL)
_HEADER_RE = re.compile(r"^\[\s*([A-Za-z]+)\s*(\d+)?\s*\]\s*$")
_NUMBERLIKE_RE = re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$")
_AMBIGUOUS_SCALAR_RE = re.compile(r"^(true|false|yes|no|on|off|null|~|none)$", re.I)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Section:
    """One block of a hymn: a verse, the chorus, a bridge, etc."""

    kind: str                      # "verse", "chorus", "bridge", "ending", ...
    number: Optional[int] = None   # e.g. verse 1, 2, 3; usually None for chorus
    lines: list[str] = field(default_factory=list)

    def header(self) -> str:
        return f"[{self.kind} {self.number}]" if self.number is not None else f"[{self.kind}]"


@dataclass
class Hymn:
    """A single hymn: metadata plus an ordered list of sections."""

    number: int
    title: str
    common_title: Optional[str] = None
    author: Optional[str] = None
    composer: Optional[str] = None
    tune: Optional[str] = None
    meter: Optional[str] = None
    sp_category: Optional[str] = None
    topic: Optional[str] = None
    subject: Optional[str] = None
    copyright: Optional[str] = None
    notes: Optional[str] = None
    extra: dict = field(default_factory=dict)        # any non-standard metadata
    sections: list[Section] = field(default_factory=list)

    # -- convenience views ---------------------------------------------------

    @property
    def verses(self) -> list[Section]:
        return [s for s in self.sections if s.kind == "verse"]

    @property
    def choruses(self) -> list[Section]:
        return [s for s in self.sections if s.kind == "chorus"]

    # -- serialization -------------------------------------------------------

    def to_text(self) -> str:
        """Render this hymn back to canonical ``.hymn`` text."""
        return _emit_front_matter(self) + "\n" + _emit_body(self)

    def save(self, path: str | Path) -> None:
        Path(path).write_text(self.to_text(), encoding="utf-8")

    # -- construction --------------------------------------------------------

    @classmethod
    def parse(cls, text: str) -> "Hymn":
        return _parse(text)

    @classmethod
    def load(cls, path: str | Path) -> "Hymn":
        return _parse(Path(path).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _parse(text: str) -> Hymn:
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    m = _FRONT_MATTER_RE.match(text)
    if not m:
        raise ValueError("missing or malformed YAML front matter (expected to start with '---')")

    meta = _load_yaml(m.group("body"))
    body = text[m.end():]

    if "number" not in meta or meta["number"] in (None, ""):
        raise ValueError("front matter is missing required key: number")
    if "title" not in meta or meta["title"] in (None, ""):
        raise ValueError("front matter is missing required key: title")

    known: dict = {}
    extra: dict = {}
    for key, value in meta.items():
        if value is None or value == "":
            continue  # treat empty/blank as absent -> keeps round-trip stable
        if key in KNOWN_META_ORDER:
            known[key] = value
        else:
            extra[key] = value

    try:
        known["number"] = int(str(known["number"]).strip())
    except (ValueError, TypeError) as exc:
        raise ValueError(f"'number' must be an integer, got {meta['number']!r}") from exc
    known["title"] = str(known["title"]).strip()

    # normalise remaining known scalars to stripped strings
    for key in list(known):
        if key not in ("number",):
            known[key] = str(known[key]).strip()

    sections = _parse_body(body)

    return Hymn(extra=extra, sections=sections, **known)


def _parse_body(body: str) -> list[Section]:
    sections: list[Section] = []
    current: Optional[Section] = None
    seen_header = False

    for raw in body.split("\n"):
        line = raw.rstrip()
        header = _HEADER_RE.match(line)

        if header:
            seen_header = True
            kind = header.group(1).lower()
            kind = SECTION_ALIASES.get(kind, kind)
            num = int(header.group(2)) if header.group(2) else None
            current = Section(kind=kind, number=num, lines=[])
            sections.append(current)
            continue

        if line == "":
            current = None  # blank line ends the current section
            continue

        if current is None:
            if not seen_header:
                raise ValueError(f"content before first section header: {line!r}")
            # stray text after a blank but before next header -> reopen a section
            raise ValueError(f"orphan line outside any section: {line!r}")

        current.lines.append(line)

    # drop any sections that ended up empty
    return [s for s in sections if s.lines]


def _load_yaml(block: str) -> dict:
    if yaml is not None:
        data = yaml.safe_load(block) or {}
        if not isinstance(data, dict):
            raise ValueError("front matter did not parse to a mapping")
        return data
    return _load_yaml_fallback(block)


def _load_yaml_fallback(block: str) -> dict:
    """Minimal ``key: value`` parser used only if PyYAML is unavailable."""
    data: dict = {}
    for line in block.split("\n"):
        line = line.split(" #", 1)[0].rstrip()
        if not line.strip():
            continue
        if ":" not in line:
            raise ValueError(f"cannot parse front-matter line without PyYAML: {line!r}")
        key, _, value = line.partition(":")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        data[key.strip()] = value
    return data


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def _emit_front_matter(h: Hymn) -> str:
    lines = ["---"]
    for key in KNOWN_META_ORDER:
        value = getattr(h, key, None)
        if value is None or value == "":
            continue
        lines.append(f"{key}: {_emit_scalar(value)}")
    for key in sorted(h.extra):
        value = h.extra[key]
        if value is None or value == "":
            continue
        lines.append(f"{key}: {_emit_scalar(value)}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def _emit_body(h: Hymn) -> str:
    blocks: list[str] = []
    for section in h.sections:
        blocks.append("\n".join([section.header(), *section.lines]))
    return "\n\n".join(blocks) + "\n"


def _emit_scalar(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    s = str(value)
    if _needs_quotes(s):
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return s


def _needs_quotes(s: str) -> bool:
    if s == "" or s != s.strip():
        return True
    if s[0] in "-?:,[]{}#&*!|>'\"%@`":
        return True
    if ": " in s or " #" in s or s.endswith(":"):
        return True
    if _AMBIGUOUS_SCALAR_RE.match(s):
        return True
    if _NUMBERLIKE_RE.match(s):
        return True
    return False


# ---------------------------------------------------------------------------
# Quick self-check:  python -m build.model
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sample = (
        "---\n"
        "number: 1\n"
        "title: All People That on Earth Do Dwell\n"
        "author: William Kethe\n"
        "composer: Louis Bourgeois\n"
        "tune: Old Hundredth\n"
        'meter: "8.8.8.8"\n'
        "sp_category: Praise and Adoration\n"
        "subject: Worship \u2014 Adoration\n"
        "copyright: Public Domain\n"
        "---\n"
        "\n"
        "[verse 1]\n"
        "All people that on earth do dwell,\n"
        "Sing to the Lord with cheerful voice;\n"
        "\n"
        "[refrain]\n"
        "Praise God, from whom all blessings flow;\n"
    )
    h = Hymn.parse(sample)
    once = h.to_text()
    twice = Hymn.parse(once).to_text()
    assert once == twice, "round-trip is not stable!"
    assert h.choruses, "refrain alias should normalise to chorus"
    print(once)
    print("round-trip stable:", once == twice)
