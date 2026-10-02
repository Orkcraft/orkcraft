"""🛠 The Workshop: a building made from scratch — its script runs on every cart.

The script and its contract live in realm/workshop.py. A cart runs it off the UI thread; exit 0
sends `workshop.done`, 4 `workshop.alert`, anything else `workshop.failed`; exit 3 hands the cart
to the steward prompt (one model call, never in the demo, never past the budget). The layout the
operator chose in the interview decides the right pane: the run log, a table of the latest JSON
rows, or a card of its fields. ▶ runs the last cart again; 🧪 runs the blueprint's mock carts in
the sandbox and shows the log; `e` edits the script (a checkpoint, so Z takes it back).
"""
from __future__ import annotations

import threading

from rich.table import Table
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from orkcraft.realm import pipes, roads, workshop
from orkcraft.screens.dialogs import TextBlock
from orkcraft.screens.typed.base import TypedView

INPUT_LIMIT = 256 * 1024
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


def mini_line(r: workshop.Run) -> str:
    mark = {"done": "✓", "alert": "!", "escalated": "?"}.get(r.outcome, "✗")
    first = (r.result or r.err).splitlines()[0][:14] if (r.result or r.err) else ""
    return f"{mark} {r.at[11:16]} {first}"


class WorkshopView(TypedView):
    TYPE = "workshop"
    BINDINGS = [Binding("e", "edit_script", "Edit script")]
    steward_runner = None                # tests put a fake model here

    def __init__(self, *a, **kw) -> None:
        super().__init__(*a, **kw)
        self.runs: list[workshop.Run] = []
        self.running = False
        self.last_cart: dict | None = None
        self.tests: list[workshop.Run] = []

    @property
    def runtime(self) -> str:
        return str(self.config.get("runtime") or "python")

    @property
    def ws_layout(self) -> str:
        return str(self.config.get("layout") or "log")

    @property
    def script(self):
        return workshop.script_path(self._get_repo_root(), self.building_id, self.runtime)

    def compose_body(self) -> ComposeResult:
        yield Static("", id="ws-head", classes="typed-head")
        with Horizontal(classes="typed-row"):
            yield OptionList(id="ws-runs", classes="typed-list")
            with VerticalScroll(classes="typed-detail"):
                yield Static("", id="ws-out")

    def on_mount(self) -> None:
        import datetime as dt
        self.last_tick = dt.datetime.now()            # its timer fires from now on
        super().on_mount()
        self.set_interval(TICK_S, self.tick)

    def tick(self, now=None) -> bool:
        """Its own timer: on schedule a `workshop.tick` cart runs the script."""
        import datetime as dt

        from orkcraft.realm import watch
        expr = str(self.config.get("schedule") or "").strip()
        now = now or dt.datetime.now()
        if not expr or not watch.cron_due(expr, getattr(self, "last_tick", None), now):
            return False
        self.last_tick = now
        return self.run_cart(workshop.cart("workshop.tick", self.building_id, now.isoformat(timespec="seconds"),
                                           "timer"))

    def refresh_data(self) -> None:
        self.runs = workshop.runs(self.state_dir)
        if self.runs and self.last_cart is None:
            r = self.runs[0]
            self.last_cart = workshop.cart(r.event, r.source, r.input)
        self._render_list()

    # -- running --------------------------------------------------------------------------------

    def receive(self, payload: pipes.Payload, title: str, markdown: str) -> None:
        value = payload.value
        if payload.kind == pipes.FILE:
            try:
                value = (self._get_repo_root() / payload.value).read_text(encoding="utf-8", errors="replace")
            except OSError:
                value = markdown or payload.value
        self.run_cart(workshop.cart(payload.mode, payload.source, value[:INPUT_LIMIT], title))

    def run_cart(self, the_cart: dict) -> bool:
        if self.running:
            return False
        self.running, self.last_cart = True, the_cart
        script, runtime, repo, app = self.script, self.runtime, self._get_repo_root(), self.app
        prompt = str(self.config.get("steward_prompt") or "")
        may_ask = bool(prompt) and not self.simulated and not getattr(app, "gold_exhausted", lambda: False)()
        runner = type(self).steward_runner
        from orkcraft.realm import feedback
        liked = [str(r.get("value", "")) for r in feedback.references(repo, self.building_id, 3)]
        self._render_list()

        def work() -> None:
            r = workshop.run(script, runtime, the_cart, repo)
            if r.code == workshop.ESCALATE and may_ask:
                from orkcraft.realm import builders
                try:
                    r.steward = (runner or builders.claude_runner)(workshop.steward_prompt(prompt, the_cart, r.out, liked))[0].strip()
                except Exception as e:  # the model is out of reach: the cart stays escalated
                    r.err = (r.err + f"\nsteward: {e}").strip()[:workshop.OUT_KEEP]
            try:
                app.call_from_thread(self.finish, r)
            except Exception:
                self.running = False

        threading.Thread(target=work, daemon=True, name=f"workshop-{self.building_id}").start()
        return True

    def finish(self, r: workshop.Run) -> None:
        self.running = False
        try:
            workshop.log(self.state_dir, r)
        except OSError:
            pass
        title = self.spec.get("title", self.building_id)
        if r.outcome == "done":
            self.emit("workshop.done", r.result, title)
        elif r.outcome == "alert":
            self.emit("workshop.alert", r.result, title)
        elif r.outcome == "failed":
            self.emit("workshop.failed", r.err or f"exit {r.code}", title)
            on_run = getattr(self.app, "on_handler_run", None)
            if on_run is not None:
                on_run(roads.HandlerRun(self.building_id, "tinker", "script", r.at, 0.0, 0.0, outcome="error",
                                        error=r.err or f"exit {r.code}"))
        self.refresh_data()

    def run_tests(self) -> list[workshop.Run]:
        bp = workshop.load_blueprint(self._get_repo_root(), self.building_id)
        source = workshop.load_script(self._get_repo_root(), self.building_id, self.runtime)
        self.tests = workshop.sandbox(source, self.runtime, bp.get("mocks") or [])
        self._render_list()
        return self.tests

    def action_edit_script(self) -> None:
        source = workshop.load_script(self._get_repo_root(), self.building_id, self.runtime)

        def done(text: str | None) -> None:
            if text is None or text == source:
                return
            why = workshop.check_syntax(text, self.runtime)
            if why:
                self.app.notify(why, title="🛠 Script not saved", severity="error")
                return
            workshop.save_script(self._get_repo_root(), self.building_id, self.runtime, text)
            mark = getattr(self.app, "checkpoint", None)
            if mark is not None:
                mark("update", self.building_id, "script edited")
            self._render_list()

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
        lst.clear_options()
        shown = self.tests or self.runs
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
        if self.running:
            return ["🛠 running…"]
        if not self.runs:
            return ["waiting for a cart"]
        return [mini_line(self.runs[0]), f"{len(self.runs)} run{'s' if len(self.runs) != 1 else ''}"]

    def quick_action(self, action_id: str) -> bool:
        if action_id == "workshop.run":
            if self.last_cart is None:
                self.app.notify("no cart yet — a road brings one, or 🧪 tests the mocks", title="🛠 Workshop")
            elif not self.run_cart(self.last_cart):
                self.app.notify("already running", title="🛠 Workshop")
            return True
        if action_id == "workshop.test":
            tests = self.run_tests()
            ok = sum(1 for r in tests if r.ok)
            self.app.notify(f"{ok}/{len(tests)} mock carts passed", title="🧪 Sandbox")
            return True
        return False
