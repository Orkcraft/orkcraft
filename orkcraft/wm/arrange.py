"""Arranging windows: minimal (single window) mode, pin, snap, move, resize, tile, hide, and window mode with its keys.

A part of `Desktop` (desktop.py): its methods run with the desktop as `self`.
"""
from __future__ import annotations

from orkcraft.realm import chronicles
from orkcraft.wm import geometry as geo
from orkcraft.wm.geometry import SNAP_SLOTS
from orkcraft.wm.window import Window

MOVE_STEP_X = 2
MOVE_STEP_Y = 1


class ArrangeMixin:
    """Window operations and the window-mode bindings' actions."""

    # -- minimal (single window) mode ----------------------------------------------

    def set_single(self, on: bool) -> None:
        if on == self.single:
            return
        self.single = on
        if not on:
            for w in self.windows:
                if not self.in_view(w):
                    continue
                w.styles.visibility = "visible"
                w.title_width = None
                w.apply_geom(w.geom, w.frac)  # back to the stored slot
                w._update_title()
        self._apply_single()
        self.sync_huts()
        self._apply_town()

    def _apply_single(self) -> None:
        """Show only the active window over the whole desktop; stored geometry is untouched."""
        if not self.single:
            return
        width, height = self.dims
        for w in self.windows:
            if not self.in_view(w):
                continue
            w.remove_class("-town-open")
            if w is self.active:
                w.styles.visibility = "visible"
                w.styles.offset = (0, 0)
                w.styles.width, w.styles.height = width, height
                if w.title_width != width:
                    w.title_width = width
                    w._update_title()
            else:
                w.styles.visibility = "hidden"
        self.replan_roads()

    # -- window operations -------------------------------------------------------

    def _refuse_pinned(self, w: Window) -> bool:
        if self.town_active:
            self.app.notify("Town view: the building opens in its place — alt+v switches to tiles to arrange windows",
                            title="Windows")
            return True
        if w.pinned:
            self.app.notify(f"📌 {w.window_title} is pinned — alt+b unpins it", title="Windows")
        return w.pinned

    def toggle_pin(self, w: Window) -> None:
        w.set_pinned(not w.pinned)
        self.save()
        self.post_message(self.LayoutChanged())
        try:
            repo_root = getattr(self.app, "repo_root", None)
            if repo_root is not None:
                ev_type = "pinned" if w.pinned else "unpinned"
                chronicles.record(repo_root, self.scroll, w.window_id, ev_type)
        except OSError:
            pass

    def snap(self, w: Window, slot: str) -> None:
        if self._refuse_pinned(w):
            return
        w.set_restore(None)
        self.place(w, SNAP_SLOTS[slot])

    def move_by(self, w: Window, dx: int, dy: int) -> None:
        if self._refuse_pinned(w):
            return
        w.set_restore(None)
        w.apply_geom(geo.move(w.geom, dx * MOVE_STEP_X, dy * MOVE_STEP_Y, *self.dims), None)

    def resize_by(self, w: Window, dw: int, dh: int) -> None:
        if self._refuse_pinned(w):
            return
        w.set_restore(None)
        w.apply_geom(geo.resize(w.geom, dw * MOVE_STEP_X, dh * MOVE_STEP_Y, *self.dims), None)

    def toggle_maximize(self, w: Window) -> None:
        if self._refuse_pinned(w):
            return
        if w.restore is not None:
            g, frac = w.restore
            w.set_restore(None)
            if frac is not None:
                self.place(w, frac)
            else:
                w.apply_geom(geo.clamp(g, *self.dims), None)
        else:
            w.set_restore((w.geom, w.frac))
            self.place(w, SNAP_SLOTS["max"])
            self.raise_window(w)

    def tile(self) -> None:
        if self.town_active:
            self.set_town(False)
            return
        visible = [w for w in self.by_number() if self.in_view(w) and not w.hidden and not w.pinned]
        for w, frac in zip(visible, geo.tile_fracs(len(visible))):
            w.set_restore(None)
            self.place(w, frac)

    def hide(self, w: Window) -> None:
        if w.hidden:
            return
        w.display = False
        self.sync_huts()
        self.replan_roads()
        if w is self.active:
            nxt = None if self.town_active else self._top_visible()
            self.set_active(None)
            if nxt is not None:
                self.focus_window(nxt)
        self.post_message(self.LayoutChanged())
        try:
            repo_root = getattr(self.app, "repo_root", None)
            if repo_root is not None:
                chronicles.record(repo_root, self.scroll, w.window_id, "building_demolished")
        except OSError:
            pass

    def cycle(self, step: int) -> None:
        visible = [w for w in self.by_number() if self.in_view(w) and not w.hidden]
        if not visible:
            return
        idx = visible.index(self.active) if self.active in visible else -step
        self.focus_window(visible[(idx + step) % len(visible)])

    def toggle_window(self, w: Window) -> None:
        """Taskbar click: focus a background window, hide the active one."""
        if not self.in_view(w):
            self.focus_window(w)
            return
        if w is self.active and not w.hidden:
            self.hide(w)
        else:
            self.focus_window(w)

    def add_window(self, window: Window) -> None:
        """Mount a newly raised custom building window and register it with the taskbar."""
        from orkcraft.wm.desktop import Taskbar, TaskbarItem   # desktop.py imports this module
        self.window_list.append(window)
        self.mount(window)
        self.place(window, SNAP_SLOTS["center"])
        if self.scroll is not None:
            self.renumber_orkspace(self.scroll.active_orkspace_id)
        self.sync_huts()
        try:
            taskbar = self.app.query_one(Taskbar)
            status_item = taskbar.query_one("#taskbar-status")
            taskbar.mount(TaskbarItem(window, classes="taskbar-item"), before=status_item)
            taskbar.refresh_items()
        except Exception:
            pass
        self.focus_window(window)
        self.post_message(self.LayoutChanged())

    # -- window mode -------------------------------------------------------------

    def enter_window_mode(self) -> None:
        if self.window_mode:
            return
        self._mode_return_focus = self.app.focused
        self.window_mode = True
        self.can_focus = True
        self.add_class("-window-mode")
        if self.active is None:
            top = self._top_visible()
            if top is not None:
                self.set_active(top)
        self.focus()
        self.refresh_bindings()
        self.post_message(self.LayoutChanged())

    def exit_window_mode(self) -> None:
        if not self.window_mode:
            return
        self.window_mode = False
        self.remove_class("-window-mode")
        self.can_focus = False
        self.save()
        if self.active is not None and not self.active.hidden:
            self.focus_window(self.active)
        elif self._mode_return_focus is not None and self._mode_return_focus.is_attached:
            self._mode_return_focus.focus()
        self._mode_return_focus = None
        self.refresh_bindings()
        self.post_message(self.LayoutChanged())


    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        # Every desktop binding is a window-mode binding.
        return self.window_mode

    def _need_active(self) -> Window | None:
        if self.active is None or self.active.hidden:
            return None
        return self.active

    def action_exit_window_mode(self) -> None:
        self.exit_window_mode()

    def action_nudge(self, dx: int, dy: int) -> None:
        if (w := self._need_active()) is not None:
            self.move_by(w, dx, dy)

    def action_grow(self, dw: int, dh: int) -> None:
        if (w := self._need_active()) is not None:
            self.resize_by(w, dw, dh)

    def action_snap(self, slot: str) -> None:
        if (w := self._need_active()) is not None:
            self.snap(w, slot)

    def action_toggle_maximize(self) -> None:
        if (w := self._need_active()) is not None:
            self.toggle_maximize(w)

    def action_tile(self) -> None:
        self.tile()

    def action_hide_window(self) -> None:
        if (w := self._need_active()) is not None:
            self.hide(w)

    def action_cycle(self, step: int) -> None:
        self.cycle(step)

    def action_focus_number(self, number: int) -> None:
        for w in self.windows:
            if w.number == number and self.in_view(w):
                self.focus_window(w)
                return

    def action_toggle_link(self) -> None:
        self.preview_linked = not self.preview_linked
        state = "linked to the selection" if self.preview_linked else "pinned"
        self.app.notify(f"Preview is {state}", title="Windows")
        self.post_message(self.LayoutChanged())

    def action_save_layout(self) -> None:
        ok = self.save()
        self.app.notify(
            f"Scroll saved to {self.scroll_path}" if ok else "Scroll could not be saved",
            title="Town Scroll",
            severity="information" if ok else "error",
        )

    def action_reset_layout(self) -> None:
        self.apply_default_layout()
        self.save()
