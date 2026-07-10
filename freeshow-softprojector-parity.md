# FreeShow Hymnal — SoftProjector Parity Features

A working brief for implementing two SoftProjector-style behaviors in this
FreeShow hymnal repo. The goal is parity with how SoftProjector presented hymns:

1. **Hymn number + verse number visible on every slide.**
2. **Asterisks at the end of the song** (three `*` after the final
   chorus) to signal the hymn is ending.

This repo contains FreeShow `.show` files (JSON). Official format reference:
<https://freeshow.app/docs/format-show>

---

## Background: how FreeShow handles this

FreeShow has two relevant mechanisms:

- **Metadata** — each show has a `meta` object with fields like `number`,
  `title`, `author`, etc. Metadata can be displayed globally on the output, or
  pulled into text via dynamic values.
- **Dynamic values** — tokens placed inside a text item that update
  automatically at runtime. Relevant ones here: the show's **metadata number**
  and the current slide's **group name** (e.g. "Verse 1", "Chorus"). In the UI
  they're added by right-clicking a text item → *Dynamic values*.
- **Slide groups** — every slide belongs to a group; the group name is
  effectively the verse/chorus label. Stored as `"group"` on each slide in the
  `.show` JSON.

There is **no built-in "is this the last slide" token**, so the asterisk marker
has to be placed explicitly on the final slide. That part is a good candidate
for scripting since it's repetitive across the whole library.

---

## Step 0 — Investigate the repo first

Before changing anything, confirm the actual structure by examining a few
`.show` files. Answer these:

1. **Where does the hymn number live?**
   - Is it in `meta.number`?
   - Or only embedded in the show `name` (e.g. `"001 - A Mighty Fortress"`)?
   - Or both? This determines which dynamic value / field to use, and whether we
     need to backfill `meta.number` for consistency.

2. **How are slide groups named?**
   - Look at the `"group"` value on slides. Are verses "Verse 1" / "Verse 2",
     or just "Verse"? Is the chorus "Chorus"? Consistent naming makes the verse
     label reliable.

3. **How is slide order determined?**
   - Order comes from the `layouts` section, not the `slides` object key order.
     Find the active layout and its `slides` array to know the true last slide
     of each song (needed for the asterisk marker).

4. **What does a text item look like?**
   - Inspect a slide's `items` → text structure so we know exactly where to
     append characters or insert a new text element.

5. **Dynamic value token syntax (if we want to script it):**
   - The cleanest way to learn the exact token strings is to create one text
     item in FreeShow with the number + group dynamic values, save, and inspect
     the resulting JSON. Then we can reproduce that token syntax programmatically
     instead of guessing.

Summarize findings before implementing.

---

## Feature 1 — Hymn number + verse number on every slide

There are two viable routes. Pick based on what the investigation shows.

### Route A — Template + dynamic values (recommended, FreeShow-native)

Keep the data clean in the files; do the display in FreeShow:

1. Ensure `meta.number` is populated consistently on every show (backfill from
   the show name if needed — a good scripted task).
2. Ensure slide `group` names are consistent (verse/chorus labels).
3. In FreeShow, build a template with a small corner text box containing the
   **metadata number** and **slide group** dynamic values, rendering like
   `#84 · Verse 2`.
4. Apply that template to the hymnal shows.

Because templates render per slide, the group/verse part updates automatically
as slides advance. CC's job here is mainly **data hygiene** (consistent
`meta.number` and `group` values) so the template works everywhere.

> Note: bulk-applying a template across many shows can be clunky in FreeShow —
> test on one hymn, then expand.

A genuinely global alternative for the *number/title* is FreeShow's **output
metadata display** (Output settings), which stamps show-level metadata on every
slide of every show with no per-file editing. It won't change per verse, so pair
it with the slide-group piece for the verse label.

### Route B — Bake static text into the files (scripted)

If we'd rather not depend on templates, script a text item onto every slide
containing the literal number + group, e.g. `#84 — Verse 2`, computed per slide
from `meta.number`/name and the slide's `group`. Pros: self-contained, no
template setup. Cons: static (won't reflow if metadata changes), and adds an
item to every slide.

**Recommendation:** Route A, with CC handling the data-consistency backfill.
Fall back to Route B only if templates prove too painful to apply at scale.

---

## Feature 2 — Asterisks at the end of the song

SoftProjector appended several asterisks after the final chorus to mark the end.
No auto-detection exists, so mark the last slide explicitly. This is a good
fully-scripted task across the whole repo:

1. For each `.show` file, resolve the **true last slide** via the active layout's
   slide order (not JSON key order).
2. Either:
   - **append** an asterisk string (e.g. `* * *`) to that slide's lyric text, or
   - **add a separate small text item** with the asterisks (cleaner — keeps it
     out of the lyric text and easier to style/remove).
3. Make it idempotent — re-running the script shouldn't stack multiple markers.
   Check whether the marker already exists before adding.

Decide on the exact glyph/count (e.g. `***`, `* * *`, or a centered dingbat) and
keep it uniform across the library.

---

## Suggested order of work

1. Examine 3–5 representative `.show` files; report structure findings (Step 0).
2. Backfill/normalize `meta.number` and `group` names if inconsistent.
3. Decide Route A vs B for Feature 1 with the repo owner.
4. Script the end-of-song asterisk marker (Feature 2), idempotently.
5. Validate by opening a couple of edited shows in FreeShow.

## References

- `.show` format: <https://freeshow.app/docs/format-show>
- Show tools / metadata & message + dynamic values: <https://freeshow.app/docs/tools>
- Slide items (incl. slide progress meter "Groups" mode): <https://freeshow.app/docs/items>
- Output styles: <https://freeshow.app/docs/styles>
