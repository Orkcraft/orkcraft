# Spec 08 — the Wiki on the grass among its readers

Branch `spec/08-wiki-on-grass` · model **flash** · design: design-system-v3.md §4c rule 1 (amended 15 October) · after spec 06

## Do
In `js/camp/layout.js` and `js/camp/services.js`:
1. The first Wiki (`scrolls`) takes no place in any band. It stands on free grass **inside the loop**, at the free
   point closest to the weighted centre of its readers (a reader = a building whose config names this Wiki in
   `notes`, or that the Wiki serves through its MCP entry; weight = reads in the last 7 days, 1 if unknown).
2. Free grass = not track, not its bed, not a path, not within one cell of a building, not an item. Search the cells
   inside the loop; pick the nearest fitting the Wiki's sprite.
3. A 16-art-px footpath runs from its door to each of up to three readers (the heaviest), crossing a line only on a
   level crossing (`track/crossing.png`) at a plain straight.
4. No fitting grass: today's rule (beside its busiest reader).

## Tests
Critical tests, plus `tests/test_camp_layout.py` (inside the loop; never on track/bed/path; up to three paths;
fallback), `tests/test_gui_camp_browser.py`.

## Prompt
Use the prompt in docs/specs/README.md with `<NN-name>` = `08-wiki-on-grass`.
