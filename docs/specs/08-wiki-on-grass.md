# Spec 08 — the Wiki on the grass among its readers

> **Parked (decisions §36, 16 October):** outside the three tracks; a hypothesis for after the testers. Do not build.

Branch `spec/08-wiki-on-grass` · model **flash** · design: design-system-v3.md §4c rule 1 (amended 15 October) · after spec 06
**Builds:** agy · **Review:** light (docs/specs/README.md "Who builds")

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
5. **Several Wikis:** the first stands on line 0.5's grass between the Task board and the Review gate; each other
   Wiki by rule 1 for its own readers; when two want the same spot, the later one takes the next nearest.
6. **Hover or tap a Wiki:** all its readers get a soft outline (the kit's teal, never yellow or red) while the
   pointer stays; nothing else changes.
7. **The person may drag a Wiki** to another free grass spot, as items are dragged (`js/camp/items.js`, `grass.js`
   for where it fits); the spot is saved in the town file; its paths are redrawn.

## Tests
Critical tests, plus `tests/test_camp_layout.py` (inside the loop; never on track/bed/path; up to three paths;
fallback), `tests/test_gui_camp_browser.py`.

## Prompt
Use the prompt in docs/specs/README.md with `<NN-name>` = `08-wiki-on-grass`.
