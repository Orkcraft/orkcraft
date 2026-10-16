# Spec 21 — entering a building: the room on the whole screen, settings behind a gear

Branch `spec/21-building-screen` · design: interiors.md §1 (read it first)
**Builds:** Claude · **Review:** light (docs/specs/README.md "Who builds")

## Do
Change only `orkcraft/gui/static/js/inside.js`, `orkcraft/gui/static/js/windows.js` (the entering only), the inside's
CSS, the Task board's room module where its size is set (`js/buildings/fields_inside.js`), and tests.
1. In Camp, entering a building that has a room hides the camp entirely: **a black screen**, the room **in the
   middle, roof off, as large as fits** (whole device pixels), lit like a stage (a soft light on its floor). Today's right-hand settings panel goes.
2. A **gear** at the room's top right slides the settings in (today's `InfoTab`, unchanged) and out; **Exit** and Esc
   leave, the camp's zoom and pan as they were.
3. **The Task board's cards grow** to interiors.md §2's size: slabs or planks at least a sixth of the room's width,
   their titles at the kit's label size or larger; more than eight show as a pile with `+N`.
4. A building with no room yet: a plain room (kit floor and walls) with today's large card in it, so every building
   enters the same way. Office unchanged.

## Tests
Critical tests, plus `tests/test_gui_camp_browser.py` (and the Task board's inside test if separate): entering hides
the camp (black round the room) and centres the room with no settings panel; the gear opens and closes the settings; Exit and Esc restore
zoom and pan; a building with no room shows the plain room; Office opens its card as today. Before/after shots of
the Task board entered into `docs/design/img/inside/`.
