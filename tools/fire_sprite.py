"""The fire over a building whose ork waits for you (design-system README: States and motion — from 60 s
flames appear over its header, more until it is covered at 5 min, flickering every frame), drawn from
code so it never drifts:

    python tools/fire_sprite.py

`design-system/sprites/fx/fire.png` (and `@2x`): a 64×16 strip of four 16×16 frames, played in order by
`.ok-flame.is-sprite` (components.css). The colours are the fire set of the tokens: `fire-ember` at the
edge, `alert` in the body, `fire-glow` in the heart, `alert-hot` at the foot.

Needs Pillow.
"""
from __future__ import annotations

import pathlib

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "design-system" / "sprites" / "fx"

EMBER, HOT, BODY, GLOW = (0xB3, 0x1B, 0x0F), (0xE8, 0x41, 0x1C), (0xFF, 0x8C, 0x1A), (0xFF, 0xC0, 0x4D)

# Four frames, 16 × 16, bottom up: `.` none, `e` ember (the edge), `h` hot (the foot), `b` body, `g` glow.
# The tongue leans left, stands, leans right, stands taller: a flicker, never a jump of the base.
FRAMES = [
    """\
................
................
................
.....e..........
.....ee.........
....ebe.........
....ebbe....e...
...ebbbe...ee...
...ebgbbe.ebe...
..ebbggbbebbe...
..ebggggbbbbe...
.ebbgggggbgbe...
.ebgggggggggbe..
.ehbggggggggbe..
..ehhbggggbbhe..
...eehhhhhhee...""",
    """\
................
................
.......e........
.......ee.......
......ebe.......
......ebbe......
.....ebbbe..e...
.....ebgbbe.ee..
..e..ebggbe.ebe.
..ee.ebggbbebbe.
..ebeebgggbbbbe.
..ebbbggggbgbe..
..ebgggggggggbe.
..ehbgggggggbe..
...ehhbggggbhe..
....eehhhhhee...""",
    """\
................
................
................
..........e.....
.........ee.....
.........ebe....
...e....ebbe....
...ee..ebbbe....
...ebe.ebgbbe...
...ebbebbggbbe..
...ebbbbggggbe..
...ebgbgggggbbe.
..ebgggggggggbe.
..ebggggggggbhe.
..ehbbggggbhhe..
...eehhhhhhee...""",
    """\
................
........e.......
........ee......
.......ebe......
.......ebbe.....
......ebbbe.....
......ebgbbe....
..e..ebggbbe.e..
..ee.ebgggbeee..
..ebeebgggbbbe..
..ebbbggggbgbe..
..ebggggggggbe..
.ebgggggggggbe..
.ehbggggggggbhe.
..ehhbggggbbhe..
...eehhhhhhee...""",
]

COLOUR = {"e": EMBER, "h": HOT, "b": BODY, "g": GLOW}


def strip(scale: int) -> Image.Image:
    img = Image.new("RGBA", (64 * scale, 16 * scale), (0, 0, 0, 0))
    for f, frame in enumerate(FRAMES):
        rows = frame.splitlines()
        assert len(rows) == 16 and all(len(r) == 16 for r in rows), f"frame {f} is not 16 × 16"
        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                if ch in COLOUR:
                    for dy in range(scale):
                        for dx in range(scale):
                            img.putpixel(((f * 16 + x) * scale + dx, y * scale + dy), (*COLOUR[ch], 255))
    return img


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    strip(1).save(OUT / "fire.png")
    strip(2).save(OUT / "fire@2x.png")
    print(f"wrote {OUT / 'fire.png'} and @2x")


if __name__ == "__main__":
    main()
