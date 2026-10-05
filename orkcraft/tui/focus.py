"""The focus state machine: what is selected (nothing, a building, an ork, a road) and the clicks and keys that change it.

A part of `OrkcraftApp` (app.py): its methods run with the app as `self`.
"""
from __future__ import annotations

from textual import events

from orkcraft import scroll
from orkcraft.realm.buildings import TOWN_HALL
from orkcraft.screens.console import ClanRoster, orc_key
from orkcraft.realm import town_presets
from orkcraft.widgets.road_layer import RoadClicked, split_key
from orkcraft.screens.dialogs import Confirm
from orkcraft.widgets.hud import Hud
from orkcraft.wm import Desktop, Window

from orkcraft.tui.base import (ACTIVE_COMMAND_KEYS, FocusState)


class FocusMixin:
    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action == "tab_cycle":
            return self.mode == "minimal"
        if action == "command_card":
            key = str(parameters[0]) if parameters else ""
            return key in ACTIVE_COMMAND_KEYS.get(self.focus_state.mode, set())
        if action == "custom_action":
            key = str(parameters[0]) if parameters else ""
            if self.focus_state.mode != "building" or not self.focus_state.building_id:
                return False
            spec = self.custom_specs.get(self.focus_state.building_id)
            if not spec:
                return False
            return any(a.get("key") == key for a in spec.get("actions", []))
        if action == "halt":
            if parameters and parameters[0] == "space":
                if self.focus_state.mode != "neutral":
                    return False
                focused = self.focused
                if focused is not None and getattr(focused, "can_focus", False):
                    if hasattr(focused, "value") or focused.__class__.__name__ in ("Input", "TextArea"):
                        return False
            return True
        if action == "new_orkspace":
            focused = self.focused
            if focused is not None and getattr(focused, "can_focus", False):
                if hasattr(focused, "value") or focused.__class__.__name__ in ("Input", "TextArea"):
                    return False
            return True
        return True

    def action_tab_cycle(self, step: int) -> None:
        self.desktop.cycle(step)

    def set_focus_state(
        self,
        mode: str,
        building_id: str | None = None,
        orc_key_val: str | None = None,
        road: str | None = None,
    ) -> None:
        if mode == "road" and road:
            self.focus_state = FocusState("road", building_id=split_key(road)[0], road_key=road)
        elif mode == "neutral":
            self.focus_state = FocusState("neutral", None, None)
        elif mode == "building":
            self.focus_state = FocusState("building", building_id=building_id, orc_key=None)
        elif mode == "unit":
            if not building_id and orc_key_val:
                orc = next((o for o in self.roster.orcs if orc_key(o) == orc_key_val), None)
                if orc and orc.building:
                    building_id = orc.building
            self.focus_state = FocusState("unit", building_id=building_id, orc_key=orc_key_val)
        if self.focus_state.mode != "road" and getattr(self, "_desktop", None) is not None:
            self._desktop.select_road(None)
        if hasattr(self, "_console") and self._console is not None:
            self._console.refresh_state(self.focus_state, self.roster)
            self.layout_console()
        self.refresh_bindings()  # check_action gates keys by state: the Footer must follow

    def action_escape(self) -> None:
        if getattr(self.desktop, "rally_mode", False):
            self.desktop.exit_rally_mode()
            return
        if self.focus_state.mode == "road" or (self.focus_state.mode == "unit" and self.focus_state.building_id
                                                and self.desktop.get_window(self.focus_state.building_id) is not None):
            # Back to the building: a garrison orc's inventory folds back into the garrison.
            self.set_focus_state("building", building_id=self.focus_state.building_id)
            return
        self.set_focus_state("neutral")
        self.desktop.set_active(None)
        if hasattr(self, "_console") and self._console is not None:
            self._console.focus_roster()

    def on_key(self, event: events.Key) -> None:
        if getattr(self.desktop, "rally_mode", False):
            if event.key in "123456789":
                self.rally_pick_number(int(event.key))
            else:
                self.desktop.exit_rally_mode()
            event.stop()
            event.prevent_default()

    def on_road_clicked(self, message: RoadClicked) -> None:
        self.select_road(message.key)

    def select_road(self, key: str) -> None:
        target_id, road_id = split_key(key)
        if self.scroll is None or scroll.find_road(self.scroll, road_id, target_id) is None:
            return
        self.desktop.select_road(key)
        self.set_focus_state("road", road=key)

    def on_desktop_canvas_clicked(self, message: Desktop.CanvasClicked) -> None:
        self.set_focus_state("neutral")
        self.desktop.set_active(None)
        if hasattr(self, "_console") and self._console is not None:
            self._console.focus_roster()

    def on_window_activated(self, message: Window.Activated) -> None:
        self.set_focus_state("building", building_id=message.window.window_id)
        if message.window.window_id == TOWN_HALL and getattr(self, "order_burning", False):
            town_presets.mark_order_seen(self.repo_root)      # opened: the order stops burning
            self.order_burning = False
            self.refresh_roster()
            order = town_presets.pending_order(self.repo_root)
            if order is not None:
                self.push_screen(Confirm("📜 A town waits to be raised. Plan it now?",
                                         f"“{order['prompt'][:800]}”\n\nThe Town Builder plans it from the "
                                         "building catalog (one Claude call); you approve the plan before "
                                         "anything is raised."),
                                 lambda yes: yes and self.build_town_from_order())

    def on_desktop_hut_selected(self, message: Desktop.HutSelected) -> None:
        self.set_focus_state("building", building_id=message.building_id)
        if hasattr(self, "_console") and self._console is not None:
            self._console.focus_roster()     # keys must not land in a building that just closed

    def on_clan_roster_building_selected(self, message: ClanRoster.BuildingSelected) -> None:
        w = self.desktop.get_window(message.building_id)
        if w is not None:
            self.desktop.focus_window(w)
        self.set_focus_state("building", building_id=message.building_id)

    def on_clan_roster_orc_selected(self, message: ClanRoster.OrcSelected) -> None:
        orc = next((o for o in self.roster.orcs if orc_key(o) == message.key), None)
        if orc is None:
            return
        if (self.focus_state.mode == "building" and orc.alert is not None
                and orc.building == self.focus_state.building_id):
            # A question in the selected building: show it, keep the building selected, drop its ❓.
            self.seen_alerts.add(orc.alert.id)
            self.open_alert(orc.alert, orc.name)
            if getattr(self, "_console", None) is not None:
                self._console.refresh_state(self.focus_state, self.roster)
            return
        self.set_focus_state("unit", orc_key_val=message.key, building_id=orc.building)
        if orc.alert is not None:
            self.open_alert(orc.alert, orc.name)

    def on_hud_menu_clicked(self, message: Hud.MenuClicked) -> None:
        self.action_system_menu()

    def on_hud_alerts_clicked(self, message: Hud.AlertsClicked) -> None:
        self.action_awaiting_orders()
