"""The yard's fence: the pieces a script-first building's card is fenced with, as pixel art (docs/design/yards.md §3).

    python tools/fence_sprites.py

Drawn from the grids below on the ork mark's way (tools/logo.py): one letter a pixel, at 3× and 6× (`@2x`),
into `design-system/sprites/fence/`; the page draws them at 3 CSS px a pixel (`image-rendering: pixelated`):

- `row.png` (21×21): one picket, tip up, and the two thin rails to the next: the bottom row and the top fence;
- `side.png` (15×27): one picket of a side, as tall as the bottom ones, and the gap under it where the rail
  behind shows (the rail itself is the stylesheet's, yards.css);
- `post.png` (15×36): a gate post, pointed like the pickets, a little taller than the title bar;
- `corner-<1|2|3>.png` (33×27): a yard's corner post by its building's renown: lashed, taller, with bone tusks;
- `plinth.png` (16×8, drawn at 2× like the footing): the paved slab every building stands on in Camp, the road's tan,
  where its roads meet it (docs/design/yards.md §3f).

Warm wood, its brightest pixel at about 3:1 to the town's ground: the card's shape reads from across the town,
yet it stays under the card's muted words (about 7:1) and its text (about 15:1), and never louder than one fire.
"""
from __future__ import annotations

import pathlib

from logo import grid_image

ROOT = pathlib.Path(__file__).resolve().parent.parent

# o outline, d shade, m wood, l lit edge, h highlight, n knot, p a picket's point (lit wood, never bone: bone is as
# bright as the card's text and would pull the eye round every card)
COLOURS = {"o": "#1a1813", "d": "#3e3122", "m": "#5a4730", "l": "#6b5538", "h": "#7a6240", "n": "#1a1813", "p": "#8a7048",
           "r": "#8a7048",   # rope: each picket lashed to its rail, the orks' way (no nails)
           "T": "#ece4cf"}   # bone: only on a corner post at renown III, never along the run
# the plinth's stones: the road's tan (#8f8166), its lit top, its mortar, its shadow
STONE = {"t": "#b5a585", "s": "#8f8166", "j": "#5f5545", "k": "#2a251c"}

GRIDS = {
    "row": [                  # its rail first, its picket last, outlined both sides: a row of whole tiles ends
        "....o..",            # on a full picket at the corner; one plain rail, so the fence reads as one calm line
        "...opo.",
        "..olmdo",
        "..olmdo",
        "hhhrrro",            # the rail, lashed to the picket with rope
        "dddlmdo",
        "..olmdo",
    ],
    "side": [
        "..o..",
        ".opo.",
        "olmdo",
        "olmdo",
        "olmdo",
        "olmdo",
        "ooooo",
        ".....",
        ".....",
    ],
    "post": [
        "..o..",
        ".opo.",
        "olhlo",
        "olmdo",
        "ooooo",
        "olhdo",
        "olmdo",
        "olmdo",
        "olndo",
        "olmdo",
        "olmdo",
        "olmdo",
    ],
}


# A yard's corner posts (yards.css ::after): thicker than a picket and lashed twice, at its bottom corners and the top
# fence's end. They grow with the building's renown (docs/design/growth.md §5), the fence's only ornament: I a lashed
# post, II taller with a longer point, III a pair of bone tusks. 11 × 9, the post in the middle seven columns.
CORNER_BODY = {
    1: ["...o...", "..opo..", ".ophdo.", "olmmmdo", "orrrrro", "olmmmdo", "orrrrro", "olmmmdo", "olmmmdo"],
    2: ["...o...", "..opo..", "..opo..", ".ophdo.", "olmmmdo", "orrrrro", "olmmmdo", "orrrrro", "olmmmdo"],
}
CORNER_BODY[3] = CORNER_BODY[2]
TUSKS = [(1, 5), (1, 4), (0, 3), (0, 2), (0, 1), (9, 5), (9, 4), (10, 3), (10, 2), (10, 1)]   # out of the post's sides, curving up


def corner(level: int) -> list[str]:
    rows = [list(".." + r + "..") for r in CORNER_BODY[level]]
    if level == 3:
        for x, y in TUSKS:
            rows[y][x] = "T"
    return ["".join(r) for r in rows]


PLINTH = [
    "tttttttt",
    "sssjssss",
    "sssjssss",
    "kkkkkkkk",
]


def main() -> None:
    out = ROOT / "design-system" / "sprites" / "fence"
    out.mkdir(parents=True, exist_ok=True)
    for name, grid in GRIDS.items():
        grid_image(grid, COLOURS, 3).save(out / f"{name}.png")
        grid_image(grid, COLOURS, 6).save(out / f"{name}@2x.png")
    for level in (1, 2, 3):
        grid_image(corner(level), COLOURS, 3).save(out / f"corner-{level}.png")
        grid_image(corner(level), COLOURS, 6).save(out / f"corner-{level}@2x.png")
    grid_image(PLINTH, STONE, 2).save(out / "plinth.png")
    grid_image(PLINTH, STONE, 4).save(out / "plinth@2x.png")
    print(f"wrote {', '.join(GRIDS)}, corner-1..3, plinth to {out}")


if __name__ == "__main__":
    main()
