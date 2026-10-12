"""The Improve buildings' orks as agents (docs/design/improve-buildings.md §8): the Mechanic, a senior AI engineer on
quality and spend, and the Alchemist, a senior UI/UX designer — and the Farseer, the Elders' product manager, who reads
a day with the Mechanic (realm/day_review.py) — one Markdown file each (design/agents/<name>.md).

Its first paragraph is who it is and what comes first: `brief` goes with every light ask (a set of cases, a card's
layout, a picture), so it costs a few dozen tokens; `persona` is the whole file, for the asks that decide (what to
change in a building, a code change, the night's council).

    agents.brief("mechanic")      agents.persona("alchemist")
"""
from __future__ import annotations

import functools
from pathlib import Path

DIR = Path(__file__).with_name("agents")
NAMES = ("mechanic", "alchemist", "farseer")


@functools.lru_cache(maxsize=None)
def persona(name: str) -> str:
    return (DIR / f"{name}.md").read_text(encoding="utf-8").strip()


def brief(name: str) -> str:
    return persona(name).split("\n\n", 1)[0].strip()
