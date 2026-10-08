"""The road engine: events travel from a source building along the incoming roads of the
receivers (Town Scroll v3), through the source filter, to a plain delivery or a handler.

    engine = Engine(lambda: app.scroll, repo_root, deliver=..., on_output=..., meta=...)
    engine.emit(Payload(kind="node", value="T1001", source="forge", mode="on_selection_change"))
    engine.tick()          # a timer calls this: starts agent runs whose quiet period is over
    engine.stop()          # interrupts running agents (on quit)

Rules (docs/design/roads-and-orcs.md):
- The filter runs at the source: a payload that does not match never leaves (cart `filtered`).
  Personal context nodes never reach a handler that uses a model, whatever the filter says.
- A handler keeps the latest payload of every road it works on and is re-run on every new
  event with that whole snapshot. Chains run at once; agents / hybrids wait `quiet_s` without
  new events, and with `restart_on_new` a new event interrupts a running agent, which then
  starts again with the fresh snapshot (its spent 🪙 is still counted: the session carries
  `ORKCRAFT_RUN`).
- Scripts (and so hybrids) run only once reviewed (`script_problem`); until then their carts are `held`.
- A road rule (`steward`) is carried out by the building's steward: on its tool and at its tier for
  `listen` (realm/steward.py `pick`, the goal in force from `aim`), with the building's purpose in the
  prompt. A hybrid with no tools of its own escalates (exit 3) to the steward the same way.
- Agents run only while the 🪙 budget allows (`budget_ok`), in the repository with read-only
  tools (Claude) or a read-only sandbox (Codex), or in an empty temp dir (agy). A pipeline harness
  is not wired yet.
- Callbacks may come from worker threads: pass `call` to marshal them (Textual:
  `call_from_thread`).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from orkcraft import scroll as ts
from orkcraft.realm import chains, halt, harnesses, pipes, tiers, tool_errors
from orkcraft.realm.pipes import FILE, NODE, Payload
from orkcraft.realm.road_agents import (  # noqa: F401  (roads.run_agent & co., as before the split)
    AGENT_TIMEOUT_S, IN_REPO, SNAPSHOT_CHARS, AgentRunner, _harness_cmd, _tokens_of, agent_prompt, codex_error, codex_thread_usage,
    examples_file, failure, harness_stdin, names_session, prompt_record, read_examples, resolve, result_of, run_agent,
    run_proc, steward_steps)

SCRIPT_TIMEOUT_S = 60
ESCALATE = 3          # a hybrid's script: "the agent should take it from here"


def script_problem(orc: ts.OrcSpec, repo_root: Path) -> str:
    """Why a script handler may not run ('' when it may): it must be reviewed (the Council and the
    operator approved it) and unchanged since — its sha256 still matches."""
    import hashlib
    info = orc.script or {}
    path = repo_root / str(info.get("path") or "")
    if not info.get("path") or not path.is_file():
        return "the script file is missing"
    if not info.get("reviewed"):
        return "the script waits for review"
    want = info.get("sha256")
    if want and hashlib.sha256(path.read_bytes()).hexdigest() != want:
        return "the script changed since its review — review it again"
    return ""


def run_handler_script(path: Path, records: list[dict], repo_root: Path, cancel: threading.Event,
                       timeout_s: int = SCRIPT_TIMEOUT_S) -> tuple[int, str, str]:
    """(exit code, stdout, stderr) of `python3 -I <path>` with the records as JSON on stdin; no shell,
    a timeout, orkcraft's own variables kept out. Raises InterruptedError when cancelled."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("ORKCRAFT_")}
    with tempfile.TemporaryFile("w+") as out, tempfile.TemporaryFile("w+") as err:
        proc = subprocess.Popen(["python3", "-I", str(path)], cwd=repo_root, env=env, stdin=subprocess.PIPE,
                                stdout=out, stderr=err, text=True, start_new_session=True)
        try:
            proc.stdin.write(json.dumps(records, ensure_ascii=False, default=str))
            proc.stdin.close()
        except (BrokenPipeError, OSError):
            pass
        deadline = time.monotonic() + timeout_s
        with halt.running(proc):
            while proc.poll() is None:
                if cancel.wait(0.1) or time.monotonic() > deadline:
                    proc.kill()
                    proc.wait(5)
                    if cancel.is_set():
                        raise InterruptedError("stopped")
                    raise RuntimeError(f"no answer within {timeout_s} s")
        out.seek(0)
        err.seek(0)
        return proc.returncode, out.read()[:20_000].strip(), err.read()[:4000]

SENT, FILTERED, DELIVERED, ERROR, HELD = "sent", "filtered", "delivered", "error", "held"
EXAMPLE_OUTPUT_CHARS = 8000
CLAUDE_READ_ONLY, CLAUDE_READ_WEB = harnesses.CLAUDE_READ_ONLY, harnesses.CLAUDE_READ_WEB   # 🪔 Clan Fire: web
CODEX_WEB = harnesses.CODEX_WEB
# harnesses that read the repository; the others (agy) work in an empty folder


@dataclass(frozen=True)
class Cart:
    """One real event on one road — the stage 6 animation and the handler's audit trail."""
    road_id: str
    source: str
    target: str
    status: str                   # sent | filtered | delivered | error | held
    payload: Payload
    detail: str = ""
    at: float = 0.0


@dataclass
class HandlerRun:
    target: str
    orc_id: str
    kind: str
    run_id: str
    started: float
    ended: float = 0.0
    outcome: str = ""             # done | error | interrupted | held | no_gold
    markdown: str = ""
    error: str = ""
    cost_usd: float | None = None
    tokens: int | None = None     # every token the model read or wrote, when the CLI says
    roads: tuple[str, ...] = ()
    inputs: list[dict] = field(default_factory=list, repr=False)   # the snapshot records it ran on
    trail: tuple = field(default=(), repr=False)   # the hops of the carts it ran on (pipes.Hop)
    ref: str = ""
    model: str = ""               # the model(s) its steps ran on ("a+b"), else their tools
    failure: tool_errors.ToolError | None = field(default=None, repr=False)   # the AI tool that failed it


@dataclass
class HandlerState:
    snapshot: dict[str, tuple[Payload, dict]] = field(default_factory=dict)   # road id → latest
    last_event: float = 0.0
    dirty: bool = False           # new data since the last start
    running: bool = False
    generation: int = 0
    cancel: threading.Event | None = None
    runs: int = 0


# -- the source filter ------------------------------------------------------------------------------

def passes(flt: dict, payload: Payload, meta: dict, target: str = "") -> tuple[bool, str]:
    """(passes, reason). Keys that do not apply to the payload's kind are ignored. `target`: the building
    the road leads to (a return road carries only what its `ref` names it for)."""
    if flt.get("returns") and target and not payload.ref.startswith(f"{target}:"):
        return False, "not its own work"
    if flt.get("exclude_personal") and meta.get("subtype") == "personal":
        return False, "personal node"
    if payload.kind == NODE:
        if flt.get("node_type") and meta.get("type") not in flt["node_type"]:
            return False, f"type {meta.get('type') or '?'}"
        if flt.get("node_status") and meta.get("status") not in flt["node_status"]:
            return False, f"status {meta.get('status') or '?'}"
    if payload.kind == FILE and flt.get("path_prefix"):
        if not any(payload.value.startswith(p) for p in flt["path_prefix"]):
            return False, "path"
    if payload.mode == "on_task_completed" and flt.get("outcome"):
        if (meta.get("outcome") or "unknown") not in flt["outcome"]:
            return False, f"outcome {meta.get('outcome') or 'unknown'}"
    if flt.get("route") and (payload.route or payload.mode == "signpost.routed"):
        route = payload.route or payload.title          # a Signpost's cart is titled by its route
        if route not in flt["route"]:
            return False, f"route {route or '?'}"
    if flt.get("want") and payload.want not in flt["want"]:      # a road for some kinds of work only (§8)
        return False, f"kind of work {payload.want or '?'}"
    if flt.get("match"):
        hay = f"{payload.title}\n{payload.value}"[: chains.FIELD_CHARS]
        if re.search(flt["match"], hay) is None:
            return False, "no match"
    return True, ""


def _needs_meta(flt: dict, payload: Payload) -> bool:
    return bool(flt.get("exclude_personal") or flt.get("outcome")
                or (payload.kind == NODE and (flt.get("node_type") or flt.get("node_status"))))


# -- the engine -------------------------------------------------------------------------------------------

class Engine:
    def __init__(self, scroll: Callable[[], ts.TownScroll | None], repo_root: Path, *,
                 deliver: Callable[[str, Payload], None],
                 on_output: Callable[..., None] | None = None,   # (target, orc, title, markdown, trail, ref)
                 meta: Callable[[Payload], dict] | None = None,
                 on_cart: Callable[[Cart], None] | None = None,
                 on_run: Callable[[HandlerRun], None] | None = None,
                 budget_ok: Callable[[], bool] = lambda: True,
                 agent_runner: AgentRunner = run_agent,
                 call: Callable[..., Any] | None = None,
                 clock: Callable[[], float] = time.monotonic,
                 run_env: dict | None = None,
                 travel: Callable[[], float] | None = None,
                 aim: Callable[[str], str | None] | None = None) -> None:
        self._scroll, self.repo_root = scroll, repo_root
        self._travel = travel or (lambda: 0.0)   # seconds a cart is on a plain road before it arrives (0: at once)
        self._deliver, self._on_output, self._meta = deliver, on_output, meta or (lambda p: {})
        self._on_cart, self._on_run, self._budget_ok = on_cart, on_run, budget_ok
        self._agent_runner, self._clock = agent_runner, clock
        self._call = call or (lambda fn, *a: fn(*a))
        self._run_env = dict(run_env or {})
        self._aim = aim or (lambda building_id: None)   # building id → the goal in force (None: its own)
        self._lock = threading.RLock()
        self.states: dict[tuple[str, str], HandlerState] = {}
        self.carts: list[Cart] = []          # recent carts, newest last (the UI reads / animates)
        self.runs: list[HandlerRun] = []     # recent handler runs, newest last

    # -- queries --------------------------------------------------------------------------------------

    def has_roads(self, source_id: str, event: str) -> bool:
        scroll = self._scroll()
        return scroll is not None and ts.has_outgoing(scroll, source_id, event)

    def state(self, target_id: str, orc_id: str) -> HandlerState:
        with self._lock:
            return self.states.setdefault((target_id, orc_id), HandlerState())

    # -- events --------------------------------------------------------------------------------------

    def emit(self, payload: Payload, meta: dict | None = None) -> list[Cart]:
        """Send one event along every matching road; returns the carts it produced."""
        scroll = self._scroll()
        if scroll is None:
            return []
        now = self._clock()
        cache: dict | None = dict(meta) if meta is not None else None

        def meta_of() -> dict:
            nonlocal cache
            if cache is None:
                try:
                    cache = dict(self._meta(payload) or {})
                except Exception:
                    cache = {}
            return cache

        carts: list[Cart] = []
        touched: list[tuple[str, str]] = []
        for target, road in ts.outgoing(scroll, payload.source):
            if road.event != payload.mode:
                continue
            flt = road.filter
            info = meta_of() if _needs_meta(flt, payload) else (cache or {})
            ok, why = passes(flt, payload, info, target.id)
            orc = target.garrison.handler(road.handler) if road.handler else None
            if ok and orc is not None and orc.uses_model and meta_of().get("subtype") == "personal":
                ok, why = False, "personal node never goes to a model"
            if not ok:
                carts.append(self._cart(road, target.id, FILTERED, payload, why, now))
                continue
            if orc is None:
                self._arrive(target.id, payload)
                carts.append(self._cart(road, target.id, DELIVERED, payload, "", now))
                continue
            with self._lock:
                st = self.states.setdefault((target.id, orc.id), HandlerState())
                st.snapshot[road.id] = (payload, dict(meta_of()) if orc.uses_model or orc.kind == "chain" else {})
                st.last_event, st.dirty = now, True
                if st.running and orc.run_policy["restart_on_new"] and st.cancel is not None:
                    st.cancel.set()
            why = script_problem(orc, self.repo_root) if orc.kind in ("script", "hybrid") else ""
            carts.append(self._cart(road, target.id, HELD if why else SENT, payload, why or orc.name, now))
            touched.append((target.id, orc.id))
        if touched:
            self.tick(now)
        return carts

    def tick(self, now: float | None = None) -> None:
        """Start every handler whose data changed and whose quiet period is over."""
        scroll = self._scroll()
        if scroll is None:
            return
        now = self._clock() if now is None else now
        with self._lock:
            due = []
            for (target_id, orc_id), st in self.states.items():
                if not st.dirty or st.running:
                    continue
                b = scroll.building(target_id)
                orc = b.garrison.handler(orc_id) if b else None
                if orc is None:
                    st.dirty = False
                    continue
                if now - st.last_event >= orc.run_policy["quiet_s"]:
                    due.append((b, orc, st))
        for b, orc, st in due:
            self._start(b, orc, st, now)

    def stop(self) -> None:
        with self._lock:
            for st in self.states.values():
                if st.cancel is not None:
                    st.cancel.set()

    # -- runs ------------------------------------------------------------------------------------------

    def _records(self, b: ts.BuildingSpec, orc: ts.OrcSpec, st: HandlerState) -> list[dict]:
        live = {r.id for r in b.roads_of(orc.id)}
        for rid in [rid for rid in st.snapshot if rid not in live]:
            del st.snapshot[rid]           # the road was unsubscribed or moved to another handler
        return [chains.record_of(rid, p, m) for rid, (p, m) in st.snapshot.items()]

    def _start(self, b: ts.BuildingSpec, orc: ts.OrcSpec, st: HandlerState, now: float) -> None:
        with self._lock:
            records = self._records(b, orc, st)
            carts = [p for p, _ in st.snapshot.values()]
            st.dirty = False
            st.generation += 1
            gen = st.generation
            run = HandlerRun(b.id, orc.id, orc.kind, uuid.uuid4().hex, now,
                             roads=tuple(r["road"] for r in records), inputs=records,
                             trail=pipes.merge_trails(*(p.trail for p in carts)),
                             ref=next((p.ref for p in carts if p.ref), ""))
        if orc.kind == "chain":
            result = chains.run_chain(orc.chain, records)
            self._finish(b, orc, run, "done" if result.ok else "error", result.markdown, result.error)
            return
        if orc.kind in ("script", "hybrid"):
            why = script_problem(orc, self.repo_root)
            if why:
                self._finish(b, orc, run, "held", "", why)
                return
            cancel = threading.Event()
            with self._lock:
                st.running, st.cancel = True, cancel
            threading.Thread(target=self._script_thread, args=(b, orc, st, run, records, cancel, gen),
                             daemon=True, name=f"script-{b.id}-{orc.id}").start()
            return
        if not self._budget_ok():
            self._finish(b, orc, run, "no_gold", "", "🪙 budget exhausted")
            return
        cancel = threading.Event()
        with self._lock:
            st.running, st.cancel = True, cancel
        threading.Thread(target=self._agent_thread, args=(b, orc, st, run, records, cancel, gen),
                         daemon=True, name=f"orc-{b.id}-{orc.id}").start()

    def _script_thread(self, b: ts.BuildingSpec, orc: ts.OrcSpec, st: HandlerState, run: HandlerRun,
                       records: list[dict], cancel: threading.Event, gen: int) -> None:
        """A reviewed script: records on stdin, Markdown on stdout. A hybrid's exit 3
        hands the records and what the script found to its agent harness."""
        outcome, text, error = "done", "", ""
        try:
            code, text, err = run_handler_script(self.repo_root / orc.script["path"], records, self.repo_root, cancel)
            if code == ESCALATE and orc.kind == "hybrid":
                if not self._budget_ok():
                    outcome, error = "no_gold", "🪙 budget exhausted — the script asked for the agent"
                else:
                    self._agent_thread(b, orc, st, run, records, cancel, gen, previous=text)
                    return
            elif code != 0:
                outcome, error = "error", f"exit {code}: {(err or text).strip()[:300]}"
        except InterruptedError:
            outcome, error = "interrupted", "restarted by a new event"
        except Exception as e:  # a failing script must not take the app down
            outcome, error = "error", str(e)[:300]
        with self._lock:
            st.running, st.cancel = False, None
            stale = gen != st.generation or cancel.is_set()
        if stale and outcome == "done":
            outcome, error, text = "interrupted", "restarted by a new event", ""
        self._finish(b, orc, run, outcome, text, error)
        if outcome == "interrupted":
            self.tick()

    def _agent_thread(self, b: ts.BuildingSpec, orc: ts.OrcSpec, st: HandlerState, run: HandlerRun,
                      records: list[dict], cancel: threading.Event, gen: int, previous: str = "") -> None:
        env = {**self._run_env, "ORKCRAFT_ORC": f"{b.id}/{orc.id}"}
        text, error, outcome, total, tokens = previous, "", "done", None, None
        from orkcraft.realm import feedback
        liked = [str(r.get("value", "")) for r in feedback.examples(self.repo_root, b.id, 3)]
        try:
            used: list[str] = []
            steps = self.steps_of(b, orc)
            for step in steps:
                prompt = agent_prompt(orc, b, records, step["role"], previous=text, liked=liked)
                model = tiers.step_model(step)       # a runner is called with a model only when there is one
                if (said := model or str(step.get("harness") or "")) and said not in used:
                    used.append(said)
                    run.model = "+".join(used)
                answer = self._agent_runner(step["harness"], prompt, self.repo_root, env, cancel,
                                            *((model,) if model else ()))
                text, cost = answer[0], answer[1]          # a runner may also say its tokens
                if cost is not None:
                    total = (total or 0.0) + cost
                if len(answer) > 2 and answer[2] is not None:
                    tokens = (tokens or 0) + answer[2]
        except InterruptedError:
            outcome, error = "interrupted", "restarted by a new event"
        except Exception as e:  # a failing orc must not take the app down
            outcome, error = "error", str(e)[:300]
            if isinstance(e, tool_errors.ToolError):
                run.failure = e
        run.cost_usd, run.tokens = total, tokens
        with self._lock:
            st.running, st.cancel = False, None
            stale = gen != st.generation or cancel.is_set()
        if stale and outcome == "done":
            outcome, error, text = "interrupted", "restarted by a new event", ""
        self._finish(b, orc, run, outcome, text, error)
        if outcome == "interrupted":
            self.tick()                     # the fresh snapshot is waiting (dirty)

    def steps_of(self, b: ts.BuildingSpec, orc: ts.OrcSpec) -> list[dict]:
        """The harness steps a handler thinks with: a road rule's are its steward's, the others' their own."""
        if orc.on_steward:
            try:
                goal = self._aim(b.id)
            except Exception:  # the goal cannot be read: the building's own
                goal = None
            return steward_steps(b, goal, orc.tier)
        return orc.harness or ts.DEFAULT_HARNESS

    def _finish(self, b: ts.BuildingSpec, orc: ts.OrcSpec, run: HandlerRun, outcome: str,
                markdown: str, error: str) -> None:
        run.ended, run.outcome, run.markdown, run.error = self._clock(), outcome, markdown, error
        run.trail = run.trail + (pipes.hop(b.id, orc.id, orc.kind, run.tokens, run.cost_usd, outcome=outcome,
                                           since=max(0.0, run.ended - run.started), model=run.model,
                                           decision=error if outcome != "done" else "", run=run.run_id),)
        with self._lock:
            self.state(b.id, orc.id).runs += 1
            self.runs = (self.runs + [run])[-200:]
        if outcome == "done" and orc.uses_model:
            self._keep_example(run)
        if outcome == "done" and self._on_output is not None:
            self._call(self._on_output, b.id, orc, f"{orc.avatar} {orc.name} · {b.title}", markdown,
                       run.trail, run.ref)
        if self._on_run is not None:
            self._call(self._on_run, run)

    def _keep_example(self, run: HandlerRun) -> None:
        """An agent's input → output, for the steward's demotion proposals and their replay.
        Local and git-ignored; personal nodes never get here (they never reach an agent)."""
        path = examples_file(self.repo_root, run.target, run.orc_id)
        entry = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "run_id": run.run_id, "inputs": run.inputs,
                 "output": run.markdown[:EXAMPLE_OUTPUT_CHARS], "cost_usd": run.cost_usd, "tokens": run.tokens}
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except (OSError, TypeError, ValueError):
            pass

    def _arrive(self, target_id: str, payload: Payload) -> None:
        """A plain road's cart reaches its building — at once, or after the travel time the face asked for
        (so a person sees it on the road before the building acts on it)."""
        try:
            wait = float(self._travel() or 0.0)
        except (TypeError, ValueError):
            wait = 0.0
        if wait <= 0:
            self._call(self._deliver, target_id, payload)
            return
        timer = threading.Timer(wait, self._call, (self._deliver, target_id, payload))
        timer.daemon = True
        timer.start()

    def _cart(self, road: ts.Road, target: str, status: str, payload: Payload, detail: str, now: float) -> Cart:
        cart = Cart(road.id, road.source, target, status, payload, detail, now)
        with self._lock:
            self.carts = (self.carts + [cart])[-500:]
        if self._on_cart is not None:
            self._call(self._on_cart, cart)
        return cart
