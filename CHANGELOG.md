# Changelog — Reformation Hymnal for Projection

All notable changes to the hymnal text and build outputs are documented here.
Entries are written for worship coordinators and projection operators, not just
developers — if a line of a hymn changed, it belongs here.

---

## [2026.06.07] — first release

This release represents the first version of the hymnal maintained as reviewed,
diff-tracked plain text. Every change from the original SoftProjector songbook
is now visible in version history. Future corrections will each have their own
commit with a clear description.

### Text quality improvements

- **Curly (typographic) quotes throughout.** All straight `"` and `'` characters
  in hymn texts have been replaced with proper opening and closing quotation marks
  (`"` `"`) and apostrophes/elisions (`'`). Word-initial elisions like `'tis`,
  `'twas`, and `'neath` use the right single quote, not an opening quote.

- **Author and composer attribution.** Author and composer names have been
  populated for all hymns where this information was able to be extracted.

### Metadata additions

- **Topic field added to all 700 hymns** using the subject categories from the
  online hymnal at hymnal.sdarm.org/rh (e.g., "Adoration", "The Second Coming",
  "Choir and Miscellaneous").

- **Common titles added for 47 hymns** where the hymn is widely known by a name
  other than its first line (e.g., Hymn 1 "All People That on Earth Do Dwell" is
  commonly known as "Old Hundredth").

- **Tune names added for 31 hymns** where the online hymnal listed a tune name
  not present in the original SoftProjector file.

### Lyrics corrections accepted from online reference

The online hymnal at hymnal.sdarm.org/rh was used as a reference for lyric
accuracy. After comparison, 690 of 700 hymns now match the online version exactly
(after normalising quotation style). The corrections accepted were primarily
punctuation and minor wording differences.

### Intentional differences from hymnal.sdarm.org

The following 10 hymns intentionally differ from the online version, with reasons.
A full report has been shared with the online hymnal maintainers.

**Hymn 27 — We Gather Together**
Verse 3, line 3 retains the first-edition wording:
> "Let Thy congregation escape tribulation,"

The online version reads "Help Thy congregation endure tribulation;" — an apparent
later editorial change. We retain the first-edition text.

**Hymn 52 — "God Is Love!" His Word Proclaims It**
Our source credits **Ryan A. Dykes** as author. The online hymnal does not list an
author for this hymn. Our attribution has been flagged for the online maintainers
to verify. The issue was a misspelling in the author's name.

**Hymn 66 — It Came Upon the Midnight Clear**
- Verse 1, line 6: the comma is placed *inside* the closing quotation mark —
  `From heaven's all-gracious King,"` — following the first-edition convention.
  The online version places the comma outside.
- Verse 3: the online text contains a two-word typo ("be side"). Our text reads
  "beside" (one word). The correction has been reported to the online maintainers.

**Hymn 71 — O Word of God Incarnate**
Verse 2 retains "And still that light **she** lifteth" (referring to "the church"
in the prior stanza). The online version reads "is lifteth," which is
grammatically anomalous and appears to be a typo introduced in the second edition.

**Hymn 177 — Jesus Is All the World to Me**
Verse 2, line 3 ends with "and" as sung: "I go to Him for blessings, **and**"
The online version moves "And" (capitalized) to begin line 4, disrupting the
natural phrasing of the melody.

**Hymn 183 — Oh, the Best Friend to Have Is Jesus**
The chorus retains the parenthetical format from the printed hymnal:
> "The best friend to have is Jesus (every day);"

The online version reformats these as separate parenthetical clauses. The inline
format is clearer for projection use, where singers may not have sheet music.

**Hymn 209 — I Hear the Saviour Say**
Verse 3 retains "Since nothing good have **I**" as the first line. The online
version breaks this as "Since nothing good have / I Whereby Thy grace to claim,"
which appears to be a line-break error, placing "I" at the start of the next line.

**Hymn 318 — We Would See Jesus**
All four first lines retain punctuation *inside* the closing quotation mark,
following the first-edition convention:
> `"We would see Jesus;" for the shadows lengthen`

The online version places the semicolon outside: `"We would see Jesus";`

**Hymn 586 — I Sing the Love of God**
The chorus retains "He gives me **joy** in place of care" (line 2). The online
version reads "love," which does not parallel line 1 ("He gives me joy in place
of sorrow") and appears to be an editorial error.

**Hymn 619 — All Things Bright and Beautiful**
Our source presents 5 verses, with the refrain text ("All things bright and
beautiful...") as Verse 1, followed by the body verses as Verses 2–5. This
matches the printed hymnal and how the hymn is sung. The online version presents
4 verses with a separate refrain section.

### Additional corrections and structural improvements

**Hymn 255 — Who Is on the Lord's Side?** and **Hymn 308 — Kind Words Can Never
Die**: These hymns had automatically-detected chorus sections that repeated lines
already present in the verses. The redundant chorus sections have been removed;
the verse text is unchanged and remains complete.

**Hymn 659 — Awake, My Soul, to Joyful Lays**: The online version lists a single
refrain ("Loving-kindness, loving-kindness, / His loving kindness, O, how good!")
applied uniformly to all verses. The correct performance has the refrain echo the
closing line of each verse. Four individual chorus sections have been added:
- After V1: "His loving-kindness, O, how free!"
- After V2: "His loving-kindness, O, how great!"
- After V3: "His loving-kindness, O, how good!"
- After V4: "His loving-kindness, evermore."

The online refrain's single-line ending "O, how good!" for verses 1 and 2 has
been reported as an error to the online maintainers.

---

## Previous versions

Prior to this migration, the hymnal was maintained as a binary SoftProjector
`.sps` file (SQLite database). Changes were not tracked as readable text diffs.
The original file is preserved at `reference/original.sps` for provenance.
