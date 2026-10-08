"""The build wizard.

    1. BuildWizard   — the type (or "let the Foreman pick") and what the building is for;
    2. (the Foreman prefills a spec from the catalog — app.start_wizard_build);
    3. BuildReview   — confirm or change title, events, quick actions and config (the size follows the content),
                       with a live preview of the hut; Build saves and raises it.

Everything offered comes from realm/catalog.py: an event, action or config key the type does not
declare cannot be picked, and the spec is checked again (masonry.validate_spec) before it is built.
"""
from __future__ import annotations

import copy
import json

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, OptionList, Select, SelectionList, Static
from textual.widgets.option_list import Option

from orkcraft.realm import catalog, huts
from orkcraft.tui import silhouettes

AUTO = "auto"

WIZARD_CSS = """
BuildWizard, BuildReview { align: center middle; }
#wizard-box, #review-box {
    width: 110; max-width: 96%; height: auto; max-height: 92%;
    border: thick $accent; background: $surface; padding: 1 2;
}
.wizard-title { text-style: bold; color: $accent; padding-bottom: 1; }
.wizard-section { text-style: bold; color: $accent; margin-top: 1; }
.wizard-hint { color: $text-muted; }
#wizard-types { height: 16; background: transparent; border: none; }
#wizard-prompt { margin-top: 1; }
#review-cols { height: auto; }
#review-form { width: 2fr; height: auto; max-height: 30; }
#review-side { width: 1fr; height: auto; padding-left: 2; }
#review-preview { height: 18; width: 100%; }
#review-preview Hut { offset: 0 0; }
#review-errors { color: $error; height: auto; }
.cfg-row { height: 3; }
.cfg-row Label { width: 16; padding-top: 1; }
.cfg-row Input { width: 1fr; }
#review-buttons { height: auto; margin-top: 1; }
#review-buttons Button { margin-right: 1; }
SelectionList { height: auto; max-height: 7; }
"""

GROUPS = (                                     # the camp map of T1107
    ("Intake and routing", ("pit", "watchtower", "signpost", "mill", "horn")),
    ("Queues and work", ("fields", "barracks", "council", "war_drum")),
    ("Storage, code, inspection", ("scrolls", "forge")),
    ("Results, telemetry, egress", ("loot", "crag", "catapult")),
)


class BuildWizard(ModalScreen[tuple[str | None, str] | None]):
    """Step 1: which type, and what it is for. Dismisses (type id | None for auto, request)."""

    DEFAULT_CSS = WIZARD_CSS
    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def compose(self) -> ComposeResult:
        with Vertical(id="wizard-box"):
            yield Static("🏗 NEW BUILDING · 1/2 — what to build", classes="wizard-title", markup=False)
            yield OptionList(id="wizard-types")
            yield Static("", id="wizard-type-help", classes="wizard-hint", markup=False)
            yield Label("What is it for? (the Foreman prefills the rest)", classes="wizard-section")
            yield Input(placeholder="e.g. watch my work inbox for messages from the release team", id="wizard-prompt")
            yield Static("↑↓ type · Tab to the description · Enter builds the proposal · Esc cancels",
                         classes="wizard-hint", markup=False)

    def on_mount(self) -> None:
        lst = self.query_one("#wizard-types", OptionList)
        lst.add_option(Option(Text("✨ Let the Foreman pick the type from the description", style="bold"), id=AUTO))
        for group, ids in GROUPS:
            lst.add_option(Option(Text(f"── {group} ──", style="dim"), disabled=True))
            for tid in ids:
                t = catalog.TYPES[tid]
                lst.add_option(Option(Text.assemble(f"{t.icon} {t.title}", (f"  {t.size}", "dim")), id=tid))
        lst.highlighted = 0
        lst.focus()

    def _type(self) -> str | None:
        lst = self.query_one("#wizard-types", OptionList)
        if lst.highlighted is None:
            return None
        oid = lst.get_option_at_index(lst.highlighted).id
        return None if oid in (None, AUTO) else oid

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        t = catalog.TYPES.get(event.option_id or "")
        self.query_one("#wizard-type-help", Static).update(
            f"{t.summary}. Sends: {', '.join(e.label for e in t.events) or '—'}" if t
            else "Describe the building; the Foreman chooses the type.")

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        self.query_one("#wizard-prompt", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        text = event.value.strip()
        tid = self._type()
        if not text and tid is None:
            self.notify("Describe the building, or pick its type", title="Build")
            return
        title = catalog.TYPES[tid].title if tid else ""
        self.dismiss((tid, text or f"a {title} building"))

    def action_cancel(self) -> None:
        self.dismiss(None)


def _parse(typ: type, raw: str):
    raw = raw.strip()
    if typ is int:
        return int(raw)
    if typ is float:
        return float(raw)
    if typ is bool:
        return raw.lower() in ("1", "true", "yes", "on", "y")
    if typ is list:
        if raw.startswith("["):                       # JSON: rules, steps with commas in them
            value = json.loads(raw)
            if not isinstance(value, list):
                raise ValueError("not a list")
            return value
        return [x.strip() for x in raw.split(";" if ";" in raw else ",") if x.strip()]
    return raw


def _show(value) -> str:
    if isinstance(value, list):
        if any(isinstance(x, (dict, list)) or "," in str(x) for x in value):
            return json.dumps(value, ensure_ascii=False)
        return ", ".join(map(str, value))
    if isinstance(value, bool):
        return "yes" if value else "no"
    return "" if value is None else str(value)


class BuildReview(ModalScreen[dict | None]):
    """Step 2: the Foreman's proposal, editable; Build dismisses the final spec (checked by the
    app before raising — its problems come back here via `show_problems`)."""

    DEFAULT_CSS = WIZARD_CSS
    BINDINGS = [Binding("escape", "cancel", "Cancel"), Binding("ctrl+s", "build", "Build")]

    def __init__(self, spec: dict, attempts: int = 1, cost_usd: float | None = None, check=None,
                 heading: str | None = None) -> None:
        super().__init__()
        self.heading = heading      # a preset's step 2 says so
        self.spec = copy.deepcopy(spec)
        self.check = check          # spec -> problems (masonry.validate_spec with the taken ids)
        self.type = catalog.type_of(spec)
        self.attempts, self.cost_usd = attempts, cost_usd

    # -- layout ---------------------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        t, s = self.type, self.spec
        cost = f" · ${self.cost_usd:.2f}" if self.cost_usd is not None else ""
        with Vertical(id="review-box"):
            yield Static(self.heading or f"🏗 NEW BUILDING · 2/2 — {t.icon} {t.title} (attempt {self.attempts}{cost})",
                         classes="wizard-title", markup=False)
            with Horizontal(id="review-cols"):
                with VerticalScroll(id="review-form"):
                    yield Label("Title", classes="wizard-section")
                    yield Input(value=s.get("title", ""), id="review-title")
                    yield Label("Icon", classes="wizard-section")
                    yield Input(value=s.get("icon", t.icon), id="review-icon", max_length=4)
                    yield Label("Description", classes="wizard-section")
                    yield Input(value=s.get("summary", ""), id="review-summary", max_length=200)
                    if t.events:
                        yield Label("Events it sends along roads", classes="wizard-section")
                        picked = set(catalog.events_of(s))
                        yield SelectionList(*[(f"{e.label} — {e.help}", e.id, e.id in picked) for e in t.events],
                                            id="review-events")
                    if t.actions:
                        yield Label(f"Quick actions on the hut (up to {catalog.MAX_QUICK_ACTIONS})",
                                    classes="wizard-section")
                        qa = {a.id for a in catalog.quick_actions_of(s)}
                        yield SelectionList(*[(f"{a.glyph} {a.label} — {a.help}", a.id, a.id in qa) for a in t.actions],
                                            id="review-actions")
                    if t.config:
                        yield Label("Settings (* required)", classes="wizard-section")
                        config = s.get("config") or {}
                        for key, (typ, allowed, required) in t.config.items():
                            hint = f"one of {', '.join(allowed)}" if isinstance(allowed, tuple) and typ is str else \
                                "a, b, c — or JSON" if typ is list else "yes / no" if typ is bool else typ.__name__
                            with Horizontal(classes="cfg-row"):
                                yield Label(f"{key}{' *' if required else ''}")
                                yield Input(value=_show(config.get(key)), placeholder=hint, id=f"cfg-{key}")
                with Vertical(id="review-side"):
                    yield Label("On the map", classes="wizard-section")
                    yield Container(id="review-preview")
                    yield Static("", id="review-sends", classes="wizard-hint", markup=False)
            yield Static("", id="review-errors", markup=False)
            with Horizontal(id="review-buttons"):
                yield Button("🏗 Build", variant="success", id="review-build")
                yield Button("Cancel", id="review-cancel")

    def on_mount(self) -> None:
        self._preview()
        self.query_one("#review-title", Input).focus()

    # -- the spec as edited -----------------------------------------------------------------------

    def current(self) -> tuple[dict, list[str]]:
        """The edited spec and the problems found while reading the form."""
        s, t, problems = copy.deepcopy(self.spec), self.type, []
        s["title"] = self.query_one("#review-title", Input).value.strip() or s.get("title", "")
        s["icon"] = self.query_one("#review-icon", Input).value.strip() or s.get("icon") or t.icon
        summary = self.query_one("#review-summary", Input).value.strip()
        if summary:
            s["summary"] = summary
        if t.events:
            s["events"] = list(self.query_one("#review-events", SelectionList).selected)
        if t.actions:
            s["quick_actions"] = list(self.query_one("#review-actions", SelectionList).selected)
        if t.config:
            config = {}
            for key, (typ, _, _) in t.config.items():
                raw = self.query_one(f"#cfg-{key}", Input).value
                if not raw.strip():
                    continue
                try:
                    config[key] = _parse(typ, raw)
                except ValueError:
                    problems.append(f"{key}: not a {typ.__name__}")
            s["config"] = config
        return s, problems

    def _preview(self) -> None:
        """The hut as it will stand on the map, updated in place as the form changes."""
        from textual.css.query import NoMatches

        from orkcraft.widgets.hut import Hut

        if not self.is_mounted:
            return
        try:
            spec, _ = self.current()
            box = self.query_one("#review-preview", Container)
        except NoMatches:               # an early change event, before the form is complete
            return
        sil, actions = silhouettes.of(spec), catalog.quick_actions_of(spec)
        hut = next(iter(box.query(Hut)), None)
        if hut is None:
            hut = Hut("preview", sil, actions)
            hut.set_silhouette(sil, actions)
            box.mount(hut)
        else:
            hut.set_silhouette(sil, actions)
        hut.set_title(1, f"{spec.get('icon', self.type.icon)} {spec.get('title', '')}")
        hut.set_status([self.type.preview, f"→ {len(catalog.events_of(spec))} events"])
        sends = ", ".join(catalog.event_label(e) or e for e in catalog.events_of(spec)) or "nothing typed"
        self.query_one("#review-sends", Static).update(f"Sends: {sends}")

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id in ("review-title", "review-icon"):
            self._preview()

    def on_select_changed(self, event: Select.Changed) -> None:
        self._preview()

    def on_selection_list_selected_changed(self, event: SelectionList.SelectedChanged) -> None:
        if event.selection_list.id == "review-actions" and len(event.selection_list.selected) > catalog.MAX_QUICK_ACTIONS:
            event.selection_list.deselect(event.selection_list.selected[-1])
            self.notify(f"At most {catalog.MAX_QUICK_ACTIONS} quick actions on a hut", title="Build")
        self._preview()

    def show_problems(self, problems: list[str]) -> None:
        self.query_one("#review-errors", Static).update("\n".join(f"⚠ {p}" for p in problems[:8]))

    # -- buttons --------------------------------------------------------------------------------

    def action_build(self) -> None:
        spec, problems = self.current()
        if not problems and self.check is not None:
            problems = self.check(spec)
        if problems:
            self.show_problems(problems)
            return
        self.dismiss(spec)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if event.button.id == "review-build":
            self.action_build()
        else:
            self.action_cancel()
