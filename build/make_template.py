"""
build/make_template.py
======================
Generate ``template/`` -- the exploded (unzipped) PPTX template that
``build/to_pptx.py`` will use as the base for every hymn deck.

Why exploded
------------
A .pptx is a zip. Committing one puts an opaque blob in a repo whose whole
point is that a change shows up as a readable diff. So the template lives as
formatted XML under ``template/`` and gets zipped at build time by
``build/pptx_template.py``. A font change or a moved placeholder is then a
one-line diff, same as a lyric fix in a .hymn file.

What is in it
-------------
One slide master ("Reformation Hymnal") carrying the gradient background and
the text defaults, plus exactly two layouts:

    Hymn Title    idx 0  title         hymn title
                  idx 1  body          "Hymn 26"
                  idx 2  body          author / composer

    Hymn Stanza   idx 1  body          the stanza lines
                  idx 2  body          "26 - Verse 1 of 4", top right
                  idx 3  body          "* * *" end-of-song marker

The layout names are what PowerPoint shows in the New Slide gallery, and for a
custom layout the name is also the only thing a paste into another deck can
match on, so they are written the way a person would read them.

Slides bind to layout placeholders by ``idx``, never by name or by position in
the shape tree. Those numbers are part of the contract: renumber them and every
already-generated deck maps its text into the wrong box. Treat them the way
this repo treats hymn numbers.

Everything visual references the theme rather than a literal value:
``+mj-lt`` / ``+mn-lt`` for fonts, ``<a:schemeClr>`` for the gradient stops and
the text color. That is what lets a receiving presentation with a same-named
master restyle imported hymn slides. Hardcode an sRGB value or a font name here
and it survives the import, which is the opposite of what we want.

Geometry comes straight from build/to_freeshow.py. At 16:9 there are exactly
6350 EMU per FreeShow canvas pixel and 144 px per inch, so the FreeShow item
boxes port across 1:1 and a FreeShow px font size is half as many points.

Usage:
    python -m build.make_template
"""

from __future__ import annotations

import os
import re
import shutil
import zipfile
from pathlib import Path
from xml.dom import minidom

ROOT = Path(__file__).parent.parent
OUT = ROOT / "template"

# 16:9, the size PowerPoint calls "Widescreen".
SLIDE_W = 12192000
SLIDE_H = 6858000

#: EMU per FreeShow canvas pixel at this slide size (12192000 / 1920).
PX = 6350

XML_DECL = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'

NS_P = 'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" ' \
       'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" ' \
       'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"'

THEME_NAME = "Reformation Hymnal"
MASTER_NAME = "Reformation Hymnal"

# Both layouts are type="cust". PowerPoint maps a pasted slide onto a
# destination layout by type first; for custom layouts the name is all it has
# left to match on, so these strings are load-bearing.
LAYOUTS = ["Hymn Title", "Hymn Stanza"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def px(n: float) -> int:
    """FreeShow canvas pixels -> EMU."""
    return int(round(n * PX))


def pt(n: float) -> int:
    """Points -> the hundredths-of-a-point unit DrawingML uses for sz."""
    return int(round(n * 100))


def _pretty(xml: str) -> str:
    """Indent for readability. The whole reason the template is exploded."""
    body = xml[len(XML_DECL):] if xml.startswith(XML_DECL) else xml
    out = minidom.parseString(body).toprettyxml(indent="  ")
    out = out.split("\n", 1)[1]                       # drop minidom's own decl
    out = re.sub(r"\n\s*\n", "\n", out).rstrip() + "\n"
    return XML_DECL + out


def write(rel: str, xml: str) -> None:
    path = OUT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_pretty(xml), encoding="utf-8")


def placeholder(
    shape_id: int,
    name: str,
    ph_type: str,
    idx: int | None,
    x: int, y: int, cx: int, cy: int,
    *,
    size: float,
    align: str = "ctr",
    anchor: str = "ctr",
    font: str = "+mn-lt",
    color: str = "lt1",
    bold: bool = False,
    italic: bool = False,
    autofit: bool = False,
    prompt: str = "",
) -> str:
    """One placeholder shape for a layout.

    ``lstStyle`` on the shape is what makes a slide inherit the look without
    storing any of it: the slide keeps the text, the layout keeps the type.
    ``buNone`` matters more than it looks -- without it every stanza line
    arrives with a bullet.

    ``autofit`` turns on PowerPoint's shrink-on-overflow for the box. The
    boxes that carry hymn text use it; the small fixed labels do not. See the
    module docstring for why the size on the slide is a scale and not a point
    value.
    """
    ph_idx = "" if idx is None else f' idx="{idx}"'
    b = ' b="1"' if bold else ""
    i = ' i="1"' if italic else ""
    fit = "<a:normAutofit/>" if autofit else "<a:noAutofit/>"
    prompt_para = (
        f'<a:p><a:r><a:rPr lang="en-US" dirty="0"/><a:t>{prompt}</a:t></a:r></a:p>'
        if prompt else "<a:p/>"
    )
    return f"""<p:sp>
  <p:nvSpPr>
    <p:cNvPr id="{shape_id}" name="{name}"/>
    <p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr>
    <p:nvPr><p:ph type="{ph_type}"{ph_idx} hasCustomPrompt="1"/></p:nvPr>
  </p:nvSpPr>
  <p:spPr>
    <a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>
    <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
  </p:spPr>
  <p:txBody>
    <a:bodyPr vert="horz" lIns="45720" tIns="45720" rIns="45720" bIns="45720"
              anchor="{anchor}" anchorCtr="0" wrap="square">{fit}</a:bodyPr>
    <a:lstStyle>
      <a:lvl1pPr marL="0" indent="0" algn="{align}">
        <a:lnSpc><a:spcPct val="100000"/></a:lnSpc>
        <a:buNone/>
        <a:defRPr sz="{pt(size)}"{b}{i} kern="1200">
          <a:solidFill><a:schemeClr val="{color}"/></a:solidFill>
          <a:latin typeface="{font}"/>
        </a:defRPr>
      </a:lvl1pPr>
    </a:lstStyle>
    {prompt_para}
  </p:txBody>
</p:sp>"""


# ---------------------------------------------------------------------------
# Parts
# ---------------------------------------------------------------------------

def content_types() -> str:
    overrides = "".join(
        f'<Override PartName="/ppt/slideLayouts/slideLayout{n}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.'
        'presentationml.slideLayout+xml"/>'
        for n in range(1, len(LAYOUTS) + 1)
    )
    return (
        XML_DECL
        + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>'
        '<Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>'
        + overrides +
        '<Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>'
        '<Override PartName="/ppt/presProps.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presProps+xml"/>'
        '<Override PartName="/ppt/viewProps.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.viewProps+xml"/>'
        '<Override PartName="/ppt/tableStyles.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.tableStyles+xml"/>'
        '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
        '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
        '</Types>'
    )


def root_rels() -> str:
    return (
        XML_DECL
        + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
        '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'
        '</Relationships>'
    )


def presentation(default_text_style: str) -> str:
    return (
        XML_DECL
        + f'<p:presentation {NS_P} saveSubsetFonts="1" autoCompressPictures="0">'
        '<p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst>'
        f'<p:sldSz cx="{SLIDE_W}" cy="{SLIDE_H}"/>'
        '<p:notesSz cx="6858000" cy="9144000"/>'
        + default_text_style +
        '</p:presentation>'
    )


def presentation_rels() -> str:
    return (
        XML_DECL
        + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/presProps" Target="presProps.xml"/>'
        '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/viewProps" Target="viewProps.xml"/>'
        '<Relationship Id="rId4" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="theme/theme1.xml"/>'
        '<Relationship Id="rId5" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/tableStyles" Target="tableStyles.xml"/>'
        '</Relationships>'
    )


def master() -> str:
    """The master: gradient background, text defaults, and the layout list.

    The gradient stops are ``schemeClr dk2`` at two luminances rather than two
    sRGB values, so a receiving deck's theme recolors the background instead of
    dragging ours along.
    """
    background = """<p:bg><p:bgPr>
      <a:gradFill rotWithShape="1">
        <a:gsLst>
          <a:gs pos="0"><a:schemeClr val="dk2"><a:lumMod val="110000"/></a:schemeClr></a:gs>
          <a:gs pos="55000"><a:schemeClr val="dk2"><a:lumMod val="65000"/></a:schemeClr></a:gs>
          <a:gs pos="100000"><a:schemeClr val="dk2"><a:lumMod val="35000"/></a:schemeClr></a:gs>
        </a:gsLst>
        <a:lin ang="5400000" scaled="0"/>
      </a:gradFill>
      <a:effectLst/>
    </p:bgPr></p:bg>"""

    # Master placeholders exist so both layouts have something to inherit from.
    # Their geometry is never used directly; the layouts override it.
    shapes = (
        placeholder(2, "Title Placeholder 1", "title", None,
                    px(50), px(88), px(1820), px(300),
                    size=44, font="+mj-lt")
        + placeholder(3, "Text Placeholder 2", "body", 1,
                      px(50), px(420), px(1820), px(572),
                      size=40)
    )

    layout_ids = "".join(
        f'<p:sldLayoutId id="{2147483649 + i}" r:id="rId{i + 1}"/>'
        for i in range(len(LAYOUTS))
    )

    # One level of each text style is enough; PowerPoint fills the rest from
    # presentation.xml's defaultTextStyle. Color is lt1 so light text sits on
    # the dark gradient, and follows the receiving theme if one takes over.
    def style(tag: str, size: float, font: str) -> str:
        return (
            f'<p:{tag}><a:lvl1pPr marL="0" indent="0" algn="ctr" rtl="0">'
            '<a:lnSpc><a:spcPct val="100000"/></a:lnSpc><a:buNone/>'
            f'<a:defRPr sz="{pt(size)}" kern="1200">'
            '<a:solidFill><a:schemeClr val="lt1"/></a:solidFill>'
            f'<a:latin typeface="{font}"/></a:defRPr>'
            f'</a:lvl1pPr></p:{tag}>'
        )

    return (
        XML_DECL
        + f'<p:sldMaster {NS_P} preserve="1"><p:cSld name="{MASTER_NAME}">'
        + background +
        '<p:spTree>'
        '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
        '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/>'
        '<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
        + shapes +
        '</p:spTree></p:cSld>'
        '<p:clrMap bg1="dk1" tx1="lt1" bg2="dk2" tx2="lt2" accent1="accent1" '
        'accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" '
        'accent6="accent6" hlink="hlink" folHlink="folHlink"/>'
        f'<p:sldLayoutIdLst>{layout_ids}</p:sldLayoutIdLst>'
        '<p:txStyles>'
        + style("titleStyle", 44, "+mj-lt")
        + style("bodyStyle", 40, "+mn-lt")
        + style("otherStyle", 24, "+mn-lt")
        + '</p:txStyles></p:sldMaster>'
    )


def master_rels() -> str:
    rels = "".join(
        f'<Relationship Id="rId{i + 1}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" '
        f'Target="../slideLayouts/slideLayout{i + 1}.xml"/>'
        for i in range(len(LAYOUTS))
    )
    theme_id = len(LAYOUTS) + 1
    return (
        XML_DECL
        + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + rels
        + f'<Relationship Id="rId{theme_id}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" '
        'Target="../theme/theme1.xml"/>'
        '</Relationships>'
    )


def _layout(name: str, shapes: str) -> str:
    return (
        XML_DECL
        + f'<p:sldLayout {NS_P} type="cust" preserve="1">'
        f'<p:cSld name="{name}"><p:spTree>'
        '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
        '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/>'
        '<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
        + shapes +
        '</p:spTree></p:cSld>'
        '<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>'
        '</p:sldLayout>'
    )


def layout_hymn_title() -> str:
    """Opening slide for a hymn: number, title, attribution.

    Sizes here are the layout default. build/to_pptx.py overrides the title
    size per hymn, because titles run from 8 to 59 characters and PowerPoint's
    own shrink-on-overflow is computed at render time by PowerPoint, not by
    anything we can write into the file.
    """
    shapes = (
        placeholder(2, "Hymn Number", "body", 1,
                    1600200, 1050000, 8991600, 700000,
                    size=36, anchor="b", color="lt2",
                    prompt="Hymn 000")
        + placeholder(3, "Hymn Title", "title", None,
                      1200000, 1900000, 9792000, 2600000,
                      size=44, font="+mj-lt", autofit=True,
                      prompt="Hymn Title")
        + placeholder(4, "Attribution", "body", 2,
                      1600200, 4800000, 8991600, 1200000,
                      size=22, anchor="t", italic=True, color="lt2",
                      prompt="Author / Composer")
    )
    return _layout(LAYOUTS[0], shapes)


def layout_hymn_stanza() -> str:
    """One stanza per slide.

    The three boxes are the FreeShow items from build/to_freeshow.py converted
    at 6350 EMU per canvas px, so a stanza lands in the same place in both
    build targets. The end marker (idx 3) only carries text on a hymn's final
    slide; to_pptx.py drops the shape entirely from the others.
    """
    shapes = (
        placeholder(2, "Stanza", "body", 1,
                    px(50), px(88), px(1820), px(904),
                    size=54, autofit=True, prompt="Stanza lines")
        + placeholder(3, "Reference", "body", 2,
                      px(1170), px(30), px(700), px(60),
                      size=20, align="r", anchor="t", color="lt2",
                      prompt="000 - Verse 1 of 4")
        + placeholder(4, "End Marker", "body", 3,
                      px(50), px(1000), px(1820), px(70),
                      size=30, anchor="b", color="lt2",
                      prompt="* * *")
    )
    return _layout(LAYOUTS[1], shapes)


def layout_rels() -> str:
    return (
        XML_DECL
        + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" '
        'Target="../slideMasters/slideMaster1.xml"/>'
        '</Relationships>'
    )


def theme(source: str) -> str:
    """Reuse python-pptx's Office theme, with our name, fonts, and dk2.

    Hand-authoring a valid fmtScheme (three fill styles, three line styles,
    three effect styles, three background fill styles) buys nothing here, and
    getting it subtly wrong makes PowerPoint refuse the file. Only the parts we
    actually care about are rewritten.
    """
    x = source
    x = x.replace('<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="Office Theme">',
                  f'<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="{THEME_NAME}">')
    # dk2 drives the gradient; lt2 is the muted text color for the small labels.
    x = x.replace('<a:dk2><a:srgbClr val="1F497D"/></a:dk2>',
                  '<a:dk2><a:srgbClr val="1B3A5C"/></a:dk2>')
    x = x.replace('<a:lt2><a:srgbClr val="EEECE1"/></a:lt2>',
                  '<a:lt2><a:srgbClr val="C8D4E0"/></a:lt2>')
    x = x.replace('<a:clrScheme name="Office">', f'<a:clrScheme name="{THEME_NAME}">')
    # Cambria and Calibri ship with Office, so a deck opens as designed on any
    # machine that has PowerPoint, and both are present on this build host for
    # the LibreOffice preview render.
    x = x.replace('<a:majorFont><a:latin typeface="Calibri"/>',
                  '<a:majorFont><a:latin typeface="Cambria"/>')
    x = x.replace('<a:fontScheme name="Office">', f'<a:fontScheme name="{THEME_NAME}">')
    return x


def core_props() -> str:
    """No dcterms dates: a fixed template means byte-stable rebuilds."""
    return (
        XML_DECL
        + '<cp:coreProperties '
        'xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:dcmitype="http://purl.org/dc/dcmitype/" '
        'xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        f'<dc:title>{THEME_NAME}</dc:title>'
        '<dc:subject>Hymn projection template</dc:subject>'
        '<cp:revision>1</cp:revision>'
        '</cp:coreProperties>'
    )


def app_props() -> str:
    n = len(LAYOUTS)
    titles = "".join(f"<vt:lpstr>{name}</vt:lpstr>" for name in LAYOUTS)
    return (
        XML_DECL
        + '<Properties '
        'xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
        'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
        '<Slides>0</Slides><Notes>0</Notes>'
        '<TitlesOfParts><vt:vector size="' + str(n + 1) + '" baseType="lpstr">'
        f'<vt:lpstr>{MASTER_NAME}</vt:lpstr>{titles}'
        '</vt:vector></TitlesOfParts>'
        '<HeadingPairs><vt:vector size="4" baseType="variant">'
        '<vt:variant><vt:lpstr>Theme</vt:lpstr></vt:variant>'
        '<vt:variant><vt:i4>1</vt:i4></vt:variant>'
        '<vt:variant><vt:lpstr>Slide Titles</vt:lpstr></vt:variant>'
        f'<vt:variant><vt:i4>{n}</vt:i4></vt:variant>'
        '</vt:vector></HeadingPairs>'
        '</Properties>'
    )


# ---------------------------------------------------------------------------

def main() -> int:
    import pptx  # only needed to locate the stock parts we reuse

    src = Path(pptx.__file__).parent / "templates" / "default.pptx"
    stock = {n: zipfile.ZipFile(src).read(n).decode("utf-8")
             for n in ("ppt/theme/theme1.xml", "ppt/presProps.xml",
                       "ppt/viewProps.xml", "ppt/tableStyles.xml",
                       "ppt/presentation.xml")}

    default_text_style = re.search(
        r"<p:defaultTextStyle>.*</p:defaultTextStyle>",
        stock["ppt/presentation.xml"], re.S
    ).group(0)

    if OUT.exists():
        shutil.rmtree(OUT)

    write("[Content_Types].xml", content_types())
    write("_rels/.rels", root_rels())
    write("ppt/presentation.xml", presentation(default_text_style))
    write("ppt/_rels/presentation.xml.rels", presentation_rels())
    write("ppt/slideMasters/slideMaster1.xml", master())
    write("ppt/slideMasters/_rels/slideMaster1.xml.rels", master_rels())
    write("ppt/slideLayouts/slideLayout1.xml", layout_hymn_title())
    write("ppt/slideLayouts/slideLayout2.xml", layout_hymn_stanza())
    for n in range(1, len(LAYOUTS) + 1):
        write(f"ppt/slideLayouts/_rels/slideLayout{n}.xml.rels", layout_rels())
    write("ppt/theme/theme1.xml", theme(stock["ppt/theme/theme1.xml"]))
    for part in ("ppt/presProps.xml", "ppt/viewProps.xml", "ppt/tableStyles.xml"):
        write(part, stock[part])
    write("docProps/core.xml", core_props())
    write("docProps/app.xml", app_props())

    count = sum(1 for _ in OUT.rglob("*") if _.is_file())
    print(f"Written {OUT}/  ({count} parts, {len(LAYOUTS)} layouts)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
