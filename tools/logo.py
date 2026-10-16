"""The Orkline mark and logo, drawn from the Mechanic's head (the owner, 15 October): SVGs, favicons, the README's
logo and the phone's icons.

    python tools/logo.py [--out DIR]

The mark is the Mechanic of the roles (`design-system/sprites/v3/orks/roles/mechanic.png`) as it is drawn, cut above
its shoulders (`MARK_BOX`). Out come, in `design-system/logo/` by default (the GUI serves it at `/ds/logo/`):

- `ork-mark.svg`, `ork-mark-camp.svg`, `ork-mark-light.svg`: the head, one path per colour (the art keeps its own);
- `ork-mark-mono.svg`: one colour (`currentColor`), its darkest pixels cut out;
- `orkcraft-dark.svg`, `orkcraft-light.svg`: the head with the word, set in New Rocker (the wordmark's face) and
  turned into outlines so it needs no font;
- `favicon-16.png`, `favicon-32.png`, `favicon.ico`, `ork-mark-256.png`, `ork-mark-<n>.png` (the head at the source's
  own pixels): the head cut from the generated sheet itself (`head_source`), downscaled once with LANCZOS on
  premultiplied alpha to each size, on a clear ground;

and `docs/img/logo-dark.png`, `logo-light.png` (the README's: the word in New Rocker with its shadow) and the phone's
`icon-192.png`, `icon-512.png` (clear) and `apple-touch-icon.png` (iOS wants it opaque: one token colour behind the
head) (`orkcraft/gui/static/pwa/`).

The agent's small head in the GUI is still the 12×8 grid below: `design-system/sprites/orks/` gets `ork.png` (drawn
at 2× (24×16) and 4× (`@2x`)) and its states with their glyph beside the head on a 20×8 grid (40×16): `ork-idle` eyes
shut and Zz, `ork-busy` a gear, `ork-waiting` a flame on the crown and `!`, `ork-frozen` a snowflake, `ork-draft` a
page.

Needs `pip install fonttools brotli pillow` (brotli reads the woff2 font).
"""
from __future__ import annotations

import argparse
import json
import pathlib

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
import numpy as np
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
    """The agent's head and its states for the GUI (design-system/sprites/orks/), and the Workchief's."""
    out.mkdir(parents=True, exist_ok=True)
    for name in STATES:
        grid = state_grid(name)
        grid_image(grid, SPRITE_COLOURS, 2).save(out / f"{name}.png")
        grid_image(grid, SPRITE_COLOURS, 4).save(out / f"{name}@2x.png")
    for name, grid in warchief_grids().items():
        grid_image(grid, SPRITE_COLOURS, 2).save(out / f"{name}.png")
        grid_image(grid, SPRITE_COLOURS, 4).save(out / f"{name}@2x.png")


# The Workchief: the ork's head under a gold crown (docs/design/growth.md §8), two rows over the 12×8 grid.
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


def word_path(text: str, cap: float, x: float, baseline: float, face: pathlib.Path = FONT) -> tuple[str, float]:
    """The word as one SVG path whose capitals stand `cap` units tall; returns it and its width."""
    font = TTFont(face)
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
    """The mark and the word side by side: capitals 45 % of the head's height, centred on it."""
    head = mark()
    hw, hh = head.width * CELL, head.height * CELL
    cap = 0.45 * hh
    baseline = (hh + cap) / 2
    gap = 3 * CELL
    d, width = word_path(WORD, cap, hw + gap, baseline, WORDMARK_FONT)
    total = hw + gap + width
    body = mark_svg_body(head) + f'<path fill="{colours["word"]}" d="{d}" shape-rendering="geometricPrecision"/>'
    return svg(round(total + 1), hh, body, WORD)


# --- the mark: the Mechanic's head, as drawn (the owner, 15 October) ------------------------------------------------
# The owner chose the Mechanic of the roles (design-system/sprites/v3/orks/roles/mechanic.png) as the mark, as it is
# drawn, cut above its shoulders. Every logo file is built from these pixels: SVGs as one path per colour, rasters at
# whole multiples (and, under its own size, the favicon's 16 px boxed down), the README's logo, the phone's icons.
MARK_SPRITE = ROOT / "design-system" / "sprites" / "v3" / "orks" / "roles" / "mechanic.png"
MARK_BOX = (5, 6, 34, 30)                   # the head on the sprite, from the cap to the chin's outline
MARK_CLEAR = [(0, 27, 12, 30), (31, 27, 40, 30)]   # the shoulders beside the chin, on the sprite, left out
WORD = "Orkline"
WORDMARK_FONT = ROOT / "design-system" / "fonts" / "new-rocker-latin-400-normal.woff2"


# Cleaned for a mark (the owner: "too many stray pixels"): every pixel moved onto the sprite's own ten main colours
# (outline, face and its shade, cap and its shade, the frames' two browns, lens, glint, tusk), then a lone fleck takes
# its neighbours' colour and a tip of the outline hanging by one pixel goes; the lenses, glints and tusks always stay.
MARK_PALETTE = ["#1b0a1e", "#6f734b", "#57573c", "#877659", "#67584a", "#553532", "#795540", "#6dcff4", "#defdff",
                "#f9f9a5"]
MARK_KEEP = 3                               # the last three: never taken for flecks


def _rgb(h: str) -> tuple[int, int, int]:
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def clean(img: Image.Image, passes: int = 2) -> Image.Image:
    from collections import Counter
    pal = [_rgb(h) for h in MARK_PALETTE]
    keep = set(pal[-MARK_KEEP:])
    out = img.copy()
    px = out.load()
    for y in range(out.height):
        for x in range(out.width):
            r, g, b, a = px[x, y]
            px[x, y] = min(pal, key=lambda p: sum((u - v) ** 2 for u, v in zip(p, (r, g, b)))) + (255,) if a else (0, 0, 0, 0)
    for _ in range(passes):
        src, px = out.copy().load(), out.load()
        for y in range(out.height):
            for x in range(out.width):
                if not src[x, y][3]:
                    continue
                near = [src[x + dx, y + dy] for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                        if 0 <= x + dx < out.width and 0 <= y + dy < out.height and src[x + dx, y + dy][3]]
                if len(near) <= 1:
                    px[x, y] = (0, 0, 0, 0)
                elif src[x, y][:3] not in keep and not any(n[:3] == src[x, y][:3] for n in near):
                    colour, n = Counter(c[:3] for c in near).most_common(1)[0]
                    if n >= 2:
                        px[x, y] = colour + (255,)
    return out


def mark() -> Image.Image:
    img = Image.open(MARK_SPRITE).convert("RGBA")
    for box in MARK_CLEAR:
        img.paste((0, 0, 0, 0), box)
    return clean(img.crop(MARK_BOX))


def mark_svg_body(img: Image.Image, mono: str | None = None) -> str:
    """The head as SVG paths, one per colour (or, `mono`, one colour with its darkest pixels cut out)."""
    by: dict[str, list[tuple[int, int, int]]] = {}
    px = img.load()
    for y in range(img.height):
        x = 0
        while x < img.width:
            r, g, b, a = px[x, y]
            if not a or (mono and 0.299 * r + 0.587 * g + 0.114 * b < 60):
                x += 1
                continue
            colour = mono or f"#{r:02x}{g:02x}{b:02x}"
            start = x
            while x < img.width and px[x, y][3] and (mono or px[x, y][:3] == (r, g, b)) and not (
                    mono and 0.299 * px[x, y][0] + 0.587 * px[x, y][1] + 0.114 * px[x, y][2] < 60):
                x += 1
            by.setdefault(colour, []).append((start, y, x - start))
    return "".join(f'<path fill="{c}" d="' + "".join(f"M{x * CELL} {y * CELL}h{n * CELL}v{CELL}h{-n * CELL}z"
                                                   for x, y, n in runs_) + '"/>' for c, runs_ in by.items())


SOURCE_FILL = 0.875     # the head fills this much of a raster's longer side, a little clear margin round it
APPLE_GROUND = "#e3bf9a"    # tokens.css `--ink-gold` (camp): the warm tan of the Mechanic's hat and frames, so the
                            # head's dark outline and olive face read on it; iOS wants this one icon opaque


def head_source() -> np.ndarray:
    """The Mechanic's head cut once from the generated sheet itself (RGBA floats 0..1, straight alpha), at the
    sheet's own pixels (about 7 per art px of today's sprite): the background keyed out with despill (tools/camp_hd.py),
    only the sprite's own cells kept, the shoulders left out, trimmed. Never re-pixelated."""
    import sys
    sys.path.insert(0, str(ROOT / "tools"))
    import camp_hd
    import camp_sheet
    spec = json.loads((ROOT / "tools" / "camp_sheets_v3.json").read_text(encoding="utf-8"))
    sh = next(x for x in spec["sheets"] for g in x.get("groups", []) for i in g["items"]
              if i["file"] == "orks/roles/mechanic.png")
    item = next(i for g in sh["groups"] for i in g["items"] if i["file"] == "orks/roles/mechanic.png")
    row = next(r for r in json.loads((ROOT / "design-system" / "sprites" / "v3" / "manifest.json")
                                     .read_text(encoding="utf-8"))["sprites"] if r["file"] == "orks/roles/mechanic.png")
    sheet = camp_sheet.Sheet(ROOT / sh.get("root", spec["root"]) / sh["file"], sh.get("fringe", 60),
                             sh.get("close", 1), sh.get("degrid", spec.get("degrid", False)))
    c = row["pitch"] * row["scale"]                 # source px per art px of today's sprite
    iw, ih = row["size"]
    today = np.asarray(Image.open(MARK_SPRITE).convert("RGBA"))[..., 3] > 0
    box = sheet.at(*item["at"])
    x0, y0, x1, y1 = sheet.screen(box)
    sx = x0 - np.flatnonzero(today.any(axis=0))[0] * c      # where the sprite's slot starts on the sheet
    sy = y1 - ih * c                                          # bottom-anchored
    bx0, by0, bx1, by1 = MARK_BOX
    X0, Y0 = int(np.floor(sx + (bx0 - 1) * c)), int(np.floor(sy + (by0 - 1) * c))
    X1, Y1 = int(np.ceil(sx + (bx1 + 1) * c)), int(np.ceil(sy + (by1 + 1) * c))
    rgba = camp_hd.unkey(sheet.a[Y0:Y1, X0:X1], sheet.bg[Y0:Y1, X0:X1])
    # keep what lies over the head of today's sprite (one art px round it): inside the box, less the shoulders beside
    # the chin, and only its biggest piece (a tool of the next frame's hangs at the edge, unjoined)
    head = today.copy()
    head[:, :bx0] = head[:, bx1:] = False
    head[:by0] = head[by1:] = False
    for cx0, cy0, cx1, cy1 in MARK_CLEAR:
        head[cy0:cy1, cx0:cx1] = False
    lab, n = camp_sheet.label(head)
    if n:
        head = lab == 1 + int(np.argmax([(lab == i).sum() for i in range(1, n + 1)]))
    keep = camp_hd._near(np.pad(head, 1), 1)
    ys = np.clip(np.floor((np.arange(Y0, Y1) - sy) / c).astype(int) + 1, 0, keep.shape[0] - 1)
    xs = np.clip(np.floor((np.arange(X0, X1) - sx) / c).astype(int) + 1, 0, keep.shape[1] - 1)
    rgba[..., 3] *= keep[ys[:, None], xs[None]]
    solid = np.argwhere(rgba[..., 3] > 0.02)
    (ty0, tx0), (ty1, tx1) = solid.min(axis=0), solid.max(axis=0) + 1
    return rgba[ty0:ty1, tx0:tx1]


def mark_raster(size: int, ground: tuple[int, int, int, int] = (0, 0, 0, 0), fill: float = SOURCE_FILL) -> Image.Image:
    """The head centred on a square of `size` px, its longer side `fill` of it: one LANCZOS downscale (premultiplied,
    linear light) straight from the sheet's pixels to `size`, never through a pixel grid."""
    import sys
    sys.path.insert(0, str(ROOT / "tools"))
    import camp_hd
    src = head_source()
    f = size * fill / max(src.shape[:2])
    w, h = max(1, round(src.shape[1] * f)), max(1, round(src.shape[0] * f))
    head = Image.fromarray(camp_hd.downscale(src, (0, 0, src.shape[1], src.shape[0]), (w, h)), "RGBA")
    img = Image.new("RGBA", (size, size), ground)
    img.alpha_composite(head, ((size - w) // 2, (size - h) // 2))
    return img


def native_size() -> int:
    """The square the head fills at the sheet's own pixels (1 source px = 1 image px)."""
    return round(max(head_source().shape[:2]) / SOURCE_FILL)


def readme_logo(text: str, shadow: str, height: int = 192) -> Image.Image:
    """The README's logo: the head at a whole multiple and the word in New Rocker with its offset shadow, on clear."""
    import io

    from PIL import ImageDraw, ImageFont
    font = TTFont(WORDMARK_FONT)
    font.flavor = None
    buf = io.BytesIO()
    font.save(buf)
    word = ImageFont.truetype(io.BytesIO(buf.getvalue()), 132)
    head = mark()
    k = int(height * 0.7) // head.height
    head = head.resize((head.width * k, head.height * k), Image.NEAREST)
    x0 = 24 + head.width + 40
    l, t, r, b = word.getbbox(WORD)
    img = Image.new("RGBA", (x0 + r + 32, height), (0, 0, 0, 0))
    img.alpha_composite(head, (24, (height - head.height) // 2))
    d = ImageDraw.Draw(img)
    y = (height - (b - t)) // 2 - t
    d.text((x0 + 6, y + 6), WORD, font=word, fill=shadow)
    d.text((x0, y), WORD, font=word, fill=text)
    return img


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=pathlib.Path, default=ROOT / "design-system" / "logo")
    out = ap.parse_args().out
    out.mkdir(parents=True, exist_ok=True)

    head = mark()
    vw, vh = head.width * CELL, head.height * CELL
    body = mark_svg_body(head)
    for name in ("ork-mark.svg", "ork-mark-camp.svg", "ork-mark-light.svg"):     # the art keeps its own colours
        (out / name).write_text(svg(vw, vh, body, WORD))
    (out / "ork-mark-mono.svg").write_text(svg(vw, vh, mark_svg_body(head, "currentColor"), WORD))
    (out / "orkcraft-dark.svg").write_text(lockup(PALETTES["office"]))
    (out / "orkcraft-light.svg").write_text(lockup(PALETTES["light"]))
    for size in (16, 32):
        mark_raster(size).save(out / f"favicon-{size}.png")
    mark_raster(256).save(out / "ork-mark-256.png")
    native = native_size()      # the largest clean size: the sheet's own pixels (not 1024)
    mark_raster(native).save(out / f"ork-mark-{native}.png")
    # every size drawn on its own, never scaled down from the largest
    mark_raster(48).save(out / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)],
                         append_images=[mark_raster(16), mark_raster(32)])
    docs = ROOT / "docs" / "img"
    readme_logo("#e8dfc6", "#000000").save(docs / "logo-dark.png")
    readme_logo("#1d1a12", "#cdbf96").save(docs / "logo-light.png")
    pwa = ROOT / "orkcraft" / "gui" / "static" / "pwa"
    for name, size in (("icon-192.png", 192), ("icon-512.png", 512)):
        mark_raster(size).save(pwa / name)                      # clear: the OS masks it as it likes
    ground = tuple(int(APPLE_GROUND[i:i + 2], 16) for i in (1, 3, 5)) + (255,)
    mark_raster(180, ground, 0.8).convert("RGB").save(pwa / "apple-touch-icon.png")   # iOS wants it opaque
    sprites(ROOT / "design-system" / "sprites" / "orks")
    print(f"wrote {out} and the ork sprites")


if __name__ == "__main__":
    main()
