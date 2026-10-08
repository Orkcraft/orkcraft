"""The ork that comes out of its building, and the pixel bubble it speaks in (docs/design/yards.md §4).

    python tools/visit_sprites.py [--preview FILE]

Drawn from the grids below on the ork mark's way (tools/logo.py): one letter a pixel, its head the head of the
ork's head alone (`logo.GRID`, the same green and tusks), a third of its building's height. At 2× and 4× (`@2x`):

- `orks/ork-stand.png` (12×9): the ork out of its door, facing you;
- `orks/ork-walk-a.png`, `ork-walk-b.png` (12×9): two steps of its walk, its head bobbing, facing left as it walks
  out; the page mirrors them as it walks back in (yards.css);
- `icons/thumb-up.png`, `thumb-down.png` (8×8 and its outline, 20 CSS px): a green pixel 👍 and 👎 in its bubble;
- `icons/bubble.png` (6×6, drawn at 2×): the bubble's frame as a nine-slice (`border-image`), its corners cut a
  pixel as a comic's are pixel; `icons/bubble-tail.png` (5×4): its tail, down to the ork's head.
"""
from __future__ import annotations

import argparse
import pathlib

from PIL import Image

from icon_sprites import outlined
from logo import GRID, SPRITE_COLOURS, grid_image

ROOT = pathlib.Path(__file__).resolve().parent.parent

COLOURS = SPRITE_COLOURS

# its head turned to the left: one eye, one tusk, the far ear behind
SIDE_HEAD = [
    "...FFFFFF...",
    "..FFFFFFFF.F",
    ".FFFFFFFFFFF",
    "FDDFFFFFFFF.",
    "FFFFFFFFFF..",
    ".TFFFFFFFF..",
    ".TFFFFFFF...",
    "..FFFFFF....",
]
BLANK = ["." * 12]

# only its head, a third of its building's height: facing you, and two steps of its walk (a bob)
ORKS = {"ork-stand": BLANK + GRID, "ork-walk-a": BLANK + SIDE_HEAD, "ork-walk-b": SIDE_HEAD + BLANK}

# the thumb in the bubble: green as the ork, a lit edge; 👎 is 👍 upside down
ICON_COLOURS = {"G": "#6ca420", "g": "#3f6b14", "L": "#a8d65a", "K": "#1a1813"}
THUMB_UP = [
    "...L....",
    "..LG....",
    "..GG....",
    "LLGGGGG.",
    "GGGGGGg.",
    "GGGGGGg.",
    "GGGGGg..",
    "gg......",
]

# the bubble: parchment inside, the camp's dark ink round it, a pixel off each corner
BUBBLE_COLOURS = {"W": "#efe6cc", "K": "#1a1813"}
BUBBLE = [
    ".KKKK.",
    "KWWWWK",
    "KWWWWK",
    "KWWWWK",
    "KWWWWK",
    ".KKKK.",
]
TAIL = [
    "KWWWK",
    ".KWK.",
    ".KWK.",
    "..K..",
]


def thumbs() -> dict[str, list[str]]:
    up = outlined(["." * 10] + ["." + r + "." for r in THUMB_UP] + ["." * 10])
    return {"thumb-up": up, "thumb-down": up[::-1]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", help="also write them side by side at 8×, for a look")
    args = ap.parse_args()
    sprites = ROOT / "design-system" / "sprites"
    for name, grid in ORKS.items():
        assert all(len(r) == 12 for r in grid) and len(grid) == 9, name
        grid_image(grid, COLOURS, 2).save(sprites / "orks" / f"{name}.png")
        grid_image(grid, COLOURS, 4).save(sprites / "orks" / f"{name}@2x.png")
    for name, grid in thumbs().items():
        grid_image(grid, ICON_COLOURS, 2).save(sprites / "icons" / f"{name}.png")
        grid_image(grid, ICON_COLOURS, 4).save(sprites / "icons" / f"{name}@2x.png")
    for name, grid in {"bubble": BUBBLE, "bubble-tail": TAIL}.items():
        grid_image(grid, BUBBLE_COLOURS, 2).save(sprites / "icons" / f"{name}.png")
        grid_image(grid, BUBBLE_COLOURS, 4).save(sprites / "icons" / f"{name}@2x.png")
    if args.preview:
        every = [(g, COLOURS) for g in ORKS.values()] + [(g, ICON_COLOURS) for g in thumbs().values()] \
            + [(BUBBLE, BUBBLE_COLOURS), (TAIL, BUBBLE_COLOURS)]
        sheet = Image.new("RGBA", (len(every) * 112, 144), (42, 36, 25, 255))
        for i, (g, c) in enumerate(every):
            sheet.alpha_composite(grid_image(g, c, 8), (i * 112 + 4, 8))
        sheet.save(args.preview)
    print(f"wrote {', '.join(ORKS)}, thumbs, bubble to {sprites}")


if __name__ == "__main__":
    main()
