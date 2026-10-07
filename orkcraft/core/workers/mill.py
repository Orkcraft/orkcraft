"""⚙️ The Mill's work: a cart's value goes through the steps (realm/mill.py), one cart at a time.

What arrives while it mills waits in a queue (no limit, nothing is dropped). The steps run in a thread
of the worker; the result goes out as `mill.done`, each of its records as `mill.item`, a failing step
as `mill.failed`. Every run is kept in `.orkcraft/mill/<id>/runs.jsonl` with what each step made of
it (`meta["steps"]`), the failing step (`meta["failed"]`) and what its agent steps cost.
"""
from __future__ import annotations

import threading
import uuid
from collections import deque

from orkcraft import scroll as ts
from orkcraft.core import delivery
from orkcraft.core.workers import Worker
from orkcraft.realm import halt, jobs, mill, pipes, roads

INPUT_LIMIT = 256 * 1024
KEEP_RUNS = 200
HELP = ("lines · grep: rx · drop: rx · replace: rx => with · trim · lower · dedupe · csv · json · "
        "extract: field = rx · pick: a, b · sort: field [desc] [num|text] · limit: n · "
        "filter: field eq|ne|contains|matches|gt|ge|lt|le value · count · to_json · template: {field} · "
        "join[: sep] · script: command [|| agent: ask] · agent: ask")


def _simulated_agent(ask: str, text: str) -> str:
    """The showcase sandbox: agents never run there."""
    return f"_(demo — simulated)_ an agent would have done: {ask}"


def failed_step(job: jobs.Job) -> int | None:
    """The 1-based step a failed run stopped at, from its trace or its error ("step 3 (…): …")."""
    if job.ok:
        return None
    if isinstance(job.meta.get("failed"), int):
        return job.meta["failed"]
    head = job.error.split(" ", 2)
    if len(head) > 1 and head[0] == "step" and head[1].isdigit():
        return int(head[1])
    return None


class MillWorker(Worker):
    TYPE = "mill"

    def __init__(self, town, building_id: str) -> None:
        super().__init__(town, building_id)
        self.runs: list[jobs.Job] = []
        self.running = False
        self.current: jobs.Job | None = None
        self.last_input = ""
        self.queue: deque[tuple] = deque()     # (text, trigger, title, cut, trail, ref) — no limit
        self._carts: dict[str, tuple[tuple, str]] = {}     # a running job's trail and ref, to send on
        self.cancel = threading.Event()
        self._halts = halt.count()

    @property
    def steps(self) -> list[str]:
        return [str(s) for s in (self.config.get("steps") or [])]

    @property
    def log(self) -> jobs.Log:
        return jobs.Log(self.state_dir)

    def start(self) -> None:
        self.refresh()

    def refresh(self) -> None:
        self.runs = self.log.read(KEEP_RUNS)
        if self.runs and not self.last_input:
            self.last_input = self.runs[0].input
        self.changed()

    def status(self) -> str:
        if self.running:
            return "WORKING"
        if self.runs and not self.runs[0].ok:
            return "ERROR"
        return ""

    # -- milling --------------------------------------------------------------------------------

    def _read_file(self, rel: str, fallback: str) -> str:
        """A file cart: its content — only a file inside the repository."""
        root = self.repo_root.resolve()
        path = (root / rel).resolve()
        if not path.is_relative_to(root):
            return fallback
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return fallback

    def receive(self, payload, title: str, markdown: str) -> None:
        text = payload.value
        if payload.kind == pipes.FILE:
            text = self._read_file(payload.value, markdown or payload.value)
        self.run_steps(text, "road", title, payload.trail, payload.ref)

    def run_steps(self, text: str, trigger: str = "manual", title: str = "", trail: tuple = (), ref: str = "") -> bool:
        """Mill `text` now, or after what is already waiting. True: it is milling or queued. A cart's
        `trail` and `ref` go on with what it becomes."""
        self.queue.append((text[:INPUT_LIMIT], trigger, title, len(text) > INPUT_LIMIT, tuple(trail), ref))
        if not self.running:
            self._next()
        else:
            self.changed()
        return True

    def run_again(self) -> bool:
        """▶ Run: the steps on the last input. False when nothing has arrived yet."""
        if not self.last_input:
            self.toast("nothing has arrived yet — a road brings the input")
            return False
        if self.running:
            self.toast("queued after the cart that is milling")
        return self.run_steps(self.last_input)

    def _steward_tool(self) -> str:
        from orkcraft.realm import steward
        scroll = getattr(self.town, "scroll", None)
        return steward.harness_for(scroll.building(self.building_id) if scroll is not None else None) or "main"

    def _agent(self, job: jobs.Job | None = None) -> mill.Agent:
        if self.simulated:
            return _simulated_agent

        def spent(cost: float | None) -> None:
            if job is not None and cost:
                job.cost_usd = (job.cost_usd or 0.0) + float(cost)

        pick = self.steward_pick("agent", str(self.config.get("model") or ""))     # its `model`, else its goal's
        ask, town = mill.default_agent(self.repo_root, self.cancel, pick.model, spent, self._steward_tool()), self.town

        def gated(what: str, text: str) -> str:
            if not town.budget_ok():
                raise RuntimeError("🪙 budget exhausted: no agent step")
            return ask(what, text)
        return gated

    def halt(self) -> int:
        """🛑 Halt All: the running steps stop (an agent step too); what waits in the queue stays."""
        if not self.running:
            return 0
        self.cancel.set()
        self.cancel = threading.Event()              # the next cart mills again
        return 1

    def _next(self) -> None:
        if not self.queue:
            return
        text, trigger, title, cut, trail, ref = self.queue.popleft()
        self.running, self.last_input = True, text
        job = jobs.Job(uuid.uuid4().hex[:8], title or self.title, "mill", text,
                       started=jobs.now_iso(), outcome="running", trigger=trigger, meta={"cut": True} if cut else {})
        self.current = job
        self._carts[job.id] = (trail, ref)
        self._halts = halt.count()
        steps, repo, agent = self.steps, self.repo_root, self._agent(job)
        env, cancel = [str(n) for n in self.config.get("env") or []], self.cancel
        self.changed()

        def work() -> None:
            trace: list[dict] = []
            r = mill.run_full(steps, text, repo, cancel, agent, env, trace)
            job.result, job.error, job.ended = r.text, r.error, jobs.now_iso()
            job.outcome = "error" if r.error else "done"
            job.meta["steps"] = trace
            if r.error and trace and "error" in trace[-1]:
                job.meta["failed"] = len(trace)
            if r.agent_steps:
                job.meta["agent"] = r.agent_steps
            try:
                self.town.call(self.finish, job, r.records)
            except Exception:
                self.running = False

        threading.Thread(target=work, daemon=True, name=f"mill-{self.building_id}").start()

    def _flat_map(self, records: list | None, title: str, cart: tuple = ((), "")) -> int:
        """Each record as its own cart — only when a road takes them (each cart is recorded)."""
        values = mill.items(records)
        scroll = self.town.scroll
        if not values or scroll is None or not ts.has_outgoing(scroll, self.building_id, "mill.item"):
            return 0
        trail, ref = cart
        return sum(self.emit("mill.item", v, title, trail=trail, ref=ref) for v in values)

    def finish(self, job: jobs.Job, records: list | None = None) -> None:
        self.running, self.current = False, None
        trail, ref = self._carts.pop(job.id, ((), ""))
        kind = "agent" if job.meta.get("agent") else "script"
        trail = tuple(trail) + (pipes.hop(self.building_id, "miller", kind, cost=job.cost_usd,
                                          outcome="done" if job.ok else "error"),)
        if job.ok:
            if records:
                job.meta["items"] = len(mill.items(records))
            self.emit("mill.done", job.result, job.title, trail=trail, ref=ref)
            self._flat_map(records, job.title, (trail, ref))
        else:
            self.emit("mill.failed", job.error, job.title, trail=trail, ref=ref)
        if not job.ok or job.cost_usd:          # a failure is marked on the map; what an agent spent is counted
            delivery.ran(self.town, roads.HandlerRun(self.building_id, "miller", kind, job.id, 0.0, 0.0,
                                                     outcome="done" if job.ok else "error", error=job.error,
                                                     cost_usd=job.cost_usd, trail=trail, ref=ref))
        try:
            self.log.append(job)
            self.log.trim(KEEP_RUNS)
        except OSError:
            pass
        self.refresh()
        if not halt.stopped_since(self._halts):   # after 🛑 Halt All the queue waits
            self._next()

    def set_steps(self, steps: list[str]) -> bool:
        """The steps, one per line (checked like any spec: an unknown step is refused)."""
        return self.save_config({"steps": [s.strip() for s in steps if s.strip()]})

    # -- the hut --------------------------------------------------------------------------------

    def mini_status(self) -> list[str]:
        lines = [f"{len(self.steps)} step{'s' if len(self.steps) != 1 else ''}"
                 + (f": {self.steps[0].split(':')[0]}…" if self.steps else "")]
        if self.running:
            lines.append("⚙ milling…" + (f" +{len(self.queue)}" if self.queue else ""))
        elif self.runs:
            j = self.runs[0]
            lines.append(("✓ " if j.ok else "✗ ") + j.started[11:16])
        return lines

    def hut_lines(self, widths: list[int]) -> list[str]:
        """One short line: the last run, or how many steps it has."""
        if self.running:
            return [f"⚙ +{len(self.queue)}" if self.queue else "milling…"]
        if self.runs:
            j = self.runs[0]
            return [("✓ " if j.ok else "✗ ") + j.started[11:16]]
        return [f"{len(self.steps)} step{'s' if len(self.steps) != 1 else ''}"] if self.steps else ["no steps"]

    def quick_action(self, action_id: str) -> bool:
        if action_id != "mill.run":
            return False
        self.run_again()
        return True
