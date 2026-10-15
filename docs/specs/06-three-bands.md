# Spec 06 — the camp lays itself out in three bands

Branch `spec/06-three-bands` · model **pro** · design: decisions-2026-10.md §20 (all of it), design-system-v3.md §4,
§4b, §4c, §4f · after Halloween

## Do
In `orkcraft/gui/static/js/camp/layout.js` (pure, tested in Node by `tests/test_camp_layout.py`):
1. **Camp ignores Office positions** for buildings (they stay Office's own drawing in `js/town.js`).
2. **Band 0, the wall** (decisions §20, "The wall band holds the border and the dispatcher"), left to right: the
   lookout (`watchtower`, the way in) · Drop file here (`pit`) · the Task board (`fields`, its booth and siding between
   the wall and row 1, the siding joining line 1 at its start) · the Calendar (`war_drum`) and any type marked
   `notices: true` in a small table in layout.js · Metrics (`crag`) · the Publisher's catapult (`catapult`) at the
   right end, its track a spur up from line 1's east end to a buffer stop by the wall (line 2's buffer stop retired).
   Stops reach line 1 by spurs, as the Calendar does today (§4f).
3. **Band 1, line 1's row, the processing**, in this fixed order of types: Router (`signpost`) · Transformer
   (`mill`) · Agent pool (`barracks`, the depot) · Research (`mine`) · Script (`workshop`) · the benches (`lab`,
   `ux_lab`) · Review board (`council`) · Inspector (`lake`) · Review gate (`loot`) at the east end, the person's
   home beside it. Absent types leave no gap. More than fit (8 places, depot = 2) overflow into band 2.
4. **Band 2+, line 2's row and on, the person's quarter:** every other building, in the order kept in the town file
   (`scroll` field `quarter: [building ids]`, new; appended when a building is built). Spec 07 adds dragging.
5. **Stable:** adding a building never moves the ones already standing in its band except to close nothing (it takes
   the first free place).
6. Keep: stations' tracks, one way round, the return line, pockets "none", the heralds' notices, 3 × 6 density, the
   wilderness, items on the grass.

## Tests
Critical tests, plus `tests/test_camp_layout.py` (new cases: Office positions ignored; band 0 / 1 / 2 membership and
order; overflow; stability when one building is added), `tests/test_gui_camp_browser.py`.

## Prompt
Use the prompt in docs/specs/README.md with `<NN-name>` = `06-three-bands`.
