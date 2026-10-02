"""⚙️ The Mill: deterministic steps over what arrives — no model.

A cart's value (a file's content for a file) goes through the steps (realm/mill.py) off the UI
thread; the result goes out as `mill.done`, a failing step as `mill.failed`. ▶ runs the steps
again on the last input; `e` in the open building edits the steps, one per line. Every run is
kept in `.orkcraft/mill/<id>/runs.jsonl`.
"""
from __future__ import annotations

import threading
import uuid

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from orkcraft.realm import jobs, mill, pipes, roads
from orkcraft.screens.dialogs import TextBlock
from orkcraft.screens.typed.base import TypedView

INPUT_LIMIT = 256 * 1024
HELP = ("lines · grep: rx · drop: rx · replace: rx => with · trim · lower · dedupe · csv · json · "
        "extract: field = rx · pick: a, b · sort: field [desc] · limit: n · filter: field eq|ne|contains|matches value · "
        "count · to_json · template: {field} · join[: sep] · script: command")


class MillView(TypedView):
    TYPE = "mill"
    BINDINGS = [Binding("e", "edit_steps", "Edit steps")]

    def __init__(self, *a, **kw) -> None:
        super().__init__(*a, **kw)
        self.runs: list[jobs.Job] = []
        self.running = False
        self.last_input = ""

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
        head.update(Text.assemble(("⚙ " + steps, "dim"), (" · milling…" if self.running else "", "yellow")))
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
        t.append("out ", style="bold green" if job.ok else "bold red")
        t.append(job.result if job.ok else job.error)
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

    def receive(self, payload, title: str, markdown: str) -> None:
        text = payload.value
        if payload.kind == pipes.FILE:
            try:
                text = (self._get_repo_root() / payload.value).read_text(encoding="utf-8", errors="replace")
            except OSError:
                text = markdown or payload.value
        self.run_steps(text[:INPUT_LIMIT], "road")

    def run_steps(self, text: str, trigger: str = "manual") -> bool:
        if self.running:
            return False
        self.running, self.last_input = True, text
        job = jobs.Job(uuid.uuid4().hex[:8], self.spec.get("title", self.building_id), "mill", text,
                       started=jobs.now_iso(), outcome="running", trigger=trigger)
        steps, repo, app = self.steps, self._get_repo_root(), self.app
        self._render_list()

        def work() -> None:
            out, err = mill.run(steps, text, repo)
            job.result, job.error, job.outcome, job.ended = out, err, "error" if err else "done", jobs.now_iso()
            try:
                app.call_from_thread(self.finish, job)
            except Exception:
                self.running = False

        threading.Thread(target=work, daemon=True, name=f"mill-{self.building_id}").start()
        return True

    def finish(self, job: jobs.Job) -> None:
        self.running = False
        try:
            self.log.append(job)
        except OSError:
            pass
        if job.ok:
            self.emit("mill.done", job.result, job.title)
        else:
            self.emit("mill.failed", job.error, job.title)
            on_run = getattr(self.app, "on_handler_run", None)
            if on_run is not None:
                on_run(roads.HandlerRun(self.building_id, "miller", "script", job.id, 0.0, 0.0, outcome="error",
                                        error=job.error))
        self.refresh_data()

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
            lines.append("⚙ milling…")
        elif self.runs:
            j = self.runs[0]
            lines.append(("✓ " if j.ok else "✗ ") + j.started[11:16])
        return lines

    def quick_action(self, action_id: str) -> bool:
        if action_id != "mill.run":
            return False
        if not self.last_input:
            self.app.notify("nothing has arrived yet — a road brings the input", title="⚙️ The Mill")
        elif not self.run_steps(self.last_input):
            self.app.notify("already milling", title="⚙️ The Mill")
        return True
