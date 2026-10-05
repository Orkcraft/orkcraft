"""Roads: rally mode (Y), the subscribe and rule dialogs, laying, removing and re-handling a road.

A part of `OrkcraftApp` (app.py): its methods run with the app as `self`.
"""
from __future__ import annotations



from orkcraft import scroll
from orkcraft.realm import fastpath, pipes
from orkcraft.screens.road_rule_modal import RoadRuleModal
from orkcraft.screens.road_modal import PLAIN, RULE, RoadHandlerModal, SubscribeModal
from orkcraft.core import roads as core_roads
from orkcraft.scroll import split_key



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
        return core_roads.choices(self.core, source_id, target_id)

    def _rule_choices(self, source_id: str, target_id: str) -> list[tuple[str, str | None, str]]:
        """Roads v2: one ✨ row per event the source sends — a rule makes the handler."""
        if self.demo or not core_roads.listenable(self.core, source_id, target_id):
            return []
        return [("*", RULE, "✨ Listen with a prompt… — pick one or several events, say how to handle them")]

    def road_with_rule(self, target_id: str, source_id: str, picked: list[str] | None = None, note: str = "") -> None:
        """Roads v3: one or several events + a prompt → the Recruiter makes the handler
        (a chain or a script when the rule needs no judgement) → the Council reviews it. A rejection
        comes back here with the prompt emptied and the reason shown."""
        src, tgt = self.scroll.building(source_id), self.scroll.building(target_id)
        events = core_roads.listenable(self.core, source_id, target_id)
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

    def add_road(self, target_id: str, source_id: str, event: str, handler: str | None, quiet: bool = False):
        return core_roads.lay(self.core, target_id, source_id, event, handler, quiet)

    def remove_road(self, key: str) -> None:
        road = core_roads.remove(self.core, key)
        if road is not None and self.focus_state.mode == "road":
            self.set_focus_state("building", building_id=split_key(key)[0])

    def change_road_handler(self, key: str) -> None:
        handlers = core_roads.handlers(self.core, key)
        if handlers is None:
            return
        target_id, road_id = split_key(key)
        _, road = scroll.find_road(self.scroll, road_id, target_id)

        def done(choice: str | None) -> None:
            if choice is not None and core_roads.set_handler(self.core, key, None if choice == PLAIN else choice):
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
