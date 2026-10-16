# Spec 24 — doors: an ork walks only into a building that has one

Branch `spec/24-open-air-buildings` · model **flash** · design: interiors.md §3
**Builds:** agy · **Review:** light (docs/specs/README.md "Who builds")

## Do
Change only `orkcraft/gui/static/js/camp/steward.js`, `orkcraft/gui/static/js/camp/orks.js` and
`tests/test_gui_camp_browser.py`. Change nothing outside these files.
1. A building whose sprite has a `doorway` in the manifest (`doorwayOf(file)`): as today, its ork steps out of the
   doorway (`OutOfDoor`).
2. A building with **no** doorway is open-air: no `OutOfDoor` and no walking out from behind its foot. Its ork stands
   beside it on its stop's side, at the building's foot, in the pose it has today (works, waits, asks); the click on
   it does what the click on the stepped-out ork does today.

## Tests
Critical tests, plus `tests/test_gui_camp_browser.py`: a Task board (no doorway) shows its ork standing beside it and
no `.gui-camp__exit`; a building with a doorway still shows its ork in the doorway; a click on either opens its
terminal. Every new test shown to fail without its code.
