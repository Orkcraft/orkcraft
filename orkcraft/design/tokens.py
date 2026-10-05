"""The design tokens (`tokens.json`, docs/design-system.md): roles for fonts, colours and space.

A building's UI document names roles only (`"font": "status"`, `"tone": "fire"`). A face maps a
role to what it can draw: the TUI to a text style, a GUI to a font family, size and weight.

    tokens.FONTS                 # ("title", "heading", "body", "mono", "status", "label", "number")
    tokens.font("status")        # {"family": "text", "size": 12, "weight": 400, "tui": "dim", ...}
    tokens.family("title", "camp")
    tokens.color("fire", "office")
"""
from __future__ import annotations

import functools
import json
from pathlib import Path

PATH = Path(__file__).with_name("tokens.json")
THEMES = ("camp", "office")


@functools.lru_cache(maxsize=1)
def load() -> dict:
    return json.loads(PATH.read_text(encoding="utf-8"))


def _fonts() -> tuple[str, ...]:
    return tuple(load()["fonts"])


def _tones() -> tuple[str, ...]:
    return tuple(k for k in load()["colors"]["about"])


FONTS: tuple[str, ...] = _fonts()
TONES: tuple[str, ...] = _tones()


def font(role: str) -> dict:
    return dict(load()["fonts"][role])


def family(role: str, theme: str) -> str:
    """The CSS font stack of a font role in a theme."""
    return load()["families"][theme][font(role)["family"]]


def color(role: str, theme: str) -> str:
    return load()["colors"][theme][role]


def space(step: int, unit: str = "px") -> int:
    steps = load()["space"][unit]
    return steps[max(0, min(step, len(steps) - 1))]


def problems() -> list[str]:
    """What is wrong with tokens.json itself: every theme has every colour role, every font names a
    family every theme has. (The tests run it; a hand edit of the file is checked the same way.)"""
    data, out = load(), []
    for theme in THEMES:
        missing = set(TONES) - set(data["colors"].get(theme, {}))
        if missing:
            out.append(f"colors.{theme}: no {sorted(missing)}")
        for role, f in data["fonts"].items():
            if f.get("family") not in data["families"].get(theme, {}):
                out.append(f"fonts.{role}: no family {f.get('family')!r} in {theme}")
    return out
