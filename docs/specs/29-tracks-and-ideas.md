# Spec 29 — tracks and ideas: the Task board's specs as Wiki pages, the phone first, no model

**Draft for the owner (17 October), not in a batch yet.**

Branch `spec/29-tracks-and-ideas` · design: decisions §43 (items 1–4, 9, 10), §41.6 · **Builds:** Claude ·
**Review:** full · track 1, P1. The first of three (29 → 30 the keeper → 31 Take it to work).

## Why
The Task board becomes the place where work starts as a spec (§43). This spec lays the ground the keeper (30) and
Take it to work (31) stand on: the project's **tracks** and its **ideas** as pages in the Wiki, shown on the board and
on the phone, written and ordered by hand. No model runs in this spec: dropping an idea costs nothing.

## What

### 1. The words
`orkcraft/realm/lexicon.py` `TERMS`: `track` ("track", "tracks") and `idea` ("idea", "ideas"). The building's Goal
setting keeps its word.

### 2. The pages (`orkcraft/realm/ideas.py`, new, no face)
- **Where:** the Wiki joined to the board: the board's setting `wiki`, else the camp's first Wiki (§41.6); with no Wiki
  in the camp, `llm-wiki/general/` (`realm/wiki.py` `default_dir`), scaffolded as the Wiki does. Two sections:
  `pages/tracks/<slug>.md` and `pages/ideas/<slug>.md`, each with its `index.md` as every Wiki section has.
- **A track page:** front matter `owner: board`, `kind: track`, `order: <int>`, `deadline: <YYYY-MM-DD>` (optional);
  the body has `## About` and `## Success criteria` (a list).
- **An idea page:** front matter `owner: board`, `kind: idea`, `track: <track slug>`, `order: <int>`,
  `state: raw | asks | ready | working | done`, `size: S | M | L` (empty until the keeper, spec 30); the body has
  the fixed sections, in this order: `## Gist`, `## Why`, `## In`, `## Out`, `## Risks`, `## Open questions`,
  `## Estimate`, `## Stages`, `## Decisions`. A dropped idea is its text under `## Gist`, the rest empty.
- **General:** the track `general` ("General") is written the first time a track is needed and none exists. It cannot
  be deleted while it holds ideas.
- **The API:** `tracks(root)`, `ideas(root, track=None)` (in order), `add_idea(root, text, track="general")`,
  `move(root, slug, track=None, before=None)` (renumbers `order` only where needed), `set_section(root, slug, name,
  text)`, `add_track(root, title)`, `set_track(root, slug, about=None, criteria=None, deadline=None)`. Writes are
  whole-file and keep any section or front matter key it does not know. Hand edits of a page are read as they are.
- `realm/wiki.py`: `owner: board` pages are not rewritten by the librarian, as `owner: human` pages are not.

### 3. The board on the desktop (Office first; Camp's booth unchanged in this spec)
New `orkcraft/gui/static/js/buildings/ideas.js` (+ `ideas.css`), opened from the board (`fields.js` is past 600 lines:
add only the entry to it), data from a new `orkcraft/gui/views/ideas.py`.
- **Left:** the tracks in order, each with its count of ideas; drag to reorder; **+ Track**.
- **Middle:** the ideas of the chosen track in order, drag to reorder or onto another track. A card: the first line of
  Gist, the size when set, the state as a word (*new · asks you · ready · working 3/5 · done*).
- **Right:** the opened idea. Every section is a block with its own colour role and icon (roles from the design
  system, never raw colours), its first line in bold as the thesis, the rest folded under *More*; an empty section shows
  its name dimmed. A section is edited in place by hand (the keeper comes in 30).
- **Today** (top): today's open to-dos (the existing `My to-dos`) and, from spec 30, Needs you. In this spec, the to-dos.
- What stays: the To Do / In Progress / Done lanes, `My to-dos`, Mission 1's drill and External listeners' cards work as
  today (31 takes the tasks off the board). A note in a lane of notes gets **Make it an idea** (to General).

### 4. The phone (designed at 390 px first)
`orkcraft/gui/static/pwa/ideas.js` (new), the tab in `pwa/fields.js`, data through `gui/mobile.py`.
- Three tabs: **Today** · **Ideas** · **+**.
- **+**: one field, text (voice through the keyboard's dictation), **Drop it**: an idea in the chosen track (General by
  default), queued offline as the dock does. The dock's *An idea… → Drop it* (`pwa/dock.js`) makes an idea, no longer a
  card in the Ideas lane.
- **Ideas:** a track switch on top, the ideas as a list; long-press to drag, or ↑ ↓ on the opened card.
- **An opened idea:** the sections as blocks, the theses only, a tap opens a section. No editing of sections on the
  phone in this spec (the talk is spec 30).
- **Today:** the open to-dos, tick with a tap.

### 5. Not in this spec
The keeper, any model call, the batch, Needs you's content, sessions (30); Take it to work, tasks, tiers, limits,
secret to-dos (31); Camp's booth.

## Tests
- `tests/test_ideas.py`: pages round-trip (front matter and sections, unknown keys kept), General made once, order
  after a move, a hand-edited page read as written, the librarian skips `owner: board`.
- `tests/test_ideas_browser.py`: at **390 × 844** — drop an idea from **+**, it shows in Ideas under General; open it,
  the theses show, a section opens; reorder by ↑. At desktop size — add a track, drag an idea onto it, edit Gist, the
  page on disk has it.
- The critical tests, `tests/test_gui_wording.py`, and the test files of the modules touched.

Change nothing outside: `realm/lexicon.py`, `realm/ideas.py`, `realm/wiki.py` (the `owner: board` skip only),
`gui/views/ideas.py`, `gui/views/__init__.py`, `gui/mobile.py`, `gui/static/js/buildings/ideas.js` + `.css`, the entry in
`gui/static/js/buildings/fields.js`, `gui/static/pwa/ideas.js`, `pwa/fields.js`, `pwa/dock.js`, the tests above.
