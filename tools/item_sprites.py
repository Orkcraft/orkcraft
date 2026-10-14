"""Stand-ins for the items the person earns (docs/design/v3-prompts.md §14, realm/items.py) until GEN draws them: an
existing v3 sprite set on a stone plinth, in the camp's calm stone greys (never yellow or red: signals win).
Writes `design-system/items/<id>.png`; each item's JSON beside it names its sprite.

    python tools/item_sprites.py
"""
from __future__ import annotations

import pathlib

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
V3 = ROOT / "design-system" / "sprites" / "v3"
OUT = ROOT / "design-system" / "items"

# stone: lit top, face, shade, the dark edge (the palisade's and the gate's greys, design-system-v3.md §2)
TOP, FACE, SHADE, EDGE = (176, 172, 160, 255), (138, 134, 124, 255), (104, 100, 92, 255), (52, 48, 44, 255)
ON_PLINTH = {"first-cart": "carts/empty.png", "lean-week": "decor/logpile.png"}


def plinth(w: int, h: int = 12) -> Image.Image:
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    px = img.load()
    for x in range(w):
        for y in range(h):
            edge = x in (0, w - 1) or y == h - 1
            px[x, y] = EDGE if edge else TOP if y <= 2 else SHADE if x >= w - 4 or y >= h - 3 else FACE
    for x in range(6, w - 4, 12):                   # the joints between the blocks
        for y in range(4, h - 2):
            px[x, y] = SHADE
    return img


def on_plinth(sprite: Image.Image) -> Image.Image:
    sprite = sprite.convert("RGBA")
    box = sprite.getbbox() or (0, 0, *sprite.size)
    sprite = sprite.crop(box)
    base = plinth(sprite.width + 8)
    out = Image.new("RGBA", (base.width, sprite.height + base.height - 2), (0, 0, 0, 0))
    out.paste(base, (0, out.height - base.height))
    out.alpha_composite(sprite, (4, 0))
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for item, src in ON_PLINTH.items():
        on_plinth(Image.open(V3 / src)).save(OUT / f"{item}.png")


if __name__ == "__main__":
    main()
