"""Growth (docs/design/growth.md): what a building has learned, and what its operator has.

A building's **level** (I–III) is its maturity: the changes of its orks that passed probation, and
what was liked of it since. It is earned from outcomes only, never from clicks, and once reached it
never drops (kept in the Town Scroll, `buildings[].level`). The goal (🪙 ⚖️ 💎) only gives it a
direction: the shape of its flag.

The operator grows too, per machine (`settings.growth`): **deeds** (what the camp learned to do: the
first road, the first change of the orks kept…) and the **stage** of their mascot (1–4), never lost.

What grew is **news**, said once by the Warchief's line: a level reached, a stage, a deed, and the
loop closed on a review ("your 👎 on Brief → the orks changed it → 4 👍 since"). The news waits in
`.orkcraft/growth.json` until the operator has seen it.

    growth.earned(root, "brief")            -> 2
    growth.next_step(root, "brief", 2)      -> "2 more kept changes, a month without a revert, …"
    growth.settle(scroll, root, machine)    -> [News]   levels, deeds, the stage, the loops; scroll and machine updated
    growth.news(root) / growth.seen(root, id)

Pure: no face. It reads the orks' changes (`realm/evolution.py`) and the ratings (`realm/feedback.py`).
"""
from __future__ import annotations

import datetime as dt
import json
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

from orkcraft.realm import evolution, feedback, intents

STATE = Path(".orkcraft") / "growth.json"
ROMAN = {0: "", 1: "I", 2: "II", 3: "III"}

# What each level asks (§4.2): kept changes, the window the ratings are read in, the days without a revert.
NEEDS = {1: {"kept": 1}, 2: {"kept": 3, "days": 30, "calm": 14}, 3: {"kept": 5, "days": 30, "calm": 30, "times": 3}}
LOOP_WAIT = dt.timedelta(days=7)      # a review's loop is told when rated since, or after this long
LOOP_BEFORE = dt.timedelta(days=7)    # a change answers the reviews of its building this long before it
NEWS_KEEP = 20


@dataclass
class News:
    kind: str                    # level | stage | deed | loop
    text: str
    building: str = ""           # the building it is about (level, loop): the page opens its Info
    icon: str = ""
    at: str = field(default_factory=lambda: dt.datetime.now().isoformat(timespec="seconds"))
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])


# -- a building's level -------------------------------------------------------------------------------

def _ago(days: int, now: dt.datetime) -> str:
    return (now - dt.timedelta(days=days)).isoformat(timespec="seconds")


def kept(root: Path, building: str, changes: list[evolution.Change] | None = None) -> list[evolution.Change]:
    """The changes that count for its level: the orks' kept after probation, and the operator's own
    edits only when a rating of `ENOUGH` followed them (hand edits alone would farm levels)."""
    changes = evolution.load(root) if changes is None else changes
    out = []
    for c in changes:
        if c.building != building or c.status != "kept":
            continue
        if c.by == "orcs" or feedback.liked(root, building, since=c.ts) >= feedback.ENOUGH - 1e-9:
            out.append(c)
    return sorted(out, key=lambda c: c.ts)


def _reverted_since(changes: list[evolution.Change], building: str, since: str) -> bool:
    return any(c.building == building and c.status == "reverted" and c.ts >= since for c in changes)


def earned(root: Path, building: str, changes: list[evolution.Change] | None = None,
           now: dt.datetime | None = None) -> int:
    """The highest level whose rule holds now (§4.2); each one asks the one below too."""
    now = now or dt.datetime.now()
    changes = evolution.load(root) if changes is None else changes
    ks = kept(root, building, changes)
    if not ks or feedback.liked(root, building, since=ks[0].ts) < feedback.ENOUGH - 1e-9:
        return 0
    month = _ago(30, now)
    liked, disliked = feedback.liked(root, building, since=month), feedback.disliked(root, building, since=month)
    if len(ks) < 3 or liked <= disliked or _reverted_since(changes, building, _ago(14, now)):
        return 1
    if (len(ks) < 5 or _reverted_since(changes, building, month)
            or liked < max(feedback.ENOUGH, 3 * disliked)):
        return 2
    return 3


def next_step(root: Path, building: str, level: int, changes: list[evolution.Change] | None = None) -> str:
    """What the next level asks, in words; "" at III."""
    if level >= 3:
        return ""
    want = NEEDS[level + 1]
    have = len(kept(root, building, changes))
    parts = []
    if have < want["kept"]:
        n = want["kept"] - have
        parts.append(f"{n} more kept change{'s' if n != 1 else ''} of its orks")
    if level + 1 == 1:
        parts.append("a 👍 after it")
    elif level + 1 == 2:
        parts.append("more liked than disliked this month, no revert for two weeks")
    else:
        parts.append("a month without a revert, three times more liked than disliked")
    return "Next: " + ", ".join(parts)


def mark(goal: str, level: int) -> str:
    """How a level reads beside its goal: "💎 II"; "" with none."""
    from orkcraft.scroll import GOAL_ICONS
    return f"{GOAL_ICONS.get(goal, '⚖️')} {ROMAN[level]}" if level else ""


# -- the operator's deeds and stage ---------------------------------------------------------------------

@dataclass(frozen=True)
class Deed:
    id: str
    icon: str
    title: str
    hint: str            # what to do to earn it, shown while it is ahead


DEEDS: tuple[Deed, ...] = (
    Deed("town", "🏰", "First town", "Raise a building beside the Town Hall"),
    Deed("road", "🛤", "First road", "Join two buildings with a road"),
    Deed("reference", "👍", "First reference", "Rate a result 👍: it becomes what good looks like"),
    Deed("week", "🗳", "A week of ratings", "Rate three buildings in one week"),
    Deed("learned", "🔁", "It learned", "Let a change of the orks pass its probation"),
    Deed("mature", "🚩", "Mature", "Bring a building to level III"),
    Deed("trusted", "⛓️‍💥", "Trusted", "Unchain a building"),
    Deed("night", "🌙", "A night's work", "Let the orks change a building in quiet hours, and keep it"),
)

# The mascot's stages by kin (realm/intents.py `Role.mascot`); stage 2 is the role's own nick.
STAGE_NAMES = {           # a fantasy rank with the job in it: what the stage means, said with a grin
    "orc": ("Commit Grunt", "", "Hotfix Berserker", "Warlord of Prod"),
    "lich": ("Standup Zombie", "", "Lich of Sprints", "Release Night King"),
    "elf": ("Pixel Sprout", "", "Ranger of the Grid", "High Elf of the Design System"),
    "gnome": ("A/B Tinkerer", "", "Growth-Hack Artificer", "Grand Tinker of Conversions"),
    "goblin": ("Spreadsheet Scrounger", "", "Pivot-Table Boss", "KPI Tycoon"),
    "knight": ("Bootstrap Squire", "", "Knight of the Seed Round", "Paladin of Product-Market Fit"),
    "skeleton": ("Inbox Skeleton", "", "Captain of the Skeleton Crew", "Lord of a Thousand Tabs"),
}
STAGE_NEXT = {1: "Rate three buildings in one week", 2: "Bring a building to level II",
              3: "Three buildings at level III, one of them on the clock or unchained", 4: ""}


def kin_of(profile: dict) -> str:
    role = intents.role(str((profile or {}).get("role") or ""))
    return role.mascot if role.mascot in STAGE_NAMES else "skeleton"


def stage_name(profile: dict, stage: int) -> str:
    role = intents.role(str((profile or {}).get("role") or ""))
    names = STAGE_NAMES[kin_of(profile)]
    return names[stage - 1] or role.nick or names[0]


def _rated_week(root: Path, scroll, now: dt.datetime) -> bool:
    since = _ago(7, now)
    rated = {i.building for i in feedback.incidents(root, 1000) if i.ts >= since}
    for bs in scroll.buildings:
        if bs.id not in rated and any(str(r.get("ts", "")) >= since for r in feedback.references(root, bs.id, 50)):
            rated.add(bs.id)
    return len(rated) >= 3


def _quiet(machine, ts: str) -> bool:
    try:
        when = dt.datetime.fromisoformat(ts)
    except ValueError:
        return False
    span = getattr(machine, "quiet", None)
    minute = when.hour * 60 + when.minute
    return span.contains(minute) if span is not None else minute < 7 * 60


def _free(bs, machine) -> bool:
    if bs.autonomy:
        return bs.autonomy in ("clock", "free")
    return int(getattr(machine, "autonomy", 0) or 0) >= 1


def deeds_done(scroll, root: Path, machine, changes: list[evolution.Change] | None = None,
               now: dt.datetime | None = None) -> set[str]:
    """The deeds this camp shows done now."""
    now = now or dt.datetime.now()
    changes = evolution.load(root) if changes is None else changes
    standing = [b for b in scroll.buildings if not b.demolished]
    done = set()
    if any(b.id != "town_hall" for b in standing):
        done.add("town")
    if any(b.roads for b in standing):
        done.add("road")
    if any(feedback.references(root, b.id, 1) for b in standing):
        done.add("reference")
    if _rated_week(root, scroll, now):
        done.add("week")
    orks_kept = [c for c in changes if c.by == "orcs" and c.status == "kept"]
    if orks_kept:
        done.add("learned")
    if any(_quiet(machine, c.ts) for c in orks_kept):
        done.add("night")
    if any((b.level or 0) >= 3 for b in standing):
        done.add("mature")
    if any(b.autonomy == "free" for b in standing):
        done.add("trusted")
    return done


def stage_of(scroll, deeds: dict, machine) -> int:
    """The stage the camp shows now (§7.2): 1 always; 2 a week of ratings; 3 a building at II; 4 three at
    III, one of them deciding by itself."""
    standing = [b for b in scroll.buildings if not b.demolished]
    three = [b for b in standing if (b.level or 0) >= 3]
    if len(three) >= 3 and any(_free(b, machine) for b in three):
        return 4
    if any((b.level or 0) >= 2 for b in standing):
        return 3
    if "week" in deeds:
        return 2
    return 1


# -- the loop closed on a review ----------------------------------------------------------------------

def loops(root: Path, scroll, told: set[str], changes: list[evolution.Change] | None = None,
          now: dt.datetime | None = None) -> list[tuple[str, News]]:
    """(change id, News) for each change of the orks that answered a review of its building (a 👎 in the
    week before it) and has proved itself: kept, and rated since or a week old; or taken back."""
    now = now or dt.datetime.now()
    changes = evolution.load(root) if changes is None else changes
    rows = feedback.incidents(root, 1000)
    out = []
    for c in changes:
        if c.by != "orcs" or c.id in told or c.status not in ("kept", "reverted"):
            continue
        try:
            at = dt.datetime.fromisoformat(c.ts)
        except ValueError:
            continue
        before = (at - LOOP_BEFORE).isoformat(timespec="seconds")
        reviews = [i for i in rows if i.building == c.building and before <= i.ts <= c.ts
                   and i.source == feedback.EXPLICIT]
        if not reviews:
            continue
        title = scroll.building(c.building).title if scroll.building(c.building) else c.building
        review = reviews[-1]
        what = f"your note “{review.note[:60]}”" if review.note else "your 👎"
        if c.status == "reverted":
            text = f"{what} on {title} → the orks changed it → it was taken back, {title} keeps its old way"
        else:
            after = (at + dt.timedelta(seconds=1)).isoformat(timespec="seconds")
            liked = feedback.liked(root, c.building, since=c.ts)
            disliked = feedback.disliked(root, c.building, since=after, rows=rows)
            if liked + disliked < feedback.ENOUGH - 1e-9 and now - at < LOOP_WAIT:
                continue                             # not proved yet: rated since, or a week old
            text = (f"{what} on {title} → the orks changed it ({c.summary[:60]}) → "
                    f"since then {liked:g} 👍, {disliked:g} 👎")
        out.append((c.id, News("loop", text[:1].upper() + text[1:], c.building, "🔁")))
    return out


# -- the state: what was told, the news waiting -----------------------------------------------------------

def _load(root: Path) -> dict:
    try:
        data = json.loads((Path(root) / STATE).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(root: Path, data: dict) -> None:
    path = Path(root) / STATE
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(path)
    except OSError:
        pass


def news(root: Path) -> list[News]:
    out = []
    for n in _load(root).get("news", []):
        try:
            out.append(News(**n))
        except TypeError:
            continue
    return out


def seen(root: Path, news_id: str) -> None:
    data = _load(root)
    data["news"] = [n for n in data.get("news", []) if n.get("id") != news_id]
    _save(root, data)


def settle(scroll, root: Path, machine, now: dt.datetime | None = None) -> list[News]:
    """Look again: levels reached go into the scroll, deeds and the stage into `machine.growth`, and what
    grew becomes news (returned, and kept until seen). The caller saves the scroll and the machine
    settings when it returns news."""
    now = now or dt.datetime.now()
    changes = evolution.load(root)
    fresh: list[News] = []
    for bs in scroll.buildings:
        if bs.demolished:
            continue
        got = earned(root, bs.id, changes, now)
        if got > (bs.level or 0):
            bs.level = got
            fresh.append(News("level", f"{bs.title} grew to {mark(bs.aim, got)}", bs.id, "🚩"))
    grown = dict(getattr(machine, "growth", None) or {})
    first = not grown                    # the first look on this machine: what is done already is not news
    deeds = dict(grown.get("deeds") or {})
    done = deeds_done(scroll, root, machine, changes, now)
    for d in DEEDS:
        if d.id not in deeds and d.id in done:
            deeds[d.id] = now.date().isoformat()
            if not first:
                fresh.append(News("deed", f"A deed: {d.title}", "", d.icon))
    stage = max(int(grown.get("stage") or 1), stage_of(scroll, deeds, machine))
    if stage > int(grown.get("stage") or 1) and not first:
        fresh.append(News("stage", f"Your mascot grew: {stage_name(getattr(machine, 'profile', {}), stage)}", "", "⭐"))
    if fresh or deeds != grown.get("deeds") or stage != grown.get("stage"):
        machine.growth = {**grown, "stage": stage, "deeds": deeds}
    data = _load(root)
    told = set(data.get("told", []))
    if data.get("loop_day") != now.date().isoformat():          # at most one loop told a day
        found = loops(root, scroll, told, changes, now)
        if found:
            cid, item = found[0]
            told.add(cid)
            data["loop_day"] = now.date().isoformat()
            fresh.append(item)
    if fresh:
        data["told"] = sorted(told)[-500:]
        data["news"] = (data.get("news", []) + [asdict(n) for n in fresh])[-NEWS_KEEP:]
        _save(root, data)
    return fresh
