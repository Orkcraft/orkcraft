"""The portrait's heads from the person's v3 class figures (docs/design/portrait.md, v3-prompts.md §13): each
`design-system/sprites/v3/people/<role id>.png` cropped to a square round its head, at the figure's own art pixel
(never resampled), into `people/heads/<role id>.png`. The head's middle is found from the figure's top rows, so a prop
held to one side (the ASO gnome's magnifier) does not pull the crop off the face.

    python tools/people_heads.py
"""
from __future__ import annotations

import pathlib

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
PEOPLE = ROOT / "design-system" / "sprites" / "v3" / "people"
SIDE = 40            # the square's side, art px: legible in the HUD's 28-px slot and the corner's 40
TOP_ROWS = 22        # the rows read for the head's middle, below the figure's top
# The gnomes' tall caps and held props put the face far from the figure's top: their square set by hand (left, top).
AT = {"aso_manager": (2, 18), "marketing": (12, 18)}
CUT = {"data_analyst"}   # its head is cut from its own sheet (camp_sheets_v3.json k4-goblin), never cropped here


def crop(img: Image.Image, at: tuple[int, int] | None = None) -> Image.Image:
    img = img.convert("RGBA")
    if at:
        return img.crop((at[0], at[1], at[0] + SIDE, at[1] + SIDE))
    a = img.getchannel("A")
    w, h = img.size
    rows = [y for y in range(h) if any(a.getpixel((x, y)) > 0 for x in range(w))]
    top = rows[0] if rows else 0
    xs = [x for y in range(top + 6, min(h, top + TOP_ROWS)) for x in range(w) if a.getpixel((x, y)) > 0]
    cx = round(sum(xs) / len(xs)) if xs else w // 2
    left = min(max(cx - SIDE // 2, 0), max(w - SIDE, 0))
    out = Image.new("RGBA", (SIDE, SIDE), (0, 0, 0, 0))
    out.paste(img.crop((left, max(top - 2, 0), left + SIDE, max(top - 2, 0) + SIDE)), (0, 0))
    return out


def main() -> None:
    (PEOPLE / "heads").mkdir(exist_ok=True)
    for f in sorted(PEOPLE.glob("*.png")):
        if f.stem in CUT:
            continue
        crop(Image.open(f), AT.get(f.stem)).save(PEOPLE / "heads" / f.name)


if __name__ == "__main__":
    main()
