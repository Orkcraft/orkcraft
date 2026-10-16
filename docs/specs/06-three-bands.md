# Spec 06 — the camp lays itself out: the wall, line 0.5, the processing line, the quarter

> **Parked (decisions §36, 16 October):** outside the three tracks; a hypothesis for after the testers. Do not build.

Branch `spec/06-three-bands` · model **pro** · design: decisions-2026-10.md §20 (all of it), design-system-v3.md §4,
§4b, §4c, §4f · after Halloween
**Builds:** Claude · **Review:** full (docs/specs/README.md "Who builds")

## Do
The shape is decisions §20, "The camp's lines, final shape" (read its diagram first). In
`orkcraft/gui/static/js/camp/layout.js` and `track.js` (pure, tested in Node by `tests/test_camp_layout.py`):
1. **Camp ignores Office positions** for buildings (they stay Office's own drawing in `js/town.js`). The Town Hall is
   not drawn (spec 13).
2. **Line 0, the wall,** left to right: the lookout (`watchtower`, the way in) · Metrics (`crag`) beside it, with a
   road from the first External listeners into it when both exist · Drop file here (`pit`) · the Calendar
   (`war_drum`) and any type marked `notices: true` in a small table · the Publisher's catapult (`catapult`) at the
   right end, throwing over the wall. Their stops reach the track by short spurs (as the Calendar's does today).
3. **Line 0.5:** the Task board (`fields`, the booth and its siding) at the left; the Review gate (`loot`, its
   weighbridge) with the person's home at the right; between them the track of line 0.5 (see 5). The Wiki
   (`scrolls`) stands on the grass between them (spec 08 refines its spot).
4. **Line 1, the processing:** in this order when built: the Agent pool (`barracks`, the depot, 2 places) · the
   Review board (`council`) · the Transformer (`mill`) · Research (`mine`) · Script (`workshop`) · the benches
   (`lab`, `ux_lab`) · Inspector (`lake`) · Router (`signpost`). More than fit (8 places) go to line 2.
5. **The track, one way, clockwise from the board:** the board's siding → down the left column → east along each
   processing line → up the right column → the Review gate's weighbridge; passed → a spur up to the catapult's
   buffer stop by the wall; **sent back → west along line 0.5 to the Task board's siding** (the return line). Remove
   today's return line under the lowest row and line 2's buffer stop. Switches stand at every fork as today.
6. **Lines 2 and on, the person's quarter:** every other building, in the order kept in the town file (`scroll`
   field `quarter: [building ids]`, new; appended when built). A new empty line is added by the action **"Lay a new
   line"** on the semaphore at the left column's lowest junction (a command that appends a line to the town file;
   at most 4 quarter lines); spec 07 adds dragging inside the quarter.
7. **Stable:** adding a building never moves those already standing in its line except to take the first free place.
8. Keep: stations' tracks, one way round, pockets "none", the heralds' notices, 3 × 6 density at the default view,
   the wilderness, items on the grass, the doorways.

## Tests
Critical tests, plus `tests/test_camp_layout.py` (new cases: Office positions ignored; band 0 / 1 / 2 membership and
order; overflow; stability when one building is added), `tests/test_gui_camp_browser.py`.

## Prompt
Use the prompt in docs/specs/README.md with `<NN-name>` = `06-three-bands`.
