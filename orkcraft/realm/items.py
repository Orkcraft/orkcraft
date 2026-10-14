"""Items the person places in the camp (docs/design/v3-prompts.md §14): rewards that are things, never powers.

An **item is a file**: `design-system/items/<id>.json` (its id, name, sprite, what earns it and why), its sprite
beside it or one of v3's; a community may add more the way it adds buildings. Some are the person's **from the
start** (g2's trees, rocks, bushes, log piles), placed as often as they like; the rest are **earned** once, by Mission
1 done, the first lean week and month (realm/score.py), a portrait stage (the class's item) and a building at III,
and land in the inventory quietly: no news, no badge, nothing owed.

    items.catalog()                         {id: Item}
    items.earn(root, "first-cart", "Mission 1 finished")   True when new (the town's .orkcraft/items.json)
    items.settle(scroll, root, machine)     the ids earned just now, by what the town has done
    items.inventory(scroll, root)           what the inventory panel lists: each item, why, how many are left
    items.place(scroll, root, "tree", "main", 4, 7)        a copy on the grass, in the town file (`scroll.items`)
    items.move(scroll, placed_id, 5, 7) / items.remove(scroll, placed_id)
    items.back(scroll, root, placed_id, "Test bench")   a building took its cell: back to the inventory, with a note
    items.notes(root) / items.seen(root)                the notes, said only in the Items panel

Where an item may stand (grass only: never on track, paths, stops, or against a building) is the camp's layout's
to say (js/camp/grass.js); here a placement is a cell of 16 art px from the camp's corner. No face.
"""
from __future__ import annotations

import datetime as dt
import functools
import json
import struct
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

from orkcraft.design import tokens
from orkcraft.realm import growth

DIR = tokens.SYSTEM / "items"
STATE = Path(".orkcraft") / "items.json"
START, MISSION, LEAN_WEEK, LEAN_MONTH, STAGE, LEVEL = "start", "mission", "lean_week", "lean_month", "stage", "level"
BY = (START, MISSION, LEAN_WEEK, LEAN_MONTH, STAGE, LEVEL)
REACH = 400                 # a placement's cell stays this close to the camp's corner
PLACED_MAX = 500            # the town file's limit (schemas/town-scroll.v3.json)


@dataclass(frozen=True)
class Item:
    id: str
    name: str
    sprite: str              # under /ds/ (design-system/): "sprites/v3/decor/tree.png", "items/first-cart.png"
    by: str                  # what earns it: start | mission | lean_week | lean_month | stage | level
    why: str                 # what it was earned for, in words
    chapter: int = 0         # a mission's: the campaign's chapter
    stage: int = 0           # a portrait stage's: the stage, and the kin whose class it is
    kin: str = ""
    type: str = ""           # a building at III's: its type ("" any type without an item of its own)
    stand_in: bool = False   # its sprite stands in until GEN draws its own
    size: tuple[int, int] = (0, 0)


def _png_size(path: Path) -> tuple[int, int]:
    try:
        head = path.read_bytes()[:24]
    except OSError:
        return (0, 0)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        return (0, 0)
    return struct.unpack(">II", head[16:24])


def _read(path: Path) -> Item | None:
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        item = Item(id=str(d["id"]), name=str(d["name"]), sprite=str(d["sprite"]), by=str(d["by"]),
                    why=str(d.get("why") or ""), chapter=int(d.get("chapter") or 0), stage=int(d.get("stage") or 0),
                    kin=str(d.get("kin") or ""), type=str(d.get("type") or ""), stand_in=bool(d.get("stand_in")))
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if item.by not in BY or item.id != path.stem or ".." in item.sprite:
        return None
    w, h = _png_size(tokens.SYSTEM / item.sprite)
    return Item(**{**asdict(item), "size": (w, h)}) if w and h else None


@functools.lru_cache(maxsize=1)
def catalog() -> dict[str, Item]:
    """Every item file, by id; one that does not read (or whose sprite is missing) is left out."""
    found = (_read(p) for p in sorted(DIR.glob("*.json"))) if DIR.is_dir() else ()
    return {i.id: i for i in found if i is not None}


# -- what the town earned (.orkcraft/items.json) -----------------------------------------------------------------

def _load(root: Path) -> dict:
    try:
        data = json.loads((Path(root) / STATE).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def earned(root: Path) -> dict[str, dict]:
    """{item id: {"at": ISO day, "why": words}} for every earned item (the starter set is not listed)."""
    got = _load(root).get("earned")
    return {str(k): v for k, v in got.items() if isinstance(v, dict)} if isinstance(got, dict) else {}


def earn(root: Path, item_id: str, why: str = "", at: dt.date | None = None) -> bool:
    """Earn an item once; True when it is new. Nothing is said: it lands in the inventory quietly (§14 rule 4)."""
    item = catalog().get(item_id)
    if item is None or item.by == START:
        return False
    data = _load(root)
    got = data.get("earned") if isinstance(data.get("earned"), dict) else {}
    if item_id in got:
        return False
    got[item_id] = {"at": (at or dt.date.today()).isoformat(), "why": why or item.why}
    data["earned"] = got
    path = Path(root) / STATE
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(path)
    except OSError:
        return False
    return True


def due(scroll, root: Path, machine, facts: dict | None = None, type_of=None) -> list[tuple[str, str]]:
    """(item id, why) for each item the town's deeds earn now: Mission 1 done, a lean week and a lean month, the
    portrait's stage (the person's class), a building at III. `type_of(building)`: its type (the town's spec knows
    it); by default its preset's id."""
    facts = facts if facts is not None else growth.read_facts(root, dt.datetime.now())
    grown = getattr(machine, "growth", None) or {}
    profile = getattr(machine, "profile", None) or {}
    kin, stage = growth.kin_of(profile), int(grown.get("stage") or 1)
    out = []
    for item in catalog().values():
        if item.by == MISSION and int(facts.get("chapters") or 0) >= max(item.chapter, 1):
            out.append((item.id, item.why))
        elif item.by == LEAN_WEEK and (facts.get("lean") or "lean" in (grown.get("deeds") or {})):
            out.append((item.id, item.why))
        elif item.by == LEAN_MONTH and int(facts.get("lean_weeks") or 0) >= growth.LEAN_MONTH:
            out.append((item.id, item.why))
        elif item.by == STAGE and item.kin == kin and stage >= max(item.stage, 2):
            out.append((item.id, f"{growth.stage_name(profile, item.stage or 2)}: your portrait's stage {item.stage or 2}"))
    own = {i.type for i in catalog().values() if i.by == LEVEL and i.type}
    for b in scroll.buildings:
        if b.demolished or (b.level or 0) < 3:
            continue
        kind = type_of(b) if type_of else b.preset_ref.split(":", 1)[-1]
        target = f"level3-{kind}" if kind in own else next((i.id for i in catalog().values() if i.by == LEVEL and not i.type), "")
        if target:
            out.append((target, f"{b.title} at III"))
    return out


def settle(scroll, root: Path, machine, facts: dict | None = None, now: dt.datetime | None = None,
           type_of=None) -> list[str]:
    """Earn what the town's deeds earn now; the ids earned just now."""
    day = (now or dt.datetime.now()).date()
    return [item_id for item_id, why in due(scroll, root, machine, facts, type_of) if earn(root, item_id, why, day)]


# -- the inventory and the grass ----------------------------------------------------------------------------------

def inventory(scroll, root: Path) -> list[dict]:
    """What the panel lists, the earned first (newest first), then the starter set: each item with why it is here and
    how many are left to place (None: as many as the person likes)."""
    got = earned(root)
    placed: dict[str, int] = {}
    for p in scroll.items:
        placed[p["item"]] = placed.get(p["item"], 0) + 1
    rows = []
    for item in catalog().values():
        if item.by != START and item.id not in got:
            continue
        mine = got.get(item.id) or {}
        rows.append({"id": item.id, "name": item.name, "sprite": item.sprite, "size": list(item.size),
                     "why": (f"Earned: {mine.get('why') or item.why}, {_day(mine.get('at'))}" if item.by != START
                             else item.why),
                     "at": mine.get("at", ""), "start": item.by == START, "stand_in": item.stand_in,
                     "left": None if item.by == START else max(0, 1 - placed.get(item.id, 0))})
    rows.sort(key=lambda r: r["name"])
    rows.sort(key=lambda r: r["at"], reverse=True)       # the earned, newest first; the starter set (no day) after
    return rows


def _day(iso: str | None) -> str:
    try:
        d = dt.date.fromisoformat(str(iso))
    except ValueError:
        return ""
    return f"{d.day} {d.strftime('%B')}"


def _cell(v) -> int:
    if not isinstance(v, int) or isinstance(v, bool) or abs(v) > REACH:
        raise ValueError("a cell of the camp's grid is a whole number near the camp")
    return v


def place(scroll, root: Path, item_id: str, orkspace: str, x: int, y: int) -> dict:
    """A copy of an item on the grass of an orkspace's camp. ValueError: not the person's, none left, or no orkspace."""
    item = catalog().get(item_id)
    if item is None:
        raise ValueError(f"No item {item_id!r}")
    if scroll.orkspace(orkspace) is None:
        raise ValueError(f"No orkspace {orkspace!r}")
    if item.by != START:
        if item_id not in earned(root):
            raise ValueError(f"{item.name} is not earned yet")
        if any(p["item"] == item_id for p in scroll.items):
            raise ValueError(f"{item.name} already stands in the camp")
    if len(scroll.items) >= PLACED_MAX:
        raise ValueError(f"The camp holds {PLACED_MAX} items at most")
    row = {"id": uuid.uuid4().hex[:10], "item": item_id, "orkspace": orkspace, "x": _cell(x), "y": _cell(y)}
    scroll.items.append(row)
    return row


def _placed(scroll, placed_id: str) -> dict:
    row = next((p for p in scroll.items if p["id"] == placed_id), None)
    if row is None:
        raise ValueError(f"No placed item {placed_id!r}")
    return row


def move(scroll, placed_id: str, x: int, y: int) -> dict:
    row = _placed(scroll, placed_id)
    row["x"], row["y"] = _cell(x), _cell(y)
    return row


def remove(scroll, placed_id: str) -> None:
    """Back to the inventory (an earned one can be placed again)."""
    row = _placed(scroll, placed_id)
    scroll.items.remove(row)


def _save(root: Path, data: dict) -> None:
    path = Path(root) / STATE
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(path)
    except OSError:
        pass


def back(scroll, root: Path, placed_id: str, because: str = "") -> str:
    """A building (or a row moving) took a placed item's cell: it goes back to the inventory quietly, keeping why it
    was earned, and a note waits for the Items panel. The note's words."""
    row = _placed(scroll, placed_id)
    scroll.items.remove(row)
    item = catalog().get(row["item"])
    name = item.name if item else row["item"]
    who = name if name.startswith("The ") else f"The {name}"
    text = (f"{who} went back to your items when the {because} was built" if because
            else f"{who} went back to your items: something now stands where it was")
    data = _load(root)
    data["notes"] = ([n for n in data.get("notes") or [] if isinstance(n, str)] + [text])[-5:]
    _save(root, data)
    return text


def notes(root: Path) -> list[str]:
    got = _load(root).get("notes")
    return [n for n in got if isinstance(n, str)] if isinstance(got, list) else []


def seen(root: Path) -> None:
    data = _load(root)
    if data.pop("notes", None) is not None:
        _save(root, data)
