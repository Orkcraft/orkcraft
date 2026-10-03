"""🧭 Onboarding: tools → autonomy → mode → town → raising it (design: docs/design/onboarding.md).

    Onboarding(app, machine_steps=True, town_step=True).start()

Steps 1–3 (tools and their billing, the orcs' autonomy, the display mode and the day) are asked once per machine and kept in
`settings.py`; step 3 (the town) once per project. Nothing is written before a step's Next, and
the project's part only on Build. Skip anywhere: an empty town, defaults for the rest, no Warder.
Step 4 raises the town over the map itself, with a progress bar along the bottom.
"""
from __future__ import annotations

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

from orkcraft import schedule, settings, tools
from orkcraft.widgets.day_bar import DAY_COLOR, OFFICE_COLOR, QUIET_COLOR, DayBar
from orkcraft.realm import silhouettes, town_presets
from orkcraft.screens.autonomy import AutonomyStep
from orkcraft.screens.build_flow import MODAL_CSS

CUSTOM = "custom"
EMPTY = "empty"
STEP_PAUSE_S = 0.35        # each raising step stays on the bar long enough to be read
NARROW = 90                # below this many columns the mode cards stack
SAMPLE = silhouettes.FORGE
SAMPLE_TITLE = "⚒️ Forge"
SAMPLE_LINES = ["tests: 42 ok", "branch: main", "merged: 2 today", "queue: 1 waiting"]


def _css(cls: str, width: int) -> str:
    return MODAL_CSS.format(cls=cls, border_color="$accent", title_color="$accent") + f"""
    {cls} > Vertical {{ width: {width}; }}
    {cls} .ob-buttons {{ height: auto; margin-top: 1; align-horizontal: right; }}
    {cls} .ob-buttons Button {{ margin-left: 1; }}
    {cls} .ob-note {{ color: $warning; height: auto; }}
    """


def _buttons(*specs: tuple[str, str, str]) -> Horizontal:
    return Horizontal(*(Button(label, id=bid, variant=variant) for label, bid, variant in specs),  # type: ignore[arg-type]
                      classes="ob-buttons")


# -- step 1: tools ----------------------------------------------------------------------------------

class ToolsStep(ModalScreen[dict | None]):
    """Which CLIs to lead, and how each is paid for. Dismisses {"action": "next", "tools": {...}},
    {"action": "skip", "tools": {...}} (the found ones, as detected) or None."""

    BINDINGS = [Binding("escape", "skip", "Skip")]
    DEFAULT_CSS = _css("ToolsStep", 92) + """
    ToolsStep #ob-tools-list { height: auto; margin-bottom: 1; }
    ToolsStep .ob-tool { height: 3; }
    ToolsStep .ob-tool Checkbox { width: 26; }
    ToolsStep .ob-tool Select { width: 22; }
    ToolsStep .ob-tool .ob-summary { width: 1fr; padding: 1 0 0 1; color: $text-muted; }
    """

    def __init__(self, machine: settings.MachineSettings, statuses: list[tools.ToolStatus] | None = None) -> None:
        super().__init__()
        self.machine = machine
        self.statuses = statuses
        self._warned = False

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("🧭 Which clans will you lead?  ·  step 1 of 4", classes="build-title")
            yield Static("Looking for your AI tools…", id="ob-tools-loading")
            yield Vertical(id="ob-tools-list")
            yield Static("The top-right corner shows ⏳ limits for a subscription and 🪙 money for an API. "
                         "Orkcraft never stores a key: the tool reads its own.", classes="build-hint")
            yield Static("", id="ob-tools-note", classes="ob-note", markup=False)
            yield _buttons(("Skip", "ob-skip", "default"), ("Next →", "ob-next", "primary"))

    def on_mount(self) -> None:
        if self.statuses is None:
            self.detect()
        else:
            self.show(self.statuses)

    @work(thread=True, exclusive=True, group="onboarding-tools")
    def detect(self) -> None:
        found = tools.detect()
        self.app.call_from_thread(self.show, found)

    def show(self, statuses: list[tools.ToolStatus]) -> None:
        self.statuses = statuses
        self.query_one("#ob-tools-loading", Static).display = False
        box = self.query_one("#ob-tools-list", Vertical)
        box.remove_children()
        for st in statuses:
            known = self.machine.tools.get(st.id, settings.ToolChoice())
            usable = st.tool.available and st.found
            enabled = (known.enabled if self.machine.onboarded else st.found) and usable
            billing = known.billing if self.machine.onboarded and known.enabled else st.billing
            box.mount(Horizontal(
                Checkbox(f"{st.tool.title}", value=enabled, id=f"ob-tool-{st.id}", disabled=not usable),
                Select([("subscription", "subscription"), ("API key", "api")], value=billing, allow_blank=False,
                       id=f"ob-billing-{st.id}", disabled=not usable),
                Static(Text(st.summary()), classes="ob-summary"),
                classes="ob-tool",
            ))

    def choices(self) -> dict[str, settings.ToolChoice]:
        out = {}
        for st in self.statuses or []:
            try:
                on_ = self.query_one(f"#ob-tool-{st.id}", Checkbox).value
                billing = self.query_one(f"#ob-billing-{st.id}", Select).value
            except Exception:
                on_, billing = False, st.billing
            out[st.id] = settings.ToolChoice(enabled=bool(on_), billing=str(billing) if billing in settings.BILLINGS
                                             else "subscription")
        return out

    def action_next(self) -> None:
        if self.statuses is None:
            return
        picked = self.choices()
        if not any(c.enabled for c in picked.values()) and not self._warned:
            self._warned = True
            self.query_one("#ob-tools-note", Static).update(
                "⚠ No tool chosen: agents and the Builder will be unavailable. Next again to go on — or try "
                "`orkcraft --demo` first.")
            return
        self.dismiss({"action": "next", "tools": picked})

    def action_skip(self) -> None:
        found = {st.id: settings.ToolChoice(enabled=st.found and st.tool.available, billing=st.billing)
                 for st in self.statuses or []}
        self.dismiss({"action": "skip", "tools": found})

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        self.action_next() if event.button.id == "ob-next" else self.action_skip()


# -- step 2: mode -----------------------------------------------------------------------------------

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
    ModeStep RadioButton:focus { text-style: bold; }
    ModeStep .ob-section { text-style: bold; margin-top: 1; }
    ModeStep #ob-day-row { height: auto; align-horizontal: center; }
    ModeStep #ob-day-legend { height: auto; }
    ModeStep #ob-quiet { margin-top: 0; }
    """

    def __init__(self, machine: settings.MachineSettings | None = None, standalone: bool = False) -> None:
        super().__init__()
        self.machine = machine or settings.MachineSettings()
        self.mode = self.machine.mode
        self.standalone = standalone

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("🕰 Your day — the look of the town and its hours" if self.standalone
                        else "🧭 How should the town look?  ·  step 3 of 4", classes="build-title")
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


# -- step 3: the town -------------------------------------------------------------------------------

class TownStep(ModalScreen[dict | None]):
    """The town: empty, a preset of a domain, or described in words. Dismisses
    {"preset": id | "empty" | "custom", "domain", "prompt", "warder"}, "back", "skip" or None."""

    BINDINGS = [Binding("escape", "back", "Back")]
    DEFAULT_CSS = _css("TownStep", 84) + """
    TownStep #ob-empty { width: 100%; margin-bottom: 1; }
    TownStep #ob-town { height: auto; }
    TownStep #ob-town-left { width: 1fr; height: auto; }
    TownStep #ob-domain { width: 100%; }
    TownStep #ob-presets { height: auto; max-height: 9; margin-top: 1; }
    TownStep #ob-mascot { width: 18; height: auto; padding: 1 0 0 2; color: $accent; }
    TownStep #ob-blurb { height: auto; color: $text-muted; padding: 0 1; }
    TownStep #ob-prompt { margin-top: 1; }
    """

    def __init__(self, can_back: bool = True, show_warder: bool = True, has_agent: bool = True,
                 domain: str = town_presets.DOMAINS[0].id) -> None:
        super().__init__()
        self.can_back = can_back
        self.show_warder = show_warder
        self.has_agent = has_agent        # some tool was chosen: presets that need an agent are open
        self.domain = domain

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("🧭 Choose a town  ·  step 4 of 4", classes="build-title")
            yield Button("🏰 Start with an empty town", id="ob-empty")
            with Horizontal(id="ob-town"):
                with Vertical(id="ob-town-left"):
                    yield Select([(f"{d.icon} {d.title}", d.id) for d in town_presets.DOMAINS], value=self.domain,
                                 allow_blank=False, id="ob-domain")
                    yield OptionList(id="ob-presets")
                    yield Static("", id="ob-blurb", markup=False)
                    yield Input(placeholder="describe the town you need…", id="ob-prompt")
                yield Static("", id="ob-mascot", markup=False)
            yield Checkbox("Install the 🛡 Warder (recommended) — edits .claude/settings.json", value=True,
                           id="ob-warder")
            yield Static("", id="ob-town-note", classes="ob-note", markup=False)
            specs = ([("← Back", "ob-back", "default")] if self.can_back else []) + [
                ("Skip", "ob-skip", "default"), ("Build", "ob-build", "success")]
            yield _buttons(*specs)

    def on_mount(self) -> None:
        self.call_after_refresh(self._setup)     # pushed as the app starts, its children may not be in yet

    def _setup(self) -> None:
        self.query_one("#ob-warder", Checkbox).display = self.show_warder
        self.show_domain(self.domain)

    def show_domain(self, domain_id: str) -> None:
        self.domain = domain_id
        d = town_presets.domain(domain_id)
        self.query_one("#ob-mascot", Static).update("\n".join(d.art))
        lst = self.query_one("#ob-presets", OptionList)
        lst.clear_options()
        for p in town_presets.of_domain(domain_id):
            off = p.needs_agent and not self.has_agent
            lst.add_option(Option(f"{p.icon} {p.title}" + ("  (needs an AI tool)" if off else ""), id=p.id,
                                  disabled=off))
        lst.add_option(Option("❓ Didn't find it?", id=CUSTOM))
        lst.highlighted = 0
        self.show_choice()

    @property
    def choice(self) -> str:
        lst = self.query_one("#ob-presets", OptionList)
        if lst.highlighted is None:
            return CUSTOM
        return lst.get_option_at_index(lst.highlighted).id or CUSTOM

    def show_choice(self) -> None:
        pid = self.choice
        prompt = self.query_one("#ob-prompt", Input)
        prompt.display = pid == CUSTOM
        p = town_presets.preset(pid)
        blurb = (f"{p.blurb}" + ("  ·  a stub for now: it opens an empty town" if p.stub else "")) if p else \
            "Say what the town is for: the Town Builder plans it from the catalog, you approve the plan, " \
            "then it is raised. Until then your words wait in the Town Hall."
        self.query_one("#ob-blurb", Static).update(blurb)

    @on(Select.Changed, "#ob-domain")
    def _domain(self, event: Select.Changed) -> None:
        event.stop()
        if isinstance(event.value, str) and event.value != self.domain:
            self.show_domain(event.value)

    @on(OptionList.OptionHighlighted, "#ob-presets")
    def _highlighted(self, event: OptionList.OptionHighlighted) -> None:
        event.stop()
        self.show_choice()

    @on(OptionList.OptionSelected, "#ob-presets")
    def _selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        if event.option_id == CUSTOM:
            self.query_one("#ob-prompt", Input).focus()
        else:
            self.action_build()

    @on(Input.Submitted, "#ob-prompt")
    def _submitted(self, event: Input.Submitted) -> None:
        event.stop()
        self.action_build()

    def _result(self, preset: str) -> dict:
        return {"preset": preset, "domain": self.domain,
                "prompt": self.query_one("#ob-prompt", Input).value.strip() if preset == CUSTOM else "",
                "warder": self.show_warder and self.query_one("#ob-warder", Checkbox).value}

    def action_build(self) -> None:
        pid = self.choice
        if pid == CUSTOM and not self.query_one("#ob-prompt", Input).value.strip():
            self.query_one("#ob-town-note", Static).update("⚠ Describe the town first — or pick a preset.")
            self.query_one("#ob-prompt", Input).focus()
            return
        self.dismiss(self._result(pid))

    def action_back(self) -> None:
        self.dismiss("back" if self.can_back else "skip")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        bid = event.button.id
        if bid == "ob-empty":
            self.dismiss(self._result(EMPTY))
        elif bid == "ob-build":
            self.action_build()
        elif bid == "ob-back":
            self.action_back()
        else:
            self.dismiss("skip")


# -- step 4: raising the town -------------------------------------------------------------------------

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
    """What raising the town does, in order — each a real piece of work."""
    steps = ["Opening the camp's records"]
    if choice.get("warder"):
        steps.append("Installing the 🛡 Warder")
    steps.append("Raising the buildings")
    if choice.get("preset") == CUSTOM:
        steps.append("Leaving your order in the Town Hall")
    return steps


# -- the flow ---------------------------------------------------------------------------------------

class Onboarding:
    """Pushes the steps one after another and applies what was chosen.

    `on_town(choice)` is called with the town step's result (or an empty town on skip); the app
    raises it. Machine settings are saved when the mode step is passed, or on skip."""

    def __init__(self, app, machine_steps: bool, town_step: bool, on_town: Callable[[dict], None],
                 statuses: list[tools.ToolStatus] | None = None) -> None:
        self.app = app
        self.machine_steps = machine_steps
        self.town_step = town_step
        self.on_town = on_town
        self.statuses = statuses
        self.machine = settings.load()
        self.picked: dict[str, settings.ToolChoice] | None = None
        self.autonomy = self.machine.autonomy

    def start(self) -> None:
        if self.machine_steps:
            self._tools()
        elif self.town_step:
            self._town(can_back=False)

    # step 1
    def _tools(self) -> None:
        self.app.push_screen(ToolsStep(self.machine, self.statuses), self._after_tools)

    def _after_tools(self, result: dict | None) -> None:
        if result is None:
            return
        self.picked = result.get("tools") or {}
        if result.get("action") == "skip":
            self._save_machine(None)
            self._skip_town()
            return
        self._autonomy()

    # step 2
    def _autonomy(self) -> None:
        tools_ = tuple(t for t, c in {**self.machine.tools, **(self.picked or {})}.items() if c.enabled)
        self.app.push_screen(AutonomyStep(self.autonomy, tools_ or ("claude", "agy")), self._after_autonomy)

    def _after_autonomy(self, result: dict | str | None) -> None:
        if result is None:
            return
        if result == "back":
            self._tools()
            return
        if isinstance(result, dict):
            self.autonomy = int(result.get("autonomy", self.autonomy))
        if result == "skip":
            self._save_machine(None)
            self._skip_town()
            return
        self._mode()

    # step 2
    def _mode(self) -> None:
        self.app.push_screen(ModeStep(self.machine), self._after_mode)

    def _after_mode(self, result: dict | str | None) -> None:
        if result is None:
            return
        if result == "back":
            self._autonomy()
            return
        self._save_machine(result if isinstance(result, dict) else None)
        if result == "skip":
            self._skip_town()
        elif self.town_step:
            self._town(can_back=True)

    def _save_machine(self, day: dict | None) -> None:
        """Tools, mode and the day go to the machine settings (and to the town on screen)."""
        tools_ = dict(self.machine.tools)
        tools_.update(self.picked or {})
        machine = replace(self.machine, tools=tools_, onboarded=True, autonomy=self.autonomy)
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

    # step 3
    def _town(self, can_back: bool) -> None:
        claude_on = self.machine.tools.get("claude", settings.ToolChoice()).enabled
        has_agent = any(c.enabled for c in self.machine.tools.values())
        self.app.push_screen(TownStep(can_back=can_back, show_warder=claude_on, has_agent=has_agent),
                             self._after_town)

    def _after_town(self, result: dict | str | None) -> None:
        if result is None:
            return
        if result == "back":
            self._mode()
        elif result == "skip" or not isinstance(result, dict):
            self._skip_town()
        else:
            self.on_town(result)

    def _skip_town(self) -> None:
        if self.town_step:
            self.on_town({"preset": EMPTY, "domain": "", "prompt": "", "warder": False})


def mount_raise_bar(screen: Widget, total: int | None) -> RaiseBar:
    bar = RaiseBar(total)
    screen.mount(bar)
    return bar


def pause() -> None:
    if STEP_PAUSE_S > 0:
        time.sleep(STEP_PAUSE_S)
