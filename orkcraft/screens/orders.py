"""Orders: modals the operator opens explicitly — never an agent.

- `AlertModal` — a ❓: minimal context and numbered quick answers.
- `UnitModal` — a resident orc: context for its work and its trigger.
"""
from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, OptionList, Select, Static
from textual.widgets.option_list import Option

from orkcraft.realm import lexicon
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
            yield Label(Text(f"❓ {self.who + ': ' if self.who else ''}{self.alert.title}"), classes="order-title -as-written")
            if self.alert.context:
                yield Static(Text("\n".join(self.alert.context[-10:])), classes="order-context -as-written")
            for key, label in self.alert.options:
                yield Button(f"[{key}] {label}", id=f"opt-{key}", variant="primary" if key == "1" else "default")
            yield Static("press the number · esc closes without answering", classes="order-hint")

    def action_choose(self, key: str) -> None:
        if any(k == key for k, _ in self.alert.options):
            self.dismiss(key)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id and event.button.id.startswith("opt-"):
            self.dismiss(event.button.id[4:])


def _title(count: str) -> str:
    return lexicon.words(f"❓ Awaiting Orders{count}")


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
        Binding("a", "follow", "Follow the Elders' advice", show=False),
        Binding("A", "follow_all", "Follow it for all", show=False),
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
    AwaitingOrdersModal #order-advice { color: $success; height: auto; }
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
            yield Label(Text(_title(count_str)), id="orders-title", classes="order-title")
            lst = OptionList(id="orders-list")
            for i, a in enumerate(self.alerts, 1):
                w = self.who_map.get(a.id, self.who)
                prefix = f"{w}: " if w else ""
                lst.add_option(Option(f"[{i}] {prefix}{a.title}", id=f"alert-opt-{i-1}"))
            yield lst
            yield Label("", id="order-target", classes="order-question -as-written")
            yield Static("", id="order-context", classes="order-context -as-written")
            yield Static("", id="order-advice", markup=False)
            with Horizontal(id="order-actions"):
                pass
            yield Static(Text("press number/letter to answer · a follows the Elders' advice, A for all · "
                              "↑↓ select question · esc closes"), classes="order-hint")

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
        title_label.update(_title(f" ({count})" if count > 1 else ""))

        target_label = self.query_one("#order-target", Label)
        prefix = f"🧌 {who}: " if who else "❓ "
        target_label.update(f"{prefix}{alert.title}")

        ctx_widget = self.query_one("#order-context", Static)
        if alert.context:
            ctx_widget.update(Text("\n".join(alert.context[-10:])))
            ctx_widget.display = True
        else:
            ctx_widget.update("")
            ctx_widget.display = False

        advice = self._advice(alert)
        advice_widget = self.query_one("#order-advice", Static)
        judged = self._judged(alert)
        if advice is not None:
            label = dict(alert.options).get(advice.key or "", "")
            text = f"🏛 The Elders advise [{advice.key}] {label} — {advice.why}"
            if advice.warn:
                text += f"\n⚠ The Warder flags this screen: {advice.warn} — read it before you follow (A skips it)"
            advice_widget.update(text)
        elif judged is not None:
            advice_widget.update(f"🏛 No advice: {judged.why}")
        advice_widget.display = judged is not None

        actions_box = self.query_one("#order-actions", Horizontal)
        await actions_box.remove_children()
        new_buttons = []
        for key, label in alert.options:
            var = "primary" if key in ("1", "y", "Y") else "default"
            new_buttons.append(Button(f"[{key}] {label}", id=f"opt-{key}", variant=var))
        if advice is not None:
            new_buttons.append(Button("[a] Follow the advice", id="btn-follow", variant="success"))
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
        elif bid == "btn-follow":
            await self.action_follow()
        elif bid == "btn-term":
            self.action_open_terminal()
        elif bid == "btn-card":
            self.action_open_card()
        elif bid == "btn-close":
            self.dismiss(None)

    # -- 🏛 the Elders' advice (left in quiet hours; followed only by the operator) ----------------

    def _judged(self, alert: Alert):
        app = getattr(self, "app", None)
        advice = getattr(app, "advice", None)
        mark = getattr(app, "elders_mark", None)
        return advice.get(mark(alert)) if advice is not None and mark is not None else None

    def _advice(self, alert: Alert):
        d = self._judged(alert)
        return d if d is not None and d.key is not None else None

    async def action_follow(self) -> None:
        """The operator follows the Elders' advice on the selected question."""
        if not self.alerts:
            return
        alert = self.alerts[self.selected_index]
        advice = self._advice(alert)
        if advice is not None:
            await self._answer_and_advance(alert, advice.key)

    async def action_follow_all(self) -> None:
        """The operator follows the advice on every question that has some, but for the ⚠ ones (the
        Warder flagged their screen: one at a time, with `a`); the rest stay."""
        for alert in [a for a in self.alerts if self._advice(a) is not None and not self._advice(a).warn]:
            self.selected_index = self.alerts.index(alert)
            await self._answer_and_advance(alert, self._advice(alert).key)
            if not self.alerts:
                return

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
            yield Label("Orders (context for this ork's work)")
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
                         "Resident orks act on them from stage 5.", classes="order-hint")

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
