"""🧪 The Test bench's window (js/bench.js, docs/design/test-bench.md): one building on its own, three tabs.

Shown only when `ORKCRAFT_BENCH=1` (the snapshot's `bench`): five clicks on a hut open it. Tech runs a case in
`orkcraft bench`, a process of its own (a run opens a town of its own, and one process holds one town); its
lines are read as they come. Its reviews, UX's and Product's are agents that only read Orkcraft's source,
each role in a thread, kept per type in `.orkcraft/bench/reviews/`. The first time a building is opened with
no review kept, its three tabs are reviewed by themselves; after that only Review again starts them. Make
tasks sends the ticked findings to an Agent pool of the town, one task each.

    host.commands.update(bench.Bench(host).commands())
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

import orkcraft
from orkcraft import env
from orkcraft.core import bench as building_bench
from orkcraft.realm import bench, bench_review, catalog, halt, harnesses, lexicon, tiers

LINES = 400                        # a run's lines kept for the window
TIERS = (("", "The building's own"), ("laborer", "Novice"), ("warrior", "Seasoned"), ("elder", "Veteran"))


class BenchError(Exception):
    """A step the bench refuses; its text is shown to the person."""


def enabled() -> bool:
    return env.getenv("BENCH").strip().lower() in ("1", "true", "yes", "on")


@dataclass
class Job:
    what: str                      # run | case
    type: str
    label: str
    started: float = field(default_factory=time.monotonic)
    lines: list[str] = field(default_factory=list)
    done: bool = False
    error: str = ""
    result: str = ""               # the run's id, the case's id
    proc: subprocess.Popen | None = field(default=None, repr=False)
    cancel: threading.Event = field(default_factory=threading.Event, repr=False)

    def public(self) -> dict:
        return {"what": self.what, "label": self.label, "lines": self.lines[-LINES:], "done": self.done,
                "error": self.error, "result": self.result, "seconds": round(time.monotonic() - self.started)}


class Bench:
    def __init__(self, host) -> None:
        self.host = host
        self.jobs: dict[str, Job] = {}                       # type → its run or its case being written
        self.reviewing: dict[tuple[str, str], dict[str, threading.Event]] = {}   # (type, tab) → role → cancel
        self.asked: set[str] = set()                         # types reviewed by themselves on a first open
        self._lock = threading.Lock()

    @property
    def root(self) -> Path:
        return self.host.town.repo_root

    def commands(self) -> dict[str, Callable[[dict], Any]]:
        return {"bench.open": self.open, "bench.state": self.state, "bench.run": self.run, "bench.stop": self.stop,
                "bench.review": self.review, "bench.case.write": self.write_case, "bench.case.read": self.read_case,
                "bench.tasks": self.tasks}

    # -- what the window sees ------------------------------------------------------------------------------

    def _type(self, args: dict) -> tuple[str, str]:
        if not enabled():
            raise BenchError("The Test bench is off: start Orkcraft with ORKCRAFT_BENCH=1")
        bid = str(args.get("id") or "")
        if self.host.town.scroll.building(bid) is None:
            raise BenchError("No such building")
        return bid, self.host.type_of(bid)

    def _tools(self) -> list[dict]:
        on = [t for t, c in self.host.town.machine.tools.items() if c.enabled and harnesses.get(t)]
        return [{"id": "main", "title": "Main tool"}] + [{"id": t, "title": harnesses.need(t).title} for t in on]

    def state(self, args: dict) -> dict[str, Any]:
        bid, type_id = self._type(args)
        spec = self.host.town.spec_of(bid) or {}
        t = catalog.TYPES.get(type_id)
        job = self.jobs.get(type_id)
        reviews = {}
        for tab in bench_review.TABS:
            kept = bench_review.load(self.root, type_id, tab)
            running = self.reviewing.get((type_id, tab), {})
            roles = []
            for rid, title, focus in bench_review.ROLES[tab]:
                entry = (kept.get("roles") or {}).get(rid) or {}
                roles.append({"id": rid, "title": title, "focus": focus, "running": rid in running,
                              "status": "running" if rid in running else entry.get("status", ""),
                              "error": entry.get("error", ""), "aha": entry.get("aha"),
                              "cost": entry.get("cost", 0.0), "seconds": entry.get("seconds", 0),
                              "findings": [{**f, "id": f"{tab}:{rid}:{n}"} for n, f in enumerate(entry.get("findings") or [])]})
            reviews[tab] = {"at": kept.get("at", ""), "version": kept.get("version", ""), "tool": kept.get("tool", ""),
                            "stale": bool(kept.get("version")) and kept.get("version") != orkcraft.__version__,
                            "roles": roles}
        return {
            "id": bid, "type": type_id, "title": spec.get("title") or bid, "word": lexicon.term(type_id),
            "summary": t.summary if t else "", "can_run": type_id in building_bench.TYPES,
            "cases": [{**asdict(c), "own": (self.root / bench.BENCH / type_id / f"{c.id}.json").is_file()}
                      for c in bench.cases(self.root, type_id)],
            "runs": [asdict(r) for r in bench.runs(self.root, type_id)[:12]],
            "against": bench.against(self.root, type_id),
            "levels": {lvl: sum(c.level == lvl and c.reviewed for c in bench.cases(self.root, type_id))
                       for lvl in bench.LEVELS},
            "gap_limit": bench.GAP_LIMIT,
            "job": job.public() if job else None,
            "reviews": reviews,
            "tools": self._tools(), "tiers": [{"id": i, "title": w} for i, w in TIERS],
            "orders": str((spec.get("config") or {}).get("orders") or ""),
            "max_spend": bench.DEFAULT_MAX_SPEND,
            "pools": [{"id": b.id, "title": b.title} for b in self.host.town.scroll.buildings
                      if not b.demolished and self.host.type_of(b.id) == "barracks"],
        }

    def open(self, args: dict) -> dict[str, Any]:
        """The window opens: a building never reviewed has its three tabs reviewed now, once."""
        _bid, type_id = self._type(args)
        if type_id not in self.asked and not any(bench_review.load(self.root, type_id, tab) for tab in bench_review.TABS):
            self.asked.add(type_id)
            for tab in bench_review.TABS:
                self._review(type_id, tab, "main")
        return self.state(args)

    # -- Tech: a run ---------------------------------------------------------------------------------------

    def run(self, args: dict) -> dict[str, Any]:
        bid, type_id = self._type(args)
        if type_id not in building_bench.TYPES:
            raise BenchError(f"Runs come to {lexicon.term(type_id)} later: the Test bench runs the Agent pool so far")
        if (job := self.jobs.get(type_id)) and not job.done:
            raise BenchError("A run is on: stop it first")
        pick = str(args.get("case") or "")
        level = pick.partition(":")[2] if pick.startswith("level:") else ""
        if level and level not in bench.LEVELS:
            raise BenchError("No such level")
        picked = bench.series(bench.cases(self.root, type_id), "" if level else pick, level) if pick else []
        if not picked:
            raise BenchError("Pick a case")
        label = picked[0].title if len(picked) == 1 and pick != bench.ALL else \
            f"{'every case' if pick == bench.ALL else f'every {level} case'} ({len(picked)})"
        tier = str(args.get("tier") or "")
        if tier and tier not in tiers.TIERS:
            raise BenchError("No such tier")
        tool = str(args.get("tool") or "main")
        if tool != "main" and harnesses.get(tool) is None:
            raise BenchError("No such AI tool")
        try:
            spend = min(max(float(args.get("max_spend") or bench.DEFAULT_MAX_SPEND), 0.1), 50.0)
        except (TypeError, ValueError):
            raise BenchError("The spend limit is a number of dollars") from None
        argv = [sys.executable, "-m", "orkcraft", "--repo", str(self.root), "bench", type_id,
                *(("--level", level) if level else ("--case", pick)),
                "--tool", tool, "--max-spend", str(spend), "--building", bid]
        if tier:
            argv += ["--tier", {"laborer": "novice", "warrior": "seasoned", "elder": "veteran"}[tier]]
        if args.get("only") in ("building", "bare"):
            argv += ["--only", str(args["only"])]
        orders = args.get("orders")
        if isinstance(orders, str) and orders != str((self.host.town.spec_of(bid) or {}).get("config", {}).get("orders") or ""):
            path = self.root / bench.BENCH / "orders" / f"{type_id}-{int(time.time())}.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(orders[:20000], encoding="utf-8")
            argv += ["--orders", str(path)]
        job = Job("run", type_id, label)
        try:
            job.proc = subprocess.Popen(argv, cwd=self.root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        text=True, start_new_session=True, env={**os.environ, "PYTHONUNBUFFERED": "1"})
        except OSError as e:
            raise BenchError(f"The run did not start: {e}") from None
        halt.started(job.proc, f"{bid}/bench", agent=True)
        self.jobs[type_id] = job
        threading.Thread(target=self._follow, args=(job,), daemon=True, name=f"bench-{type_id}").start()
        return self.state(args)

    def _follow(self, job: Job) -> None:
        proc = job.proc
        for line in proc.stdout:
            line = line.rstrip()
            if line.startswith(bench.DONE):
                job.result = line[len(bench.DONE):].strip()
            elif line:
                job.lines = (job.lines + [line])[-LINES:]
        code = proc.wait()
        halt.ended(proc)
        if code != 0 and not job.result:
            job.error = "stopped" if job.cancel.is_set() else f"the run ended with exit {code}"
        job.done = True
        self.host.town.call(self.host.on_change)

    def stop(self, args: dict) -> dict[str, Any]:
        _bid, type_id = self._type(args)
        job = self.jobs.get(type_id)
        if job and not job.done:
            job.cancel.set()
            if job.proc is not None:
                try:
                    os.killpg(job.proc.pid, signal.SIGTERM)
                except (ProcessLookupError, PermissionError):
                    pass
        for cancel in list(self.reviewing.get((type_id, str(args.get("tab") or "")), {}).values()):
            cancel.set()
        return self.state(args)

    # -- the reviews ---------------------------------------------------------------------------------------

    def review(self, args: dict) -> dict[str, Any]:
        _bid, type_id = self._type(args)
        tab = str(args.get("tab") or "")
        if tab not in bench_review.TABS:
            raise BenchError("No such tab")
        if self.reviewing.get((type_id, tab)):
            raise BenchError("This review is on")
        self._review(type_id, tab, str(args.get("tool") or "main"))
        return self.state(args)

    def _review(self, type_id: str, tab: str, tool: str) -> None:
        roles = {rid: threading.Event() for rid, _t, _f in bench_review.ROLES[tab]}
        started = list(roles.items())              # a quick reviewer leaves `roles` before the last one starts
        with self._lock:
            self.reviewing[(type_id, tab)] = roles
        for n, (rid, _cancel) in enumerate(started):
            bench_review.put(self.root, type_id, tab, rid, {"status": "running", "findings": []}, tool, fresh=n == 0)
        for rid, cancel in started:
            threading.Thread(target=self._one, args=(type_id, tab, rid, tool, cancel), daemon=True,
                             name=f"bench-{tab}-{rid}").start()

    def _one(self, type_id: str, tab: str, role: str, tool: str, cancel: threading.Event) -> None:
        try:
            bench_review.review(self.root, type_id, tab, role, tool, cancel=cancel)
        finally:
            with self._lock:
                running = self.reviewing.get((type_id, tab), {})
                running.pop(role, None)
                if not running:
                    self.reviewing.pop((type_id, tab), None)
            self.host.town.call(self.host.on_change)

    # -- cases ---------------------------------------------------------------------------------------------

    def write_case(self, args: dict) -> dict[str, Any]:
        _bid, type_id = self._type(args)
        if (job := self.jobs.get(type_id)) and not job.done:
            raise BenchError("A run is on: wait for it, or stop it")
        job = Job("case", type_id, "Writing a case")
        self.jobs[type_id] = job
        brief, tool = str(args.get("brief") or "")[:2000], str(args.get("tool") or "main")

        def write() -> None:
            try:
                job.result = bench_review.write_case(self.root, type_id, brief, tool, cancel=job.cancel).id
            except (RuntimeError, OSError) as e:
                job.error = str(e)[:500]
            job.done = True
            self.host.town.call(self.host.on_change)

        threading.Thread(target=write, daemon=True, name=f"bench-case-{type_id}").start()
        return self.state(args)

    def read_case(self, args: dict) -> dict[str, Any]:
        _bid, type_id = self._type(args)
        if not bench.mark_read(self.root, type_id, str(args.get("case") or "")):
            raise BenchError("No such written case")
        return self.state(args)

    # -- Make tasks ----------------------------------------------------------------------------------------

    def tasks(self, args: dict) -> dict[str, Any]:
        bid, type_id = self._type(args)
        pool = str(args.get("pool") or "")
        if self.host.type_of(pool) != "barracks" or self.host.town.scroll.building(pool) is None:
            raise BenchError("Pick an Agent pool for the tasks")
        picks = {str(x) for x in args.get("picks") or []}
        chosen = [f for f in bench_review.findings(self.root, type_id) if f["id"] in picks]
        if not chosen:
            raise BenchError("Tick the findings to make tasks of")
        worker = self.host.town.worker(pool)
        word = lexicon.term(type_id)
        made = 0
        for f in chosen:
            brief = (f"From the Test bench, {f['role']} ({f['tab']} review) of the {word} (`{type_id}`, building "
                     f"`{bid}`), Orkcraft {orkcraft.__version__}.\n\n{f['detail']}"
                     + (f"\n\nWhere: {f['where']}" if f.get("where") else "") + f"\n\nSeverity: {f['severity']}.")
            if worker.new_task(f"{word}: {f['title']}", brief) is not None:
                made += 1
        self.host.town.toast(f"{made} task{'s' if made != 1 else ''} sent to {self.host.town.title_of(pool)}",
                             title="Test bench")
        return {**self.state(args), "made": made}
