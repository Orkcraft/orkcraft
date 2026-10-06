# Building sprites — the flat set

The buildings' header sprites are being redrawn in the ork mark's style: flat pixels, no outline, no
shading, five colours (the mark's green, a darker green, ivory, gold and the dark of the ground), an
ork touch (tusks, horns, bones) on each. They replace the Warcraft 2 headers one sheet at a time.

| sheet | buildings | state |
|---|---|---|
| 1 | Town Hall, War Drum, Watchtower, Forge, Scroll Dump, Barracks, Lake of Insight, Loot Vault | done |
| 2 | Mill, Horn, Signpost, Pit, Catapult, Workshop, Task Fields, Council | |
| 3 | File Forest, Tally Crag, Custom | |

## Making a sheet

An image model draws eight buildings on one sheet, so they share a palette, a pixel size and a ground
line (one at a time they drift apart). The prompt:

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
pixel in screen pixels (about 16.6 on a 2000-wide sheet), `--preview` writes them side by side.

Office shows no building sprites; its huts are the same cards without the header.
