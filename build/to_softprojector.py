"""
build/to_softprojector.py
=========================
Compile source/*.hymn -> dist/ReformationHymnal.sps (SoftProjector SQLite songbook).

SPS encoding notes (discovered from reference/original.sps in Phase 1):
  - Song text stored in `song_text` column as a single string.
  - Verses:   "Verse N of M\\n{lines}"   (M = total verse count for this hymn)
  - Refrains: "Refrain \\n{lines}"       (note: trailing space after "Refrain")
  - Sections separated by "\\n\\n"; no trailing separator after the last section.
  - `words` = author, `music` = composer, `category` = integer from sp_category.

Display-settings defaults are taken from the majority of hymns in the original SPS.
A handful of hymns in the original had empty font/color (inherited from SoftProjector
global settings); we use the explicit defaults for all hymns to ensure consistency.

Usage:
    python -m build.to_softprojector
"""

from __future__ import annotations

import sqlite3
import sys
from datetime import date
from pathlib import Path

from build.model import Hymn

SOURCE = Path(__file__).parent.parent / "source"
DIST   = Path(__file__).parent.parent / "dist"
OUT    = DIST / "ReformationHymnal.sps"

_FONT  = ",28,-1,5,50,0,0,0,0,0"
_WHITE = 4294967295

_SCHEMA = """\
PRAGMA user_version = 2;
CREATE TABLE 'SongBook' ('title' TEXT, 'info' TEXT);
CREATE TABLE 'Songs' (
    'number'          INTEGER,
    'title'           TEXT,
    'category'        INTEGER DEFAULT 0,
    'tune'            TEXT,
    'words'           TEXT,
    'music'           TEXT,
    'song_text'       TEXT,
    'notes'           TEXT,
    'use_private'     BOOL,
    'alignment_v'     INTEGER,
    'alignment_h'     INTEGER,
    'color'           INTEGER,
    'font'            TEXT,
    'info_color'      INTEGER,
    'info_font'       TEXT,
    'ending_color'    INTEGER,
    'ending_font'     TEXT,
    'use_background'  BOOL,
    'background_name' TEXT,
    'background'      BLOB,
    'count'           INTEGER DEFAULT 0,
    'date'            TEXT
);
"""


def _encode_song_text(hymn: Hymn) -> str:
    """Encode a Hymn's sections into SoftProjector song_text format."""
    verse_count = sum(1 for s in hymn.sections if s.kind == "verse")
    parts: list[str] = []
    verse_num = 0
    for s in hymn.sections:
        body = "\n".join(s.lines)
        if s.kind == "verse":
            verse_num += 1
            parts.append(f"Verse {verse_num} of {verse_count}\n{body}")
        elif s.kind in ("chorus", "refrain"):
            parts.append(f"Refrain \n{body}")
    return "\n\n".join(parts)


def main() -> int:
    DIST.mkdir(exist_ok=True)
    if OUT.exists():
        OUT.unlink()

    con = sqlite3.connect(OUT)
    cur = con.cursor()
    cur.executescript(_SCHEMA)

    today = date.today().strftime("%Y/%m/%d")
    cur.execute(
        "INSERT INTO SongBook VALUES (?, ?)",
        ("Reformation Hymnal", f"Digital Version for SoftProjector - {today}"),
    )

    paths = sorted(SOURCE.glob("*.hymn"))
    for path in paths:
        hymn = Hymn.load(path)
        cur.execute(
            "INSERT INTO Songs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                hymn.number,
                hymn.title,
                int(hymn.sp_category) if hymn.sp_category else 0,
                hymn.tune or "",
                hymn.author or "",
                hymn.composer or "",
                _encode_song_text(hymn),
                hymn.notes or "",
                0,              # use_private
                1,              # alignment_v
                1,              # alignment_h
                _WHITE,         # color
                _FONT,          # font
                _WHITE,         # info_color
                "Arial,28,-1,5,50,0,0,0,0,0",  # info_font
                _WHITE,         # ending_color
                "Arial,28,-1,5,50,0,0,0,0,0",  # ending_font
                0,              # use_background
                "\n",           # background_name (original SPS default)
                None,           # background BLOB
                0,              # count (reset usage counter)
                "",             # date
            ),
        )

    con.commit()
    con.close()
    size_kb = OUT.stat().st_size // 1024
    print(f"Written {OUT}  ({len(paths)} hymns, {size_kb} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
