"""The town's one look: what its marks are and how a building that waits burns.

Camp and Office were two looks once (a game and a work tool), switched per machine, per project and
by office hours. They are one now: the GUI wears Office's layout on Camp's design system, every
concept goes by its one word (`realm/lexicon.py`), and the deprecated TUI keeps the camp's ASCII.
`preferences.mode` of an older Town Scroll and `mode` of older machine settings still load and are
ignored. The module keeps its name so imports stay. Pure module, no Textual.

    a question is fire 🔥 — a building left waiting burns (orange, then red, then its roof turns to
    🔥), resources are gold 🪙, lumber 🪵 and meat 🥩, rocks 🪨 roll along the roads.
"""
from __future__ import annotations

import re
import time

from orkcraft.realm import lexicon

PERSON = "🧑"
QUESTION = "?"
ROCK = "🪨"

# A building whose orc waits for an answer burns in stages (seconds since the question came up):
# orange flickers first, then it turns red, then its roof turns to 🔥 bit by bit until it is all fire.
FIRE_RED_S = 30.0
FIRE_ROOF_S = 60.0
FIRE_ROOF_FULL_S = 300.0


# Emoji and pictographs (and what glues them together); box drawing, arrows, ✓ ✗ and · stay.
_EMOJI = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000026FF\U00002300-\U000023FF\U00002B00-\U00002BFF"
    "\u2702\u2705\u2708-\u270D\u270F\u2712\u271D\u2721\u2728\u2733\u2734\u2744\u2747\u274C\u274E"
    "\u2753-\u2755\u2757\u2763\u2764\u2795-\u2797\u27B0\u27BF"
    "\u2139\u2122\u3030\u303D\u3297\u3299\uFE0E\uFE0F\u200D\u20E3]")   # ✓ ✗ ✻ ✦ ➜ are text: they stay


_WORDS = {"👍": "+1", "👎": "-1", "🗑": "Delete", "🗑️": "Delete"}   # a button that is only an icon becomes a word


def strip_emoji(text: str) -> str:
    """`text` without emoji: `🌾 Task fields` → `Task fields`, `[🪙 $1 / $5]` → `[$1 / $5]`."""
    if not text:
        return text
    out = str(text)
    if _EMOJI.sub("", out).strip() == "" and out.strip() in _WORDS:     # a bare 👍 button reads +1
        return _WORDS[out.strip()]
    out = re.sub(r"👍\s*(?=\d)", "+", re.sub(r"👎\s*(?=\d)", "−", out))   # `👍 3 👎 1` → `+3 −1`
    out = out.replace("👍", "+1").replace("👎", "-1")       # `👍 / 👎 of the stewards` → `+1 / -1 of …`
    out = _EMOJI.sub("", out)
    out = re.sub(r"(?<=\S) {2,}(?=\S)", " ", out)          # a removed icon leaves no double gap
    out = re.sub(r"([\[(]) +", r"\1", out)
    out = re.sub(r" +([\])])", r"\1", out)
    return out.strip()


def plain(value: str) -> str:
    """A label in today's words without emoji (`🗼 Watchtower` → `External listeners`): the `_plain`
    fields of the GUI's snapshot. For the interface only, never for what someone wrote."""
    return strip_emoji(lexicon.words(value)) if value else value


# HUD resources: (icon, word) — the TUI shows the icon, the GUI the word.
RESOURCES = {"quota": ("⏳", "Quota"), "gold": ("🪙", "Spend"), "lumber": ("🪵", "Context"), "supply": ("🥩", "Orks")}


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
