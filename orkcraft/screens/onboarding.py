"""🧭 Onboarding: who you are → your day → the town → (the interview) → tools → autonomy → the look.

    Onboarding(app, machine_steps=True, town_step=True, on_town=app.raise_town).start()

The person comes first (design: docs/design/onboarding.md): the role and the industry, then a
typical day and its rhythm — both kept in the machine settings (`settings.profile`). Then the town:
the role's intents, those that fit the day first. When none fits, the interview asks about sources,
outputs, problems and AI tried, and the Town Builder adapts the role's templates to the answers.
The machine's part follows (tools and billing, the orcs' autonomy, the look and the hours).

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
from textual.message import Message
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import (Button, Checkbox, Input, Label, OptionList, ProgressBar, RadioButton, Select,
                             SelectionList, Static)
from textual.widgets.option_list import Option
from textual.widgets.selection_list import Selection

from orkcraft import schedule, settings, tools
from orkcraft.widgets.day_bar import DAY_COLOR, OFFICE_COLOR, QUIET_COLOR, DayBar
from orkcraft.realm import intents, interview, silhouettes
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


def hide_skip(screen: ModalScreen) -> None:
    """A newcomer is walked through every step: no Skip (Back still leads to the experience step)."""
    for b in screen.query("#ob-skip, #au-skip"):
        b.display = False


def _highlight(lst: OptionList, option_id: str) -> None:
    for i in range(lst.option_count):
        if lst.get_option_at_index(i).id == option_id:
            lst.highlighted = i
            return


def _highlighted_id(lst: OptionList) -> str:
    return "" if lst.highlighted is None else lst.get_option_at_index(lst.highlighted).id or ""


# -- how well you know orchestration -------------------------------------------------------------------

class XpStep(ModalScreen[dict | str | None]):
    """The first question: how well the operator knows agent orchestration. It picks the path —
    🐣 walked through everything, 🪓 the same with Skip, 🤘 straight to the tools and an empty town.
    Dismisses {"orchestration": "new" | "some" | "expert"}, "skip" or None."""

    BINDINGS = [Binding("escape", "back", "Back")]
    DEFAULT_CSS = _css("XpStep", 84) + """
    XpStep #ob-xp { height: auto; }
    XpStep #ob-xp > .option-list--option { padding: 0 1; }
    XpStep #ob-xp-path { height: auto; margin-top: 1; color: $text-muted; }
    """
    PATHS = {
        interview.NEW: "Next: who you are, your day, your AI tools, then a town picked or built with you — "
                       "every step, no skipping.",
        interview.SOME: "Next: who you are, your day, your AI tools, then a ready town or a short interview.",
        interview.EXPERT: "No interview: the rest of the setup, then an empty town you build yourself.",
    }

    def __init__(self, level: str = "", step: str = "", can_back: bool = False) -> None:
        super().__init__()
        self.level = level
        self.step = step
        self.can_back = can_back

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(_title("🧭 How well do you know agent orkestration?", self.step), classes="build-title")
            yield Static("Running several AI agents that hand work to each other. Your answer picks the path.",
                         classes="build-hint")
            options = []
            for lv in interview.ORCHESTRATION:
                prompt = Text(lv.label, style="bold")
                prompt.append(f"\n   {lv.blurb}", style="dim")
                options.append(Option(prompt, id=lv.id))
            yield OptionList(*options, id="ob-xp")
            yield Static("", id="ob-xp-path", markup=False)
            yield Static("", id="ob-xp-note", classes="ob-note", markup=False)
            yield _nav(self.can_back)

    def on_mount(self) -> None:
        self.call_after_refresh(self._setup)

    def _setup(self) -> None:
        lst = self.query_one("#ob-xp", OptionList)
        lst.highlighted = None
        if self.level:
            _highlight(lst, self.level)
        lst.focus()
        self.show()

    @property
    def choice(self) -> str:
        return _highlighted_id(self.query_one("#ob-xp", OptionList))

    def show(self) -> None:
        self.query_one("#ob-xp-path", Static).update(self.PATHS.get(self.choice, ""))

    @on(OptionList.OptionHighlighted)
    def _picked(self, event: OptionList.OptionHighlighted) -> None:
        event.stop()
        self.show()

    @on(OptionList.OptionSelected)
    def _selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        self.action_next()

    def action_next(self) -> None:
        if not self.choice:
            self.query_one("#ob-xp-note", Static).update("⚠ Pick the one closest to you.")
            return
        self.dismiss({"orchestration": self.choice})

    def action_skip(self) -> None:
        self.dismiss("skip")

    def action_back(self) -> None:
        self.dismiss("back" if self.can_back else "skip")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        {"ob-next": self.action_next, "ob-back": self.action_back}.get(event.button.id or "", self.action_skip)()


# -- who you are ------------------------------------------------------------------------------------

class Chip(Static, can_focus=True):
    """A one-row toggle: a click, space or enter turns it on or off (a Checkbox is three rows)."""

    BINDINGS = [Binding("space,enter", "toggle", "Toggle", show=False)]
    DEFAULT_CSS = """
    Chip { width: auto; height: 1; padding: 0 1; margin: 0 1 0 0; background: $panel; color: $text-muted; }
    Chip.-on { background: $accent 40%; color: $text; text-style: bold; }
    Chip:focus { text-style: bold reverse; }
    Chip:hover { background: $boost; }
    """

    class Toggled(Message):
        def __init__(self, chip: Chip) -> None:
            super().__init__()
            self.chip = chip

    def __init__(self, label: str, value: str, on: bool = False, id: str | None = None,
                 classes: str | None = None) -> None:
        super().__init__(label, id=id, classes=classes, markup=False)
        self.value = value
        self.set_class(on, "-on")

    @property
    def on(self) -> bool:
        return self.has_class("-on")

    def set_on(self, on: bool) -> None:
        self.set_class(on, "-on")

    def action_toggle(self) -> None:
        self.set_on(not self.on)
        self.post_message(self.Toggled(self))

    def on_click(self) -> None:
        self.focus()
        self.action_toggle()


class PersonStep(ModalScreen[dict | str | None]):
    """Who the operator is and how their day goes, on one screen: the role and the industry (each
    from a list or in their own words) and a typical day as chips — the role's own parts first (an
    ork's: writing code, tests and CI, deploys). Dismisses {"profile": {role, role_other, industry,
    industry_other, day, day_other}}, "back", "skip" or None."""

    BINDINGS = [Binding("escape", "back", "Back")]
    DEFAULT_CSS = _css("PersonStep", 100) + """
    PersonStep #ob-who { height: auto; }
    PersonStep .ob-col { width: 1fr; height: auto; margin-right: 1; }
    PersonStep .ob-col OptionList { height: auto; max-height: 12; }
    PersonStep .ob-col Label, PersonStep .ob-day-label { text-style: bold; }
    PersonStep .ob-day-label { margin-top: 1; }
    PersonStep #ob-day-chips { layout: grid; grid-size: 4; grid-rows: 1; grid-gutter: 0 1; height: auto; }
    PersonStep #ob-day-chips Chip { margin: 0; }
    PersonStep #ob-day-other { margin-top: 0; }
    PersonStep #ob-who-line { margin-top: 1; height: auto; }
    """

    def __init__(self, profile: dict | None = None, step: str = "", can_back: bool = False) -> None:
        super().__init__()
        self.profile = dict(profile or {})
        self.step = step
        self.can_back = can_back
        self.day: list[str] = list(self.profile.get("day") or [])
        self._chips_for = None                     # the role whose chips are shown

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(_title("🧭 Who are you?", self.step), classes="build-title")
            yield Static("Your role, where you work and what fills your day. Your first town starts from what "
                         "people like you do.", classes="build-hint")
            with Horizontal(id="ob-who"):
                with Vertical(classes="ob-col"):
                    yield Label("I work as…")
                    yield OptionList(*(Option(r.label, id=r.id) for r in intents.ROLES), id="ob-role")
                    yield Input(self.profile.get("role_other", ""), placeholder="your role, in your words",
                                id="ob-role-other")
                with Vertical(classes="ob-col"):
                    yield Label("…in")
                    yield OptionList(*(Option(i.label, id=i.id) for i in intents.INDUSTRIES), id="ob-industry")
                    yield Input(self.profile.get("industry_other", ""), placeholder="your field, in your words",
                                id="ob-industry-other")
                yield Static("", id="ob-mascot", classes="ob-mascot", markup=False)
            yield Label("A typical day is…", classes="ob-day-label")
            yield Vertical(id="ob-day-chips")
            yield Input(self.profile.get("day_other", ""), placeholder="…or your day in your own words",
                        id="ob-day-other")
            yield Static("", id="ob-who-line", markup=False)
            yield Static("", id="ob-who-note", classes="ob-note", markup=False)
            yield _nav(self.can_back)

    def on_mount(self) -> None:
        self.call_after_refresh(self._setup)

    def _setup(self) -> None:
        role_list, ind_list = self.query_one("#ob-role", OptionList), self.query_one("#ob-industry", OptionList)
        role_list.highlighted = None
        ind_list.highlighted = None
        if self.profile.get("role"):
            _highlight(role_list, self.profile["role"])
        if self.profile.get("industry"):
            _highlight(ind_list, self.profile["industry"])
        role_list.focus()
        self.show()

    def _chips(self, role_id: str) -> None:
        """The day's chips for this role (its own parts first); what was on stays on."""
        if role_id == self._chips_for:
            return
        self._chips_for = role_id
        box = self.query_one("#ob-day-chips", Vertical)
        box.remove_children()                     # chips have no ids: the old ones may still be leaving
        box.mount(*(Chip(c.label, c.id, c.id in self.day, classes="ob-day-chip")
                    for c in interview.day_options(role_id)))

    def chip(self, value: str) -> Chip:
        """The day's chip for this value, as shown now."""
        return next(c for c in self.query(".ob-day-chip").results(Chip) if c.value == value and c.is_attached)

    @on(Chip.Toggled)
    def _toggled(self, event: Chip.Toggled) -> None:
        event.stop()
        v = event.chip.value
        if event.chip.on and v not in self.day:
            self.day.append(v)
        elif not event.chip.on and v in self.day:
            self.day.remove(v)

    def result(self) -> dict:
        role = _highlighted_id(self.query_one("#ob-role", OptionList))
        ind = _highlighted_id(self.query_one("#ob-industry", OptionList))
        out: dict = {"role": role, "industry": ind}
        if role == intents.OTHER:
            out["role_other"] = self.query_one("#ob-role-other", Input).value.strip()
        if ind == intents.OTHER:
            out["industry_other"] = self.query_one("#ob-industry-other", Input).value.strip()
        shown = {c.id for c in interview.day_options(role)}
        out["day"] = [d for d in self.day if d in shown]
        out["day_other"] = self.query_one("#ob-day-other", Input).value.strip()
        return {k: v for k, v in out.items() if v}

    def show(self) -> None:
        r = self.result()
        self.query_one("#ob-who-note", Static).update("")          # a warning goes once something is picked
        self.query_one("#ob-role-other", Input).display = r.get("role") == intents.OTHER
        self.query_one("#ob-industry-other", Input).display = r.get("industry") == intents.OTHER
        self.query_one("#ob-mascot", Static).update("\n".join(intents.mascot(r.get("role", intents.OTHER))))
        self._chips(r.get("role", ""))
        line = Text()
        if r.get("role"):
            line.append("→ ", style="dim")
            line.append(interview.who(r), style="bold")
            line.append(f" · your mascot: {intents.nick(r['role'])}", style="bold")
            n = len(intents.for_role(r["role"]))
            line.append(f"  ·  {n} ready towns for this role, or the Builder makes one with you", style="dim")
        self.query_one("#ob-who-line", Static).update(line)

    @on(OptionList.OptionHighlighted)
    def _picked(self, event: OptionList.OptionHighlighted) -> None:
        event.stop()
        self.show()

    @on(OptionList.OptionSelected)
    def _selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        if event.option_id == intents.OTHER:
            box = "#ob-role-other" if event.option_list.id == "ob-role" else "#ob-industry-other"
            self.query_one(box, Input).focus()
        elif event.option_list.id == "ob-role":
            self.query_one("#ob-industry", OptionList).focus()

    @on(Input.Changed)
    def _typed(self, event: Input.Changed) -> None:
        event.stop()
        if event.input.id != "ob-day-other":
            self.show()

    def action_next(self) -> None:
        r = self.result()
        note = self.query_one("#ob-who-note", Static)
        if not r.get("role"):
            note.update("⚠ Pick your role — or Someone else and say it in your words.")
            return
        if r["role"] == intents.OTHER and not r.get("role_other"):
            note.update("⚠ Say your role in a few words.")
            self.query_one("#ob-role-other", Input).focus()
            return
        self.dismiss({"profile": r})

    def action_back(self) -> None:
        self.dismiss("back" if self.can_back else "skip")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        {"ob-next": self.action_next, "ob-back": self.action_back}.get(
            event.button.id or "", lambda: self.dismiss("skip"))()


# -- questions with options: your day, the interview ------------------------------------------------

class QuestionsStep(ModalScreen[dict | str | None]):
    """One page of interview.Page: each question a multi-select list (the role's common options
    first, marked ✦) and, where it has one, a field for anything else. Dismisses {"answers": {qid:
    [ids], qid + "_other": text}}, "back", "skip" or None."""

    BINDINGS = [Binding("escape", "back", "Back")]
    DEFAULT_CSS = _css("QuestionsStep", 100) + """
    QuestionsStep #ob-q-row { height: auto; }
    QuestionsStep .ob-q { width: 1fr; height: auto; margin-right: 1; }
    QuestionsStep .ob-q Label { text-style: bold; }
    QuestionsStep .ob-q SelectionList { height: auto; max-height: 16; }
    """

    def __init__(self, page: interview.Page, answers: dict | None = None, profile: dict | None = None,
                 step: str = "", can_back: bool = True, last: bool = False) -> None:
        super().__init__()
        self.page = page
        self.answers = dict(answers or {})
        self.profile = dict(profile or {})
        self.step = step
        self.can_back = can_back
        self.last = last

    def compose(self) -> ComposeResult:
        role, ind = self.profile.get("role", ""), self.profile.get("industry", "")
        with Vertical():
            yield Label(_title(f"🧭 {self.page.title}", self.step), classes="build-title")
            yield Static(self.page.hint, classes="build-hint")
            with Horizontal(id="ob-q-row"):
                for q in self.page.questions:
                    picked = set(self.answers.get(q.id) or [])
                    with Vertical(classes="ob-q"):
                        yield Label(q.title)
                        items = []
                        for choice, common in self.page.options(q, role, ind):
                            label = Text(choice.label)
                            if common:
                                label.append("  ✦", style="dim")
                            items.append(Selection(label, choice.id, choice.id in picked))
                        yield SelectionList[str](*items, id=f"ob-q-{q.id}")
                        if q.other:
                            yield Input(self.answers.get(f"{q.id}_other", ""), placeholder=q.other,
                                        id=f"ob-q-{q.id}-other")
            if any(q.suggest for q in self.page.questions) and role:
                yield Static(f"✦ common for {intents.role(role).title.lower()}s · space toggles",
                             classes="build-hint")
            else:
                yield Static("space toggles · pick as many as fit, or none", classes="build-hint")
            yield _nav(self.can_back, self.last)

    def result(self) -> dict:
        out: dict = {}
        for q in self.page.questions:
            out[q.id] = list(self.query_one(f"#ob-q-{q.id}", SelectionList).selected)
            if q.other:
                text = self.query_one(f"#ob-q-{q.id}-other", Input).value.strip()
                if text:
                    out[f"{q.id}_other"] = text
        return out

    def action_back(self) -> None:
        self.dismiss("back" if self.can_back else "skip")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        self.dismiss({"answers": self.result()})

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        bid = event.button.id
        if bid == "ob-next":
            self.dismiss({"answers": self.result()})
        elif bid == "ob-back":
            self.action_back()
        else:
            self.dismiss("skip")


# -- the town: the role's intents ---------------------------------------------------------------------

def intent_blurb(it: intents.Intent) -> Text:
    return Text("🏗 " + " · ".join(f"{b['icon']} {b['title']}" for b in it.plan["buildings"]), style="dim")


def intent_label(it: intents.Intent, star: bool) -> Text:
    """"⭐ Review War Tent ★  store reviews sorted, replies drafted" — the ork name, then plain words."""
    t = Text(it.label, style="bold")
    if star:
        t.append(" ★", style="bold")
    t.append(f"  {it.blurb}", style="dim")
    return t


class IntentStep(ModalScreen[dict | str | None]):
    """What the first town is for: an intent of the role (★ when it fits the operator's day), none
    fits — the interview — or, at the bottom, an empty town. Dismisses {"preset": id | "empty" |
    "custom", "role", "warder"}, "back", "skip" or None."""

    BINDINGS = [Binding("escape", "back", "Back")]
    DEFAULT_CSS = _css("IntentStep", 100) + """
    IntentStep #ob-for { height: auto; margin-bottom: 1; }
    IntentStep #ob-town { height: auto; }
    IntentStep #ob-town-left { width: 1fr; height: auto; }
    IntentStep #ob-role-browse { width: 100%; }
    IntentStep #ob-presets { height: auto; max-height: 8; margin-top: 1; }
    IntentStep #ob-blurb { height: auto; padding: 0 1; }
    IntentStep .ob-buttons #ob-empty { margin-left: 0; margin-right: 1; }
    IntentStep .ob-spacer { width: 1fr; }
    """

    def __init__(self, profile: dict | None = None, step: str = "", can_back: bool = True, last: bool = False,
                 show_warder: bool = False, choice: dict | None = None, builder: bool = True) -> None:
        super().__init__()
        self.profile = dict(profile or {})
        self.step = step
        self.can_back = can_back
        self.last = last
        self.show_warder = show_warder
        self.builder = builder            # the Town Builder plans with Claude Code: is it chosen?
        self.choice = dict(choice or {})
        self.role = self.choice.get("role") or self.profile.get("role") or intents.OTHER

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(_title("🧭 What should your first town do?", self.step), classes="build-title")
            yield Static("", id="ob-for", markup=False)
            with Horizontal(id="ob-town"):
                with Vertical(id="ob-town-left"):
                    yield Select([(r.label, r.id) for r in intents.ROLES], value=self.role, allow_blank=False,
                                 id="ob-role-browse")
                    yield OptionList(id="ob-presets")
                    yield Static("", id="ob-blurb", markup=False)
                yield Static("", id="ob-mascot", classes="ob-mascot", markup=False)
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
        day = self.profile.get("day") or []
        line = Text("For ", style="dim")
        line.append(interview.who(self.profile), style="bold")
        if day:
            line.append("  ·  ★ takes over a part of your day", style="dim")
        self.query_one("#ob-for", Static).update(line)
        self.show_role(self.role)
        if self.choice.get("preset"):
            _highlight(self.query_one("#ob-presets", OptionList), self.choice["preset"])

    def show_role(self, role_id: str) -> None:
        self.role = role_id
        self.query_one("#ob-mascot", Static).update("\n".join(intents.mascot(role_id)))
        lst = self.query_one("#ob-presets", OptionList)
        lst.clear_options()
        day = self.profile.get("day") or []
        for it in intents.for_role(role_id, day):
            lst.add_option(Option(intent_label(it, bool(intents.fit(it, day))), id=it.id))
        if self.builder:
            lst.add_option(Option("❓ None fits — tell the Builder about your work", id=CUSTOM))
        else:
            lst.add_option(Option("❓ None fits — needs Claude Code for the Builder", id=CUSTOM, disabled=True))
        lst.highlighted = 0
        self.show_choice()

    @property
    def choice_id(self) -> str:
        return _highlighted_id(self.query_one("#ob-presets", OptionList)) or CUSTOM

    def show_choice(self) -> None:
        it = intents.intent(self.choice_id)
        note = self.query_one("#ob-town-note", Static)
        note.update("" if self.builder else "The Builder plans a town with Claude Code: turn it on on the tools "
                    "step (Back) to describe your own — a ready town or an empty one needs no model.")
        blurb = intent_blurb(it) if it else Text(
            f"Two short questions: where your work comes from and goes, and what hurts. The Builder adapts a "
            f"{intents.role(self.role).title.lower()} town to your answers; you approve the plan before "
            "anything is raised.", style="dim")
        self.query_one("#ob-blurb", Static).update(blurb)

    @on(Select.Changed, "#ob-role-browse")
    def _role(self, event: Select.Changed) -> None:
        event.stop()
        if isinstance(event.value, str) and event.value != self.role:
            self.show_role(event.value)

    @on(OptionList.OptionHighlighted, "#ob-presets")
    def _highlighted(self, event: OptionList.OptionHighlighted) -> None:
        event.stop()
        self.show_choice()

    @on(OptionList.OptionSelected, "#ob-presets")
    def _selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        self.action_next()

    def _result(self, preset: str) -> dict:
        return {"preset": preset, "role": self.role,
                "warder": self.show_warder and self.query_one("#ob-warder", Checkbox).value}

    def action_next(self) -> None:
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


# -- your AI tools: the ones installed, led and rated -------------------------------------------------

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

XP, PERSON, TOOLS, INTENT, RULES = "xp", "person", "tools", "intent", "rules"
WHO_KEYS = ("role", "role_other", "industry", "industry_other", "day", "day_other")
INTERVIEW_STEPS = tuple(f"q:{p.id}" for p in interview.INTERVIEW)


class Onboarding:
    """Pushes the steps one after another, Back and Skip included, and applies what was chosen.

    The first answer — how well the operator knows orkestration — picks the path:
      🐣 new / 🪓 some   who you are (and your day) · your AI tools · the town (· 2 interview pages) · camp rules
      🤘 punk ork        your AI tools · camp rules, then an empty town to build themselves
    The AI tools are looked for in the background from the start, so their step opens ready. A
    newcomer gets no Skip after the first step. The person's part is asked when the machine is new
    or the profile is missing; the town for a project with none yet. `on_town(choice)` is called at
    the end with {"preset", "role", "warder", "prompt", "answers", "expert"} (an empty town on
    skip); the app raises it."""

    def __init__(self, app, machine_steps: bool, town_step: bool, on_town: Callable[[dict], None],
                 statuses: list[tools.ToolStatus] | None = None) -> None:
        self.app = app
        self.machine_steps = machine_steps
        self.town_step = town_step
        self.on_town = on_town
        self.detected: DETECTED | None = (statuses, []) if statuses is not None else None
        self.machine = settings.load()
        self.profile = dict(self.machine.profile)
        self.answers: dict = {}
        self.choice: dict = {}
        self.picked: dict[str, settings.ToolChoice] | None = None
        self.autonomy = self.machine.autonomy
        self.warder = True
        self.day: dict | None = None
        self.ask_person = machine_steps or not self.profile.get("orchestration") or (
            not self.expert and not self.profile.get("role"))
        self.steps = self._plan()
        self.i = 0
        if machine_steps and self.detected is None:
            threading.Thread(target=self._detect, daemon=True).start()

    def _detect(self) -> None:
        """In the background from the first step: the tools step opens with them found."""
        detected = detect_all()
        if self.detected is None:
            self.detected = detected

    @property
    def expert(self) -> bool:
        return self.profile.get("orchestration") == interview.EXPERT

    @property
    def novice(self) -> bool:
        return self.profile.get("orchestration") == interview.NEW

    def _plan(self) -> list[str]:
        """The steps of this run, from what is known so far (the first answer reshapes them)."""
        steps: list[str] = []
        if self.ask_person:
            steps.append(XP)
            if not self.expert:
                steps.append(PERSON)
        if self.machine_steps:
            steps.append(TOOLS)
        if self.town_step and not self.expert:
            steps.append(INTENT)
            if self._interviewing:
                steps += list(INTERVIEW_STEPS)
        if self.machine_steps:
            steps.append(RULES)
        return steps

    def start(self) -> None:
        if self.steps:
            self._show()
        elif self.town_step:                  # a punk ork's new project: nothing to ask
            self.warder = False
            self._finish()

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
        if name == XP:
            screen = XpStep(self.profile.get("orchestration", ""), self.step, can_back=back)
        elif name == PERSON:
            screen = PersonStep(self.profile, self.step, can_back=back)
        elif name == TOOLS:
            screen = ToolsStep(self.machine, self.detected, self.step, can_back=back, show_warder=self.town_step,
                               chosen=self.picked, warder=self.warder, ratings=self.profile.get("ai_tools"))
        elif name == INTENT:
            screen = IntentStep(self.profile, self.step, back, last and not self._interviewing,
                                show_warder=TOOLS not in self.steps and self.claude_on, choice=self.choice,
                                builder=self.claude_on)
        elif name in INTERVIEW_STEPS:
            page = interview.INTERVIEW[INTERVIEW_STEPS.index(name)]
            screen = QuestionsStep(page, self.answers, {**self.profile, "role": self.choice.get("role", "")},
                                   self.step, back, last)
        else:
            enabled = tuple(t for t, c in {**self.machine.tools, **(self.picked or {})}.items() if c.enabled)
            screen = AutonomyStep(self.autonomy, enabled or ("claude", "agy"), step=self.step, look=self.machine)
        self.app.push_screen(screen, done)
        if self.novice and name != XP:
            self.app.call_after_refresh(hide_skip, screen)

    @property
    def _interviewing(self) -> bool:
        return self.choice.get("preset") == CUSTOM

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
        if name == XP:
            self.profile["orchestration"] = result["orchestration"]
            self.steps = self._plan()
        elif name == PERSON:
            keep = {k: v for k, v in self.profile.items() if k not in WHO_KEYS}
            self.profile = {**keep, **result["profile"]}
        elif name == TOOLS:
            self.picked = result.get("tools") or {}
            self.detected = result.get("detected") or self.detected
            self.warder = bool(result.get("warder"))
            if result.get("ratings"):
                self.profile["ai_tools"] = result["ratings"]
            else:
                self.profile.pop("ai_tools", None)
        elif name == INTENT:
            self.choice = result
            self.warder = result.get("warder", self.warder) if TOOLS not in self.steps else self.warder
            self.steps = self._plan()
        elif name in INTERVIEW_STEPS:
            page = interview.INTERVIEW[INTERVIEW_STEPS.index(name)]
            for q in page.questions:
                self.answers.pop(f"{q.id}_other", None)
            self.answers.update(result["answers"])
        elif name == RULES:
            self.autonomy = int(result.get("autonomy", self.autonomy))
            self.day = {"mode": result.get("mode", self.machine.mode), "quiet": result.get("quiet"),
                        "office": self.machine.office, "office_days": self.machine.office_days}
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
        if not self.town_step:
            return
        choice = {"preset": self.choice.get("preset") or EMPTY, "role": self.choice.get("role", ""),
                  "warder": self.warder and self.claude_on, "prompt": "", "answers": {}, "expert": self.expert}
        if choice["preset"] == CUSTOM:
            choice["answers"] = dict(self.answers)
            choice["prompt"] = interview.summary({**self.profile, "role": self.profile.get("role", "")},
                                                 self.answers)
        self.on_town(choice)

    def _skip(self) -> None:
        if self.picked is None and self.detected is not None:          # skipped before the tools: the found ones
            self.picked = {st.id: settings.ToolChoice(enabled=st.found and st.tool.available, billing=st.billing)
                           for st in self.detected[0]}
        self._save_machine(None)
        if self.town_step:
            self.on_town({"preset": EMPTY, "role": "", "warder": False, "prompt": "", "answers": {}})


def mount_raise_bar(screen: Widget, total: int | None) -> RaiseBar:
    bar = RaiseBar(total)
    screen.mount(bar)
    return bar


def pause() -> None:
    if STEP_PAUSE_S > 0:
        time.sleep(STEP_PAUSE_S)
