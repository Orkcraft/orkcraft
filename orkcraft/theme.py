"""Canvas biomes, palettes and deterministic ASCII terrain generation."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Biome:
    name: str
    canvas: str              # canvas background
    glyphs: tuple[str, ...]  # terrain glyphs, each exactly one terminal cell
    terrain: str | None      # terrain glyph colour (None for void)
    window_bg: str           # window interior, 100 % opaque
    border: str              # inactive window border
    border_focus: str        # focused window border


BIOMES: dict[str, Biome] = {
    "void": Biome(
        name="void",
        canvas="#080808",
        glyphs=(),
        terrain=None,
        window_bg="#0e1611",
        border="#22262b",
        border_focus="#c99a3e",
    ),
    "forest": Biome(
        name="forest",
        canvas="#0a130c",
        glyphs=("·", ",", '"', "↟"),
        terrain="#1f3823",
        window_bg="#0e1611",
        border="#3e6b48",
        border_focus="#c99a3e",
    ),
    "ice": Biome(
        name="ice",
        canvas="#070d14",
        glyphs=("·", "'", "*", "⁕"),
        terrain="#162736",
        window_bg="#090f14",
        border="#2b4763",
        border_focus="#82aaff",
    ),
}

BIOME_ICONS = {"void": "🌑", "forest": "🌲", "ice": "🧊"}   # the War Map shows a biome by its icon

DEFAULT_BIOME = "forest"
SOLID_BLACK = "#000000"
MAX_DENSITY = 0.12          # share of canvas cells that may carry a glyph
TERRAIN_DENSITY = 0.09      # what the generator actually aims for
UNIT_ACTIVE = "#e5c07b"
UNIT_ALERT = "#e06c75"
DIFF_ADD = "#3fb950"
DIFF_REMOVE = "#f85149"


def _mix64(v: int) -> int:
    """SplitMix64 bit mixer."""
    v = (v ^ (v >> 30)) * 0xbf58476d1ce4e5b9 & 0xffffffffffffffff
    v = (v ^ (v >> 27)) * 0x94d049bb133111eb & 0xffffffffffffffff
    return (v ^ (v >> 31)) & 0xffffffffffffffff


def _coord_hash(x: int, y: int, seed: int, stream: int = 0) -> int:
    """Deterministic 64-bit integer hash for (x, y, seed, stream)."""
    h = (
        (x & 0xffffffff) * 0x9e3779b97f4a7c15
        ^ (y & 0xffffffff) * 0x6c62272e07bb0142
        ^ (seed & 0xffffffff) * 0x517cc1b727220a95
        ^ (stream & 0xffffffff) * 0x31848bab8b22f129
        + 0xa0761d6478bd642f
    ) & 0xffffffffffffffff
    return _mix64(h)


def terrain_glyph(x: int, y: int, biome: Biome, seed: int = 0) -> str | None:
    """Return a deterministic terrain glyph for (x, y) or None if cell is empty."""
    if not biome.glyphs:
        return None
    h1 = _coord_hash(x, y, seed, 0)
    if (h1 / 0x10000000000000000) < TERRAIN_DENSITY:
        h2 = _coord_hash(x, y, seed, 1)
        return biome.glyphs[h2 % len(biome.glyphs)]
    return None


def terrain_rows(width: int, height: int, biome: Biome, seed: int = 0) -> list[str]:
    """Generate `height` rows of exactly `width` characters for the given biome."""
    if height <= 0:
        return []
    if width <= 0:
        return ["" for _ in range(height)]
    if not biome.glyphs:
        return [" " * width for _ in range(height)]
    rows: list[str] = []
    for y in range(height):
        chars: list[str] = []
        for x in range(width):
            g = terrain_glyph(x, y, biome, seed)
            chars.append(g if g is not None else " ")
        rows.append("".join(chars))
    return rows
