"""
build/apply_online.py
=====================
Apply online JSON lyrics to all source/*.hymn files (the "accept online" step),
with per-hymn exception patches for cases where our source is intentionally
different, then generate dist/online-diff-report.md for the online maintainers.

Strategy per hymn:
  - Replace each [verse N] section's lines with online verse N's lines
  - Replace each [chorus] section's lines with the online refrain's lines
  - Keep the SOURCE structure (section order, chorus placement)
  - Apply hardcoded patches for the 7 exception hymns

Hymns left untouched (SKIP):
  586 - user manually corrected; online chorus has "love" where "joy" is correct
  619 - source already has correct verse structure; online inverts verse/refrain order

Usage:
    python -m build.apply_online --dry-run   # preview, no files written
    python -m build.apply_online             # apply and generate report
"""

from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Callable

from build.model import Hymn

SOURCE = Path(__file__).parent.parent / "source"
REF    = Path(__file__).parent.parent / "reference" / "rh_online.json"
DIST   = Path(__file__).parent.parent / "dist"
REPORT = DIST / "online-diff-report.md"

SKIP = {586, 619, 659}


# ---------------------------------------------------------------------------
# Core apply
# ---------------------------------------------------------------------------

def _apply(hymn: Hymn, onl: dict) -> list[str]:
    """Replace verse/chorus lines with online counterparts in-place."""
    o_verses  = onl["stanzas"].get("verses")  or []
    o_refrain = onl["stanzas"].get("refrain") or []
    warnings: list[str] = []
    vi = 0
    for s in hymn.sections:
        if s.kind == "verse":
            if vi < len(o_verses):
                s.lines = list(o_verses[vi])
                vi += 1
            else:
                warnings.append(
                    f"Hymn {hymn.number}: verse {vi + 1} has no online counterpart -- kept source"
                )
        elif s.kind == "chorus":
            if o_refrain:
                s.lines = list(o_refrain)
    if vi < len(o_verses):
        warnings.append(
            f"Hymn {hymn.number}: online has {len(o_verses)} verses, "
            f"source has {vi} verse section(s) -- extra online verses not added"
        )
    return warnings


# ---------------------------------------------------------------------------
# Exception patches
# ---------------------------------------------------------------------------

def _patch_27(h: Hymn, orig: Hymn) -> None:
    """V3 line 2: retain 'Let Thy congregation escape tribulation,'"""
    verses = [s for s in h.sections    if s.kind == "verse"]
    ovrs   = [s for s in orig.sections if s.kind == "verse"]
    verses[2].lines[2] = ovrs[2].lines[2]


def _patch_66(h: Hymn, orig: Hymn) -> None:
    # V1 l5: comma stays before closing quote (King,") | V3: fix "be side" typo
    # King," line: restore from source (curly-quote regex is fragile)
    h_vs   = [s for s in h.sections    if s.kind == "verse"]
    orig_vs = [s for s in orig.sections if s.kind == "verse"]
    h_vs[0].lines[5] = orig_vs[0].lines[5]
    # "be side" typo: plain string replace is fine (ASCII-safe)
    for s in h.sections:
        for i, line in enumerate(s.lines):
            if 'be side' in line:
                s.lines[i] = line.replace('be side', 'beside')


def _patch_71(h: Hymn, orig: Hymn) -> None:
    """V2 l2: 'she lifteth' not 'is lifteth' (second-edition typo in online)"""
    for s in h.sections:
        for i, line in enumerate(s.lines):
            if 'is lifteth' in line:
                s.lines[i] = line.replace('is lifteth', 'she lifteth')


def _patch_177(h: Hymn, orig: Hymn) -> None:
    """V2 lines 2-3: 'blessings, and' stays at line-end (not moved to start next)"""
    verses = [s for s in h.sections    if s.kind == "verse"]
    ovrs   = [s for s in orig.sections if s.kind == "verse"]
    verses[1].lines[2] = ovrs[1].lines[2]   # I go to Him for blessings, and
    verses[1].lines[3] = ovrs[1].lines[3]   # He gives them o'er and o'er.


def _patch_183(h: Hymn, orig: Hymn) -> None:
    """Restore source chorus format -- parentheticals inline, not reformatted."""
    orig_ch = next(s for s in orig.sections if s.kind == "chorus")
    for s in h.sections:
        if s.kind == "chorus":
            s.lines = list(orig_ch.lines)


def _patch_209(h: Hymn, orig: Hymn) -> None:
    """V3 lines 0-1: 'I' stays at line-end, not pushed to start of next line."""
    verses = [s for s in h.sections    if s.kind == "verse"]
    ovrs   = [s for s in orig.sections if s.kind == "verse"]
    verses[2].lines[0] = ovrs[2].lines[0]   # Since nothing good have I
    verses[2].lines[1] = ovrs[2].lines[1]   # Whereby Thy grace to claim,


def _patch_318(h: Hymn, orig: Hymn) -> None:
    """Keep punctuation inside closing quotes on all 'We would see Jesus' lines."""
    # Restore line 0 of each verse directly from source -- no curly-quote regex needed
    h_vs    = [s for s in h.sections    if s.kind == "verse"]
    orig_vs = [s for s in orig.sections if s.kind == "verse"]
    for hv, ov in zip(h_vs, orig_vs):
        hv.lines[0] = ov.lines[0]


PATCHES: dict[int, Callable[[Hymn, Hymn], None]] = {
    27: _patch_27, 66: _patch_66, 71: _patch_71,
    177: _patch_177, 183: _patch_183, 209: _patch_209,
    318: _patch_318,
}


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def _report(online_by_num: dict) -> str:
    lines: list[str] = [
        "# Reformation Hymnal -- Notes for Online Maintainers",
        "",
        "This report documents places where the Reformation Hymnal plain-text",
        "source intentionally diverges from the online hymnal at",
        "hymnal.sdarm.org/rh, with notes explaining each difference.",
        "",
        f"Generated: {date.today().isoformat()}  ",
        f"Reference: `reformation-hymnal-v2.json`",
        "",
        "---",
        "",
    ]

    def section(num, title, body_lines):
        lines.append(f"## Hymn {num}: {title}")
        lines.append("")
        lines.extend(body_lines)
        lines.append("")
        lines.append("---")
        lines.append("")

    # 27
    section(27, "We Gather Together", [
        "**Verse 3, line 3**",
        "",
        "| Our source (first edition) | Online version |",
        "|---|---|",
        "| `Let Thy congregation escape tribulation,` | `Help Thy congregation endure tribulation;` |",
        "",
        '**Note:** "escape" is the original first-edition wording. "Help ... endure" appears',
        "to be a later editorial change. We retain the first-edition text.",
    ])

    # 52
    h52 = Hymn.load(SOURCE / "052.hymn")
    section(52, h52.title, [
        f"**Author attribution:** Our source credits `{h52.author}` as author.",
        "",
        "**Note:** Please verify this attribution. The online hymnal does not currently",
        "list an author for this hymn.",
    ])

    # 66
    section(66, "It Came Upon the Midnight Clear", [
        "**Verse 1, line 6 -- quotation-mark placement**",
        "",
        "| Our source | Online version |",
        "|---|---|",
        '| `From heaven\'s all-gracious King,"` | `From heaven\'s all-gracious King",` |',
        "",
        "**Note:** We retain the first-edition convention of placing the comma inside the",
        "closing quotation mark.",
        "",
        "**Verse 3 -- possible typo in online**",
        "",
        "| Our source | Online version |",
        "|---|---|",
        '| `O rest beside the weary road,` | `O rest be side the weary road,` |',
        "",
        '**Note:** "be side" (two words) appears to be a typo for "beside".',
    ])

    # 71
    section(71, "O Word of God Incarnate", [
        "**Verse 2, line 3 -- pronoun**",
        "",
        "| Our source (first edition) | Online version |",
        "|---|---|",
        '| `And still that light she lifteth` | `And still that light is lifteth` |',
        "",
        '**Note:** "is lifteth" is grammatically anomalous and appears to be a typo',
        'introduced in the second edition. The first-edition reading "she lifteth"',
        "(referring to 'the church' in the previous stanza) is grammatically correct.",
    ])

    # 177
    section(177, "Jesus Is All the World to Me", [
        "**Verse 2, lines 3-4 -- line break**",
        "",
        "| Our source | Online version |",
        "|---|---|",
        '| `I go to Him for blessings, and` | `I go to Him for blessings,` |',
        '| `He gives them o\'er and o\'er.` | `And He gives them o\'er and o\'er.` |',
        "",
        '**Note:** The word "and" concludes the third line as sung; moving it to begin',
        "the fourth line (capitalized) disrupts the natural phrasing.",
    ])

    # 183
    section(183, "Oh, the Best Friend to Have Is Jesus", [
        "**Chorus lines 2-3 -- parenthetical format**",
        "",
        "| Our source | Online version |",
        "|---|---|",
        '| `The best friend to have is Jesus (every day);` | `The best friend to have is Jesus; (Jesus every day),` |',
        '| `The best friend to have is Jesus (all the way);` | `The best friend to have is Jesus; (Jesus all the way),` |',
        "",
        "**Note:** We retain the parentheticals inline with their line. This format is",
        "clearer for projection use where singers may not have sheet music. The inline",
        '"every day" / "all the way" serves as a sung cue.',
    ])

    # 209
    section(209, "I Hear the Saviour Say", [
        "**Verse 3, lines 1-2 -- line break**",
        "",
        "| Our source | Online version |",
        "|---|---|",
        '| `Since nothing good have I` | `Since nothing good have` |',
        '| `Whereby Thy grace to claim,` | `I Whereby Thy grace to claim,` |',
        "",
        '**Note:** "I" belongs at the end of the first line as sung. Beginning the next',
        'line with "I Whereby" appears to be a line-break error.',
    ])

    # 318
    section(318, "We Would See Jesus", [
        "**All four verses, line 1 -- quotation-mark and punctuation placement**",
        "",
        "| Our source | Online version |",
        "|---|---|",
        '| `"We would see Jesus;" for the shadows lengthen` | `"We would see Jesus"; for the shadows lengthen` |',
        '| `"We would see Jesus," Rock of our salvation,` | `"We would see Jesus", Rock of our salvation,` |',
        '| `"We would see Jesus;" other lights are paling,` | `"We would see Jesus"; other lights are paling,` |',
        '| `"We would see Jesus;" this is all we\'re needing` | `"We would see Jesus"; this is all we\'re needing` |',
        "",
        "**Note:** We follow the first-edition convention of placing punctuation inside",
        "the closing quotation mark throughout this hymn.",
    ])

    # 586
    h586 = Hymn.load(SOURCE / "586.hymn")
    onl586_refrain = online_by_num[586]["stanzas"].get("refrain") or []
    section(586, h586.title, [
        "**Chorus/refrain line 2 -- possible error in online**",
        "",
        "| Our source | Online version |",
        "|---|---|",
        f'| `{h586.sections[1].lines[1]}` | `{onl586_refrain[1] if len(onl586_refrain) > 1 else ""}` |',
        "",
        '**Note:** Online refrain line 2 reads "He gives me **love** in place of care".',
        'We believe this should be "**joy**" -- parallel with line 1 ("He gives me joy',
        'in place of sorrow"). "love" appears to be an editorial error.',
        "",
        "**Also:** Our source retains the parenthetical format used throughout the chorus:",
        "`(He gives me joy in place of care);` rather than `(He gives me love in place of care;)`",
    ])

    # 619
    section(619, "All Things Bright and Beautiful", [
        "**Structure -- verse vs. refrain ordering**",
        "",
        "The online version presents this hymn with 4 verses and a separate refrain",
        '("All things bright and beautiful, / All creatures great and small...").',
        "",
        "Our source presents 5 verses with the refrain text as verse 1, followed by",
        "the body verses as verses 2-5. This matches how the hymn is sung (the refrain",
        "functions as a recurring verse) and how it appears in the printed hymnal.",
        "",
        "The text of all stanzas is identical between the two versions.",
    ])

    # 659
    section(659, "Awake, My Soul, to Joyful Lays", [
        "**Refrain -- last line should vary by verse**",
        "",
        "The online version provides a single fixed refrain for all four verses:",
        "",
        "| | Refrain last line |",
        "|---|---|",
        "| Online (all verses) | `His loving kindness, O, how good!` |",
        "",
        "Our source has the refrain last line echo the last line of each verse:",
        "",
        "| Verse | Our refrain last line |",
        "|---|---|",
        "| V1 | `His loving-kindness, O, how free!` |",
        "| V2 | `His loving-kindness, O, how great!` |",
        "| V3 | `His loving-kindness, O, how good!` |",
        "| V4 | `His loving-kindness, evermore.` |",
        "",
        '**Note:** The online version provides a single refrain ending "O, how good!"',
        "for all verses. The correct performance has the refrain echo the closing line",
        "of each verse: 'how free!' after verse 1, 'how great!' after verse 2,",
        "'how good!' after verse 3, and 'evermore.' after verse 4.",
    ])

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(dry_run: bool = False) -> None:
    if not REF.exists():
        sys.exit(f"Reference JSON not found: {REF}\nRun: python -m build.fetch_online")

    data = json.loads(REF.read_text(encoding="utf-8"))
    online_by_num: dict[int, dict] = {int(h["num"]): h for h in data["hymns"]}

    changed = 0
    all_warnings: list[str] = []

    for path in sorted(SOURCE.glob("*.hymn")):
        orig = Hymn.load(path)
        num  = orig.number

        if num in SKIP:
            continue

        onl = online_by_num.get(num)
        if onl is None:
            all_warnings.append(f"Hymn {num}: not in online data -- skipped")
            continue

        hymn = Hymn.load(path)
        warns = _apply(hymn, onl)
        all_warnings.extend(warns)

        if num in PATCHES:
            PATCHES[num](hymn, orig)

        new_text = hymn.to_text()
        if new_text != path.read_text(encoding="utf-8"):
            changed += 1
            if not dry_run:
                hymn.save(path)

    for w in all_warnings:
        print(f"  {w}")

    verb = "Would update" if dry_run else "Updated"
    print(f"{verb} {changed} hymn files.")

    if not dry_run:
        DIST.mkdir(exist_ok=True)
        REPORT.write_text(_report(online_by_num), encoding="utf-8")
        print(f"Report written -> {REPORT}")


if __name__ == "__main__":
    main(dry_run="--dry-run" in sys.argv)
