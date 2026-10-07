"""The road handle and the target brackets: the pieces of pulling a road out of a hut, as pixel art.

    python tools/road_sprites.py

Drawn from the grids below on the ork mark's way (tools/logo.py): one letter a pixel, at 2× and 4× (`@2x`),
into `design-system/sprites/icons/`:

- `road-handle.png` (22×22): the `+` on a hut's card the person pulls a road out of (js/hut.js): a gold
  cross on a dark plate in a round, road-coloured rim, a pixel clear of it all round;
- `road-target.png` (18×18): four corner brackets, the hut the pulled road would land on, as an RTS marks
  its target; a nine-slice, the CSS stretches its middles (layout.css `.gui-hut.is-target`).
"""
from __future__ import annotations

import pathlib

from logo import grid_image

ROOT = pathlib.Path(__file__).resolve().parent.parent

# K outline (`canvas`-dark), R rim (`road-selected`), B plate (`panel-raised`), Y gold (`ink-gold`)
COLOURS = {"K": "#1a1813", "R": "#d9a066", "B": "#3a2f1f", "Y": "#f2c66d"}

GRIDS = {
    "road-handle": [
        "...KKKKK...",
        "..KRRRRRK..",
        ".KRBBBBBRK.",
        "KRBBBYBBBRK",
        "KRBBBYBBBRK",
        "KRBYYYYYBRK",
        "KRBBBYBBBRK",
        "KRBBBYBBBRK",
        ".KRBBBBBRK.",
        "..KRRRRRK..",
        "...KKKKK...",
    ],
    "road-target": [
        "YYY...YYY",
        "YKK...KKY",
        "YK.....KY",
        ".........",
        ".........",
        ".........",
        "YK.....KY",
        "YKK...KKY",
        "YYY...YYY",
    ],
}


def main() -> None:
    out = ROOT / "design-system" / "sprites" / "icons"
    for name, grid in GRIDS.items():
        grid_image(grid, COLOURS, 2).save(out / f"{name}.png")
        grid_image(grid, COLOURS, 4).save(out / f"{name}@2x.png")
    print(f"wrote {', '.join(GRIDS)} to {out}")


if __name__ == "__main__":
    main()
