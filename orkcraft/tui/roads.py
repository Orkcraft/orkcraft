"""Roads: rally mode (Y), the subscribe and rule dialogs, laying, removing and re-handling a road.

A part of `OrkcraftApp` (app.py): its methods run with the app as `self`.
"""
from __future__ import annotations



from orkcraft import scroll
from orkcraft.realm import fastpath, catalog, chronicles, pipes
from orkcraft.screens.road_rule_modal import RoadRuleModal
from orkcraft.screens.road_modal import PLAIN, RULE, RoadHandlerModal, SubscribeModal
from orkcraft.widgets.road_layer import split_key



class RoadsMixin:
    def rally_pick_number(self, number: int) -> None:
        """`Y` picked a source window for the receiver: choose the event and the handler."""
        target_id = getattr(self.desktop, "rally_source", None)
        self.desktop.exit_rally_mode()
        if not target_id or self.scroll is None:
            return
        source_w = next((w for w in self.desktop.windows if w.number == number and self.desktop.in_view(w)), None)
        if source_w is None:
            return
        source_id = source_w.window_id
        src_spec, tgt_spec = self.scroll.building(source_id), self.scroll.building(target_id)
        src_title = src_spec.title if src_spec else source_id
        tgt_title = tgt_spec.title if tgt_spec else target_id
        choices = self._road_choices(source_id, target_id) + self._rule_choices(source_id, target_id)
        if not choices:
            self.notify(f"{tgt_title} can take nothing from {src_title}", title="Roads")
            return

        def done(choice: tuple[str, str | None] | None) -> None:
            if choice and choice[1] == RULE:
                self.road_with_rule(target_id, source_id)
                return
            if choice:
                event, handler = choice
                orc = tgt_spec.garrison.handler(handler) if handler and tgt_spec else None
                base, _, route = event.partition("#")
                subject = fastpath.Subject("road", f"{source_id}->{target_id}", {
                    "source": source_id, "target": target_id, "event": base,
                    "handler_kind": orc.kind if orc else "", "filter": {"route": [route]} if route else {}})
                self.council_gate(subject, lambda: self.add_road(target_id, source_id, event, handler))

        self.push_screen(SubscribeModal(src_title, tgt_title, choices), done)

    def _road_choices(self, source_id: str, target_id: str) -> list[tuple[str, str | None, str]]:
        """(event, handler or None, label) the receiver can subscribe to from the source."""
        if self.scroll is None or source_id == target_id:
            return []
        src, tgt = self.scroll.building(source_id), self.scroll.building(target_id)
        if src is None or tgt is None:
            return []
        has_garrison = bool(src.garrison.members)
        out = [(ev, None, f"plain · {pipes.label(ev)}")
               for ev in pipes.road_events(source_id, target_id, has_garrison, handler=False)]
        spec = self.custom_specs.get(source_id)
        if spec is not None and catalog.type_of(spec).id == "signpost":     # one road per route
            from orkcraft.realm import signpost
            out = [(f"signpost.routed#{r}", None, f"plain · route {r}")
                   for r in signpost.routes((spec.get("config") or {}).get("rules") or [])] + out
        for orc in tgt.garrison.handlers:
            for ev in pipes.road_events(source_id, target_id, has_garrison, handler=True):
                out.append((ev, orc.id, f"{orc.avatar} {orc.name} ({orc.kind}) · {pipes.label(ev)}"))
        return out

    def _rule_choices(self, source_id: str, target_id: str) -> list[tuple[str, str | None, str]]:
        """Roads v2: one ✨ row per event the source sends — a rule makes the handler."""
        src = self.scroll.building(source_id) if self.scroll is not None else None
        if self.demo or src is None or source_id == target_id:
            return []
        if not pipes.road_events(source_id, target_id, bool(src.garrison.members), handler=True):
            return []
        return [("*", RULE, "✨ Listen with a prompt… — pick one or several events, say how to handle them")]

    def road_with_rule(self, target_id: str, source_id: str, picked: list[str] | None = None, note: str = "") -> None:
        """Roads v3: one or several events + a prompt → the Recruiter makes the handler
        (a chain or a script when the rule needs no judgement) → the Council reviews it. A rejection
        comes back here with the prompt emptied and the reason shown."""
        src, tgt = self.scroll.building(source_id), self.scroll.building(target_id)
        has = bool(src.garrison.members) if src else False
        events = [(ev, pipes.label(ev)) for ev in pipes.road_events(source_id, target_id, has, handler=True)]
        if not events:
            self.notify("this source sends nothing a listener can take", title="Roads")
            return

        def done(answer: tuple[list[str], str] | None) -> None:
            if not answer:
                return
            chosen, prompt = answer
            self.recruit_from_prompt(target_id, prompt, road=[(source_id, e) for e in chosen],
                                     on_rejected=lambda why: self.road_with_rule(target_id, source_id, chosen, why))

        self.push_screen(RoadRuleModal(src.title if src else source_id, tgt.title if tgt else target_id, events,
                                       picked, note), done)

    def _roads_changed(self) -> None:
        self.desktop.save()
        self.desktop.replan_roads()
        self.refresh_rally_indicators()

    def add_road(self, target_id: str, source_id: str, event: str, handler: str | None, quiet: bool = False) -> None:
        event, _, route = event.partition("#")             # a Signpost's route: a road that waits for it
        flt = {"route": [route]} if route else None
        try:
            road = scroll.subscribe(self.scroll, target_id, source_id, event, flt, handler=handler,
                                    label=route)
        except ValueError as e:
            self.notify(str(e), title="Roads", severity="warning")
            return
        self._roads_changed()
        if not quiet:
            self.checkpoint("road", target_id, f"road from {source_id} on {event}{' (' + route + ')' if route else ''}")
        src, tgt = self.scroll.building(source_id), self.scroll.building(target_id)
        orc = tgt.garrison.handler(handler) if handler and tgt else None
        who = orc.name if orc else "plain"
        src_title = src.title if src else source_id
        try:
            chronicles.record(self.repo_root, self.scroll, target_id, "road_subscribed",
                              source=src_title, event=pipes.label(event), handler=who)
        except OSError:
            pass
        if not quiet:
            self.notify(f"🛤 {src_title} → {tgt.title if tgt else target_id} ({pipes.label(event)}, {who})",
                        title="Roads")
        return road

    def remove_road(self, key: str) -> None:
        target_id, road_id = split_key(key)
        try:
            road = scroll.unsubscribe(self.scroll, target_id, road_id)
        except ValueError as e:
            self.notify(str(e), title="Roads", severity="warning")
            return
        self._roads_changed()
        self.checkpoint("road", target_id, f"remove road {road_id}")
        src = self.scroll.building(road.source)
        try:
            chronicles.record(self.repo_root, self.scroll, target_id, "road_removed",
                              source=src.title if src else road.source, event=pipes.label(road.event))
        except OSError:
            pass
        if self.focus_state.mode == "road":
            self.set_focus_state("building", building_id=target_id)
        self.notify(f"🚧 road from {src.title if src else road.source} removed", title="Roads")

    def change_road_handler(self, key: str) -> None:
        target_id, road_id = split_key(key)
        found = scroll.find_road(self.scroll, road_id, target_id)
        if found is None:
            return
        tgt, road = found
        src = self.scroll.building(road.source)
        # a handler takes whatever the source emits; plain only what the receiver shows
        handlers = [(o.id, f"{o.avatar} {o.name} ({o.kind})") for o in tgt.garrison.handlers]

        def done(choice: str | None) -> None:
            if choice is None:
                return
            handler = None if choice == PLAIN else choice
            if handler is None and road.event not in pipes.road_events(road.source, target_id, handler=False):
                self.notify(f"{tgt.title} cannot show this event without a handler", title="Roads", severity="warning")
                return
            try:
                scroll.set_road_handler(self.scroll, target_id, road_id, handler)
            except ValueError as e:
                self.notify(str(e), title="Roads", severity="warning")
                return
            self._roads_changed()
            orc = tgt.garrison.handler(handler) if handler else None
            try:
                chronicles.record(self.repo_root, self.scroll, target_id, "road_changed",
                                  source=src.title if src else road.source, handler=orc.name if orc else "plain")
            except OSError:
                pass
            self.set_focus_state("road", road=key)

        self.push_screen(RoadHandlerModal(self.desktop._road_label(key), handlers, road.handler), done)

    def refresh_rally_indicators(self) -> None:
        if self.scroll is None:
            return
        for w in self.desktop.windows:
            rally = self.scroll.rally_of(w.window_id)
            if rally:
                target_id = rally.target_building_id
                target_spec = self.scroll.building(target_id)
                target_title = target_spec.title if target_spec else target_id
                target_icon = target_spec.icon if target_spec and target_spec.icon else ""
                # Short, as in the spec's frame `[ 🚩 ──► 🔮 Spire ]`: the full title rarely fits beside the badge.
                short = (target_title.split() or [target_id])[-1].strip("()")
                target_label = f"{target_icon} {short}".strip()
                arrow = "🚩 ⏹──►" if rally.pipe_mode == pipes.ON_TASK else "🚩 ──►"
                w.set_rally(f"{arrow} {target_label}")
            else:
                w.set_rally("")
