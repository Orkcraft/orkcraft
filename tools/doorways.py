"""Each building sprite's doorway, measured once (the PM, 15 October: an ork steps out of the real door, no drawn leaf).

    python tools/doorways.py [--sheet OUT.png]

For every `buildings/*.png` in design-system/sprites/v3/ it finds the dark opening at the sprite's lower middle — the
largest connected patch of near-black, opaque pixels whose box lies in the lower 60 % and the middle 70 % of the
sprite, at least 8 × 10 art px — and writes its box as `doorway: [x, y, w, h]` (art px from the sprite's top left)
into that row of the manifest; a sprite with no such patch gets no doorway, and a row's old doorway goes. The depot's
doorway is its west gateway (the dark patch furthest west), not a bay. `--sheet` draws every sprite with its box for a
check by eye; `BY_EYE` holds the boxes set by hand after that check. Needs `pip install pillow`.
"""
from __future__ import annotations

import argparse
import json
from collections import deque
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
V3 = ROOT / "design-system" / "sprites" / "v3"
DARK = 70                       # a pixel's summed RGB / 3 at or under this is the darkness of an opening
MIN_W, MIN_H = 8, 8
# Checked by eye on the sheet (15 October): where the measure misses a doorway that is there, or finds one that is not.
BY_EYE = {
    "buildings/council.png": [40, 52, 48, 26],         # the Review board's hall: the open front under the awning
    "buildings/custom.png": [22, 68, 20, 34],          # a house with a teal door (not dark: the measure misses it)
    "buildings/loot_vault.png": [44, 62, 60, 42],      # the Review gate: its portcullis arch, barrier down …
    "buildings/loot_vault-up.png": [44, 62, 60, 42],   # … and up
    "buildings/scrolls.png": None,                     # the Wiki: open shelves, no door
}


def patches(im: Image.Image) -> list[tuple[int, int, int, int, int]]:
    """The dark opaque patches, as (x, y, w, h, pixels)."""
    w, h = im.size
    px = im.load()
    raw = [[px[x, y][3] > 200 and sum(px[x, y][:3]) / 3 <= DARK for x in range(w)] for y in range(h)]
    # eroded: a pixel whose 5 × 5 square is all dark, so the 1–2 px outlines round every shape fall away and only an
    # opening's inside is left (its box grown back by the 2 px after)
    dark = [[all(0 <= x + i < w and 0 <= y + j < h and raw[y + j][x + i] for i in range(-2, 3) for j in range(-2, 3))
             for x in range(w)] for y in range(h)]
    seen = [[False] * w for _ in range(h)]
    out = []
    for y0 in range(h):
        for x0 in range(w):
            if not dark[y0][x0] or seen[y0][x0]:
                continue
            q, xs, ys, n = deque([(x0, y0)]), [], [], 0
            seen[y0][x0] = True
            while q:
                x, y = q.popleft()
                xs.append(x), ys.append(y)
                n += 1
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    a, b = x + dx, y + dy
                    if 0 <= a < w and 0 <= b < h and dark[b][a] and not seen[b][a]:
                        seen[b][a] = True
                        q.append((a, b))
            out.append((min(xs) - 2, min(ys) - 2, max(xs) - min(xs) + 5, max(ys) - min(ys) + 5, n))
    return out


def doorway(file: str, im: Image.Image) -> list[int] | None:
    w, h = im.size
    ok = [p for p in patches(im) if p[2] >= MIN_W and p[3] >= MIN_H and p[1] + p[3] >= h * 0.55
          and p[1] >= h * 0.25 and p[0] >= w * 0.02 and p[0] + p[2] <= w * 0.98]
    if not ok:
        return None
    if file.endswith("depot.png"):
        best = min(ok, key=lambda p: p[0])                                 # its west gateway
    else:
        best = min(ok, key=lambda p: (abs(p[0] + p[2] / 2 - w / 2) / w) - p[4] / (w * h))   # central and large
    return list(best[:4])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet", type=Path, default=None)
    args = ap.parse_args()
    manifest = V3 / "manifest.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    found, shots = {}, []
    for row in data["sprites"]:
        f = row["file"]
        if not f.startswith("buildings/"):
            continue
        im = Image.open(V3 / f).convert("RGBA")
        d = BY_EYE[f] if f in BY_EYE else doorway(f, im)
        row.pop("doorway", None)
        if d:
            row["doorway"] = d
        found[f] = d
        shots.append((f, im, d))
    manifest.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    for f, d in found.items():
        print(f"{f}: {d}")
    if args.sheet:
        k, pad = 3, 12
        W = sum(im.width * k + pad for _, im, _ in shots) + pad
        H = max(im.height for _, im, _ in shots) * k + 2 * pad
        sheet = Image.new("RGBA", (W, H), (120, 170, 90, 255))
        draw, x = ImageDraw.Draw(sheet), pad
        for _, im, d in shots:
            sheet.alpha_composite(im.resize((im.width * k, im.height * k), Image.NEAREST), (x, pad))
            if d:
                draw.rectangle([x + d[0] * k, pad + d[1] * k, x + (d[0] + d[2]) * k - 1, pad + (d[1] + d[3]) * k - 1],
                               outline=(255, 0, 255, 255), width=2)
            x += im.width * k + pad
        sheet.save(args.sheet)


if __name__ == "__main__":
    main()
