"""Two looks of the same town: camp (the game) and office (a work tool).

    camp        buildings wear their ASCII, agents are orcs 🧌, a question is fire 🔥 — a building
                left waiting burns (orange, then red, then its roof turns to 🔥), resources are gold
                🪙, lumber 🪵 and meat 🥩, rocks 🪨 roll along the roads.
    office      no game and, as far as it goes, no emoji at all — buildings are grey frames on black,
                names and status lines lose their icons, a question is `?` and a waiting building
                only gets a red frame, resources are words, the roads carry small squares. Every
                concept goes by its office name (`realm/lexicon.py`): the Watchtower is External
                listeners, an ork an agent, a road a link.

The mode is kept as `preferences.mode` of the Town Scroll (`immersion` / `hidden` / `plain`, its old
names, read as camp / office);
the Desktop sets `current` so every widget draws the same look. Pure module, no Textual.
"""
from __future__ import annotations

import re
import time

from orkcraft.realm import lexicon
from orkcraft.realm.looks import KIND_ICONS
from orkcraft.realm.orcs import ALERT_ICON

CAMP, OFFICE = lexicon.CAMP, lexicon.OFFICE
MODES = (CAMP, OFFICE)
OLD_NAMES = {"immersion": CAMP, "hidden": OFFICE, "plain": OFFICE}

PERSON = "🧑"
QUESTION = "?"
ROCK = "🪨"
SQUARE = "■"

# A building whose orc waits for an answer burns in stages (seconds since the question came up):
# orange flickers first, then it turns red, then its roof turns to 🔥 bit by bit until it is all fire.
FIRE_RED_S = 30.0
FIRE_ROOF_S = 60.0
FIRE_ROOF_FULL_S = 300.0

_current = CAMP


def normalize(value: object) -> str:
    value = OLD_NAMES.get(value, value)  # type: ignore[arg-type]
    return OFFICE if value == OFFICE else CAMP


def current() -> str:
    return _current


def set_current(mode: str) -> None:
    global _current
    _current = normalize(mode)


def office(mode: str | None = None) -> bool:
    return normalize(mode or _current) == OFFICE


_ORC_ICONS = sorted({i for i in KIND_ICONS.values()}, key=len, reverse=True)   # 🪧🧌 before 🧌


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
    out = _EMOJI.sub("", out)
    out = re.sub(r"(?<=\S) {2,}(?=\S)", " ", out)          # a removed icon leaves no double gap
    out = re.sub(r"([\[(]) +", r"\1", out)
    out = re.sub(r" +([\])])", r"\1", out)
    return out.strip()


def words(value: str, mode: str | None = None) -> str:
    """A label in the mode's words, its emoji kept: `🗼 Watchtower` in the camp, `🗼 External listeners`
    in the office (`realm/lexicon.py`)."""
    return lexicon.office_words(value) if office(mode) and value else value


def text(value: str, mode: str | None = None) -> str:
    """What the mode shows of a label: as it is in the camp; in the office in its words and without emoji
    (`🗼 Watchtower` → `External listeners`). For the interface only, never for what someone wrote."""
    return strip_emoji(lexicon.office_words(value)) if office(mode) and value else value


def skin(text_: str, mode: str | None = None) -> str:
    """Badges in the mode's words: `🧌 Smith+1 C 🔨 🔥` stays in the camp, reads `Smith+1 C ?` in the office
    (a busy one `Smith+1 C busy`, an idle one only its name)."""
    if not office(mode) or not text_:
        return text_
    text_ = text_.replace(ALERT_ICON, f" {QUESTION} ").replace("⚙", " busy ")
    return " ".join(strip_emoji(text_).split())


def alert_style(mode: str | None = None) -> str:
    """The colour of a place with a question waiting (a War Map row): the camp's fire orange, the office's red."""
    return "bold #ef4444" if office(mode) else "bold #ff8c1a"


def alert_icon(mode: str | None = None) -> str:
    return QUESTION if office(mode) else ALERT_ICON


def cart_glyph(mode: str | None = None) -> str:
    return SQUARE if office(mode) else ROCK


def coin_glyph(mode: str | None = None) -> str:
    return "$" if office(mode) else "🪙"


def footer(description: str, mode: str | None = None) -> str:
    """A key's description in the footer: `📯 War Horn` → `Stop all`, `🔥 Orders` → `Answers` in the office."""
    return text(description, mode)


# HUD resources: (camp icon, office word) — the values are the same in both.
RESOURCES = {"quota": ("⏳", "Quota"), "gold": ("🪙", "Spend"), "lumber": ("🪵", "Context"), "supply": ("🥩", "Agents")}


def resource(name: str, mode: str | None = None) -> str:
    icon, word = RESOURCES[name]
    return word if office(mode) else icon


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
