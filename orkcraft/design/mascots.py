"""The operator's mascots as grids (docs/design/improve-buildings.md §6.4): each head a 12 × 11 grid of palette letters,
drawn by tools/growth_sprites.py and shipped as `design-system/sprites/mascots/grids.json`, so the UX bench can draw one
again from a person's words without an image model: the Alchemist edits the grid as text, the palette stays the
palette, and the picture is made from the grid here (no Pillow in the product).

    mascots.path("marketing", 2)            -> "sprites/mascots/marketing-2.png"
    mascots.grid(path)                      -> this machine's grid of it, else the design system's
    mascots.problems(grid)                  -> what is wrong with a grid ([] when it can be drawn)
    mascots.png(grid, 2)                    -> its PNG at 2 screen px a cell (the sprite's 1x; 4 for its @2x)
    mascots.cells(region)                   -> a region of the picture said as the rows and columns it covers

The call that draws one again is the painter's (realm/painter.py `mascot`). Pure: no face.
"""
from __future__ import annotations

import functools
import json
import re
import struct
import zlib

from orkcraft.design import tokens

W, H = 12, 11
STAGES = (1, 2, 3, 4)
PATH = re.compile(r"^sprites/mascots/([a-z_]+)-([1-4])\.png$")
SCALE = 2                     # screen px a cell in the sprite's 1x file (its @2x: twice that)


@functools.cache
def _shipped() -> dict:
    return json.loads((tokens.SYSTEM / "sprites" / "mascots" / "grids.json").read_text(encoding="utf-8"))


def palette() -> dict[str, str]:
    return dict(_shipped()["palette"])


def path(role: str, stage: int) -> str:
    return f"sprites/mascots/{role}-{stage}.png"


def is_mascot(p: str) -> bool:
    m = PATH.match(p or "")
    return bool(m) and f"{m[1]}-{m[2]}" in _shipped()["grids"]


def own_grid(p: str):
    """Where this machine keeps the grid of a head it drew again (beside its picture)."""
    return tokens.assets_dir() / p.replace(".png", ".grid.json")


def shipped_grid(p: str) -> list[str]:
    m = PATH.match(p)
    return list(_shipped()["grids"][f"{m[1]}-{m[2]}"])


def grid(p: str) -> list[str]:
    """The head as it stands on this machine: its own grid, else the design system's."""
    own = own_grid(p)
    if own.is_file():
        try:
            g = json.loads(own.read_text(encoding="utf-8")).get("grid")
            if not problems(g):
                return list(g)
        except (OSError, ValueError, AttributeError):
            pass
    return shipped_grid(p)


def problems(g) -> list[str]:
    if not isinstance(g, list) or not all(isinstance(r, str) for r in g):
        return ["the grid is a list of rows, each a string"]
    out = []
    if len(g) != H:
        out.append(f"the grid has {H} rows, not {len(g)}")
    letters = set(palette()) | {"."}
    for i, row in enumerate(g):
        if len(row) != W:
            out.append(f"row {i} has {W} cells, not {len(row)}")
        bad = sorted(set(row) - letters)
        if bad:
            out.append(f"row {i} uses letters not in the palette: {''.join(bad)}")
    if not out and all(set(r) == {"."} for r in g):
        out.append("the grid is empty")
    return out


def png(g: list[str], scale: int = SCALE) -> bytes:
    """The grid as an RGBA PNG, `scale` px a cell, '.' transparent (as tools/growth_sprites.py `grid_image`)."""
    colours = {k: bytes(int(v[i:i + 2], 16) for i in (1, 3, 5)) + b"\xff" for k, v in palette().items()}
    clear = b"\x00\x00\x00\x00"
    rows = []
    for row in g:
        line = b"".join(colours.get(c, clear) * scale for c in row)
        rows += [b"\x00" + line] * scale
    chunk = lambda kind, data: (struct.pack(">I", len(data)) + kind + data  # noqa: E731
                                + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", W * scale, H * scale, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"".join(rows), 9)) + chunk(b"IEND", b""))


def cells(region: dict | None) -> str:
    """A region of the picture (shares of its width and height) as the rows and columns it covers."""
    if not region:
        return ""
    c0, c1 = int(region["x"] * W), min(W - 1, max(int(region["x"] * W), int((region["x"] + region["w"]) * W - 1e-9)))
    r0, r1 = int(region["y"] * H), min(H - 1, max(int(region["y"] * H), int((region["y"] + region["h"]) * H - 1e-9)))
    return (f"\nChange ONLY rows {r0}–{r1} and columns {c0}–{c1} (counted from 0, from the top left); keep every "
            "other cell exactly as it is.")


USES = {"K": "eyes, mouths, outlines", "I": "ivory: tusks, teeth, beards, bone, bandages", "G": "gold",
        "Y": "bright gold", "W": "gold shade", "R": "red", "r": "dark red", "O": "orange", "L": "leaf green",
        "l": "its shade", "B": "blue", "b": "light blue", "c": "glass", "P": "purple", "p": "plum", "q": "deep plum",
        "M": "metal", "m": "dark metal", "H": "highlight", "t": "leather", "T": "dark leather", "k": "pink plume",
        "o": "ork skin", "d": "its brows", "g": "goblin skin", "n": "gnome skin", "N": "nose", "e": "elf skin",
        "h": "blonde hair, parchment", "j": "its shade", "a": "auburn hair", "A": "its shade", "v": "lich",
        "f": "ghost sheet", "F": "its shade", "u": "mummy's bandage shade", "s": "lamp light", "z": "visor green"}
