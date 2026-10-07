"""The sprites of growth and of the biomes, drawn from code so they never drift (docs/design/growth.md,
docs/design/war-map.md):

    python tools/growth_sprites.py

- `design-system/sprites/mascots/<kin>-<stage>.png` (and `@2x`): the operator's mascot, a head on the
  ork mark's grid per kin, its four stages drawn by adding to it (a band, horns, then gold eyes and a
  gem), never a crown: the crown is the Warchief's.
- `design-system/sprites/flags/`: a building's renown and goal, drawn at the header sprites' scale (2 px
  a pixel). `level-<n>.png`, the flag on its roof at I–III (ivory, taller at II, gold at III; the pole's
  foot at the bottom left, `js/icons.js` `FLAG_AT` says where on each roof it stands); `footing-<n>.png`,
  a tile of the stones under it, a course more at each level; `annex-thrift.png` (a lean-to over a stack
  of logs) and `annex-quality.png` (a crystal on a whetstone), beside it by its goal. Balance has none.
- `design-system/sprites/buildings/<type>/header-<biome>.png` (and `@2x`): each flat header redrawn
  for ice (snow on the edges facing the sky), dust (dry olive, sand at the foot), void (ashen violet)
  and lava (basalt, embers at the foot). Dirt and forest keep `header.png`.

Needs Pillow.
"""
from __future__ import annotations

import pathlib

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
SPRITES = ROOT / "design-system" / "sprites"

# -- the palette: the ork mark's flat colours (building-sprites.md) and the kins' skins --------------------
GREEN, DARK_GREEN, IVORY, GOLD, NIGHT = "#86c062", "#628a4c", "#ece4cf", "#e8b94a", "#1a1813"


def rgb(hex_: str) -> tuple[int, int, int, int]:
    return tuple(int(hex_[i:i + 2], 16) for i in (1, 3, 5)) + (255,)


def grid_image(grid: list[str], colours: dict[str, str], k: int) -> Image.Image:
    img = Image.new("RGBA", (len(grid[0]) * k, len(grid) * k), (0, 0, 0, 0))
    for y, row in enumerate(grid):
        for x, c in enumerate(row):
            if c not in ". ":
                img.paste(rgb(colours[c]), (x * k, y * k, (x + 1) * k, (y + 1) * k))
    return img


def save_pair(img1x: Image.Image, path: pathlib.Path) -> None:
    """`img1x` at the sprite's own scale, and its @2x by nearest neighbour."""
    path.parent.mkdir(parents=True, exist_ok=True)
    img1x.save(path)
    img1x.resize((img1x.width * 2, img1x.height * 2), Image.NEAREST).save(path.with_name(path.stem + "@2x.png"))


# -- the mascots ---------------------------------------------------------------------------------------
# F face, D eyes and mouth, T tusks, teeth or beard, N nose, M metal. 12 × 8, as the ork mark.
HEADS = {
    "orc": ["...FFFFFF...",
            "F.FFFFFFFF.F",
            "FFFFFFFFFFFF",
            ".FFDDFFDDFF.",
            "..FFFFFFFF..",
            "..FTFFFFTF..",
            "..FTFFFFTF..",
            "...FFFFFF..."],
    "elf": ["...FFFFFF...",
            "..FFFFFFFF..",
            "FFFFFFFFFFFF",
            ".FFDDFFDDFF.",
            "..FFFFFFFF..",
            "..FFFFFFFF..",
            "...FFDDFF...",
            "....FFFF...."],
    "lich": ["...FFFFFF...",
             "..FFFFFFFF..",
             ".FFFFFFFFFF.",
             ".FDDDFFDDDF.",
             ".FFFFFFFFFF.",
             "..FFFDDFFF..",
             "..FTFTFTFF..",
             "...FFFFFF..."],
    "skeleton": ["...FFFFFF...",
                 "..FFFFFFFF..",
                 ".FFFFFFFFFF.",
                 ".FDDFFFFDDF.",
                 ".FDDFFFFDDF.",
                 "..FFFDDFFF..",
                 "...FDFDFD...",
                 "...FFFFFF..."],
    "gnome": ["..FFFFFFFF..",
              ".FFFFFFFFFF.",
              ".FFDDFFDDFF.",
              ".FFFFNNFFFF.",
              ".TFFFNNFFFT.",
              ".TTTFFFFTTT.",
              "..TTTTTTTT..",
              "...TTTTTT..."],
    "goblin": ["...FFFFFF...",
               "FF.FFFFFF.FF",
               ".FFFFFFFFFF.",
               "..FDDFFDDF..",
               "..FFFFFFFF..",
               "..FDTDTDTF..",
               "...FFFFFF...",
               "............"],
    "knight": ["...MMMMMM...",
               "..MMMMMMMM..",
               ".MMMMMMMMMM.",
               ".MMDDDDDDMM.",
               ".MMMMMMMMMM.",
               ".MMDMDMDMMM.",
               "..MMMMMMMM..",
               "...MMMMMM..."],
}
SKINS = {"orc": GREEN, "elf": "#c9d6a3", "lich": "#8e88a8", "skeleton": IVORY, "gnome": "#e3b58c",
         "goblin": "#a8c040", "knight": "#9aa0a8"}
KINS = tuple(HEADS)
# Three rows over the head: what each stage adds (W a band of dark green, T ivory horns, G gold).
STAGE_MARKS = {
    1: ["............", "............", "............"],
    2: ["............", "............", "..WWWWWWWW.."],
    3: ["............", "T..........T", ".TWWWWWWWWT."],
    4: ["T..........T", "TT...GG...TT", ".TWWWGGWWWT."],
}
STAGES = (1, 2, 3, 4)


def mascot_grid(kin: str, stage: int) -> list[str]:
    head = [row for row in HEADS[kin]]
    if stage >= 4:                                   # the top stage: the eyes glow gold
        head = [row.replace("D", "G") if i in (3, 4) else row for i, row in enumerate(head)]
    return STAGE_MARKS[stage] + head


def mascots() -> None:
    for kin in KINS:
        colours = {"F": SKINS[kin], "D": NIGHT, "T": IVORY, "N": "#c99a74", "M": SKINS[kin], "W": DARK_GREEN,
                   "G": GOLD}
        for stage in STAGES:
            save_pair(grid_image(mascot_grid(kin, stage), colours, 2), SPRITES / "mascots" / f"{kin}-{stage}.png")


# -- a building's renown and goal (docs/design/growth.md §5) ---------------------------------------------
# The renown is told twice, by a flag on the roof and by the stones under the hut; the goal by an annex
# beside it. ⚖️ balance, the default, has none, so a goal chosen stands out.
#
# The flag: | the pole (dark green), X the cloth. The pole's foot is the bottom left pixel. None at level 0;
# ivory at I, the pole taller at II, the cloth gold at III.
FLAG = ["|XXX", "|XXX"]
POLE = {1: 1, 2: 3, 3: 3}                         # the bare pole under the cloth, by level
CLOTH = {1: IVORY, 2: IVORY, 3: GOLD}
FLAGS = {level: FLAG + ["|"] * POLE[level] for level in POLE}

# The stones: a tile the width of four pixels, repeated under the whole hut (`js/icons.js` `HutSprite`),
# a course of stones (S) and mortar (m) for each level, the top edge in ivory (c) from II.
STONE, MORTAR = "#8f8166", "#4a4235"
FOOTINGS = {1: ["SSSm", "mmmm"],
            2: ["cccc", "SSSm", "SmSS", "mmmm"],
            3: ["cccc", "SSSm", "SmSS", "SSSm", "SmSS", "mmmm"]}

# The annex, standing on the ground at the hut's right: G green, W dark green, I ivory, D the dark.
ANNEXES = {
    "thrift": ["......WW........",          # a lean-to over a stack of logs: kept, counted, reused
               "....WWGGGG......",
               "..WWGGGGGGGG....",
               "WWGGGGGGGGGGGGW.",
               "GGGGGGGGGGGGGGGW",
               ".W............W.",
               ".W.II.II.II...W.",
               ".W.ID.ID.ID...W.",
               ".W..II.II.II..W.",
               ".W..ID.ID.ID..W.",
               ".W.II.II.II.II.W",
               ".W.ID.ID.ID.ID.W",
               "WWWWWWWWWWWWWWWW"],
    "quality": [".....I......",               # a crystal on a whetstone: cut, polished, checked
                "....III.....",
                "...IIWII....",
                "..IIIWIII...",
                "..IIWIIII...",
                ".IIIWIIIII..",
                ".IIWIIIIWI..",
                ".IIWIIIWII..",
                "..IIIIWII...",
                "..IIIWIII...",
                "...IIWII....",
                "....III.....",
                "..WWWWWWW...",
                ".WGGGGGGGW..",
                "WWWWWWWWWWW."],
}


def renown_and_goals() -> None:
    folder = SPRITES / "flags"
    for old in folder.glob("*.png"):          # the old goal flags, <goal>-<level>.png
        old.unlink()
    for level, rows in FLAGS.items():
        w = max(len(r) for r in rows)
        grid = [r.ljust(w).replace(" ", ".") for r in rows]
        save_pair(grid_image(grid, {"|": DARK_GREEN, "X": CLOTH[level]}, 2), folder / f"level-{level}.png")
        save_pair(grid_image(FOOTINGS[level], {"S": STONE, "m": MORTAR, "c": IVORY}, 2),
                  folder / f"footing-{level}.png")
    for goal, grid in ANNEXES.items():
        save_pair(grid_image(grid, {"G": GREEN, "W": DARK_GREEN, "I": IVORY, "D": NIGHT}, 2),
                  folder / f"annex-{goal}.png")


# -- the huts of each biome -------------------------------------------------------------------------------

def _near(c: tuple, ref: str) -> bool:
    r = rgb(ref)
    return sum(abs(a - b) for a, b in zip(c[:3], r[:3])) < 40


def biome_sprite(native: Image.Image, biome: str) -> Image.Image:
    """A flat header at its own pixel (1 px a pixel) for `biome`: only colours swapped and pixels added."""
    im = native.copy()
    px, (w, h) = im.load(), im.size
    if biome == "ice":                         # snow on the edges that face the sky, two pixels deep
        for x in range(w):
            for y in range(h):
                if not px[x, y][3]:
                    continue
                if _near(px[x, y], GREEN) or _near(px[x, y], DARK_GREEN):
                    px[x, y] = rgb(IVORY)
                    if y + 1 < h and _near(px[x, y + 1], GREEN):
                        px[x, y + 1] = rgb(IVORY)
                break
    swaps = {"dust": ("#a8a05c", "#7a7040"), "void": ("#8e88a8", "#5e587a"), "lava": ("#5e5652", "#3c3634")}
    if biome in swaps:
        light, dark = swaps[biome]
        for x in range(w):
            for y in range(h):
                c = px[x, y]
                if c[3] and _near(c, GREEN):
                    px[x, y] = rgb(light)
                elif c[3] and _near(c, DARK_GREEN):
                    px[x, y] = rgb(dark)
        foot = {"dust": ("#c9a46a", 5, 3), "lava": ("#8a2a10", 6, 2)}.get(biome)
        if foot:
            colour, every, of = foot
            for x in range(w):
                if px[x, h - 1][3] and x % every < of:
                    px[x, h - 1] = rgb(colour)
    return im


BIOME_VARIANTS = ("ice", "dust", "void", "lava")


def biome_huts() -> None:
    for folder in sorted((SPRITES / "buildings").iterdir()):
        header = folder / "header.png"
        if not header.is_file():
            continue
        img = Image.open(header).convert("RGBA")
        native = img.resize((img.width // 2, img.height // 2), Image.NEAREST)
        for biome in BIOME_VARIANTS:
            out = biome_sprite(native, biome)
            save_pair(out.resize((out.width * 2, out.height * 2), Image.NEAREST), folder / f"header-{biome}.png")


def main() -> None:
    mascots()
    renown_and_goals()
    biome_huts()
    print("wrote the mascots, the flags, footings and annexes, and the huts of each biome")


if __name__ == "__main__":
    main()
