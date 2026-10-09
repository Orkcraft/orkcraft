"""A steward's headgear by the work of its building: one ork head, a role's hat over it (docs/design/select-a-building.md
§2), as the Warchief wears his crown (tools/logo.py).

    python tools/hat_sprites.py [--preview FILE]

Out come, in `design-system/sprites/orks/` (the GUI serves it at `/ds/sprites/orks/`), at 2× and 4× (`@2x`):

- `hat-<role>.png` (12×2, 24×4 drawn): the hat alone, worn by the ork that comes out of its building (js/visit.js);
- `steward-<role>.png` (12×10, 24×20 drawn): the head under its hat, the steward's face on the Warchief's line when
  its building is selected (js/warchief.js).

Which type wears which hat is `js/icons.js` `HATS`. Needs `pip install pillow fonttools brotli` (tools/logo.py).
"""
from __future__ import annotations

import argparse
import pathlib

from PIL import Image

from logo import GRID, SPRITE_COLOURS, grid_image

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "design-system" / "sprites" / "orks"

COLOURS = {**SPRITE_COLOURS, "B": "#3a4a8c", "W": "#efe6cc", "H": "#e8e0c8", "M": "#9aa0a6", "L": "#8b5a2b",
           "Q": "#7fd4e8", "C": "#3f7fbf", "R": "#c8402a", "Y": "#f2c66d"}

# two rows over the head's 12×8 grid; the head's crown is its columns 3–8
HATS = {
    "scribe": ["....BBBB.W..",      # a beret and a quill: the Wiki, the Mill, the Gramophone, the Lake
               "...BBBBBBW.."],
    "lookout": ["..H......H..",     # a horned helm: External listeners, the Horn, the Crag
                "..MMMMMMMM.."],
    "smith": ["...LLLLLL...",       # a leather cap and its goggles: the Forge, the Workshop, the Catapult
              "..LQQLLQQL.."],
    "clerk": ["....CCCC....",       # a cap with a visor: the Task board, the Calendar, the Vault, a Signpost
              "...CCCCCCCC."],
    "captain": [".....RR.....",     # a plumed helm: the Agent pool, the Review board
                "...MMMMMM..."],
    "miner": [".....W......",       # a lamp on a hard hat: the Mine
              "..YYYYYYYY.."],
}


def build(out: pathlib.Path = OUT) -> dict[str, list[str]]:
    out.mkdir(parents=True, exist_ok=True)
    faces = {}
    for role, hat in HATS.items():
        face = hat + GRID
        faces[role] = face
        for name, grid in ((f"hat-{role}", hat), (f"steward-{role}", face)):
            grid_image(grid, COLOURS, 2).save(out / f"{name}.png")
            grid_image(grid, COLOURS, 4).save(out / f"{name}@2x.png")
    return faces


def preview(faces: dict[str, list[str]], path: pathlib.Path) -> None:
    k, gap = 8, 16
    imgs = [grid_image(g, COLOURS, k) for g in faces.values()]
    sheet = Image.new("RGBA", (sum(i.width for i in imgs) + gap * (len(imgs) + 1), imgs[0].height + 2 * gap), "#1a1813")
    x = gap
    for i in imgs:
        sheet.alpha_composite(i, (x, gap))
        x += i.width + gap
    sheet.save(path)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--preview", type=pathlib.Path)
    a = ap.parse_args()
    faces = build()
    if a.preview:
        preview(faces, a.preview)
