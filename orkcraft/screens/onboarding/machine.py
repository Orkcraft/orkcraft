"""🧭 Onboarding, the machine: your AI tools and the day."""
from __future__ import annotations

from rich.text import Text
from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import Button, Checkbox, Label, Select, Static

from orkcraft import schedule, settings, tools
from orkcraft.widgets.day_bar import DAY_COLOR, QUIET_COLOR, DayBar
from orkcraft.realm import interview
from orkcraft.screens.onboarding.common import AGY_UNGUARDED, agy_warder_line, _buttons, _css, _nav, _title
from orkcraft.screens.onboarding.person import Chip


USE_OPTIONS = [(title, key) for key, title in interview.USES]
DETECTED = tuple[list[tools.ToolStatus], list[tools.Other]]


def detect_all() -> DETECTED:
    """Blocking: the CLIs orkcraft leads (a `--version` each) and the other AI tools installed."""
    return tools.detect(), tools.detect_others()


class ToolsStep(ModalScreen[dict | str | None]):
    """The AI tools installed here, one row each and nothing else: the CLIs orkcraft leads get a
    ✓ and how they are paid for; every one gets 👍 / 👎, and a 👍 or 👎 opens what for — "good for
    documentation", "weak at tickets". The ones not found are named once, dimly, under the rows.
    Dismisses {"action": "next", "tools": {...}, "ratings": {...}, "detected": ..., "warder": bool},
    {"action": "skip", "tools": {...}}, "back" or None. `chosen` / `ratings`: what was picked before."""

    BINDINGS = [Binding("escape", "back", "Back")]
    DEFAULT_CSS = _css("ToolsStep", 100) + """
    ToolsStep #ob-tools-list { height: auto; margin-bottom: 1; }
    ToolsStep .ob-tool { height: 1; margin-top: 0; }
    ToolsStep .ob-tool Checkbox { width: 24; height: 1; border: none; padding: 0; background: transparent; }
    ToolsStep .ob-tool .ob-tool-name { width: 24; padding-left: 4; }
    ToolsStep .ob-tool .ob-billing { width: 16; height: 1; margin-right: 1; }
    ToolsStep .ob-tool .ob-billing-gap { width: 17; }
    ToolsStep .ob-tool Select { height: 1; }
    ToolsStep .ob-tool .ob-use { width: 22; margin-left: 1; }
    ToolsStep .ob-tool SelectCurrent { margin-top: 0; }
    ToolsStep .ob-tool Chip { margin: 0; }
    ToolsStep .ob-tool .ob-tool-note { width: 1fr; color: $text-muted; padding-left: 1; }
    ToolsStep .ob-head { height: 1; color: $text-muted; text-style: bold; }
    ToolsStep #ob-tools-missing { color: $text-muted; height: auto; }
    """

    def __init__(self, machine: settings.MachineSettings, detected: DETECTED | None = None, step: str = "",
                 can_back: bool = False, show_warder: bool = False,
                 chosen: dict[str, settings.ToolChoice] | None = None, warder: bool = True,
                 ratings: dict | None = None) -> None:
        super().__init__()
        self.machine = machine
        self.detected = detected
        self.step = step
        self.can_back = can_back
        self.show_warder = show_warder
        self.chosen = chosen
        self.warder = warder
        self.ratings = dict(ratings or {})
        self._warned = False

    @property
    def statuses(self) -> list[tools.ToolStatus] | None:
        return None if self.detected is None else self.detected[0]

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(_title("🧭 Your AI tools", self.step), classes="build-title")
            yield Static("✓ the ones your orks run on · 👍 / 👎 what you think of each, and what for — the town "
                         "picks its models by it.", classes="build-hint")
            yield Static("Looking for your AI tools…", id="ob-tools-loading")
            yield Static("tool".ljust(24) + "paid by".ljust(17) + "👍 👎  what for", classes="ob-head")
            yield Vertical(id="ob-tools-list")
            yield Static("", id="ob-tools-missing", markup=False)
            yield Checkbox("Install the 🛡 Warder in this project (recommended) — edits .claude/settings.json "
                           "(and .codex/hooks.json with Codex)",
                           value=self.warder, id="ob-warder")
            yield Static(AGY_UNGUARDED, id="ob-warder-agy", classes="build-hint", markup=False)
            yield Static("", id="ob-tools-note", classes="ob-note", markup=False)
            yield _nav(self.can_back)

    def on_mount(self) -> None:
        self.query_one("#ob-warder", Checkbox).display = self.show_warder
        self.query_one("#ob-warder-agy", Static).display = self.show_warder
        self.query_one(".ob-head").display = False
        if self.detected is None:
            self.detect()
        else:
            self.show(self.detected)

    @work(thread=True, exclusive=True, group="onboarding-tools")
    def detect(self) -> None:
        found = detect_all()
        self.app.call_from_thread(self.show, found)

    def _rating_cells(self, tid: str) -> list[Widget]:
        r = self.ratings.get(tid) or {}
        good = Select(USE_OPTIONS, value=r.get("good") or Select.NULL, prompt="good for…", compact=True,
                      id=f"ob-good-{tid}", classes="ob-use")
        weak = Select(USE_OPTIONS, value=r.get("weak") or Select.NULL, prompt="weak at…", compact=True,
                      id=f"ob-weak-{tid}", classes="ob-use")
        good.styles.visibility = "visible" if r.get("like") else "hidden"      # hidden keeps the column
        weak.styles.visibility = "visible" if r.get("dislike") else "hidden"
        return [Chip("👍", "like", bool(r.get("like")), id=f"ob-like-{tid}"),
                Chip("👎", "dislike", bool(r.get("dislike")), id=f"ob-dislike-{tid}"), good, weak]

    def show(self, detected: DETECTED) -> None:
        self.detected = detected
        statuses, others = detected
        self.query_one("#ob-tools-loading", Static).display = False
        box = self.query_one("#ob-tools-list", Vertical)
        box.remove_children()
        rows, missing = [], []
        for st in statuses:
            if not (st.tool.available and st.found):
                if st.tool.available:
                    missing.append(f"{st.tool.title} ({st.tool.install})")
                continue
            if self.chosen is not None and st.id in self.chosen:
                enabled, billing = self.chosen[st.id].enabled, self.chosen[st.id].billing
            else:
                known = self.machine.tools.get(st.id, settings.ToolChoice())
                enabled = known.enabled if self.machine.onboarded else True
                billing = known.billing if self.machine.onboarded and known.enabled else st.billing
            note = "not logged in" if st.logged_in is False else ""
            rows.append(Horizontal(
                Checkbox(st.tool.title, value=enabled, id=f"ob-tool-{st.id}", compact=True),
                Select([("subscription", "subscription"), ("API key", "api")], value=billing, allow_blank=False,
                       compact=True, id=f"ob-billing-{st.id}", classes="ob-billing"),
                *self._rating_cells(st.id), Static(note, classes="ob-tool-note", markup=False),
                classes="ob-tool"))
        led = {st.id for st in statuses if st.tool.available and st.found}
        for o in others:
            if o.id in led:                       # Cursor's CLI is led above: its editor is not asked about twice
                continue
            rows.append(Horizontal(Static(o.title, classes="ob-tool-name", markup=False),
                                   Static("", classes="ob-billing-gap"), *self._rating_cells(o.id),
                                   classes="ob-tool"))
        box.mount(*rows)
        self.query_one(".ob-head").display = bool(rows)
        text = ""
        if not rows:
            text = (f"No AI tools found here. Agents and the Builder need one of "
                    f"{', '.join(t.title for t in tools.TOOLS)} — or try `orkcraft --demo` first.")
        elif missing:
            text = "Not found: " + " · ".join(missing)
        self.query_one("#ob-tools-missing", Static).update(text)
        self.query_one("#ob-warder-agy", Static).update(agy_warder_line(self.machine.agy_warder_checked, statuses))

    @on(Chip.Toggled)
    def _rated(self, event: Chip.Toggled) -> None:
        event.stop()
        tid = (event.chip.id or "").split("-", 2)[-1]
        which = "good" if event.chip.value == "like" else "weak"
        for sel in self.query(f"#ob-{which}-{tid}").results(Select):
            sel.styles.visibility = "visible" if event.chip.on else "hidden"

    def choices(self) -> dict[str, settings.ToolChoice]:
        out = {}
        for st in self.statuses or []:
            if not (st.tool.available and st.found):
                out[st.id] = settings.ToolChoice(enabled=False, billing=st.billing)
                continue
            on_ = self.query_one(f"#ob-tool-{st.id}", Checkbox).value
            billing = self.query_one(f"#ob-billing-{st.id}", Select).value
            out[st.id] = settings.ToolChoice(enabled=bool(on_), billing=str(billing) if billing in settings.BILLINGS
                                             else "subscription")
        return out

    def rated(self) -> dict:
        """{tool: {title, like, good, dislike, weak}} for every tool given a 👍 or a 👎."""
        if self.detected is None:
            return {}
        titles = {st.id: st.tool.title for st in self.detected[0]} | {o.id: o.title for o in self.detected[1]}
        out = {}
        for tid, title in titles.items():
            like = [c.on for c in self.query(f"#ob-like-{tid}").results(Chip)]
            dislike = [c.on for c in self.query(f"#ob-dislike-{tid}").results(Chip)]
            if not (any(like) or any(dislike)):
                continue
            r: dict = {"title": title, "like": any(like), "dislike": any(dislike)}
            for key, flag in (("good", r["like"]), ("weak", r["dislike"])):
                value = next((s.value for s in self.query(f"#ob-{key}-{tid}").results(Select)), Select.NULL)
                if flag and isinstance(value, str):
                    r[key] = value
            out[tid] = r
        return out

    def action_next(self) -> None:
        if self.detected is None:
            return
        picked = self.choices()
        if not any(c.enabled for c in picked.values()) and not self._warned:
            self._warned = True
            self.query_one("#ob-tools-note", Static).update(
                "⚠ No tool to run on: agents and the Builder will be unavailable. Next again to go on — or try "
                "`orkcraft --demo` first.")
            return
        self.dismiss({"action": "next", "tools": picked, "ratings": self.rated(), "detected": self.detected,
                      "warder": self.show_warder and self.query_one("#ob-warder", Checkbox).value})

    def action_skip(self) -> None:
        found = {st.id: settings.ToolChoice(enabled=st.found and st.tool.available, billing=st.billing)
                 for st in self.statuses or []}
        self.dismiss({"action": "skip", "tools": found})

    def action_back(self) -> None:
        if self.can_back:
            self.dismiss("back")
        else:
            self.action_skip()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        {"ob-next": self.action_next, "ob-back": self.action_back}.get(event.button.id or "", self.action_skip)()


# -- the day -----------------------------------------------------------------------------------------------

def day_legend(bar: DayBar) -> Text:
    t = Text()
    t.append("█", style=DAY_COLOR)
    t.append(" day   ")
    t.append("█", style=QUIET_COLOR)
    t.append(f" 🌙 quiet {bar.quiet.label()}" if bar.quiet else " 🌙 quiet off")
    return t


class DayStep(ModalScreen[dict | str | None]):
    """🕰 The day: the quiet hours on the day bar. Dismisses {"quiet"}, "back", "skip" or None.
    `standalone` (F10 → 🕰 Your day): Save and Cancel instead of the onboarding's buttons."""

    BINDINGS = [Binding("escape", "back", "Back")]
    DEFAULT_CSS = _css("DayStep", 80) + """
    DayStep .ob-section { text-style: bold; margin-top: 1; }
    DayStep #ob-day-row { height: auto; align-horizontal: center; }
    DayStep #ob-day-legend { height: auto; }
    DayStep #ob-quiet { margin-top: 0; }
    """

    def __init__(self, machine: settings.MachineSettings | None = None, standalone: bool = False,
                 step: str = "") -> None:
        super().__init__()
        self.step = step
        self.machine = machine or settings.MachineSettings()
        self.standalone = standalone

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("🕰 Your day — the quiet hours" if self.standalone
                        else _title("🕰 Your day", self.step), classes="build-title")
            yield Label("Your day", classes="ob-section")
            with Horizontal(id="ob-day-row"):
                yield DayBar(self.machine.quiet, id="ob-day")
            yield Static("", id="ob-day-legend", markup=False)
            yield Checkbox("🌙 Do not disturb — no fires, only ❓ (later: no sound, no push)",
                           value=self.machine.quiet is not None, id="ob-quiet")
            yield Static("Drag across the bar, or Tab to an edge and move it with ←/→ (shift: the whole span).",
                         classes="build-hint")
            if self.standalone:
                yield _buttons(("Cancel", "ob-cancel", "default"), ("Save", "ob-save", "success"))
            else:
                yield _buttons(("← Back", "ob-back", "default"), ("Skip", "ob-skip", "default"),
                               ("Next →", "ob-next", "primary"))

    def on_mount(self) -> None:
        self._legend()

    @property
    def bar(self) -> DayBar:
        return self.query_one("#ob-day", DayBar)

    def _legend(self) -> None:
        self.query_one("#ob-day-legend", Static).update(day_legend(self.bar))

    @on(DayBar.Changed)
    def _day(self, event: DayBar.Changed) -> None:
        event.stop()
        box = self.query_one("#ob-quiet", Checkbox)
        if box.value != (self.bar.quiet is not None):
            with box.prevent(Checkbox.Changed):
                box.value = self.bar.quiet is not None
        self._legend()

    @on(Checkbox.Changed, "#ob-quiet")
    def _quiet(self, event: Checkbox.Changed) -> None:
        event.stop()
        if event.value and self.bar.quiet is None:
            self.bar.set_quiet(schedule.DEFAULT_QUIET)
        elif not event.value and self.bar.quiet is not None:
            self.bar.set_quiet(None)

    def result(self) -> dict:
        return {"quiet": self.bar.quiet}

    def action_back(self) -> None:
        self.dismiss(None if self.standalone else "back")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        bid = event.button.id
        if bid in ("ob-next", "ob-save"):
            self.dismiss(self.result())
        elif bid == "ob-skip":
            self.dismiss("skip")
        elif bid == "ob-back":
            self.dismiss("back")
        else:
            self.dismiss(None)


# -- raising the town -------------------------------------------------------------------------
