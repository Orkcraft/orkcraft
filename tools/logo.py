"""The ork mark and the Orkcraft logo, drawn from one pixel grid: SVGs, favicons and a preview.

    python tools/logo.py [--out DIR]

The mark is a 12×8 ork head on a plain grid: green face, pointed ears, a dark brow band for the eyes
and two tusks. No outline, no shading, three colours, so it reads at 16 px and stays sober enough for
the Office. Every file is built from `GRID` below; change the grid, run this again, and they all follow.

Out come, in `design-system/logo/` by default (the GUI serves it at `/ds/logo/`):

- `ork-mark.svg`, `ork-mark-camp.svg`, `ork-mark-light.svg`: the mark in the Office, Camp and
  light-ground colours;
- `ork-mark-mono.svg`: one colour (`currentColor`), eyes and tusks cut out;
- `orkcraft-dark.svg`, `orkcraft-light.svg`: the mark with the word, set in Titillium Web 700 from
  `design-system/fonts/` and turned into outlines so it needs no font;
- `favicon-16.png`, `favicon-32.png`, `favicon.ico`, `ork-mark-256.png`.

The same head is the agent everywhere in the GUI: `design-system/sprites/orks/` gets `ork.png` (the
head's 12×8 grid, drawn at 2× (24×16) and 4× (`@2x`)) and its states with their glyph beside the head
on a 20×8 grid (40×16): `ork-idle` eyes shut and Zz, `ork-busy` a gear, `ork-waiting` a flame on the
crown and `!`, `ork-frozen` a snowflake, `ork-draft` a page.

Needs `pip install fonttools brotli pillow` (brotli reads the woff2 font).
"""
from __future__ import annotations

import argparse
import pathlib

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
FONT = ROOT / "design-system" / "fonts" / "titillium-web-latin-700-normal.woff2"

# F face, D eyes (the brow band), T tusks, . nothing
GRID = [
    "...FFFFFF...",
    "F.FFFFFFFF.F",
    "FFFFFFFFFFFF",
    ".FFDDFFDDFF.",
    "..FFFFFFFF..",
    "..FTFFFFTF..",
    "..FTFFFFTF..",
    "...FFFFFF...",
]

# The colours come from design-system/tokens.json where one fits: Office `success` and `ink`,
# `canvas`, `ink-gold`; Camp's green is the ork sprite's own.
PALETTES = {
    "office": {"F": "#86c062", "D": "#1a1813", "T": "#ece4cf", "word": "#ece4cf"},
    "camp": {"F": "#6ca420", "D": "#1a2816", "T": "#e8e0c8", "word": "#e8e0c8"},
    "light": {"F": "#548c34", "D": "#181c28", "T": "#e8b94a", "word": "#181c28"},
}

W, H = len(GRID[0]), len(GRID)

# The agent's states: the head keeps its own 12×8 grid and the state stands beside it as a glyph on a
# 7×8 cell, one blank column apart, so the sprite is 20×8 (40×16 drawn) and the state reads at a glance.
# On the head: d shut eyes asleep, O and Y a flame (alert orange, gold core) on the crown while waiting.
# The glyphs: Zz asleep (idle), a gold gear at work (busy), an orange `!` waiting on a person (alert),
# a snowflake frozen, a page with lines a draft.
STATES = {
    "ork": {},
    "ork-idle": {},
    "ork-busy": {},
    "ork-waiting": {(4, 0): "O", (5, 0): "Y", (6, 0): "Y", (7, 0): "O"},
    "ork-frozen": {},
    "ork-draft": {},
}
GLYPHS = {
    "ork-idle": [
        "....zzz",
        ".....z.",
        "....z..",
        "....zzz",
        "ZZZZ...",
        "..Z....",
        ".Z.....",
        "ZZZZ...",
    ],
    "ork-busy": [
        "...G...",
        ".GGGGG.",
        ".GG.GG.",
        "GG...GG",
        ".GG.GG.",
        ".GGGGG.",
        "...G...",
        ".......",
    ],
    "ork-waiting": [
        "..OO...",
        "..OO...",
        "..OO...",
        "..OO...",
        "..OO...",
        ".......",
        "..OO...",
        "..OO...",
    ],
    "ork-frozen": [
        "...I...",
        ".I.I.I.",
        "..III..",
        "IIIIIII",
        "..III..",
        ".I.I.I.",
        "...I...",
        ".......",
    ],
    "ork-draft": [
        "PPPP...",
        "PLLPP..",
        "PPPPPP.",
        "PLLLLP.",
        "PPPPPP.",
        "PLLLLP.",
        "PPPPPP.",
        ".......",
    ],
}
SPRITE_COLOURS = {"F": "#6ca420", "D": "#1a2816", "T": "#e8e0c8", "d": "#3f6b14",
                  "z": "#9fd3ff", "Z": "#9fd3ff", "G": "#f2c66d", "O": "#ff8c1a", "Y": "#f2c66d",
                  "I": "#bfe6ff", "P": "#d8c79a", "L": "#8a7a58"}


def state_grid(name: str) -> list[str]:
    """The head in its state, with the state's glyph beside it when it has one."""
    head = [list(row.replace("D", "d") if name == "ork-idle" else row) for row in GRID]
    for (x, y), c in STATES[name].items():
        head[y][x] = c
    glyph = GLYPHS.get(name)
    return ["".join(row) + ("." + glyph[y] if glyph else "") for y, row in enumerate(head)]


def grid_image(grid: list[str], colours: dict[str, str], k: int) -> Image.Image:
    img = Image.new("RGBA", (len(grid[0]) * k, len(grid) * k), (0, 0, 0, 0))
    for y, row in enumerate(grid):
        for x, c in enumerate(row):
            if c != ".":
                rgb = tuple(int(colours[c][i:i + 2], 16) for i in (1, 3, 5))
                img.paste(rgb + (255,), (x * k, y * k, (x + 1) * k, (y + 1) * k))
    return img


def sprites(out: pathlib.Path) -> None:
    """The agent's head and its states for the GUI (design-system/sprites/orks/), and the Warchief's."""
    out.mkdir(parents=True, exist_ok=True)
    for name in STATES:
        grid = state_grid(name)
        grid_image(grid, SPRITE_COLOURS, 2).save(out / f"{name}.png")
        grid_image(grid, SPRITE_COLOURS, 4).save(out / f"{name}@2x.png")
    for name, grid in warchief_grids().items():
        grid_image(grid, SPRITE_COLOURS, 2).save(out / f"{name}.png")
        grid_image(grid, SPRITE_COLOURS, 4).save(out / f"{name}@2x.png")


# The Warchief: the ork's head under a gold crown (docs/design/growth.md §8), two rows over the 12×8 grid.
# The crown marks the role, it is never earned. Waiting, the crown's points burn instead of the ork's flame.
# A state's glyph stands beside the head as the ork's does, the crown's rows padded to its width.
CROWN = ["...Y.YY.Y...", "...YYYYYY..."]
CROWN_BURNING = ["...O.OO.O...", "...YYYYYY..."]


def crowned(crown: list[str], grid: list[str]) -> list[str]:
    return [row.ljust(len(grid[0]), ".") for row in crown] + grid


def warchief_grids() -> dict[str, list[str]]:
    waiting = [row[:W] + glyph for row, glyph in zip(state_grid("ork"), (r[W:] for r in state_grid("ork-waiting")))]
    return {"warchief": CROWN + state_grid("ork"),
            "warchief-idle": crowned(CROWN, state_grid("ork-idle")),
            "warchief-busy": crowned(CROWN, state_grid("ork-busy")),
            "warchief-waiting": crowned(CROWN_BURNING, waiting)}


CELL = 10  # SVG units per pixel of the grid


def runs(keys: str) -> list[tuple[int, int, int]]:
    """(x, y, length) of each horizontal run of cells whose letter is in `keys`."""
    out = []
    for y, row in enumerate(GRID):
        x = 0
        while x < W:
            if row[x] in keys:
                start = x
                while x < W and row[x] in keys:
                    x += 1
                out.append((start, y, x - start))
            else:
                x += 1
    return out


def path(keys: str, dx: float = 0, dy: float = 0) -> str:
    return "".join(f"M{dx + x * CELL:g} {dy + y * CELL:g}h{n * CELL}v{CELL}h{-n * CELL}z"
                   for x, y, n in runs(keys))


def mark_paths(colours: dict[str, str], dx: float = 0, dy: float = 0) -> str:
    return "".join(f'<path fill="{colours[k]}" d="{path(k, dx, dy)}"/>' for k in "FDT")


def svg(width: float, height: float, body: str, title: str) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:g} {height:g}" '
            f'width="{width:g}" height="{height:g}" shape-rendering="crispEdges" role="img">'
            f"<title>{title}</title>{body}</svg>\n")


def word_path(text: str, cap: float, x: float, baseline: float) -> tuple[str, float]:
    """The word as one SVG path whose capitals stand `cap` units tall; returns it and its width."""
    font = TTFont(FONT)
    glyphs, cmap = font.getGlyphSet(), font.getBestCmap()
    scale = cap / font["OS/2"].sCapHeight
    hmtx = font["hmtx"]
    pen = SVGPathPen(glyphs)
    advance = 0.0
    for ch in text:
        name = cmap[ord(ch)]
        glyphs[name].draw(TransformPen(pen, (scale, 0, 0, -scale, x + advance * scale, baseline)))
        advance += hmtx[name][0]
    return pen.getCommands(), advance * scale


def lockup(colours: dict[str, str]) -> str:
    """The mark and the word side by side: capitals five pixels tall, centred on the head."""
    cap = 5 * CELL
    baseline = (H * CELL + cap) / 2
    gap = 3 * CELL
    d, width = word_path("Orkcraft", cap, W * CELL + gap, baseline)
    total = W * CELL + gap + width
    body = mark_paths(colours) + f'<path fill="{colours["word"]}" d="{d}" shape-rendering="geometricPrecision"/>'
    return svg(round(total + 1), H * CELL, body, "Orkcraft")


def raster(colours: dict[str, str], size: int) -> Image.Image:
    """The mark centred on a transparent square of `size` px, each grid pixel a whole number of px."""
    k = max(1, size // W)
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ox, oy = (size - W * k) // 2, (size - H * k) // 2
    for y, row in enumerate(GRID):
        for x, c in enumerate(row):
            if c != ".":
                rgb = tuple(int(colours[c][i:i + 2], 16) for i in (1, 3, 5))
                img.paste(rgb + (255,), (ox + x * k, oy + y * k, ox + (x + 1) * k, oy + (y + 1) * k))
    return img


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=pathlib.Path, default=ROOT / "design-system" / "logo")
    out = ap.parse_args().out
    out.mkdir(parents=True, exist_ok=True)

    vw, vh = W * CELL, H * CELL
    (out / "ork-mark.svg").write_text(svg(vw, vh, mark_paths(PALETTES["office"]), "Orkcraft"))
    (out / "ork-mark-camp.svg").write_text(svg(vw, vh, mark_paths(PALETTES["camp"]), "Orkcraft"))
    (out / "ork-mark-light.svg").write_text(svg(vw, vh, mark_paths(PALETTES["light"]), "Orkcraft"))
    mono = f'<path fill="currentColor" d="{path("F")}"/>'
    (out / "ork-mark-mono.svg").write_text(svg(vw, vh, mono, "Orkcraft"))
    (out / "orkcraft-dark.svg").write_text(lockup(PALETTES["office"]))
    (out / "orkcraft-light.svg").write_text(lockup(PALETTES["light"]))

    office = PALETTES["office"]
    for size in (16, 32):
        raster(office, size).save(out / f"favicon-{size}.png")
    raster(office, 256).save(out / "ork-mark-256.png")
    # every size drawn on its own grid, never scaled down from the largest
    raster(office, 48).save(out / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)],
                            append_images=[raster(office, 16), raster(office, 32)])
    sprites(ROOT / "design-system" / "sprites" / "orks")
    print(f"wrote {out} and the ork sprites")


if __name__ == "__main__":
    main()
