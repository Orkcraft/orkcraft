"""The Warchief at the top of the installer (install.sh), drawn in the terminal from his sprite.

    python tools/install_banner.py            # rewrites the banner between its marks in install.sh

`design-system/sprites/orks/warchief.png` is 24×20 in 2×2 pixels: 12×10 of his own. He is drawn in
five of those rows (`ROWS`: the crown's points, the ears, the eyes, the tusks, the chin), one coloured
space per pixel: a terminal's cell is about twice as tall as wide, so 12×5 cells keep his shape. Only
background colour, no ▀ / ▄ glyphs: a glyph stops where the font does, and a terminal with more line
spacing left a dark seam on every row; a cell's background fills the whole row. The colours are the
xterm 256 palette's nearest, which every terminal of macOS and Linux draws (Terminal.app has no 24-bit
colour). Beside him go three short lines, only when the terminal is wide enough (`banner WIDTH`); in a
narrow one he stands alone, so nothing wraps under him. Needs Pillow.
"""
from __future__ import annotations

import pathlib

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPRITE = ROOT / "design-system" / "sprites" / "orks" / "warchief.png"
SCRIPT = ROOT / "install.sh"
BEGIN, END = "# -- banner: tools/install_banner.py --", "# -- end of banner --"
# Beside him, on the rows of his face (the camp's voice: the Warchief speaks first, then the facts).
WORDS = {1: r"\033[1mOrkcraft\033[0m", 2: "The Warchief raises your camp", 3: r"\033[2muv · Python · Orkcraft\033[0m"}
WIDE = 48            # the columns his words need beside him; below it he stands alone
ROWS = (0, 3, 5, 7, 9)   # of his ten: the crown's points, the ears, the eyes, the tusks, the chin

_LEVELS = (0, 95, 135, 175, 215, 255)


def xterm(rgb: tuple[int, int, int]) -> int:
    """The nearest colour of the 256 palette: its 6×6×6 cube or its greys."""
    def near(v: int) -> int:
        return min(range(6), key=lambda i: abs(_LEVELS[i] - v))
    r, g, b = (near(c) for c in rgb)
    cube = 16 + 36 * r + 6 * g + b
    d_cube = sum((_LEVELS[i] - c) ** 2 for i, c in zip((r, g, b), rgb))
    grey = max(0, min(23, round((sum(rgb) / 3 - 8) / 10)))
    d_grey = sum((8 + 10 * grey - c) ** 2 for c in rgb)
    return cube if d_cube <= d_grey else 232 + grey


def rows() -> list[str]:
    """His five rows, as `printf` format strings (escapes written out, no `%`)."""
    im = Image.open(SPRITE).convert("RGBA")
    im = im.resize((im.width // 2, im.height // 2), Image.NEAREST)
    px = im.load()
    out = []
    for y in ROWS:
        line, last = "", None
        for x in range(im.width):
            p = px[x, y]
            style = f"48;5;{xterm(p[:3])}" if p[3] > 127 else None
            if style != last:
                line += r"\033[0m" + (rf"\033[{style}m" if style else "")
                last = style
            line += " "
        line += r"\033[0m"
        out.append(line)
    return out


def block() -> str:
    lines = [BEGIN, "banner() {                                    # $1: the terminal's width in columns"]
    for i, row in enumerate(rows()):
        words = f"; [ \"$1\" -ge {WIDE} ] && printf '   {WORDS[i]}'" if i in WORDS else ""
        lines.append(f"  printf '  {row}'{words}; printf '\\n'")
    lines += ["}", END]
    return "\n".join(lines)


def main() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    start, stop = text.index(BEGIN), text.index(END) + len(END)
    SCRIPT.write_text(text[:start] + block() + text[stop:], encoding="utf-8")


if __name__ == "__main__":
    main()
