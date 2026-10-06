"""Sessions: deploying a garrison ork, the ork's chat, the War Tent, Halt All.

A part of `OrkcraftApp` (app.py): its methods run with the app as `self`.
"""
from __future__ import annotations


from orkcraft.realm import halt
from orkcraft.realm.buildings import TOWN_HALL
from orkcraft.screens.town_hall import TownHallView
from orkcraft.wm import Desktop, Window

from orkcraft.tui.base import HALT_RESET_S


class SessionsMixin:
    def deploy_resident(self, orc, first_message: str = "", show_tent: bool = True) -> str | None:
        """C on a garrison orc (and the orc's chat line): its running session, else a new Claude
        session (Codex for an orc whose first step runs on it) with its orders — and, from the
        chat, the operator's first message. The session is the core's (core/sessions.py)."""
        ref = orc.ref if "/" in orc.ref else f"{orc.building or ''}/"
        try:
            key = self.tent.deploy(ref, self.muster, self.treasury, first_message, ticket=self.chat.node_id)
        except ValueError as e:
            self.notify(str(e), title="Deploy", severity="warning")
            return None
        if key is None:
            return None
        self.chat.show_session(key)
        if show_tent:
            chat_win = self._sessions_window()
            if chat_win:
                self.desktop.focus_window(chat_win)
            self.chat.show_terminal(key)
        self.refresh_roster()
        return key

    def resume_for_orc(self, orc, session) -> None:
        """An earlier session of the orc, reopened in the War Tent and bound to the orc again."""
        self.chat.open_session(session)
        if session.key in self.chat.terminals and orc.ref:
            self.deployments[session.key] = orc.ref
        self.refresh_roster()

    def action_focus_orc_chat(self) -> None:
        if self._orc_chat.display:
            self._orc_chat.query_one("#orc-chat-input").focus()

    def _tick_orc_chat(self) -> None:
        if getattr(self, "_orc_chat", None) is not None and self._orc_chat.display:
            self._orc_chat.refresh_chat()

    def _sessions_window(self) -> Window | None:
        """The live sessions (the War Tent of old) live in the Town Hall's Sessions tab."""
        w = self.desktop.get_window(TOWN_HALL)
        view = next(iter(w.query(TownHallView)), None) if w is not None else None
        if view is not None:
            view.show_tab("sessions")
        return w

    def on_desktop_node_highlighted(self, message: Desktop.NodeHighlighted) -> None:
        if not self._windows_alive():
            return
        self.selected_node = message.node_id
        self.chat.set_node(message.node_id)

    def _session_output(self, key: str, data: bytes) -> None:
        """A session printed something: its terminal draws it (the core calls on the UI thread)."""
        term = getattr(getattr(self, "chat", None), "terminals", {}).get(key)
        if term is not None:
            term.output()

    def _session_changed(self, event) -> None:
        """A session ended: its terminal says so (a deployed ork's report is the core's)."""
        if event.data.get("state") != "exited":
            return
        try:
            term = self.chat.terminals.get(event.data["key"])
        except Exception:          # the War Tent is gone: the app is closing
            return
        if term is not None:
            term.finished(event.data.get("code"))

    def action_spawn_orc(self) -> None:
        """A new Claude session in the War Tent, tied to the selected node."""
        w = self._sessions_window()
        if w is None:
            return
        if self.roster.active >= self.scroll.budget.supply_max_workers:
            self.notify(f"🥩 Supply {self.roster.active}/{self.scroll.budget.supply_max_workers}: build more farms first "
                        "(stop a session with x in the War Tent)", title="Not enough food", severity="warning")
            return
        if self.gold_exhausted():
            return
        self.desktop.focus_window(w)
        self.chat.set_node(self.selected_node)
        self.chat.action_new_session("claude")

    def action_halt(self, source: str = "") -> None:
        """Emergency freeze: everything the camp runs stops — War Tent sessions, road agents, the
        buildings' own work (orcs, reviews, the librarian, scripts, tests, browsers) and every model
        call; queues wait. The TUI stays open."""
        sessions = self.tent.interrupt_all()           # every session the core runs (core/sessions.py)
        killed = halt.halt_all()                        # every agent, script, test and browser process
        for worker in self.workers:                     # the terminals this face runs agents in
            if worker.group.startswith("orkcraft-agent"):
                worker.cancel()
        buildings = self.core.halt()                    # the road handlers and every building's worker
        stopped = sessions + max(killed, buildings)
        hud = self._hud
        hud.set_halt(f"HALTED — {stopped} stopped")
        parts = [f"{n} {one if n == 1 else many} {done}" for n, one, many, done in
                 ((sessions, "session", "sessions", "interrupted"), (killed, "process", "processes", "killed"),
                  (buildings, "building", "buildings", "stopped")) if n]
        self.notify("🛑 Halt All: " + (", ".join(parts) if parts else "nothing was running"),
                    title="Emergency freeze", severity="warning")
        self.set_timer(HALT_RESET_S, lambda: hud.set_halt("READY"))

    def open_chat(self, node_id: str | None = None) -> None:
        """Show the War Tent with the node's latest session (or a new one)."""
        node_id = node_id or self.selected_node
        w = self._sessions_window()
        if w is not None:
            self.desktop.focus_window(w)
        if node_id:
            self.chat.open_for_node(node_id)

    def open_session(self, session) -> None:
        w = self._sessions_window()
        if w is not None:
            self.desktop.focus_window(w)
        self.chat.open_session(session)

    def action_open_chat(self) -> None:
        self.open_chat()
