"""⚙️ The Mill: changes what arrives, step by step — a map, or a flat map when the result is records.

A cart's value (a file's content for a file) goes through the steps (realm/mill.py) off the UI
thread, one cart at a time: what arrives while it mills waits in a queue (no limit, nothing is
dropped). The result goes out as `mill.done`, each of its records as `mill.item`, a failing step as
`mill.failed`. ▶ runs the steps again on the last input; `e` in the open building edits the steps,
one per line. The newest runs are kept in `.orkcraft/mill/<id>/runs.jsonl`.
"""
from __future__ import annotations

import threading
import uuid
from collections import deque

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from orkcraft import scroll as ts
from orkcraft.realm import jobs, mill, pipes, roads
from orkcraft.screens.dialogs import TextBlock
from orkcraft.screens.typed.base import TypedView

INPUT_LIMIT = 256 * 1024
KEEP_RUNS = 200
HELP = ("lines · grep: rx · drop: rx · replace: rx => with · trim · lower · dedupe · csv · json · "
        "extract: field = rx · pick: a, b · sort: field [desc] [num|text] · limit: n · "
        "filter: field eq|ne|contains|matches|gt|ge|lt|le value · count · to_json · template: {field} · "
        "join[: sep] · script: command [|| agent: ask] · agent: ask")


def _simulated_agent(ask: str, text: str) -> str:
    """The showcase sandbox: agents never run there."""
    return f"_(demo — simulated)_ an agent would have done: {ask}"


class MillView(TypedView):
    TYPE = "mill"
    BINDINGS = [Binding("e", "edit_steps", "Edit steps")]

    def __init__(self, *a, **kw) -> None:
        super().__init__(*a, **kw)
        self.runs: list[jobs.Job] = []
        self.running = False
        self.last_input = ""
        self.queue: deque[tuple] = deque()     # (text, trigger, title, cut, trail, ref) — no limit
        self._carts: dict[str, tuple[tuple, str]] = {}     # a running job's trail and ref, to send on
        self.cancel = threading.Event()

    @property
    def steps(self) -> list[str]:
        return [str(s) for s in (self.config.get("steps") or [])]

    @property
    def log(self) -> jobs.Log:
        return jobs.Log(self.state_dir)

    def compose_body(self) -> ComposeResult:
        yield Static("", id="mill-head", classes="typed-head")
        with Horizontal(classes="typed-row"):
            yield OptionList(id="mill-runs", classes="typed-list")
            with VerticalScroll(classes="typed-detail"):
                yield Static("", id="mill-out", markup=False)

    def refresh_data(self) -> None:
        self.runs = self.log.read()
        if self.runs and not self.last_input:
            self.last_input = self.runs[0].input
        self._render_list()

    def _render_list(self) -> None:
        try:
            head, lst = self.query_one("#mill-head", Static), self.query_one("#mill-runs", OptionList)
        except Exception:
            return
        steps = " → ".join(self.steps) or "no steps yet — e edits them"
        busy = (" · milling…" + (f" +{len(self.queue)} waiting" if self.queue else "")) if self.running else ""
        head.update(Text.assemble(("⚙ " + steps, "dim"), (busy, "yellow")))
        lst.clear_options()
        for j in self.runs:
            row = Text(no_wrap=True, overflow="ellipsis")
            row.append("✓ " if j.ok else "✗ ", style="green" if j.ok else "red")
            row.append(f"{j.started[5:16].replace('T', ' ')} {j.trigger}  ")
            row.append((j.result if j.ok else j.error).replace("\n", " ⏎ ")[:80], style="dim")
            lst.add_option(Option(row, id=j.id))
        if self.runs:
            lst.highlighted = 0
            self._show(self.runs[0])

    def _show(self, job: jobs.Job) -> None:
        t = Text()
        t.append("in  ", style="bold cyan")
        t.append(job.input[:2000] + ("…" if len(job.input) > 2000 else "") + "\n\n")
        if job.meta.get("cut"):
            t.append(f"(cut to {INPUT_LIMIT // 1024} KB)\n\n", style="yellow")
        t.append("out ", style="bold green" if job.ok else "bold red")
        t.append(job.result if job.ok else job.error)
        if job.meta.get("items"):
            t.append(f"\n\n→ {job.meta['items']} records went out one by one", style="dim")
        if job.meta.get("agent"):
            t.append(f"\n🤖 an agent did {job.meta['agent']} step(s)", style="dim")
        try:
            self.query_one("#mill-out", Static).update(t)
        except Exception:
            pass

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        if event.option_list.id == "mill-runs":
            event.stop()
            job = next((j for j in self.runs if j.id == event.option.id), None)
            if job is not None:
                self._show(job)

    # -- milling ------------------------------------------------------------------------------------

    def _read_file(self, rel: str, fallback: str) -> str:
        """A file cart: its content — only a file inside the repository."""
        root = self._get_repo_root().resolve()
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
            self._render_list()
        return True

    def _agent(self) -> mill.Agent:
        if self.simulated:
            return _simulated_agent
        ask, app = mill.default_agent(self._get_repo_root(), self.cancel, str(self.config.get("model") or "")), self.app

        def gated(what: str, text: str) -> str:
            if getattr(app, "gold_exhausted", lambda: False)():
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
        job = jobs.Job(uuid.uuid4().hex[:8], title or self.spec.get("title", self.building_id), "mill", text,
                       started=jobs.now_iso(), outcome="running", trigger=trigger, meta={"cut": True} if cut else {})
        self._carts[job.id] = (trail, ref)
        steps, repo, app, agent = self.steps, self._get_repo_root(), self.app, self._agent()
        env, cancel = [str(n) for n in self.config.get("env") or []], self.cancel
        self._render_list()

        def work() -> None:
            r = mill.run_full(steps, text, repo, cancel, agent, env)
            job.result, job.error, job.ended = r.text, r.error, jobs.now_iso()
            job.outcome = "error" if r.error else "done"
            if r.agent_steps:
                job.meta["agent"] = r.agent_steps
            try:
                app.call_from_thread(self.finish, job, r.records)
            except Exception:
                self.running = False

        threading.Thread(target=work, daemon=True, name=f"mill-{self.building_id}").start()

    def _flat_map(self, records: list | None, title: str, cart: tuple = ((), "")) -> int:
        """Each record as its own cart — only when a road takes them (each cart is recorded)."""
        scroll = getattr(self.app, "scroll", None)
        values = mill.items(records)
        if not values or scroll is None or not ts.has_outgoing(scroll, self.building_id, "mill.item"):
            return 0
        trail, ref = cart
        return sum(self.emit("mill.item", v, title, trail=trail, ref=ref) for v in values)

    def finish(self, job: jobs.Job, records: list | None = None) -> None:
        self.running = False
        trail, ref = self._carts.pop(job.id, ((), ""))
        kind = "agent" if job.meta.get("agent") else "script"
        trail = tuple(trail) + (pipes.hop(self.building_id, "miller", kind, outcome="done" if job.ok else "error"),)
        if job.ok:
            if records:
                job.meta["items"] = len(mill.items(records))
            self.emit("mill.done", job.result, job.title, trail=trail, ref=ref)
            self._flat_map(records, job.title, (trail, ref))
        else:
            self.emit("mill.failed", job.error, job.title, trail=trail, ref=ref)
            on_run = getattr(self.app, "on_handler_run", None)
            if on_run is not None:
                kind = "agent" if job.meta.get("agent") else "script"
                on_run(roads.HandlerRun(self.building_id, "miller", kind, job.id, 0.0, 0.0, outcome="error",
                                        error=job.error))
        try:
            self.log.append(job)
            self.log.trim(KEEP_RUNS)
        except OSError:
            pass
        self.refresh_data()
        self._next()

    def action_edit_steps(self) -> None:
        def done(text: str | None) -> None:
            if text is None:
                return
            steps = [ln.strip() for ln in text.splitlines() if ln.strip()]
            if self.save_config({"steps": steps}):
                self._render_list()

        self.app.push_screen(TextBlock("⚙️ The Mill — steps, one per line", "\n".join(self.steps), HELP), done)

    # -- the hut ----------------------------------------------------------------------------------

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
        if not self.last_input:
            self.app.notify("nothing has arrived yet — a road brings the input", title="⚙️ The Mill")
        else:
            if self.running:
                self.app.notify("queued after the cart that is milling", title="⚙️ The Mill")
            self.run_steps(self.last_input)
        return True
