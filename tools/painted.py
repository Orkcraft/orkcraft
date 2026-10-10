"""Cut a generated sheet of buildings into header sprites as it was painted: no grid, no palette.

    python tools/painted.py SHEET TYPE [TYPE ...] [--scale 0.3] [--split X ...]

`tools/sheet.py` reads a sheet as true pixel art (a grid, five colours). An image model's buildings are not: their
"pixels" are uneven and carry shading, and snapping them to a grid loses the axes, the palisade, a gear's teeth. Here
each building keeps its picture. The ground around it becomes transparent (flooded from the box's edge, so a door or
a window it encloses stays dark), its edge is feathered, and it is scaled down smoothly by `--scale` to
`design-system/sprites/buildings/<TYPE>/header.png` and by twice that to `header@2x.png` (the town shows the @2x on a
retina screen). One scale for the whole sheet keeps the buildings' sizes to each other as drawn.

The biome versions (`header-<biome>.png`) are written too, keeping the shading: each pixel moves by what its nearest
palette green moves in that biome, and on ice what faces the sky goes under snow (tools/growth_sprites.py swaps the palette's own colours, which a painted sprite
has few of; it leaves a painted header's biomes to this tool).

`--open` names the buildings drawn as open frames (a gantry, a tower on stilts): the ground seen through them goes
too. Buildings are found as in tools/sheet.py; two drawn so close they read as one are split at `--split` x positions.
TYPEs in the sheet's reading order. Needs `pip install pillow`.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import sheet  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "design-system" / "sprites" / "buildings"
GROUND_NEAR, GROUND_FAR = 40, 110          # distance from the ground's colour: under it ground, over it the building

# The palette's two greens and where each biome takes them (tools/growth_sprites.py `biome_sprite`).
GREEN, DARK = (134, 192, 98), (98, 138, 76)
BIOMES = {"dust": ((212, 183, 122), (156, 122, 70)), "void": ((142, 136, 168), (94, 88, 122)),
          "lava": ((164, 154, 150), (106, 96, 92)), "meadow": ((127, 191, 154), (79, 138, 108))}
IVORY = (236, 228, 207)
SNOW = 0.06                                # ice: snow on what faces the sky, this share of the sprite's height deep


def _dist(a, b) -> int:
    return sum(abs(x - y) for x, y in zip(a[:3], b[:3]))


def cut(im: Image.Image, box: tuple[int, int, int, int], ground: tuple, open_frame: bool = False) -> Image.Image:
    """The building in `box` with the ground around it transparent and its edge feathered; `open_frame`: the ground
    seen through it too (a gantry, a tower's legs), not only around it."""
    pad = 4
    x0, y0, x1, y1 = max(box[0] - pad, 0), max(box[1] - pad, 0), box[2] + pad + 1, box[3] + pad + 1
    part = im.crop((x0, y0, x1, y1)).convert("RGBA")
    px, (w, h) = part.load(), part.size
    outside = set()
    stack = [(x, y) for x in range(w) for y in (0, h - 1)] + [(x, y) for y in range(h) for x in (0, w - 1)]
    if open_frame:
        stack = [(x, y) for x in range(w) for y in range(h)]
    while stack:                                            # the ground reached from the edge, never through a wall
        x, y = stack.pop()
        if (x, y) in outside or not (0 <= x < w and 0 <= y < h) or _dist(px[x, y], ground) >= GROUND_FAR:
            continue
        outside.add((x, y))
        stack += [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
    for x, y in outside:
        d = _dist(px[x, y], ground)
        a = 0 if d < GROUND_NEAR else int(255 * (d - GROUND_NEAR) / (GROUND_FAR - GROUND_NEAR))
        px[x, y] = px[x, y][:3] + (a,)
    bbox = part.getchannel("A").point(lambda v: 255 if v > 24 else 0).getbbox()
    return part.crop(bbox)


def snow(img: Image.Image) -> Image.Image:
    """`img` on ice: the green that faces the sky under snow, as the flat sprites have it."""
    out = img.copy()
    px = out.load()
    deep = max(2, round(out.height * SNOW))
    for x in range(out.width):
        for y in range(out.height):
            if px[x, y][3] > 128:
                for k in range(y, min(y + deep, out.height)):
                    p = px[x, k]
                    if p[3] and min(_dist(p, GREEN), _dist(p, DARK)) <= 90:
                        px[x, k] = IVORY + (p[3],)
                break
    return out


def biome(img: Image.Image, which: str) -> Image.Image:
    """`img` in a biome: a green pixel moves as its green does there, the shading kept."""
    if which == "ice":
        return snow(img)
    light, dark = BIOMES[which]
    out = img.copy()
    px = out.load()
    for y in range(out.height):
        for x in range(out.width):
            p = px[x, y]
            if not p[3]:
                continue
            dl, dd = _dist(p, GREEN), _dist(p, DARK)
            if min(dl, dd) > 90:                            # ivory, gold, the dark of a door: as painted
                continue
            ref, to = (GREEN, light) if dl <= dd else (DARK, dark)
            px[x, y] = tuple(max(0, min(255, c + t - r)) for c, r, t in zip(p[:3], ref, to)) + (p[3],)
    return out


def save(img: Image.Image, folder: pathlib.Path, scale: float, stem: str = "header") -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for k, name in ((1, f"{stem}.png"), (2, f"{stem}@2x.png")):
        size = (max(1, round(img.width * scale * k)), max(1, round(img.height * scale * k)))
        img.resize(size, Image.LANCZOS).save(folder / name)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("sheet", type=pathlib.Path)
    ap.add_argument("types", nargs="+")
    ap.add_argument("--scale", type=float, default=0.3, help="the sprite's size against the sheet's")
    ap.add_argument("--split", type=int, nargs="*", default=[], help="x positions that part two buildings")
    ap.add_argument("--gap", type=float, default=22, help="parts closer than this many sheet pixels are one building")
    ap.add_argument("--open", nargs="*", default=[], help="types whose frame is open: the ground through them goes too")
    ap.add_argument("--out", type=pathlib.Path, default=OUT)
    a = ap.parse_args()
    im = Image.open(a.sheet).convert("RGB")
    ground = im.getpixel((4, 4))
    found = []
    for box in sheet.boxes(im, ground, gap=a.gap):
        cuts = [x for x in a.split if box[0] < x < box[2]]
        edges = [box[0], *cuts, box[2] + 1]
        found += [(l, box[1], r - 1, box[3]) for l, r in zip(edges, edges[1:])]
    if len(found) != len(a.types):
        raise SystemExit(f"{len(found)} buildings on the sheet, {len(a.types)} types given")
    for kind, box in zip(a.types, found):
        img = cut(im, box, ground, kind in a.open)
        save(img, a.out / kind, a.scale)
        for which in (*BIOMES, "ice"):
            save(biome(img, which), a.out / kind, a.scale, f"header-{which}")
        print(f"{kind}: {img.width}×{img.height} → {round(img.width * a.scale)}×{round(img.height * a.scale)}")


if __name__ == "__main__":
    main()
