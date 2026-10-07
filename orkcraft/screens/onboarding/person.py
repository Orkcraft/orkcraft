"""🧭 Onboarding, the person: how well you know orkestration, who you are, questions with options."""
from __future__ import annotations

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, OptionList, SelectionList, Static
from textual.widgets.option_list import Option
from textual.widgets.selection_list import Selection

from orkcraft.realm import intents, interview
from orkcraft.screens.onboarding.common import _css, _highlight, _highlighted_id, _nav, _title


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
            # the mascot's nick is a name (orkcraft.dev's class): said as written, never in today's words
            yield Static("", id="ob-who-line", markup=False, classes="-as-written")   # tui/wording.py AS_WRITTEN
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
