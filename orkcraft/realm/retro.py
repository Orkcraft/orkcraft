"""🗓 The Town retro's survey: a few results of the week for the operator to rate
(design: docs/design/retros-and-goals.md §4).

When the operator pressed no 👍 / 👎 in the last 7 days, the Town retro first shows at most `MAX`
past results — in all, one per building — the ones most worth knowing about, in this order:

    changed    a building the orcs or the operator changed this week (does the change hold?)
    quality    a 💎 building with no rating this week
    failed     a run that failed, alerted or was escalated
    pressure   the building that eats most of the camp / the limit — the next Building retro's pick

    samples(root, "brief")             its recorded runs, newest first (Workshop, Mill, jobs, agents)
    pick(root, scroll, camp, now)      the survey: [Sample] with `why`
"""
from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass
from pathlib import Path

from orkcraft.realm import evolution, feedback, pressure

MAX = 4
DAYS = 7
CUT = 240
BAD = ("failed", "error", "alert", "escalated", "interrupted")
WHY = {"changed": "changed this week", "quality": "💎 quality, not rated this week",
       "failed": "a run went wrong", "pressure": "eats the most of the camp"}


@dataclass
class Sample:
    building: str
    ts: str
    input: str
    output: str
    outcome: str = "done"
    why: str = ""

    def as_output(self) -> dict:
        """What 👍 keeps as a reference / 👎 as the incident's output."""
        return {"ts": self.ts, "event": "retro", "value": self.output}


def _cut(value) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    text = " ".join(str(text or "").split())
    return text if len(text) <= CUT else text[:CUT - 1] + "…"


def _rows(path: Path, limit: int = 50) -> list[dict]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()[-limit:]
    except OSError:
        return []
    out = []
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def _outcome(row: dict) -> str:
    if "code" in row:                                     # a Workshop run
        code = row.get("code")
        if code == 0:
            return "done"
        if code == 4:
            return "alert"
        if code == 3:
            return "done" if row.get("steward") else "escalated"
        return "failed"
    return str(row.get("outcome") or "done")


def samples(root: Path, building: str, since: str = "") -> list[Sample]:
    """The building's recorded runs since `since`, newest first: Workshop / Mill / job logs
    (`.orkcraft/<kind>/<id>/runs.jsonl`) and its agents' examples (`history/handlers/<id>/`)."""
    base = Path(root) / ".orkcraft"
    out: list[Sample] = []
    for path in base.glob(f"*/{building}/runs.jsonl"):
        for r in _rows(path):
            ts = str(r.get("at") or r.get("ended") or r.get("started") or r.get("ts") or "")
            got = r.get("input") if r.get("input") not in (None, "") else r.get("inputs") or r.get("title") or ""
            gave = r.get("steward") or r.get("out") or r.get("result") or r.get("output") or r.get("error") or r.get("err") or ""
            out.append(Sample(building, ts, _cut(got), _cut(gave), _outcome(r)))
    for path in (base / "history" / "handlers" / building).glob("*.jsonl"):
        for r in _rows(path):
            out.append(Sample(building, str(r.get("ts") or ""), _cut(r.get("inputs") or ""), _cut(r.get("output") or "")))
    out = [s for s in out if s.ts >= since and (s.input or s.output)]
    if not out:                                           # at least its last result, when it is recent
        last = feedback.last_output(Path(root), building)
        if last and str(last.get("ts", "")) >= since:
            out.append(Sample(building, str(last.get("ts")), "", _cut(last.get("value", ""))))
    return sorted(out, key=lambda s: s.ts, reverse=True)


def needed(root: Path, now: dt.datetime | None = None) -> bool:
    """The survey runs only when the operator rated nothing in the last 7 days."""
    now = now or dt.datetime.now()
    return not feedback.rated_since(Path(root), (now - dt.timedelta(days=DAYS)).isoformat(timespec="seconds"))


def pick(root: Path, scroll, camp: pressure.Camp | None = None, now: dt.datetime | None = None,
         limit: int = MAX) -> list[Sample]:
    """At most `limit` samples, one per building, the most useful first (see the module's doc)."""
    root = Path(root)
    now = now or dt.datetime.now()
    since = (now - dt.timedelta(days=DAYS)).isoformat(timespec="seconds")
    live = [b for b in getattr(scroll, "buildings", []) if not b.demolished] if scroll is not None else []
    ids = [b.id for b in live]
    cache: dict[str, list[Sample]] = {}

    def runs(bid: str) -> list[Sample]:
        if bid not in cache:
            cache[bid] = samples(root, bid, since)
        return cache[bid]

    chosen: list[Sample] = []

    def take(bid: str, why: str, bad_only: bool = False) -> None:
        if len(chosen) >= limit or any(s.building == bid for s in chosen):
            return
        pool = [s for s in runs(bid) if s.outcome in BAD] if bad_only else runs(bid)
        if pool:
            s = pool[0]
            s.why = WHY[why]
            chosen.append(s)

    changed = [c.building for c in sorted(evolution.load(root), key=lambda c: c.ts, reverse=True) if c.ts >= since]
    for bid in dict.fromkeys(changed):
        if bid in ids:
            take(bid, "changed")
    for b in live:                                        # nothing is rated this week when the survey runs
        if getattr(b, "goal", "") == "quality":
            take(b.id, "quality")
    for bid in ids:
        take(bid, "failed", bad_only=True)
    if camp is None:
        camp = pressure.measure(root, None, now)
    for bid in camp.heaviest(len(camp.buildings)):
        if bid in ids:
            take(bid, "pressure")
    return chosen
