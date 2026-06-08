"""
build/clean.py
==============
Semi-automated cleanup passes for source/*.hymn — Phase 2.

Two independent, separately-runnable passes:

1. Curly-quote pass  (python -m build.clean --pass quotes)
   Converts straight quotes/apostrophes to typographic equivalents.
   Writes changes to source/ in place and emits a report to
   dist/reports/quotes.txt for human review before committing.

2. Line-break pass   (python -m build.clean --pass linebreaks)
   Proposes re-joins of PDF-wrapped lines based on heuristics and meter.
   Writes proposals to dist/reports/linebreaks/NNN.diff — NEVER auto-applies.
   (Phase 2 later — not yet implemented.)

Usage::

    python -m build.clean --pass quotes [--source source/] [--report dist/reports/quotes.txt]
    python -m build.clean --pass quotes --dry-run   # report only, no writes
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .model import Hymn

# ---------------------------------------------------------------------------
# Unicode quote characters
# ---------------------------------------------------------------------------

LDQUOTE = '“'   # "  left double quotation mark
RDQUOTE = '”'   # "  right double quotation mark
RSQUOTE = '’'   # '  right single quotation mark (apostrophe)
LSQUOTE = '‘'   # '  left single quotation mark

# Characters that indicate the preceding context is "open" (→ next " is opening)
_OPEN_AFTER = frozenset(' \t\n([{“‘')

# Elision words whose initial apostrophe must be a right single quote (not left).
# Add to this list if more are found in the corpus.
_ELISIONS = frozenset([
    'tis', 'twas', 'tween', 'twixt', 'til', 'till',
    'neath', 'gainst', 'round', 'bout', 'em', 'ere',
    'midst', 'mongst',
])


# ---------------------------------------------------------------------------
# Per-change record
# ---------------------------------------------------------------------------

@dataclass
class Change:
    path: Path
    location: str   # e.g. "[verse 1]:3" or "title"
    old: str        # the straight-quote character(s) replaced
    new: str        # what they became
    context: str    # surrounding snippet for the report
    kind: str       # 'apostrophe' | 'open-double' | 'close-double'


# ---------------------------------------------------------------------------
# Core conversion — operates on a plain string
# ---------------------------------------------------------------------------

def _convert(s: str, path: Path, location: str) -> tuple[str, list[Change]]:
    """
    Convert straight quotes in string *s*.

    Rules:
    - ``"``  → opening or closing curly double quote (position-based).
    - ``'``  → right single quote (apostrophe), universally in hymn text.
              This is correct for mid-word contractions ('s, 'll, o'er, heav'n)
              AND for word-initial elisions ('tis, 'twas, 'neath) — both use the
              RIGHT quote.  Genuine opening single quotation marks don't appear in
              this corpus.
    - Already-curly characters are left untouched.
    """
    out: list[str] = []
    changes: list[Change] = []
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == '"':
            prev = s[i - 1] if i > 0 else ' '
            if i == 0 or prev in _OPEN_AFTER:
                new, kind = LDQUOTE, 'open-double'
            else:
                new, kind = RDQUOTE, 'close-double'
            snippet = s[max(0, i - 8):i + 9].replace('\n', '↵')
            changes.append(Change(path, location, ch, new, snippet, kind))
            out.append(new)
        elif ch == "'":
            snippet = s[max(0, i - 8):i + 9].replace('\n', '↵')
            changes.append(Change(path, location, ch, RSQUOTE, snippet, 'apostrophe'))
            out.append(RSQUOTE)
        else:
            out.append(ch)
        i += 1
    return ''.join(out), changes


# ---------------------------------------------------------------------------
# File-level pass
# ---------------------------------------------------------------------------

def _process_file(path: Path) -> list[Change]:
    """
    Load a .hymn file, apply curly-quote conversion to metadata values and
    body lines, save in place. Return the list of changes made.
    """
    hymn = Hymn.load(path)
    all_changes: list[Change] = []

    # ---- metadata string fields ----
    # We convert ' → ' in all string values.
    # We do NOT convert " in metadata because the title field sometimes contains
    # speech markers that are already handled by the model's YAML serialiser.
    # Exception: we DO convert " inside string values (not the YAML delimiters —
    # those are stripped by the parser before we see the value).
    for attr in ('title', 'author', 'composer', 'tune', 'subject', 'copyright', 'notes'):
        val = getattr(hymn, attr)
        if isinstance(val, str) and val:
            new_val, changes = _convert(val, path, attr)
            if new_val != val:
                setattr(hymn, attr, new_val)
                all_changes.extend(changes)

    for key, val in list(hymn.extra.items()):
        if isinstance(val, str) and val:
            new_val, changes = _convert(val, path, f'extra:{key}')
            if new_val != val:
                hymn.extra[key] = new_val
                all_changes.extend(changes)

    # ---- body lines ----
    for section in hymn.sections:
        new_lines: list[str] = []
        for idx, line in enumerate(section.lines, 1):
            new_line, changes = _convert(line, path, f'{section.header()}:{idx}')
            new_lines.append(new_line)
            all_changes.extend(changes)
        section.lines = new_lines

    if all_changes:
        hymn.save(path)

    return all_changes


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def _write_report(report_path: Path, all_changes: list[Change], modified: list[Path]) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)

    apostrophes = [c for c in all_changes if c.kind == 'apostrophe']
    doubles = [c for c in all_changes if c.kind in ('open-double', 'close-double')]

    with report_path.open('w', encoding='utf-8') as f:
        f.write("Curly-quote substitution report\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"Files modified  : {len(modified)}\n")
        f.write(f"Total changes   : {len(all_changes)}\n")
        f.write(f"  apostrophes   : {len(apostrophes)}\n")
        f.write(f"  double quotes : {len(doubles)}\n\n")

        if doubles:
            f.write("Double-quote conversions (verify opening vs closing is correct)\n")
            f.write("-" * 60 + "\n")
            cur_file = None
            for c in doubles:
                if c.path != cur_file:
                    f.write(f"\n{c.path.name}\n")
                    cur_file = c.path
                arrow = LDQUOTE if c.kind == 'open-double' else RDQUOTE
                f.write(f"  [{c.location}] {c.kind}: …{c.context}…  →  '{arrow}'\n")
            f.write("\n")

        f.write("Apostrophe changes by file\n")
        f.write("-" * 60 + "\n")
        by_file: dict[Path, int] = {}
        for c in apostrophes:
            by_file[c.path] = by_file.get(c.path, 0) + 1
        for path, count in sorted(by_file.items(), key=lambda x: x[0].name):
            f.write(f"  {path.name}: {count} apostrophe(s)\n")

    print(f"Report written to {report_path}")


# ---------------------------------------------------------------------------
# Passes
# ---------------------------------------------------------------------------

def quotes_pass(source_dir: Path, report_path: Path, dry_run: bool = False) -> int:
    all_changes: list[Change] = []
    modified: list[Path] = []

    for path in sorted(source_dir.glob('*.hymn')):
        if dry_run:
            # Load and detect changes without writing
            hymn = Hymn.load(path)
            # We re-use _process_file logic but on a temp copy
            changes = _detect_changes(path)
        else:
            changes = _process_file(path)

        if changes:
            all_changes.extend(changes)
            modified.append(path)

    _write_report(report_path, all_changes, modified)
    print(f"{'[dry-run] ' if dry_run else ''}Modified {len(modified)} files, {len(all_changes)} substitutions.")
    return 0


def _detect_changes(path: Path) -> list[Change]:
    """Like _process_file but does not write anything."""
    hymn = Hymn.load(path)
    all_changes: list[Change] = []
    for attr in ('title', 'author', 'composer', 'tune', 'subject', 'copyright', 'notes'):
        val = getattr(hymn, attr)
        if isinstance(val, str) and val:
            _, changes = _convert(val, path, attr)
            all_changes.extend(changes)
    for key, val in hymn.extra.items():
        if isinstance(val, str) and val:
            _, changes = _convert(val, path, f'extra:{key}')
            all_changes.extend(changes)
    for section in hymn.sections:
        for idx, line in enumerate(section.lines, 1):
            _, changes = _convert(line, path, f'{section.header()}:{idx}')
            all_changes.extend(changes)
    return all_changes


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Cleanup passes for source/*.hymn")
    ap.add_argument('--pass', dest='pass_name', required=True,
                    choices=['quotes', 'linebreaks'],
                    help='Which pass to run')
    ap.add_argument('--source', default='source',
                    help='Source directory (default: source/)')
    ap.add_argument('--report', default=None,
                    help='Report output path (default: dist/reports/<pass>.txt)')
    ap.add_argument('--dry-run', action='store_true',
                    help='Report changes without modifying files')
    args = ap.parse_args(argv)

    source_dir = Path(args.source)
    if not source_dir.is_dir():
        print(f"error: source directory not found: {source_dir}", file=sys.stderr)
        return 1

    if args.pass_name == 'quotes':
        report_path = Path(args.report or 'dist/reports/quotes.txt')
        return quotes_pass(source_dir, report_path, dry_run=args.dry_run)

    if args.pass_name == 'linebreaks':
        raise NotImplementedError("linebreaks pass is Phase 2 (later) — not yet implemented")

    return 1


if __name__ == '__main__':
    raise SystemExit(main())
