"""📍 Places: a paired phone says it came to a place or left it (docs/design/phone-places.md).

    places.parse(config)                      → the Watchtower's places: [Place("home", "chains", …)]
    places.check(body, names, device)         → a Report, or PlaceError with what the phone is told
    places.History(places.history_file(root)) → what was heard, on this machine, for `keep` days

The phone works the place out itself: a place here is a name and how freely its news is acted on,
never where it is. A report carries the name, `arrived` or `left`, when the phone saw it and the phone's
own id (a retry is heard once). The history is a history of where a person was: it is kept beside the
machine's settings (`settings.path()`), never in the project or its git, and only `keep_days` long.

A place's cart says what the road was made for (`say`), never the place or the time: the steward that
takes it on reads no more than that. The road knows the place by its route (`route`): `home-arrived`.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from orkcraft import autonomy, settings

CHANGES = ("arrived", "left")
NAME = re.compile(r"^[a-z0-9][a-z0-9_-]{0,23}$")
NAME_HINT = "a short name in small letters: home, office, gym"
LIMIT = 10                       # places a tower keeps (a building's list setting holds ten lines)
SAY_LIMIT = 200
SHELF_H = 2.0                    # a report older than this is kept but sends no cart
SHELF_MAX_H = 48.0
CLOCK_MIN = 10                   # Apply if unanswered: the cart goes this long after the question
KEEP_DAYS = 7                    # how long the history is kept
KEEP_MAX_DAYS = 365
FUTURE_S = 300                   # a phone's clock may run ahead this much
ID = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
SAY = {"arrived": "You may start the evening's work.", "left": "Nobody is at the desk now."}


class PlaceError(ValueError):
    """A report refused; its text is what the phone is told."""


@dataclass(frozen=True)
class Place:
    name: str
    autonomy: str = "chains"         # chains: Propose only · clock: Apply if unanswered · free: Apply at once
    shelf_h: float = SHELF_H
    say: str = ""                    # what its cart says ("" the default of its change)

    def text(self, change: str) -> str:
        return self.say or SAY.get(change, "")

    def as_dict(self) -> dict:
        return {"name": self.name, "autonomy": self.autonomy, "shelf_h": self.shelf_h, "say": self.say}

    def line(self) -> str:
        """As the tower's settings keep it: `home autonomy=clock shelf=2 say=You may start.` (`say` last)."""
        out = [self.name]
        if self.autonomy != "chains":
            out.append(f"autonomy={self.autonomy}")
        if self.shelf_h != SHELF_H:
            out.append(f"shelf={self.shelf_h:g}")
        if self.say:
            out.append(f"say={self.say}")
        return " ".join(out)


@dataclass(frozen=True)
class Report:
    id: str
    place: str
    change: str
    at: str                          # when the phone saw it, local time, ISO
    device: str = ""                 # the paired phone's name
    device_id: str = ""              # …and its id (Forget deletes its reports)


def clean_name(name: object) -> str:
    """A place's name as kept: small letters, digits, - and _; "" when nothing is left."""
    text = re.sub(r"[^a-z0-9_-]+", "-", str(name or "").strip().lower()).strip("-_")
    return text[:24] if NAME.match(text[:24] or "") else ""


def _number(value: object, default: float, low: float, high: float) -> float:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return default
    return min(high, max(low, n))


def _fields(line: str) -> dict:
    """`home autonomy=clock shelf=2 say=You may start.` → {"name", "autonomy", "shelf_h", "say"}."""
    head, _, say = line.partition(" say=")
    if head.startswith("say="):
        head, say = "", head[4:]
    words = head.split()
    out: dict = {"name": words[0] if words else "", "say": say}
    for w in words[1:]:
        key, _, value = w.partition("=")
        out[{"shelf": "shelf_h"}.get(key, key)] = value
    return out


def place_of(raw: object) -> Place | None:
    """One place of the settings: a line (`home autonomy=clock shelf=2 say=…`) or, from the page,
    {"name", "autonomy", "shelf_h", "say"}."""
    raw = _fields(raw) if isinstance(raw, str) else raw
    if not isinstance(raw, dict):
        return None
    name = clean_name(raw.get("name"))
    if not name:
        return None
    level = str(raw.get("autonomy") or "chains")
    say = " ".join(str(raw.get("say") or "").split())[:SAY_LIMIT]
    return Place(name, level if level in autonomy.WORDS else "chains",
                 _number(raw.get("shelf_h"), SHELF_H, 0.25, SHELF_MAX_H), say)


def parse(config: dict) -> list[Place]:
    """The tower's places, in their order, each name once."""
    out: list[Place] = []
    raw = config.get("places")
    for item in raw if isinstance(raw, list) else []:
        p = place_of(item)
        if p is not None and all(o.name != p.name for o in out):
            out.append(p)
    return out[:LIMIT]


def keep_days(config: dict) -> int:
    return int(_number(config.get("places_keep_days"), KEEP_DAYS, 1, KEEP_MAX_DAYS))


def route(place: str, change: str) -> str:
    """The route a place's cart takes: a road laid on `watch.place#home-arrived` takes only that."""
    return f"{place}-{change}"


def _when(value: object, now: dt.datetime) -> dt.datetime:
    """A phone's time (ISO, with its zone or without) as local time; refused when it is not a time or runs ahead."""
    try:
        when = dt.datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        raise PlaceError("at is not a time: say it as 2026-10-08T19:42:10+02:00") from None
    if when.tzinfo is not None:
        when = when.astimezone().replace(tzinfo=None)
    if (when - now).total_seconds() > FUTURE_S:
        raise PlaceError("at is in the future: check the phone's clock")
    return when


def check(body: object, names: list[str], device: str = "", device_id: str = "",
          now: dt.datetime | None = None) -> Report:
    """A phone's report, checked: a place this town knows, `arrived` or `left`, a time and an id."""
    now = now or dt.datetime.now()
    if not isinstance(body, dict):
        raise PlaceError("Not a place report")
    rid = str(body.get("id") or "")
    if not ID.match(rid):
        raise PlaceError("id is 8 to 64 letters, digits, - or _: the phone's own, the same on a retry")
    name = str(body.get("place") or "").strip().lower()
    if name not in names:
        raise PlaceError(f"No place named {name!r} here: name it in the External listeners first" if name
                         else "place is missing")
    change = str(body.get("change") or "")
    if change not in CHANGES:
        raise PlaceError("change is arrived or left")
    at = _when(body.get("at") or now.isoformat(), now)
    return Report(rid, name, change, at.isoformat(timespec="seconds"), str(device or "")[:60], str(device_id or "")[:32])


def stale(report: Report, place: Place, now: dt.datetime | None = None) -> bool:
    """Older than its place's shelf life: kept, but news no longer."""
    now = now or dt.datetime.now()
    try:
        age = (now - dt.datetime.fromisoformat(report.at)).total_seconds()
    except ValueError:
        return True
    return age > place.shelf_h * 3600


# -- the history, on this machine ---------------------------------------------------------------------------

def history_file(repo_root: Path) -> Path:
    """`<settings folder>/places/<project>.jsonl`: beside the machine's settings, one file a project."""
    key = hashlib.sha256(str(Path(repo_root).resolve()).encode("utf-8")).hexdigest()[:16]
    return settings.path().parent / "places" / f"{key}.jsonl"


@dataclass
class Heard:
    id: str
    place: str
    change: str
    at: str
    device: str
    device_id: str
    heard: str                        # when the town heard it
    outcome: str                      # sent · asked · waiting · refused · stale · no road · halted


class History:
    def __init__(self, file: Path, keep: int = KEEP_DAYS) -> None:
        self.file, self.keep = file, keep

    def all(self) -> list[Heard]:
        try:
            lines = self.file.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        out = []
        for line in lines:
            try:
                out.append(Heard(**json.loads(line)))
            except (ValueError, TypeError):
                continue
        return out

    def seen(self, rid: str) -> bool:
        return any(h.id == rid for h in self.all())

    def _write(self, rows: list[Heard]) -> None:
        if not rows:
            self.file.unlink(missing_ok=True)
            return
        self.file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.file.with_suffix(".tmp")
        tmp.write_text("".join(json.dumps(asdict(h), ensure_ascii=False) + "\n" for h in rows), encoding="utf-8")
        try:
            tmp.chmod(0o600)
        except OSError:
            pass
        tmp.replace(self.file)

    def add(self, report: Report, outcome: str, now: dt.datetime | None = None) -> Heard:
        now = now or dt.datetime.now()
        h = Heard(report.id, report.place, report.change, report.at, report.device, report.device_id,
                  now.isoformat(timespec="seconds"), outcome)
        self._write(self._fresh(self.all(), now) + [h])
        return h

    def mark(self, rid: str, outcome: str) -> None:
        rows = self.all()
        for h in rows:
            if h.id == rid:
                h.outcome = outcome
        self._write(rows)

    def _fresh(self, rows: list[Heard], now: dt.datetime) -> list[Heard]:
        edge = now - dt.timedelta(days=self.keep)
        out = []
        for h in rows:
            try:
                if dt.datetime.fromisoformat(h.heard) >= edge:
                    out.append(h)
            except ValueError:
                continue
        return out

    def prune(self, now: dt.datetime | None = None) -> int:
        """Drop what is older than `keep` days; how many went."""
        rows = self.all()
        kept = self._fresh(rows, now or dt.datetime.now())
        if len(kept) != len(rows):
            self._write(kept)
        return len(rows) - len(kept)

    def recent(self, n: int = 20) -> list[Heard]:
        return list(reversed(self.all()))[:n]

    def clear(self) -> None:
        self._write([])

    def forget(self, device_id: str) -> int:
        """A phone forgotten: its reports go too. How many."""
        rows = self.all()
        kept = [h for h in rows if h.device_id != device_id]
        if len(kept) != len(rows):
            self._write(kept)
        return len(rows) - len(kept)


def forget_device(device_id: str, folder: Path | None = None) -> int:
    """A phone forgotten (Settings → Phones): its reports go from every project's history on this machine."""
    folder = folder or settings.path().parent / "places"
    try:
        files = sorted(folder.glob("*.jsonl"))
    except OSError:
        return 0
    return sum(History(f).forget(device_id) for f in files)
