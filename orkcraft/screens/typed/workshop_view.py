"""🛠 The Workshop: a building made from scratch — its script runs on every cart.

The script and its contract live in realm/workshop.py. A cart runs it off the UI thread; exit 0
sends `workshop.done`, 4 `workshop.alert`, anything else `workshop.failed`; exit 3 hands the cart
to the steward prompt (one model call, never in the demo, never past the budget). The layout the
operator chose in the interview decides the right pane: the run log, a table of the latest JSON
rows, or a card of its fields. ▶ runs the last cart again; 🧪 runs the blueprint's mock carts in
the sandbox and shows the log; `e` edits the script (a checkpoint, so Z takes it back).

The work — running, the schedule, the tests, saving the script — is the building's worker's
(core/workers/workshop.py). The view draws its runs and holds the editor and its timer.
"""
from __future__ import annotations

from rich.table import Table
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from orkcraft.core.workers.workshop import WorkshopWorker, mini_line  # noqa: F401  (the builder's preview)
from orkcraft.realm import pipes, workshop
from orkcraft.screens.dialogs import TextBlock
from orkcraft.screens.typed.base import TypedView

TICK_S = 30


def render_run(layout: str, r: workshop.Run):
    """How a run shows in the open Workshop — a table, a card, or input and output (also the
    blueprint's preview, T1108 stage 15)."""
    if layout != "log" and r.ok and r.result:
        kind, data = workshop.shape(r.result)
        if kind == "rows" and layout == "table":
            cols = list(dict.fromkeys(k for row in data for k in row))[:8]
            table = Table(*cols, expand=True)
            for row in data:
                table.add_row(*(str(row.get(c, ""))[:40] for c in cols))
            return table
        if kind == "card":
            t = Text()
            for k, v in list(data.items())[:20]:
                t.append(f"{k}\n", style="dim")
                t.append(f"{v}\n\n", style="bold")
            return t
    t = Text()
    t.append("in  ", style="bold cyan")
    t.append(r.input[:2000] + "\n\n")
    t.append("out ", style="bold green" if r.ok else "bold red")
    t.append((r.result or "") + ("\n" + r.err if r.err else ""))
    t.append(f"\n\nexit {r.code} · {r.ms} ms", style="dim")
    return t


class WorkshopView(TypedView):
    TYPE = "workshop"
    UI_PANES = {"head": "#ws-head", "runs": "#ws-runs", "run": "#ws-detail", "tests": "#ws-tests"}
    BINDINGS = [Binding("e", "edit_script", "Edit script")]

    @property
    def worker(self) -> WorkshopWorker:
        return super().worker

    # -- the worker's state, as the view's own (tests and other views read these) ------------------

    @property
    def runs(self) -> list[workshop.Run]:
        return self.worker.runs

    @property
    def running(self) -> bool:
        return self.worker.running

    @property
    def last_cart(self) -> dict | None:
        return self.worker.last_cart

    @property
    def tests(self) -> list[workshop.Run]:
        return self.worker.tests

    @property
    def last_tick(self):
        return self.worker.last_tick

    @last_tick.setter
    def last_tick(self, value) -> None:
        self.worker.last_tick = value

    @property
    def runtime(self) -> str:
        return self.worker.runtime

    @property
    def ws_layout(self) -> str:
        return self.worker.layout

    @property
    def script(self):
        return self.worker.script

    def compose_body(self) -> ComposeResult:
        yield Static("", id="ws-head", classes="typed-head")
        with Horizontal(classes="typed-row"):
            yield OptionList(id="ws-runs", classes="typed-list")
            with VerticalScroll(classes="typed-detail", id="ws-detail"):
                yield Static("", id="ws-out", classes="-as-written")
        yield Static("", id="ws-tests", classes="typed-head")

    def on_mount(self) -> None:
        super().on_mount()
        self.set_interval(TICK_S, self.tick)

    def tick(self, now=None) -> bool:
        """Its own timer: on schedule a `workshop.tick` cart runs the script."""
        return self.worker.tick(now)

    def refresh_data(self) -> None:
        self.worker.refresh()

    def redraw(self) -> None:
        self._render_list()

    # -- running --------------------------------------------------------------------------------

    def receive(self, payload: pipes.Payload, title: str, markdown: str) -> None:
        self.worker.receive(payload, title, markdown)

    def run_cart(self, the_cart: dict) -> bool:
        return self.worker.run_cart(the_cart)

    def finish(self, r: workshop.Run) -> None:
        self.worker.finish(r)

    def run_tests(self) -> list[workshop.Run]:
        return self.worker.run_tests()

    def action_edit_script(self) -> None:
        source = self.worker.source()

        def done(text: str | None) -> None:
            if text is None:
                return
            why = self.worker.save_script(text)
            if why:
                self.app.notify(why, title="🛠 Script not saved", severity="error")

        self.app.push_screen(TextBlock(f"🛠 {self.spec.get('title', '')} — {self.script.name}", source,
                                       "stdin: the cart as JSON · exit 0 done · 3 steward · 4 alert"), done)

    # -- the view -------------------------------------------------------------------------------

    def _render_list(self) -> None:
        try:
            head, lst = self.query_one("#ws-head", Static), self.query_one("#ws-runs", OptionList)
        except Exception:
            return
        steward = " · steward on exit 3" if self.config.get("steward_prompt") else ""
        if self.config.get("schedule"):
            steward += f" · ⏰ {self.config['schedule']}"
        head.update(Text.assemble((f"🛠 {self.script.name} ({self.runtime}) · layout {self.ws_layout}{steward}", "dim"),
                                  (" · running…" if self.running else "", "yellow")))
        tests = self.tests
        try:
            self.query_one("#ws-tests", Static).update(
                Text(f"🧪 {sum(1 for r in tests if r.ok)}/{len(tests)} mock carts passed · the list shows them", style="dim")
                if tests else "")
        except Exception:
            pass
        lst.clear_options()
        shown = tests or self.runs
        for i, r in enumerate(shown):
            row = Text(no_wrap=True, overflow="ellipsis")
            mark = {"done": ("✓ ", "green"), "alert": ("! ", "yellow"), "escalated": ("? ", "yellow")}.get(
                r.outcome, ("✗ ", "red"))
            row.append(("🧪" if self.tests else "") + mark[0], style=mark[1])
            row.append(f"{r.at[11:19]} {r.event or 'cart'}  ")
            row.append((r.result or r.err).replace("\n", " ⏎ ")[:80], style="dim")
            lst.add_option(Option(row, id=f"r{i}"))
        if shown:
            lst.highlighted = 0
            self._show(shown[0])
        else:
            self._out(Text("no carts yet — a road brings them; 🧪 runs the mock carts", style="dim"))

    def _out(self, renderable) -> None:
        try:
            self.query_one("#ws-out", Static).update(renderable)
        except Exception:
            pass

    def _show(self, r: workshop.Run) -> None:
        self._out(render_run(self.ws_layout, r))

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        if event.option_list.id == "ws-runs" and event.option.id:
            event.stop()
            shown = self.tests or self.runs
            i = int(event.option.id[1:])
            if i < len(shown):
                self._show(shown[i])

    # -- the hut --------------------------------------------------------------------------------

    def mini_status(self) -> list[str]:
        return self.worker.mini_status()

    def hut_lines(self, widths: list[int]) -> list[str]:
        return self.worker.hut_lines(widths)

    def quick_action(self, action_id: str) -> bool:
        if action_id == "workshop.run":
            why = self.worker.run_again()
            if why:
                self.app.notify(why, title="🛠 Workshop")
            return True
        if action_id == "workshop.test":
            tests = self.run_tests()
            ok = sum(1 for r in tests if r.ok)
            self.app.notify(f"{ok}/{len(tests)} mock carts passed", title="🧪 Sandbox")
            return True
        return False
