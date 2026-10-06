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

The same head is the agent everywhere in the GUI: `design-system/sprites/orks/` gets `ork.png` and its
states (`ork-idle` asleep, `ork-busy` sweating, `ork-waiting` with a flame on its crown), each on the
head's own 12×8 grid, drawn at 2× (24×16) and 4× (`@2x`), and `ork-portrait`,
the head at 3× in the 46×38 portrait slot.

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

# The agent's states, drawn inside the head's own 12×8 grid so the sprite fits a badge's plate:
# d shut eyes and z a sleep mark over the right ear, S a drop of sweat past it, O and Y a flame
# (alert orange, gold core) on the crown.
STATES = {
    "ork": {},
    "ork-idle": {(10, 0): "z"},
    "ork-busy": {(10, 0): "S", (10, 1): "S"},
    "ork-waiting": {(4, 0): "O", (5, 0): "Y", (6, 0): "Y", (7, 0): "O"},
}
SPRITE_COLOURS = {"F": "#6ca420", "D": "#1a2816", "T": "#e8e0c8", "d": "#3f6b14",
                  "z": "#e8e0c8", "S": "#9fd3ff", "O": "#ff8c1a", "Y": "#f2c66d"}


def state_grid(name: str) -> list[str]:
    head = [list(row.replace("D", "d") if name == "ork-idle" else row) for row in GRID]
    for (x, y), c in STATES[name].items():
        head[y][x] = c
    return ["".join(row) for row in head]


def grid_image(grid: list[str], colours: dict[str, str], k: int) -> Image.Image:
    img = Image.new("RGBA", (len(grid[0]) * k, len(grid) * k), (0, 0, 0, 0))
    for y, row in enumerate(grid):
        for x, c in enumerate(row):
            if c != ".":
                rgb = tuple(int(colours[c][i:i + 2], 16) for i in (1, 3, 5))
                img.paste(rgb + (255,), (x * k, y * k, (x + 1) * k, (y + 1) * k))
    return img


def sprites(out: pathlib.Path) -> None:
    """The agent's head and its states for the GUI (design-system/sprites/orks/)."""
    out.mkdir(parents=True, exist_ok=True)
    for name in STATES:
        grid = state_grid(name)
        grid_image(grid, SPRITE_COLOURS, 2).save(out / f"{name}.png")
        grid_image(grid, SPRITE_COLOURS, 4).save(out / f"{name}@2x.png")
    for scale, suffix, (w, h) in ((3, "", (46, 38)), (6, "@2x", (92, 76))):
        head = grid_image(GRID, SPRITE_COLOURS, scale)
        slot = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        slot.alpha_composite(head, ((w - head.width) // 2, h - head.height - scale))
        slot.save(out / f"ork-portrait{suffix}.png")
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
