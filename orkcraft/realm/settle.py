"""A task settles before it goes, related ones go together (docs/design/settle-and-join.md).

A board that sends its tasks by itself holds a new one for a while; a related card that comes meanwhile
joins it, and both go as one task. What is related is judged here, by the words two cards share — on
this machine, no model. A word counts by its start (`alike`), so "экспорта" meets "экспорт" and
"designs" meets "design"; the common short words never count.

    closeness("Make the CSV export", "New design for the CSV export")   == CLOSE
    best("New design for the CSV export", [("csv-export", "Make the CSV export")]) == ("csv-export", CLOSE)
    combined("Make the CSV export", ["New design for the CSV export"])  # one task's text

Pure module, no face.
"""
from __future__ import annotations

import re

SETTLE_S = 120                    # how long a new task waits on the board by default (`settle`)
LATER_MIN = 60                    # how long a task marked Not urgent waits (`later_minutes`)
STRETCH = 3                       # a held task waits at most this many `settle`s after it came, joins and all
STEM = 5                          # two words are one when they start alike: this many letters at most
WORDS = 200                       # the words of a card that are read
CLOSE, NEAR = "close", "near"     # joins at once / asks first
ADDED = "Added later — where it disagrees with the above, this wins"

_WORD = re.compile(r"[^\W\d_][\w-]*", re.U)
STOP = frozenset(
    # English
    "the and for with this that from have will what when where which into your there their about please "
    "should could would also make sure some them then than only just like need want task add new can let "
    "now all any but not are was were has had its it's our out use using via one two way get set "
    # Russian
    "для что это как так все всё ещё еще уже или надо нужно чтобы когда где там тут его она они оно "
    "мне нам вам был была были будет есть нет без при про над под после перед через сделай сделать "
    "сделайте давай добавь добавить новый новая новое новую новые хочу можно пусть тоже также "
    "задача задачу".split())


def stems(text: str) -> set[str]:
    """The words of `text` that say what it is about (lower case): words of three letters or more, the
    common ones aside, and the short names written in capitals ("X", "UI")."""
    out = set()
    for raw in _WORD.findall(text or "")[:WORDS]:
        w = raw.strip("-").lower()
        if w in STOP:
            continue
        if len(w) >= 3 or (raw.strip("-").isupper() and raw[:1].isalpha()):
            out.add(w)
    return out


def alike(a: str, b: str) -> bool:
    """Two words are one when they start alike: all but the shorter one's last letter (its ending), at
    least three letters, at most `STEM` — "экспорта" and "экспорт", "фичу" and "фичи", "mode" and "modes"."""
    if a == b:
        return True
    need = min(STEM, min(len(a), len(b)) - 1)
    return need >= 3 and a[:need] == b[:need]


def score(a: str, b: str) -> tuple[int, float]:
    """How many words two texts share, and what part of the shorter one that is (0…1)."""
    sa, sb = stems(a), stems(b)
    if not sa or not sb:
        return 0, 0.0
    few, many = (sa, sb) if len(sa) <= len(sb) else (sb, sa)
    shared = sum(1 for w in few if any(alike(w, o) for o in many))
    return shared, shared / len(few)


def closeness(a: str, b: str) -> str:
    """CLOSE: two or more words in common, at least half of the shorter text; NEAR: a word in common, a
    quarter of the shorter text; "" when they are not related."""
    shared, part = score(a, b)
    if shared >= 2 and part >= 0.5:
        return CLOSE
    if shared >= 1 and part >= 0.25:
        return NEAR
    return ""


def best(text: str, candidates: list[tuple[str, str]]) -> tuple[str, str]:
    """The candidate (id, text) closest to `text` and how close it is; ("", "") when none is related.
    The closest by its part of the shorter text, then by the words shared, then the latest."""
    found, key, level = "", (0.0, 0), ""
    for cid, other in candidates:
        how = closeness(text, other)
        if not how:
            continue
        shared, part = score(text, other)
        if (part, shared) >= key:
            found, key, level = cid, (part, shared), how
    return found, level


def added(text: str) -> str:
    """A card's text as an addition to a task."""
    return f"---\n{ADDED}: {text.strip()}"


def is_addition(text: str) -> bool:
    """The text is an addition to a task (what `added` writes), not a task of its own."""
    return text.lstrip().startswith(f"---\n{ADDED}:")


def combined(first: str, more: list[str]) -> str:
    """One task's text: the first card's, then each joined card under a line of its own."""
    return "\n\n".join([first.strip()] + [added(t) for t in more if t.strip()])


def goes_at(came: float, now: float, settle: float) -> float:
    """When a held task goes once something joined it now: `settle` from now, but no later than `STRETCH`
    `settle`s after it came."""
    return min(now + settle, came + STRETCH * settle)
