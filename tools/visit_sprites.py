"""The ork that comes out of its building, and the pixel bubble it speaks in (docs/design/yards.md §4).

    python tools/visit_sprites.py [--preview FILE]

Drawn from the grids below on the ork mark's way (tools/logo.py): one letter a pixel, its head the head of the
ork's head alone (`logo.GRID`, the same green and tusks), a third of its building's height. At 2× and 4× (`@2x`);
the ork's own sprites are Scale2x'd to those sizes instead of blown up, so their pixels are as fine as its
building's (whose sprites are drawn at about a CSS pixel a pixel, twice as fine at @2x) and its edges round, and
lit as its building is (`shade`: the light from the top left, a dark rim below and right, the jaw and the brows in
shadow, a glint in each eye, each tusk's side shaded):

- `orks/ork-stand.png` (12×9): the ork out of its door, facing you;
- `orks/ork-walk-a.png`, `ork-walk-b.png` (12×9): two steps of its walk, its head bobbing, facing left as it walks
  out; the page mirrors them as it walks back in (yards.css);
- `icons/thumb-up.png`, `thumb-down.png` (20×20 with its outline, 20 CSS px, a pixel a CSS pixel): a green pixel 👍
  and 👎 in its bubble and in a building's Info (js/console.js `Thumb`): a fist over a leather cuff, its fingers
  parted by a shade, lit from the top left;
- `icons/settings.png` (20×20 the same way): an iron gear in its bubble (js/visit.js), its settings: its tier and AI
  tool. The gear means settings everywhere; the Mechanic's is a wrench (js/icons.js);
- `icons/bubble.png` (10×10, drawn at 2×): the bubble's frame as a nine-slice (`border-image`, 4 pixels a corner),
  its corners rounded in pixel steps; `icons/bubble-tail.png` (5×4): its tail, down to the ork's head.
"""
from __future__ import annotations

import argparse
import pathlib

from PIL import Image

from icon_sprites import outlined
from logo import GRID, SPRITE_COLOURS, grid_image

ROOT = pathlib.Path(__file__).resolve().parent.parent

# the ork lit as its building is (`shade`): its green's light, shade and rim, a tusk's shaded side, an eye's glint
SHADE_COLOURS = {"f": "#93c94a", "s": "#4f8418", "k": "#2e4f12", "t": "#b3a88c", "e": "#e8e0c8"}
COLOURS = {**SPRITE_COLOURS, **SHADE_COLOURS}

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

# the bubble's icons, drawn at 20×20 (their outline included), a pixel a CSS pixel at 1×, so they stay sharp at the
# bubble's 20 px: the thumb green as the ork, a lit edge, its fingers parted by a shade, a leather cuff; 👎 is 👍
# upside down. The gear iron, lit from the top left, its hole's wall in shade on that side.
ICON_COLOURS = {"G": "#6ca420", "g": "#3f6b14", "m": "#548a1a", "L": "#a8d65a", "K": "#1a1813",
                "H": "#8a6a42", "h": "#5e4528", "j": "#b08a58",
                "T": "#eef1f5", "l": "#b9c2cf", "D": "#7d8695", "d": "#4a525e"}
THUMB_UP = [
    "........LL........",
    ".......LGGg.......",
    ".......LGGg.......",
    "......LGGGg.......",
    "......LGGg........",
    ".....LGGGg........",
    "....LGGGGLLLLLLL..",
    "jjKLGGGGGGGGGGGGm.",
    "HHKLGGGGGGmmmmmmmg",
    "HHKLGGGGGGLLLLLLLg",
    "HHKLGGGGGGGGGGGGGg",
    "HHKLGGGGGGmmmmmmmg",
    "HHKLGGGGGGLLLLLLg.",
    "HHKLGGGGGGGGGGGGg.",
    "HHKLGGGGGGmmmmmmg.",
    "hhKmGGGGGGLLLLLg..",
    "hhKgggggggggggg...",
    "..................",
]
GEAR = [
    ".......TTTT.......",
    ".......Tlld.......",
    "...TT..Tlld..TT...",
    "..TllTTllllTTlDT..",
    "..TllllllllllDDd..",
    "...TllllddllDDd...",
    "...Tllld..TDDDd...",
    "TTTllld....TDDDTTT",
    "Tlllld......TDDDDd",
    "Tlllld......TDDDDd",
    "TddlllT....TDDDddd",
    "...TllDT..TDDDd...",
    "...TlDDDTTDDDDd...",
    "..TlDDDDDDDDDDDT..",
    "..TDDddDDDDddDDd..",
    "...Td..TDDd..Td...",
    ".......TDDd.......",
    ".......Tddd.......",
]

# the bubble: parchment inside, the camp's dark ink round it, each corner rounded in pixel steps over four pixels,
# so its sides read round as a comic's do, and stay pixel
BUBBLE_COLOURS = {"W": "#efe6cc", "K": "#1a1813"}
BUBBLE = [
    "...KKKK...",
    ".KKWWWWKK.",
    ".KWWWWWWK.",
    "KWWWWWWWWK",
    "KWWWWWWWWK",
    "KWWWWWWWWK",
    "KWWWWWWWWK",
    ".KWWWWWWK.",
    ".KKWWWWKK.",
    "...KKKK...",
]
TAIL = [
    "KWWWK",
    ".KWK.",
    ".KWK.",
    "..K..",
]


def scale2x(grid: list[str]) -> list[str]:
    """The grid at twice its size by Scale2x (EPX): a pixel art's own way up, its diagonals stepped finer and no
    colour added, where a plain enlargement only makes its pixels bigger."""
    h, w = len(grid), len(grid[0])

    def at(y: int, x: int) -> str:
        return grid[y][x] if 0 <= y < h and 0 <= x < w else "."
    out: list[str] = []
    for y in range(h):
        top, bottom = [], []
        for x in range(w):
            p, a, b, c, d = grid[y][x], at(y - 1, x), at(y, x + 1), at(y, x - 1), at(y + 1, x)
            top += [a if c == a and c != d and a != b else p, b if a == b and a != c and b != d else p]
            bottom += [c if d == c and d != b and c != a else p, d if b == d and b != a and d != c else p]
        out += ["".join(top), "".join(bottom)]
    return out


def shade(grid: list[str]) -> list[str]:
    """The ork's head lit from the top left, at Scale2x's grain: its green's edge below and right a dark rim (k),
    above and left its light (f); the jaw, the far side and the brows over its eyes in shade (s); a glint at each eye's
    top left (e) and each tusk's right side shaded (t). Pixels of another colour (a hat) stay as they are."""
    h, w = len(grid), len(grid[0])

    def at(y: int, x: int) -> str:
        return grid[y][x] if 0 <= y < h and 0 <= x < w else "."
    out = [list(r) for r in grid]
    for y in range(h):
        for x in range(w):
            p = grid[y][x]
            if p == "F":
                if at(y + 1, x) == "." or at(y, x + 1) == ".":
                    out[y][x] = "k"
                elif at(y - 1, x) == "." or at(y, x - 1) == ".":
                    out[y][x] = "f"
                elif at(y + 2, x) == "." or at(y, x + 2) == "." or at(y + 1, x) in "TD":
                    out[y][x] = "s"
            elif p == "D" and at(y - 1, x) != "D" and at(y, x - 1) != "D":
                out[y][x] = "e"
            elif p == "T" and at(y, x + 1) != "T":
                out[y][x] = "t"
    return ["".join(r) for r in out]


def framed(grid: list[str]) -> list[str]:
    """An 18×18 drawing in a pixel of room each side, and its outline there: 20×20."""
    return outlined(["." * 20] + ["." + r + "." for r in grid] + ["." * 20])


def bubble_icons() -> dict[str, list[str]]:
    up = framed(THUMB_UP)
    return {"thumb-up": up, "thumb-down": up[::-1], "settings": framed(GEAR)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", help="also write them side by side at 8×, for a look")
    args = ap.parse_args()
    sprites = ROOT / "design-system" / "sprites"
    for name, grid in ORKS.items():
        assert all(len(r) == 12 for r in grid) and len(grid) == 9, name
        fine = shade(scale2x(grid))
        grid_image(fine, COLOURS, 1).save(sprites / "orks" / f"{name}.png")
        grid_image(scale2x(fine), COLOURS, 1).save(sprites / "orks" / f"{name}@2x.png")
    for name, grid in bubble_icons().items():
        assert len(grid) == 20 and all(len(r) == 20 for r in grid), name
        grid_image(grid, ICON_COLOURS, 1).save(sprites / "icons" / f"{name}.png")
        grid_image(grid, ICON_COLOURS, 2).save(sprites / "icons" / f"{name}@2x.png")
    for name, grid in {"bubble": BUBBLE, "bubble-tail": TAIL}.items():
        grid_image(grid, BUBBLE_COLOURS, 2).save(sprites / "icons" / f"{name}.png")
        grid_image(grid, BUBBLE_COLOURS, 4).save(sprites / "icons" / f"{name}@2x.png")
    if args.preview:
        every = [(g, COLOURS) for g in ORKS.values()] + [(g, ICON_COLOURS) for g in bubble_icons().values()] \
            + [(BUBBLE, BUBBLE_COLOURS), (TAIL, BUBBLE_COLOURS)]
        sheet = Image.new("RGBA", (len(every) * 112, 144), (42, 36, 25, 255))
        for i, (g, c) in enumerate(every):
            sheet.alpha_composite(grid_image(g, c, 8), (i * 112 + 4, 8))
        sheet.save(args.preview)
    print(f"wrote {', '.join(ORKS)}, thumbs, gear, bubble to {sprites}")


if __name__ == "__main__":
    main()
