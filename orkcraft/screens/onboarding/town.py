"""🧭 Onboarding, the town: the role's intents."""
from __future__ import annotations

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Label, OptionList, Select, Static
from textual.widgets.option_list import Option

from orkcraft.realm import intents, interview
from orkcraft.screens.onboarding.common import CUSTOM, EMPTY, _css, _highlight, _highlighted_id, _title


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
