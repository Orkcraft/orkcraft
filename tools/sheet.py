"""Cut a generated sheet of flat pixel buildings into header sprites, snapped to their pixel grid.

    python tools/sheet.py SHEET TYPE [TYPE ...] [--cell PX] [--scale N] [--preview PNG]

A sheet is what an image model made from the building prompt (docs/design/building-sprites.md): the
buildings in rows on a plain dark ground, drawn in "pixels" of about `--cell` screen pixels that are
never quite even. Each building is found by the empty columns around it, read cell by cell (the
colour most of a cell's inner pixels are near, out of the five of the ork mark's palette), and written
as `design-system/sprites/buildings/<TYPE>/header.png` at `--scale` and `header@2x.png` at twice that.
The ground around a building becomes transparent; the dark of a door or a window it encloses stays.
TYPEs are given in the sheet's reading order, left to right, top to bottom.

Needs `pip install pillow`.
"""
from __future__ import annotations

import argparse
import pathlib
from collections import Counter

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "design-system" / "sprites" / "buildings"

# The ork mark's palette (tools/logo.py, Office's `success`, `ink`, `ink-gold`, `canvas`).
PALETTE = {"G": (134, 192, 98), "g": (98, 138, 76), "T": (236, 228, 207), "Y": (232, 185, 74),
           "y": (196, 140, 60), "d": (26, 24, 19)}


def nearest(p: tuple[int, int, int]) -> str:
    return min(PALETTE, key=lambda k: sum((a - b) ** 2 for a, b in zip(p, PALETTE[k])))


def boxes(im: Image.Image, ground: tuple[int, int, int], gap: float = 0) -> list[tuple[int, int, int, int]]:
    """Each building's box: rows of buildings split by empty bands, buildings by empty columns. Parts
    closer than `gap` pixels (the stones of a ring, the posts of a fence) make one building."""
    w, h = im.size
    px = im.load()
    empty = lambda p: sum(abs(a - b) for a, b in zip(p, ground)) < 70
    rows_full = [any(not empty(px[x, y]) for x in range(0, w, 3)) for y in range(h)]
    bands, y = [], 0
    while y < h:
        if rows_full[y]:
            top = y
            while y < h and rows_full[y]:
                y += 1
            bands.append((top, y))
        y += 1
    out = []
    for y0, y1 in bands:
        cols = [any(not empty(px[x, yy]) for yy in range(y0, y1, 3)) for x in range(w)]
        x = 0
        while x < w:
            if cols[x]:
                left = x
                while x < w and cols[x]:
                    x += 1
                ys = [yy for yy in range(y0, y1) if any(not empty(px[xx, yy]) for xx in range(left, x, 3))]
                part = (left, ys[0], x, ys[-1] + 1)
                if out and out[-1][1] < y1 and part[0] - out[-1][2] < gap and out[-1][3] > y0:
                    last = out.pop()
                    part = (last[0], min(last[1], part[1]), part[2], max(last[3], part[3]))
                out.append(part)
            x += 1
    return out


def grid(im: Image.Image, box: tuple[int, int, int, int], cell: float) -> list[list[str]]:
    x0, y0, x1, y1 = box
    cols, rows = max(1, round((x1 - x0) / cell)), max(1, round((y1 - y0) / cell))
    cw, ch = (x1 - x0) / cols, (y1 - y0) / rows
    px = im.load()
    out = []
    for r in range(rows):
        line = []
        for c in range(cols):
            votes = Counter(nearest(px[int(x0 + (c + fx / 10) * cw), int(y0 + (r + fy / 10) * ch)])
                            for fx in range(3, 8) for fy in range(3, 8))
            line.append(votes.most_common(1)[0][0])
        out.append(line)
    return out


def clear_ground(g: list[list[str]]) -> None:
    """The dark that reaches the edge is ground: it turns transparent ('.'); enclosed dark stays."""
    rows, cols = len(g), len(g[0])
    todo = [(r, c) for r in range(rows) for c in (0, cols - 1)] + [(r, c) for c in range(cols) for r in (0, rows - 1)]
    while todo:
        r, c = todo.pop()
        if 0 <= r < rows and 0 <= c < cols and g[r][c] == "d":
            g[r][c] = "."
            todo += [(r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)]


def image(g: list[list[str]], k: int) -> Image.Image:
    img = Image.new("RGBA", (len(g[0]) * k, len(g) * k), (0, 0, 0, 0))
    for r, line in enumerate(g):
        for c, ch in enumerate(line):
            if ch != ".":
                img.paste(PALETTE[ch] + (255,), (c * k, r * k, (c + 1) * k, (r + 1) * k))
    return img


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("sheet", type=pathlib.Path)
    ap.add_argument("types", nargs="+")
    ap.add_argument("--cell", type=float, default=16.6, help="the sheet's pixel, in screen pixels")
    ap.add_argument("--scale", type=int, default=3, help="screen pixels per grid pixel in header.png")
    ap.add_argument("--out", type=pathlib.Path, default=OUT)
    ap.add_argument("--preview", type=pathlib.Path, help="also write every sprite side by side here")
    a = ap.parse_args()
    im = Image.open(a.sheet).convert("RGB")
    found = boxes(im, im.getpixel((4, 4)), gap=3 * a.cell)
    if len(found) != len(a.types):
        raise SystemExit(f"{len(found)} buildings on the sheet, {len(a.types)} types given")
    shown = []
    for kind, box in zip(a.types, found):
        g = grid(im, box, a.cell)
        clear_ground(g)
        folder = a.out / kind
        folder.mkdir(parents=True, exist_ok=True)
        image(g, a.scale).save(folder / "header.png")
        image(g, a.scale * 2).save(folder / "header@2x.png")
        shown.append(image(g, a.scale * 2))
        print(f"{kind}: {len(g[0])}×{len(g)} → {len(g[0]) * a.scale}×{len(g) * a.scale}")
    if a.preview:
        sheet = Image.new("RGBA", (sum(s.width + 24 for s in shown) + 24, max(s.height for s in shown) + 48),
                          (26, 24, 19, 255))
        x = 24
        for s in shown:
            sheet.alpha_composite(s, (x, sheet.height - 24 - s.height))
            x += s.width + 24
        sheet.save(a.preview)


if __name__ == "__main__":
    main()
