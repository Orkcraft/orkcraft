"""The roster: every ork of the camp, their questions (🔥) and the answers sent back.

A part of `OrkcraftApp` (app.py): its methods run with the app as `self`.
"""
from __future__ import annotations

import time

from orkcraft.realm import pipes
from orkcraft.realm.buildings import TOWN_HALL
from orkcraft.realm.orcs import ALERT_ICON, Alert, garrison_badge
from orkcraft.realm.roster import build_roster, worker_infos
from orkcraft.screens.town_hall import TownHallView
from orkcraft.screens.orders import AwaitingOrdersModal


class RosterMixin:
    def _note_alerts(self) -> None:
        """Remember when each question first came up (the oldest opens first); forget the answered ones."""
        now = time.monotonic()
        live = {a.id for a in self.roster.alerts} | {o.alert.id for o in self.roster.orcs if o.alert is not None}
        for aid in live:
            self.alert_first_seen.setdefault(aid, now)
        for aid in set(self.alert_first_seen) - live:
            del self.alert_first_seen[aid]

    def refresh_roster(self) -> None:
        # The 1 s timer can fire while the app shuts down and the windows are already unmounted.
        if not self._desktop.is_attached or not self._desktop.query("#chat-view"):
            return
        existing_terms = getattr(self.chat, "terminals", {})
        self.deployments = {k: v for k, v in self.deployments.items() if k in existing_terms}

        built = []
        for b_spec in self.scroll.buildings:
            if b_spec.demolished:
                continue
            b = self.building(b_spec.id)
            if b is None:
                continue
            labels: dict[str, list[str]] = {}
            for road in b_spec.roads:
                if road.handler:
                    src = self.scroll.building(road.source)
                    src_label = f"{src.icon} {src.title}".strip() if src else road.source
                    labels.setdefault(road.handler, []).append(f"{src_label} · {pipes.label(road.event)}")
            built.append((b, b_spec.garrison.members, b_spec.garrison.lead_orc_id, labels))

        workers = worker_infos(self.chat.terminals, self.chat.meta)
        self.roster = build_roster(
            self.repo_root, built, workers, self.dismissed, deployments=self.deployments
        )
        self._view_alerts()
        self._note_alerts()
        burning = set(self._loot_burning())
        for w in self.desktop.windows:
            badge = garrison_badge(self.roster.garrison(w.window_id))
            if w.window_id == TOWN_HALL and getattr(self, "order_burning", False) and ALERT_ICON not in badge:
                badge = f"{badge} {ALERT_ICON}".strip()      # a town described in words waits for the Builder
            if w.window_id in burning and ALERT_ICON not in badge:
                badge = f"{badge} {ALERT_ICON}".strip()      # a Loot cart waits for review
            w.set_badge(badge)
            if (hut := self.desktop.huts.get(w.window_id)) is not None:
                hut.set_badge(w.badge)

        if hasattr(self, "_console") and self._console is not None:
            self._console.refresh_state(self.focus_state, self.roster)
        self.refresh_hud()
        self._elders_consider()

    def _view_alerts(self) -> None:
        """A building whose own view needs the operator (a Catapult that must log in again) sets its
        lead orc's hut on fire: `orders_alert()` → (id, title, context, options)."""
        for b_spec in self.scroll.buildings:
            if b_spec.demolished:
                continue
            view = self._custom_view(b_spec.id)
            ask = getattr(view, "orders_alert", None)
            wanted = ask() if callable(ask) else None
            if not wanted:
                continue
            key, title, context, options = wanted
            alert = Alert(id=f"view:{b_spec.id}:{key}", title=title, context=list(context), options=list(options),
                          source="view", ref=b_spec.id)
            if alert.id in self.dismissed:
                continue
            orc = self.roster.by_building(b_spec.id)
            if orc is not None:
                orc.status, orc.alert = "alert", alert
            self.roster.alerts.append(alert)

    def _alert_who_map(self) -> dict[str, str]:
        who_map: dict[str, str] = {}
        for o in self.roster.orcs:
            if o.alert:
                who_map[o.alert.id] = o.name
        for a in self.roster.alerts:
            if a.id not in who_map:
                if a.source == "ticket":
                    who_map[a.id] = f"Ticket {a.ref}" if a.ref else "Ticket"
                elif a.source == "warder":
                    who_map[a.id] = "Warder"
                elif a.source == "terminal":
                    who_map[a.id] = f"Session {a.ref}"
                else:
                    who_map[a.id] = "Alert"
        return who_map

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
