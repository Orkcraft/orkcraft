"""The AI tools' marks and the Do not disturb horn, as Camp's pixel icons.

    python tools/icon_sprites.py [--preview FILE]

Drawn from the grids below on the road sprites' way (tools/road_sprites.py): one letter a pixel, and
every empty pixel beside a drawn one becomes the house's dark outline, so a grid holds only its colours.
At 1× (16×16) and 2× (`@2x`), into `design-system/sprites/icons/`:

- `harness-<tool>.png`: the tool's mark in a harness scheme, in a toast, the settings and the onboarding
  (js/icons.js `ToolMark`), each a simple sign of its own in the tool's colours, no one's logo:
  Claude an orange starburst, Antigravity an arch in Google's four colours, Codex a green tile with a
  `>_` prompt, Hermes a purple winged staff, pi a rose tile with π, Cursor a grey cube;
- `notify-on.png`, `notify-off.png`: the horn beside the portrait (js/portrait.js `Toggles`), a bone
  speaking-horn with a gold rim while the town may call, the same horn struck through while Do not
  disturb holds;
- `day.png`, `night.png`: the hour in the middle of the HUD (js/chrome.js `Hour`), as the day and night
  dial of an old strategy game: a gold sun while the orks work, a pale moon in quiet hours.

The Office draws the same signs as small SVGs (js/icons.js `TOOL_SVG`, `HORN`), in the same colours.
"""
from __future__ import annotations

import argparse
import pathlib

from PIL import Image

from logo import grid_image

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUTLINE = "#1a1813"

COLOURS = {
    "K": OUTLINE,
    "O": "#d97757", "o": "#b5583a",                                  # Claude: its clay orange, a shade
    "B": "#4285f4", "R": "#ea4335", "Y": "#fbbc05", "G": "#34a853",  # Antigravity: Google's four
    "C": "#10a37f", "c": "#0b7c60",                                  # Codex: the green tile, a shade
    "V": "#a855f7", "v": "#d8b4fe",                                  # Hermes: purple, lilac wings
    "P": "#e5395b", "p": "#b8233f",                                  # pi: rose, a shade
    "T": "#e3e8ef", "L": "#9aa5b4", "D": "#4a525e",                  # Cursor: the cube's three faces
    "W": "#f4efe2",                                                  # the white on a tile
    "I": "#ece4cf", "S": "#b5ab92", "H": "#7a6240", "A": "#e8b94a",  # the horn: bone, shade, wood, gold
    "X": "#e0453a",                                                  # the stroke through it
    "U": "#f2c14e", "u": "#c98a2a",                                  # the sun: gold, its shade
    "M": "#dde3ec", "m": "#9aa5b4",                                  # the moon: pale, its shade
}

GRIDS = {
    "harness-claude": [
        "................",
        ".......OO.......",
        "..O....OO....O..",
        "...O...OO...O...",
        "....O..OO..O....",
        ".....O.OO.O.....",
        "......OOOO......",
        ".OOOOOOOOOOOOOO.",
        ".ooooooOOoooooo.",
        "......oOOo......",
        ".....o.oo.o.....",
        "....o..oo..o....",
        "...o...oo...o...",
        "..o....oo....o..",
        ".......oo.......",
        "................",
    ],
    "harness-agy": [
        "................",
        "................",
        "......RRYY......",
        "....RRRRYYYY....",
        "...RRR....YYY...",
        "..BRR......YYG..",
        "..BB........GG..",
        "..BB........GG..",
        "..BB........GG..",
        "..BB........GG..",
        "..BB........GG..",
        "..BB........GG..",
        ".BBB........GGG.",
        ".BBB........GGG.",
        "................",
        "................",
    ],
    "harness-codex": [
        "................",
        "..CCCCCCCCCCCC..",
        ".CCCCCCCCCCCCCc.",
        ".CCCCCCCCCCCCCc.",
        ".CCWCCCCCCCCCCc.",
        ".CCWWCCCCCCCCCc.",
        ".CCCWWCCCCCCCCc.",
        ".CCCCWWCCCCCCCc.",
        ".CCCCWWCCCCCCCc.",
        ".CCCWWCCCCCCCCc.",
        ".CCWWCCCCCCCCCc.",
        ".CCWCCCCWWWWWCc.",
        ".CCCCCCCCCCCCCc.",
        ".CCCCCCCCCCCCCc.",
        "..cccccccccccc..",
        "................",
    ],
    "harness-hermes": [
        "................",
        ".......vv.......",
        ".vv...vVVv...vv.",
        "..vvv..VV..vvv..",
        "...vvvvVVvvvv...",
        "......VVVV......",
        ".....V.VV.V.....",
        "....V..VV..V....",
        ".....V.VV.V.....",
        "......VVVV......",
        ".....V.VV.V.....",
        "....V..VV..V....",
        ".....V.VV.V.....",
        "......VVVV......",
        ".......VV.......",
        "................",
    ],
    "harness-pi": [
        "................",
        "..PPPPPPPPPPPP..",
        ".PPPPPPPPPPPPPp.",
        ".PPPPPPPPPPPPPp.",
        ".PPWWWWWWWWWWPp.",
        ".PPWWWWWWWWWWPp.",
        ".PPPPWWPPWWPPPp.",
        ".PPPPWWPPWWPPPp.",
        ".PPPPWWPPWWPPPp.",
        ".PPPPWWPPWWPPPp.",
        ".PPPWWPPPWWPPPp.",
        ".PPPWWPPPPWWWPp.",
        ".PPPPPPPPPPPPPp.",
        ".PPPPPPPPPPPPPp.",
        "..pppppppppppp..",
        "................",
    ],
    "harness-cursor": [
        ".......TT.......",
        ".....TTTTTT.....",
        "...TTTTTTTTTT...",
        ".TTTTTTTTTTTTTT.",
        ".LLTTTTTTTTTTDD.",
        ".LLLLTTTTTTDDDD.",
        ".LLLLLLTTDDDDDD.",
        ".LLLLLLLDDDDDDD.",
        ".LLLLLLLDDDDDDD.",
        ".LLLLLLLDDDDDDD.",
        ".LLLLLLLDDDDDDD.",
        ".LLLLLLLDDDDDDD.",
        "...LLLLLDDDDD...",
        ".....LLLDDD.....",
        ".......LD.......",
        "................",
    ],
    "notify-on": [
        "................",
        "................",
        "...........A....",
        ".........IIA....",
        ".......IIIIA....",
        "...HHIIIIIIA....",
        "...HHIIIIIIA....",
        "...HHIIIIIIA....",
        "...HHSSSSSSA....",
        "...HHSSSSSSA....",
        ".......SSSSA....",
        "......H..SSA....",
        "......H....A....",
        "......H.........",
        "................",
        "................",
    ],
    "day": [
        "................",
        ".......UU.......",
        "..U....UU....U..",
        "...U........U...",
        "......UUUU......",
        ".....UUUUUU.....",
        "....UUUUUUUu....",
        ".UU.UUUUUUUu.UU.",
        ".UU.UUUUUUUu.UU.",
        "....UUUUUUuu....",
        ".....UUuuuu.....",
        "......uuuu......",
        "...U........U...",
        "..U....UU....U..",
        ".......UU.......",
        "................",
    ],
    "night": [
        "................",
        ".........MMMM...",
        ".......MMMM.....",
        "......MMMm....M.",
        ".....MMMm.......",
        ".....MMm........",
        "....MMMm........",
        "....MMMm........",
        "....MMMm........",
        "....MMMm........",
        ".....MMm........",
        ".....MMMm.....M.",
        "......MMMm......",
        ".......MMMMm....",
        ".........MMMM...",
        "................",
    ],
}


def struck(grid: list[str]) -> list[str]:
    """The grid struck through from its top left to its bottom right, two pixels wide."""
    rows = [list(r) for r in grid]
    for i in range(1, 15):
        for x in (i, i + 1):
            if x < 16:
                rows[i][x] = "X"
    return ["".join(r) for r in rows]


GRIDS["notify-off"] = struck(GRIDS["notify-on"])


def outlined(grid: list[str]) -> list[str]:
    """Every empty pixel beside a drawn one (up, down, left, right) becomes the outline."""
    h, w = len(grid), len(grid[0])
    drawn = lambda x, y: 0 <= x < w and 0 <= y < h and grid[y][x] != "."
    return ["".join("K" if c == "." and any(drawn(x + dx, y + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
                    else c for x, c in enumerate(row)) for y, row in enumerate(grid)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", help="also write them side by side at 8×, for a look")
    args = ap.parse_args()
    out = ROOT / "design-system" / "sprites" / "icons"
    for name, grid in GRIDS.items():
        assert len(grid) == 16 and all(len(r) == 16 for r in grid), name
        g = outlined(grid)
        grid_image(g, COLOURS, 1).save(out / f"{name}.png")
        grid_image(g, COLOURS, 2).save(out / f"{name}@2x.png")
    if args.preview:
        sheet = Image.new("RGBA", (len(GRIDS) * 144, 144), (42, 36, 25, 255))
        for i, grid in enumerate(GRIDS.values()):
            sheet.alpha_composite(grid_image(outlined(grid), COLOURS, 8), (i * 144 + 8, 8))
        sheet.save(args.preview)
    print(f"wrote {', '.join(GRIDS)} to {out}")


if __name__ == "__main__":
    main()
