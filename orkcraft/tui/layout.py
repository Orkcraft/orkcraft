"""Layout: the responsive viewports, the console over the town, windows moved and resized by keys, the look (camp / office).

A part of `OrkcraftApp` (app.py): its methods run with the app as `self`.
"""
from __future__ import annotations

import datetime as dt

from textual import events

from orkcraft import scroll
from orkcraft.screens.console import Console, orc_key
from orkcraft.screens.orc_chat import OrcChat
from orkcraft.realm import modes
from orkcraft.widgets.office import OfficeStatic
from orkcraft.wm import Desktop

from orkcraft.tui.base import (ORC_CHAT_PCT, BUILDING_CONSOLE_MIN_H, WARMAP_FLOAT_W, mode_for)
from orkcraft.tui.text import office_rich


class LayoutMixin:
    def on_resize(self, event: events.Resize) -> None:
        mode = mode_for(event.size.width)
        if mode != self.mode:
            self._console_forced = None
        self.mode = mode
        self._apply_mode()

    def _apply_mode(self) -> None:
        console = self._console
        default_display = self.mode in ("full", "compact")
        console.display = self._console_forced if self._console_forced is not None else default_display
        self.desktop.set_single(self.mode == "minimal")
        self._hud.mode = self.mode
        self._taskbar.compact = self.mode != "full"
        self.on_desktop_layout_changed(None)
        self.layout_console()

    def action_toggle_console(self) -> None:
        console = self._console
        self._console_forced = not console.display
        self._apply_mode()

    def wear_mode(self) -> None:
        """The mode changed (camp ↔ office): everything outside the town follows it."""
        self._hud.update_hud()
        self._taskbar.refresh_items()
        self.refresh_bindings()                  # the footer recomposes in the mode's words
        for widget in self.query(OfficeStatic):
            widget.rewear()
        if getattr(self, "_console", None) is not None:
            self._console.refresh_state(self.focus_state, self.roster)

    def notify(self, message, *, title: str = "", **kwargs) -> None:  # type: ignore[override]
        if modes.office():                       # the office: its words and no emoji in the toasts too
            message = office_rich(message) if not isinstance(message, str) else modes.text(message)
            title = modes.text(title)
        super().notify(message, title=title, **kwargs)

    def _save_screenshot(self) -> None:
        now_str = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = f"orkcraft-{now_str}.svg"
        screenshot_dir = self.repo_root / "loot" / "screenshots"
        try:
            screenshot_dir.mkdir(parents=True, exist_ok=True)
            self.save_screenshot(filename=filename, path=str(screenshot_dir))
            self.notify(f"📸 loot/screenshots/{filename}", title="Screenshot")
        except OSError as e:
            self.notify(f"Screenshot failed: {e}", title="Screenshot", severity="error")

    def action_focus_number(self, number: int) -> None:
        if getattr(self.desktop, "rally_mode", False):
            self.rally_pick_number(number)
            return
        # The key of the building already in focus opens its resident orc's orders.
        w = next((x for x in self.desktop.windows if x.number == number and self.desktop.in_view(x)), None)
        selected = self.focus_state.mode != "neutral" and self.focus_state.building_id == getattr(w, "window_id", None)
        if w is not None and w is self.desktop.active and not w.hidden and selected:
            self.open_unit(w)
            return
        self.desktop.action_focus_number(number)
        if w is not None:
            self.set_focus_state("building", building_id=w.window_id)

    def action_cycle_window(self, step: int) -> None:
        self.desktop.cycle(step)

    def action_window_mode(self) -> None:
        self.desktop.enter_window_mode()

    def action_move_active(self, dx: int, dy: int) -> None:
        if self.desktop.active is not None:
            self.desktop.move_by(self.desktop.active, dx, dy)

    def action_resize_active(self, dw: int, dh: int) -> None:
        if self.desktop.active is not None:
            self.desktop.resize_by(self.desktop.active, dw, dh)

    def action_toggle_pin(self) -> None:
        w = self.desktop.active
        if w is not None:
            self.desktop.toggle_pin(w)
            self.notify(f"📌 {w.window_title} {'pinned' if w.pinned else 'unpinned'}", title="Windows")

    def action_toggle_terrain(self) -> None:
        self.desktop.toggle_terrain()

    def layout_console(self) -> None:
        """Town view: the console floats over the map's bottom edge. Calm (nothing
        selected) → the War Map alone, bottom left, and the Build button bottom right; a
        selection → the full console. The huts are laid out above the calm strip, which never
        changes with the selection, so the town does not move; the open building shrinks to stay
        clear of the full console. Tiles: the docked console of old."""
        console = getattr(self, "_console", None)
        if console is None or not console.is_attached:
            return
        desk = self.desktop
        town = desk.town_active
        width, height = self.size
        calm = self.focus_state.mode == "neutral"
        shown = bool(console.display)
        strip = len(self.scroll.orkspaces) + 3                     # border, title, one row each, footer
        full = max(strip, 6, round(console.height_pct * max(height - 2, 1) / 100))
        if self.focus_state.mode in ("building", "unit"):
            full = max(full, BUILDING_CONSOLE_MIN_H)    # Info's name, about, runs and roads all show
        orc = next((o for o in self.roster.orcs if orc_key(o) == self.focus_state.orc_key), None) \
            if self.focus_state.mode == "unit" else None
        chat = shown and OrcChat.supports(orc)
        chat_w = max(56, round(width * 0.32)) if chat else 0
        sig = (town, calm, shown, width, height, strip, full, chat, self.focus_state.orc_key)
        if sig == self._console_signature:
            return
        self._console_signature = sig
        self._orc_chat.display = chat
        if chat:
            chat_h = max(full, round(ORC_CHAT_PCT * max(height - 2, 1) / 100))
            self._orc_chat.styles.width, self._orc_chat.styles.height = chat_w, chat_h
            self._orc_chat.styles.offset = (max(width - chat_w, 0), max(height - 1 - chat_h, 0))
            self._orc_chat.show_orc(self.focus_state.orc_key)
        console.set_class(town, "-floating")
        console.set_class(town and calm, "-calm")
        self._taskbar.display = not town
        if not town:
            console.styles.offset = (0, 0)
            console.styles.width = max(width - chat_w, WARMAP_FLOAT_W + 22 + 20) if chat else "100%"
            console.styles.height = f"{console.height_pct}%"
            desk.set_reserves(0, 0, 0)
            return
        # A selected orc's chat stands at the right edge: the console ends where the chat begins.
        h, w = (strip, WARMAP_FLOAT_W) if calm else (full, max(width - chat_w, WARMAP_FLOAT_W + 22 + 20))
        console.styles.width, console.styles.height = w, h
        console.styles.offset = (0, max(height - 1 - h, 0))
        bottom = strip if shown else 0
        desk.set_reserves(bottom, (bottom if calm else full) if shown else 0, chat_w)

    def on_desktop_layout_changed(self, message: Desktop.LayoutChanged | None) -> None:
        self.layout_console()
        try:
            self._taskbar.refresh_items()
            self.refresh_rally_indicators()
            if hasattr(self, "_console") and self._console is not None:
                self._console.refresh_state(self.focus_state, self.roster)
        except Exception:
            pass

    def _windows_alive(self) -> bool:
        """False while the app shuts down: selection events can still arrive after the War Tent
        and the Scrying Spire are unmounted (a board refresh finishing during exit)."""
        return self._desktop.is_attached and bool(self._desktop.query("#chat-view"))

    def action_toggle_view(self) -> None:
        """alt+v: the town (huts, one building open) ↔ tiles (every window side by side)."""
        town = not self.desktop.town
        self.desktop.set_town(town)
        if town:
            self.desktop.refresh_huts()
        self.notify("🏘 Town: click a hut or press its number to open it, esc closes it" if town
                    else "🪟 Tiles: every building open side by side", title="View")

    def action_cycle_carts(self) -> None:
        order = list(scroll.CART_MODES)
        cur = self.scroll.preferences.get("carts", "selected")
        nxt = order[(order.index(cur) + 1) % len(order)] if cur in order else "selected"
        self.scroll.preferences["carts"] = nxt
        if nxt == "off":
            self.desktop.traffic.clear()
        self.desktop.save()
        label = {"off": "off", "selected": "the selected building's roads", "all": "all roads"}[nxt]
        self.notify(f"🛒 carts: {label}", title="Roads")

    def action_console_height(self, step: int) -> None:
        pct = self._console.set_height_pct(self._console.height_pct + step)
        self._store_console_height(pct)

    def on_console_resized(self, message: Console.Resized) -> None:
        self._store_console_height(message.pct)

    def _store_console_height(self, pct: int) -> None:
        self.scroll.preferences["console_height_pct"] = pct
        self.desktop.save()
