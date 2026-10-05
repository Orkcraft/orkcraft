"""🧭 Onboarding for an indie maker who already works with AI: your AI tools → your day → the town.

    Onboarding(app, machine_steps=True, town_step=True, on_town=app.raise_town).start()

Design: docs/design/onboarding.md. The AI tools are looked for in the background from the start;
the day is the look of the town, the office hours and do not disturb; the town is one of the
indie maker's ready towns — ★ where the project shows it fits (code, notes for agents, GitHub) —
a phrase for the Town Builder when none fits, or an empty town. The orks' autonomy keeps its
default; F10 → 🏛 Ork autonomy changes it.

Nothing is written before the last step; Skip anywhere = an empty town, defaults for the rest,
no Warder. The town is raised over the map itself, with a progress bar along the bottom.
"""
from __future__ import annotations

import threading
import time
from dataclasses import replace
from typing import Callable

from rich.text import Text
from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import Button, Checkbox, Input, Label, OptionList, ProgressBar, RadioButton, Select, Static
from textual.widgets.option_list import Option

from orkcraft import autonomy, schedule, settings, tools
from orkcraft.widgets.day_bar import DAY_COLOR, OFFICE_COLOR, QUIET_COLOR, DayBar
from orkcraft.realm import intents, interview, silhouettes
from orkcraft.screens.build_flow import MODAL_CSS

CUSTOM = "custom"
EMPTY = "empty"
STEP_PAUSE_S = 0.35        # each raising step stays on the bar long enough to be read
NARROW = 90                # below this many columns the mode cards stack
SHORT, SHORT_NARROW = 52, 80   # below this many rows the mode cards hide (side by side · stacked): the radios stay
SAMPLE = silhouettes.FORGE
SAMPLE_TITLE = "⚒️ Forge"
SAMPLE_LINES = ["tests: 42 ok", "branch: main", "merged: 2 today", "queue: 1 waiting"]


def _css(cls: str, width: int) -> str:
    return MODAL_CSS.format(cls=cls, border_color="$accent", title_color="$accent") + f"""
    {cls} > Vertical {{ width: {width}; }}
    {cls} .ob-buttons {{ height: auto; margin-top: 1; align-horizontal: right; }}
    {cls} .ob-buttons Button {{ margin-left: 1; }}
    {cls} .ob-note {{ color: $warning; height: auto; }}
    {cls} .ob-mascot {{ width: 16; height: auto; padding: 1 0 0 2; color: $accent; }}
    """


def _title(text: str, step: str) -> str:
    return f"{text}  ·  {step}" if step else text


def _buttons(*specs: tuple[str, str, str]) -> Horizontal:
    return Horizontal(*(Button(label, id=bid, variant=variant) for label, bid, variant in specs),  # type: ignore[arg-type]
                      classes="ob-buttons")


def _nav(can_back: bool, last: bool = False) -> Horizontal:
    return _buttons(*([("← Back", "ob-back", "default")] if can_back else []), ("Skip", "ob-skip", "default"),
                    ("Build", "ob-next", "success") if last else ("Next →", "ob-next", "primary"))


def _highlight(lst: OptionList, option_id: str) -> None:
    for i in range(lst.option_count):
        if lst.get_option_at_index(i).id == option_id:
            lst.highlighted = i
            return


def _highlighted_id(lst: OptionList) -> str:
    return "" if lst.highlighted is None else lst.get_option_at_index(lst.highlighted).id or ""


# -- the town: the indie maker's ready towns ---------------------------------------------------------

def intent_blurb(it: intents.Intent, why: str = "") -> Text:
    t = Text("🏗 " + " · ".join(f"{b['icon']} {b['title']}" for b in it.plan["buildings"]), style="dim")
    if why:
        t.append(f"\n{why}", style="bold")
    return t


def intent_label(it: intents.Intent, star: bool) -> Text:
    """"📨 Inbox Keep ★  mail and GitHub sorted into tasks" — the ork name, then plain words."""
    t = Text(it.label, style="bold")
    if star:
        t.append(" ★", style="bold")
    t.append(f"  {it.blurb}", style="dim")
    return t


class IntentStep(ModalScreen[dict | str | None]):
    """What the first town is for: an indie maker's ready town (★ when the project shows it fits),
    none fits — a phrase for the Town Builder — or, at the bottom, an empty town. `fits`:
    intents.project_fit, {intent id: why}. Dismisses {"preset": id | "empty" | "custom", "role",
    "warder", "wish"}, "back", "skip" or None."""

    BINDINGS = [Binding("escape", "back", "Back")]
    DEFAULT_CSS = _css("IntentStep", 100) + """
    IntentStep #ob-for { height: auto; margin-bottom: 1; }
    IntentStep #ob-town { height: auto; }
    IntentStep #ob-town-left { width: 1fr; height: auto; }
    IntentStep #ob-presets { height: auto; max-height: 8; }
    IntentStep #ob-blurb { height: auto; padding: 0 1; }
    IntentStep #ob-wish { margin-top: 1; }
    IntentStep .ob-buttons #ob-empty { margin-left: 0; margin-right: 1; }
    IntentStep .ob-spacer { width: 1fr; }
    """

    def __init__(self, fits: dict[str, str] | None = None, step: str = "", can_back: bool = True,
                 last: bool = False, show_warder: bool = False, choice: dict | None = None,
                 builder: bool = True) -> None:
        super().__init__()
        self.fits = dict(fits or {})
        self.step = step
        self.can_back = can_back
        self.last = last
        self.show_warder = show_warder
        self.builder = builder            # the Town Builder plans with Claude Code: is it chosen?
        self.choice = dict(choice or {})

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(_title("🧭 What should your first town do?", self.step), classes="build-title")
            yield Static("", id="ob-for", markup=False)
            with Horizontal(id="ob-town"):
                with Vertical(id="ob-town-left"):
                    yield OptionList(id="ob-presets")
                    yield Static("", id="ob-blurb", markup=False)
                    yield Input(self.choice.get("wish", ""), id="ob-wish",
                                placeholder="what should the town do? e.g. triage GitHub issues, draft release notes")
                yield Static("\n".join(intents.mascot(intents.FOUNDER)), id="ob-mascot", classes="ob-mascot",
                             markup=False)
            yield Checkbox("Install the 🛡 Warder (recommended) — edits .claude/settings.json "
                           "(and .codex/hooks.json with Codex)",
                           value=self.choice.get("warder", True), id="ob-warder")
            yield Static("", id="ob-town-note", classes="ob-note", markup=False)
            yield Horizontal(
                Button("🏰 Empty town", id="ob-empty"), Static("", classes="ob-spacer"),
                *([Button("← Back", id="ob-back")] if self.can_back else []), Button("Skip", id="ob-skip"),
                Button("Build", id="ob-next", variant="success") if self.last
                else Button("Next →", id="ob-next", variant="primary"),
                classes="ob-buttons")

    def on_mount(self) -> None:
        self.call_after_refresh(self._setup)     # pushed as the app starts, its children may not be in yet

    def _setup(self) -> None:
        self.query_one("#ob-warder", Checkbox).display = self.show_warder
        line = Text("For an indie maker who already works with AI", style="bold")
        if self.fits:
            line.append("  ·  ★ fits what is in this project", style="dim")
        self.query_one("#ob-for", Static).update(line)
        lst = self.query_one("#ob-presets", OptionList)
        for it in sorted(intents.for_role(intents.FOUNDER), key=lambda it: it.id not in self.fits):
            lst.add_option(Option(intent_label(it, it.id in self.fits), id=it.id))
        if self.builder:
            lst.add_option(Option("❓ None fits — say what it should do, the Builder draws it", id=CUSTOM))
        else:
            lst.add_option(Option("❓ None fits — needs Claude Code for the Builder", id=CUSTOM, disabled=True))
        lst.highlighted = 0
        if self.choice.get("preset"):
            _highlight(lst, self.choice["preset"])
        self.show_choice()

    @property
    def choice_id(self) -> str:
        return _highlighted_id(self.query_one("#ob-presets", OptionList)) or CUSTOM

    @property
    def wish(self) -> str:
        return self.query_one("#ob-wish", Input).value.strip()

    def show_choice(self) -> None:
        it = intents.intent(self.choice_id)
        note = self.query_one("#ob-town-note", Static)
        note.update("" if self.builder else "The Builder plans a town with Claude Code: turn it on on the tools "
                    "step (Back) to describe your own — a ready town or an empty one needs no model.")
        blurb = intent_blurb(it, self.fits.get(it.id, "")) if it else Text(
            "In a phrase: what the town should do. The Builder adapts an indie maker's town to it and to what "
            "is in this project; you approve the plan before anything is raised.", style="dim")
        self.query_one("#ob-blurb", Static).update(blurb)
        self.query_one("#ob-wish", Input).display = it is None

    @on(OptionList.OptionHighlighted, "#ob-presets")
    def _highlighted(self, event: OptionList.OptionHighlighted) -> None:
        event.stop()
        self.show_choice()

    @on(OptionList.OptionSelected, "#ob-presets")
    def _selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        if event.option_id == CUSTOM:
            self.query_one("#ob-wish", Input).focus()
        else:
            self.action_next()

    @on(Input.Submitted, "#ob-wish")
    def _said(self, event: Input.Submitted) -> None:
        event.stop()
        self.action_next()

    def _result(self, preset: str) -> dict:
        return {"preset": preset, "role": intents.FOUNDER, "wish": self.wish,
                "warder": self.show_warder and self.query_one("#ob-warder", Checkbox).value}

    def action_next(self) -> None:
        if self.choice_id == CUSTOM and not self.wish:
            self.query_one("#ob-town-note", Static).update("⚠ Say in a phrase what the town should do.")
            self.query_one("#ob-wish", Input).focus()
            return
        self.dismiss(self._result(self.choice_id))

    def action_back(self) -> None:
        self.dismiss("back" if self.can_back else "skip")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        bid = event.button.id
        if bid == "ob-empty":
            self.dismiss(self._result(EMPTY))
        elif bid == "ob-next":
            self.action_next()
        elif bid == "ob-back":
            self.action_back()
        else:
            self.dismiss("skip")


# -- your AI tools: the ones installed and led ----------------------------------------------------------

DETECTED = tuple[list[tools.ToolStatus], list[tools.Other]]


def detect_all() -> DETECTED:
    """Blocking: the CLIs orkcraft leads (a `--version` each) and the other AI tools installed."""
    return tools.detect(), tools.detect_others()


class ToolsStep(ModalScreen[dict | str | None]):
    """The AI tools installed here, one row each and nothing else: the CLIs orkcraft leads get a
    ✓ and how they are paid for; the others are named, so the operator sees they were found. The
    ones not found are named once, dimly, under the rows. Dismisses {"action": "next", "tools":
    {...}, "detected": ..., "warder": bool}, {"action": "skip", "tools": {...}}, "back" or None.
    `chosen`: what was picked before."""

    BINDINGS = [Binding("escape", "back", "Back")]
    DEFAULT_CSS = _css("ToolsStep", 100) + """
    ToolsStep #ob-tools-list { height: auto; margin-bottom: 1; }
    ToolsStep .ob-tool { height: 1; margin-top: 0; }
    ToolsStep .ob-tool Checkbox { width: 24; height: 1; border: none; padding: 0; background: transparent; }
    ToolsStep .ob-tool .ob-tool-name { width: 24; padding-left: 4; }
    ToolsStep .ob-tool .ob-billing { width: 16; height: 1; margin-right: 1; }
    ToolsStep .ob-tool .ob-billing-gap { width: 17; }
    ToolsStep .ob-tool Select { height: 1; }
    ToolsStep .ob-tool SelectCurrent { margin-top: 0; }
    ToolsStep .ob-tool .ob-tool-note { width: 1fr; color: $text-muted; padding-left: 1; }
    ToolsStep .ob-head { height: 1; color: $text-muted; text-style: bold; }
    ToolsStep #ob-tools-missing { color: $text-muted; height: auto; }
    """

    def __init__(self, machine: settings.MachineSettings, detected: DETECTED | None = None, step: str = "",
                 can_back: bool = False, show_warder: bool = False,
                 chosen: dict[str, settings.ToolChoice] | None = None, warder: bool = True) -> None:
        super().__init__()
        self.machine = machine
        self.detected = detected
        self.step = step
        self.can_back = can_back
        self.show_warder = show_warder
        self.chosen = chosen
        self.warder = warder
        self._warned = False

    @property
    def statuses(self) -> list[tools.ToolStatus] | None:
        return None if self.detected is None else self.detected[0]

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(_title("🧭 Your AI tools", self.step), classes="build-title")
            yield Static("✓ the ones your orks run on, and how you pay for each.", classes="build-hint")
            yield Static("Looking for your AI tools…", id="ob-tools-loading")
            yield Static("tool".ljust(24) + "paid by", classes="ob-head")
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
                Static(note, classes="ob-tool-note", markup=False),
                classes="ob-tool"))
        for o in others:
            rows.append(Horizontal(Static(o.title, classes="ob-tool-name", markup=False),
                                   Static("", classes="ob-billing-gap"),
                                   Static("found — orkcraft does not run it", classes="ob-tool-note"),
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
        self.dismiss({"action": "next", "tools": picked, "detected": self.detected,
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
    """🧌 Camp, 👔 Office or 🧌/👔 Shift, and the day: do not disturb (the quiet hours) and, for
    Shift, the office hours. Dismisses {"mode", "quiet", "office", "office_days"}, "back", "skip"
    or None. `standalone` (F10 → 🕰 Your day): Save and Cancel instead of the onboarding's buttons;
    `last`: the onboarding ends here (F10 → 🧭 Onboarding), Done instead of Next."""

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
                 step: str = "", last: bool = False) -> None:
        super().__init__()
        self.step = step
        self.last = last
        self.machine = machine or settings.MachineSettings()
        self.mode = self.machine.mode
        self.standalone = standalone

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("🕰 Your day — the look of the town and its hours" if self.standalone
                        else _title("🧭 Your day — office hours and do not disturb", self.step), classes="build-title")
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
                               ("Done", "ob-next", "success") if self.last else ("Next →", "ob-next", "primary"))

    def on_mount(self) -> None:
        self.pick(self.mode)
        self._fit()

    def on_resize(self) -> None:
        self._fit()

    def _fit(self) -> None:
        narrow = self.app.size.width < NARROW
        cards = self.query_one("#ob-cards")
        cards.styles.layout = "vertical" if narrow else "horizontal"
        cards.display = self.app.size.height >= (SHORT_NARROW if narrow else SHORT)   # the buttons come first
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

class RaiseBar(Horizontal):
    """The progress of raising the town, along the bottom of the map."""

    DEFAULT_CSS = """
    RaiseBar {
        dock: bottom;
        height: 3;
        width: 100%;
        background: $panel;
        border-top: solid $accent;
        padding: 0 2;
        layer: overlay;
    }
    RaiseBar #raise-label { width: 1fr; padding-top: 0; }
    RaiseBar ProgressBar { width: 40; }
    """

    def __init__(self, total: int | None) -> None:     # None: it runs until told (the Town Builder thinking)
        super().__init__(id="raise-bar")
        self.total = total
        self.label = "🏗 Raising the town…"
        self.done = 0

    def compose(self) -> ComposeResult:
        yield Static(self.label, id="raise-label", markup=False)
        yield ProgressBar(total=self.total, show_eta=False, id="raise-progress")

    def on_mount(self) -> None:
        self._show()

    def say(self, label: str) -> None:
        self.label = label
        self._show()

    def step(self, label: str, done: int) -> None:
        self.label, self.done = f"🏗 {label}", done
        self._show()

    def _show(self) -> None:
        """Safe before the bar's children are in (mounted from the same handler)."""
        for w in self.query("#raise-label").results(Static):
            w.update(self.label)
        for bar in self.query("#raise-progress").results(ProgressBar):
            if self.total is not None:
                bar.update(progress=self.done)


def raising_steps(choice: dict) -> list[str]:
    """What raising the town does, in order — each a real piece of work. An intent's buildings and
    the Town Builder's plan are raised after it, on their own bar."""
    steps = ["Opening the camp's records"]
    if choice.get("warder"):
        steps.append("Installing the 🛡 Warder")
    if choice.get("preset") == CUSTOM:
        steps.append("Leaving your order in the Town Hall")
    return steps


# -- the flow ---------------------------------------------------------------------------------------

TOOLS, DAY, INTENT = "tools", "day", "intent"


class Onboarding:
    """Pushes the steps one after another, Back and Skip included, and applies what was chosen.

      a new machine        your AI tools · your day · the town
      a known one          the town (a project with none yet)
      F10 → 🧭 Onboarding  your AI tools · your day

    The operator is an indie maker (intents.FOUNDER); the town's ★ come from the project itself.
    The AI tools are looked for in the background from the start, so their step opens ready.
    `on_town(choice)` is called at the end with {"preset", "role", "warder", "prompt", "answers"}
    (an empty town on skip); the app raises it."""

    def __init__(self, app, machine_steps: bool, town_step: bool, on_town: Callable[[dict], None],
                 statuses: list[tools.ToolStatus] | None = None) -> None:
        self.app = app
        self.machine_steps = machine_steps
        self.town_step = town_step
        self.on_town = on_town
        self.root = getattr(app, "repo_root", None)
        self.detected: DETECTED | None = (statuses, []) if statuses is not None else None
        self.machine = settings.load()
        self.profile = {**self.machine.profile, "role": intents.FOUNDER}
        self.choice: dict = {}
        self.picked: dict[str, settings.ToolChoice] | None = None
        self.autonomy = self.machine.autonomy
        self.warder = True
        self.day: dict | None = None
        self.steps = ([TOOLS, DAY] if machine_steps else []) + ([INTENT] if town_step else [])
        self.i = 0
        if machine_steps and self.detected is None:
            threading.Thread(target=self._detect, daemon=True).start()

    def _detect(self) -> None:
        """In the background from the first step: the tools step opens with them found."""
        detected = detect_all()
        if self.detected is None:
            self.detected = detected

    def start(self) -> None:
        if self.steps:
            self._show()

    @property
    def step(self) -> str:
        return f"step {self.i + 1} of {len(self.steps)}" if len(self.steps) > 1 else ""

    @property
    def claude_on(self) -> bool:
        tools_ = {**self.machine.tools, **(self.picked or {})}
        return tools_.get("claude", settings.ToolChoice()).enabled

    def _show(self) -> None:
        name, back, last = self.steps[self.i], self.i > 0, self.i == len(self.steps) - 1
        done = lambda result: self._done(name, result)  # noqa: E731
        if name == TOOLS:
            screen = ToolsStep(self.machine, self.detected, self.step, can_back=back, show_warder=self.town_step,
                               chosen=self.picked, warder=self.warder)
        elif name == DAY:
            day = self.day or {}
            look = replace(self.machine, mode=day.get("mode", self.machine.mode),
                           quiet=day.get("quiet", self.machine.quiet), office=day.get("office", self.machine.office))
            screen = ModeStep(look, step=self.step, last=last)
        else:
            screen = IntentStep(intents.project_fit(self.root), self.step, back, last,
                                show_warder=TOOLS not in self.steps and self.claude_on, choice=self.choice,
                                builder=self.claude_on)
        self.app.push_screen(screen, done)

    def _done(self, name: str, result: dict | str | None) -> None:
        if result is None:
            return
        if result == "back":
            self.i = max(0, self.i - 1)
            self._show()
            return
        if result == "skip" or (isinstance(result, dict) and result.get("action") == "skip"):
            if isinstance(result, dict):
                self.picked = result.get("tools") or {}
            self._skip()
            return
        assert isinstance(result, dict)
        if name == TOOLS:
            self.picked = result.get("tools") or {}
            self.detected = result.get("detected") or self.detected
            self.warder = bool(result.get("warder"))
        elif name == DAY:
            self.day = {"mode": result.get("mode", self.machine.mode), "quiet": result.get("quiet"),
                        "office": result.get("office") or self.machine.office,
                        "office_days": tuple(result.get("office_days") or self.machine.office_days)}
        elif name == INTENT:
            self.choice = result
            self.warder = result.get("warder", self.warder) if TOOLS not in self.steps else self.warder
        self.i += 1
        if self.i < len(self.steps):
            self._show()
        else:
            self._finish()

    def _save_machine(self, day: dict | None) -> None:
        """The profile, and — when the machine's part was asked — tools, autonomy, mode and the day."""
        machine = replace(self.machine, profile=settings.clean_profile(self.profile))
        if not self.machine_steps:
            settings.save(machine)
            desktop = getattr(self.app, "desktop", None)
            if desktop is not None:
                desktop.machine.profile = machine.profile
            self.machine = machine
            return
        tools_ = dict(self.machine.tools)
        tools_.update(self.picked or {})
        machine = replace(machine, tools=tools_, onboarded=True, autonomy=self.autonomy)
        if not self.machine.onboarded and day is None:
            machine.mode = settings.DEFAULT_MODE
        desktop = getattr(self.app, "desktop", None)
        apply_day = getattr(self.app, "apply_day", None)
        if desktop is not None and apply_day is not None:
            desktop.machine = machine
            settings.save(machine)
            apply_day(day or {"mode": machine.mode, "quiet": machine.quiet, "office": machine.office,
                              "office_days": machine.office_days})
            machine = desktop.machine
        else:
            if day:
                machine.mode, machine.quiet, machine.office = day["mode"], day["quiet"], day["office"]
            settings.save(machine)
        self.machine = machine

    def _finish(self) -> None:
        self._save_machine(self.day)
        if self.machine_steps:
            lvl = autonomy.LEVELS[self.machine.autonomy]
            self.app.notify(f"{lvl.icon} {lvl.title}: {lvl.questions}\nF10 → 🏛 Ork autonomy changes it.",
                            title="🏛 Your orks", timeout=10)
        if not self.town_step:
            return
        choice = {"preset": self.choice.get("preset") or EMPTY, "role": intents.FOUNDER,
                  "warder": self.warder and self.claude_on, "prompt": "", "answers": {}}
        if choice["preset"] == CUSTOM:
            choice["prompt"] = interview.summary(self.profile, self.choice.get("wish", ""),
                                                 intents.signs_text(self.root))
        self.on_town(choice)

    def _skip(self) -> None:
        if self.picked is None and self.detected is not None:          # skipped before the tools: the found ones
            self.picked = {st.id: settings.ToolChoice(enabled=st.found and st.tool.available, billing=st.billing)
                           for st in self.detected[0]}
        self._save_machine(None)
        if self.town_step:
            self.on_town({"preset": EMPTY, "role": intents.FOUNDER, "warder": False, "prompt": "", "answers": {}})


def mount_raise_bar(screen: Widget, total: int | None) -> RaiseBar:
    bar = RaiseBar(total)
    screen.mount(bar)
    return bar


def pause() -> None:
    if STEP_PAUSE_S > 0:
        time.sleep(STEP_PAUSE_S)
