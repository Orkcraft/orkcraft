# Spec 20 — the wilderness composed, not scattered

Branch `spec/20-composed-wilderness` · design: decisions §30, design-system-v3.md §4.9 (the decor stays quiet) ·
after 18 (the darker grass) and 19 (the camera)
**Builds:** Claude · **Review:** light, **and the owner signs off the before/after shots before it is merged**

## Why
`decorAround` in `js/camp/layout.js` puts trees, pines, bushes, rocks and logs on a grid of 40 art px by a hash and a
chance that falls with distance. It reads as what it is: noise on a grid. The owner, 16 October: place them with
care, as a level designer would; the person will add their own pieces later (the items on the grass already exist).

## Do
Change only `orkcraft/gui/static/js/camp/layout.js` (the wilderness part), a new `orkcraft/gui/static/js/camp/wild.js`
(the compositions as data and their placement), and tests. No new art: the sprites in `design-system/sprites/v3/decor/`
and `decor/wild/` as they are. Change nothing outside these files.
1. **Groves, not cells.** A handful of hand-composed groups as data (`wild.js`): each 3–5 pieces with one dominant
   tree, the smaller pieces in front, odd counts, pieces overlapping only inside a grove, never two groves alike side
   by side (mirrored or with a piece swapped). Examples: *a pine stand* (3 pines, a bush), *an oak corner* (a big tree,
   a small one, two bushes, a rock), *a fallen log* (log, stump, mushrooms, reeds near water).
2. **Places, not chance.** Groves stand on named places round the camp: a dark band of pines behind the back wall
   (tall at the back, lower towards the camp); the two sides as alternating groves with clear gaps between them; a
   grove at each corner; the pond with its jetty and reeds on the west as today. Between groves, at most a few single
   low pieces (a rock, a stump, a bush). The grass next to the camp stays open: nothing taller than a bush within one
   tile of it, and nothing on the way in to the lookout.
3. **Grows with the camp:** when a line is added at the bottom, the side bands extend down by the same pattern,
   shifted so the repeat doesn't show. The same town always looks the same (deterministic), and a new line moves
   nothing already placed above it.
4. **Leaves the person's grass to the person:** no wild piece inside the camp; the items' blockers (`js/camp/grass.js`)
   keep counting the wild pieces, as now.

## Tests
Critical tests, plus `tests/test_camp_layout.py` (deterministic; nothing inside the camp or on the way in; no two
groves overlapping; a new bottom line leaves every piece above it where it was) and `tests/test_gui_camp_browser.py`.
Screenshots into `docs/design/img/wild/`: before (from `main`) and after, at the default zoom and scrolled to the
bottom, for a small and a large camp. **The owner looks at them before the merge.**
