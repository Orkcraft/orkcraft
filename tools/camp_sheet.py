"""Cut keyed reference sheets into Camp's v2 sprites (docs/design/design-system-v2.md §11).

    python tools/camp_sheet.py                  cut every sheet in tools/camp_sheets.json
    python tools/camp_sheet.py --only carts     cut only the sheets whose name contains "carts"
    python tools/camp_sheet.py --list SHEET     print the pieces found on a sheet (to write its spec)
    python tools/camp_sheet.py --check DIR      also render each nine-slice kit as a 3 × 3 and a 5 × 4 into DIR
    python tools/camp_sheet.py --v3             cut the v3 sheets that have arrived (tools/camp_sheets_v3.json) into
                                                design-system/sprites/v3/; the rest are listed as awaited
    python tools/camp_sheet.py --v3 --expect    only list the v3 sheets, their sprites and sizes, and which are there

A sheet is a generated image on flat `#FF00FF` drawn in "pixels" of a few screen pixels. The steps, in v2's order:

1. **key** the magenta, and the purple fringe a shadow blended into it (red and blue both well above green);
2. **snap** the sheet to its own pixel grid (the pitch and phase read from where the colour changes): each cell
   takes the median of its inner pixels, and a cell less than half covered is transparent;
3. **find** each sprite as a connected shape on that grid (gaps of `close` cells closed) and take the one nearest
   the point the spec names (fractions of the sheet, so a spec survives a resized sheet);
4. a sprite that does not fit its slot is read again from the screen pixels at a coarser cell (one scale for a
   whole group, so the frames of a strip match); a tile drawn with a dark border is cut inside the border first
   and read into exactly its size;
5. **trim**, then **pad** to the slot (a multiple of 8) at its anchor (feet at the bottom centre, tiles at the
   top left); a nine-slice kit's pieces are cut from the outer side of each piece at the sheet's own scale;
6. **snap the colours** to the `art-*` / `world-*` tokens and the tones the spec lists for the group, the outline
   to `art-outline`; only signal sprites may keep `signal-*`;
7. **write** the PNG (RGBA, no smoothing, no metadata), its row in `manifest.json`, and for the covers the map's
   half-size copy;
8. **check:** every size a multiple of 8, no signal hue outside signal sprites; with `--check`, the kits tiled;
9. **faces:** each ork's face recut from its role body (`tools/camp_faces.py`, the spec's `faces`).

**v3** (docs/design/design-system-v3.md §8): the sheets of docs/design/v3-prompts.md §3 are drawn "in a neat grid with
even spacing", so a v3 item names its piece by `order`, its place in reading order (rows top to bottom, each left to
right, counted from 0), instead of a point; `--list` prints that order. A sheet not yet in the folder is skipped and
listed as awaited, so the command is the same before and after each sheet arrives. A sheet with `degrid` (the ork sheets: the
model drew a box round every cell) has its drawn grid dropped before the pieces are found: long, thin, dark straight
runs with the background on both sides, the key's own darkened violet, and a cut along every line drawn across most of
the sheet (`--degrid --list SHEET` to try it). The v3 spec sets `native` (each
sprite cut at the sheet's own art pixel, never re-read coarser; its slot is what the sheet draws, rounded up to the
grid of 8, and a size in the spec is only the plan) and `keep_colours` (no snap to the tokens: the art keeps its own
shading; the cutter only reports pixels in a signal's yellow, orange or red). The sheets are soft (the model renders
at about 4.17 image px per art px and smooths it, and JPEG blurs again), so each art pixel is the median of its cell's
inner pixels, then the magenta cast near the key is removed and the sprite is reduced to its own 24 colours (a median
cut on its own pixels), with a hard alpha.

Every sprite it writes is a **placeholder** (generated art, docs/design/color-pass.md §10b), to be replaced by the
commissioned artist's; the manifest says so on every row. Needs `pip install pillow numpy`.
"""
from __future__ import annotations

import argparse
import colorsys
import json
import pathlib
from collections import deque

import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
SPEC = ROOT / "tools" / "camp_sheets.json"
OUT = ROOT / "design-system" / "sprites" / "camp"
TOKENS = ROOT / "design-system" / "tokens.json"
LICENCE = "placeholder: generated reference art, not for release (docs/design/color-pass.md §10b)"
AUTHOR = "generated (docs/design/img/references/), cut by tools/camp_sheet.py"


# --- 1. key ---------------------------------------------------------------------------------------------------

def load(path: pathlib.Path) -> np.ndarray:
    return np.asarray(Image.open(path).convert("RGB")).astype(np.int16)


def keyed(a: np.ndarray, fringe: int = 60) -> np.ndarray:
    """True where the sheet is background: the magenta, and the purple a blended shadow left in it."""
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    return ((r - g > fringe) & (b - g > fringe) & (b > r * 0.55)) | ((r > 200) & (b > 200) & (g < 90))


def _runs(m: np.ndarray) -> np.ndarray:
    """For each True pixel, the length of the horizontal run of True it lies in."""
    out = np.zeros(m.shape, np.int32)
    for y in range(m.shape[0]):
        row = m[y].astype(np.int8)
        d = np.diff(np.concatenate(([0], row, [0])))
        starts, ends = np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]
        for a, b in zip(starts, ends):
            out[y, a:b] = b - a
    return out


def degrid(a: np.ndarray, bg: np.ndarray, length: int = 120, thick: int = 14, dark: int = 90) -> np.ndarray:
    """The background with a drawn grid added to it: the boxes or lines an image model draws round each cell (thin
    dark straight runs at least `length` px long and at most `thick` px across), so they no longer join the sprites.
    A sprite's own outline is shorter, or lies against a dark area of the sprite (thicker than `thick`)."""
    lum = 0.3 * a[..., 0] + 0.59 * a[..., 1] + 0.11 * a[..., 2]
    d = ~bg & (lum < dark)
    h_run, v_thick = _runs(d), _runs(d.T).T
    v_run, h_thick = v_thick, h_run
    # a drawn line has the background on both sides; a sprite's own straight outline has the sprite on one side
    def near_bg(dy: int, dx: int) -> np.ndarray:
        out = np.zeros_like(bg)
        for k in range(1, thick + 4):
            out |= np.roll(bg, (dy * k, dx * k), axis=(0, 1))
        return out
    across_v = near_bg(1, 0) & near_bg(-1, 0)          # background above and below: a horizontal line
    across_h = near_bg(0, 1) & near_bg(0, -1)          # left and right: a vertical one
    line = (h_run >= length) & (v_thick <= thick) & across_v | (v_run >= length) & (h_thick <= thick) & across_h
    # where a sprite touches a drawn line the run is thicker; the line's own colour is the key darkened (a violet with
    # blue at least red: the plum cloth, bluer than red never, is kept), so that goes too
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    violet = ~bg & (lum < 110) & (r - g > 40) & (b - g > 40) & (b * 20 >= r * 19)
    out = bg | _grow(line, 2) | violet
    # a line drawn across most of the sheet is a cut between cells, whatever smudge crosses it (cut wide enough that
    # the closing of small gaps, a cell or two, does not bridge it)
    lines = line | violet
    for axis in (0, 1):
        full = lines.mean(axis=axis) >= 0.6
        if axis == 0:
            out[:, _grow(full[None], 8)[0]] = True
        else:
            out[_grow(full[:, None], 8)[:, 0], :] = True
    return out


# --- 2. the sheet's own grid ----------------------------------------------------------------------------------

def _period(profile: np.ndarray, lo: float = 4.0, hi: float = 12.0) -> tuple[float, float]:
    """The pitch and phase at which the colour edges along one axis line up best."""
    n = np.arange(len(profile))
    best = (0.0, lo, 0.0)
    for p in np.arange(lo, hi, 0.01):
        s = (profile * np.exp(2j * np.pi * n / p)).sum()
        c = abs(s) / max(profile.sum(), 1)
        if c > best[0]:
            best = (c, p, (np.angle(s) % (2 * np.pi)) * p / (2 * np.pi))
    return best[1], best[2]


def grid(a: np.ndarray, bg: np.ndarray) -> tuple[float, float, float]:
    """The pitch (screen px per art px) and the x, y where a cell starts."""
    lum = 0.3 * a[..., 0] + 0.59 * a[..., 1] + 0.11 * a[..., 2]
    dx = np.abs(np.diff(lum, axis=1))
    dx[bg[:, 1:] | bg[:, :-1]] = 0
    dy = np.abs(np.diff(lum, axis=0))
    dy[bg[1:] | bg[:-1]] = 0
    px, ox = _period(dx.sum(0))
    py, oy = _period(dy.sum(1))
    pitch = (px + py) / 2
    # an edge at diff index i lies between pixels i and i+1: a cell starts one pixel after it
    return pitch, (ox + 1) % pitch, (oy + 1) % pitch


def snap(a: np.ndarray, bg: np.ndarray, x0: float, y0: float, cw: float, ch: float, w: int, h: int,
         samples: int = 4) -> np.ndarray:
    """Read a w × h grid of cells (cw × ch screen px each, from x0, y0) into RGBA: each cell's median colour over
    its inner pixels, opaque when at least half of them are not background."""
    H, W = bg.shape
    k = np.arange(samples)
    fx = 0.2 + 0.6 * k / max(samples - 1, 1)                    # the inner 60 % of a cell, away from JPEG bleed
    xs = np.clip((x0 + (np.arange(w)[:, None] + fx[None]) * cw).astype(int), 0, W - 1)    # w × s
    ys = np.clip((y0 + (np.arange(h)[:, None] + fx[None]) * ch).astype(int), 0, H - 1)    # h × s
    yy = ys[:, None, :, None]
    xx = xs[None, :, None, :]
    px = a[yy, xx]                                                # h × w × s × s × 3
    cover = ~bg[yy, xx]
    flat = px.reshape(h, w, -1, 3).astype(float)
    mask = cover.reshape(h, w, -1)
    flat[~mask] = np.nan
    with np.errstate(all="ignore"):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            med = np.nanmedian(flat, axis=2)
    out = np.zeros((h, w, 4), np.uint8)
    opaque = mask.mean(axis=2) >= 0.5
    out[..., :3] = np.nan_to_num(med).clip(0, 255).astype(np.uint8)
    out[..., 3] = np.where(opaque, 255, 0)
    out[~opaque, :3] = 0
    return out


# --- 3. find each sprite ---------------------------------------------------------------------------------------

def _grow(m: np.ndarray, n: int) -> np.ndarray:
    out = m.copy()
    p = np.pad(m, n)
    h, w = m.shape
    for dy in range(2 * n + 1):
        for dx in range(2 * n + 1):
            out |= p[dy:dy + h, dx:dx + w]
    return out


def label(m: np.ndarray) -> tuple[np.ndarray, int]:
    """Each 8-connected shape of a mask numbered from 1."""
    h, w = m.shape
    lab = np.zeros(m.shape, np.int32)
    n = 0
    for y0, x0 in zip(*np.nonzero(m)):
        if lab[y0, x0]:
            continue
        n += 1
        lab[y0, x0] = n
        q = deque([(y0, x0)])
        while q:
            y, x = q.popleft()
            for ny in (y - 1, y, y + 1):
                for nx in (x - 1, x, x + 1):
                    if 0 <= ny < h and 0 <= nx < w and m[ny, nx] and not lab[ny, nx]:
                        lab[ny, nx] = n
                        q.append((ny, nx))
    return lab, n


def pieces(alpha: np.ndarray, close: int = 1, min_cells: int = 12) -> list[tuple[int, int, int, int]]:
    """Each connected shape's box (x0, y0, x1, y1) on the art grid, gaps of `close` cells closed."""
    m = alpha > 0
    lab, n = label(_grow(m, close))
    out = []
    for i in range(1, n + 1):
        ys, xs = np.nonzero(lab == i)
        box = (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)
        if m[box[1]:box[3], box[0]:box[2]].sum() >= min_cells:
            out.append(box)
    return out


def largest(img: np.ndarray, close: int = 1) -> np.ndarray:
    """Only the biggest shape (and what lies within `close` of it): a stray speck or smudge of the sheet dropped."""
    m = img[..., 3] > 0
    lab, n = label(_grow(m, close))
    if n < 2:
        return img
    sizes = [(m & (lab == i)).sum() for i in range(1, n + 1)]
    out = img.copy()
    out[lab != 1 + int(np.argmax(sizes))] = 0
    return trim(out)


class Sheet:
    def __init__(self, path: pathlib.Path, fringe: int = 60, close: int = 1, grid_lines: bool = False):
        self.path = path
        self.a = load(path)
        self.bg = keyed(self.a, fringe)
        self.pitch, self.ox, self.oy = grid(self.a, self.bg)
        if grid_lines:                          # a drawn box or line round every cell: background too (after the
            self.bg = degrid(self.a, self.bg)   # pitch, which the sprites' own edges set either way)
        H, W = self.bg.shape
        self.w, self.h = int((W - self.ox) / self.pitch), int((H - self.oy) / self.pitch)
        self.art = snap(self.a, self.bg, self.ox, self.oy, self.pitch, self.pitch, self.w, self.h)
        self.boxes = pieces(self.art[..., 3], close)

    def at(self, fx: float, fy: float) -> tuple[int, int, int, int]:
        """The piece nearest a point given as fractions of the sheet."""
        x, y = fx * self.w, fy * self.h
        def dist(b):
            dx = max(b[0] - x, 0, x - b[2])
            dy = max(b[1] - y, 0, y - b[3])
            return (dx * dx + dy * dy, abs((b[0] + b[2]) / 2 - x) + abs((b[1] + b[3]) / 2 - y))
        return min(self.boxes, key=dist)

    def ordered(self) -> list[tuple[int, int, int, int]]:
        """The pieces in reading order: rows (a piece joins a row when its middle lies within the row's first piece's
        height), top to bottom, each left to right."""
        rows: list[list[tuple[int, int, int, int]]] = []
        for b in sorted(self.boxes, key=lambda b: b[1]):
            mid = (b[1] + b[3]) / 2
            for row in rows:
                if row[0][1] <= mid <= row[0][3]:
                    row.append(b)
                    break
            else:
                rows.append([b])
        return [b for row in rows for b in sorted(row, key=lambda b: b[0])]

    def nth(self, n: int) -> tuple[int, int, int, int]:
        pieces_ = self.ordered()
        if n >= len(pieces_):
            raise SystemExit(f"{self.path.name}: piece {n} asked, {len(pieces_)} found (see --list)")
        return pieces_[n]

    def box(self, fbox: list[float]) -> tuple[int, int, int, int]:
        return (int(fbox[0] * self.w), int(fbox[1] * self.h), int(np.ceil(fbox[2] * self.w)),
                int(np.ceil(fbox[3] * self.h)))

    def screen(self, box) -> tuple[float, float, float, float]:
        return (self.ox + box[0] * self.pitch, self.oy + box[1] * self.pitch,
                self.ox + box[2] * self.pitch, self.oy + box[3] * self.pitch)

    def native(self, box) -> np.ndarray:
        return self.art[box[1]:box[3], box[0]:box[2]].copy()

    def coarse(self, box, scale: float) -> np.ndarray:
        """The piece read again at `scale` art px of this sheet per new art px."""
        x0, y0, x1, y1 = self.screen(box)
        c = self.pitch * scale
        w, h = int(np.ceil((x1 - x0) / c)), int(np.ceil((y1 - y0) / c))
        return snap(self.a, self.bg, x0, y0, c, c, w, h)

    def tile(self, box, w: int, h: int, border_lum: int = 70) -> np.ndarray:
        """A tile cut inside its dark border and read into exactly w × h."""
        x0, y0, x1, y1 = self.tile_box(box, border_lum)
        return snap(self.a, self.bg, x0, y0, (x1 - x0) / w, (y1 - y0) / h, w, h)

    def tile_box(self, box, border_lum: int = 70) -> tuple[int, int, int, int]:
        """The tile's box in screen px, inside its dark border."""
        x0, y0, x1, y1 = (int(v) for v in self.screen(box))
        lum = 0.3 * self.a[..., 0] + 0.59 * self.a[..., 1] + 0.11 * self.a[..., 2]
        def is_border(ys, xs):
            sl = lum[ys, xs]
            bgs = self.bg[ys, xs]
            return bool(np.median(np.where(bgs, 0, sl)) < border_lum)
        for _ in range(int(self.pitch * 4)):
            if is_border(slice(y0, y1), x0):
                x0 += 1
            else:
                break
        for _ in range(int(self.pitch * 4)):
            if is_border(slice(y0, y1), x1 - 1):
                x1 -= 1
            else:
                break
        for _ in range(int(self.pitch * 4)):
            if is_border(y0, slice(x0, x1)):
                y0 += 1
            else:
                break
        for _ in range(int(self.pitch * 4)):
            if is_border(y1 - 1, slice(x0, x1)):
                y1 -= 1
            else:
                break
        return x0, y0, x1, y1


# --- 4–5. trim, pad, anchor ------------------------------------------------------------------------------------

def trim(img: np.ndarray) -> np.ndarray:
    ys, xs = np.nonzero(img[..., 3])
    if not len(xs):
        return img[:0, :0]
    return img[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def feet_x(img: np.ndarray, rows: int = 6) -> float:
    """The centre of what stands on the ground: the opaque columns of the bottom rows."""
    a = img[..., 3] > 0
    bottom = a[-rows:].any(axis=0)
    xs = np.nonzero(bottom)[0]
    return (xs.min() + xs.max() + 1) / 2 if len(xs) else img.shape[1] / 2


def pad(img: np.ndarray, w: int, h: int, anchor: str, cx: float | None = None) -> np.ndarray:
    """Place a trimmed sprite into a w × h slot at its anchor, cropping what overflows (said by the caller)."""
    out = np.zeros((h, w, 4), np.uint8)
    ih, iw = img.shape[:2]
    if anchor in ("feet", "bottom-centre"):
        cx = iw / 2 if cx is None or anchor == "bottom-centre" else cx
        x = int(round(w / 2 - cx))
        y = h - ih
    elif anchor == "bottom-left":
        x, y = 0, h - ih
    elif anchor == "centre":
        x, y = (w - iw) // 2, (h - ih) // 2
    else:                                                       # top-left
        x, y = 0, 0
    sx0, sy0 = max(0, -x), max(0, -y)
    dx0, dy0 = max(0, x), max(0, y)
    cw, ch = min(iw - sx0, w - dx0), min(ih - sy0, h - dy0)
    if cw > 0 and ch > 0:
        out[dy0:dy0 + ch, dx0:dx0 + cw] = img[sy0:sy0 + ch, sx0:sx0 + cw]
    return out


def up8(n: int) -> int:
    return -(-n // 8) * 8


# --- 6. the palette ---------------------------------------------------------------------------------------------

def palette(extra: list[str] = (), signals: bool = False) -> dict[str, tuple[int, int, int]]:
    toks = json.loads(TOKENS.read_text(encoding="utf-8"))["color"]["tokens"]
    names = ("world-", "art-") + (("signal-",) if signals else ())
    out = {t["name"]: _rgb(t["value"]["camp"]) for t in toks
           if t["name"].startswith(names) and t["name"] not in ("art-shadow", "art-grid")
           and len(t["value"]["camp"]) == 7}
    for hx in extra:
        out[hx] = _rgb(hx)
    return out


def _rgb(hx: str) -> tuple[int, int, int]:
    return int(hx[1:3], 16), int(hx[3:5], 16), int(hx[5:7], 16)


def _lab(rgb: np.ndarray) -> np.ndarray:
    c = rgb / 255.0
    c = np.where(c > 0.04045, ((c + 0.055) / 1.055) ** 2.4, c / 12.92)
    m = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = c @ m.T / np.array([0.9505, 1.0, 1.089])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def recolour(img: np.ndarray, pal: dict[str, tuple[int, int, int]]) -> np.ndarray:
    names = list(pal)
    cols = np.array([pal[n] for n in names], float)
    lab = _lab(img[..., :3].astype(float))
    d = ((lab[..., None, :] - _lab(cols)[None, None]) ** 2).sum(-1)
    idx = d.argmin(-1)
    out = img.copy()
    out[..., :3] = cols[idx].astype(np.uint8)
    out[img[..., 3] == 0] = 0
    return out


def loud(rgb: tuple[int, int, int]) -> bool:
    """A signal's yellow or red (the rule of tests/test_design.py for the world tokens)."""
    h, _, s = colorsys.rgb_to_hls(*(v / 255 for v in rgb))
    return s > 0.6 and (h * 360 < 15 or h * 360 > 345 or 45 <= h * 360 <= 65)


def decast(img: np.ndarray, near: int = 3) -> np.ndarray:
    """The magenta a soft sheet blended into a sprite's edge (the Agent pool's floor shade): an opaque pixel within
    `near` px of the transparent key whose hue leans to magenta (red and blue both well above green, blue at least
    three quarters of red — the plum banners' cloth is redder) takes the median of its non-magenta neighbours, or is
    dropped when it has none."""
    rgb = img[..., :3].astype(int)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    opaque = img[..., 3] > 0
    magenta = opaque & (r - g > 25) & (b - g > 25) & (b * 4 >= r * 3)
    magenta &= _grow(~opaque, near)
    out = img.copy()
    h, w = magenta.shape
    for y, x in zip(*np.nonzero(magenta)):
        y0, y1, x0, x1 = max(y - 2, 0), min(y + 3, h), max(x - 2, 0), min(x + 3, w)
        ok = opaque[y0:y1, x0:x1] & ~magenta[y0:y1, x0:x1]
        if ok.any():
            out[y, x, :3] = np.median(rgb[y0:y1, x0:x1][ok], axis=0).astype(np.uint8)
        else:
            out[y, x] = 0
    return out


def own_palette(img: np.ndarray, n: int = 24) -> np.ndarray:
    """The sprite reduced to its own `n` colours (a median cut on its own opaque pixels, not the tokens), so the
    smoothing of the image model and the JPEG's noise inside one art pixel are gone and the shading stays."""
    opaque = img[..., 3] > 0
    px = img[..., :3][opaque].astype(int)
    if len(px) == 0:
        return img
    boxes = [px]
    while len(boxes) < n:
        i = max(range(len(boxes)), key=lambda k: (np.ptp(boxes[k], axis=0).max() if len(boxes[k]) > 1 else -1))
        box = boxes[i]
        if len(box) < 2 or np.ptp(box, axis=0).max() == 0:
            break
        ch = int(np.ptp(box, axis=0).argmax())
        box = box[box[:, ch].argsort()]
        boxes[i:i + 1] = [box[:len(box) // 2], box[len(box) // 2:]]
    cols = np.array([np.median(bx, axis=0) for bx in boxes]).round()
    d = ((img[..., :3].astype(int)[..., None, :] - cols[None, None]) ** 2).sum(-1)
    out = np.zeros_like(img)
    out[..., :3] = cols[d.argmin(-1)].astype(np.uint8)
    out[..., 3] = np.where(opaque, 255, 0)                          # hard alpha
    out[~opaque, :3] = 0
    return out


def signal_hue(rgb: tuple[int, int, int]) -> bool:
    """A signal's yellow, orange or red (v3, docs/design/design-system-v3.md §8): saturated and bright, from red to
    yellow. The honey wood and the sand (saturation about 0.5–0.65) are below it; `#facc15` and `#e8411c` above."""
    h, s, v = colorsys.rgb_to_hsv(*(c / 255 for c in rgb))
    return s >= 0.75 and v >= 0.7 and (h * 360 <= 65 or h * 360 >= 340)


def seam(img: np.ndarray, rel: str, period: int = 0) -> str:
    """How a straight tile joins itself: the colour step across the seam against the mean step inside the tile, and
    the ties' spacing across the seam against their spacing inside (a straight-v is read turned)."""
    a = img if "straight-h" in rel else img.transpose(1, 0, 2)
    rgb = a[..., :3].astype(float)
    inside = np.abs(np.diff(rgb, axis=1)).mean()
    across = np.abs(rgb[:, 0] - rgb[:, -1]).mean()
    if period:                                              # the same place inside: from one tie spacing to the next
        same = np.mean([np.abs(rgb[:, k - 1] - rgb[:, k]).mean() for k in range(period, a.shape[1], period)])
        return f"{rel}: across the seam {across:.0f}, at the same place inside {same:.0f} (one tie spacing repeated)"
    lum = (0.3 * rgb[..., 0] + 0.59 * rgb[..., 1] + 0.11 * rgb[..., 2]) * (a[..., 3] > 0)
    prof = lum.sum(axis=0)
    dark = prof < np.median(prof) * 0.9                         # tie columns: darker across the tile
    starts = [i for i in range(len(dark)) if dark[i] and (i == 0 or not dark[i - 1])]
    gaps = np.diff(starts) if len(starts) > 1 else []
    tie = f"ties every {np.median(gaps):.0f} px, across the seam {starts[0] + len(dark) - starts[-1]} px" if len(gaps) \
        else "no ties found"
    return f"{rel}: seam step {across:.0f} against {inside:.0f} inside; {tie}"


# --- 7. write ----------------------------------------------------------------------------------------------------

def save(img: np.ndarray, rel: str) -> None:
    path = OUT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(img, "RGBA").save(path, optimize=True)


def half(img: np.ndarray) -> np.ndarray:
    """The map's half-size copy: each 2 × 2 block's most common opaque colour, opaque when two of four are."""
    h, w = img.shape[0] // 2, img.shape[1] // 2
    out = np.zeros((h, w, 4), np.uint8)
    for y in range(h):
        for x in range(w):
            block = img[2 * y:2 * y + 2, 2 * x:2 * x + 2].reshape(4, 4)
            op = block[block[:, 3] > 0]
            if len(op) >= 2:
                vals, counts = np.unique(op[:, :3], axis=0, return_counts=True)
                out[y, x, :3] = vals[counts.argmax()]
                out[y, x, 3] = 255
    return out


def strip(frames: list[np.ndarray]) -> np.ndarray:
    return np.concatenate(frames, axis=1)


# --- the spec's groups ---------------------------------------------------------------------------------------

def _extract(sheet: Sheet, item: dict) -> tuple[int, int, int, int]:
    """The piece's box on the sheet's grid: the shape nearest `at`, or everything inside `box`; then `crop` (fractions
    of that box) and `rim_of` (only what stands above the top of another piece of the same foot, e.g. a load over the
    rim of the empty cart, keeping `rim` rows below it)."""
    b = sheet.box(item["box"]) if "box" in item else sheet.nth(item["order"]) if "order" in item else sheet.at(*item["at"])
    if "crop" in item:
        fx0, fy0, fx1, fy1 = item["crop"]
        w, h = b[2] - b[0], b[3] - b[1]
        b = (b[0] + int(fx0 * w), b[1] + int(fy0 * h), b[0] + int(round(fx1 * w)), b[1] + int(round(fy1 * h)))
    if "rim_of" in item:
        ref = _trimmed_box(sheet, sheet.at(*item["rim_of"]))
        own = _trimmed_box(sheet, b)
        b = (own[0], own[1], own[2], own[3] - (ref[3] - ref[1]) + item.get("rim", 0))
    return _trimmed_box(sheet, b)


def _trimmed_box(sheet: Sheet, b) -> tuple[int, int, int, int]:
    ys, xs = np.nonzero(sheet.art[b[1]:b[3], b[0]:b[2], 3])
    if not len(xs):
        return b
    return (b[0] + xs.min(), b[1] + ys.min(), b[0] + xs.max() + 1, b[1] + ys.max() + 1)


def load_only(loaded: np.ndarray, empty: np.ndarray, rim: int) -> np.ndarray:
    """What a loaded cart has that the empty one has not: the two put foot to foot, the pixels of the loaded one that
    differ from the empty one's (or stand where it has none), down to `rim` rows below the empty bin's top, so the
    load drawn over the cart gives the loaded cart back."""
    H, W = loaded.shape[:2]
    h, w = empty.shape[:2]
    ref = np.zeros_like(loaded)
    x = (W - w) // 2
    y = H - h
    sx0, sy0 = max(0, -x), max(0, -y)
    ref[max(y, 0):max(y, 0) + h - sy0, max(x, 0):max(x, 0) + w - sx0] = empty[sy0:sy0 + H, sx0:sx0 + W][:H, :W]
    d = np.sqrt(((_lab(loaded[..., :3].astype(float)) - _lab(ref[..., :3].astype(float))) ** 2).sum(-1))
    keep = (loaded[..., 3] > 0) & ((ref[..., 3] == 0) | (d > 18))
    keep[max(y, 0) + rim:] = False
    keep = _grow(keep, 1)
    keep = ~_grow(~keep, 1) & (loaded[..., 3] > 0)              # holes where the load matched the bin, closed
    big = np.zeros_like(keep)
    for x0, y0, x1, y1 in pieces(keep.astype(np.uint8), close=0, min_cells=10):
        big[y0:y1, x0:x1] |= keep[y0:y1, x0:x1]                   # slivers of the rim a pixel off, dropped
    keep = big
    above = np.nonzero(keep[:max(y, 1)].any(axis=0))[0]          # the load's width is what stands over the rim
    if len(above):
        keep[:, :max(above.min() - 1, 0)] = False
        keep[:, above.max() + 2:] = False
    out = loaded.copy()
    out[~keep] = 0
    return trim(out)


def grass_keyed(img: np.ndarray, margin: int = 12) -> np.ndarray:
    """Transparent where green clearly leads red and blue (grass baked into a tile), so only the bed, the ties and
    the rails stay; a lone opaque pixel left in the grass goes too."""
    rgb = img[..., :3].astype(int)
    grass = (rgb[..., 1] > rgb[..., 0] + margin) & (rgb[..., 1] > rgb[..., 2] + margin)
    out = img.copy()
    out[grass] = 0
    keep = out[..., 3] > 0
    p = np.pad(keep, 1)
    near = sum(p[1 + dy:1 + dy + keep.shape[0], 1 + dx:1 + dx + keep.shape[1]]
               for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dy or dx)
    out[keep & (near < 2)] = 0
    return out


def _cut(img: np.ndarray, cut: list) -> np.ndarray:
    """A repeat unit of w × h out of a longer piece: centred across, from the bottom (a row of posts) or the middle."""
    w, h, where = cut
    H, W = img.shape[:2]
    x = max((W - w) // 2, 0)
    y = H - h if where == "bottom" else max((H - h) // 2, 0)
    return img[max(y, 0):max(y, 0) + h, x:x + w]


def _rails(img: np.ndarray, axis: int) -> tuple[np.ndarray, float]:
    """The dark rail lines across a piece (rows for axis 0: horizontal rails) and the middle between the outer two."""
    rgb = img[..., :3].astype(float)
    lum = 0.3 * rgb[..., 0] + 0.59 * rgb[..., 1] + 0.11 * rgb[..., 2]
    dark = (img[..., 3] > 0) & (lum < 90)
    prof = dark.mean(axis=1 - axis)
    lines = np.nonzero(prof >= 0.5)[0]
    return lines, ((lines.min() + lines.max() + 1) / 2 if len(lines) else img.shape[axis] / 2)


def _edge_centre(img: np.ndarray, side: str) -> float | None:
    """Where the rails cross one side of a piece: the middle of the dark pixels on its outermost opaque line."""
    a = img[..., 3] > 0
    rgb = img[..., :3].astype(float)
    dark = a & ((0.3 * rgb[..., 0] + 0.59 * rgb[..., 1] + 0.11 * rgb[..., 2]) < 90)
    line = {"n": dark[:3].any(0), "s": dark[-3:].any(0), "w": dark[:, :3].any(1), "e": dark[:, -3:].any(1)}[side]
    idx = np.nonzero(line)[0]
    return (idx.min() + idx.max() + 1) / 2 if len(idx) else None


def cut_track(sheet: Sheet, group: dict, rows: list[dict], problems: list[str]) -> None:
    """A track set that tiles (v3, design-system-v3.md §8). The tile's length is a whole number of tie spacings of the
    straight piece (`ties` of them), rounded to the grid of 8 — the one place v3 resamples, along the rails by a few %,
    so that ties keep their rhythm across every seam; a straight is one tie spacing repeated, so it joins itself exactly. Each piece is placed so that the rails cross each of its `exits`
    at the tile's middle, and a rail that stops short of an edge is carried on to it."""
    pieces_ = {item["file"]: trim(sheet.native(_extract(sheet, item))) for item in group["items"]}
    straight = next(img for f, img in pieces_.items() if f.endswith("straight-h.png"))
    a = straight[..., 3] > 0
    rails, mid = _rails(straight, 0)
    band = a[int(rails.min()) + 1:int(rails.max())] if len(rails) > 1 else a
    tie_cols = band.mean(0) > 0.5
    starts = np.nonzero(tie_cols & ~np.concatenate(([False], tie_cols[:-1])))[0]
    ends = np.nonzero(tie_cols & ~np.concatenate((tie_cols[1:], [False])))[0] + 1
    centres = (starts + ends) / 2
    period = float(np.median(np.diff(centres)))
    n = group.get("ties", 4)
    T = max(8, int(round(period * n / 8)) * 8)
    f = T / (period * n)
    if group.get("target_tile"):
        group["_show"] = max(1, int(round(group["target_tile"] / T)))
    problems.append(f"{group['_sheet']}: ties every {period:.1f} art px; a tile of {n} ties = {period * n:.1f} → "
                    f"{T} × {T} (×{f:.3f} along the rails), shown ×{group.get('_show', 1)}")
    def scaled(img):
        h, w = img.shape[:2]
        return np.asarray(Image.fromarray(img, "RGBA").resize((max(1, round(w * f)), max(1, round(h * f))),
                                                               Image.NEAREST))
    for item in group["items"]:
        img = scaled(pieces_[item["file"]])
        exits = item["exits"]
        sw, sh_ = item.get("span", [1, 1])
        W, H = T * sw, T * sh_
        if item["file"].endswith(("straight-h.png", "straight-v.png")):
            vert = item["file"].endswith("straight-v.png")
            src = img.transpose(1, 0, 2) if vert else img
            _, m = _rails(src, 0)
            aa = src[..., 3] > 0
            r0 = _rails(src, 0)[0]
            bnd = aa[int(r0.min()) + 1:int(r0.max())] if len(r0) > 1 else aa
            tc = bnd.mean(0) > 0.5
            st = np.nonzero(tc & ~np.concatenate(([False], tc[:-1])))[0]
            en = np.nonzero(tc & ~np.concatenate((tc[1:], [False])))[0] + 1
            x0 = int(round((st[0] + en[0]) / 2))              # from the first tie's middle: half a tie at each edge
            p = T // n                                       # one tie spacing, repeated: the seam is the same as inside
            seg = np.concatenate([src[:, x0:x0 + p]] * n, axis=1)
            out = np.zeros((T, T, 4), np.uint8)
            y0 = int(round(T / 2 - m))
            ys, yd = max(0, -y0), max(0, y0)
            hh = min(seg.shape[0] - ys, T - yd)
            out[yd:yd + hh, :seg.shape[1]] = seg[ys:ys + hh]
            out = out.transpose(1, 0, 2) if vert else out
        else:
            out = np.zeros((H, W, 4), np.uint8)
            ns = next((e for e in "ns" if e in exits), None)
            we = next((e for e in "we" if e in exits), None)
            c = _edge_centre(img, ns) if ns and sw == 1 else None     # across: a north or south exit at the middle
            dx = int(round(W / 2 - c)) if c is not None else (0 if "w" in exits else W - img.shape[1])
            c = _edge_centre(img, we) if we and sh_ == 1 else None     # down: a west or east exit at the middle
            dy = int(round(H / 2 - c)) if c is not None else (0 if "n" in exits else H - img.shape[0])
            ys, xs = max(0, -dy), max(0, -dx)
            yd, xd = max(0, dy), max(0, dx)
            hh, ww = min(img.shape[0] - ys, H - yd), min(img.shape[1] - xs, W - xd)
            out[yd:yd + hh, xd:xd + ww] = img[ys:ys + hh, xs:xs + ww]
            for side in exits:                               # carry a rail that stops short on to its edge
                if side == "w" and xd > 0:
                    out[:, :xd] = out[:, xd:xd + 1]
                if side == "e" and xd + ww < W:
                    out[:, xd + ww:] = out[:, xd + ww - 1:xd + ww]
                if side == "n" and yd > 0:
                    out[:yd] = out[yd:yd + 1]
                if side == "s" and yd + hh < H:
                    out[yd + hh:] = out[yd + hh - 1:yd + hh]
        out = own_palette(decast(out), group.get("colours", 24)) if group.get("keep_colours") else out
        _write(out, item["file"], group, rows, problems, (W, H), 1, f, anchor="top-left")
        if item["file"].endswith(("straight-h.png", "straight-v.png")):
            problems.append(seam(out, item["file"], T // n))


def cut_ground(sheet: Sheet, group: dict, rows: list[dict], problems: list[str]) -> None:
    """The ground (v3, g1). Its grass and earth are moved onto the tokens' (`world-grass`, `world-earth`: F1's), so an
    edge meets the plain grass, which is the token itself, without a step; outlines stay. Roles: `decal` (a tile's
    plain grass made transparent, its tufts or flowers kept), `fill` (the earth from inside the tile's drawn border,
    `inset` of it, cut to a multiple of 8 so it repeats), `rim-n|s|w|e` (the strip of an edge tile from its grass side
    to just inside the earth, the earth side flush with a path's edge, repeated along it), `tile` (whole)."""
    tok = {t["name"]: _rgb(t["value"]["camp"]) for t in json.loads(TOKENS.read_text(encoding="utf-8"))["color"]["tokens"]
           if t["name"] in ("world-grass", "world-earth")}
    def inner(img, f=0.25):
        h, w = img.shape[:2]
        return img[int(h * f):int(h * (1 - f)), int(w * f):int(w * (1 - f))]
    def med(img):
        px = img[img[..., 3] > 0][:, :3].astype(float)
        return np.median(px, axis=0)
    # each cell less its outermost pixel, where the magenta between the cells bled in
    by_order = {item["order"]: trim(sheet.native(_extract(sheet, item)))[1:-1, 1:-1] for item in group["items"]}
    g_med = med(inner(trim(sheet.native(sheet.nth(group["grass_ref"])))))
    e_med = med(inner(trim(sheet.native(sheet.nth(group["earth_ref"])))))
    def is_grass(rgb):
        return (rgb[..., 1] > rgb[..., 0] + 8) & (rgb[..., 1] > rgb[..., 2] + 8)
    def onto_tokens(img):
        out = img.copy()
        rgb = img[..., :3].astype(float)
        lum = 0.3 * rgb[..., 0] + 0.59 * rgb[..., 1] + 0.11 * rgb[..., 2]
        g = is_grass(rgb) & (img[..., 3] > 0)
        e = ~g & (img[..., 3] > 0) & (lum > 45)
        rgb[g] += np.array(tok["world-grass"]) - g_med
        rgb[e] += np.array(tok["world-earth"]) - e_med
        out[..., :3] = rgb.clip(0, 255).astype(np.uint8)
        return out
    problems.append(f"{group['_sheet']}: the sheet's grass {'#%02x%02x%02x' % tuple(int(v) for v in g_med)} → "
                    f"world-grass, its earth {'#%02x%02x%02x' % tuple(int(v) for v in e_med)} → world-earth")
    for item in group["items"]:
        img, role = by_order[item["order"]], item["role"]
        if role == "decal":
            rgb = img[..., :3].astype(float)
            plain = np.sqrt(((rgb - g_med) ** 2).sum(-1)) < group.get("plain", 22)
            img = img.copy()
            img[plain] = 0
            img = onto_tokens(img)
        elif role == "fill":
            h, w = img.shape[:2]
            f = item.get("inset", 0.12)
            img = img[int(h * f):, int(w * f):]
            n = min(img.shape[0], img.shape[1], int(min(h, w) * (1 - 2 * f))) // 8 * 8
            img = onto_tokens(img[:n, :n])
        elif role.startswith("rim-"):
            side = role[-1]
            a = img if side in "ns" else img.transpose(1, 0, 2)
            a = a if side in "nw" else a[::-1]                     # grass side first
            earth = ~is_grass(a[..., :3].astype(int)) & (a[..., 3] > 0)
            frac = earth.mean(axis=1)
            r = int(np.argmax(frac >= 0.9)) if (frac >= 0.9).any() else a.shape[0] // 2
            a = a[:r + 2]
            L = a.shape[1] // 8 * 8                                  # a whole number of 8 along the edge, centred
            x0 = (a.shape[1] - L) // 2
            a = a[:, x0:x0 + L]
            a = a if side in "nw" else a[::-1]
            img = onto_tokens(a if side in "ns" else a.transpose(1, 0, 2))
        else:
            img = onto_tokens(img)
        img = own_palette(img, group.get("colours", 24))
        _write(img, item["file"], group, rows, problems, img.shape[1::-1], 1, 1, anchor="top-left")


def cut_group(sheet: Sheet, group: dict, rows: list[dict], problems: list[str]) -> None:
    kind = group.get("kind", "sprite")
    if kind == "ground":
        return cut_ground(sheet, group, rows, problems)
    if kind == "track":
        return cut_track(sheet, group, rows, problems)
    pal = palette(group.get("tones", []), group.get("signals", False))
    if kind == "nine":
        return cut_nine(sheet, group, pal, rows, problems)
    if kind == "tiles":
        w, h = group["size"]
        if group.get("native"):                 # v3: one size for the set, the drawn tile at the sheet's own pitch
            boxes = [sheet.tile_box(_extract(sheet, item)) for item in group["items"]]
            drawn = float(np.median([max(b[2] - b[0], b[3] - b[1]) for b in boxes])) / sheet.pitch
            w = h = max(8, int(round(drawn / 8)) * 8)
            problems.append(f"{group['_sheet']}: tiles drawn about {drawn:.0f} art px, cut at {w} × {h}")
        for item in group["items"]:
            img = sheet.tile(_extract(sheet, item), w, h)
            img[..., 3] = 255
            if group.get("key_grass"):                           # the tile's grass: the ground layer draws its own
                img = grass_keyed(img)
            if group.get("keep_colours"):
                img[..., 3] = np.where(img[..., 3] > 0, 255, 0)
                img = own_palette(img, group.get("colours", 24))
            else:
                img = recolour(img, pal)
            _write(img, item["file"], group, rows, problems, (w, h), 1)
            if item["file"].rsplit("/", 1)[-1] in ("straight-h.png", "straight-v.png"):
                problems.append(seam(img, item["file"]))
        return
    w, h = group["size"]
    boxes = [[_extract(sheet, f) for f in item.get("frames", [item])] for item in group["items"]]
    scale = 1 if group.get("native") else group.get("scale")
    if scale is None:                                            # one scale for the group: the largest piece fits
        # a group's `fit` (v2), else each piece's own slot (v3's buildings differ in size)
        fits = [group.get("fit") or item.get("size", [w, h]) for item in group["items"]]
        scale = max([1.0] + [max((b[2] - b[0]) / fit[0], (b[3] - b[1]) / fit[1])
                             for fit, bs in zip(fits, boxes) for b in bs])
    anchor = group.get("anchor", "feet")
    for item, bs in zip(group["items"], boxes):
        frames = []
        if group.get("native"):                 # v3: the slot is what the sheet draws, on the grid of 8, never resampled
            imgs = [trim(sheet.native(b)) for b in bs]
            r8 = (lambda n: n) if group.get("exact") else up8          # `exact`: nine-slice pieces keep their size
            item = {**item, "size": (r8(max(i.shape[1] for i in imgs)), r8(max(i.shape[0] for i in imgs)))}
        read = lambda box: trim(sheet.native(box) if scale == 1 else sheet.coarse(box, scale))  # noqa: E731
        for b in bs:
            img = read(b)
            if "load_of" in item:
                img = load_only(img, read(_trimmed_box(sheet, sheet.at(*item["load_of"]))), item.get("rim", 6))
            if item.get("largest", group.get("largest")):
                img = largest(img)
            if "cut" in item:
                img = _cut(img, item["cut"])
            iw, ih = item.get("size", (w, h))
            if img.shape[1] > iw or img.shape[0] > ih:
                problems.append(f"{item['file']}: {img.shape[1]} × {img.shape[0]} cropped to its slot {iw} × {ih}")
            cx = feet_x(img)
            if group.get("native") and len(bs) == 1 and abs(iw / 2 - cx) > (iw - img.shape[1]) / 2 + 0.5:
                cx = None                       # centred on its feet it would lose a side (a forge's anvil at its foot)
            frame = pad(img, iw, ih, item.get("anchor", anchor), cx)
            for fx0, fy0, fx1, fy1 in item.get("clear", []):        # a smudge of the sheet touching the sprite
                frame[int(fy0 * ih):int(fy1 * ih), int(fx0 * iw):int(fx1 * iw)] = 0
            frames.append(frame)
        out = strip(frames) if len(frames) > 1 else frames[0]
        if group.get("keep_colours"):           # v3: re-pixelised in its own colours, the magenta cast removed
            out = decast(out)
            if not group.get("signals"):        # checked before the palette, which could average a banner's orange away
                opaque = out[out[..., 3] > 0][:, :3]
                n = sum(signal_hue(tuple(int(v) for v in p)) for p in opaque)
                if n >= 8:
                    problems.append(f"{item['file']}: {n} px in a signal's yellow, orange or red "
                                    f"({100 * n / max(len(opaque), 1):.1f} %) — redraw it without them")
            out = own_palette(out, group.get("colours", 24))
        else:
            out = recolour(out, pal)
        _write(out, item["file"], group, rows, problems, frames[0].shape[1::-1], len(frames), scale,
               anchor=item.get("anchor"))


def cut_nine(sheet: Sheet, group: dict, pal, rows: list[dict], problems: list[str]) -> None:
    """A 3 × 3 kit on the sheet into v2's nine-slice set (§4b): each piece cut from its outer side at the sheet's
    own scale, so a corner keeps its border on its two outer sides only and an edge on its one; the edges as 8 px
    repeat units in up to three variants from along the piece; the centre a 32 × 32 field."""
    names = ("nw", "n", "ne", "w", "c", "e", "sw", "s", "se")
    d, back, ln, nv = group.get("depth", 24), group.get("back", 32), 8, group.get("variants", 3)
    prefix = group["prefix"]
    imgs = {}
    for name, item in zip(names, group["items"]):
        imgs[name] = trim(sheet.native(_extract(sheet, item)))
    def corner(img, w, h, right, bottom):
        H, W = img.shape[:2]
        x = W - w if right else 0
        y = H - h if bottom else 0
        return pad(img[max(y, 0):max(y, 0) + h, max(x, 0):max(x, 0) + w], w, h, "top-left")
    out = {
        "nw": corner(imgs["nw"], d, back, False, False), "ne": corner(imgs["ne"], d, back, True, False),
        "sw": corner(imgs["sw"], d, d, False, True), "se": corner(imgs["se"], d, d, True, True),
    }
    for name, (horizontal, deep, far) in {"n": (True, back, False), "s": (True, d, True),
                                          "w": (False, d, False), "e": (False, d, True)}.items():
        img = imgs[name]
        H, W = img.shape[:2]
        length = W if horizontal else H
        starts = [int(length * f) - ln // 2 for f in (0.5, 0.35, 0.65)[:nv]]
        for i, s in enumerate(starts):
            if horizontal:
                piece = img[(H - deep if far else 0):(H if far else deep), s:s + ln]
                piece = pad(piece, ln, deep, "top-left")
            else:
                piece = img[s:s + ln, (W - deep if far else 0):(W if far else deep)]
                piece = pad(piece, deep, ln, "top-left")
            out[name if i == 0 else f"{name}-{i}"] = piece
    c = imgs["c"]
    H, W = c.shape[:2]
    out["c"] = pad(c[(H - 32) // 2:(H - 32) // 2 + 32, (W - 32) // 2:(W - 32) // 2 + 32], 32, 32, "top-left")
    for name, img in out.items():
        _write(recolour(img, pal), f"{prefix}/{name}.png", group, rows, problems, img.shape[1::-1], 1, 1,
               anchor="top-left")


def _write(img, rel, group, rows, problems, frame, frames, scale=1.0, anchor=None) -> None:
    h, w = img.shape[:2]
    if w % 8 or h % 8:
        problems.append(f"{rel}: {w} × {h} is off the grid of 8")
    if not group.get("signals") and not group.get("keep_colours"):   # v3 is checked in cut_group, before its palette
        opaque = img[img[..., 3] > 0][:, :3]
        if any(loud(p) for p in {tuple(int(v) for v in p) for p in opaque}):
            problems.append(f"{rel}: a signal's yellow or red outside a signal sprite")
    save(img, rel)
    row = {"file": rel, "size": [w, h], "frame": list(frame), "frames": frames,
           **({"pitch": group["_pitch"], "show": group["_show"]} if "_show" in group else {}),
           "anchor": anchor or group.get("anchor", "feet"), "placeholder": True,
           "source": group["_sheet"], "scale": round(float(scale), 3), "licence": LICENCE, "author": AUTHOR}
    if frames > 1:
        row["fps"] = group.get("fps", 8)
    if group.get("tones"):
        row["tones"] = group["tones"]
    if group.get("slots"):
        row["slots"] = group["slots"]
    if group.get("map"):
        m = half(img)
        mrel = "map/" + rel
        save(m, mrel)
        row["map"] = mrel
    rows.append(row)


# --- 8. check ------------------------------------------------------------------------------------------------

def render_kits(rows: list[dict], into: pathlib.Path) -> None:
    """Each nine-slice kit tiled as a 3 × 3 and a 5 × 4 of its centre, at 4× so a seam shows."""
    into.mkdir(parents=True, exist_ok=True)
    kits = sorted({r["file"].rsplit("/", 1)[0] for r in rows if r["file"].endswith("/nw.png")})
    for kit in kits:
        p = lambda n: np.asarray(Image.open(OUT / kit / f"{n}.png"))  # noqa: E731
        for cols, rws in ((3, 3), (5, 4)):
            iw, ih = cols * 32, rws * 32
            nw, ne, sw, se = p("nw"), p("ne"), p("sw"), p("se")
            dl, back = nw.shape[1], nw.shape[0]
            dd = sw.shape[0]
            W, H = iw + 2 * dl, ih + back + dd
            canvas = np.zeros((H, W, 4), np.uint8)
            def put(img, x, y):
                h, w = img.shape[:2]
                sub = canvas[y:y + h, x:x + w]
                m = img[..., 3:4] > 0
                canvas[y:y + h, x:x + w] = np.where(m, img, sub)
            for y in range(back, back + ih, 32):
                for x in range(dl, dl + iw, 32):
                    put(p("c"), x, y)
            variants = lambda e: [v for v in (e, f"{e}-1", f"{e}-2") if (OUT / kit / f"{v}.png").exists()]  # noqa
            for i, x in enumerate(range(dl, dl + iw, 8)):
                put(p(variants("n")[i % len(variants("n"))]), x, 0)
                put(p(variants("s")[i % len(variants("s"))]), x, back + ih)
            for i, y in enumerate(range(back, back + ih, 8)):
                put(p(variants("w")[i % len(variants("w"))]), 0, y)
                put(p(variants("e")[i % len(variants("e"))]), dl + iw, y)
            put(nw, 0, 0)
            put(ne, dl + iw, 0)
            put(sw, 0, back + ih)
            put(se, dl + iw, back + ih)
            Image.fromarray(canvas, "RGBA").resize((W * 4, H * 4), Image.NEAREST).save(
                into / f"{kit.replace('/', '_')}-{cols}x{rws}.png")


V3 = ROOT / "tools" / "camp_sheets_v3.json"


def shown(sheet: Sheet, target: dict | None) -> int:
    """The whole multiple (×1, ×2, …) that brings a sheet's pieces nearest their target size on screen (v3: each sheet
    comes at its own pixel size; a cart drawn 38 px wide is shown at ×2 to be about 64). `target`: {"w": px} or
    {"h": px}, compared with the median piece; none, ×1. A track sheet sets its own from its tile (`cut_track`)."""
    if not target or not sheet.boxes:
        return 1
    side = 0 if "w" in target else 1
    size = float(np.median([b[2 + side] - b[side] for b in sheet.boxes]))
    return max(1, int(round(target.get("w", target.get("h")) / size)))


def expect(spec: dict) -> None:
    """Every sheet of a spec, whether it is in the folder, and the sprites with their sizes it is cut into."""
    for sh in spec["sheets"]:
        p = ROOT / sh.get("root", spec["root"]) / sh["file"]
        there = any(q.exists() for q in (p, p.with_suffix(".jpg"), p.with_suffix(".jpeg")))
        print(f"{'✓' if there else '·'} {sh['file']}  ({sh['name']}{': ' + sh['about'] if sh.get('about') else ''})")
        for group in sh.get("groups", []):
            for item in group["items"]:
                w, h = item.get("size", group["size"])
                n = len(item.get("frames", [item]))
                print(f"      {item['file']}  {w} × {h}" + (f" × {n} frames" if n > 1 else ""))
        if sh.get("later"):
            print(f"      cut later: {sh['later']}")


def main() -> None:
    global OUT
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--spec", type=pathlib.Path, default=SPEC)
    ap.add_argument("--v3", action="store_true", help="the v3 sheets (tools/camp_sheets_v3.json)")
    ap.add_argument("--expect", action="store_true", help="list the spec's sheets and sprites, cut nothing")
    ap.add_argument("--only", default="")
    ap.add_argument("--list", type=pathlib.Path)
    ap.add_argument("--check", type=pathlib.Path)
    ap.add_argument("--degrid", action="store_true", help="with --list: drop a grid the model drew round the cells")
    args = ap.parse_args()
    if args.list:
        s = Sheet(args.list, grid_lines=args.degrid)
        print(f"pitch {s.pitch:.2f} px, phase {s.ox:.1f}, {s.oy:.1f}; grid {s.w} × {s.h}")
        for i, b in enumerate(s.ordered()):
            print(f"  order {i:2d}  at [{(b[0] + b[2]) / 2 / s.w:.3f}, {(b[1] + b[3]) / 2 / s.h:.3f}]  "
                  f"{b[2] - b[0]} × {b[3] - b[1]}")
        return
    spec_path = V3 if args.v3 else args.spec
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    if args.expect:
        return expect(spec)
    if spec.get("out"):
        OUT = ROOT / spec["out"]
    manifest = OUT / "manifest.json"
    old = json.loads(manifest.read_text(encoding="utf-8"))["sprites"] if manifest.exists() else []
    rows: list[dict] = []
    problems: list[str] = []
    done = set()
    for sh in spec["sheets"]:
        if args.only not in sh["name"] or not sh.get("groups"):
            continue
        path = ROOT / sh.get("root", spec["root"]) / sh["file"]
        for other in (path.with_suffix(".jpg"), path.with_suffix(".jpeg")):     # an image model that only gives JPEG
            if not path.exists() and other.exists():
                path = other
        if not path.exists():
            print(f"{sh['name']}: awaited ({path.relative_to(ROOT)})")
            continue
        done.add(sh["file"])
        sheet = Sheet(path, sh.get("fringe", 60), sh.get("close", 1), sh.get("degrid", spec.get("degrid", False)))
        print(f"{sh['name']}: pitch {sheet.pitch:.2f} px, {len(sheet.boxes)} pieces")
        for group in sh["groups"]:
            group["_sheet"] = sh["file"]
            group["_pitch"] = round(float(sheet.pitch), 2)
            group["_show"] = group.get("show", sh.get("show") or shown(sheet, sh.get("target")))
            for key in ("native", "keep_colours"):              # v3: set once for the whole spec
                group.setdefault(key, spec.get(key, False))
            cut_group(sheet, group, rows, problems)
    # a one-building sheet (`over`, listed after the sheet it overrides) replaces that sheet's sprite of the same name
    rows = list({r["file"]: r for r in rows}.values())
    cut = {r["file"] for r in rows}
    rows += [r for r in old if r["source"] not in done and r["file"] not in cut]
    rows.sort(key=lambda r: r["file"])
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps({"note": spec.get("manifest_note") or (
                                        "Placeholders cut from generated reference sheets by tools/camp_sheet.py; "
                                        "every row is replaced by the commissioned artist's sprite "
                                        "(docs/design/design-system-v2.md §11)."),
                                    "sprites": rows}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(rows)} sprites in {manifest}")
    if spec_path == V3:
        import campkit_v3                   # the preview learns what was cut and at what multiple
        print(f"preview: {campkit_v3.build().relative_to(ROOT)}")
    if "faces" in spec:
        import camp_faces                   # the interface's faces, recut from the role bodies (tools/camp_faces.py)
        camp_faces.write_manifest(camp_faces.cut(spec))
    if args.check:
        render_kits(rows, args.check)
    for p in problems:
        print("  check:", p)


if __name__ == "__main__":
    main()
