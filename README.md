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

## About this project

The hymn texts are maintained as plain-text `.hymn` files in `source/` and compiled
into the above formats by the build scripts in `build/`. This makes every lyric
change visible as a readable diff in version history.

Text has been cross-checked against the online hymnal at hymnal.sdarm.org/rh.
See `CHANGELOG.md` for a full account of corrections and intentional differences.

### Building from source

```
pip install -e .
make build
```

Output is written to `dist/`.
