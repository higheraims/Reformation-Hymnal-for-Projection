"""
build/parse_hymn.py
===================
Load all source/*.hymn files and return them as a list of Hymn objects.
Used by the compiler scripts (to_softprojector, to_freeshow) as a shared
entry point so they don't each re-implement directory scanning.
"""

from __future__ import annotations

from pathlib import Path

from .model import Hymn


def load_all(source_dir: str | Path = "source") -> list[Hymn]:
    """Return every .hymn in source_dir, sorted by hymn number."""
    src = Path(source_dir)
    hymns = [Hymn.load(p) for p in sorted(src.glob("*.hymn"))]
    hymns.sort(key=lambda h: h.number)
    return hymns
