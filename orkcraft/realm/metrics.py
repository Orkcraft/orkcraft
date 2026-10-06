"""🪨 What the Tally Crag charts.

Two stores, both under `.orkcraft/`:

    ledger.jsonl           one line per run of any orc, chain, Mill, Barracks task, Clan Fire review
                           (written by the app): when, building, outcome, $, tokens
    crag/<id>/samples.jsonl  what a Crag sampled once a minute: limits, busy orcs, CPU, road numbers

Sources (the `source` setting):

    limits   % of each claude / agy / codex quota used (sampled)       horizontal: per quota
    spend    $ of the runs                            (ledger)         horizontal: per building
    tokens   tokens of the runs                       (ledger)         horizontal: per building
    runs     runs, ✓ and ✗                            (ledger)         horizontal: per building
    orcs     busy orcs                                (sampled)        horizontal: now / avg / max
    tasks    tasks per column of every Task Fields    (read now)       horizontal: per column
    cpu      the machine's load average (1 min)       (sampled)
    road     the first number in each cart that arrives

Vertical bars are the source over time (buckets of the window); horizontal bars break it down.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

LEDGER = Path(".orkcraft") / "ledger.jsonl"
WINDOWS = {"1h": (dt.timedelta(hours=1), 12), "24h": (dt.timedelta(hours=24), 24), "7d": (dt.timedelta(days=7), 14)}
SOURCES = ("limits", "spend", "tokens", "runs", "orcs", "tasks", "cpu", "road")
UNITS = {"limits": "% used", "spend": "$", "tokens": "tok", "runs": "runs", "orcs": "orks", "tasks": "tasks",
         "cpu": "load", "road": ""}
NUMBER = re.compile(r"-?\d+(?:[.,]\d+)?")
KEEP_DAYS = 8


@dataclass
class Series:
    source: str
    unit: str
    buckets: list[tuple[str, float]] = field(default_factory=list)    # vertical: (label, value) in time order
    parts: list[tuple[str, float]] = field(default_factory=list)      # horizontal: (label, value)
    now: float | None = None
    scale: float | None = None           # a fixed top (100 for %), else the largest value
    note: str = ""


def _parse(ts: str) -> dt.datetime | None:
    try:
        return dt.datetime.fromisoformat(ts)
    except (TypeError, ValueError):
        return None


def _read(path: Path, since: dt.datetime) -> list[dict]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        at = _parse(row.get("at", ""))
        if at is not None and at >= since:
            row["_at"] = at
            out.append(row)
    return out


# -- writing ----------------------------------------------------------------------------------------------

def record_run(repo_root: Path, building: str, outcome: str, cost: float | None, tokens: int | None,
               now: dt.datetime | None = None) -> None:
    path = repo_root / LEDGER
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {"at": (now or dt.datetime.now()).isoformat(timespec="seconds"), "building": building, "outcome": outcome,
           "cost": round(cost, 4) if cost else 0.0, "tokens": int(tokens or 0)}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def sample(state_dir: Path, source: str, value: float, by: str = "", now: dt.datetime | None = None) -> None:
    path = state_dir / "samples.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {"at": (now or dt.datetime.now()).isoformat(timespec="seconds"), "source": source, "value": round(value, 4)}
    if by:
        row["by"] = by
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def first_number(text: str) -> float | None:
    m = NUMBER.search(text or "")
    return float(m.group(0).replace(",", ".")) if m else None


# -- reading ----------------------------------------------------------------------------------------------

def _bucket_labels(now: dt.datetime, window: str) -> tuple[list[dt.datetime], dt.timedelta]:
    span, n = WINDOWS.get(window, WINDOWS["24h"])
    step = span / n
    start = now - span
    return [start + step * i for i in range(n)], step


def _label(t: dt.datetime, window: str) -> str:
    return t.strftime("%a" if window == "7d" else "%H:%M")


def _buckets(rows: list[dict], key, now: dt.datetime, window: str, agg: str = "sum") -> list[tuple[str, float]]:
    starts, step = _bucket_labels(now, window)
    vals: list[list[float]] = [[] for _ in starts]
    for r in rows:
        i = int((r["_at"] - starts[0]) / step)
        if 0 <= i < len(starts):
            vals[i].append(key(r))
    out = []
    for t, v in zip(starts, vals):
        x = (sum(v) if agg == "sum" else max(v) if agg == "max" else sum(v) / len(v)) if v else 0.0
        out.append((_label(t, window), round(x, 4)))
    return out


def _by(rows: list[dict], key, field_: str = "building") -> list[tuple[str, float]]:
    acc: dict[str, float] = {}
    for r in rows:
        acc[r.get(field_) or "?"] = acc.get(r.get(field_) or "?", 0.0) + key(r)
    return sorted(((k, round(v, 4)) for k, v in acc.items()), key=lambda kv: kv[1], reverse=True)


def series(source: str, repo_root: Path, state_dir: Path, window: str = "24h", now: dt.datetime | None = None,
           tasks: dict[str, int] | None = None) -> Series:
    now = now or dt.datetime.now()
    span = WINDOWS.get(window, WINDOWS["24h"])[0]
    since = now - span
    s = Series(source, UNITS.get(source, ""))
    if source in ("spend", "tokens", "runs"):
        rows = _read(repo_root / LEDGER, since)
        key = {"spend": lambda r: float(r.get("cost") or 0), "tokens": lambda r: float(r.get("tokens") or 0),
               "runs": lambda r: 1.0}[source]
        s.buckets = _buckets(rows, key, now, window)
        s.parts = _by(rows, key)
        if source == "runs":
            bad = sum(1 for r in rows if r.get("outcome") == "error")
            s.note = f"{len(rows) - bad} ✓ · {bad} ✗"
        s.now = round(sum(key(r) for r in rows), 4)
        return s
    if source == "tasks":
        s.parts = list((tasks or {}).items())
        s.now = float(sum((tasks or {}).values()))
        s.note = "" if tasks else "no Task Fields in this camp"
        return s
    rows = [r for r in _read(state_dir / "samples.jsonl", since) if r.get("source") == source]
    if source == "limits":
        s.scale = 100.0
        s.buckets = _buckets(rows, lambda r: float(r["value"]), now, window, "max")
        latest: dict[str, float] = {}
        for r in rows:
            latest[r.get("by") or "?"] = float(r["value"])
        s.parts = sorted(latest.items())
        s.now = max(latest.values()) if latest else None
        s.note = "" if rows else "no quota read yet"
        return s
    s.buckets = _buckets(rows, lambda r: float(r["value"]), now, window, "max" if source == "orcs" else "avg")
    vals = [float(r["value"]) for r in rows]
    if vals:
        s.now = vals[-1]
        s.parts = [("now", vals[-1]), ("avg", round(sum(vals) / len(vals), 2)), ("max", max(vals))]
    else:
        s.note = "nothing sampled yet" if source != "road" else "no number has come by road yet"
    return s


def prune(state_dir: Path, now: dt.datetime | None = None) -> None:
    """Keep the samples of the last KEEP_DAYS days."""
    path = state_dir / "samples.jsonl"
    rows = _read(path, (now or dt.datetime.now()) - dt.timedelta(days=KEEP_DAYS))
    if path.exists():
        path.write_text("".join(json.dumps({k: v for k, v in r.items() if k != "_at"}) + "\n" for r in rows),
                        encoding="utf-8")


# -- a Crag's charts --------------------------------------------------------------------------------------
#
# A Crag is a dashboard: each line of its `charts` setting is one chart, written by its keeper from
# what the person asked in plain words:
#
#     Spend today = spend 24h warn 1 crit 5 all
#     cpu 1h horizontal full
#
# `<title> =` is optional; then the source, and in any order a window, an orientation, `warn N`,
# `crit N`, and where it shows: `all` (the hut too), `command` (the Command Card and the dashboard)
# or `full` (the dashboard only). A Crag without `charts` has one chart, from its old settings.

SHOWS = ("all", "command", "full")
NAMES = {"orcs": "busy orks"}           # how a source is said where it has no title
ORIENTATIONS = ("vertical", "horizontal")


@dataclass
class Chart:
    source: str
    title: str = ""
    window: str = "24h"
    orientation: str = "vertical"
    warn: float | None = None
    crit: float | None = None
    show: str = "all"

    @property
    def name(self) -> str:
        return self.title or NAMES.get(self.source, self.source)

    def shows_in(self, view: str) -> bool:
        """`closed` (the hut), `command` (the Command Card) or `full` (the dashboard)."""
        if view == "closed":
            return self.show == "all"
        if view == "command":
            return self.show in ("all", "command")
        return True


def _num(word: str) -> float | None:
    try:
        return float(word.replace(",", "."))
    except ValueError:
        return None


def parse_chart(line: str) -> tuple[Chart | None, str]:
    """One `charts` line → (its chart, "") or (None, why not)."""
    title, _, rest = line.rpartition("=") if "=" in line else ("", "", line)
    words = rest.split()
    if not words or words[0] not in SOURCES:
        return None, f"{line.strip()[:40]!r}: start with a source ({', '.join(SOURCES)})"
    c = Chart(words[0], " ".join(title.split())[:40])
    i = 1
    while i < len(words):
        w = words[i]
        if w in WINDOWS:
            c.window = w
        elif w in ORIENTATIONS:
            c.orientation = w
        elif w in SHOWS:
            c.show = w
        elif w in ("warn", "crit") and i + 1 < len(words) and _num(words[i + 1]) is not None:
            setattr(c, w, _num(words[i + 1]))
            i += 1
        else:
            return None, f"{line.strip()[:40]!r}: {w!r} is not a window, orientation, warn N, crit N or {'/'.join(SHOWS)}"
        i += 1
    return c, ""


def parse_charts(lines: list) -> tuple[list[Chart], list[str]]:
    charts, errors = [], []
    for line in lines:
        c, why = parse_chart(str(line))
        if c is None:
            errors.append(why)
        else:
            charts.append(c)
    return charts, errors


def chart_line(c: Chart) -> str:
    """A chart as its `charts` line (what `parse_chart` reads back)."""
    def fmt(x: float) -> str:
        return f"{x:g}"
    words = [c.source, c.window, c.orientation]
    words += [f"warn {fmt(c.warn)}"] if c.warn is not None else []
    words += [f"crit {fmt(c.crit)}"] if c.crit is not None else []
    words.append(c.show)
    return (f"{c.title} = " if c.title else "") + " ".join(words)
