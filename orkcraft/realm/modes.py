"""Two looks of the same town: immersion (the game) and hidden (the office).

    immersion   buildings wear their ASCII, agents are orcs 🧌, a question is fire 🔥 — a building
                left waiting burns (orange, then red, then its roof turns to 🔥), resources are gold
                🪙, lumber 🪵 and meat 🥩, rocks 🪨 roll along the roads.
    hidden      nothing that looks like a game: buildings are only frames, agents are people 🧑, a
                question is ❓ and a waiting building only turns red, resources are words, the roads
                carry small squares. The icons of the buildings' names stay.

The mode is kept as `preferences.mode` of the Town Scroll (`plain`, its old name, reads as hidden);
the Desktop sets `current` so every widget draws the same look. Pure module, no Textual.
"""
from __future__ import annotations

import time

from orkcraft.realm.looks import KIND_ICONS
from orkcraft.realm.orcs import ALERT_ICON

IMMERSION, HIDDEN = "immersion", "hidden"
MODES = (IMMERSION, HIDDEN)

PERSON = "🧑"
QUESTION = "❓"
ROCK = "🪨"
SQUARE = "■"

# A building whose orc waits for an answer burns in stages (seconds since the question came up):
# orange flickers first, then it turns red, then its roof turns to 🔥 bit by bit until it is all fire.
FIRE_RED_S = 30.0
FIRE_ROOF_S = 60.0
FIRE_ROOF_FULL_S = 300.0

_current = IMMERSION


def normalize(value: object) -> str:
    return HIDDEN if value in (HIDDEN, "plain") else IMMERSION


def current() -> str:
    return _current


def set_current(mode: str) -> None:
    global _current
    _current = normalize(mode)


def hidden(mode: str | None = None) -> bool:
    return (mode or _current) == HIDDEN


_ORC_ICONS = sorted({i for i in KIND_ICONS.values()}, key=len, reverse=True)   # 🗿🧌 before 🧌


def skin(text: str, mode: str | None = None) -> str:
    """Badges and titles in the mode's words: in hidden, orcs become 🧑 and the fire a ❓."""
    if not hidden(mode) or not text:
        return text
    for icon in _ORC_ICONS:
        text = text.replace(icon, PERSON)
    return text.replace(ALERT_ICON, QUESTION)


def alert_icon(mode: str | None = None) -> str:
    return QUESTION if hidden(mode) else ALERT_ICON


def cart_glyph(mode: str | None = None) -> str:
    return SQUARE if hidden(mode) else ROCK


def coin_glyph(mode: str | None = None) -> str:
    return "$" if hidden(mode) else "🪙"


# HUD resources: (immersion icon, hidden word) — the values are the same in both.
RESOURCES = {"gold": ("🪙", "Spend"), "lumber": ("🪵", "Context"), "supply": ("🥩", "Agents")}


def resource(name: str, mode: str | None = None) -> str:
    icon, word = RESOURCES[name]
    return word if hidden(mode) else icon


# -- fire --------------------------------------------------------------------------------------------

def fire_stage(elapsed: float) -> tuple[str, float]:
    """(colour stage, share of the roof on fire) after `elapsed` seconds of waiting.

    stage: `orange` (a fresh question) | `red` (left waiting); the roof starts burning at FIRE_ROOF_S
    and is all fire at FIRE_ROOF_FULL_S."""
    if elapsed < FIRE_RED_S:
        return "orange", 0.0
    if elapsed < FIRE_ROOF_S:
        return "red", 0.0
    share = (elapsed - FIRE_ROOF_S) / max(FIRE_ROOF_FULL_S - FIRE_ROOF_S, 1e-9)
    return "red", min(max(share, 0.0), 1.0)


def _order(row: int, col: int) -> int:
    """A fixed pseudo-random order in which the cells of a roof catch fire (the same every redraw)."""
    return (row * 7919 + col * 104729 + (col * col) * 31) % 1009


def burn(lines: list[str], share: float) -> list[str]:
    """`lines` (the roof: single-cell characters) with `share` of their drawn pairs of cells turned to 🔥.

    A 🔥 takes two cells, so the roof is cut into pairs; a pair with anything drawn in it is fuel.
    The width of every line stays the same."""
    if share <= 0 or not lines:
        return list(lines)
    pairs = [(r, c) for r, ln in enumerate(lines) for c in range(0, len(ln) - 1, 2) if ln[c:c + 2].strip()]
    if not pairs:
        return list(lines)
    n = len(pairs) if share >= 1 else int(round(share * len(pairs)))
    lit = set(sorted(pairs, key=lambda p: _order(*p))[:n])
    out = []
    for r, ln in enumerate(lines):
        s, c = [], 0
        while c < len(ln):
            if (r, c) in lit:
                s.append("🔥")
                c += 2
            else:
                s.append(ln[c])
                c += 1
        out.append("".join(s))
    return out


def now() -> float:
    return time.monotonic()
