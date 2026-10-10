"""🧪 The Test bench's building side for buildings whose work is not code (docs/design/test-bench.md §3.5): a town of
its own on the case's copy of the project, the building raised there as it is in the operator's town, the case's
input given the way its sources would give it, and its result read back in its kit's shape
(realm/bench_kits.py), so the bare AI tool's answer and the building's go through one check.

    bench_kits.RUNS["watchtower"](ctx) → bench.Side

Spend and tokens are read from the copy's own ledger of model calls (`.orkcraft/spend/calls.jsonl`), so every
call counts: the steward's and each ork's.
"""
from __future__ import annotations

import datetime as dt
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from orkcraft import scroll as ts
from orkcraft.core import buildings
from orkcraft.core.town import Town
from orkcraft.realm import bench, bench_kits, builders, checkpoint, steward_models, watch
from orkcraft.sources import telemetry

POLL_S = 0.5
# What points at the operator's own sources, accounts or project: a copy never listens there.
SOURCES_OUT = ("feeds", "host", "gmail", "user_env", "password_env", "folder", "port", "github", "cron",
               "webhook_port", "webhook_secret_env", "repo", "notes", "base", "google", "imports", "wikis", "path")


@dataclass
class Ctx:
    case: bench.Case
    project: Path
    template: dict                       # the operator's building of the type: its config
    tool: str = "main"
    tier: str = ""
    max_spend: float = bench.DEFAULT_MAX_SPEND
    timeout_s: float = 20 * 60
    cancel: threading.Event | None = None
    say: Callable[[str], None] = lambda _line: None
    pool_template: dict = field(default_factory=dict)   # the operator's Agent pool, for a building that hands it work
    orders: str | None = None


def open_town(project: Path) -> Town:
    """A town on the copy whose callbacks take turns, as the window's one thread makes them (a card named by a model
    and one added meanwhile would both write the board's file at once). `town.bench_lock` is held by the bench's own
    calls into it too."""
    checkpoint.ensure(project)
    town = Town(project, auto_commit=False, layout_file=project / ".orkcraft.json")
    lock = threading.RLock()

    def call(fn, *a):
        with lock:
            return fn(*a)

    town.call, town.bench_lock = call, lock
    return town


def raised(town: Town, type_id: str, config: dict):
    spec = buildings.type_spec(town, type_id)
    if spec is None:
        raise ValueError(f"no building type {type_id!r}")
    spec["config"] = {**(spec.get("config") or {}), **{k: v for k, v in config.items() if k not in SOURCES_OUT}}
    built = buildings.raise_spec(town, spec)
    if built is None:
        raise ValueError(f"the {type_id} was refused: " + "; ".join(town.scroll_problems[-3:]))
    return town.worker(built.id)


def on_tool(w, tool: str, tier: str) -> None:
    """Its steward thinks with the bench's AI tool and tier, when the run names them (only on this copy)."""
    if tool in ("", "main") and not tier:
        return
    kind = w.TYPE or w.btype.id

    def runner(use: str, setting: str = ""):
        return builders.tagged(builders.runner_for("" if tool == "main" else tool, tier or None),
                               steward_models.purpose_of(use, kind), w.building_id)

    w.steward_runner = runner


def spent(project: Path, since: dt.datetime) -> tuple[float, int]:
    rows = telemetry.calls(project, since)
    return round(sum(float(r.get("usd") or 0) for r in rows), 4), sum(int(r.get("tokens") or 0) for r in rows)


def wait(ctx: Ctx, side: bench.Side, done: Callable[[], bool], since: dt.datetime, start: float) -> str:
    """Until `done`, or stopped, over the spend limit or the time: "" when done, else why it stopped."""
    while not done():
        if ctx.cancel is not None and ctx.cancel.is_set():
            return "stopped"
        if spent(ctx.project, since)[0] > ctx.max_spend:
            side.cut = True
            return "over its spend limit"
        if time.monotonic() - start > ctx.timeout_s:
            side.cut = True
            return f"over {int(ctx.timeout_s // 60)} minutes"
        time.sleep(POLL_S)
    return ""


def _run(ctx: Ctx, work: Callable[[Town, bench.Side, dt.datetime, float], dict]) -> bench.Side:
    """A town on the copy, `work` in it, then the kit's checks of what it made; the copy's ledger for spend."""
    side, start, since = bench.Side("building", where=str(ctx.project)), time.monotonic(), dt.datetime.now()
    town = open_town(ctx.project)
    try:
        result = work(town, side, since, start)
        if not side.error:
            bench_kits.judged(side, ctx.case, bench_kits.KITS[ctx.case.type], result)
    except (ValueError, RuntimeError, OSError) as e:
        side.error = side.error or str(e)[:500]
    finally:
        town.close()
        side.seconds = round(time.monotonic() - start, 1)
        side.cost, side.tokens = spent(ctx.project, since)
    return side


def _stopped(side: bench.Side, why: str) -> dict:
    side.error = f"stopped: {why}"
    return {}


# -- External listeners ---------------------------------------------------------------------------------------

def run_watchtower(ctx: Ctx) -> bench.Side:
    msgs = ctx.case.inputs.get("messages") or []

    def work(town: Town, side: bench.Side, since: dt.datetime, start: float) -> dict:
        w = raised(town, "watchtower", {**ctx.template, "intent": ctx.case.inputs.get("intent") or "",
                                        "triage": True})
        on_tool(w, ctx.tool, ctx.tier)
        side.model = ctx.tier or w.steward_pick("judge").tier
        at = since.isoformat(timespec="seconds")
        for n, m in enumerate(msgs, 1):
            with town.bench_lock:
                w.add_signal(watch.Signal(at, m.get("source") or "mail", m.get("title") or f"Message {n}",
                                          m.get("body") or "", ref=f"bench-{n}", sender=m.get("sender") or "",
                                          tags=list(m.get("tags") or [])))
            ctx.say(f"message {n} in: {m.get('title', '')}")
        judged = lambda: sum(1 for s in w.signals if s.ref.startswith("bench-")) >= len(msgs) \
            and not w.pending and not w._judging                                       # noqa: E731
        if why := wait(ctx, side, judged, since, start):
            return _stopped(side, why)
        if w.errors.get("intent"):
            side.error = f"the Listener could not judge: {w.errors['intent']}"
        rows = []
        for s in w.signals:
            if s.ref.startswith("bench-"):
                rows.append({"n": int(s.ref[6:]), "kept": s.kept is not False, "importance": s.importance,
                             "answer": s.answer, "why": s.why or (s.sort or {}).get("auto", "")})
                ctx.say(f"#{s.ref[6:]} {'kept' if s.kept is not False else 'left out'}, {s.importance or '—'}: {s.why}"[:200])
        side.how = [f"#{r['n']}: {'kept' if r['kept'] else 'left out'} · {r['importance'] or '—'} · "
                    f"answer {r['answer'] or '—'} · {r['why']}"[:200] for r in sorted(rows, key=lambda r: r["n"])]
        return {"messages": rows}

    return _run(ctx, work)


# -- Task board -----------------------------------------------------------------------------------------------

def run_fields(ctx: Ctx) -> bench.Side:
    from orkcraft.core.workers import scrolls
    from orkcraft.realm import tasklist
    titles, plans = ctx.case.inputs.get("titles") or [], ctx.case.inputs.get("plans") or []

    def work(town: Town, side: bench.Side, since: dt.datetime, start: float) -> dict:
        scrolls.SETTLE_S = 10 ** 6                       # the librarian never ingests by itself in a copy
        wikis = []
        if (ctx.project / "llm-wiki").is_dir():
            kb = raised(town, "scrolls", {"sources": []})
            kb.refresh()
            wikis = [kb.building_id]
        w = raised(town, "fields", {**ctx.template, "mode": "board", "wikis": wikis})
        on_tool(w, ctx.tool, ctx.tier)
        side.model = ctx.tier or w.steward_pick("plan", str(ctx.template.get("plan_model") or "")).tier
        for t in titles:
            with town.bench_lock:
                w.write(t["text"], "todo")
        cards = []
        for p in plans:
            with town.bench_lock:
                card = w.add(p["title"], tasklist.MINE, p.get("body") or "")
            if card is None:
                raise ValueError(f"the to-do “{p['title']}” was not added")
            cards.append(card.id)
            pages = [pg.title for pg in w.lore.context(card.id)]
            ctx.say(f"to-do “{p['title']}”: context {', '.join(pages) or 'none'}")
            side.how.append(f"“{p['title']}” took its context from: {', '.join(pages) or 'nothing'}")
            with town.bench_lock:
                started = w.plan(card.id, trust=True)
            if not started:
                raise ValueError(f"no plan could start for “{p['title']}”: {w.plan_error or 'no model'}")

        def named(t):
            return next((c for c in w.cards if (c.body or "").strip() == t["text"].strip()), None)

        done = lambda: all(named(t) for t in titles) and not w.planning                 # noqa: E731
        if why := wait(ctx, side, done, since, start):
            return _stopped(side, why)
        if w.plan_error:
            side.how.append(f"plan: {w.plan_error}")
        got_titles = []
        for n, t in enumerate(titles, 1):
            card = named(t)
            got_titles.append({"n": n, "title": card.title if card else ""})
            ctx.say(f"card {n} named “{card.title if card else ''}”")
        got_plans = [{"n": n, "steps": w.lore.plan(cid)} for n, cid in enumerate(cards, 1)]
        for p, row in zip(plans, got_plans):
            side.how.append(f"plan of “{p['title']}”: " + " / ".join(row["steps"])[:300])
        return {"titles": got_titles, "plans": got_plans}

    return _run(ctx, work)


# -- Calendar: a meeting's brief through the Agent pool ---------------------------------------------------------

def run_war_drum(ctx: Ctx) -> bench.Side:
    from orkcraft.core import bench as code_bench
    from orkcraft.core.workers.war_drum import WarDrumWorker
    events = bench_kits.events_of(ctx.case)

    def work(town: Town, side: bench.Side, since: dt.datetime, start: float) -> dict:
        now = since
        WarDrumWorker.clock = staticmethod(lambda: now)       # the case's week is from the run's start
        (ctx.project / "cal.ics").write_text(bench_kits.ics_of(ctx.case, now), encoding="utf-8")
        drum = raised(town, "war_drum", {**ctx.template, "ics": "cal.ics", "beats": ["meeting"], "day_starts": "23:59",
                                         "prepare_new": False})
        orders = ctx.case.inputs.get("orders") if ctx.orders is None else ctx.orders
        pool_config = code_bench.bench_config(ctx.pool_template, bench.Case("brief", "barracks", "", ""), ctx.tool,
                                              ctx.tier, ctx.max_spend)
        pool = raised(town, "barracks", {**pool_config, **({"orders": orders} if orders else {})})
        ts.subscribe(town.scroll, pool.building_id, drum.building_id, "calendar.event_upcoming")
        ts.subscribe(town.scroll, drum.building_id, pool.building_id, "pool.done", filter={"returns": True})
        side.model = ctx.tier
        drum.refresh()
        mine = sorted((e for e in drum.day.events if e.uid.startswith("bench-")), key=lambda e: e.uid)
        if len(mine) != len(events):
            raise ValueError(f"the calendar read {len(mine)} of the case's {len(events)} meetings")
        for e in mine:
            with town.bench_lock:
                why = drum.prepare(e)
            if why:
                raise ValueError(f"“{e.summary}” was not sent for its brief: {why}")
            ctx.say(f"asked the Agent pool for the brief of “{e.summary}”")
        heard = 0

        def done() -> bool:
            nonlocal heard
            decisions = pool.state.decisions(500)
            for d in decisions[heard:]:
                ctx.say(f"pool: {d.action}: {d.orc + ' — ' if d.orc else ''}{d.why}"[:200])
            heard = len(decisions)
            failed = [t for t in pool.state.tasks if t.status == "failed"]
            if failed:
                side.error = f"the Agent pool failed “{failed[0].title}”: {failed[0].error}"[:400]
                return True
            return all(drum.doc_of(e) for e in mine)

        if why := wait(ctx, side, done, since, start):
            return _stopped(side, why)
        side.orks = len(pool.state.orcs)
        side.how = [f"{d.action}: {d.orc + ' — ' if d.orc else ''}{d.why}"[:200] for d in pool.state.decisions(40)]
        briefs = []
        for e in mine:
            n = int(e.uid.split("-")[1].split("@")[0])
            doc = drum.doc_of(e) or {}
            try:
                text = (ctx.project / doc.get("path", "")).read_text(encoding="utf-8") if doc.get("path") else ""
            except OSError:
                text = ""
            briefs.append({"n": n, "text": text})
            ctx.say(f"brief of “{e.summary}” came back: {len(text)} characters")
        side.text = "\n\n---\n\n".join(b["text"] for b in briefs)[:6000]
        return {"briefs": briefs}

    return _run(ctx, work)


RUNS: dict[str, Callable[[Ctx], bench.Side]] = {"watchtower": run_watchtower, "fields": run_fields,
                                                "war_drum": run_war_drum}
