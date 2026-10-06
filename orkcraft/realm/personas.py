"""🎭 Personas of a Barracks: who an ork is when it takes a part of a plan (design:
docs/design/barracks-planning.md §4.3).

A persona is a template — a name, the tier it prefers and a few lines on who it is and how it works;
an ork is an instance hired *as* a persona. The steward writes a new one while it plans; it is kept in
`personas/<name>.md` under the building's state folder and used again whenever a plan names it.

A new persona is the orks' decision, so it waits as the autonomy level says (autonomy.waits):
⛓️ for the operator, 🕰 the question wait of its building, ⛓️‍💥 not at all. Until it is approved it is `approved: false`.

    p = personas.load(state_dir, "backend")      # None when there is none
    personas.save(state_dir, p)
    personas.listing(state_dir)                  # [(name, tier, first line)] for the steward's plan
"""
from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from pathlib import Path

from orkcraft.realm import tiers

DIR = "personas"
NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,29}$")


@dataclass
class Persona:
    name: str
    prompt: str
    tier: str = "warrior"
    approved: bool = False
    created: str = ""
    by: str = "steward"          # steward | operator

    def first_line(self) -> str:
        return next((ln.strip() for ln in self.prompt.splitlines() if ln.strip()), "")[:120]


def _file(state_dir: Path, name: str) -> Path:
    return state_dir / DIR / f"{name}.md"


def load(state_dir: Path, name: str) -> Persona | None:
    if not NAME.match(name or ""):
        return None
    try:
        raw = _file(state_dir, name).read_text(encoding="utf-8")
    except OSError:
        return None
    head, body = {}, raw
    if raw.startswith("---\n") and "\n---\n" in raw[4:]:
        front, body = raw[4:].split("\n---\n", 1)
        for line in front.splitlines():
            k, _, v = line.partition(":")
            head[k.strip()] = v.strip()
    tier = head.get("tier", "warrior")
    return Persona(name, body.strip(), tier if tier in tiers.TIERS else "warrior",
                   head.get("approved", "").lower() == "true", head.get("created", ""), head.get("by", "steward"))


def save(state_dir: Path, p: Persona) -> None:
    if not NAME.match(p.name):
        raise ValueError(f"a persona's name is lowercase letters, digits and dashes: {p.name!r}")
    f = _file(state_dir, p.name)
    f.parent.mkdir(parents=True, exist_ok=True)
    created = p.created or dt.datetime.now().isoformat(timespec="seconds")
    f.write_text(f"---\ntier: {p.tier}\napproved: {str(p.approved).lower()}\ncreated: {created}\nby: {p.by}\n---\n\n"
                 f"{p.prompt.strip()}\n", encoding="utf-8")


def all_of(state_dir: Path) -> list[Persona]:
    try:
        names = sorted(f.stem for f in (state_dir / DIR).glob("*.md"))
    except OSError:
        return []
    return [p for p in (load(state_dir, n) for n in names) if p is not None]


def listing(state_dir: Path) -> list[tuple[str, str, str]]:
    """The approved personas, for the steward's plan: (name, tier, first line)."""
    return [(p.name, p.tier, p.first_line()) for p in all_of(state_dir) if p.approved]
