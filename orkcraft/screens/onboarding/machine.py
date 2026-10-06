"""🧭 Onboarding, the machine: your AI tools, the look and the day."""
from __future__ import annotations

from rich.text import Text
from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import Button, Checkbox, Label, RadioButton, Select, Static

from orkcraft import schedule, settings, tools
from orkcraft.widgets.day_bar import DAY_COLOR, OFFICE_COLOR, QUIET_COLOR, DayBar
from orkcraft.realm import interview
from orkcraft.tui import silhouettes
from orkcraft.screens.onboarding.common import NARROW, _buttons, _css, _nav, _title
from orkcraft.screens.onboarding.person import Chip


SAMPLE = silhouettes.FORGE
SAMPLE_TITLE = "⚒️ Forge"
SAMPLE_LINES = ["tests: 42 ok", "branch: main", "merged: 2 today", "queue: 1 waiting"]


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
            yield Static("", id="ob-tools-note", classes="ob-note", markup=False)
            yield _nav(self.can_back)

    def on_mount(self) -> None:
        self.query_one("#ob-warder", Checkbox).display = self.show_warder
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
        for o in others:
            rows.append(Horizontal(Static(o.title, classes="ob-tool-name", markup=False),
                                   Static("", classes="ob-billing-gap"), *self._rating_cells(o.id),
                                   classes="ob-tool"))
        box.mount(*rows)
        self.query_one(".ob-head").display = bool(rows)
        text = ""
        if not rows:
            text = "No AI tools found here. Agents and the Builder need Claude Code or Antigravity — or try " \
                   "`orkcraft --demo` first."
        elif missing:
            text = "Not found: " + " · ".join(missing)
        self.query_one("#ob-tools-missing", Static).update(text)

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


# -- the look and the day -----------------------------------------------------------------------------------

def card_art(plain: bool) -> Text:
    """The sample building, in its ASCII or as just a frame, with the same live rows."""
    sil = silhouettes.styled(SAMPLE, plain)
    t = Text()
    t.append(f"{SAMPLE_TITLE}\n", style="bold")
    for row in sil.draw(SAMPLE_LINES):
        for text, role in row:
            t.append(text, style="dim" if role == "frame" and not plain else "" if role == "frame" else "bold")
        t.append("\n")
    return t


class ModeCard(Static):
    """A clickable picture of one look: the camp (ASCII) or the office (frames)."""

    def __init__(self, mode: str) -> None:
        super().__init__(card_art(mode == "office"), id=f"ob-card-{mode}", classes="ob-card")
        self.mode = mode

    def on_click(self) -> None:
        self.screen.pick(self.mode)  # type: ignore[attr-defined]


def day_legend(bar: DayBar, days: tuple[int, ...]) -> Text:
    t = Text()
    t.append("█", style=DAY_COLOR)
    t.append(" day   ")
    t.append("█", style=QUIET_COLOR)
    t.append(f" 🌙 quiet {bar.quiet.label()}   " if bar.quiet else " 🌙 quiet off   ")
    if bar.show_office:
        t.append("█", style=OFFICE_COLOR)
        names = "–".join((schedule.DAYS[days[0]], schedule.DAYS[days[-1]])) if days else "no days"
        t.append(f" 👔 office {bar.office.label()} {names}")
    return t


class ModeStep(ModalScreen[dict | str | None]):
    """🧌 Camp, 👔 Office or 🧌/👔 Shift, and the day: quiet hours and (for Shift) office hours.
    Dismisses {"mode", "quiet", "office", "office_days"}, "back", "skip" or None. `standalone`
    (F10 → 🕰 Your day): Save and Cancel instead of the onboarding's buttons."""

    BINDINGS = [Binding("escape", "back", "Back")]
    DEFAULT_CSS = _css("ModeStep", 80) + """
    ModeStep #ob-cards, ModeStep #ob-modes { height: auto; }
    ModeStep .ob-card { width: 1fr; height: auto; border: round $panel-lighten-2; padding: 0 1; margin: 0 1; }
    ModeStep .ob-card.-picked { border: round $accent; }
    ModeStep .ob-gap { width: 20; height: 1; }
    ModeStep .ob-radio-cell { width: 1fr; height: 1; align-horizontal: center; margin: 0 1; }
    ModeStep .ob-radio-cell.-middle { width: 20; margin: 0; }
    ModeStep RadioButton { width: auto; height: 1; border: none; padding: 0; background: transparent; }
    ModeStep RadioButton:focus { text-style: bold; border: none; }
    ModeStep .ob-section { text-style: bold; margin-top: 1; }
    ModeStep #ob-day-row { height: auto; align-horizontal: center; }
    ModeStep #ob-day-legend { height: auto; }
    ModeStep #ob-quiet { margin-top: 0; }
    """

    def __init__(self, machine: settings.MachineSettings | None = None, standalone: bool = False,
                 step: str = "") -> None:
        super().__init__()
        self.step = step
        self.machine = machine or settings.MachineSettings()
        self.mode = self.machine.mode
        self.standalone = standalone

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("🕰 Your day — the look of the town and its hours" if self.standalone
                        else _title("🧭 How should the town look?", self.step), classes="build-title")
            # Camp under the camp's picture, Office under the office's, Shift — both — between them:
            # the radio row has the cards' columns (1fr · the gap · 1fr).
            with Horizontal(id="ob-cards"):
                yield ModeCard("camp")
                yield Static("", classes="ob-gap")
                yield ModeCard("office")
            with Horizontal(id="ob-modes"):
                for mode in ("camp", "shift", "office"):
                    with Horizontal(classes="ob-radio-cell" + (" -middle" if mode == "shift" else "")):
                        yield RadioButton(settings.MODE_TITLES[mode], value=self.mode == mode, id=f"ob-mode-{mode}")
            yield Static("", id="ob-mode-hint", classes="build-hint")
            yield Label("Your day", classes="ob-section")
            with Horizontal(id="ob-day-row"):
                yield DayBar(self.machine.quiet, self.machine.office, show_office=self.mode == "shift", id="ob-day")
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
        self.pick(self.mode)
        self._fit()

    def on_resize(self) -> None:
        self._fit()

    def _fit(self) -> None:
        narrow = self.app.size.width < NARROW
        self.query_one("#ob-cards").styles.layout = "vertical" if narrow else "horizontal"
        for gap in self.query(".ob-gap"):
            gap.display = not narrow

    @property
    def bar(self) -> DayBar:
        return self.query_one("#ob-day", DayBar)

    def pick(self, mode: str) -> None:
        self.mode = mode
        for card in self.query(ModeCard):
            card.set_class(card.mode == mode or mode == "shift", "-picked")
        for button in self.query(RadioButton):          # one of three, kept by hand: they sit in separate cells
            on_ = button.id == f"ob-mode-{mode}"
            if button.value != on_:
                with button.prevent(RadioButton.Changed):
                    button.value = on_
        self.query_one("#ob-mode-hint", Static).update({
            "camp": "🧌 Buildings wear their ASCII all day.",
            "office": "👔 Buildings are just frames — nothing to explain over a shoulder.",
            "shift": "🧌/👔 Office in office hours on weekdays (grey on the bar), the camp the rest of the time.",
        }[mode] + "  You can change it at any time: F10.")
        self.bar.set_show_office(mode == "shift")
        self._legend()

    def _legend(self) -> None:
        self.query_one("#ob-day-legend", Static).update(day_legend(self.bar, self.machine.office_days))

    @on(RadioButton.Changed)
    def _radio(self, event: RadioButton.Changed) -> None:
        event.stop()
        mode = (event.radio_button.id or "").removeprefix("ob-mode-")
        if mode in settings.MODES:
            self.pick(mode if event.value else self.mode)       # a second click keeps it on

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
        return {"mode": self.mode, "quiet": self.bar.quiet, "office": self.bar.office,
                "office_days": self.machine.office_days}

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
