"""Camp's interface kit, v4 (docs/design/design-system-v4.md): the chrome's pixel pieces drawn in code, never generated.

    python tools/ui_kit.py [--out DIR]

Each piece is drawn on its own art pixel grid in the tokens' colours (`design-system/tokens.json`, Camp's values), then
written twice, enlarged by whole multiples so a pixel stays a square: `<piece>.png` at 2 CSS px an art pixel, and
`<piece>@2x.png` at 4 (for a density-2 screen). Out they go to `design-system/sprites/v4/ui/` (the GUI serves them at
`/ds/sprites/v4/ui/`) with `kit.json`, which names each piece's size and its nine-slice inset in art px; CSS uses the
inset ×2 as `border-image-slice` (image px of the 1× file) and as `border-width`.

The pieces (a nine-slice unless said):

- `frame`: a panel's thick wooden frame with the teal inner border and teal caps at its corners (the target's side
  panel); `frame-thin`: the same without caps, for a window inside a window and the toasts.
- `bar`: the top bar's and the command bar's frame: walnut and wood round a parchment strip.
- `well`: a counter's chip and any parchment field, engraved into the parchment.
- `btn-wood`, `btn-teal` and their `-hover`, `-down`, `-off`: a bevelled button; teal is the primary and the active.
- `plate`: a tab header's teal plate.
- `tab`, `tab-hover`, `tab-on`: an icon tab at a panel's left side, open on its right where it meets the frame.
- `slot`, `slot-hover`, `slot-on`: an inventory slot, sunk into the parchment.
- `band`: a section's wooden strip inside a panel ("Items").
- `parchment`: a 32 × 32 tile of the panels' parchment with a few fibres (not a nine-slice: a background).

Needs `pip install pillow`.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import random

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "design-system" / "sprites" / "v4" / "ui"
TOKENS = ROOT / "design-system" / "tokens.json"


def _palette() -> dict[str, tuple[int, int, int, int]]:
    """Camp's value of every colour token, as RGBA."""
    data = json.loads(TOKENS.read_text(encoding="utf-8"))
    out = {}
    for t in data["color"]["tokens"]:
        v = t["value"]["camp"]
        if v.startswith("#") and len(v) == 7:
            out[t["name"]] = (int(v[1:3], 16), int(v[3:5], 16), int(v[5:7], 16), 255)
    return out


C = _palette()
CLEAR = (0, 0, 0, 0)


class Grid:
    """A piece on its art pixel grid."""

    def __init__(self, w: int, h: int, fill=CLEAR):
        self.w, self.h = w, h
        self.img = Image.new("RGBA", (w, h), fill)

    def px(self, x: int, y: int, c) -> None:
        if 0 <= x < self.w and 0 <= y < self.h:
            self.img.putpixel((x, y), c)

    def rect(self, x0: int, y0: int, x1: int, y1: int, c) -> None:
        """Fill the box [x0, x1] × [y0, y1], both ends included."""
        for y in range(max(0, y0), min(self.h, y1 + 1)):
            for x in range(max(0, x0), min(self.w, x1 + 1)):
                self.img.putpixel((x, y), c)

    def ring(self, i: int, top, left=None, bottom=None, right=None) -> None:
        """The ring `i` px in from the edge, each side its own colour (corners go to the top and the bottom)."""
        left, bottom, right = left or top, bottom or top, right or top
        w, h = self.w - 1 - i, self.h - 1 - i
        self.rect(i, i, i, h, left)
        self.rect(w, i, w, h, right)
        self.rect(i, i, w, i, top)
        self.rect(i, h, w, h, bottom)


def _grain(g: Grid, band: tuple[int, int], seed: int) -> None:
    """A few darker knots and streaks along a wooden band of rings (`band` = first and last ring), the same on every
    run; a streak never sits in the nine-slice's corners, so the edges tile evenly."""
    rnd = random.Random(seed)
    lo, hi = band
    for _ in range((g.w + g.h) // 3):
        ring = rnd.randint(lo, hi)
        side = rnd.choice("tblr")
        t = rnd.randint(hi + 1, (g.w if side in "tb" else g.h) - hi - 2)
        x, y = {"t": (t, ring), "b": (t, g.h - 1 - ring), "l": (ring, t), "r": (g.w - 1 - ring, t)}[side]
        g.px(x, y, C["kit-wood-dark"])


def _cap(g: Grid, x0: int, y0: int, n: int) -> None:
    """A teal corner cap, `n` px square: outline, a lit top-left, a shaded bottom-right, a rivet in the middle."""
    g.rect(x0, y0, x0 + n - 1, y0 + n - 1, C["art-outline"])
    g.rect(x0 + 1, y0 + 1, x0 + n - 2, y0 + n - 2, C["accent-teal"])
    g.rect(x0 + 1, y0 + 1, x0 + n - 2, y0 + 1, C["kit-teal-light"])
    g.rect(x0 + 1, y0 + 1, x0 + 1, y0 + n - 2, C["kit-teal-light"])
    g.rect(x0 + 1, y0 + n - 2, x0 + n - 2, y0 + n - 2, C["kit-teal-dark"])
    g.rect(x0 + n - 2, y0 + 1, x0 + n - 2, y0 + n - 2, C["kit-teal-dark"])
    m = x0 + n // 2, y0 + n // 2
    g.px(*m, C["kit-teal-dark"])
    g.px(m[0] - 1, m[1] - 1, C["kit-teal-light"])


def frame(caps: bool = True) -> tuple[Grid, int]:
    """Outline, three rings of wood (lit above, shaded below), walnut, teal, a teal shade; inside clear. 7 px in."""
    g = Grid(22, 22)
    g.ring(0, C["art-outline"])
    g.ring(1, C["kit-wood-light"], C["kit-wood-light"], C["kit-wood-dark"], C["kit-wood-dark"])
    g.ring(2, C["kit-wood"])
    g.ring(3, C["kit-wood"], C["kit-wood"], C["kit-wood-dark"], C["kit-wood-dark"])
    _grain(g, (2, 3), seed=7)
    g.ring(4, C["walnut"])
    g.ring(5, C["kit-teal-light"], C["kit-teal-light"], C["accent-teal"], C["accent-teal"])
    g.ring(6, C["kit-teal-dark"])
    if caps:
        n = 7
        for x0, y0 in ((0, 0), (g.w - n, 0), (0, g.h - n), (g.w - n, g.h - n)):
            _cap(g, x0, y0, n)
    return g, 7


def bar() -> tuple[Grid, int]:
    """The bars' frame: outline, wood lit above, wood, wood shaded below, walnut; inside clear. 5 px in."""
    g = Grid(16, 16)
    g.ring(0, C["art-outline"])
    g.ring(1, C["kit-wood-light"], C["kit-wood-light"], C["kit-wood-dark"], C["kit-wood-dark"])
    g.ring(2, C["kit-wood"])
    g.ring(3, C["kit-wood"], C["kit-wood"], C["kit-wood-dark"], C["kit-wood-dark"])
    _grain(g, (2, 3), seed=11)
    g.ring(4, C["walnut"])
    return g, 5


def well() -> tuple[Grid, int]:
    """Engraved into parchment: a rule line, a shade along its top and left; the parchment shows inside. 2 px in."""
    g = Grid(8, 8)
    g.ring(0, C["kit-parchment-rule"])
    g.ring(1, C["kit-parchment-deep"], C["kit-parchment-deep"], CLEAR, CLEAR)
    return g, 2


BUTTONS = {"wood": ("kit-wood", "kit-wood-light", "kit-wood-dark", "kit-wood-hover"),
           "teal": ("accent-teal", "kit-teal-light", "kit-teal-dark", "kit-teal-hover")}


def button(kind: str, state: str = "") -> tuple[Grid, int]:
    """Outline, a bevel lit top-left and shaded bottom-right, the face filled (`fill` in CSS). 3 px in.
    hover: a lighter face; down: the bevel turned over; off: a flat face in the parchment's shade."""
    face, light, dark, hover = (C[n] for n in BUTTONS[kind])
    if state == "hover":
        face = hover
    if state == "off":
        face, light, dark = C["kit-parchment-rule"], C["kit-parchment-deep"], C["kit-parchment-rule"]
    g = Grid(10, 10, face)
    g.ring(0, C["art-outline"])
    if state == "down":
        g.ring(1, dark, dark, face, face)
        g.ring(2, dark, dark, face, face)
    else:
        g.ring(1, light, light, dark, dark)
        g.ring(2, face, face, dark, face)
    return g, 3


def plate() -> tuple[Grid, int]:
    """A tab header's teal plate: outline, a lit top row, a shaded bottom, teal. 3 px in."""
    g = Grid(10, 10, C["accent-teal"])
    g.ring(0, C["art-outline"])
    g.ring(1, C["kit-teal-light"], C["accent-teal"], C["kit-teal-dark"], C["accent-teal"])
    g.ring(2, C["accent-teal"], C["accent-teal"], C["kit-teal-dark"], C["accent-teal"])
    return g, 3


def tab(state: str = "") -> tuple[Grid, int]:
    """An icon tab at a panel's left side: outline on three sides, open on the right where it meets the frame; wood,
    or teal when it is the open one. 4 px in."""
    face, light, dark = C["kit-wood"], C["kit-wood-light"], C["kit-wood-dark"]
    if state == "hover":
        face = C["kit-wood-hover"]
    if state == "on":
        face, light, dark = C["accent-teal"], C["kit-teal-light"], C["kit-teal-dark"]
    g = Grid(12, 12, face)
    o = C["art-outline"]
    g.rect(0, 0, g.w - 1, 0, o)
    g.rect(0, g.h - 1, g.w - 1, g.h - 1, o)
    g.rect(0, 0, 0, g.h - 1, o)
    g.rect(1, 1, g.w - 1, 1, light)
    g.rect(1, 1, 1, g.h - 2, light)
    g.rect(1, g.h - 2, g.w - 1, g.h - 2, dark)
    g.rect(2, g.h - 3, g.w - 1, g.h - 3, dark)
    return g, 4


def slot(state: str = "") -> tuple[Grid, int]:
    """An inventory slot sunk into parchment: a wood rim, shade top-left, light bottom-right, a deeper parchment
    inside. hover: the rim lit; on: a teal rim (the slot picked). 3 px in."""
    rim = {"": C["kit-wood-dark"], "hover": C["kit-wood-light"], "on": C["accent-teal"]}[state]
    g = Grid(10, 10, C["kit-parchment-deep"])
    g.ring(0, rim)
    g.ring(1, C["kit-parchment-rule"], C["kit-parchment-rule"], C["parchment"], C["parchment"])
    if state == "on":
        g.ring(1, C["kit-teal-light"], C["kit-teal-light"], C["kit-teal-light"], C["kit-teal-light"])
    return g, 3


def band() -> tuple[Grid, int]:
    """A section's wooden strip inside a panel: outline above and below, a lit top row, wood. 2 px in."""
    g = Grid(6, 6, C["kit-wood"])
    g.rect(0, 0, 5, 0, C["art-outline"])
    g.rect(0, 5, 5, 5, C["art-outline"])
    g.rect(0, 1, 5, 1, C["kit-wood-light"])
    g.rect(0, 4, 5, 4, C["kit-wood-dark"])
    return g, 2


def parchment() -> tuple[Grid, int]:
    """32 × 32 parchment with a few fibres and flecks, tiling seamlessly (the fibres wrap)."""
    g = Grid(32, 32, C["parchment"])
    rnd = random.Random(23)
    for _ in range(14):
        x, y, n = rnd.randrange(32), rnd.randrange(32), rnd.randint(2, 4)
        for i in range(n):
            g.px((x + i) % 32, y, C["kit-parchment-deep"])
    for _ in range(6):
        g.px(rnd.randrange(32), rnd.randrange(32), C["kit-parchment-rule"])
    return g, 0


def pieces() -> dict[str, tuple[Grid, int]]:
    out = {"frame": frame(), "frame-thin": frame(caps=False), "bar": bar(), "well": well(), "plate": plate(),
           "band": band(), "parchment": parchment()}
    for kind in BUTTONS:
        for state in ("", "hover", "down", "off"):
            out[f"btn-{kind}" + (f"-{state}" if state else "")] = button(kind, state)
    for state in ("", "hover", "on"):
        out["tab" + (f"-{state}" if state else "")] = tab(state)
        out["slot" + (f"-{state}" if state else "")] = slot(state)
    return out


def write(out: pathlib.Path = OUT) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    kit = {"note": "Written by tools/ui_kit.py (docs/design/design-system-v4.md §2). Sizes and insets in art px; "
                   "<piece>.png is 2 CSS px an art px, <piece>@2x.png 4.", "px": 2, "pieces": {}}
    for name, (g, inset) in pieces().items():
        for scale, suffix in ((2, ""), (4, "@2x")):
            g.img.resize((g.w * scale, g.h * scale), Image.NEAREST).save(out / f"{name}{suffix}.png", optimize=True)
        kit["pieces"][name] = {"size": [g.w, g.h], "inset": inset}
    (out / "kit.json").write_text(json.dumps(kit, indent=1) + "\n", encoding="utf-8")
    return kit


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=pathlib.Path, default=OUT)
    kit = write(ap.parse_args().out)
    print(f"{len(kit['pieces'])} pieces → {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
