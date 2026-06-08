"""
build/check_pdf.py
==================
Cross-check source/*.hymn against reference/reformation-hymnal.pdf — Phase 3.

Strategy
--------
SoftProjector lyrics pages embed lyrics inside music notation. The notation is
set in the Maestro font; everything else (lyrics, title, attribution) uses News
706 / Palatino. We filter out all Maestro glyphs with pdfplumber's page.filter()
API, leaving clean text we can extract normally.

After filtering:
- Hymn header (section name, number, title, attribution) is stripped.
- Syllable hyphens ("glad - ly", "pro-claims") are collapsed.
- Both sides are normalised to lowercase bare words (no punctuation, quotes
  normalised to apostrophe) before diffing.

The comparison is a *word-frequency* diff (Counter subtraction) rather than a
sequence diff, because the PDF interleaves verses 1/2/3/4 within each music
system, producing a different word order than the source files. Word-frequency
diff catches the differences that matter: a wrong or missing word.

Output
------
Per-hymn Markdown files under dist/reports/pdf-check/NNN.md — but ONLY when
there are discrepancies. Hymns that match cleanly produce no file.

Usage::

    python -m build.check_pdf [--pdf reference/reformation-hymnal.pdf]
                              [--source source/]
                              [--out dist/reports/pdf-check/]
    python -m build.check_pdf --hymn 52   # check just one hymn

    # First run: populate author/composer metadata from the PDF attribution lines.
    # Each hymn page has an attribution line with the author (left-aligned) and
    # composer (right-aligned). Font-filtered word extraction + x-position split
    # gives clean names. Run this, review the diff, commit, then run the check.
    python -m build.check_pdf --enrich    # write author/composer into source/*.hymn
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

try:
    import pdfplumber
except ImportError:
    pdfplumber = None  # type: ignore

from .model import Hymn

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PDF_DEFAULT = Path('reference/reformation-hymnal.pdf')
SOURCE_DEFAULT = Path('source')
OUT_DEFAULT = Path('dist/reports/pdf-check')

# Maestro is the music-notation font; exclude it entirely.
_NOTATION_FONTS = ('Maestro',)

# Lines that are pure structural noise (section headers, "Refrain" label, etc.)
# Matched against the stripped line.
_HEADER_RE = re.compile(
    r"^(?:"
    r"[A-Z'‘’“”0-9\s]+"  # ALL-CAPS section headers
    r"|Refrain\.?"                              # "Refrain" / "Refrain."
    r"|\d+"                                    # bare hymn number
    r")$"
)

# Attribution lines contain: dates in parens, "Tr. by", initials, etc.
_ATTRIB_RE = re.compile(
    r"\(\d{4}[–\-]\d{4}\)"          # date range "(1674-1748)"
    r"|Tr\.\s+by"                    # "Tr. by"
    r"|\bAnon(?:ymous)?\b"
    r"|\bAttr(?:ibuted)?\b",
    re.I
)

# Verse/refrain prefix at start of a line: "1.", "2.", "R.", "Ch."
_VERSE_PREFIX_RE = re.compile(r'^\s*(?:\d+|R|Ch)\.\s*')

# Syllable hyphens in the PDF: "glad - ly" or "pro-claims" → "gladly"
# We strip a hyphen when it sits between two word characters (with or without spaces).
_SYLLABLE_HYPHEN_RE = re.compile(r'(\w)\s*-\s*(\w)')

# Characters we strip before comparing (everything except letters, digits, apostrophe)
_NOISE_CHARS_RE = re.compile(r"[^\w']", re.UNICODE)

# Curly quotes → plain apostrophe/quote for normalisation
_CURLY_MAP = str.maketrans({
    '‘': "'", '’': "'",
    '“': '"', '”': '"',
})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _not_notation(obj: dict) -> bool:
    """pdfplumber filter: keep everything that is NOT a notation glyph."""
    fontname = obj.get('fontname', '')
    return not any(f in fontname for f in _NOTATION_FONTS)


def _extract_page_text(page) -> str:
    """Return lyric-only text from a single PDF page (Maestro stripped)."""
    filtered = page.filter(_not_notation)
    return filtered.extract_text() or ''


def _normalize_for_title_match(s: str) -> str:
    """Reduce a string to bare lowercase letters/digits for title comparison."""
    return re.sub(r'\W+', '', s).lower()


def _clean_pdf_text(raw: str, title: str | None = None) -> str:
    """
    Remove structural noise (headers, attribution, verse prefixes) from
    the raw extracted text of one or more hymn pages.

    Pass *title* to also strip the hymn title line, which is mixed-case and
    therefore not caught by _HEADER_RE (which only strips ALL-CAPS lines).
    """
    title_norm = _normalize_for_title_match(title) if title else None
    lines = raw.splitlines()
    clean: list[str] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if _HEADER_RE.match(line):
            continue
        if _ATTRIB_RE.search(line):
            continue
        if title_norm and _normalize_for_title_match(line) == title_norm:
            continue
        # Strip verse/refrain prefix
        line = _VERSE_PREFIX_RE.sub('', line).strip()
        if line in ('Refrain', 'Refrain:'):
            continue
        if line:
            clean.append(line)
    return ' '.join(clean)


def _join_syllables(text: str) -> str:
    """Collapse syllable hyphens: "glad - ly" → "gladly", "pro-claims" → "proclaims"."""
    # First collapse multiple consecutive hyphens (e.g. "E - ter - ni - - ty")
    # into a single hyphen so the word-char pattern can then join them.
    text = re.sub(r'\s*-\s*-\s*', ' - ', text)
    # Repeat because collapsing one hyphen may reveal another
    prev = None
    while prev != text:
        prev = text
        text = _SYLLABLE_HYPHEN_RE.sub(r'\1\2', text)
    return text


def _normalize_words(text: str) -> list[str]:
    """Return a list of lowercase bare-words suitable for counting."""
    text = text.translate(_CURLY_MAP)
    text = _join_syllables(text)
    # Remove everything that isn't a word char or apostrophe
    text = _NOISE_CHARS_RE.sub(' ', text)
    return [w.lower() for w in text.split() if w.strip("'")]


def _source_words(hymn: Hymn) -> list[str]:
    """All normalised words from a Hymn's body sections."""
    body = ' '.join(
        line
        for section in hymn.sections
        for line in section.lines
    )
    return _normalize_words(body)


# ---------------------------------------------------------------------------
# Attribution extraction (for --enrich mode)
# ---------------------------------------------------------------------------

# Patterns to strip from raw attribution strings
_DATE_PAREN_RE = re.compile(r'\s*\([^)]*\d{3,4}[^)]*\)')   # (1674-1748), (d. 1793)
_DATE_TRAIL_RE = re.compile(r',?\s*\d{4}[–\-]\d{4}$')       # 1823–1876 at end
_YEAR_TRAIL_RE = re.compile(r',?\s*\d{4}$')                  # , 1561 at end
_SEMICOL_TRAIL_RE = re.compile(r'[;,]+$')


def _clean_attribution(raw: str) -> str | None:
    """Strip dates and punctuation, return the cleaned name or None if empty."""
    s = raw.strip()
    s = _DATE_PAREN_RE.sub('', s)
    s = _DATE_TRAIL_RE.sub('', s)
    s = _YEAR_TRAIL_RE.sub('', s)
    s = _SEMICOL_TRAIL_RE.sub('', s)
    s = s.strip()
    return s if s else None


def _extract_attribution(filtered_page) -> tuple[str | None, str | None]:
    """
    Return (author, composer) from the attribution line of a hymn page.

    The PDF lays out the attribution as:
        [author/words credit]          [composer/music credit]
    left-aligned                       right-aligned

    We split at the page midpoint (x < mid → author, x ≥ mid → composer).
    Font filtering (no Maestro) must already be applied to filtered_page.
    """
    try:
        page_width = filtered_page.width
        mid = page_width / 2
        words = filtered_page.extract_words()
    except Exception:
        return None, None

    # Attribution is in the band top ≈ 55–82pt (below title, above notation)
    attrib = [w for w in words if 55 < w['top'] < 82]
    if not attrib:
        return None, None

    left_text  = ' '.join(w['text'] for w in attrib if w['x0'] < mid)
    right_text = ' '.join(w['text'] for w in attrib if w['x0'] >= mid)

    return _clean_attribution(left_text), _clean_attribution(right_text)


def enrich_metadata(pdf_path: Path, source_dir: Path) -> list[dict]:
    """
    Populate author/composer fields in source/*.hymn from the PDF attribution lines.
    Only fills in fields that are currently empty (never overwrites existing data).
    Returns a list of change records: [{hymn, field, old, new}, ...].
    """
    source_hymns: dict[int, tuple[Path, Hymn]] = {}
    for p in sorted(source_dir.glob('*.hymn')):
        h = Hymn.load(p)
        source_hymns[h.number] = (p, h)

    changes: list[dict] = []

    with pdfplumber.open(str(pdf_path)) as pdf:
        hymn_page_map = build_hymn_page_map(pdf)

        for num, (path, hymn) in sorted(source_hymns.items()):
            pages = hymn_page_map.get(num)
            if not pages:
                continue
            # Only look at the FIRST page of the hymn for the attribution
            first_page = pdf.pages[pages[0]]
            filtered = first_page.filter(_not_notation)
            author, composer = _extract_attribution(filtered)

            changed = False
            if author and not hymn.author:
                changes.append({'hymn': num, 'field': 'author',
                                 'old': None, 'new': author})
                hymn.author = author
                changed = True
            if composer and not hymn.composer:
                changes.append({'hymn': num, 'field': 'composer',
                                 'old': None, 'new': composer})
                hymn.composer = composer
                changed = True
            if changed:
                hymn.save(path)

    return changes


# ---------------------------------------------------------------------------
# PDF page → hymn mapping
# ---------------------------------------------------------------------------

def _find_hymn_number_on_page(page) -> int | None:
    """
    Return the hymn number if this page begins a new hymn, else None.

    Two-pass strategy
    -----------------
    Fast path  — original unfiltered logic with early break on top > 55pt.
                 Handles the majority of pages; Maestro notation characters
                 appear early in the content stream and cause an early break
                 before any false positive can be returned.
    Slow path  — filtered (no Maestro), sorted by top, scans 55–250pt.
                 Needed for section-transition pages where the new hymn
                 number appears below a previous-hymn overhang.
                 The 55pt lower bound skips any volta-bracket numbers that
                 happen to use a non-Maestro font (e.g. top ≈ 37–42pt).
                 Words with x0 ≥ page.width are out-of-bounds artefacts
                 (right-margin numbers from indices or bold decorations)
                 and are rejected.
    """
    # --- Fast path (original logic) ---
    # Works for the vast majority of pages: the hymn number appears in the
    # top 55pt band.  Use unfiltered words so Maestro notation characters that
    # appear early in the content stream cause an early break, which
    # accidentally—but reliably—prevents volta-bracket false positives.
    try:
        words = page.extract_words()
    except Exception:
        return None
    for w in words:
        if w['top'] > 55:
            break
        try:
            n = int(w['text'])
            if 1 <= n <= 700:
                return n
        except ValueError:
            pass

    # --- Slow path (section-transition pages) ---
    # On pages where the previous hymn ends at the top and a new hymn begins
    # further down (e.g. top ~150-200pt), the fast path returns nothing.
    # Use filtered (no-Maestro) words sorted top-to-bottom, scanning 55-250pt,
    # with strict title validation so vera-number false positives are rejected.
    try:
        filtered = page.filter(_not_notation)
        words = filtered.extract_words()
    except Exception:
        return None

    page_width = page.width
    sorted_words = sorted(words, key=lambda w: w['top'])

    for idx, w in enumerate(sorted_words):
        top = w['top']
        if top <= 55:      # already covered by fast path
            continue
        if top > 250:
            break
        if w['x0'] >= page_width:   # reject out-of-bounds artefacts
            continue
        try:
            n = int(w['text'])
            if not (1 <= n <= 700):
                continue
        except ValueError:
            continue

        # Strict title validation: require ≥2 Title-Case words (len > 3)
        # within 20pt.  Verse/doxology numbers with short titles don't pass.
        title_limit = top + 20
        title_words = [
            w2 for w2 in sorted_words[idx + 1:]
            if w2['top'] <= title_limit
            and w2['x0'] < page_width
            and not w2['text'].isupper()
            and not w2['text'].isdigit()
            and len(w2['text']) > 3
            and w2['text'][0].isupper()
        ]
        if len(title_words) >= 2:
            return n

    return None


def build_hymn_page_map(pdf) -> dict[int, list[int]]:
    """
    Return {hymn_number: [page_index, ...]} for every hymn in the PDF.
    Pages without a new hymn number are assigned to the preceding hymn.

    Monotonicity guard: large backward jumps (e.g. detecting "2" after hymn 280)
    are rejected as false positives (volta brackets, verse numbers, index entries).
    Small backward steps (up to 5) are allowed for out-of-order reprints.
    """
    mapping: dict[int, list[int]] = {}
    current: int | None = None
    max_seen: int = 0
    for i, page in enumerate(pdf.pages):
        n = _find_hymn_number_on_page(page)
        if n is not None:
            if n > max_seen or n >= max_seen - 5:
                current = n
                max_seen = max(max_seen, n)
        if current is not None:
            mapping.setdefault(current, []).append(i)
    return mapping


# ---------------------------------------------------------------------------
# Per-hymn comparison
# ---------------------------------------------------------------------------

def _compare(src_words: list[str], pdf_words: list[str]) -> dict:
    """
    Return a dict with keys 'src_only' and 'pdf_only', each a Counter of
    words that appear *more* in one side than the other.
    Ignores: single-letter words, pure-digit tokens, and very short tokens
    (likely PDF artefacts from split syllables).
    """
    def _filter(counter: Counter) -> Counter:
        return Counter({
            w: c for w, c in counter.items()
            if len(w) > 2 and not w.isdigit()
        })

    src = _filter(Counter(src_words))
    pdf = _filter(Counter(pdf_words))

    src_only = src - pdf   # words source has more of than PDF
    pdf_only = pdf - src   # words PDF has more of than source

    return {'src_only': src_only, 'pdf_only': pdf_only}


def _write_report(out_dir: Path, hymn: Hymn, comparison: dict,
                  src_words: list[str], pdf_words: list[str]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f'{hymn.number:03d}.md'

    src_only = comparison['src_only']
    pdf_only = comparison['pdf_only']

    with path.open('w', encoding='utf-8') as f:
        f.write(f'# Hymn {hymn.number}: {hymn.title}\n\n')
        f.write(f'**Source word count:** {len(src_words)}  \n')
        f.write(f'**PDF word count:** {len(pdf_words)}\n\n')

        if src_only:
            f.write('## Words in SOURCE but not (enough) in PDF\n\n')
            for word, diff in sorted(src_only.items()):
                f.write(f'- `{word}` (source: {src_only[word] + (Counter(pdf_words)[word])}, '
                        f'pdf: {Counter(pdf_words).get(word, 0)})\n')
            f.write('\n')

        if pdf_only:
            f.write('## Words in PDF but not (enough) in SOURCE\n\n')
            for word in sorted(pdf_only):
                f.write(f'- `{word}` (source: {Counter(src_words).get(word, 0)}, '
                        f'pdf: {pdf_only[word] + (Counter(src_words)[word])})\n')
            f.write('\n')

        f.write('## DECISION\n\n')
        f.write('<!-- Fill in: ACCEPT (keep source), ADOPT-PDF (update source to match PDF), '
                'or SKIP (artefact/irrelevant) for each discrepancy above. -->\n\n')


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------

def run(pdf_path: Path, source_dir: Path, out_dir: Path,
        only_hymn: int | None = None) -> int:
    if pdfplumber is None:
        print('error: pdfplumber is not installed. Run: pip install pdfplumber', file=sys.stderr)
        return 1
    if not pdf_path.exists():
        print(f'error: PDF not found: {pdf_path}', file=sys.stderr)
        return 1
    if not source_dir.is_dir():
        print(f'error: source directory not found: {source_dir}', file=sys.stderr)
        return 1

    # Load source hymns
    source_hymns: dict[int, Hymn] = {}
    for p in sorted(source_dir.glob('*.hymn')):
        h = Hymn.load(p)
        source_hymns[h.number] = h

    print(f'Loaded {len(source_hymns)} source hymns.')

    with pdfplumber.open(str(pdf_path)) as pdf:
        print(f'Scanning {len(pdf.pages)} PDF pages…')
        hymn_page_map = build_hymn_page_map(pdf)
        print(f'Found {len(hymn_page_map)} hymns in PDF (page map built).')

        hymn_numbers = [only_hymn] if only_hymn else sorted(source_hymns)
        discrepancies = 0

        for num in hymn_numbers:
            hymn = source_hymns.get(num)
            if hymn is None:
                print(f'  hymn {num}: not in source, skipping')
                continue

            page_indices = hymn_page_map.get(num)
            if not page_indices:
                print(f'  hymn {num}: not found in PDF, skipping')
                continue

            # Extract and clean PDF text for this hymn
            raw_parts = [_extract_page_text(pdf.pages[i]) for i in page_indices]
            raw = '\n'.join(raw_parts)
            cleaned = _clean_pdf_text(raw, title=hymn.title)
            pdf_words = _normalize_words(cleaned)

            # Attribution names leak when the PDF line has no date range to flag it.
            # Subtract the known author/composer words (by count) so they don't
            # show up as spurious pdf_only discrepancies.
            if hymn.author or hymn.composer:
                attrib_text = ' '.join(filter(None, [hymn.author, hymn.composer]))
                attrib_counts = Counter(_normalize_words(attrib_text))
                pdf_word_counter = Counter(pdf_words) - attrib_counts
                pdf_words = list(pdf_word_counter.elements())

            src_words = _source_words(hymn)

            comparison = _compare(src_words, pdf_words)

            if comparison['src_only'] or comparison['pdf_only']:
                _write_report(out_dir, hymn, comparison, src_words, pdf_words)
                discrepancies += 1
                if only_hymn:
                    print(f'  hymn {num}: {len(comparison["src_only"])} src-only, '
                          f'{len(comparison["pdf_only"])} pdf-only words')
            else:
                if only_hymn:
                    print(f'  hymn {num}: clean (no discrepancies)')

    total = len(hymn_numbers)
    clean = total - discrepancies
    print(f'\nDone. {clean}/{total} hymns clean. '
          f'{discrepancies} discrepancy report(s) written to {out_dir}/')
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='Cross-check source hymns against the PDF.')
    ap.add_argument('--pdf', default=str(PDF_DEFAULT), help='Path to the PDF')
    ap.add_argument('--source', default=str(SOURCE_DEFAULT), help='Source directory')
    ap.add_argument('--out', default=str(OUT_DEFAULT), help='Report output directory')
    ap.add_argument('--hymn', type=int, default=None,
                    help='Check only this hymn number (for testing)')
    ap.add_argument('--enrich', action='store_true',
                    help='Populate author/composer from PDF attribution lines '
                         '(only fills empty fields). Review git diff before committing.')
    args = ap.parse_args(argv)

    if pdfplumber is None:
        print('error: pdfplumber is not installed. Run: pip install -e ".[pdf]"',
              file=sys.stderr)
        return 1

    pdf_path = Path(args.pdf)
    source_dir = Path(args.source)

    if not pdf_path.exists():
        print(f'error: PDF not found: {pdf_path}', file=sys.stderr)
        return 1
    if not source_dir.is_dir():
        print(f'error: source directory not found: {source_dir}', file=sys.stderr)
        return 1

    if args.enrich:
        print(f'Enriching author/composer metadata from {pdf_path} …')
        changes = enrich_metadata(pdf_path, source_dir)
        if not changes:
            print('No changes made (all author/composer fields already populated).')
        else:
            by_hymn: dict[int, list] = {}
            for c in changes:
                by_hymn.setdefault(c['hymn'], []).append(c)
            print(f'\nUpdated {len(by_hymn)} hymn(s), {len(changes)} field(s):')
            for num in sorted(by_hymn):
                for c in by_hymn[num]:
                    print(f'  hymn {num:03d}: {c["field"]} = {c["new"]!r}')
            print('\nReview with: git diff source/')
            print('Then commit: git add source/ && git commit -m "feat: populate author/composer from PDF"')
        return 0

    return run(
        pdf_path=pdf_path,
        source_dir=source_dir,
        out_dir=Path(args.out),
        only_hymn=args.hymn,
    )


if __name__ == '__main__':
    raise SystemExit(main())
