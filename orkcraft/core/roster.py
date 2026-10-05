"""The roster as the core keeps it: every ork of the camp — garrisons, the Council, the sessions that
run — their questions (🔥), which were dismissed, and since when each has waited.

The face hands over what only it can see today: the live sessions (`WorkerInfo`, from its terminals)
and the questions a building's own view raises (`view_alerts`). Everything else is read from the town.
"""
from __future__ import annotations

import time
from collections.abc import Iterable

from orkcraft.core.town import Town
from orkcraft.realm import pipes
from orkcraft.realm.orcs import ALERT_ICON, Alert, Orc, garrison_badge
from orkcraft.realm.roster import Roster, WorkerInfo, build_roster

# A building's own question: (building id, key, title, context lines, options).
ViewAlert = tuple[str, str, str, list, list]


class Muster:
    def __init__(self, town: Town) -> None:
        self.town = town
        self.roster = Roster()
        self.dismissed: set[str] = set()              # questions acknowledged; the logs keep them
        self.deployments: dict[str, str] = {}         # session key → "<building id>/<orc id>"
        self.alert_first_seen: dict[str, float] = {}  # question id → when the roster first had it

    def rebuild(self, workers: Iterable[WorkerInfo], live: Iterable[str] = (),
                view_alerts: Iterable[ViewAlert] = ()) -> Roster:
        """The roster anew. `live`: the keys of the sessions that still exist (a deployment of a closed
        one is forgotten)."""
        town, live = self.town, set(live)
        self.deployments = {k: v for k, v in self.deployments.items() if k in live}
        built = []
        for b_spec in town.scroll.buildings:
            if b_spec.demolished:
                continue
            b = town.building(b_spec.id)
            if b is None:
                continue
            labels: dict[str, list[str]] = {}
            for road in b_spec.roads:
                if road.handler:
                    src = town.scroll.building(road.source)
                    src_label = f"{src.icon} {src.title}".strip() if src else road.source
                    labels.setdefault(road.handler, []).append(f"{src_label} · {pipes.label(road.event)}")
            built.append((b, b_spec.garrison.members, b_spec.garrison.lead_orc_id, labels))
        self.roster = build_roster(town.repo_root, built, list(workers), self.dismissed, deployments=self.deployments)
        self._add_view_alerts(view_alerts)
        self.note_alerts()
        return self.roster

    def _add_view_alerts(self, view_alerts: Iterable[ViewAlert]) -> None:
        """A building that needs the operator (a Catapult that must log in again) sets its lead ork's hut
        on fire."""
        standing = {b.id for b in self.town.scroll.buildings if not b.demolished}
        for bid, key, title, context, options in view_alerts:
            if bid not in standing:
                continue
            alert = Alert(id=f"view:{bid}:{key}", title=title, context=list(context), options=list(options),
                          source="view", ref=bid)
            if alert.id in self.dismissed:
                continue
            orc = self.roster.by_building(bid)
            if orc is not None:
                orc.status, orc.alert = "alert", alert
            self.roster.alerts.append(alert)

    def note_alerts(self) -> None:
        """Remember when each question first came up (the oldest opens first); forget the answered ones."""
        now = time.monotonic()
        live = {a.id for a in self.roster.alerts} | {o.alert.id for o in self.roster.orcs if o.alert is not None}
        for aid in live:
            self.alert_first_seen.setdefault(aid, now)
        for aid in set(self.alert_first_seen) - live:
            del self.alert_first_seen[aid]

    def questions_of(self, orkspace_id: str) -> list[Orc]:
        """The orks of an orkspace's buildings that wait for an answer, the longest waiting first."""
        self.note_alerts()
        scroll = self.town.scroll
        asking = [o for o in self.roster.orcs if o.alert is not None and o.building
                  and (ork := scroll.orkspace_of(o.building)) is not None and ork.id == orkspace_id]
        return sorted(asking, key=lambda o: self.alert_first_seen.get(o.alert.id, float("inf")))   # stable

    def who(self) -> dict[str, str]:
        """Question id → who asks it: an ork's name, a ticket, the Warder, a session."""
        out: dict[str, str] = {o.alert.id: o.name for o in self.roster.orcs if o.alert}
        for a in self.roster.alerts:
            if a.id not in out:
                out[a.id] = {"ticket": f"Ticket {a.ref}" if a.ref else "Ticket", "warder": "Warder",
                             "terminal": f"Session {a.ref}"}.get(a.source, "Alert")
        return out

    def badge(self, building_id: str, burning: bool = False) -> str:
        """The badge on a building's window and hut: its garrison, with 🔥 when something else waits
        there for the person (`burning`: a town order, a Loot cart)."""
        badge = garrison_badge(self.roster.garrison(building_id))
        if burning and ALERT_ICON not in badge:
            badge = f"{badge} {ALERT_ICON}".strip()
        return badge
