# Spec 07 — the person's quarter: drag buildings in Camp

Branch `spec/07-quarter-drag` · model **flash** · design: decisions §20 · after spec 06
**Builds:** agy · **Review:** light (docs/specs/README.md "Who builds")

## Do
1. In Camp, a building in the quarter (band 2+) can be dragged with the mouse (and a long press on touch). While
   dragging, the places of the quarter show as faint outlines; dropping on a place moves it there (others shift by one
   along the order); dropping anywhere else puts it back.
2. The new order is saved in the town file's `quarter` list through a command (the same way items are saved:
   `orkcraft/realm/items.py` `place`/`move` and their GUI command, as a pattern).
3. Buildings of bands 0 and 1 are not draggable (the cursor says so; a tooltip "This one stands on the main line").
4. Office unchanged.

## Tests
Critical tests, plus `tests/test_camp_layout.py`, a browser test in `tests/test_gui_camp_browser.py`: drag a quarter
building to another place, reload, it stays; a band-1 building does not drag.

## Prompt
Use the prompt in docs/specs/README.md with `<NN-name>` = `07-quarter-drag`.
