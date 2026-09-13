"""
build/pptx_template.py
======================
Move the PPTX template between its two forms.

    pack      template/  ->  dist/ReformationHymnal-template.pptx
    explode   a .pptx    ->  template/

``template/`` is the checked-in source of truth: formatted XML, one file per
OPC part, so a change to the gradient or a moved placeholder shows up as a
readable diff. PowerPoint cannot open that, so ``pack`` zips it. After editing
the template in PowerPoint, ``explode`` writes the result back over
``template/`` and git shows exactly what PowerPoint changed -- which is worth
reading, because PowerPoint rewrites more than you touched.

Usage:
    python -m build.pptx_template pack
    python -m build.pptx_template explode path/to/edited.pptx
"""

from __future__ import annotations

import re
import shutil
import sys
import zipfile
from pathlib import Path
from xml.dom import minidom

ROOT = Path(__file__).parent.parent
TEMPLATE = ROOT / "template"
DIST = ROOT / "dist"
PACKED = DIST / "ReformationHymnal-template.pptx"

XML_DECL = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'

# Fixed timestamp so the same template/ always produces byte-identical output.
# zipfile refuses anything before 1980.
_EPOCH = (1980, 1, 1, 0, 0, 0)


def _parts() -> list[Path]:
    """[Content_Types].xml first; the rest sorted so the zip is deterministic."""
    files = sorted(p for p in TEMPLATE.rglob("*") if p.is_file())
    ct = TEMPLATE / "[Content_Types].xml"
    return [ct] + [p for p in files if p != ct]


def pack(dest: Path = PACKED) -> Path:
    if not TEMPLATE.is_dir():
        raise SystemExit(f"{TEMPLATE} does not exist -- run build.make_template first")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        for path in _parts():
            info = zipfile.ZipInfo(str(path.relative_to(TEMPLATE)), _EPOCH)
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, path.read_bytes())
    return dest


def _pretty(data: bytes) -> bytes:
    """Re-indent an XML part. Left alone if it will not parse."""
    try:
        out = minidom.parseString(data).toprettyxml(indent="  ")
    except Exception:
        return data
    out = out.split("\n", 1)[1]
    out = re.sub(r"\n\s*\n", "\n", out).rstrip() + "\n"
    return (XML_DECL + out).encode("utf-8")


def explode(src: Path, dest: Path = TEMPLATE) -> Path:
    if dest.exists():
        shutil.rmtree(dest)
    with zipfile.ZipFile(src) as z:
        for name in z.namelist():
            if name.endswith("/"):
                continue
            target = dest / name
            target.parent.mkdir(parents=True, exist_ok=True)
            data = z.read(name)
            target.write_bytes(_pretty(data) if name.endswith((".xml", ".rels")) else data)
    return dest


def main(argv: list[str]) -> int:
    if len(argv) >= 1 and argv[0] == "pack":
        out = pack()
        print(f"Written {out}  ({out.stat().st_size // 1024} KB)")
        return 0
    if len(argv) == 2 and argv[0] == "explode":
        out = explode(Path(argv[1]))
        n = sum(1 for p in out.rglob("*") if p.is_file())
        print(f"Written {out}/  ({n} parts)")
        return 0
    print(__doc__.strip().rsplit("Usage:", 1)[-1].strip(), file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
