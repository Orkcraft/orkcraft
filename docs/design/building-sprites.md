# Building sprites — the flat set

The buildings' header sprites are being redrawn in the ork mark's style: flat pixels, no outline, no
shading, five colours (the mark's green, a darker green, ivory, gold and the dark of the ground), an
ork touch (tusks, horns, bones) on each. All nineteen catalog buildings have one; the Warcraft 2 headers are gone.

| sheet | buildings | state |
|---|---|---|
| 4 (2026-10-10) | all twenty in one sheet, each with a silhouette of its own: Town Hall the only gabled house; External listeners a tower on stilts with ear-trumpets; Task board a notice board; Calendar a war drum; Agent pool three tents; Review board a ring of stones round a fire; Wiki a pyramid of scrolls; Research a mine cart with ore; Audio briefing a gramophone; Branches & PRs a furnace with a chimney to one side; Review gate a gatehouse; Publisher a catapult; Test bench an open gantry with a cog and a gauge; UX bench a round tower with a flask; Script a lean-to over a workbench; Drop files a pit; Router a signpost; Transformer a windmill; Metrics a rock spire; Sound alerts a horn on a stand | done: `tools/sheet.py SHEET <the twenty types> --cell 7.5 --scale 2`, the dark inside the Test bench's and the Catapult's open frames made transparent; the flag points (`js/icons.js` `FLAG_AT`) found again. The UX bench's waits under `ux_lab/` for its type |
| 1–3 and the single ones before | the first flat set: most of them a box with a gabled roof and a door, told apart only by their details | replaced by sheet 4; File Forest, Lake and Custom keep theirs (retired types, old scrolls only) |

## Making a sheet

An image model draws the buildings on one sheet, so they share a palette, a pixel size and a ground
line (one at a time they drift apart). Sheet 4 asked for all twenty at once, 5 × 4, the first rule being
that each has a silhouette of its own and only the Town Hall is a gabled house; the eight-building
prompt it grew from:

```
A sprite sheet of 8 minimal flat pixel-art buildings for an orc-themed developer tool, arranged in
a 4×2 grid with generous empty space between them, each building centered in its own cell.
Every building is a front view, symmetrical where possible, about 28×17 large chunky square pixels,
every pixel clearly visible, same pixel size and same ground line for all eight.
Strict 5-color palette for ALL buildings, nothing else: green #86c062 (walls and roofs),
dark green #628a4c (windows, roof details), ivory #ece4cf (tusks, horns, bones, trims),
gold #e8b94a (one small accent per building: a flag, a flame, a coin, a sign),
near-black #1a1813 (doors, openings, roof shadow lines, background).
No outline, no shading, no gradients, no dithering, no texture, no anti-aliasing, no ground, no scenery.
Orc touch on each: curved ivory tusks or horns as roof finials.
The eight buildings, left to right, top to bottom: <the list>.
Plain #1a1813 background. Modern, iconic, sober, readable at 32px — brand icons, not a game screenshot.
```

Then cut it: `python tools/sheet.py SHEET <the eight types in reading order>` finds each building,
reads it cell by cell onto the palette, makes the ground around it transparent and writes
`design-system/sprites/buildings/<type>/header.png` at 3× (and `@2x` at 6×). `--cell` is the sheet's
pixel in screen pixels (about 16.6 on a 2000-wide sheet; the second sheet was drawn finer, about 11,
and cut at `--scale 2` so its buildings come out the same size), `--preview` writes them side by side.
Parts closer than three pixels (a ring of stones) make one building.

Office shows no building sprites; its huts are the same cards without the header.

Two things are added to a sprite and never drawn into it: its renown and goal, a flag on its roof, the
stones under it and an annex beside it (docs/design/growth.md §5; the flag gold at level III, the one
exception to a single gold accent), and its biome (`header-<biome>.png`, made from
the flat one by `tools/growth_sprites.py`; docs/design/war-map.md §3).
