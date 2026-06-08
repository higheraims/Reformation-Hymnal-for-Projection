"""
build/extract_sps.py
====================

One-time (re-runnable) extractor:  SoftProjector ``.sps``  ->  ``source/*.hymn``.

A ``.sps`` songbook is a **SQLite 3 database** (SoftProjector 2.0+). This script
opens it, finds the song table, maps its columns to our fields, splits each
song's text into sections, and writes one ``.hymn`` file per song using the
canonical serializer in ``build/model.py``.

IMPORTANT — verify against the real file before trusting the output
-------------------------------------------------------------------
Column names and the in-text stanza encoding vary between SoftProjector
versions, so this script *auto-detects* and then *reports what it decided*.
Always start with::

    python -m build.extract_sps --db reference/original.sps --inspect

That prints the schema, the detected column mapping, the chosen stanza
separator, and a couple of fully-parsed sample songs. Confirm those look right
(or override them with the flags below) before doing the real run::

    python -m build.extract_sps --db reference/original.sps --out source/

Override knobs (all optional):
    --table NAME            force the song table
    --separator REGEX       force the stanza separator (Python regex)
    --col-number COL  --col-title COL  --col-author COL
    --col-composer COL --col-tune COL  --col-category COL --col-lyrics COL

Notes
-----
* Extraction is **verbatim**: straight quotes and original line breaks are kept.
  Cleanup (curly quotes, line-break repair) is a later, separately-reviewed pass.
* Chorus detection is heuristic and flagged in each file's ``notes`` when used,
  so a human can confirm it during review.
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from pathlib import Path

from .model import Hymn, Section

# Legacy SoftProjector formatting markers that sometimes survive in song text.
_LEGACY_MARKERS = ["@$", "@%"]

# Candidate stanza separators, tried in order during auto-detection.
_SEPARATOR_CANDIDATES = [
    r"\n[ \t]*\n",   # blank line (most common)
    r"\r?\n\r?\n",   # CRLF blank line
    r"<br>\s*<br>",  # occasionally seen in PDF-derived text
]

# Column-name heuristics: logical field -> ordered list of substring matchers.
# Earlier matchers win. Matched case-insensitively against actual column names.
_COLUMN_HINTS = {
    "number":   ["song_number", "songnumber", "number", "num", "no"],
    "title":    ["title", "name", "caption"],
    "author":   ["author", "words", "writer", "lyricist", "text_author"],
    "composer": ["composer", "music", "tune_author", "melody_author"],
    "tune":     ["tune", "melody"],
    "category": ["category", "categ", "theme", "topic", "subject", "type"],
    "lyrics":   ["song_text", "songtext", "lyrics", "lyric", "text", "verses",
                 "stanza", "words", "body"],
}

# A leading section label line like "Chorus", "Refrain:", "Verse 2", "Verse 1 of 4", "1."
# The "N of M" suffix appears in SoftProjector-exported text and must be consumed.
_LABEL_RE = re.compile(
    r"^\s*(chorus|refrain|bridge|ending|verse)?\s*[:\-]?\s*(\d+)?\s*(?:of\s+\d+)?\s*[.):]?\s*$",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Schema discovery
# ---------------------------------------------------------------------------

def list_tables(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    return [r[0] for r in rows]


def columns_of(conn: sqlite3.Connection, table: str) -> list[str]:
    return [r[1] for r in conn.execute(f'PRAGMA table_info("{table}")').fetchall()]


def find_song_table(conn: sqlite3.Connection) -> str:
    """Pick the table most likely to hold songs.

    Score = has a title-ish column (+2) + has a big text column (+2)
            + table name contains 'song' (+1).
    """
    best, best_score = None, -1
    for table in list_tables(conn):
        if table.startswith("sqlite_"):
            continue
        cols = [c.lower() for c in columns_of(conn, table)]
        if not cols:
            continue
        score = 0
        if any("title" in c or "name" in c for c in cols):
            score += 2
        if any(h in c for c in cols for h in ("text", "lyric", "words", "verse")):
            score += 2
        if "song" in table.lower():
            score += 1
        if score > best_score:
            best, best_score = table, score
    if best is None:
        raise SystemExit("could not find a song table; pass --table NAME")
    return best


def detect_columns(conn: sqlite3.Connection, table: str) -> dict[str, str | None]:
    """Map logical fields to actual column names using name heuristics."""
    actual = columns_of(conn, table)
    lower = {c.lower(): c for c in actual}
    mapping: dict[str, str | None] = {}
    used: set[str] = set()

    for field, hints in _COLUMN_HINTS.items():
        chosen = None
        for hint in hints:
            for low, real in lower.items():
                if real in used:
                    continue
                if hint == low or hint in low:
                    chosen = real
                    break
            if chosen:
                break
        if chosen:
            used.add(chosen)
        mapping[field] = chosen

    # If lyrics not found by name, fall back to the longest-average-text column.
    if mapping["lyrics"] is None:
        mapping["lyrics"] = _longest_text_column(conn, table, exclude=used)
    return mapping


def _longest_text_column(conn, table, exclude) -> str | None:
    best, best_len = None, -1
    for col in columns_of(conn, table):
        if col in exclude:
            continue
        try:
            row = conn.execute(
                f'SELECT AVG(LENGTH("{col}")) FROM "{table}"'
            ).fetchone()
        except sqlite3.Error:
            continue
        avg = row[0] or 0
        if avg > best_len:
            best, best_len = col, avg
    return best


def detect_categories(conn: sqlite3.Connection) -> dict[int, str]:
    """Find a category lookup table (id -> name), if one exists."""
    for table in list_tables(conn):
        cols = [c.lower() for c in columns_of(conn, table)]
        if any("categ" in c for c in cols) or "category" in table.lower():
            id_col = next((c for c in columns_of(conn, table)
                           if c.lower() in ("id", "category_id", "rowid")), None)
            name_col = next((c for c in columns_of(conn, table)
                             if "name" in c.lower() or "categ" in c.lower()
                             and c != id_col), None)
            if id_col and name_col:
                try:
                    rows = conn.execute(
                        f'SELECT "{id_col}", "{name_col}" FROM "{table}"'
                    ).fetchall()
                    return {int(r[0]): str(r[1]) for r in rows if r[0] is not None}
                except sqlite3.Error:
                    pass
    return {}


# ---------------------------------------------------------------------------
# Stanza handling
# ---------------------------------------------------------------------------

def clean_markers(text: str) -> str:
    for marker in _LEGACY_MARKERS:
        text = text.replace(marker, "")
    return text


def detect_separator(conn, table, lyrics_col) -> str:
    """Pick the separator that splits the most songs into >1 stanza."""
    rows = conn.execute(
        f'SELECT "{lyrics_col}" FROM "{table}" WHERE "{lyrics_col}" IS NOT NULL LIMIT 50'
    ).fetchall()
    texts = [clean_markers(str(r[0])).replace("\r\n", "\n") for r in rows]
    best, best_hits = _SEPARATOR_CANDIDATES[0], -1
    for sep in _SEPARATOR_CANDIDATES:
        hits = sum(1 for t in texts if len(re.split(sep, t)) > 1)
        if hits > best_hits:
            best, best_hits = sep, hits
    return best


def split_sections(text: str, separator: str) -> list[Section]:
    """Split verbatim song text into Section objects.

    Heuristics, all conservative and review-friendly:
    * blocks separated by ``separator`` become sections;
    * a block whose first line is a bare label ("Chorus", "Refrain:") becomes a
      chorus, with the label line stripped;
    * a block whose first line is a bare number/"1." uses that as the verse no.;
    * everything else is a verse, numbered in order of appearance.
    """
    text = clean_markers(text).replace("\r\n", "\n").strip("\n")
    blocks = [b for b in re.split(separator, text) if b.strip()]

    sections: list[Section] = []
    verse_no = 0
    for block in blocks:
        lines = [ln.rstrip() for ln in block.split("\n")]
        # peel a leading label/number line if present
        kind, number = "verse", None
        if lines:
            m = _LABEL_RE.match(lines[0])
            if m and (m.group(1) or m.group(2)) and lines[0].strip():
                label, num = m.group(1), m.group(2)
                if label and label.lower() in ("chorus", "refrain"):
                    kind = "chorus"
                elif label and label.lower() in ("bridge", "ending"):
                    kind = label.lower()
                if num:
                    number = int(num)
                lines = lines[1:]  # drop the label line
        lines = [ln for ln in lines if ln.strip() != ""] or lines
        if not any(ln.strip() for ln in lines):
            continue
        if kind == "verse":
            verse_no += 1
            number = number or verse_no
        sections.append(Section(kind=kind, number=number, lines=lines))
    return sections


# ---------------------------------------------------------------------------
# Row -> Hymn
# ---------------------------------------------------------------------------

def row_to_hymn(row, cols, mapping, categories, separator, index) -> Hymn:
    def get(field):
        col = mapping.get(field)
        return row[cols.index(col)] if col and col in cols else None

    raw_number = get("number")
    try:
        number = int(str(raw_number).strip())
    except (TypeError, ValueError):
        number = index  # fall back to row order if no usable number

    title = (get("title") or f"Hymn {number}")
    title = str(title).strip()

    category = get("category")
    if category is not None:
        try:
            category = categories.get(int(category), str(category))
        except (TypeError, ValueError):
            category = str(category)

    lyrics = get("lyrics") or ""
    sections = split_sections(str(lyrics), separator)

    used_chorus_heuristic = any(s.kind == "chorus" for s in sections)
    notes = "AUTO: chorus detected heuristically — verify" if used_chorus_heuristic else None

    def s(v):
        return str(v).strip() if v not in (None, "") else None

    return Hymn(
        number=number,
        title=title,
        author=s(get("author")),
        composer=s(get("composer")),
        tune=s(get("tune")),
        sp_category=s(category),
        notes=notes,
        sections=sections,
    )


# ---------------------------------------------------------------------------
# Inspection & main
# ---------------------------------------------------------------------------

def inspect(conn, table, mapping, separator) -> None:
    print(f"# Tables: {', '.join(list_tables(conn))}")
    print(f"# Song table: {table}")
    print(f"# Columns: {', '.join(columns_of(conn, table))}")
    print("# Detected mapping:")
    for field in _COLUMN_HINTS:
        print(f"#   {field:9s} -> {mapping.get(field)}")
    print(f"# Stanza separator regex: {separator!r}")
    cats = detect_categories(conn)
    print(f"# Category lookup rows: {len(cats)}")
    print("\n# ---- sample songs ----\n")
    cols = columns_of(conn, table)
    rows = conn.execute(f'SELECT * FROM "{table}" LIMIT 2').fetchall()
    for i, row in enumerate(rows, 1):
        hymn = row_to_hymn(row, cols, mapping, cats, separator, i)
        print(hymn.to_text())
        print("# " + "-" * 40)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Extract a SoftProjector .sps songbook to .hymn files.")
    ap.add_argument("--db", required=True, help="path to the .sps (SQLite) file")
    ap.add_argument("--out", default="source", help="output directory for .hymn files")
    ap.add_argument("--inspect", action="store_true", help="report detection & samples, write nothing")
    ap.add_argument("--table", help="force the song table name")
    ap.add_argument("--separator", help="force the stanza separator (Python regex)")
    for field in _COLUMN_HINTS:
        ap.add_argument(f"--col-{field}", dest=f"col_{field}", help=f"force the {field} column")
    args = ap.parse_args(argv)

    conn = sqlite3.connect(args.db)
    try:
        table = args.table or find_song_table(conn)
        mapping = detect_columns(conn, table)
        for field in _COLUMN_HINTS:  # apply overrides
            override = getattr(args, f"col_{field}")
            if override:
                mapping[field] = override
        separator = args.separator or detect_separator(conn, table, mapping["lyrics"])

        if args.inspect:
            inspect(conn, table, mapping, separator)
            return 0

        cols = columns_of(conn, table)
        categories = detect_categories(conn)
        rows = conn.execute(f'SELECT * FROM "{table}"').fetchall()

        hymns = [row_to_hymn(r, cols, mapping, categories, separator, i)
                 for i, r in enumerate(rows, 1)]

        # zero-pad filenames to the widest number present
        width = max(3, len(str(max((h.number for h in hymns), default=0))))
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)

        seen: set[int] = set()
        for hymn in hymns:
            if hymn.number in seen:
                print(f"WARNING: duplicate hymn number {hymn.number} ({hymn.title})", file=sys.stderr)
            seen.add(hymn.number)
            hymn.save(out / f"{hymn.number:0{width}d}.hymn")

        print(f"Wrote {len(hymns)} hymns to {out}/ (table={table}, separator={separator!r})")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
