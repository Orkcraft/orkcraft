# Spec 26 — five buildings at the first start; the others hidden

## Round 2 (16 October): two test fixes, one small change — nothing else
On the branch `spec/26-five-buildings` (round 1 `1433e8c`; the code is right). The PM allows these old tests to change:
1. `tests/test_gui_browser.py::test_a_test_bench_is_set_up_by_a_frame_dragged_round_its_buildings` builds a Test bench
   through the Build dialog, which spec 26 hides. In that test only, turn `catalog.all_types` on in the test town's
   settings (the way the suite already writes settings), so the Build dialog offers the Test bench again.
2. `tests/test_gui_browser.py` builds its per-type `TYPES` list from `catalog_types()`, so it now covers only the five.
   Build that list with `catalog.all_types` on (pass the settings dict), so every type keeps its browser test.
3. `builder.catalog_types` and `town_hall.buildable`: read the settings once per call and pass the dict to
   `offered()`, not once per type.
Tests: the critical tests, `tests/test_first_types.py`, `tests/test_gui_browser.py` (whole file), and the test files of
the modules touched.


Branch `spec/26-five-buildings` · design: decisions §35 · **Builds:** Claude · **Review:** light

## What
A person starting Orkline is offered **five buildings**, no more:

| type id | building |
|---|---|
| `fields` | Task board |
| `barracks` | Agent pool |
| `loot_vault` | Review gate |
| `watchtower` | External listeners |
| `scrolls` | Wiki |

1. `orkcraft/realm/catalog.py`: `FIRST_TYPES = frozenset({...})` with the five, and one function
   `offered(type_id: str, settings: dict | None = None) -> bool`: true for the five, for every landscape type
   (`LANDSCAPE`: no ork, the camp's look), and for any type when the setting `catalog.all_types` is true (default
   false; a key in settings.json only, no control in the interface). System, scratch and retired types stay hidden as
   today.
2. Use `offered()` at **every place that offers a building to raise**. Known ones: `orkcraft/gui/builder.py`
   `catalog_types` (the Build dialog) and `for_role`, `orkcraft/core/workers/town_hall.py` `buildable` (the
   Workchief's planner), the ready towns of *Punk ork* (`orkcraft/realm/town_presets.py`, `town_builder.py`; a preset
   or a plan keeps only offered buildings and drops the roads to the ones it dropped), and any growth or onboarding
   suggestion that names a building (`realm/growth.py`, `gui/onboarding.py`, `realm/interview.py`, `realm/masonry.py`:
   grep for where a type is proposed). Find the others with grep; list them in the commit message.
3. **Nothing already built changes.** A town scroll with a Test bench, a Review board or any other type loads, draws
   and works as today; its building can be opened, moved and removed. Old scrolls and settings keep loading.
4. Mission 1 is unchanged (it raises the Task board, the Agent pool, the Review gate, External listeners).

## Not in this spec
No type is deleted; no art, no CSS; no change to Office or Camp drawing; no setting in the interface.

## Tests
New `tests/test_first_types.py`: the Build dialog's list (`catalog_types()`) has exactly the five plus the landscape;
`buildable()` likewise; every *Punk ork* preset raises only offered types and has no road to a dropped one; with
`catalog.all_types` true the lists are as before this spec; a scroll with a `lab` and a `council` loads and keeps them.
Run the critical tests (CLAUDE.md) plus the test files of every module touched, and `tests/test_gui_browser.py -k build`.
