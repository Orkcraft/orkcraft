"""The roster: every ork of the camp, their questions (🔥) and the answers sent back.

A part of `OrkcraftApp` (app.py): its methods run with the app as `self`.
"""
from __future__ import annotations


from orkcraft.realm.buildings import TOWN_HALL
from orkcraft.realm.orcs import Alert
from orkcraft.realm.roster import worker_infos
from orkcraft.screens.town_hall import TownHallView
from orkcraft.screens.orders import AwaitingOrdersModal


class RosterMixin:
    def _note_alerts(self) -> None:
        """Remember when each question first came up (core/roster.py)."""
        self.muster.note_alerts()

    def refresh_roster(self) -> None:
        # The 1 s timer can fire while the app shuts down and the windows are already unmounted.
        if not self._desktop.is_attached or not self._desktop.query("#chat-view"):
            return
        terminals = getattr(self.chat, "terminals", {})
        self.muster.rebuild(worker_infos(terminals, self.chat.meta), terminals, self._view_alerts())
        burning = set(self._loot_burning())
        for w in self.desktop.windows:
            hall_order = w.window_id == TOWN_HALL and getattr(self, "order_burning", False)
            w.set_badge(self.muster.badge(w.window_id, hall_order or w.window_id in burning))
            if (hut := self.desktop.huts.get(w.window_id)) is not None:
                hut.set_badge(w.badge)
        if hasattr(self, "_console") and self._console is not None:
            self._console.refresh_state(self.focus_state, self.roster)
        self.refresh_hud()
        self._elders_consider()

    def _view_alerts(self) -> list[tuple]:
        """What buildings' own views ask the operator: `orders_alert()` → (id, title, context, options)."""
        out = []
        for b_spec in self.scroll.buildings:
            if b_spec.demolished:
                continue
            ask = getattr(self._custom_view(b_spec.id), "orders_alert", None)
            wanted = ask() if callable(ask) else None
            if wanted:
                key, title, context, options = wanted
                out.append((b_spec.id, key, title, list(context), list(options)))
        return out

    def _alert_who_map(self) -> dict[str, str]:
        return self.muster.who()

    def open_alert(self, alert: Alert, who: str = "") -> None:
        who_map = {alert.id: who} if who else self._alert_who_map()
        self.push_screen(AwaitingOrdersModal([alert], who_map, who=who))

    def answer_alert(self, alert: Alert, key: str) -> None:
        if alert.source == "terminal":
            # Claude / agy menus take digits directly; Codex's want Enter after one, as yes/no
            # or input prompts do
            harness = self.chat.meta.get(alert.ref, ("",))[0]
            to_send = key if key.isdigit() and harness != "codex" else f"{key}\r"
            self.chat.send(alert.ref, to_send.encode())
            self.desktop.focus_window(self._sessions_window())  # type: ignore[arg-type]
            self.chat.show_terminal(alert.ref)
        elif alert.source == "warder":
            if key == "1":
                self.dismissed.add(alert.id)      # acknowledged; the log keeps it
        elif alert.source == "view":
            view = self._custom_view(alert.ref)
            answer = getattr(view, "answer_alert", None)
            if callable(answer) and answer(key) == "dismiss":
                self.dismissed.add(alert.id)
        self.refresh_roster()

    def action_awaiting_orders(self) -> None:
        if self.roster.alerts:
            who_map = self._alert_who_map()
            self.push_screen(AwaitingOrdersModal(self.roster.alerts, who_map))
        elif burning := self._loot_burning():
            self.desktop.focus_window(self.desktop.get_window(burning[0]))     # a cart waits for review
        else:
            self.notify("No units requiring orders", title="❓")

    def action_next_alert(self) -> None:
        self.action_awaiting_orders()

    def _console_refresh(self) -> None:
        if getattr(self, "_console", None) is not None:
            self._console.refresh_state(self.focus_state, self.roster)

    def _refresh_hall(self) -> None:
        w = self.desktop.get_window(TOWN_HALL)
        view = next(iter(w.query(TownHallView)), None) if w is not None else None
        if view is not None:
            view.refresh_hall()
