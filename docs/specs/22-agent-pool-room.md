# Spec 22 — the Agent pool's room: bays, orks at work, the idle bench

Branch `spec/22-agent-pool-room` · design: interiors.md §2 (the Agent pool row), §5 (art card i-depot) · after 21
**Builds:** Claude · **Review:** light; the owner looks at the shots before the merge

## Part A — art (the owner, interiors.md §5 "i-depot"), then the PM session cuts it once to
`design-system/sprites/v3/inside/depot-room.png` and its `@hd*` WebP (CLAUDE.md "Art"; `tools/camp_sheet.py`).

## Part B — the room
Change only a new `orkcraft/gui/static/js/buildings/barracks_inside.js`, `js/buildings/barracks.js` (to export
`inside`), its CSS, and tests.
1. The room: `depot-room` as the floor. A big bay per run slot of the pool (🥩 n / 8, at most six bays; more show `+N`),
   sized by interiors.md §2. In a bay with a run: its ork at the room's scale, as large as its cart, its task in a
   bubble over them, readable at the kit's label size (the same words as the camp's bubble); ❓ over an ork who asks.
2. Idle orks sit on the bench by the back wall.
3. A click on an ork opens its console (as the camp's click does). The empty bay's sign is **Add ork** (the existing
   command).
4. Words through `say()`; plain words where money is (a run's cost stays in the console, not drawn).

## Tests
Critical tests, plus `tests/test_gui_camp_browser.py`: two runs and one idle ork draw two busy bays and one ork on
the bench; ❓ on the asking ork; a click opens its console; *Add ork* runs the command. Shots into
`docs/design/img/inside/`.
