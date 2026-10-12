"""The Warchief at the top of the installer (install.sh), drawn in the terminal from his sprite.

    python tools/install_banner.py            # rewrites the banner between its marks in install.sh

`design-system/sprites/orks/warchief.png` is 24×20 in 2×2 pixels: 12×10 of his own. Each of those is
two columns wide and half a row high (▀ / ▄ with a foreground and a background colour), so he stands
24 columns by 5 rows with square pixels. The colours are the xterm 256 palette's nearest, which every
terminal of macOS and Linux draws (Terminal.app has no 24-bit colour). Needs Pillow.
"""
from __future__ import annotations

import pathlib

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPRITE = ROOT / "design-system" / "sprites" / "orks" / "warchief.png"
SCRIPT = ROOT / "install.sh"
BEGIN, END = "# -- banner: tools/install_banner.py --", "# -- end of banner --"
# Beside him, on the rows of his face (the camp's voice: the Warchief speaks first, then the facts).
WORDS = {1: r"\033[1mOrkcraft\033[0m", 2: r"\033[2mMany coding agents in one project, as a real-time strategy game\033[0m",
         3: r"\033[2mThe Warchief raises your camp: uv, Python, Orkcraft\033[0m"}

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
    for y in range(0, im.height, 2):
        line, last = "", None
        for x in range(im.width):
            top = px[x, y]
            low = px[x, y + 1] if y + 1 < im.height else (0, 0, 0, 0)
            t, b = (xterm(top[:3]) if top[3] > 127 else None), (xterm(low[:3]) if low[3] > 127 else None)
            if t is None and b is None:
                cell, style = "  ", None
            elif t is not None and b is not None:
                cell, style = "▀▀", f"38;5;{t};48;5;{b}"
            elif t is not None:
                cell, style = "▀▀", f"38;5;{t}"
            else:
                cell, style = "▄▄", f"38;5;{b}"
            if style != last:
                line += r"\033[0m" + (rf"\033[{style}m" if style else "")
                last = style
            line += cell
        line += r"\033[0m"
        out.append(line)
    return out


def block() -> str:
    body = rows()
    lines = [BEGIN, "banner() {"]
    for i, row in enumerate(body):
        words = f"   {WORDS[i]}" if i in WORDS else ""
        lines.append(f"  printf '  {row}{words}\\n'")
    lines += ["}", END]
    return "\n".join(lines)


def main() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    start, stop = text.index(BEGIN), text.index(END) + len(END)
    SCRIPT.write_text(text[:start] + block() + text[stop:], encoding="utf-8")


if __name__ == "__main__":
    main()
