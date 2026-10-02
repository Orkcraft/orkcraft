"""🏕 Barracks: a foreman orc runs incoming tasks in parallel.

A task arrives (a cart from Tasks, a ticket, any text). The foreman decides, by rules:

    follow-up   it names a ticket an orc already worked on, or reads like a follow-up of the
                only orc with history → that orc gets it (now if idle, else when it is free)
    reuse       an idle orc with nothing waiting for it takes it
    hire        fewer orcs than `max_orcs` and budget left → a new orc; the foreman picks its
                provider and model from `providers`
    queue       otherwise it waits

Rules first, a model only when in doubt (not wired yet: a doubtful follow-up goes to the most
recent orc and the decision says so). The foreman learns: every finished task updates the stats
of its provider/model, and the next hire weighs success rate against cost — the self-reflection
the orcs of the town already do.

State lives in `.orkcraft/pool/<id>/`: `barracks.json` (orcs, queue, recent tasks),
`decisions.jsonl` (every decision with its reason) and `stats.json` (per provider/model).
"""
from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

DEFAULT_PROVIDERS = ("claude", "agy")
DEFAULT_MAX_ORCS = 3
AGY_CODE, AGY_DOCS = "gemini-3.8-flash-high", "gemini-3.1-pro-high"
TICKET = re.compile(r"\b([A-Z]{1,5}-?\d{2,6})\b")
FOLLOW_UP = re.compile(r"^\s*(follow[- ]?up|re:|also|and also|fix (the )?review|уточн|ещё|еще|также|доработ|поправ)",
                       re.I)
DOCS_WORDS = re.compile(r"\b(doc|docs|readme|write[- ]?up|research|summar|explain|report|документ|исследу|опиши)",
                        re.I)
NAMES = ("Grub", "Mogka", "Thrak", "Ugluk", "Snaga", "Lurtz", "Gorbag", "Shagrat", "Muzgash", "Radbug")
KEEP_TASKS = 50


def now_iso() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


@dataclass
class PoolOrc:
    name: str
    harness: str
    model: str = ""
    status: str = "idle"            # idle | working
    task: str = ""                  # the task id it works on
    keys: list[str] = field(default_factory=list)   # tickets / nodes it worked on
    worktree: str = ""
    branch: str = ""
    session: str = ""               # the harness session to resume for a follow-up
    hired: str = ""
    done: int = 0
    failed: int = 0
    cost_usd: float = 0.0
    last: str = ""                  # when it last finished

    @property
    def label(self) -> str:
        return f"{self.harness}:{self.model}" if self.model else self.harness


@dataclass
class PoolTask:
    id: str
    title: str
    text: str
    key: str = ""
    arrived: str = ""
    status: str = "queued"          # queued | working | done | failed
    orc: str = ""
    wait_for: str = ""              # a follow-up waiting for this orc
    result: str = ""
    error: str = ""
    cost_usd: float | None = None
    decided: str = ""               # the last decision about it


@dataclass
class Decision:
    at: str
    task: str
    action: str                     # follow-up | wait | reuse | hire | queue | budget | paused
    orc: str = ""
    why: str = ""


def task_key(kind: str, value: str, title: str = "") -> str:
    """What a task is about: a node id, else the first ticket id it names."""
    if kind == "node" and value:
        return value.strip()
    m = TICKET.search(f"{title} {value}")
    return m.group(1) if m else ""


def parse_provider(entry: str) -> tuple[str, str]:
    harness, _, model = str(entry).partition(":")
    return harness.strip(), model.strip()


class Foreman:
    def __init__(self, config: dict, stats: dict | None = None) -> None:
        self.max_orcs = int(config.get("max_orcs") or DEFAULT_MAX_ORCS)
        self.budget = float(config.get("budget_usd") or 0.0)          # 0: no budget of its own
        self.providers = [parse_provider(p) for p in (config.get("providers") or DEFAULT_PROVIDERS)]
        self.providers = [(h, m) for h, m in self.providers if h in ("claude", "agy")] or \
            [parse_provider(p) for p in DEFAULT_PROVIDERS]
        self.stats = stats or {}

    # -- the model ------------------------------------------------------------------------------------

    def choose_model(self, task: PoolTask) -> tuple[str, str, str]:
        """(harness, model, why): the best provider by its record, nudged by what the task is."""
        docs = bool(DOCS_WORDS.search(f"{task.title} {task.text}"))
        best, best_score, best_why = None, -1e9, ""
        for harness, model in self.providers:
            if harness == "agy" and not model:
                model = AGY_DOCS if docs else AGY_CODE
            key = f"{harness}:{model}" if model else harness
            st = self.stats.get(key, {})
            runs, ok, cost = int(st.get("runs", 0)), int(st.get("ok", 0)), float(st.get("cost", 0.0))
            rate = (ok + 1) / (runs + 2)                         # Laplace: unknown providers start at ½
            avg_cost = cost / runs if runs else 0.0
            fit = 0.1 if (docs and harness == "agy") or (not docs and harness == "claude") else 0.0
            score = rate - 0.2 * min(avg_cost, 2.0) + fit
            if score > best_score:
                why = f"{key}: {ok}/{runs} ok" + (f", ${avg_cost:.2f}/task" if runs else ", no record yet")
                why += "; fits a docs task" if fit and docs else "; fits a code task" if fit else ""
                best, best_score, best_why = (harness, model), score, why
        assert best is not None
        return best[0], best[1], best_why

    def learn(self, orc: PoolOrc, ok: bool, cost: float | None) -> None:
        st = self.stats.setdefault(orc.label, {"runs": 0, "ok": 0, "cost": 0.0})
        st["runs"] += 1
        st["ok"] += int(ok)
        st["cost"] = round(st["cost"] + (cost or 0.0), 4)

    # -- the decision -----------------------------------------------------------------------------------

    def follow_up_of(self, task: PoolTask, orcs: list[PoolOrc]) -> tuple[PoolOrc | None, str]:
        if task.key:
            for o in orcs:
                if task.key in o.keys:
                    return o, f"{task.key} was {o.name}'s"
        if FOLLOW_UP.search(task.text) or FOLLOW_UP.search(task.title):
            seasoned = sorted((o for o in orcs if o.keys or o.done or o.failed), key=lambda o: o.last, reverse=True)
            if len(seasoned) == 1:
                return seasoned[0], f"reads like a follow-up; {seasoned[0].name} is the only one with history"
            if seasoned:
                return seasoned[0], f"reads like a follow-up; in doubt — {seasoned[0].name} finished last"
        return None, ""

    def decide(self, task: PoolTask, orcs: list[PoolOrc], queue: list[PoolTask], spent: float,
               paused: bool = False) -> Decision:
        at = now_iso()
        if paused:
            return Decision(at, task.id, "paused", why="the barracks is paused")
        orc, why = self.follow_up_of(task, orcs)
        if orc is not None:
            if orc.status == "idle":
                return Decision(at, task.id, "follow-up", orc.name, why)
            return Decision(at, task.id, "wait", orc.name, why + f"; waits until {orc.name} is free")
        if self.budget and spent >= self.budget:
            return Decision(at, task.id, "budget", why=f"spent ${spent:.2f} of ${self.budget:.2f}")
        waiting_for = {t.wait_for for t in queue if t.wait_for}
        idle = next((o for o in orcs if o.status == "idle" and o.name not in waiting_for), None)
        if idle is not None:
            return Decision(at, task.id, "reuse", idle.name, f"{idle.name} is idle")
        if len(orcs) < self.max_orcs:
            harness, model, mwhy = self.choose_model(task)
            name = next((n for n in NAMES if n not in {o.name for o in orcs}), f"Orc{len(orcs) + 1}")
            return Decision(at, task.id, "hire", name, f"{len(orcs)}/{self.max_orcs} orcs busy → hire; {mwhy}")
        return Decision(at, task.id, "queue", why=f"all {len(orcs)} orcs busy — waits in the queue")

    def next_for(self, orc: PoolOrc, queue: list[PoolTask]) -> PoolTask | None:
        """What a freed orc takes: its own follow-ups first, then the oldest task nobody waits on."""
        mine = next((t for t in queue if t.wait_for == orc.name), None)
        return mine or next((t for t in queue if not t.wait_for), None)


class Barracks:
    """The state on disk of one Barracks building."""

    def __init__(self, state_dir: Path) -> None:
        self.dir = state_dir
        self.orcs: list[PoolOrc] = []
        self.queue: list[PoolTask] = []
        self.tasks: list[PoolTask] = []       # working and finished, newest last
        self.paused = False
        self.stats: dict = {}
        self.load()

    @property
    def spent(self) -> float:
        return round(sum(o.cost_usd for o in self.orcs), 4)

    def orc(self, name: str) -> PoolOrc | None:
        return next((o for o in self.orcs if o.name == name), None)

    def task(self, task_id: str) -> PoolTask | None:
        return next((t for t in self.queue + self.tasks if t.id == task_id), None)

    def load(self) -> None:
        try:
            data = json.loads((self.dir / "barracks.json").read_text(encoding="utf-8"))
            self.orcs = [PoolOrc(**o) for o in data.get("orcs", [])]
            self.queue = [PoolTask(**t) for t in data.get("queue", [])]
            self.tasks = [PoolTask(**t) for t in data.get("tasks", [])]
            self.paused = bool(data.get("paused", False))
        except (OSError, ValueError, TypeError):
            pass
        for o in self.orcs:                   # a restart interrupts the work: those tasks go back
            if o.status == "working":
                t = next((x for x in self.tasks if x.id == o.task and x.status == "working"), None)
                if t is not None:
                    self.tasks.remove(t)
                    t.status, t.wait_for = "queued", o.name
                    self.queue.insert(0, t)
                o.status, o.task = "idle", ""
        try:
            self.stats = json.loads((self.dir / "stats.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.stats = {}

    def save(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        data = {"orcs": [asdict(o) for o in self.orcs], "queue": [asdict(t) for t in self.queue],
                "tasks": [asdict(t) for t in self.tasks[-KEEP_TASKS:]], "paused": self.paused}
        (self.dir / "barracks.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        (self.dir / "stats.json").write_text(json.dumps(self.stats, indent=2), encoding="utf-8")

    def log(self, d: Decision) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        with (self.dir / "decisions.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(d), ensure_ascii=False) + "\n")

    def decisions(self, limit: int = 30) -> list[Decision]:
        try:
            lines = (self.dir / "decisions.jsonl").read_text(encoding="utf-8").splitlines()[-limit:]
        except OSError:
            return []
        out = []
        for line in reversed(lines):
            try:
                out.append(Decision(**json.loads(line)))
            except (ValueError, TypeError):
                continue
        return out
