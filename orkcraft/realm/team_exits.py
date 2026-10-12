"""The Review board's exits, its one-click presets and what its steward's answer names (docs/design/review-board.md §2):
where a judged document goes, the route, the task and the time read out of an answer. Split out of realm/team.py,
which re-exports every name here.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_ROUTE = re.compile(r"^[\s*#_>`-]*(?:ROUTE|EXIT)\b[\s*_`]*:?[\s*_`]*([A-Za-z0-9_-]{1,32})[\s*_`.]*$", re.I | re.M)
_TASK = re.compile(r"^[\s*#_>`-]*TASK\b[\s*_`]*:[\s*_`]*(.+?)[\s*_`]*$", re.I | re.M)
_WHEN = re.compile(r"^[\s*#_>`-]*WHEN\b[\s*_`]*:[\s*_`]*(.+?)[\s*_`.]*$", re.I | re.M)


@dataclass(frozen=True)
class Exit:
    """Where a judged document can go (docs/design/review-board.md §2): a name, the rule the steward reads, and
    `id`, the route a road out waits for. *Back to the author* and *Ask me* are built in, not exits here."""
    id: str
    name: str
    when: str = ""


BACK, ASK = "back", "ask"                     # the built-in exits' ids
TEMPLATES = {                                 # the setup's one-click starts
    "decision": ("Next: it may go on as it is",),
    "who": ("To an agent: an agent can do it", "To a person: it needs a person's judgment or a reply"),
}
OUT_KEEP = 20_000                             # what went out, as the discussion keeps it


@dataclass(frozen=True)
class Preset:
    """A board set up in one click: its purpose, its members (role, what it checks, tier) and its rounds."""
    id: str
    title: str
    purpose: str
    members: tuple[tuple[str, str, str], ...]
    max_cycles: int
    wiki: bool = False                         # its members check against the town's Wiki (config `notes`)


# A preset is a Review board set up as one, not a building type of its own (docs/design/barracks-flows.md §6.2).
PRESETS: dict[str, Preset] = {p.id: p for p in (
    Preset("reply_check", "Reply check",
           "A reply an ork drafted, before it goes out: its tone and its facts. Approve lets it go on to the Review "
           "gate; rework sends it back to the ork that wrote it, with what to change.",
           (("Tone", "Polite and plain, in the language of the message. No promise of a date, a price, money or a "
                     "commitment the person did not make; nothing private about other people.", "laborer"),
            ("Facts", "Every claim in the draft is found in the Wiki's notes lent with it or in the message and its "
                      "thread; a claim found nowhere is marked, and the draft says it will be checked.", "laborer")),
           max_cycles=2, wiki=True),
)}


def exit_id(name: str) -> str:
    return re.sub(r"[^a-z0-9_-]+", "-", str(name).strip().lower()).strip("-")[:32]


def parse_exit(entry: str) -> Exit | None:
    """`To development: ready to build, no open risk` → Exit("to-development", "To development", "ready to …")."""
    name, _, when = str(entry).partition(":")
    name, when = " ".join(name.split())[:60], " ".join(when.split())[:300]
    eid = exit_id(name)
    return Exit(eid, name, when) if eid and eid not in (BACK, ASK) else None


def exits_of(config: dict) -> list[Exit]:
    """A board's exits: its `exits`, else its `routes` of old (no rule), else none (it only approves)."""
    out: list[Exit] = []
    raw = config.get("exits")
    for e in (parse_exit(x) for x in raw) if isinstance(raw, list) and raw else (Exit(r, r) for r in routes_of(config)):
        if e is not None and all(x.id != e.id for x in out):
            out.append(e)
    return out


def routes_of(config: dict) -> list[str]:
    """The routes a clan that routes chooses from (`routes`), as road filters spell them."""
    out = []
    for r in config.get("routes") or []:
        r = re.sub(r"[^a-z0-9_-]+", "-", str(r).strip().lower()).strip("-")[:32]
        if r and r not in out:
            out.append(r)
    return out


def parse_route(text: str, routes: list[str] | tuple[str, ...]) -> tuple[str, str]:
    """(the route the steward named — one of `routes` — or "", its answer without the ROUTE line)."""
    m = _ROUTE.search(text or "")
    if not m:
        return "", text
    rest = (text[:m.start()] + text[m.end():]).strip()
    route = m.group(1).lower()
    return (route if route in routes else ""), rest


def parse_task(text: str) -> tuple[str, str]:
    """(the task the steward named in one line, or "", its answer without the TASK line)."""
    m = _TASK.search(text or "")
    if not m:
        return "", text
    return " ".join(m.group(1).split())[:120], (text[:m.start()] + text[m.end():]).strip()


def parse_when(text: str) -> tuple[str, str]:
    """(the time the steward named — `tomorrow 11:00, 30 min` — or "", its answer without the WHEN line)."""
    m = _WHEN.search(text or "")
    if not m:
        return "", text
    return " ".join(m.group(1).split())[:60], (text[:m.start()] + text[m.end():]).strip()
