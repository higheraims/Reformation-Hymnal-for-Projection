"""
build/to_freeshow.py
====================
Compile source/*.hymn into two FreeShow deliverables:

  dist/ReformationHymnal.project   -- plain-JSON project (File > Import > FreeShow Project)
  dist/shows/NNN.show              -- 700 individual show files (single-hymn import)

FreeShow .project format (reverse-engineered from a native FreeShow export):
  Plain JSON (not ZIP) with top-level keys:
    "project"      -- name, created, parent="/", shows[] as {id, index}
    "parentFolder" -- ""
    "shows"        -- { id: Show, ... }
    "files"        -- []

  Show object keys (matching FreeShow native export):
    name, origin, private, category, settings, timestamps, quickAccess,
    meta, slides, layouts, media

  Slide item format:
    { "style": "top:88px;left:50px;height:904px;width:1820px;",
      "lines": [ {"align": "", "text": [{"style": "", "value": line}]} ] }

  Category: FreeShow derives IDs as name.toLowerCase().replaceAll(" ", "_").
  User must pre-create "Reformation Hymnal" category in FreeShow before import.

Slide IDs and show IDs are deterministic strings (h{num}s{idx}, h{num}) so
rebuilds are byte-stable and diffs show only real content changes.

Usage:
    python -m build.to_freeshow
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from build.model import Hymn, Section

SOURCE      = Path(__file__).parent.parent / "source"
DIST        = Path(__file__).parent.parent / "dist"
SHOWS_DIR   = DIST / "shows"
PROJECT_OUT = DIST / "ReformationHymnal.project"

# FreeShow category ID for all hymns.
# FreeShow derives IDs as: name.toLowerCase().replaceAll(" ", "_")
# So this matches a category the user creates named "Reformation Hymnal".
CATEGORY_ID = "reformation_hymnal"

# Default item bounding box -- matches FreeShow's native SPS import output.
_ITEM_STYLE = "top:88px;left:50px;height:904px;width:1820px;"

# Per-slide reference label ("26 · Verse 1 of 4"), small, top-right corner.
# A separate, independently styled item so it can be restyled/removed in FreeShow.
_REF_STYLE = "top:30px;left:1170px;height:60px;width:700px;"
_REF_TEXT  = "font-size:40px;"
_REF_ALIGN = "text-align:right;"

# End-of-song marker, centered below the lyrics (parity with SoftProjector's "* * *").
_END_STYLE = "top:1000px;left:50px;height:70px;width:1820px;"
_END_TEXT  = "font-size:60px;"
_END_ALIGN = "text-align:center;"
_END_GLYPH = "* * *"


def _show_id(hymn_num: int) -> str:
    return f"h{hymn_num:03d}"


def _slide_id(hymn_num: int, section_index: int) -> str:
    return f"h{hymn_num:03d}s{section_index:02d}"


def _layout_id(hymn_num: int) -> str:
    return f"h{hymn_num:03d}l00"


def _group_label(s: Section, verse_num: int) -> str:
    if s.kind == "verse":
        return f"Verse {verse_num}"
    if s.kind in ("chorus", "refrain"):
        return "Chorus"
    return s.kind.capitalize()


def _text_item(style: str, align: str, text_style: str, value: str) -> dict:
    """A single-line text item following FreeShow's item shape."""
    return {
        "style": style,
        "lines": [{"align": align, "text": [{"style": text_style, "value": value}]}],
    }


def _build_show(hymn: Hymn) -> dict:
    slides: dict[str, dict] = {}
    layout_slides: list[dict] = []

    verse_count = sum(1 for s in hymn.sections if s.kind == "verse")

    verse_num = 0
    for i, s in enumerate(hymn.sections):
        if s.kind == "verse":
            verse_num += 1
        sid = _slide_id(hymn.number, i)

        # Reference label: verses carry the "of M" count; other sections don't.
        if s.kind == "verse":
            ref_label = f"Verse {verse_num} of {verse_count}"
        else:
            ref_label = _group_label(s, verse_num)

        slides[sid] = {
            "group":    _group_label(s, verse_num),
            "color":    None,
            "settings": {},
            "notes":    "",
            "items": [
                {
                    "style": _ITEM_STYLE,
                    "lines": [
                        {"align": "", "text": [{"style": "", "value": line}]}
                        for line in s.lines
                    ],
                },
                _text_item(
                    _REF_STYLE, _REF_ALIGN, _REF_TEXT,
                    f"{hymn.number} · {ref_label}",
                ),
            ],
        }
        layout_slides.append({"id": sid})

    # End-of-song marker on the true last slide (layout order == section order).
    if layout_slides:
        last_sid = layout_slides[-1]["id"]
        slides[last_sid]["items"].append(
            _text_item(_END_STYLE, _END_ALIGN, _END_TEXT, _END_GLYPH)
        )

    lid = _layout_id(hymn.number)
    return {
        "name":        hymn.title,
        "origin":      None,
        "private":     False,
        "category":    CATEGORY_ID,
        "settings":    {"activeLayout": lid, "template": None},
        "timestamps":  {"created": None, "modified": None, "used": None},
        "quickAccess": {"number": hymn.number},
        "meta": {
            "number":   hymn.number,
            "title":    hymn.title,
            "author":   hymn.author or "",
            "composer": hymn.composer or "",
            "note":     hymn.copyright or "",
            "key":      "",
        },
        "slides":  slides,
        "layouts": {
            lid: {
                "name":   "Default",
                "notes":  "",
                "slides": layout_slides,
            }
        },
        "media": {},
    }


def main() -> int:
    DIST.mkdir(exist_ok=True)
    SHOWS_DIR.mkdir(exist_ok=True)

    paths = sorted(SOURCE.glob("*.hymn"))
    now_ms = int(time.time() * 1000)

    shows_map: dict[str, dict] = {}
    project_show_refs: list[dict] = []

    for i, path in enumerate(paths):
        hymn = Hymn.load(path)
        show = _build_show(hymn)
        sid  = _show_id(hymn.number)

        # Individual .show file
        (SHOWS_DIR / f"{hymn.number:03d}.show").write_text(
            json.dumps(show, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        shows_map[sid] = show
        project_show_refs.append({"id": sid, "index": i})

    # .project bundle (plain JSON, matching FreeShow native export format)
    data_json = {
        "project": {
            "name":    "Reformation Hymnal",
            "created": now_ms,
            "parent":  "/",
            "shows":   project_show_refs,
        },
        "parentFolder": "",
        "shows": shows_map,
        "files": [],
    }

    PROJECT_OUT.write_text(
        json.dumps(data_json, ensure_ascii=False), encoding="utf-8"
    )

    project_kb = PROJECT_OUT.stat().st_size // 1024
    print(f"Written {PROJECT_OUT}  ({len(paths)} hymns, {project_kb} KB)")
    print(f"Written {SHOWS_DIR}/   ({len(paths)} individual .show files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
