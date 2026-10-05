"""Commands: the F10 menu, the Command Card's keys, quick actions, custom building actions, refresh and quit.

A part of `OrkcraftApp` (app.py): its methods run with the app as `self`.
"""
from __future__ import annotations

from orkcraft import scroll
from orkcraft.scroll import OrcSpec
from orkcraft.realm import audit, fastpath, catalog, chronicles, pipes
from orkcraft.realm.buildings import BUILTIN_SPECS, TOWN_HALL
from orkcraft.realm.orcs import WORKER, RESIDENT
from orkcraft.screens.settings_modal import SettingsModal
from orkcraft.screens.console import orc_key
from orkcraft.screens.chronicles_view import BuildingChronicles, UnitChronicles
from orkcraft.screens.custom_view import CustomBuildingView
from orkcraft.screens.presets_modal import PresetsModal
from orkcraft.screens.garrison_modal import GarrisonModal
from orkcraft.screens.town_hall import TownHallView
from orkcraft import settings
from orkcraft.screens.road_modal import _PickModal
from orkcraft.widgets.road_layer import road_key
from orkcraft.screens.system_menu import (
    KeysCheatSheet,
    QuitConfirm,
    SystemMenu,
)


class CommandsMixin:
    def action_system_menu(self) -> None:
        if isinstance(self.screen, SystemMenu):
            self.screen.dismiss(None)
            return

        def done(action: str | None) -> None:
            if not action:
                return
            if action == "halt":
                self.action_halt()
            elif action == "screenshot":
                self.call_after_refresh(self._save_screenshot)
            elif action == "keys":
                self.push_screen(KeysCheatSheet())
            elif action in settings.MODES:
                self.desktop.set_mode(action)
                self.refresh_hud()
                self.notify({"camp": "the town of orks, fire and gold", "office": "hidden — frames, people and plain words",
                             "shift": "Office in office hours, Camp otherwise — F10 → 🕰 Your day"}[action],
                            title=settings.MODE_TITLES[action])
            elif action == "day":
                self.open_day()
            elif action == "autonomy":
                self.open_autonomy()
            elif action == "changes":
                self.show_changes()
            elif action == "terrain":
                self.action_toggle_terrain()
            elif action == "save":
                if self.desktop.save():
                    self.notify("💾 Town Scroll saved", title="Town Scroll")
                else:
                    self.notify("Town Scroll not saved", title="Town Scroll", severity="warning")
            elif action == "audit":
                self.run_audit()
            elif action == "cleanup":
                self.cleanup()
            elif action == "settings":
                self.open_settings()
            elif action == "improve":
                self.open_proposals()
            elif action == "weekly":
                self.open_weekly()
            elif action == "town_order":
                self.build_town_from_order()
            elif action == "onboarding":
                self.start_onboarding(machine_steps=True, town_step=False)
            elif action == "quit":
                self.action_graceful_quit()

        self.push_screen(SystemMenu(self.desktop.mode), done)

    def action_command_card(self, key: str) -> None:
        mode = self.focus_state.mode
        if mode == "neutral":
            if key == "B":
                self.action_build_menu()
            elif key == "P":
                self.action_presets_catalog()
            elif key == "S":
                self.action_spawn_orc()
            elif key == "T":
                self.action_toggle_terrain()
            elif key == "G":
                self.action_worktree()
        elif mode == "building":
            b_id = self.focus_state.building_id
            w = self.desktop.get_window(b_id) if b_id else self.desktop.active
            if key == "R":
                spec = self.scroll.building(b_id) if b_id else None
                b_title = spec.title if spec else "Building"

                def done(orc: OrcSpec | str | None) -> None:
                    if isinstance(orc, str):
                        self.recruit_from_prompt(b_id, orc)
                        return
                    if orc is not None:
                        self.desktop.save()
                        self.refresh_roster()
                        try:
                            chronicles.record(self.repo_root, self.scroll, b_id, "orc_recruited", orc=orc.name)
                        except OSError:
                            pass
                        self.notify(f"🧌 {orc.name} joined the {b_title} garrison", title="Garrison")

                self.push_screen(GarrisonModal(b_title, b_id), done)
            elif key == "L":
                b_id = self.focus_state.building_id or (self.desktop.active.window_id if self.desktop.active else "forge")
                self.push_screen(BuildingChronicles(self.repo_root, self.scroll, b_id))
            elif key == "Y":
                target_id = b_id or (self.desktop.active.window_id if self.desktop.active else None)
                if target_id:
                    sources = {w.window_id for w in self.desktop.windows
                               if self.desktop.in_view(w) and not w.hidden
                               and (self._road_choices(w.window_id, target_id) or self._rule_choices(w.window_id, target_id))}
                    self.desktop.enter_rally_mode(target_id, candidates=sources)
                    # The taskbar status is squeezed out by the window tabs on common widths.
                    tgt = self.scroll.building(target_id)
                    self.notify("click the source building (or press its number) · any other key cancels",
                                title=f"🛤 Road into {tgt.title if tgt else target_id}")
            elif key == "U":
                target_id = b_id or (self.desktop.active.window_id if self.desktop.active else None)
                spec = self.scroll.building(target_id) if target_id else None
                if spec is not None:
                    if not spec.roads:
                        self.notify("no incoming roads", title="Roads")
                    elif len(spec.roads) > 1:
                        self.notify("select a road first — click it or its gate", title="Roads")
                    else:
                        self.remove_road(road_key(spec.id, spec.roads[0].id))
            elif key == "P":
                if w is not None:
                    self.desktop.toggle_pin(w)
                    self.notify(f"📌 {w.window_title} {'pinned' if w.pinned else 'unpinned'}", title="Windows")
            elif key == "M":
                if w is not None:
                    self.desktop.focus_window(w)
                self.desktop.enter_window_mode()
            elif key == "X":
                if w is not None:
                    self.desktop.hide(w)
                    self.desktop.save()
                self.set_focus_state("neutral")
                self.desktop.set_active(None)
                if hasattr(self, "_console") and self._console is not None:
                    self._console.focus_roster()
            elif key == "Z":
                if b_id:
                    self.revert_by_you(b_id)
            elif key == "K":
                if b_id:
                    self.like_building(b_id)
            elif key == "F":
                if b_id:
                    self.dislike_building(b_id)
            elif key == "D":
                if b_id:
                    self.redesign_building(b_id)
            elif b_id and any(a.get("key") == key for a in self.custom_specs.get(b_id, {}).get("actions", [])):
                self.action_custom_action(key)
        elif mode == "road":
            road = self.focus_state.road_key
            if road and key == "U":
                self.remove_road(road)
            elif road and key == "H":
                self.change_road_handler(road)
        elif mode == "unit":
            if key == "W":
                orc = next((o for o in self.roster.orcs if orc_key(o) == self.focus_state.orc_key), None)
                if orc is not None and orc.category == RESIDENT and orc.lead and orc.building:
                    self.watch_building(orc.building, interactive=True)
                else:
                    self.notify("W is the steward's: select a building's ★ ork", title="Steward")
                return
            orc_k = self.focus_state.orc_key
            orc = next((o for o in self.roster.orcs if orc_key(o) == orc_k), None) if orc_k else None
            if orc is None:
                return
            if orc.category == RESIDENT:
                b_id, orc_id = orc.ref.split("/", 1) if "/" in orc.ref else (orc.building or "", "")
                b_spec = self.scroll.building(b_id) if b_id else None
                m_spec = next((m for m in b_spec.garrison.members if m.id == orc_id), None) if b_spec else None
                b_title = b_spec.title if b_spec else (orc.building or "Building")
                w = self.desktop.get_window(b_id) if b_id else None

                if key == "C":
                    self.deploy_resident(orc)
                elif key == "T":
                    if w is not None and m_spec is not None:
                        self.open_unit(w, member=m_spec)
                    else:
                        self.notify(f"{orc.name}: no window or spec found", title="⚡ Triggers")
                elif key == "D":
                    term = self.chat.terminals.get(orc.session) if orc.session else None
                    if term is not None and term.running:
                        self.notify("halt it first", title="Dismiss", severity="warning")
                        return
                    try:
                        scroll.dismiss_orc(self.scroll, b_id, orc_id)
                    except ValueError as e:
                        self.notify(str(e), title="Dismiss", severity="warning")
                        return
                    self.desktop.save()
                    self.set_focus_state("building", building_id=b_id)
                    self.refresh_roster()
                    try:
                        chronicles.record(self.repo_root, self.scroll, b_id, "orc_dismissed", orc=orc.name)
                    except OSError:
                        pass
                elif key == "H":
                    term = self.chat.terminals.get(orc.session) if orc.session else None
                    if term is not None and term.running:
                        term.interrupt()
                        try:
                            chronicles.record(self.repo_root, self.scroll, b_id, "orc_halted", orc=orc.name)
                        except OSError:
                            pass
                        self.notify(f"🛑 Halted {orc.name}", title="Halt")
                    else:
                        self.notify("nothing to halt", title="Halt")
                elif key == "L":
                    self.push_screen(UnitChronicles(orc, self.repo_root))
            else:
                w = self.desktop.get_window(orc.building) if orc.building else None
                if key == "C":
                    if orc.category == WORKER:
                        chat_win = self._sessions_window()
                        if chat_win:
                            self.desktop.focus_window(chat_win)
                        self.chat.show_terminal(orc.ref)
                    else:
                        self.notify(f"{orc.name}: no terminal or window", title="🧌 Unit")
                elif key == "L":
                    self.push_screen(UnitChronicles(orc, self.repo_root))
                elif key == "T":
                    self.notify(f"{orc.name}: triggers only for residents", title="⚡ Triggers")
                elif key == "H":
                    if orc.category == WORKER and orc.ref in getattr(self.chat, "terminals", {}):
                        self.chat.terminals[orc.ref].interrupt()
                        if orc.building:
                            try:
                                chronicles.record(self.repo_root, self.scroll, orc.building, "orc_halted", orc=orc.name)
                            except OSError:
                                pass
                        self.notify(f"🛑 Halted {orc.name}", title="Halt")
                    else:
                        self.notify("nothing to halt", title="Halt")
                elif key == "D":
                    self.notify("Dismiss is only for garrison members", title="Dismiss")

    def action_custom_action(self, key: str) -> None:
        if self.focus_state.mode != "building" or not self.focus_state.building_id:
            return
        spec = self.custom_specs.get(self.focus_state.building_id)
        if not spec:
            return
        action_item = next((a for a in spec.get("actions", []) if a.get("key") == key), None)
        if not action_item:
            return
        action_type = action_item.get("action")

        w = self.desktop.get_window(self.focus_state.building_id)
        custom_view = None
        if w is not None:
            try:
                custom_view = w.query_one(CustomBuildingView)
            except Exception:
                custom_view = None

        node_id = custom_view.get_selected_node() if custom_view else None

        if action_type == "node:open":
            self.notify("node detail view is not available")
        elif action_type == "node:chat":
            if not node_id:
                self.notify("select a node first")
                return
            self.open_chat(node_id)
        elif action_type == "node:preview":
            self.notify("preview view is not available")
        elif action_type == "building:refresh":
            if custom_view:
                custom_view.refresh_data()
            self.notify("Building data reloaded", title="Refresh")

    def action_presets_catalog(self) -> None:
        numbers = {w.window_id: w.number for w in self.desktop.windows if self.desktop.in_view(w)}

        def done(building_id: str | None) -> None:
            if not building_id:
                return
            if building_id.startswith("type:"):
                self.preset_params(building_id[5:])
                return
            active_id = self.scroll.active_orkspace_id
            spec = self.scroll.building(building_id)
            cur_ork = self.scroll.orkspace_of(building_id)
            raised = cur_ork is None or (spec is not None and spec.demolished)
            moved = (not raised) and (cur_ork is not None and cur_ork.id != active_id)

            if raised or moved:
                scroll.move_building(self.scroll, building_id, active_id)
                self.desktop.apply_orkspace(active_id)
                self.desktop.save()
                active_ork = self.scroll.orkspace(active_id)
                ork_name = active_ork.name if active_ork else active_id
                try:
                    ev_type = "building_raised" if raised else "building_moved"
                    chronicles.record(self.repo_root, self.scroll, building_id, ev_type, orkspace=ork_name)
                except OSError:
                    pass

            w = self.desktop.get_window(building_id)
            if w is not None:
                self.desktop.focus_window(w)
                self.set_focus_state("building", building_id=building_id)

        self.push_screen(PresetsModal(self.buildings, self.scroll, numbers), done)

    def spec_of(self, building_id: str | None) -> dict | None:
        """A building's spec: a custom one's file, or the catalog type a built-in wears."""
        if not building_id:
            return None
        return self.custom_specs.get(building_id) or BUILTIN_SPECS.get(building_id)

    def action_quick_action(self, index: int) -> None:
        """`[` / `]`: the selected building's first / second quick action."""
        b_id = self.focus_state.building_id if self.focus_state.mode == "building" else None
        actions = catalog.quick_actions_of(self.spec_of(b_id)) if b_id else []
        if index < len(actions):
            self.run_quick_action(b_id, actions[index].id)

    def run_quick_action(self, building_id: str, action_id: str) -> None:
        """A hut button or `[` / `]`. Each type's view brings its own handler (`quick_action`);
        until it lands the operator is told so, never left with a silent button."""
        spec = self.spec_of(building_id)
        t = catalog.type_of(spec)
        act = t.action(action_id)
        if act is None:
            return
        w = self.desktop.get_window(building_id)
        view = next(iter(w.children), None) if w is not None else None
        handler = getattr(view, "quick_action", None)
        if handler is not None and handler(action_id):
            return
        self.notify(f"{act.glyph} {act.label}: arrives with the {t.title} view", title=f"{t.icon} {spec.get('title', building_id) if spec else building_id}")

    def run_audit(self) -> None:
        """🔍 Audit: the hall's three agents look over the town (rules, no model call)."""
        report = audit.run(self.repo_root, self.scroll, dict(self.custom_specs), self.snapshot.spent_usd,
                           self.scroll.budget.gold_session_limit_usd)
        try:
            audit.save(self.repo_root, report)
        except OSError:
            pass
        w = self.desktop.get_window(TOWN_HALL)
        view = next(iter(w.query(TownHallView)), None) if w is not None else None
        if view is not None:
            view.refresh_hall(report)
            view.show_tab("hall")
        if scroll.has_outgoing(self.scroll, TOWN_HALL, "hall.audit_done"):
            self.roads.emit(pipes.Payload(pipes.TEXT, report.markdown(), TOWN_HALL, "hall.audit_done", "Audit"))
        serious = sum(f.severity != "info" for f in report.findings)
        self.notify(f"{report.summary()}" + (f" — {serious} to look at" if serious else ""), title="🔍 Audit")

    def action_build_menu(self) -> None:
        """One way to build: raise a preset (built-in or saved) or describe a new one."""
        def done(choice: str | None) -> None:
            if choice == "preset":
                self.action_presets_catalog()
            elif choice == "scratch":
                self.action_build_scratch()
            elif choice == "new":
                self.action_build_wizard()

        self.push_screen(_PickModal("🏗 Build", [
            ("preset", "📜 From presets — pick what you need, name it, place it"),
            ("scratch", "🛠 From scratch — the Builder asks, writes a script, tests it in a sandbox"),
            ("new", "✨ A camp building the Foreman prefills from a description"),
        ], "Enter picks · Esc cancels"), done)

    def restart_app(self) -> None:
        """Save everything and start again (the CLI runs the app anew on "restart")."""
        self.desktop.save()
        self.exit(result="restart")

    def open_settings(self) -> None:
        """F10 → ⚙: the retros' models and schedules (`.orkcraft/council/settings.json`)."""
        def done(values: dict | None) -> None:
            if values:
                fastpath.save_settings(self.repo_root, values)
                self.notify("saved", title="⚙ Retro settings")

        self.push_screen(SettingsModal(fastpath.settings(self.repo_root)), done)

    def action_toggle_commit(self) -> None:
        self.config.auto_commit = not self.config.auto_commit
        self.refresh_roster()
        status_str = "ENABLED" if self.config.auto_commit else "DISABLED"
        self.notify(f"§10 per-action git commits are now {status_str}", title="Auto-Commit Setting")

    def action_refresh_graph(self) -> None:
        for w in self.desktop.windows:
            for view in w.children:
                refresh = getattr(view, "refresh_view", None)
                if refresh is not None:
                    try:
                        refresh()
                    except Exception as e:  # one broken source must not block the others
                        self.notify(f"{w.window_title}: {e}", severity="error")
        self.refresh_roster()
        self.notify("Data reloaded from disk", title="Refresh")

    def action_show_help(self) -> None:
        self.push_screen(KeysCheatSheet())

    def action_graceful_quit(self) -> None:
        chat = getattr(self, "chat", None)
        terminals = getattr(chat, "terminals", {}) if chat else {}
        running = [t for t in terminals.values() if getattr(t, "running", False)]
        if not running:
            try:
                self.desktop.save()
            except Exception:
                pass
            self.exit(0)
            return

        def done(confirmed: bool | None) -> None:
            if confirmed:
                try:
                    self.desktop.save()
                except Exception:
                    pass
                chat_obj = getattr(self, "chat", None)
                terms = getattr(chat_obj, "terminals", {}) if chat_obj else {}
                for t in terms.values():
                    if getattr(t, "running", False):
                        try:
                            t.stop()
                        except Exception:
                            pass
                self.exit(0)

        self.push_screen(QuitConfirm(len(running)), done)

    def action_quit(self) -> None:
        self.action_graceful_quit()
