"""The orks' high-density cut (tools/camp_sheet.py, a sheet's `"hd": [1, 1.5, 2]`): each ork straight from the
generated sheet, downscaled once to the device pixels it is drawn at, never re-pixelated.

A generated sheet's "pixel art" sits on an uneven grid, so reading it into art pixels (`pick: mode`, a palette) makes
noise; the ork is only some 45 of its own pixels tall, so nothing is lost by not doing it. For each frame:

1. **key with despill:** the sheet's background (the magenta and a drawn grid, `Sheet.bg`) is transparent; a pixel near
   it is unmixed from the key — its share of magenta (how far red and blue both stand over green) becomes
   transparency and is taken out of its colour, so no pink fringe is left on the outline;
2. only the piece's own shape (its cells on the sheet's grid, one cell round them) is kept, so a neighbour or a frame
   beside it never bleeds in;
3. **one LANCZOS downscale** of the slot today's sprite was cut into, on premultiplied linear light (no dark halo),
   to `w × h × show × 2k` for each step `k`: a dpr-2 screen draws the ork at `k` CSS px per art px (js/camp/layout.js
   HI's `o`: 1, 1.5, 2), so the file is one image pixel per device pixel. Feet stay on the slot's bottom row.

Written next to today's file as `<name>@hd1.png`, `@hd1_5.png`, `@hd2.png`; today's stays the dpr-1 sprite.
"""
from __future__ import annotations

import numpy as np
from PIL import Image

EDGE = 3            # source px from the background within which a pixel is unmixed from the key
SPILL0 = 16.0       # magenta strength under this is the sheet's noise, not the key


def suffix(k: float) -> str:
    return "@hd" + f"{k:g}".replace(".", "_")


def hd_name(rel: str, k: float) -> str:
    stem, ext = rel.rsplit(".", 1)
    return f"{stem}{suffix(k)}.{ext}"


def _near(bg: np.ndarray, n: int) -> np.ndarray:
    """True within n px (8-neighbour steps) of the background."""
    out = bg.copy()
    for _ in range(n):
        g = out.copy()
        g[1:] |= out[:-1]
        g[:-1] |= out[1:]
        g[:, 1:] |= g[:, :-1].copy()
        g[:, :-1] |= g[:, 1:].copy()
        out = g
    return out


def unkey(rgb: np.ndarray, bg: np.ndarray) -> np.ndarray:
    """RGBA floats 0..1 (straight alpha): the background transparent, the key unmixed from the pixels at its edge."""
    p = rgb.astype(np.float64)
    spill = np.minimum(p[..., 0], p[..., 2]) - p[..., 1]                  # magenta's strength: red and blue over green
    t = np.clip((spill - SPILL0) / (255.0 - SPILL0), 0.0, 1.0)             # the key's share of the pixel
    t = np.where(_near(bg, EDGE) & ~bg, t, 0.0)                            # only at the edge: a purple robe stays
    t = np.where(bg, 1.0, t)
    a = 1.0 - t
    key = np.array([255.0, 0.0, 255.0])
    with np.errstate(invalid="ignore", divide="ignore"):
        f = (p - t[..., None] * key) / a[..., None]
    f = np.where(a[..., None] > 1e-3, np.clip(f, 0, 255), 0.0)
    return np.dstack([f / 255.0, a])


def _lin(c: np.ndarray) -> np.ndarray:
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _srgb(c: np.ndarray) -> np.ndarray:
    c = np.clip(c, 0.0, 1.0)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def downscale(rgba: np.ndarray, box: tuple[float, float, float, float], size: tuple[int, int]) -> np.ndarray:
    """`box` (source px, may reach past the image: transparent there) to `size`, LANCZOS on premultiplied linear
    light; RGBA uint8."""
    a = rgba[..., 3]
    planes = [_lin(rgba[..., i]) * a for i in range(3)] + [a]
    out = [np.asarray(Image.fromarray(q.astype(np.float32), "F").resize(size, Image.LANCZOS, box=box)) for q in planes]
    al = np.clip(out[3], 0.0, 1.0)
    rgb = np.dstack([np.where(al > 1e-4, o / np.maximum(al, 1e-4), 0.0) for o in out[:3]])
    al = np.where(al < 1.5 / 255, 0.0, al)
    img = np.dstack([_srgb(rgb), al])
    return (img * 255 + 0.5).astype(np.uint8)


def frame(sheet, b, slot: tuple[int, int], at: tuple[int, int], c: float, out: tuple[int, int],
          bottom: bool = True) -> np.ndarray:
    """One frame: the piece at grid box `b`, placed as today's sprite places it in its `slot` (art px) at `at` (its
    top left in the slot), `c` source px per art px, downscaled to `out` device px."""
    pitch, ox, oy = sheet.pitch, sheet.ox, sheet.oy
    m = 2 * int(np.ceil(pitch)) + 2                                        # a margin of transparency round the crop
    x0, y0, x1, y1 = sheet.screen(b)
    iw, ih = slot
    sx = x0 - at[0] * c
    sy = (y1 - ih * c) if bottom else (y0 - at[1] * c)
    X0, Y0 = int(np.floor(min(sx, x0))) - m, int(np.floor(min(sy, y0))) - m
    X1, Y1 = int(np.ceil(max(sx + iw * c, x1))) + m, int(np.ceil(max(sy + ih * c, y1))) + m
    H, W = sheet.bg.shape
    rgba = np.zeros((Y1 - Y0, X1 - X0, 4))
    cy0, cx0, cy1, cx1 = max(Y0, 0), max(X0, 0), min(Y1, H), min(X1, W)
    rgba[cy0 - Y0:cy1 - Y0, cx0 - X0:cx1 - X0] = unkey(sheet.a[cy0:cy1, cx0:cx1], sheet.bg[cy0:cy1, cx0:cx1])
    # only the piece's own cells (and one round them): no neighbour, no frame beside it
    cells = np.zeros((sheet.h + 2, sheet.w + 2), bool)
    cells[b[1] + 1:b[3] + 1, b[0] + 1:b[2] + 1] = sheet.art[b[1]:b[3], b[0]:b[2], 3] > 0
    cells = _near(cells, 1)
    ys = ((np.arange(Y0, Y1) - oy) // pitch).astype(int) + 1
    xs = ((np.arange(X0, X1) - ox) // pitch).astype(int) + 1
    ok = (ys[:, None] >= 0) & (ys[:, None] < cells.shape[0]) & (xs[None] >= 0) & (xs[None] < cells.shape[1])
    keep = ok & cells[np.clip(ys, 0, cells.shape[0] - 1)[:, None], np.clip(xs, 0, cells.shape[1] - 1)[None]]
    rgba[..., 3] *= keep
    return downscale(rgba, (sx - X0, sy - Y0, sx - X0 + iw * c, sy - Y0 + ih * c), out)
