"""Orkspaces (F1–F8): switching and creating them, the questions waiting on arrival, their git worktrees.

A part of `OrkcraftApp` (app.py): its methods run with the app as `self`.
"""
from __future__ import annotations

from pathlib import Path

from orkcraft import scroll
from orkcraft.realm.orcs import Orc
from orkcraft.screens.console import orc_key
from orkcraft.screens.orkspace_modal import OrkspaceModal
from orkcraft.screens.orders import AwaitingOrdersModal
from orkcraft.realm import worktrees
from orkcraft.screens.worktree_modal import WorktreeModal
from orkcraft.wm import Desktop


class OrkspacesMixin:
    def action_orkspace(self, hotkey: str) -> None:
        ork = scroll.orkspace_by_hotkey(self.scroll, hotkey)
        if ork is None:
            self.notify(f"No orkspace on {hotkey} — N creates one", title="Orkspaces")
            return
        self.desktop.switch_orkspace(ork.id)

    def action_new_orkspace(self) -> None:
        def done(orkspace_id: str | None) -> None:
            if orkspace_id:
                self.desktop.switch_orkspace(orkspace_id)
                self.set_focus_state("neutral")
        self.push_screen(OrkspaceModal(self.scroll), done)

    def on_desktop_orkspace_changed(self, message: Desktop.OrkspaceChanged) -> None:
        self.set_focus_state("neutral")
        self.desktop.set_active(None)
        self.refresh_roster()
        self.refresh_rally_indicators()
        try:
            self._taskbar.refresh_items()
        except Exception:
            pass
        if hasattr(self, "_console") and self._console is not None:
            self._console.refresh_state(self.focus_state, self.roster)
            visible = [w for w in self.desktop.windows if self.desktop.in_view(w) and not w.hidden]
            if not visible:
                self._console.focus_roster()
        self.questions_on_arrival(message.orkspace_id)

    def questions_of(self, orkspace_id: str) -> list[Orc]:
        """The orcs of an orkspace's buildings that wait for an answer, the longest waiting first."""
        self._note_alerts()
        asking = [o for o in self.roster.orcs if o.alert is not None and o.building
                  and (ork := self.scroll.orkspace_of(o.building)) is not None and ork.id == orkspace_id]
        return sorted(asking, key=lambda o: self.alert_first_seen.get(o.alert.id, float("inf")))   # stable

    def questions_on_arrival(self, orkspace_id: str) -> None:
        """Arriving on an orkspace with questions: the first one opens at once, its building and its orc
        selected behind it (the others wait in the same dialog, ↑↓)."""
        if len(self.screen_stack) > 1:                 # the operator is busy in a dialog
            return
        asking = self.questions_of(orkspace_id)
        if not asking:
            return
        first = asking[0]
        self.desktop.select_hut(first.building)
        self.set_focus_state("unit", orc_key_val=orc_key(first), building_id=first.building)
        self.seen_alerts.update(o.alert.id for o in asking if o.alert is not None)
        self.push_screen(AwaitingOrdersModal([o.alert for o in asking if o.alert is not None],
                                             {o.alert.id: o.name for o in asking if o.alert is not None}))

    def session_cwd(self) -> Path:
        """Where new War Tent sessions run: the active orkspace's worktree, else the repository."""
        return worktrees.cwd_for(self.scroll, self.scroll.active_orkspace_id, self.repo_root)

    def action_worktree(self) -> None:
        ork = self.scroll.active_orkspace
        if ork.git.enabled and ork.git.mode == "root":
            self.notify(f"{ork.name} works in the repository itself — create another orkspace (N) for a worktree",
                        title="⎇ Worktree")
            return

        def done(changed: bool | None) -> None:
            if changed:
                self.desktop.save()
                self.refresh_worktree_marks()
                g = self.scroll.active_orkspace.git
                self.notify(f"⎇ {ork.name}: " + (f"{g.branch} in {g.path}" if g.enabled else "no worktree"),
                            title="Worktree")
                self.refresh_roster()

        self.push_screen(WorktreeModal(self.scroll, self.repo_root, ork.id), done)

    def refresh_worktree_marks(self) -> None:
        """War Map marks: `⎇ branch` (+ `*` when there is uncommitted work, `?` when the folder is gone)."""
        marks: dict[str, str] = {}
        for ork in self.scroll.orkspaces:
            if not (ork.git.enabled and ork.git.mode == "worktree"):
                continue
            path = (self.repo_root / ork.git.path).resolve()
            if self.demo:   # the sandbox describes worktrees, it does not create them
                marks[ork.id] = f"⎇ {ork.git.branch}"
                continue
            try:
                st = worktrees.status(path)
                marks[ork.id] = f"⎇ {ork.git.branch}{'*' if st.dirty else ''}"
            except (worktrees.WorktreeError, OSError, Exception):
                marks[ork.id] = f"⎇ {ork.git.branch}?"
        self.worktree_marks = marks
