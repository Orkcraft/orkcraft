"""What a building is for, as a small pixel icon: the Build tray's tiles (docs/design/warchief-line-and-cards.md §2).

    python tools/intent_sprites.py [--preview FILE]

A tile in the tray says what you want done — take in what comes, work in parallel, talk a hard topic over — not
which house does it: the
house comes when it is built. Drawn on the AI tools' marks' way (tools/icon_sprites.py): one letter a pixel on a
14×14 grid set in 16×16, every empty pixel beside a drawn one becomes the dark outline. Simple signs in plain
colours, no one's logo. At 1× (16×16) and 2× (`@2x`), into `design-system/sprites/intents/`, one `<intent>.png`
each; which building each raises is `js/build.js` `INTENTS`.
"""
from __future__ import annotations

import argparse
import pathlib

from PIL import Image

from icon_sprites import outlined
from logo import grid_image

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "design-system" / "sprites" / "intents"

COLOURS = {
    "K": "#1a1813", "W": "#efe6cc", "s": "#8a8270", "S": "#9aa0a6", "R": "#d0453a", "B": "#3f7fbf", "b": "#2a5a8c",
    "Q": "#7fd4e8", "G": "#6ca420", "g": "#3f6b14", "Y": "#f2c66d", "y": "#b8862f", "L": "#8b5a2b", "T": "#d8c79a",
    "P": "#8e5bd0", "O": "#e8803a",
}

GRIDS = {
    "incoming": [             # a letter with a new one's badge: whatever it listens to — mail, chats, tickets
        ".........RRR..",
        "........RRRRR.",
        "WWWWWWWWRRWRR.",
        "WRWWWWWWRRWRR.",
        "WWRWWWWWRRRRR.",
        "WWWRWWWWRRWRR.",
        "WWWWRWWWWRRRW.",
        "WWWWWRRRRRWWW.",
        "WWWWWWWWWWWWW.",
        "WWWWWWWWWWWWW.",
        "WWWWWWWWWWWWW.",
    ],
    "discuss": [              # two voices: a hard topic talked over from every side
        "BBBBBBBBB.....",
        "BWWWWWWWB.....",
        "BWsssssWB.....",
        "BWWWWWWWB.....",
        "BBBBBBBBB.....",
        ".BB...........",
        "....YYYYYYYYYY",
        "....YWWWWWWWWY",
        "....YWssssssWY",
        "....YWWWWWWWWY",
        "....YYYYYYYYYY",
        "...........YY.",
    ],
    "drop": [                 # an arrow down into a tray
        "......GG......",
        "......GG......",
        "......GG......",
        "...GGGGGGGG...",
        "....GGGGGG....",
        ".....GGGG.....",
        "......GG......",
        "..............",
        ".LL........LL.",
        ".LL........LL.",
        ".LLLLLLLLLLLL.",
    ],
    "tasks": [                # a checklist, two done
        "GG.WWWWWWWWW..",
        "GG.WWWWWWWWW..",
        "..............",
        "GG.WWWWWWW....",
        "GG.WWWWWWW....",
        "..............",
        "SS.WWWWWWWWWW.",
        "SS.WWWWWWWWWW.",
    ],
    "calendar": [             # a month, today in red
        "...S.....S....",
        "RRRSRRRRRSRRRR",
        "RRRRRRRRRRRRRR",
        "WWWWWWWWWWWWWW",
        "WsWWsWWsWWsWWW",
        "WWWWWWWWWWWWWW",
        "WsWWsWWRRWsWWW",
        "WWWWWWWRRWWWWW",
        "WsWWsWWWWWsWWW",
        "WWWWWWWWWWWWWW",
    ],
    "agents": [               # crossed swords: orks put to work
        "SS..........SS",
        "SSS........SSS",
        ".SSS......SSS.",
        "..SSS....SSS..",
        "...SSS..SSS...",
        "....SSSSSS....",
        ".....SSSS.....",
        "....SSSSSS....",
        "..YLLS..SLLY..",
        "..YLL....LLY..",
        ".LL........LL.",
    ],
    "wiki": [                 # a book, its spine gold
        "..LLLLLLLLLL..",
        "..LYLLLLLLLL..",
        "..LYLLWWWWLL..",
        "..LYLLLLLLLL..",
        "..LYLLWWWLLL..",
        "..LYLLLLLLLL..",
        "..LYLLLLLLLL..",
        "..LYLLLLLLLL..",
        "..LYWWWWWWWW..",
        "..LLLLLLLLLL..",
    ],
    "research": [             # a magnifying glass
        "...SSSS.......",
        "..SQQQQS......",
        ".SQWQQQQS.....",
        ".SQQQQQQS.....",
        ".SQQQQQQS.....",
        "..SQQQQS......",
        "...SSSSLL.....",
        ".......LLL....",
        "........LLL...",
        ".........LLL..",
        "..........LL..",
    ],
    "listen": [               # headphones
        "....SSSSSS....",
        "..SS......SS..",
        ".S..........S.",
        "S............S",
        "S............S",
        "RRR........RRR",
        "RRR........RRR",
        "RRR........RRR",
        "RRR........RRR",
    ],
    "code": [                 # a branch off the main line
        ".GG...........",
        ".GG.......OO..",
        ".SS.......OO..",
        ".SS.......SS..",
        ".SS......SS...",
        ".SS.....SS....",
        ".SS...SSS.....",
        ".SSSSSS.......",
        ".SS...........",
        ".GG...........",
        ".GG...........",
    ],
    "check": [                # a shield and its tick: what passes, what is held
        ".YYYYYYYYYYYY.",
        ".YGGGGGGGGGGY.",
        ".YGGGGGGGGWGY.",
        ".YGGGGGGGWWGY.",
        ".YGWGGGGWWGGY.",
        ".YGWWGGWWGGGY.",
        "..YGWWWWGGGY..",
        "...YGWWGGGY...",
        "....YGGGGY....",
        ".....YGGY.....",
        "......YY......",
    ],
    "test": [                 # a flask, a potion bubbling in it: the Test bench
        ".....YYYY.....",
        "......SS......",
        "......WS......",
        "......WS......",
        ".....WWSS.....",
        "....WWWSSS....",
        "...WWWWSSSS...",
        "...GGQGGGGG...",
        "..GGGGGQGGGG..",
        "..GQGGGGGGGG..",
        "..GGGGGGGQGG..",
        "...GGGGGGGG...",
    ],
    "send": [                 # a paper plane
        "............WW",
        "..........WWW.",
        "........WWWsW.",
        "......WWWWsWW.",
        "....WWWWWsWWW.",
        "..WWWWWWsWWWW.",
        "WWWWWWWsWWWWW.",
        "......ssWWWW..",
        "......sWWWW...",
        "......WWWW....",
        "......WW......",
    ],
    "route": [                # one road forking in two
        "..........YYYY",
        "...........YYY",
        "..........YYYY",
        ".........YY..Y",
        "........YY....",
        "YYYYYYYYY.....",
        "YYYYYYYYY.....",
        "........YY....",
        ".........YY..Y",
        "..........YYYY",
        "...........YYY",
        "..........YYYY",
    ],
    "transform": [            # a funnel: in one shape, out another
        "BBBBBBBBBBBBBB",
        ".BBBBBBBBBBBB.",
        "..BBBBBBBBBB..",
        "...BBBBBBBB...",
        "....BBBBBB....",
        ".....BBBB.....",
        ".....BBBB.....",
        ".....BBBB.....",
        "..............",
        "......GG......",
        "......GG......",
    ],
    "chart": [                # bars
        "..........GG..",
        "..........GG..",
        "......YY..GG..",
        "......YY..GG..",
        "..BB..YY..GG..",
        "..BB..YY..GG..",
        "..BB..YY..GG..",
        "SSSSSSSSSSSSSS",
    ],
    "sound": [                # a bell
        "......YY......",
        "....YYYYYY....",
        "...YYYYYYYY...",
        "...YYYYYYYY...",
        "...YYYYYYYY...",
        "..YYYYYYYYYY..",
        ".YYYYYYYYYYYY.",
        "..............",
        "......yy......",
    ],
}


def framed(grid: list[str]) -> list[str]:
    """The 14-wide drawing set in the middle of 16×16, room for its outline all round."""
    assert all(len(r) == 14 for r in grid) and len(grid) <= 14
    top = (14 - len(grid)) // 2 + 1
    rows = ["." * 16] * top + ["." + r + "." for r in grid]
    return rows + ["." * 16] * (16 - len(rows))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--preview", help="also write them side by side at 8×, for a look")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    for name, grid in GRIDS.items():
        g = outlined(framed(grid))
        grid_image(g, COLOURS, 1).save(OUT / f"{name}.png")
        grid_image(g, COLOURS, 2).save(OUT / f"{name}@2x.png")
    if args.preview:
        cols = 10
        rows = (len(GRIDS) + cols - 1) // cols
        sheet = Image.new("RGBA", (cols * 144, rows * 144), (42, 36, 25, 255))
        for i, grid in enumerate(GRIDS.values()):
            sheet.alpha_composite(grid_image(outlined(framed(grid)), COLOURS, 8), ((i % cols) * 144 + 8, (i // cols) * 144 + 8))
        sheet.save(args.preview)
    print(f"wrote {len(GRIDS)} to {OUT}")


if __name__ == "__main__":
    main()
