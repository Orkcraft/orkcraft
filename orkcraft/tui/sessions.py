"""Sessions: deploying a garrison ork, the ork's chat, the War Tent, Halt All.

A part of `OrkcraftApp` (app.py): its methods run with the app as `self`.
"""
from __future__ import annotations

from pathlib import Path

from orkcraft.realm import halt, chronicles, pipes
from orkcraft.realm.buildings import TOWN_HALL
from orkcraft.screens.town_hall import TownHallView
from orkcraft.sources.sessions import deploy_command
from orkcraft.widgets.terminal import Terminal
from orkcraft.wm import Desktop, Window

from orkcraft.tui.base import HALT_RESET_S


class SessionsMixin:
    def deploy_resident(self, orc, first_message: str = "", show_tent: bool = True) -> str | None:
        """C on a garrison orc (and the orc's chat line): its running session, else a new Claude
        session (Codex for an orc whose first step runs on it) with its orders — and, from the
        chat, the operator's first message."""
        b_id, orc_id = orc.ref.split("/", 1) if "/" in orc.ref else (orc.building or "", "")
        b_spec = self.scroll.building(b_id) if b_id else None
        m_spec = next((m for m in b_spec.garrison.members if m.id == orc_id), None) if b_spec else None
        b_title = b_spec.title if b_spec else (orc.building or "Building")
        term = self.chat.terminals.get(orc.session) if orc.session else None
        if term is not None and term.running:
            if first_message:
                term.write((first_message + "\r").encode())
            if show_tent:
                chat_win = self._sessions_window()
                if chat_win:
                    self.desktop.focus_window(chat_win)
                self.chat.show_terminal(orc.session)
            return orc.session
        if self.roster.active >= self.scroll.budget.supply_max_workers:
            self.notify(
                f"🥩 Supply {self.roster.active}/{self.scroll.budget.supply_max_workers}: build more farms first "
                "(stop a session with x in the War Tent)", title="Not enough food", severity="warning"
            )
            return None
        if self.gold_exhausted():
            return None
        orders_text = m_spec.orders if m_spec else orc.task
        prompt = f"You are {orc.name}, {orc.role}, a garrison orc of the {b_title} building in orkcraft."
        if orders_text:
            prompt += f" Orders: {orders_text}"
        if first_message:
            prompt += f"\n\nThe operator says: {first_message}"
        first = (m_spec.harness[0].get("harness") if m_spec and m_spec.harness else "") or "claude"
        harness = first if first == "codex" else "claude"      # agy has no deployment: its orcs deploy as Claude
        command = deploy_command(harness, prompt)
        if command is None:
            self.notify("agy deployment is not supported yet — open an agy session in the War Tent", title="Deploy",
                        severity="warning")
            return None
        chat_key = self.chat.deploy(f"deploy:{b_id}/{orc_id}", command, harness, f"{orc.name} · {b_title}",
                                    env={"ORKCRAFT_ORC": f"{b_id}/{orc_id}"})
        self.deployments[chat_key] = f"{b_id}/{orc_id}"
        try:
            chronicles.record(self.repo_root, self.scroll, b_id, "orc_deployed", orc=orc.name, harness=harness)
        except OSError:
            pass
        if show_tent:
            chat_win = self._sessions_window()
            if chat_win:
                self.desktop.focus_window(chat_win)
        self.refresh_roster()
        return chat_key

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

    def on_terminal_exited(self, event: Terminal.Exited) -> None:
        term = event.terminal
        chat = getattr(self, "chat", None)
        terminals = getattr(chat, "terminals", {}) if chat else {}
        term_key = next((k for k, t in terminals.items() if t is term), None)
        if not term_key or term_key not in self.deployments:
            return
        deployment_ref = self.deployments[term_key]
        if "/" not in deployment_ref:
            return
        b_id, orc_id = deployment_ref.split("/", 1)
        b_spec = self.scroll.building(b_id) if self.scroll is not None else None
        m_spec = next((m for m in b_spec.garrison.members if m.id == orc_id), None) if b_spec else None
        orc_name = m_spec.name if m_spec else orc_id
        try:
            chronicles.record(self.repo_root, self.scroll, b_id, "orc_returned", orc=orc_name, by=orc_name)
        except OSError:
            pass
        if b_spec is None or not self.roads.has_roads(b_id, pipes.ON_TASK):
            return
        title, md = pipes.task_report(orc_name, b_spec.title, term.text_lines())
        cwd = Path(getattr(term, "cwd", None) or self.repo_root)
        worktree = str(cwd.relative_to(self.repo_root)) if cwd != self.repo_root and self.repo_root in cwd.parents else ""
        hop = pipes.hop(b_id, orc_id, "task", worktree=worktree, outcome="done")
        payload = pipes.Payload(kind=pipes.TEXT, value=md, source=b_id, mode=pipes.ON_TASK, title=title, trail=(hop,))
        self.roads.emit(payload)

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
        halted = self.chat.interrupt_all()
        killed = halt.halt_all()                        # every agent, script, test and browser process
        for worker in self.workers:
            if worker.group.startswith("orkcraft-agent"):
                worker.cancel()
        stopped = 0
        for b_spec in self.scroll.buildings:          # what buildings run themselves: they stop and hold their queues
            stop = getattr(self._custom_view(b_spec.id), "halt", None)
            if callable(stop):
                stopped += int(stop() or 0)
        halted += max(killed, stopped)
        hud = self._hud
        hud.set_halt(f"HALTED — {halted} stopped")
        self.notify(f"🛑 Halt All: {halted} running session{'s' if halted != 1 else ''} interrupted",
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
