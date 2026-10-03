"""Orders: modals the operator opens explicitly — never an agent.

- `AlertModal` — a ❓: minimal context and numbered quick answers.
- `UnitModal` — a resident orc: context for its work and its trigger.
- `BuildModal` — ask Mason & Artisan for a new building.
"""
from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, OptionList, Select, Static
from textual.widgets.option_list import Option

from orkcraft.realm import modes
from orkcraft.realm.orcs import TRIGGERS, Alert, Orc, Trigger

MODAL_CSS = """
{cls} {{ align: center middle; }}
{cls} > Vertical {{
    width: 76; max-width: 95%; height: auto; max-height: 90%;
    border: thick $accent; background: $surface; padding: 1 2;
}}
{cls} .order-title {{ text-style: bold; color: $accent; margin-bottom: 1; }}
{cls} .order-context {{ color: $text-muted; margin-bottom: 1; }}
{cls} .order-hint {{ color: $text-muted; margin-top: 1; }}
{cls} Horizontal {{ height: auto; }}
{cls} Button {{ margin-right: 1; }}
"""


class AlertModal(ModalScreen[str | None]):
    """Dismisses with the chosen option key ("1", "2", …) or None."""

    BINDINGS = [Binding("escape", "dismiss(None)", "Close")] + [
        Binding(str(i), f"choose('{i}')", show=False) for i in range(1, 10)
    ]
    DEFAULT_CSS = MODAL_CSS.format(cls="AlertModal")

    def __init__(self, alert: Alert, who: str = "") -> None:
        super().__init__()
        self.alert = alert
        self.who = who

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(Text(f"❓ {self.who + ': ' if self.who else ''}{self.alert.title}"), classes="order-title")
            if self.alert.context:
                yield Static(Text("\n".join(self.alert.context[-10:])), classes="order-context")
            for key, label in self.alert.options:
                yield Button(f"[{key}] {label}", id=f"opt-{key}", variant="primary" if key == "1" else "default")
            yield Static("press the number · esc closes without answering", classes="order-hint")

    def action_choose(self, key: str) -> None:
        if any(k == key for k, _ in self.alert.options):
            self.dismiss(key)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id and event.button.id.startswith("opt-"):
            self.dismiss(event.button.id[4:])


class AwaitingOrdersModal(AlertModal):
    """Modal displaying all questions awaiting operator orders in a list.

    Supports cycling through questions, viewing details/context,
    and directly answering via digits 1..9, y/n, or clicking action buttons.
    """

    BINDINGS = [
        Binding("escape", "dismiss(None)", "Close"),
        Binding("t", "open_terminal", "Open Terminal", show=False),
        Binding("c", "open_card", "Open Card", show=False),
        Binding("y", "choose('y')", show=False),
        Binding("n", "choose('n')", show=False),
    ] + [
        Binding(str(i), f"choose('{i}')", show=False) for i in range(1, 10)
    ]
    DEFAULT_CSS = """
    AwaitingOrdersModal { align: center middle; }
    AwaitingOrdersModal > Vertical {
        width: 82; max-width: 95%; height: auto; max-height: 90%;
        border: thick $accent; background: $surface; padding: 1 2;
    }
    AwaitingOrdersModal .order-title { text-style: bold; color: $accent; margin-bottom: 1; }
    AwaitingOrdersModal #orders-list {
        height: auto; max-height: 6; margin-bottom: 1; border: solid $surface-lighten-2;
    }
    AwaitingOrdersModal .order-question { text-style: bold; color: $text; margin-bottom: 1; }
    AwaitingOrdersModal .order-context { color: $text-muted; margin-bottom: 1; max-height: 8; overflow-y: auto; }
    AwaitingOrdersModal #order-actions { height: auto; margin-top: 1; margin-bottom: 1; }
    AwaitingOrdersModal #order-actions Button { margin-right: 1; margin-bottom: 1; }
    AwaitingOrdersModal .order-hint { color: $text-muted; margin-top: 1; }
    """

    def __init__(self, alerts: list[Alert] | Alert, who_map: dict[str, str] | None = None, who: str = "") -> None:
        if isinstance(alerts, Alert):
            alerts = [alerts]
        super().__init__(alerts[0] if alerts else Alert(id="", title=""), who=who)
        self.alerts: list[Alert] = list(alerts)
        self.who_map: dict[str, str] = who_map or {}
        self.selected_index: int = 0

    def compose(self) -> ComposeResult:
        with Vertical():
            count = len(self.alerts)
            count_str = f" ({count})" if count > 1 else ""
            yield Label(Text(f"❓ Awaiting Orders{count_str}"), id="orders-title", classes="order-title")
            lst = OptionList(id="orders-list")
            for i, a in enumerate(self.alerts, 1):
                w = self.who_map.get(a.id, self.who)
                prefix = f"{w}: " if w else ""
                lst.add_option(Option(f"[{i}] {prefix}{a.title}", id=f"alert-opt-{i-1}"))
            yield lst
            yield Label("", id="order-target", classes="order-question")
            yield Static("", id="order-context", classes="order-context")
            with Horizontal(id="order-actions"):
                pass
            yield Static(Text("press number/letter to answer · ↑↓ select question · esc closes"), classes="order-hint")

    async def on_mount(self) -> None:
        await self._sync_view()

    async def _sync_view(self) -> None:
        if not self.alerts:
            self.dismiss(None)
            return
        self.selected_index = max(0, min(self.selected_index, len(self.alerts) - 1))
        alert = self.alerts[self.selected_index]
        self.alert = alert  # Keep self.alert synced for AlertModal compatibility
        who = self.who_map.get(alert.id, self.who)

        title_label = self.query_one("#orders-title", Label)
        count = len(self.alerts)
        title_label.update(f"❓ Awaiting Orders ({count})" if count > 1 else "❓ Awaiting Orders")

        target_label = self.query_one("#order-target", Label)
        prefix = f"{modes.skin('🧌')} {who}: " if who else "❓ "
        target_label.update(f"{prefix}{alert.title}")

        ctx_widget = self.query_one("#order-context", Static)
        if alert.context:
            ctx_widget.update(Text("\n".join(alert.context[-10:])))
            ctx_widget.display = True
        else:
            ctx_widget.update("")
            ctx_widget.display = False

        actions_box = self.query_one("#order-actions", Horizontal)
        await actions_box.remove_children()
        new_buttons = []
        for key, label in alert.options:
            var = "primary" if key in ("1", "y", "Y") else "default"
            new_buttons.append(Button(f"[{key}] {label}", id=f"opt-{key}", variant=var))
        if alert.source == "terminal":
            new_buttons.append(Button("[T] Terminal", id="btn-term", variant="default"))
        elif alert.source == "ticket":
            new_buttons.append(Button("[C] Ticket", id="btn-card", variant="default"))
        new_buttons.append(Button("Close", id="btn-close", variant="default"))
        await actions_box.mount_all(new_buttons)

    async def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        if event.option_index is not None and event.option_index != self.selected_index:
            self.selected_index = event.option_index
            await self._sync_view()

    async def action_choose(self, key: str) -> None:
        if not self.alerts:
            self.dismiss(None)
            return
        alert = self.alerts[self.selected_index]
        if any(k.lower() == key.lower() for k, _ in alert.options):
            await self._answer_and_advance(alert, key)

    async def _answer_and_advance(self, alert: Alert, key: str) -> None:
        app = getattr(self, "app", None)
        if app and hasattr(app, "answer_alert"):
            app.answer_alert(alert, key)
        self.alerts.pop(self.selected_index)
        if not self.alerts:
            self.dismiss(key)
            return
        self.selected_index = min(self.selected_index, len(self.alerts) - 1)
        try:
            lst = self.query_one("#orders-list", OptionList)
            lst.clear_options()
            for i, a in enumerate(self.alerts, 1):
                w = self.who_map.get(a.id, self.who)
                prefix = f"{w}: " if w else ""
                lst.add_option(Option(f"[{i}] {prefix}{a.title}", id=f"alert-opt-{i-1}"))
            lst.highlighted = self.selected_index
        except Exception:
            pass
        await self._sync_view()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid.startswith("opt-"):
            await self.action_choose(bid[4:])
        elif bid == "btn-term":
            self.action_open_terminal()
        elif bid == "btn-card":
            self.action_open_card()
        elif bid == "btn-close":
            self.dismiss(None)

    def action_open_terminal(self) -> None:
        if not self.alerts:
            self.dismiss(None)
            return
        alert = self.alerts[self.selected_index]
        if alert.source == "terminal" and alert.ref:
            app = getattr(self, "app", None)
            if app:
                self.dismiss(None)
                w = app._sessions_window()                # the hall's Sessions tab
                if w:
                    app.desktop.focus_window(w)
                app.chat.show_terminal(alert.ref)

    def action_open_card(self) -> None:
        if not self.alerts:
            self.dismiss(None)
            return
        alert = self.alerts[self.selected_index]
        if alert.source == "ticket" and alert.ref:
            app = getattr(self, "app", None)
            if app:
                self.dismiss(None)
                from orkcraft.screens.node_detail import NodeDetailScreen
                app.push_screen(NodeDetailScreen(alert.ref))


class UnitModal(ModalScreen[dict | None]):
    """Dismisses with {"trigger": Trigger, "context": str[, "tier": str]} or None."""

    BINDINGS = [Binding("escape", "dismiss(None)", "Close")]
    DEFAULT_CSS = MODAL_CSS.format(cls="UnitModal")

    def __init__(self, orc: Orc, building_title: str, context: str = "", tier: str | None = None) -> None:
        """`tier` is the handler's tier ("" for the CLI default); None hides the picker (stewards, chains)."""
        super().__init__()
        self.orc = orc
        self.building_title = building_title
        self.context = context
        self.tier = tier

    def compose(self) -> ComposeResult:
        o = self.orc
        with Vertical():
            yield Label(Text(f"🧌 {o.tier_icon + ' ' if o.tier_icon else ''}{o.name} — {self.building_title}"),
                        classes="order-title")
            yield Static(Text(f"{o.role}\nstatus: {o.status_icon} {o.status}"), classes="order-context")
            yield Label("Orders (context for this orc's work)")
            yield Input(value=self.context, placeholder="e.g. keep an eye on T1092 and nudge me before 06:00",
                        id="unit-context")
            yield Label("Trigger")
            with Horizontal():
                yield Select([(f"{icon} {name}", key) for key, (icon, name) in TRIGGERS.items()],
                             value=o.trigger.type, allow_blank=False, id="unit-trigger")
                yield Input(value=o.trigger.expression, placeholder="cron: */15 * * * * · webhook: /path",
                            id="unit-expr")
            if self.tier is not None:
                from orkcraft.screens.garrison_modal import tier_options
                yield Label("Tier")
                yield Select(tier_options(), value=self.tier, allow_blank=False, id="unit-tier")
            with Horizontal():
                yield Button("Save orders", variant="primary", id="unit-save")
                if o.alert is not None:
                    yield Button("Answer ❓", variant="warning", id="unit-answer")
                yield Button("Cancel", id="unit-cancel")
            yield Static("Orders and trigger are kept in the Town Scroll (.orkcraft.json). "
                         "Resident orcs act on them from stage 5.", classes="order-hint")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "unit-save":
            trigger = Trigger(str(self.query_one("#unit-trigger", Select).value),
                              self.query_one("#unit-expr", Input).value.strip())
            result = {"trigger": trigger, "context": self.query_one("#unit-context", Input).value.strip()}
            if self.tier is not None:
                tier = str(self.query_one("#unit-tier", Select).value)
                if tier != self.tier:
                    result["tier"] = tier
            self.dismiss(result)
        elif bid == "unit-answer":
            self.dismiss({"answer": True})
        else:
            self.dismiss(None)


class BuildModal(ModalScreen[str | None]):
    BINDINGS = [Binding("escape", "dismiss(None)", "Close")]
    DEFAULT_CSS = MODAL_CSS.format(cls="BuildModal")

    def __init__(self, initial_prompt: str = "") -> None:
        super().__init__()
        self.initial_prompt = initial_prompt

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("🏗️ Build Window — Mason & Artisan", classes="order-title")
            yield Static(Text("Describe the building: what it shows, where the data comes from, who watches it.\n"
                              "Mason designs the data schema, Artisan offers layouts and actions;\n"
                              "the spec is validated against the JSON Schema before you confirm raising it."),
                         classes="order-context")
            yield Input(value=self.initial_prompt, placeholder="e.g. a window with failing CI runs and the last 50 log lines", id="build-prompt")
            with Horizontal():
                yield Button("Send to Mason", variant="primary", id="build-send")
                yield Button("Cancel", id="build-cancel")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value.strip() or None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "build-send":
            self.dismiss(self.query_one("#build-prompt", Input).value.strip() or None)
        else:
            self.dismiss(None)
