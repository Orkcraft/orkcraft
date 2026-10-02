"""🛠 A building from scratch: the Builder's interview and the blueprint's review.

    BuilderInterview   1 what it is for · 2 one of three layouts · 3 the carts it takes · 4 what it sends
    BlueprintReview    the script (editable), the Council's verdict, the sandbox log of the mock carts;
                       Approve (only when nothing blocks and every mock cart passed), Re-run after an
                       edit, Reject with a note — the Builder tries again with it
"""
from __future__ import annotations

from typing import Callable

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, RadioButton, RadioSet, SelectionList, Static, TextArea

from orkcraft.realm import fastpath, workshop
from orkcraft.screens.council_review import verdict_text

CSS = """
BuilderInterview, BlueprintReview { align: center middle; }
#iv-box, #bp-box {
    width: 116; max-width: 97%; height: auto; max-height: 94%;
    border: thick $accent; background: $surface; padding: 1 2;
}
#iv-box { height: 94%; }
.iv-title { text-style: bold; color: $accent; padding-bottom: 1; }
.iv-section { text-style: bold; color: $accent; margin-top: 1; }
.iv-hint { color: $text-muted; }
#iv-form { height: 1fr; }
#iv-purpose { height: 5; }
#iv-layouts { height: auto; }
.iv-preview { width: 1fr; height: 6; border: round $surface-lighten-1; padding: 0 1; color: $text-muted; }
#iv-layout { width: 100%; height: auto; layout: horizontal; border: none; background: transparent; }
#iv-layout RadioButton { width: 1fr; }
#iv-errors, #bp-errors { color: $error; height: auto; }
.iv-buttons { height: 3; margin-top: 1; }
.iv-buttons Button { margin-right: 1; }
#bp-cols { height: 30; }
#bp-script { width: 3fr; height: 1fr; }
#bp-side { width: 2fr; height: 1fr; padding-left: 1; }
SelectionList { height: auto; max-height: 7; }
"""

PREVIEWS = {
    "log": "✓ 05:01 pit.text  3 words\n✓ 05:00 pit.text  12 words\n✗ 04:58 pit.link  exit 1",
    "table": "┌ name ──┬ count ┐\n│ alpha  │ 3     │\n│ beta   │ 12    │\n└────────┴───────┘",
    "card": "words\n  12\nstatus\n  ok",
}
EVENTS = (("workshop.done", "done — the script's output", True),
          ("workshop.failed", "failed — the error", True),
          ("workshop.alert", "alert — flagged output (exit 4)", False))


class BuilderInterview(ModalScreen[dict | None]):
    DEFAULT_CSS = CSS
    BINDINGS = [Binding("escape", "cancel", "Cancel"), Binding("ctrl+s", "draft", "Draft", priority=True)]
    AUTO_FOCUS = "#iv-purpose"

    def __init__(self, sources: list[tuple[str, str]], previous: dict | None = None) -> None:
        super().__init__()
        self.sources = sources            # ("source:event", label)
        self.previous = previous or {}

    def compose(self) -> ComposeResult:
        prev = self.previous
        with Vertical(id="iv-box"):
            yield Static("🛠 FROM SCRATCH · the Builder's interview — a script does the work, a model only "
                         "where it must", classes="iv-title", markup=False)
            with VerticalScroll(id="iv-form"):
                yield Label("1 · What should it do?", classes="iv-section")
                yield TextArea(str(prev.get("purpose") or ""), id="iv-purpose")
                yield Static("what comes in, what it should find or make, when it should raise an alert",
                             classes="iv-hint")
                yield Label("2 · How should it show its results?", classes="iv-section")
                with Horizontal(id="iv-layouts"):
                    for name, art in PREVIEWS.items():
                        yield Static(art, classes="iv-preview", markup=False)
                chosen = prev.get("layout") if prev.get("layout") in workshop.LAYOUTS else "log"
                with RadioSet(id="iv-layout"):
                    for name, label in (("log", "a log of runs"), ("table", "a table"), ("card", "a card")):
                        yield RadioButton(f"{name} — {label}", value=name == chosen, id=f"iv-layout-{name}")
                yield Label("3 · Which carts should it take?", classes="iv-section")
                if self.sources:
                    picked = set(prev.get("inputs") or [])
                    yield SelectionList(*[(label, value, value in picked) for value, label in self.sources],
                                        id="iv-inputs")
                else:
                    yield Static("no building sends anything yet — add roads later with Y", classes="iv-hint")
                yield Label("4 · What should it send along its roads?", classes="iv-section")
                sent = set(prev.get("events") or [e for e, _, on in EVENTS if on])
                yield SelectionList(*[(label, eid, eid in sent) for eid, label, _ in EVENTS], id="iv-events")
            yield Static("", id="iv-errors", markup=False)
            with Horizontal(classes="iv-buttons"):
                yield Button("🛠 Draft the blueprint [ctrl+s]", variant="success", id="iv-draft")
                yield Button("Cancel", id="iv-cancel")

    def answers(self) -> dict:
        layout = next((n for n in workshop.LAYOUTS if self.query_one(f"#iv-layout-{n}", RadioButton).value), "log")
        inputs = list(self.query_one("#iv-inputs", SelectionList).selected) if self.sources else []
        return {"purpose": self.query_one("#iv-purpose", TextArea).text.strip(), "layout": layout,
                "inputs": inputs, "events": list(self.query_one("#iv-events", SelectionList).selected)}

    def action_draft(self) -> None:
        a = self.answers()
        problems = []
        if len(a["purpose"]) < 10:
            problems.append("1 · say in a sentence what it should do")
        if not a["events"]:
            problems.append("4 · pick at least one event")
        if problems:
            self.query_one("#iv-errors", Static).update("\n".join(f"⚠ {p}" for p in problems))
            return
        self.dismiss(a)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if event.button.id == "iv-draft":
            self.action_draft()
        else:
            self.action_cancel()


EMULATE_STEP_S = 0.8

CHAT_CSS = """
BuilderChat { align: center middle; }
#chat-box { width: 116; max-width: 97%; height: 94%; border: thick $accent; background: $surface; padding: 1 2; }
#chat-log { height: 1fr; min-height: 9; border: round $surface-lighten-1; padding: 0 1; }
#chat-ready { height: auto; max-height: 20; overflow-y: auto; display: none; }
#chat-ready.-on { display: block; }
#chat-views { height: auto; }
.chat-view { width: 1fr; height: 6; border: round $surface-lighten-1; padding: 0 1; color: $text-muted; }
#chat-view-pick { width: 100%; height: auto; layout: horizontal; border: none; background: transparent; }
#chat-view-pick RadioButton { width: 1fr; }
#chat-input { margin-top: 1; }
#chat-errors { color: $error; height: auto; }
"""
GREETING = "What should the new building do? Tell me what comes in and what you want to see."


class BuilderChat(ModalScreen[dict | None]):
    """🛠 The Builder as a conversation: it asks until it knows what the building does,
    offers three views, the carts it takes and the events it sends; Draft makes the blueprint.
    Dismisses the interview for `blueprint.build` (with the conversation under "history"), "form"
    (the operator prefers the plain form), or None."""

    DEFAULT_CSS = CHAT_CSS
    BINDINGS = [Binding("escape", "cancel", "Cancel"), Binding("ctrl+s", "draft", "Draft", priority=True)]
    AUTO_FOCUS = "#chat-input"

    def __init__(self, sources: list[tuple[str, str]], ask: Callable, history: list[tuple[str, str]] | None = None,
                 opening: str = GREETING) -> None:
        super().__init__()
        self.sources, self.ask = sources, ask        # ask(history) -> blueprint.Turn (called off the UI thread)
        self.history: list[tuple[str, str]] = list(history or [])
        self.history.append(("builder", opening))
        self.turn = None
        self.thinking = False

    def compose(self) -> ComposeResult:
        with Vertical(id="chat-box"):
            yield Static("🛠 FROM SCRATCH · talk with the Builder — a script does the work, a model only where it must",
                         classes="iv-title", markup=False)
            with VerticalScroll(id="chat-log"):
                yield Static("", id="chat-text")
            with Vertical(id="chat-ready"):
                yield Label("Pick a view", classes="iv-section")
                yield Horizontal(id="chat-views")
                yield RadioSet(id="chat-view-pick")
                yield Label("Carts it takes", classes="iv-section")
                yield SelectionList(id="chat-inputs")
                yield Label("Events it sends", classes="iv-section")
                yield SelectionList(id="chat-events")
                yield Label("Its own timer (optional): every 15m · hourly · daily 05:00 · weekly mon 09:00",
                            classes="iv-section")
                yield Input(id="chat-schedule", placeholder="empty — it runs only when a cart arrives")
            yield Input(placeholder="answer the Builder · Enter sends", id="chat-input")
            yield Static("", id="chat-errors", markup=False)
            with Horizontal(classes="iv-buttons"):
                yield Button("🛠 Draft the blueprint [ctrl+s]", variant="success", id="chat-draft", disabled=True)
                yield Button("Use the form instead", id="chat-form")
                yield Button("Cancel", id="chat-cancel")

    def on_mount(self) -> None:
        self._render_log()

    def _render_log(self) -> None:
        t = Text()
        for who, text in self.history:
            t.append("🛠 Builder  " if who == "builder" else "🧑 You      " if who == "operator" else "· ",
                     style="bold cyan" if who == "builder" else "bold green" if who == "operator" else "dim")
            t.append(text + "\n\n")
        if self.thinking:
            t.append("🛠 Builder is thinking…\n", style="dim italic")
        self.query_one("#chat-text", Static).update(t)
        self.query_one("#chat-log", VerticalScroll).scroll_end(animate=False)

    # -- talking --------------------------------------------------------------------------------

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        if event.input.id != "chat-input":
            return
        text = event.value.strip()
        if not text or self.thinking:
            return
        event.input.value = ""
        self.history.append(("operator", text))
        self.thinking = True
        self.query_one("#chat-errors", Static).update("")
        self._render_log()
        history = list(self.history)

        def work() -> None:
            turn = self.ask(history)
            self.app.call_from_thread(self._answered, turn)

        self.run_worker(work, thread=True, name="builder-talk")

    def _answered(self, turn) -> None:
        self.thinking = False
        if turn.error:
            self.query_one("#chat-errors", Static).update(f"⚠ {turn.error} — answer again, or use the form")
        elif not turn.ready:
            self.history.append(("builder", "\n".join(f"• {q}" for q in turn.questions)))
        else:
            self.turn = turn
            self.history.append(("builder", f"I have enough. {turn.purpose}\n\nPick one of the three views, check "
                                            "the carts and the events, then Draft the blueprint."))
            self._show_ready(turn)
        self._render_log()

    def _show_ready(self, turn) -> None:
        views = self.query_one("#chat-views", Horizontal)
        views.remove_children()
        views.mount_all([Static(Text(f"{v['name']} · {v['layout']}\n", style="bold") + Text(v["preview"]),
                                classes="chat-view") for v in turn.views])
        pick = self.query_one("#chat-view-pick", RadioSet)
        pick.remove_children()
        pick.mount_all([RadioButton(f"{i + 1} · {v['name']}", value=i == 0, id=f"chat-view-{i}")
                        for i, v in enumerate(turn.views)])
        inputs = self.query_one("#chat-inputs", SelectionList)
        inputs.clear_options()
        inputs.add_options([(label, value, value in turn.inputs) for value, label in self.sources])
        events = self.query_one("#chat-events", SelectionList)
        events.clear_options()
        events.add_options([(label, eid, eid in turn.events) for eid, label, _ in EVENTS])
        self.query_one("#chat-schedule", Input).value = turn.schedule
        self.query_one("#chat-ready").add_class("-on")
        self.query_one("#chat-draft", Button).disabled = False

    def picks(self) -> tuple[int, list[str], list[str]]:
        view = next((i for i in range(3) if self.query(f"#chat-view-{i}") and
                     self.query_one(f"#chat-view-{i}", RadioButton).value), 0)
        return (view, list(self.query_one("#chat-inputs", SelectionList).selected),
                list(self.query_one("#chat-events", SelectionList).selected))

    def action_draft(self) -> None:
        if self.turn is None or self.thinking:
            return
        from orkcraft.realm import blueprint
        view, inputs, events = self.picks()
        schedule = self.query_one("#chat-schedule", Input).value.strip()
        if not events:
            self.query_one("#chat-errors", Static).update("⚠ pick at least one event")
            return
        from orkcraft.realm import watch
        if schedule and not watch.schedule_ok(schedule):
            self.query_one("#chat-errors", Static).update("⚠ timer: every 15m · hourly · daily 05:00 · weekly mon 09:00")
            return
        self.dismiss(blueprint.interview_from(self.turn, view, inputs, events, self.history, schedule))

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if event.button.id == "chat-draft":
            self.action_draft()
        elif event.button.id == "chat-form":
            self.dismiss("form")
        else:
            self.action_cancel()


def sandbox_text(runs: list[workshop.Run], blocked: bool) -> Text:
    t = Text()
    if blocked:
        t.append("the sandbox did not run — a rule blocks the script\n", style="bold red")
        return t
    if not runs:
        t.append("no mock carts\n", style="dim")
    for i, r in enumerate(runs, 1):
        mark, style = {"done": ("✓", "green"), "alert": ("!", "yellow"), "escalated": ("?", "yellow")}.get(
            r.outcome, ("✗", "bold red"))
        t.append(f"{mark} cart {i} ", style=style)
        t.append(f"{r.event or 'cart'} · exit {r.code} · {r.ms} ms\n", style="dim")
        t.append(f"  in  {r.input[:120]}\n")
        if r.out:
            t.append(f"  out {r.out[:300]}\n")
        if r.code == workshop.ESCALATE:
            t.append("  → the steward prompt takes this cart\n", style="yellow")
        if r.err:
            t.append(f"  err {r.err[:300]}\n", style="red")
    return t


class BlueprintReview(ModalScreen[tuple[str, object] | None]):
    """("approve", blueprint) · ("reject", the operator's note) · None (cancelled)."""

    DEFAULT_CSS = CSS
    BINDINGS = [Binding("escape", "cancel", "Cancel"), Binding("ctrl+s", "approve", "Approve", priority=True),
                Binding("ctrl+e", "emulate", "Emulate", priority=True),
                Binding("ctrl+r", "rerun", "Re-run", priority=True), Binding("ctrl+n", "reject", "Reject", priority=True)]

    def __init__(self, bp: dict, verdict: fastpath.Verdict, runs: list[workshop.Run],
                 recheck: Callable[[dict], tuple[fastpath.Verdict, list[workshop.Run]]], cost_usd: float | None = None) -> None:
        super().__init__()
        self.bp = dict(bp)
        self.verdict, self.runs = verdict, runs
        self.recheck = recheck
        self.cost_usd = cost_usd
        self.checked_script = bp.get("script") or ""
        self.checking = False

    @property
    def passed(self) -> bool:
        return not self.verdict.blocked and bool(self.runs) and all(r.ok for r in self.runs)

    def compose(self) -> ComposeResult:
        bp = self.bp
        cost = f" · ${self.cost_usd:.2f}" if self.cost_usd is not None else ""
        with Vertical(id="bp-box"):
            yield Static(f"🛠 BLUEPRINT · {bp.get('icon', '')} {bp.get('title', '')} [{bp.get('id', '')}] · "
                         f"{bp.get('runtime')} · layout {bp.get('layout')}{cost}", classes="iv-title", markup=False)
            yield Static(Text(bp.get("summary") or "", style="dim"))
            with Horizontal(id="bp-cols"):
                yield TextArea(bp.get("script") or "", id="bp-script", show_line_numbers=True)
                with VerticalScroll(id="bp-side"):
                    yield Label("🖼 Preview — how it will show a result", classes="iv-section")
                    yield Static("", id="bp-preview")
                    yield Label("▶ Emulation [ctrl+e] — the carts arriving, one by one", classes="iv-section")
                    yield Static("", id="bp-emulate")
                    yield Input(placeholder="try your own cart: type its value, Enter runs it in the sandbox",
                                id="bp-try")
                    yield Label("🧪 Sandbox — the mock carts", classes="iv-section")
                    yield Static("", id="bp-sandbox")
                    yield Label("🏛 Council", classes="iv-section")
                    yield Static("", id="bp-council")
                    if bp.get("steward_prompt"):
                        yield Label("🧙 Steward prompt (only on exit 3)", classes="iv-section")
                        yield Static(Text(f"{bp['steward_prompt']}\n\nwhy not a script: {bp.get('steward_why', '')}"))
            yield Static("", id="bp-errors", markup=False)
            with Horizontal(classes="iv-buttons"):
                yield Button("✓ Approve [ctrl+s]", variant="success", id="bp-approve")
                yield Button("▶ Emulate [ctrl+e]", id="bp-emulate-btn")
                yield Button("↻ Re-run [ctrl+r]", id="bp-rerun")
                yield Button("✗ Reject… [ctrl+n]", variant="error", id="bp-reject")
                yield Button("Cancel", id="bp-cancel")

    def on_mount(self) -> None:
        self.show()
        self.preview(self.runs[0] if self.runs else None)

    # -- the preview and the emulation --------------------------------------------

    def preview(self, r: workshop.Run | None) -> None:
        from orkcraft.screens.typed.workshop_view import mini_line, render_run
        if r is None:
            self.query_one("#bp-preview", Static).update(Text("no result to show yet", style="dim"))
            return
        hut = Text(f"on its hut: {self.bp.get('icon', '')} {self.bp.get('title', '')} · {mini_line(r)}\n\n", style="dim")
        body = render_run(str(self.bp.get("layout") or "log"), r)
        if isinstance(body, Text):
            self.query_one("#bp-preview", Static).update(hut + body)
        else:                                       # a table
            from rich.console import Group
            self.query_one("#bp-preview", Static).update(Group(hut, body))

    def action_emulate(self) -> None:
        """The mock carts arrive one by one: what came in, what the script did, what it sends."""
        if not self.runs or getattr(self, "_emulating", False):
            return
        self._emulating, self._step, self._log = True, 0, Text()
        self.set_timer(0.05, self._emulate_step)

    def _emulate_step(self) -> None:
        if not self.is_mounted:
            return
        i = self._step
        if i >= len(self.runs):
            self._log.append("■ done\n", style="dim")
            self.query_one("#bp-emulate", Static).update(self._log)
            self._emulating = False
            return
        r = self.runs[i]
        sends = {"done": "📤 workshop.done", "alert": "📤 workshop.alert", "escalated": "🧙 to the steward prompt"}.get(
            r.outcome, "📤 workshop.failed")
        self._log.append(f"📥 cart {i + 1} · {r.event or 'cart'} from {r.source or '?'}: {r.input[:40]!r}\n")
        self._log.append(f"   ⚙ exit {r.code} · {r.ms} ms → {sends}\n", style="green" if r.ok else "red")
        self.query_one("#bp-emulate", Static).update(self._log)
        self.preview(r)
        self._step += 1
        self.set_timer(EMULATE_STEP_S, self._emulate_step)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "bp-try":
            return
        event.stop()
        value = event.value
        event.input.value = ""
        first = (self.bp.get("mocks") or [{}])[0]
        source, runtime = self.query_one("#bp-script", TextArea).text, str(self.bp.get("runtime"))
        if self.verdict.blocked:
            self.query_one("#bp-errors", Static).update("a rule blocks the script — it does not run")
            return
        cart = workshop.cart(str(first.get("event") or "cart"), str(first.get("source") or "you"), value)

        def work() -> None:
            r = workshop.sandbox(source, runtime, [cart])[0]
            self.app.call_from_thread(self._tried, r)

        self.run_worker(work, thread=True, name="blueprint-try")

    def _tried(self, r: workshop.Run) -> None:
        log = getattr(self, "_log", None) or Text()
        log.append(f"📥 your cart: {r.input[:40]!r}\n   ⚙ exit {r.code} · {r.ms} ms\n", style="green" if r.ok else "red")
        self._log = log
        self.query_one("#bp-emulate", Static).update(log)
        self.preview(r)

    def show(self) -> None:
        self.query_one("#bp-sandbox", Static).update(sandbox_text(self.runs, self.verdict.blocked))
        self.query_one("#bp-council", Static).update(verdict_text(self.verdict))
        self.query_one("#bp-approve", Button).disabled = not self.passed or self.checking
        why = ("" if self.passed else "✗ a rule blocks it — edit the script, then re-run" if self.verdict.blocked
               else "✗ a mock cart failed — edit the script, then re-run" if self.runs else "")
        self.query_one("#bp-errors", Static).update(why)

    # -- actions --------------------------------------------------------------------------------

    def action_rerun(self) -> None:
        if self.checking:
            return
        source = self.query_one("#bp-script", TextArea).text
        why = workshop.check_syntax(source, str(self.bp.get("runtime")))
        if why:
            self.query_one("#bp-errors", Static).update(f"✗ the script does not parse: {why}")
            return
        self.bp["script"] = source
        self.checking = True
        self.query_one("#bp-errors", Static).update("↻ the Council and the sandbox are at it…")
        self.query_one("#bp-approve", Button).disabled = True
        bp = dict(self.bp)

        def work() -> None:
            verdict, runs = self.recheck(bp)
            self.app.call_from_thread(self._rechecked, source, verdict, runs)

        self.run_worker(work, thread=True, name="blueprint-recheck")

    def _rechecked(self, source: str, verdict: fastpath.Verdict, runs: list[workshop.Run]) -> None:
        self.checking = False
        self.checked_script, self.verdict, self.runs = source, verdict, runs
        self.show()
        self.preview(runs[0] if runs else None)

    def action_approve(self) -> None:
        if self.checking:
            return
        if self.query_one("#bp-script", TextArea).text != self.checked_script:
            self.query_one("#bp-errors", Static).update("the script changed — ctrl+r re-runs the sandbox first")
            return
        if self.passed:
            self.dismiss(("approve", dict(self.bp, script=self.checked_script)))

    def action_reject(self) -> None:
        """Back to the conversation with the Builder: say there what to change."""
        self.dismiss(("reject", ""))

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        {"bp-approve": self.action_approve, "bp-rerun": self.action_rerun, "bp-emulate-btn": self.action_emulate,
         "bp-reject": self.action_reject}.get(event.button.id or "", self.action_cancel)()
