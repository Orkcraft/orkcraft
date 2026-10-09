"""The yard's fence: the pieces a script-first building's card is fenced with, as pixel art (docs/design/yards.md §3).

    python tools/fence_sprites.py

Drawn from the grids below on the ork mark's way (tools/logo.py): one letter a pixel, at 3× and 6× (`@2x`),
into `design-system/sprites/fence/`; the page draws them at 3 CSS px a pixel (`image-rendering: pixelated`):

- `row.png` (21×21): one picket, tip up, and the two thin rails to the next: the bottom row and the top fence;
- `side.png` (15×27): one picket of a side, as tall as the bottom ones, and the gap under it where the rail
  behind shows (the rail itself is the stylesheet's, yards.css);
- `post.png` (15×36): a gate post, pointed like the pickets, a little taller than the title bar;
- `plinth.png` (16×8, drawn at 2× like the footing): the paved slab every building stands on in Camp, the road's tan,
  where its roads meet it (docs/design/yards.md §3f).

Muted bronze wood (palette B): a step above the ground, a step below the card, never louder than one fire.
"""
from __future__ import annotations

import pathlib

from logo import grid_image

ROOT = pathlib.Path(__file__).resolve().parent.parent

# o outline, d shade, m wood, l lit edge, h highlight, n knot
# dark, low-chroma wood a step or two over the town's ground (#141210): an edge that never pulls the eye from a card
COLOURS = {"o": "#0b0907", "d": "#1c1814", "m": "#262019", "l": "#302820", "h": "#3a3026", "n": "#0b0907"}
# the plinth's stones: the road's tan (#8f8166), its lit top, its mortar, its shadow
STONE = {"t": "#b5a585", "s": "#8f8166", "j": "#5f5545", "k": "#2a251c"}

GRIDS = {
    "row": [                  # its rails first, its picket last: a row of whole tiles ends on a picket at the corner
        ".....o.",
        "....olo",
        "oooolmd",
        "ohholmd",
        "oooolmd",
        "ohholmd",
        "oooolmd",
    ],
    "side": [
        "..o..",
        ".olo.",
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
        ".olo.",
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
    grid_image(PLINTH, STONE, 2).save(out / "plinth.png")
    grid_image(PLINTH, STONE, 4).save(out / "plinth@2x.png")
    print(f"wrote {', '.join(GRIDS)}, plinth to {out}")


if __name__ == "__main__":
    main()
