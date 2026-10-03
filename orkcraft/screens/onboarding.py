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

    BINDINGS = [Binding("escape", "skip", "Skip")]
    DEFAULT_CSS = _css("XpStep", 84) + """
    XpStep #ob-xp { height: auto; }
    XpStep #ob-xp > .option-list--option { padding: 0 1; }
    XpStep #ob-xp-path { height: auto; margin-top: 1; color: $text-muted; }
    """
    PATHS = {
        interview.NEW: "Next: who you are, your day, your AI tools, then a town picked or built with you.",
        interview.SOME: "Next: who you are, your day, your AI tools, then a ready town or a short interview.",
        interview.EXPERT: "Next: the CLIs you lead, the orcs' autonomy and the look — then an empty town to build.",
    }

    def __init__(self, level: str = "", step: str = "") -> None:
        super().__init__()
        self.level = level
        self.step = step

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(_title("🧭 How well do you know agent orchestration?", self.step), classes="build-title")
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
            yield _nav(False)

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

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        self.action_next() if event.button.id == "ob-next" else self.action_skip()


# -- your AI tools: experience × how often -------------------------------------------------------------

class AiToolsStep(ModalScreen[dict | str | None]):
    """Each AI tool graded twice — experience and how often — with the growth zones live below.
    Dismisses {"ai_tools": {tool: {"skill", "freq"}}} (tools left at none / never are left out),
    "back", "skip" or None."""

    BINDINGS = [Binding("escape", "back", "Back")]
    DEFAULT_CSS = _css("AiToolsStep", 84) + """
    AiToolsStep .ob-ai-row { height: 1; margin-top: 0; }
    AiToolsStep .ob-ai-head { height: 1; margin-top: 1; color: $text-muted; text-style: bold; }
    AiToolsStep .ob-ai-name { width: 36; }
    AiToolsStep .ob-ai-row Select { width: 18; height: 1; margin-right: 2; }
    AiToolsStep .ob-ai-row SelectCurrent { margin-top: 0; }      /* a Horizontal: no modal margin */
    AiToolsStep #ob-growth { height: auto; margin-top: 1; }
    """

    def __init__(self, graded: dict | None = None, step: str = "", can_back: bool = True) -> None:
        super().__init__()
        self.graded = dict(graded or {})
        self.step = step
        self.can_back = can_back

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(_title("🧭 Your AI tools — how well, how often", self.step), classes="build-title")
            yield Static("Experience and use for each. Where they differ is where you can grow; the town "
                         "leans on it.", classes="build-hint")
            yield Static("tool".ljust(36) + "experience".ljust(20) + "how often", classes="ob-ai-head")
            for tool in interview.AI_TOOLS:
                grade = self.graded.get(tool.id) or {}
                yield Horizontal(
                    Static(tool.label, classes="ob-ai-name"),
                    Select([(label, key) for key, label in interview.SKILLS], value=grade.get("skill", "none"), allow_blank=False, compact=True,
                           id=f"ob-skill-{tool.id}"),
                    Select([(label, key) for key, label in interview.FREQS], value=grade.get("freq", "never"), allow_blank=False, compact=True,
                           id=f"ob-freq-{tool.id}"),
                    classes="ob-ai-row")
            yield Static("", id="ob-growth", markup=False)
            yield _nav(self.can_back)

    def on_mount(self) -> None:
        self.show()

    def result(self) -> dict:
        out = {}
        for tool in interview.AI_TOOLS:
            skill = str(self.query_one(f"#ob-skill-{tool.id}", Select).value)
            freq = str(self.query_one(f"#ob-freq-{tool.id}", Select).value)
            if (skill, freq) != ("none", "never"):
                out[tool.id] = {"skill": skill, "freq": freq}
        return out

    def show(self) -> None:
        graded = self.result()
        zones = interview.growth(graded)
        t = Text()
        if not graded:
            t.append("🌱 New to AI tools — the town starts gently: you accept what the agents make before it leaves.",
                     style="dim")
        elif not zones:
            t.append("⚖️ Your experience matches your use — no gaps to grow into.", style="dim")
        else:
            t.append("Growth zones\n", style="bold")
            t.append("\n".join(zones))
        self.query_one("#ob-growth", Static).update(t)

    @on(Select.Changed)
    def _changed(self, event: Select.Changed) -> None:
        event.stop()
        self.show()

    def action_back(self) -> None:
        self.dismiss("back" if self.can_back else "skip")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        bid = event.button.id
        if bid == "ob-next":
            self.dismiss({"ai_tools": self.result()})
        elif bid == "ob-back":
            self.action_back()
        else:
            self.dismiss("skip")


# -- who you are ------------------------------------------------------------------------------------

class PersonStep(ModalScreen[dict | str | None]):
    """The role and the industry, each from a list or in the operator's words. Dismisses
    {"profile": {role, role_other, industry, industry_other}}, "back", "skip" or None."""

    BINDINGS = [Binding("escape", "back", "Back")]
    DEFAULT_CSS = _css("PersonStep", 96) + """
    PersonStep #ob-who { height: auto; }
    PersonStep .ob-col { width: 1fr; height: auto; margin-right: 1; }
    PersonStep .ob-col OptionList { height: auto; max-height: 12; }
    PersonStep .ob-col Label { text-style: bold; }
    PersonStep #ob-who-line { margin-top: 1; height: auto; }
    """

    def __init__(self, profile: dict | None = None, step: str = "", can_back: bool = False) -> None:
        super().__init__()
        self.profile = dict(profile or {})
        self.step = step
        self.can_back = can_back

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(_title("🧭 Who are you?", self.step), classes="build-title")
            yield Static("Your role and where you work. Your first town starts from what people like you do.",
                         classes="build-hint")
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

    def result(self) -> dict:
        role = _highlighted_id(self.query_one("#ob-role", OptionList))
        ind = _highlighted_id(self.query_one("#ob-industry", OptionList))
        out = {"role": role, "industry": ind}
        if role == intents.OTHER:
            out["role_other"] = self.query_one("#ob-role-other", Input).value.strip()
        if ind == intents.OTHER:
            out["industry_other"] = self.query_one("#ob-industry-other", Input).value.strip()
        return {k: v for k, v in out.items() if v}

    def show(self) -> None:
        r = self.result()
        self.query_one("#ob-who-note", Static).update("")          # a warning goes once something is picked
        self.query_one("#ob-role-other", Input).display = r.get("role") == intents.OTHER
        self.query_one("#ob-industry-other", Input).display = r.get("industry") == intents.OTHER
        self.query_one("#ob-mascot", Static).update("\n".join(intents.mascot(r.get("role", intents.OTHER))))
        line = Text()
        if r.get("role"):
            line.append("→ ", style="dim")
            line.append(interview.who(r), style="bold")
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
    t = Text()
    t.append(it.blurb + "\n")
    t.append("🏗 " + " · ".join(f"{b['icon']} {b['title']}" for b in it.plan["buildings"]), style="dim")
    return t


class IntentStep(ModalScreen[dict | str | None]):
    """What the first town is for: an intent of the role (★ when it fits the operator's day), an
    empty town, or none fits — the interview. Dismisses {"preset": id | "empty" | "custom",
    "role", "warder"}, "back", "skip" or None."""

    BINDINGS = [Binding("escape", "back", "Back")]
    DEFAULT_CSS = _css("IntentStep", 92) + """
    IntentStep #ob-empty { width: 100%; margin-bottom: 1; }
    IntentStep #ob-for { height: auto; margin-bottom: 1; }
    IntentStep #ob-town { height: auto; }
    IntentStep #ob-town-left { width: 1fr; height: auto; }
    IntentStep #ob-role-browse { width: 100%; }
    IntentStep #ob-presets { height: auto; max-height: 8; margin-top: 1; }
    IntentStep #ob-blurb { height: auto; color: $text-muted; padding: 0 1; }
    """

    def __init__(self, profile: dict | None = None, step: str = "", can_back: bool = True, last: bool = False,
                 show_warder: bool = False, choice: dict | None = None) -> None:
        super().__init__()
        self.profile = dict(profile or {})
        self.step = step
        self.can_back = can_back
        self.last = last
        self.show_warder = show_warder
        self.choice = dict(choice or {})
        self.role = self.choice.get("role") or self.profile.get("role") or intents.OTHER

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(_title("🧭 What should your first town do?", self.step), classes="build-title")
            yield Static("", id="ob-for", markup=False)
            yield Button("🏰 Start with an empty town", id="ob-empty")
            with Horizontal(id="ob-town"):
                with Vertical(id="ob-town-left"):
                    yield Select([(r.label, r.id) for r in intents.ROLES], value=self.role, allow_blank=False,
                                 id="ob-role-browse")
                    yield OptionList(id="ob-presets")
                    yield Static("", id="ob-blurb", markup=False)
                yield Static("", id="ob-mascot", classes="ob-mascot", markup=False)
            yield Checkbox("Install the 🛡 Warder (recommended) — edits .claude/settings.json",
                           value=self.choice.get("warder", True), id="ob-warder")
            yield Static("", id="ob-town-note", classes="ob-note", markup=False)
            yield _nav(self.can_back, self.last)

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
            star = "  ★" if intents.fit(it, day) else ""
            lst.add_option(Option(f"{it.label}{star}", id=it.id))
        lst.add_option(Option("❓ None fits — tell the Builder about your work", id=CUSTOM))
        lst.highlighted = 0
        self.show_choice()

    @property
    def choice_id(self) -> str:
        return _highlighted_id(self.query_one("#ob-presets", OptionList)) or CUSTOM

    def show_choice(self) -> None:
        it = intents.intent(self.choice_id)
        blurb = intent_blurb(it) if it else Text(
            f"A short interview: where your data comes from, where results go, what hurts and what AI you "
            f"tried. The Builder adapts a {intents.role(self.role).title.lower()} town to your answers; you "
            "approve the plan before anything is raised.")
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


# -- tools ------------------------------------------------------------------------------------------

class ToolsStep(ModalScreen[dict | str | None]):
    """Which CLIs to lead, and how each is paid for. Dismisses {"action": "next", "tools": {...},
    "statuses": [...], "warder": bool}, {"action": "skip", "tools": {...}} (the found ones, as
    detected), "back" or None. `chosen`: what was picked before (Back keeps it)."""

    BINDINGS = [Binding("escape", "back", "Back")]
    DEFAULT_CSS = _css("ToolsStep", 92) + """
    ToolsStep #ob-tools-list { height: auto; margin-bottom: 1; }
    ToolsStep .ob-tool { height: 3; }
    ToolsStep .ob-tool Checkbox { width: 26; }
    ToolsStep .ob-tool Select { width: 22; }
    ToolsStep .ob-tool .ob-summary { width: 1fr; padding: 1 0 0 1; color: $text-muted; }
    """

    def __init__(self, machine: settings.MachineSettings, statuses: list[tools.ToolStatus] | None = None,
                 step: str = "", can_back: bool = False, show_warder: bool = False,
                 chosen: dict[str, settings.ToolChoice] | None = None, warder: bool = True) -> None:
        super().__init__()
        self.machine = machine
        self.statuses = statuses
        self.step = step
        self.can_back = can_back
        self.show_warder = show_warder
        self.chosen = chosen
        self.warder = warder
        self._warned = False

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(_title("🧭 Which clans will you lead?", self.step), classes="build-title")
            yield Static("Looking for your AI tools…", id="ob-tools-loading")
            yield Vertical(id="ob-tools-list")
            yield Static("The top-right corner shows ⏳ limits for a subscription and 🪙 money for an API. "
                         "Orkcraft never stores a key: the tool reads its own.", classes="build-hint")
            yield Checkbox("Install the 🛡 Warder in this project (recommended) — edits .claude/settings.json",
                           value=self.warder, id="ob-warder")
            yield Static("", id="ob-tools-note", classes="ob-note", markup=False)
            yield _nav(self.can_back)

    def on_mount(self) -> None:
        self.query_one("#ob-warder", Checkbox).display = self.show_warder
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
            usable = st.tool.available and st.found
            if self.chosen is not None and st.id in self.chosen:
                enabled, billing = self.chosen[st.id].enabled and usable, self.chosen[st.id].billing
            else:
                known = self.machine.tools.get(st.id, settings.ToolChoice())
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
        self.dismiss({"action": "next", "tools": picked, "statuses": self.statuses,
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

XP, PERSON, DAY, AI, INTENT = "xp", "person", "day", "ai", "intent"
TOOLS, AUTONOMY, MODE = "tools", "autonomy", "mode"
WHO_KEYS = ("role", "role_other", "industry", "industry_other")
INTERVIEW_STEPS = tuple(f"q:{p.id}" for p in interview.INTERVIEW)


class Onboarding:
    """Pushes the steps one after another, Back and Skip included, and applies what was chosen.

    The first answer — how well the operator knows orchestration — picks the path:
      🐣 new / 🪓 some   who you are · your day · your AI tools · the town (· the interview) · machine
      🤘 punk orc        the machine's part, then an empty town to build themselves
    A newcomer gets no Skip after the first step. The person's part is asked when the machine is
    new or the profile is missing; the town for a project with none yet. `on_town(choice)` is called
    at the end with {"preset", "role", "warder", "prompt", "answers", "expert"} (an empty town on
    skip); the app raises it."""

    def __init__(self, app, machine_steps: bool, town_step: bool, on_town: Callable[[dict], None],
                 statuses: list[tools.ToolStatus] | None = None) -> None:
        self.app = app
        self.machine_steps = machine_steps
        self.town_step = town_step
        self.on_town = on_town
        self.statuses = statuses
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
                steps += [PERSON, DAY, AI]
        if self.town_step and not self.expert:
            steps.append(INTENT)
            if self._interviewing:
                steps += list(INTERVIEW_STEPS)
        if self.machine_steps:
            steps += [TOOLS, AUTONOMY, MODE]
        return steps

    def start(self) -> None:
        if self.steps:
            self._show()
        elif self.town_step:                  # a punk orc's new project: nothing to ask
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
            screen = XpStep(self.profile.get("orchestration", ""), self.step)
        elif name == AI:
            screen = AiToolsStep(self.profile.get("ai_tools"), self.step, can_back=back)
        elif name == PERSON:
            screen = PersonStep(self.profile, self.step, can_back=back)
        elif name == DAY:
            screen = QuestionsStep(interview.DAY_PAGE, self.profile, self.profile, self.step, back, last)
        elif name == INTENT:
            screen = IntentStep(self.profile, self.step, back, last and not self._interviewing,
                                show_warder=TOOLS not in self.steps and self.claude_on, choice=self.choice)
        elif name in INTERVIEW_STEPS:
            page = interview.INTERVIEW[INTERVIEW_STEPS.index(name)]
            screen = QuestionsStep(page, self.answers, {**self.profile, "role": self.choice.get("role", "")},
                                   self.step, back, last)
        elif name == TOOLS:
            screen = ToolsStep(self.machine, self.statuses, self.step, can_back=back,
                               show_warder=self.town_step, chosen=self.picked, warder=self.warder)
        elif name == AUTONOMY:
            enabled = tuple(t for t, c in {**self.machine.tools, **(self.picked or {})}.items() if c.enabled)
            screen = AutonomyStep(self.autonomy, enabled or ("claude", "agy"), step=self.step)
        else:
            screen = ModeStep(self.machine, step=self.step)
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
        elif name == AI:
            self.profile["ai_tools"] = result["ai_tools"]
            if not result["ai_tools"]:
                self.profile.pop("ai_tools")
        elif name == PERSON:
            keep = {k: v for k, v in self.profile.items() if k not in WHO_KEYS}
            self.profile = {**keep, **result["profile"]}
        elif name == DAY:
            self.profile.update({k: v for k, v in result["answers"].items()})
            if "day_other" not in result["answers"]:
                self.profile.pop("day_other", None)
        elif name == INTENT:
            self.choice = result
            self.warder = result.get("warder", self.warder) if TOOLS not in self.steps else self.warder
            self.steps = self._plan()
        elif name in INTERVIEW_STEPS:
            page = interview.INTERVIEW[INTERVIEW_STEPS.index(name)]
            for q in page.questions:
                self.answers.pop(f"{q.id}_other", None)
            self.answers.update(result["answers"])
        elif name == TOOLS:
            self.picked = result.get("tools") or {}
            self.statuses = result.get("statuses") or self.statuses
            self.warder = bool(result.get("warder"))
        elif name == AUTONOMY:
            self.autonomy = int(result.get("autonomy", self.autonomy))
        elif name == MODE:
            self.day = result
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
