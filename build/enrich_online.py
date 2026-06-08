"""
build/enrich_online.py
======================
Enrich source/*.hymn files with data from the online hymnal JSON:

  - topic:        topical category (all 700 hymns)
  - common_title: official/popular title where it differs from the first-line title
  - tune:         from composerOrTune, only when tune is not already set in source

Reads:  reference/rh_online.json   (produced by build/fetch_online.py)
Writes: source/*.hymn (in-place, idempotent)

Usage:
    python -m build.enrich_online            # apply changes
    python -m build.enrich_online --dry-run  # preview without writing
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from build.model import Hymn

SOURCE = Path(__file__).parent.parent / "source"
REF = Path(__file__).parent.parent / "reference" / "rh_online.json"


def main(dry_run: bool = False) -> None:
    if not REF.exists():
        sys.exit(f"Reference JSON not found: {REF}\nRun: python -m build.fetch_online")

    data = json.loads(REF.read_text(encoding="utf-8"))
    online_by_num: dict[int, dict] = {int(h["num"]): h for h in data["hymns"]}

    changed = 0
    warnings: list[str] = []

    for path in sorted(SOURCE.glob("*.hymn")):
        hymn = Hymn.load(path)
        online = online_by_num.get(hymn.number)
        if online is None:
            warnings.append(f"  WARNING: hymn {hymn.number} not in online data")
            continue

        modified = False

        # topic (all 700 hymns in the JSON have this)
        topic = (online.get("topic") or "").strip()
        if topic and hymn.topic != topic:
            hymn.topic = topic
            modified = True

        # common_title: only when officialTitle is non-empty AND differs from title
        official = (online.get("officialTitle") or "").strip()
        first_line = (online.get("title") or "").strip()
        if official and official != first_line:
            if hymn.common_title != official:
                hymn.common_title = official
                modified = True
        else:
            # clear stale common_title if it no longer applies
            if hymn.common_title is not None:
                hymn.common_title = None
                modified = True

        # tune: add from online only when source has no tune set
        tune_online = (online.get("composerOrTune") or "").strip()
        if tune_online and not hymn.tune:
            hymn.tune = tune_online
            modified = True

        if modified:
            changed += 1
            if dry_run:
                print(f"  would update {path.name}")
            else:
                hymn.save(path)

    for w in warnings:
        print(w)

    verb = "Would update" if dry_run else "Updated"
    print(f"{verb} {changed} of {len(list(SOURCE.glob('*.hymn')))} hymn files.")


if __name__ == "__main__":
    main(dry_run="--dry-run" in sys.argv)
