"""The yard's fence: the pieces a script-first building's card is fenced with, as pixel art (docs/design/yards.md §3).

    python tools/fence_sprites.py

Drawn from the grids below on the ork mark's way (tools/logo.py): one letter a pixel, at 3× and 6× (`@2x`),
into `design-system/sprites/fence/`; the page draws them at 3 CSS px a pixel (`image-rendering: pixelated`):

- `row.png` (21×21): one picket, tip up, and the two thin rails to the next: the bottom row and the top fence;
- `side.png` (15×27): one picket of a side, as tall as the bottom ones, and the gap under it where the rail
  behind shows (the rail itself is the stylesheet's, yards.css);
- `post.png` (15×36): a gate post, pointed like the pickets, a little taller than the title bar.

Muted bronze wood (palette B): a step above the ground, a step below the card, never louder than one fire.
"""
from __future__ import annotations

import pathlib

from logo import grid_image

ROOT = pathlib.Path(__file__).resolve().parent.parent

# o outline, d shade, m wood, l lit edge, h highlight, n knot
COLOURS = {"o": "#120d08", "d": "#2b2116", "m": "#3f3120", "l": "#54422a", "h": "#665233", "n": "#120d08"}

GRIDS = {
    "row": [
        "..o....",
        ".olo...",
        "olmdooo",
        "olmdohh",
        "olmdooo",
        "olmdohh",
        "olmdooo",
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


def main() -> None:
    out = ROOT / "design-system" / "sprites" / "fence"
    out.mkdir(parents=True, exist_ok=True)
    for name, grid in GRIDS.items():
        grid_image(grid, COLOURS, 3).save(out / f"{name}.png")
        grid_image(grid, COLOURS, 6).save(out / f"{name}@2x.png")
    print(f"wrote {', '.join(GRIDS)} to {out}")


if __name__ == "__main__":
    main()
