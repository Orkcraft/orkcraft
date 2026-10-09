"""The yard's fence: the pieces a script-first building's card is fenced with, as pixel art (docs/design/yards.md §3).

    python tools/fence_sprites.py

Drawn from the grids below on the ork mark's way (tools/logo.py): one letter a pixel, at 3× and 6× (`@2x`),
into `design-system/sprites/fence/`; the page draws them at 3 CSS px a pixel (`image-rendering: pixelated`):

- `row.png` (21×21): one picket, tip up, and the two thin rails to the next: the bottom row and the top fence;
- `side.png` (15×27): one picket of a side, as tall as the bottom ones, and the gap under it where the rail
  behind shows (the rail itself is the stylesheet's, yards.css);
- `post.png` (15×36): a gate post, pointed like the pickets, a little taller than the title bar;
- `corner-<1|2|3>[-r].png` (21×27): a yard's corner tusk by its building's renown (II an iron band), `axes.png` at III;
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
           }
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


# A yard's corners (yards.css ::after): a bone tusk curving in over the card at its bottom corners and the top fence's
# end, and the building's renown adds iron, never more bone (docs/design/growth.md §5): II a spiked iron band round
# each tusk's root, III a pair of crossed axes where the top fence meets the house (`axes.png`). The bone is old bone,
# under the card's words; the iron is as quiet as the wood. 7 × 9, the tusk's root at the bottom left, its tip curling
# right; the right corners wear it mirrored (`-r`).
TUSK = [
    "....ooo",
    "...obbo",
    "..obso.",
    ".obso..",
    ".obo...",
    "obso...",
    "obbso..",
    "obbso..",
    "obsso..",
]
BAND = {6: "oiiiio.", 7: "ijjjjio", 8: "oiiiio."}     # II: an iron band with a spike out at each side
IRON = {"i": "#4e585e", "j": "#6e7a80"}
BONE = {"b": "#b8ac90", "s": "#8a8070"}             # old bone: about 8:1 to the ground, the text's 15:1 above it


def tusk(level: int) -> list[str]:
    rows = list(TUSK)
    if level >= 2:
        rows = [BAND.get(y, r) for y, r in enumerate(rows)]
    return rows


AXES = [                      # III: two axes crossed, iron heads up, wooden hafts
    "ii.....ii",
    "iij...jii",
    ".iim.mii.",
    "...m.m...",
    "....m....",
    "...m.m...",
    "..m...m..",
]


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
    colours = {**COLOURS, **IRON, **BONE}
    for level in (1, 2, 3):
        grid = tusk(level)
        for side, g in (("", grid), ("-r", [r[::-1] for r in grid])):
            grid_image(g, colours, 3).save(out / f"corner-{level}{side}.png")
            grid_image(g, colours, 6).save(out / f"corner-{level}{side}@2x.png")
    grid_image(AXES, colours, 3).save(out / "axes.png")
    grid_image(AXES, colours, 6).save(out / "axes@2x.png")
    grid_image(PLINTH, STONE, 2).save(out / "plinth.png")
    grid_image(PLINTH, STONE, 4).save(out / "plinth@2x.png")
    print(f"wrote {', '.join(GRIDS)}, corner-1..3, axes, plinth to {out}")


if __name__ == "__main__":
    main()
