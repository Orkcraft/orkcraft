"""🥁 The War Drum's one timeline: the person's meetings, the town's scheduled runs and the moments its
limits are likely to be reached, side by side.

    jobs(scroll, specs)                    every schedule in the town: a Watchtower's `cron`, a
                                           Workshop's `schedule`, a steward's cron trigger
    sample(path, now, run, spent, ctx, who)  the spend and the fullest session's context, kept over time
    limits(rows, gold_limit, lumber_limit, now)  each limit, its burn rate and ≈ when it is reached
    timeline(events, jobs, limits, now, until)   all three kinds as `Beat`s in time order
    ahead(beats, n)                        the next `n`, each kind there when it has one

A limit's moment is an estimate: the burn of the last hour (else of the whole run) carried on in a
straight line. Faces mark it as approximate (≈) and say each kind by its role (`TONE`), never by a
colour. Pure module, no face.
"""
from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass
from pathlib import Path

from orkcraft.realm import daybook, steward, watch

KINDS = ("meeting", "schedule", "limit")
TONE = {"meeting": "text", "schedule": "accent", "limit": "wait"}     # colour roles (docs/design-system.md)
MARK = {"meeting": "▪", "schedule": "↻", "limit": "≈"}                # the same, without colour
WINDOW = dt.timedelta(hours=1)           # the burn rate is read over this much of the past
MIN_SPAN = dt.timedelta(minutes=5)       # … when it holds at least this much
KEEP = dt.timedelta(hours=12)            # samples older than this go
EVERY = dt.timedelta(minutes=5)          # an unchanged value is sampled again this often
MAX_ROWS = 600
PER_JOB = 8                              # runs of one job on the timeline; more is said as "+N"


@dataclass(frozen=True)
class Job:
    ref: str            # its building's id ("stewards" for the stewards' watch together)
    title: str          # the building's title, or what runs
    expr: str           # as written: `every 15m`, `daily 05:00`, a 5-field cron
    what: str           # watch | script | steward
    count: int = 1      # stewards that share this schedule


@dataclass(frozen=True)
class Limit:
    what: str                       # gold | lumber
    value: float                    # where it stands ($, tokens)
    limit: float
    rate: float = 0.0               # per hour; 0 when flat or unknown
    at: dt.datetime | None = None   # ≈ when it is reached at this rate; None: not at this rate
    reached: bool = False
    who: str = ""                   # lumber: the session it is about

    @property
    def share(self) -> float:
        return self.value / self.limit if self.limit > 0 else 0.0


@dataclass(frozen=True)
class Beat:
    kind: str                       # meeting | schedule | limit
    at: dt.datetime
    title: str
    ref: str = ""                   # the meeting's id, the job's building, the limit's name
    detail: str = ""                # the schedule as written, "$2.60 / $5.00", …
    end: dt.datetime | None = None
    approx: bool = False            # an estimate (a limit)
    now: bool = False               # the meeting on now
    reached: bool = False           # a limit already reached
    more: int = 0                   # a job's further runs left off the timeline

    @property
    def tone(self) -> str:
        return "error" if self.reached else TONE[self.kind]


# -- the town's schedules ------------------------------------------------------------------------------

def jobs(scroll, specs: dict[str, dict]) -> list[Job]:
    """Every schedule of a standing building: its own timer (a Watchtower's `cron`, a Workshop's
    `schedule`) and its steward's cron trigger (tui/garrison.py runs those). The stewards that share
    a schedule are one job."""
    from orkcraft.realm import catalog
    out: list[Job] = []
    stewards: dict[str, list[str]] = {}
    for b in getattr(scroll, "buildings", []) or []:
        if b.demolished:
            continue
        spec = specs.get(b.id) or {}
        cfg = spec.get("config") or {}
        kind = catalog.type_of(spec).id if spec else ""
        own = {"watchtower": ("cron", "watch"), "workshop": ("schedule", "script")}.get(kind)
        if own and str(cfg.get(own[0]) or "").strip() and watch.schedule_ok(str(cfg[own[0]])):
            out.append(Job(b.id, b.title, str(cfg[own[0]]).strip(), own[1]))
        st = b.garrison.steward
        if st is not None and st.trigger.get("type") == "cron" and st.trigger.get("expression"):
            stewards.setdefault(str(st.trigger["expression"]), []).append(b.title)
    for expr, titles in stewards.items():
        if watch.schedule_ok(expr):
            title = f"{titles[0]} steward" if len(titles) == 1 else f"{len(titles)} stewards"
            out.append(Job("stewards", title, expr, "steward", len(titles)))
    return out


def next_runs(expr: str, after: dt.datetime, until: dt.datetime, cap: int = PER_JOB) -> tuple[list[dt.datetime], int]:
    """The runs of `expr` after `after` up to `until`: the first `cap` of them and how many more."""
    cron = watch.to_schedule(expr)
    runs: list[dt.datetime] = []
    more, t = 0, after
    while t < until:
        nxt = steward.next_due(cron, t, until - t)
        if nxt is None or nxt > until:
            break
        if len(runs) < cap:
            runs.append(nxt)
        else:
            more += 1
            if more > 999:
                break
        t = nxt
    return runs, more


# -- the limits ----------------------------------------------------------------------------------------

def read_samples(path: Path, run: str | None = None) -> list[dict]:
    """The samples kept at `path`, oldest first; only `run`'s when it is given."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for line in lines:
        try:
            row = json.loads(line)
            row["_at"] = dt.datetime.fromisoformat(row["at"])
        except (ValueError, KeyError, TypeError):
            continue
        if run is None or row.get("run") == run:
            out.append(row)
    return out


def sample(path: Path, now: dt.datetime, run: str, spent: float, ctx: int | None, who: str = "") -> bool:
    """Keep where spend and context stand now: a new row when either moved, or `EVERY` after the last.
    Rows older than `KEEP` and of another run go. True when a row was written."""
    rows = read_samples(path, run)
    last = rows[-1] if rows else None
    row = {"at": now.isoformat(timespec="seconds"), "run": run, "spent": round(float(spent), 4),
           "ctx": int(ctx or 0), "who": who}
    if last and (last["spent"], last.get("ctx", 0), last.get("who", "")) == (row["spent"], row["ctx"], who) \
            and now - last["_at"] < EVERY:
        return False
    keep = [r for r in rows if now - r["_at"] <= KEEP][-(MAX_ROWS - 1):]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps({k: v for k, v in r.items() if k != "_at"}) + "\n" for r in keep + [row]),
                    encoding="utf-8")
    return True


def rate(points: list[tuple[dt.datetime, float]], now: dt.datetime) -> float:
    """Units per hour: over the last `WINDOW` when it holds `MIN_SPAN`, else over all the points."""
    if len(points) < 2:
        return 0.0
    recent = [p for p in points if now - p[0] <= WINDOW]
    use = recent if len(recent) >= 2 and recent[-1][0] - recent[0][0] >= MIN_SPAN else points
    (t0, v0), (t1, v1) = use[0], use[-1]
    hours = (t1 - t0).total_seconds() / 3600
    return (v1 - v0) / hours if hours > 0 else 0.0


def project(what: str, points: list[tuple[dt.datetime, float]], limit: float, now: dt.datetime,
            who: str = "") -> Limit:
    """Where a limit stands and ≈ when it is reached, the rate carried on in a straight line."""
    value = points[-1][1] if points else 0.0
    if limit <= 0:
        return Limit(what, value, limit, who=who)
    if value >= limit:
        when = next((t for t, v in points if v >= limit), now)
        return Limit(what, value, limit, 0.0, when, True, who)
    r = rate(points, now)
    if r <= 0:
        return Limit(what, value, limit, 0.0, None, False, who)
    at = points[-1][0] + dt.timedelta(hours=(limit - value) / r)
    return Limit(what, value, limit, r, max(at, now).replace(microsecond=0), False, who)


def limits(rows: list[dict], gold_limit: float, lumber_limit: float, now: dt.datetime) -> list[Limit]:
    """The 🪙 spend limit of the run and the 🪵 context limit of the fullest session, from the samples."""
    gold = [(r["_at"], float(r.get("spent") or 0)) for r in rows]
    who = rows[-1].get("who", "") if rows else ""
    lumber = [(r["_at"], float(r.get("ctx") or 0)) for r in rows if r.get("who", "") == who]
    return [project("gold", gold, gold_limit, now), project("lumber", lumber, lumber_limit, now, who)]


def amount(what: str, value: float) -> str:
    """`$2.60` for spend, `92k` for context."""
    if what == "gold":
        return f"${value:.2f}"
    from orkcraft.sources.telemetry import fmt_tokens
    return fmt_tokens(int(value))


# -- the timeline ----------------------------------------------------------------------------------------

def timeline(events: list, job_list: list[Job], limit_list: list[Limit], now: dt.datetime,
             until: dt.datetime) -> list[Beat]:
    """The meetings still to come or on now, each job's runs and each limit's moment, from `now` to
    `until`, in time order (a limit already reached stands at `now`)."""
    cur, _, _ = daybook.now_and_next(events, now)
    beats: list[Beat] = []
    for e in events:
        if e.all_day or not isinstance(e.start, dt.datetime):
            continue
        end = daybook._end(e)
        if (end or e.start) > now and e.start < until:
            beats.append(Beat("meeting", e.start, e.summary, daybook.meet_id(e), e.location, end, now=e is cur))
    for j in job_list:
        runs, more = next_runs(j.expr, now, until)
        for i, t in enumerate(runs):
            beats.append(Beat("schedule", t, j.title, j.ref, j.expr, more=more if i == len(runs) - 1 else 0))
    for lim in limit_list:
        if lim.at is None or lim.at > until:
            continue
        detail = f"{amount(lim.what, lim.value)} / {amount(lim.what, lim.limit)}"
        beats.append(Beat("limit", max(lim.at, now) if lim.reached else lim.at, lim.what, lim.what, detail,
                          approx=not lim.reached, reached=lim.reached))
    order = {k: i for i, k in enumerate(KINDS)}
    return sorted(beats, key=lambda b: (b.at, order[b.kind]))


def ahead(beats: list[Beat], n: int) -> list[Beat]:
    """The next `n` beats in time order; a kind that has one but would be left out takes the place
    of the latest beat of a kind that has more than one."""
    picked = list(beats[:n])
    for kind in KINDS:
        if any(b.kind == kind for b in picked):
            continue
        first = next((b for b in beats if b.kind == kind), None)
        if first is None:
            continue
        counts = {k: sum(b.kind == k for b in picked) for k in KINDS}
        drop = next((b for b in reversed(picked) if counts[b.kind] > 1), None)
        if drop is None and len(picked) >= n:
            continue
        if drop is not None and len(picked) >= n:
            picked.remove(drop)
        picked.append(first)
    order = {k: i for i, k in enumerate(KINDS)}
    return sorted(picked, key=lambda b: (b.at, order[b.kind]))
