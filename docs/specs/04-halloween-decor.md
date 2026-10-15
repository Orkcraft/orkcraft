# Spec 04 — Halloween decor (an art card for the owner + items for agy)

Branch `spec/04-halloween-decor` · model **flash** · design: v3-prompts.md §14 (items), decisions §22
**Builds:** agy · **Review:** light (docs/specs/README.md "Who builds")

## Part A — the owner generates the art (Gemini app or agy, no API)
Attach these references: `docs/design/img/references/v3/f1-town.jpg`, `b1-core.jpg` (same folder).
Prompt to paste:

> Pixel-art sprite sheet for a cozy top-down-front-view ork camp, same style, palette and pixel size as the attached
> frame. Eight separate Halloween decorations on a flat magenta (#ff00ff) background, evenly spaced in a 4×2 grid,
> each fully inside its cell, no text, no shadows outside the object, crisp dark 1-pixel outline: 1) a carved pumpkin
> with a warm glow inside, 2) a stack of three small pumpkins, 3) a scarecrow on a pole, 4) a cauldron on a small
> fire, 5) a lantern on a post, 6) a gravestone with a skull carving, 7) a cobweb draped between two fence stakes,
> 8) a crow on a fence post. Warm oranges and browns, muted purples; no bright yellow, no red.

Make 3 candidates; save them as `docs/design/img/references/v3/candidates/h1-halloween/1.png`, `2.png`, `3.png`,
commit and push on the branch. The PM session picks and cuts (`tools/camp_sheet.py --pick`) into
`design-system/sprites/v3/items/halloween-<name>.png`.

## Part B — agy, after the PM session has cut the sprites
1. Eight item files `design-system/items/halloween-<name>.json` in the existing item format (`id`, `name`, `sprite`,
   `by`, `why`), `by: "start"` (free decor, placed as often as liked), plus a new optional field
   `"season": {"from": "10-24", "to": "11-07"}`.
2. `orkcraft/realm/items.py`: an item with `season` is offered in the Items panel only while today (local date) is
   within it; one already placed **stays** after the season (it is the person's).
3. The Items panel (`js/camp/items.js`) shows seasonal items under a small heading "Halloween" while in season.
4. Office draws none (as for every item).

## Tests
Critical tests, plus `tests/test_items.py` (offered in season, not offered out of season, placed ones kept) and
`tests/test_camp_layout.py`.

## Prompt (Part B)
Use the prompt in docs/specs/README.md with `<NN-name>` = `04-halloween-decor`, adding: "Part A is done; do Part B."
