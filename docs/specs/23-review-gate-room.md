# Spec 23 — the Review gate's room: the results on the table, the waybill, pass or send back

Branch `spec/23-review-gate-room` · design: interiors.md §2 (the Review gate row), §5 (art card i-gate); decisions
§24 (the words) · after 21
**Builds:** Claude · **Review:** light; the owner looks at the shots before the merge

## Part A — art (the owner, interiors.md §5 "i-gate"), then the PM session cuts it once to
`design-system/sprites/v3/inside/gate-room.png` and its `@hd*` WebP.

## Part B — the room
Change only a new `orkcraft/gui/static/js/buildings/loot_vault_inside.js`, `js/buildings/loot_vault.js` (to export
`inside`), its CSS, and tests.
1. The results waiting at the gate on the floor's three lots (more show `+N`), each a **large crate** (as tall as an
   ork, interiors.md §2) with a **bubble** over it holding its title at the kit's label size and its one state.
2. A click opens its waybill over the room (today's waybill, js/camp/waybill.js) with **Pass**, **Needs another
   round** (a note) and **Not this** (a reason chip), decisions §24's words; the commands are today's.
3. Passed: the crate leaves through the far door as the barrier lifts (no motion under reduced motion). The last few
   passed stand stacked by the exit; a click opens its waybill read-only.

## Tests
Critical tests, plus `tests/test_gui_camp_browser.py`: two waiting results draw two large crates with readable titles; a click opens
the waybill with the three actions; Pass runs today's pass and the crate leaves its lot; the stack shows the last
passed. Shots
into `docs/design/img/inside/`.
