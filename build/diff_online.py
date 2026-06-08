"""
build/diff_online.py
====================
Compare source/*.hymn lyrics against the online hymnal JSON and produce a
single, self-contained HTML file at dist/diff.html.

The report has:
  - A summary table (all 700 hymns, ✓ for matches, linked diff-count for mismatches)
  - A per-hymn diff section for each hymn whose lyrics differ after normalisation

Normalisation before comparison:
  - Curly/smart quotes folded to ASCII single and double quotes
  - Leading/trailing whitespace stripped per line

Usage:
    python -m build.diff_online
"""

from __future__ import annotations

import difflib
import html
import json
import sys
from datetime import date
from pathlib import Path

from build.model import Hymn

SOURCE = Path(__file__).parent.parent / "source"
REF = Path(__file__).parent.parent / "reference" / "rh_online.json"
DIST = Path(__file__).parent.parent / "dist"
OUT = DIST / "diff.html"

# Curly-quote → ASCII mapping
_QUOTE_TABLE = str.maketrans({
    "‘": "'",  # left single
    "’": "'",  # right single / apostrophe
    "“": '"',  # left double
    "”": '"',  # right double
})


def _norm(line: str) -> str:
    return line.translate(_QUOTE_TABLE).strip()


def _source_lyrics(hymn: Hymn) -> list[str]:
    """Verse lines in order, then the first chorus block (once)."""
    verse_lines: list[str] = []
    chorus_lines: list[str] = []
    chorus_seen = False
    for s in hymn.sections:
        if s.kind == "verse":
            verse_lines.extend(s.lines)
        elif s.kind == "chorus" and not chorus_seen:
            chorus_lines = list(s.lines)
            chorus_seen = True
    return verse_lines + chorus_lines


def _online_lyrics(h: dict) -> list[str]:
    """Verse lines in order, then refrain lines."""
    lines: list[str] = []
    for verse in h["stanzas"].get("verses", []):
        lines.extend(verse)
    lines.extend(h["stanzas"].get("refrain") or [])
    return lines


def _diff_lines(src: list[str], online: list[str]) -> list[str]:
    """Return a list of ndiff opcodes for display. Empty → identical."""
    src_n = [_norm(l) for l in src]
    online_n = [_norm(l) for l in online]
    if src_n == online_n:
        return []
    return list(difflib.ndiff(src_n, online_n))


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------

_DIFFLIB_CSS = """\
table.diff {border-collapse:collapse;font-family:monospace;font-size:13px;width:100%}
table.diff thead th {background:#e8e8e8;padding:4px 8px;text-align:left;border:1px solid #ccc}
table.diff tbody td {padding:3px 8px;border:1px solid #ddd;vertical-align:top;white-space:pre-wrap;word-break:break-word}
td.diff_header {background:#e8e8e8;text-align:right;width:3em;color:#666}
.diff_add {background:#d4edda}
.diff_chg {background:#fff3cd}
.diff_sub {background:#f8d7da}
"""

_PAGE_CSS = """\
body {font-family:system-ui,sans-serif;margin:0;padding:1rem 2rem;background:#fafafa}
h1 {margin-bottom:0.2em}
p.meta {color:#555;margin-top:0.2em}
h2 {border-bottom:2px solid #ccc;padding-bottom:0.2em}
h3 {margin-top:2em;font-size:1.1em}
table.summary {border-collapse:collapse;width:100%;margin-bottom:1.5em}
table.summary th {background:#333;color:#fff;padding:6px 10px;text-align:left}
table.summary td {padding:5px 10px;border-bottom:1px solid #ddd}
table.summary tr:hover td {background:#f0f0f0}
.ok {color:green;font-weight:bold}
.diff-count {color:#c00;font-weight:bold}
.hymn-diff {margin-bottom:2.5em}
"""


def _summary_row(num: int, title: str, n_diffs: int) -> str:
    if n_diffs == 0:
        status = '<span class="ok">&#10003;</span>'
    else:
        status = f'<a class="diff-count" href="#h{num}">{n_diffs} line(s)</a>'
    return (
        f"<tr><td>{num}</td>"
        f"<td>{html.escape(title)}</td>"
        f"<td>{status}</td></tr>\n"
    )


def _hymn_diff_section(num: int, title: str, src_lines: list[str], online_lines: list[str]) -> str:
    differ = difflib.HtmlDiff(wrapcolumn=80)
    table = differ.make_table(
        [_norm(l) for l in src_lines],
        [_norm(l) for l in online_lines],
        fromdesc="source/.hymn",
        todesc="online JSON",
        context=True,
        numlines=2,
    )
    return (
        f'<div id="h{num}" class="hymn-diff">\n'
        f"<h3>{num}. {html.escape(title)}</h3>\n"
        f"{table}\n"
        f"</div>\n"
    )


def build_html(results: list[tuple[int, str, list[str], list[str], int]]) -> str:
    n_match = sum(1 for *_, n in results if n == 0)
    n_diff = len(results) - n_match

    summary_rows = "".join(
        _summary_row(num, title, n_diffs)
        for num, title, _, _, n_diffs in results
    )

    diff_sections = "".join(
        _hymn_diff_section(num, title, src, online)
        for num, title, src, online, n_diffs in results
        if n_diffs > 0
    )

    today = date.today().isoformat()
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Reformation Hymnal — Lyrics Diff</title>
<style>
{_DIFFLIB_CSS}
{_PAGE_CSS}
</style>
</head>
<body>
<h1>Reformation Hymnal &#8212; Source vs Online Reference</h1>
<p class="meta">Generated {today} &nbsp;|&nbsp;
  <strong>{n_match}</strong> hymns match &nbsp;|&nbsp;
  <strong>{n_diff}</strong> hymns differ</p>

<h2>Summary</h2>
<table class="summary">
<thead><tr><th>#</th><th>Title</th><th>Status</th></tr></thead>
<tbody>
{summary_rows}</tbody>
</table>

<h2>Differences</h2>
{diff_sections if diff_sections else "<p><em>No differences found.</em></p>"}
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    if not REF.exists():
        sys.exit(f"Reference JSON not found: {REF}\nRun: python -m build.fetch_online")

    data = json.loads(REF.read_text(encoding="utf-8"))
    online_by_num: dict[int, dict] = {int(h["num"]): h for h in data["hymns"]}

    results: list[tuple[int, str, list[str], list[str], int]] = []
    missing_from_online = []

    for path in sorted(SOURCE.glob("*.hymn")):
        hymn = Hymn.load(path)
        online = online_by_num.get(hymn.number)
        if online is None:
            missing_from_online.append(hymn.number)
            continue

        src = _source_lyrics(hymn)
        onl = _online_lyrics(online)
        diffs = _diff_lines(src, onl)
        # count only changed/added/removed lines (not context lines)
        n_diffs = sum(1 for l in diffs if l.startswith(("+ ", "- ", "? ")))
        results.append((hymn.number, hymn.title, src, onl, n_diffs))

    if missing_from_online:
        print(f"WARNING: {len(missing_from_online)} source hymns not found in online data: "
              f"{missing_from_online[:5]}{'...' if len(missing_from_online) > 5 else ''}")

    DIST.mkdir(exist_ok=True)
    OUT.write_text(build_html(results), encoding="utf-8")

    n_match = sum(1 for *_, n in results if n == 0)
    n_diff = len(results) - n_match
    print(f"Wrote {OUT}")
    print(f"  {n_match} hymns match, {n_diff} differ")


if __name__ == "__main__":
    main()
