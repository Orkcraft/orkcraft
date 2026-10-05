"""⚙️ The Mill: changes what arrives, step by step — a map, or a flat map when the result is records.

A cart's value (a file's content for a file) goes through the steps (realm/mill.py) off the UI
thread, one cart at a time: what arrives while it mills waits in a queue (no limit, nothing is
dropped). The result goes out as `mill.done`, each of its records as `mill.item`, a failing step as
`mill.failed`. ▶ runs the steps again on the last input; `e` in the open building edits the steps,
one per line. The newest runs are kept in `.orkcraft/mill/<id>/runs.jsonl`.

The milling — the queue, the thread, what goes out — is the building's worker's
(core/workers/mill.py). The view draws its runs and holds the keys.
"""
from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from orkcraft.core.workers.mill import HELP, INPUT_LIMIT, KEEP_RUNS, MillWorker  # noqa: F401 (old names)
from orkcraft.realm import jobs, mill
from orkcraft.screens.dialogs import TextBlock
from orkcraft.screens.typed.base import TypedView


class MillView(TypedView):
    TYPE = "mill"
    UI_PANES = {"steps": "#mill-head", "runs": "#mill-runs", "run": "#mill-out", "queue": "#mill-head"}
    BINDINGS = [Binding("e", "edit_steps", "Edit steps")]

    @property
    def worker(self) -> MillWorker:
        return super().worker

    # -- the worker's state, as the view's own (tests and other views read these) -------------------

    @property
    def runs(self) -> list[jobs.Job]:
        return self.worker.runs

    @property
    def running(self) -> bool:
        return self.worker.running

    @running.setter
    def running(self, value: bool) -> None:
        self.worker.running = value

    @property
    def queue(self):
        return self.worker.queue

    @property
    def cancel(self):
        return self.worker.cancel

    @property
    def last_input(self) -> str:
        return self.worker.last_input

    @property
    def steps(self) -> list[str]:
        return self.worker.steps

    @property
    def log(self) -> jobs.Log:
        return self.worker.log

    def receive(self, payload, title: str, markdown: str) -> None:
        self.worker.receive(payload, title, markdown)

    def run_steps(self, text: str, trigger: str = "manual", title: str = "", trail: tuple = (), ref: str = "") -> bool:
        return self.worker.run_steps(text, trigger, title, trail, ref)

    def _agent(self) -> mill.Agent:
        return self.worker._agent()

    def halt(self) -> int:
        return self.worker.halt()

    def status(self) -> str:
        return self.worker.status()

    # -- the view -----------------------------------------------------------------------------------

    def compose_body(self) -> ComposeResult:
        yield Static("", id="mill-head", classes="typed-head")
        with Horizontal(classes="typed-row"):
            yield OptionList(id="mill-runs", classes="typed-list")
            with VerticalScroll(classes="typed-detail", id="mill-out"):
                yield Static("", id="mill-run", markup=False, classes="-as-written")

    def refresh_data(self) -> None:
        self.worker.refresh()

    def redraw(self) -> None:
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
            self.query_one("#mill-run", Static).update(t)
        except Exception:
            pass

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        if event.option_list.id == "mill-runs":
            event.stop()
            job = next((j for j in self.runs if j.id == event.option.id), None)
            if job is not None:
                self._show(job)

    def action_edit_steps(self) -> None:
        def done(text: str | None) -> None:
            if text is not None and self.worker.set_steps(text.splitlines()):
                self.spec = self.worker.spec
                self._render_list()

        self.app.push_screen(TextBlock("⚙️ The Mill — steps, one per line", "\n".join(self.steps), HELP), done)

    # -- the hut ----------------------------------------------------------------------------------

    def mini_status(self) -> list[str]:
        return self.worker.mini_status()

    def hut_lines(self, widths: list[int]) -> list[str]:
        return self.worker.hut_lines(widths)

    def quick_action(self, action_id: str) -> bool:
        return self.worker.quick_action(action_id)
