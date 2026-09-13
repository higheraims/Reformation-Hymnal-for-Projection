# Reformation Hymnal for Projection

The Reformation Hymnal in digital format for projection software. The Reformation Hymnal is the official hymnal of the Seventh-day Adventist Reform Movement (SDARM).

> The Reformation Hymnal is copyright © 2003 Reformation Herald Publishing Association.

---

## Downloads

Visit the [Releases](../../releases/latest) page to download the latest compiled files.

| File | Use with |
|---|---|
| `ReformationHymnal.sps` | SoftProjector — Import Songbook |
| `ReformationHymnal.project` | FreeShow — File → Import → FreeShow Project File |
| `ReformationHymnal-pptx.zip` | PowerPoint — one `.pptx` per hymn, numbered `001` to `700` |
| `ReformationHymnal-template.pptx` | PowerPoint — the slide master the hymn decks are built on |

---

## SoftProjector

1. Download `ReformationHymnal.sps` from the latest release.
2. In SoftProjector: **Edit → Manage Database** and choose Import on the Songbooks tab.
3. All 700 hymns will appear in the song list.

## FreeShow

1. Download `ReformationHymnal.project` from the latest release.
2. In FreeShow: **File → Import → FreeShow Project File** and select the file.
3. All 700 hymns will be imported. Drag them into your category as needed.

---

## PowerPoint

1. Download `ReformationHymnal-pptx.zip` and unzip it. Each hymn is its own
   file, named by hymn number.
2. Open the hymn you want and copy its slides into your service presentation.

Slides carry no formatting of their own. Everything visible comes from two
layouts on a master named **Hymn Title** and **Hymn Stanza**. 

If your own presentation has a master with those names, the
slides take on its background, fonts and colours when you paste with the
destination theme. The easiest way to set that up is to open
`ReformationHymnal-template.pptx`, go to View - Slide Master and copy the two layouts 
into your own master, and restyle them there. Then when you copy slides from a slide
deck for a particular hymn, they will paste in and will match the look of your
destination slideshow.

---

## About this project

The hymn texts are maintained as plain-text `.hymn` files in `source/` and compiled
into the above formats by the build scripts in `build/`. This makes any lyric
change visible as a readable diff in version history.

Text has been cross-checked against the online hymnal at hymnal.sdarm.org/rh.
See `CHANGELOG.md` for a full account of corrections and intentional differences.

**Versioning: CalVer (`YYYY.MM.DD`)**

This project uses calendar-based versioning rather than semantic versioning.
The "version" of a release is intrinsically the date its text was finalised.
A user downloading `2026.06.08` immediately knows when it was published.

If two releases are needed on the same day, append a counter: `2026.06.08.1`.

### Building from source

```
pip install -e ".[pptx]"
make build
```

Output is written to `dist/`. The PowerPoint target measures text to choose a
stanza size, so it wants Cambria and Calibri installed; it falls back to the
metric-compatible Caladea and Carlito and warns if it finds neither.

The PowerPoint template lives in `template/` as unzipped XML, one file per
part, so a change to the gradient or a moved placeholder reads as a normal
diff. `make template` zips it. After editing the template in PowerPoint, run
`python -m build.pptx_template explode path/to/edited.pptx` to write it back.
