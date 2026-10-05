"""Delivery: what roads carry — payloads into buildings' views, handler results, carts on the map, the runs they report.

A part of `OrkcraftApp` (app.py): its methods run with the app as `self`.
"""
from __future__ import annotations

import json
import threading

from textual import events

from orkcraft import scroll
from orkcraft.core import bus, delivery
from orkcraft.realm import pipes, roads
from orkcraft.screens.custom_view import CustomBuildingView
from orkcraft.widgets.carts import CartClicked
from orkcraft.wm import Desktop


class DeliveryMixin:
    def on_desktop_payload_emitted(self, message: Desktop.PayloadEmitted) -> None:
        if not self._windows_alive():
            return
        payload = message.payload
        if self.scroll is None:
            return
        self.roads.emit(payload)

    def _show_demo_samples(self) -> None:
        from orkcraft.demo import SAMPLES
        try:
            data = json.loads((self.repo_root / SAMPLES).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        for bid, sample in data.items():
            view = self._custom_view(bid)
            if view is not None:
                view.show_incoming(sample.get("title", ""), sample.get("markdown", ""))

    def _spec_changed(self, building_id: str, spec: dict, refresh: bool = False) -> None:
        """A custom building's spec changed in the core (a revert, a retro): its view takes the new one
        (and reloads its data when `refresh`)."""
        view = self._custom_view(building_id)
        if view is not None:
            view.spec = spec
            reload = getattr(view, "refresh_data", None) if refresh else None
            if reload is not None:
                reload()

    def _ui_changed(self, building_id: str, doc: dict) -> None:
        """A building's UI document changed (a redesign, a revert): its view lays itself out again."""
        apply_ui = getattr(self._custom_view(building_id), "apply_ui", None)
        if apply_ui is not None:
            apply_ui(doc)

    def _custom_view(self, building_id: str):
        w = self.desktop.get_window(building_id)
        if w is None:
            return None
        try:
            return w.query_one(CustomBuildingView)
        except Exception:
            return None

    def return_for_rework(self, source_id: str, payload: pipes.Payload) -> str:
        """A Loot checkpoint or a Clan Fire sends a cart back to the building that made it — directly, not
        by a road (a road back would close a loop). The building that redoes delivered work (`TAKES_REWORK`:
        a Barracks queues the task again) is the source, else the latest one in the cart's trail (past a
        Signpost or a Mill on the way). Its id, or "" when nobody can take it back."""
        for bid in [source_id] + [h.building for h in reversed(payload.trail) if h.building != source_id]:
            if getattr(self._custom_view(bid), "TAKES_REWORK", False):
                self.deliver_payload(bid, payload, payload.title, payload.value)
                return bid
        return ""

    def return_approved(self, source_id: str, payload: pipes.Payload) -> str:
        """A Loot accepted a draft its maker holds back until approved (a Barracks ork's post to Jira…): the
        maker is told directly, like a rework. Its id, or "" when nobody waited for it."""
        for bid in [source_id] + [h.building for h in reversed(payload.trail) if h.building != source_id]:
            approved = getattr(self._custom_view(bid), "approved", None)
            if callable(approved) and approved(payload):
                return bid
        return ""

    def _loot_burning(self) -> list[str]:
        """Loot buildings with a cart waiting for the person (they burn like an orc waiting for orders)."""
        out = []
        for w in self.desktop.windows:
            view = self._custom_view(w.window_id)
            burning = getattr(view, "burning", None)
            if callable(burning) and burning():
                out.append(w.window_id)
        return out

    def _payload_markdown(self, payload: pipes.Payload) -> tuple[str, str]:
        """(title, markdown) of what a road carries, for a custom building's 📥 pane."""
        return delivery.markdown_of(self.core, payload)

    def on_paste(self, event: events.Paste) -> None:
        """A file dragged onto the terminal while a Drop Zone is selected is a drop."""
        bid = self.focus_state.building_id if self.focus_state.mode == "building" else None
        drop = getattr(self._custom_view(bid), "drop", None) if bid else None
        if drop is not None:
            event.stop()
            drop(event.text)

    def emit_typed(self, building_id: str, event_id: str, value: str, title: str = "",
                   trail: tuple = (), ref: str = "") -> bool:
        """A typed building sends one of its events (core/delivery.py)."""
        return self.core.emit_typed(building_id, event_id, value, title, trail, ref)

    def deliver_payload(self, target_id: str, payload: pipes.Payload, title: str = "", markdown: str = "") -> None:
        self.core.deliver(target_id, payload, title, markdown)

    def _call_on_ui(self, fn, *args) -> None:
        """Road engine callbacks come from agent threads too; Textual widgets live on the UI thread."""
        if threading.current_thread() is threading.main_thread() or not self.is_running:
            fn(*args)
            return
        try:
            self.call_from_thread(fn, *args)
        except RuntimeError:
            pass  # the app is shutting down

    def payload_meta(self, payload: pipes.Payload) -> dict:
        return delivery.meta(self.core, payload)

    def deliver_handler_output(self, target_id: str, orc: scroll.OrcSpec, title: str, markdown: str,
                               trail: tuple = (), ref: str = "") -> None:
        delivery.output(self.core, target_id, orc, title, markdown, trail, ref)

    def on_handler_run(self, run: roads.HandlerRun) -> None:
        delivery.ran(self.core, run)

    def on_cart_clicked(self, message: CartClicked) -> None:
        cart = message.cart
        payload = getattr(cart, "payload", None)
        what = "a failed run" if payload is None else (
            f"{payload.kind} {payload.title or payload.value[:80]}".strip())
        detail = f" — {cart.detail}" if getattr(cart, "detail", "") else ""
        self.notify(f"🛒 {cart.status}: {what}{detail}", title=f"Cart · {cart.source} → {cart.target}")

    # -- what the core publishes, drawn (core/bus.py) -------------------------------------------------

    def _wire_delivery(self) -> None:
        on = self.core.bus.subscribe
        on(bus.DELIVERED, lambda e: self._show_delivered(**e.data))
        on(bus.OUTPUT, lambda e: self._show_output(**e.data))
        on(bus.CART, lambda e: self._show_cart(e.data["cart"]))
        on(bus.RUN, lambda e: self._show_run(e.data["run"], e.data["name"]))
        on(bus.LOOT, lambda e: self._refresh_loot())
        on(bus.WORKER, lambda e: self._worker_changed(e.data["building"]))

    def _worker_changed(self, building_id: str) -> None:
        """A building's worker changed its state: its view draws it again."""
        redraw = getattr(self._custom_view(building_id), "redraw", None)
        if redraw is not None:
            redraw()

    def _show_delivered(self, building: str, payload: pipes.Payload, title: str, markdown: str, label: str,
                        worker: bool) -> None:
        """A cart arrived: the view notes it; a view whose type has no worker yet takes it itself."""
        view = self._custom_view(building)
        if view is None:
            return
        view.show_incoming(label, markdown, payload.trail, payload.ref)
        receive = None if worker else getattr(view, "receive", None)
        if receive is not None:
            receive(payload, title, markdown)

    def _show_output(self, building: str, orc: str, title: str, markdown: str, trail: tuple = (),
                     ref: str = "") -> None:
        if not self._windows_alive():
            return
        view = self._custom_view(building)
        if view is not None:
            view.show_incoming(title, markdown, tuple(trail), ref)

    def _show_cart(self, cart: roads.Cart) -> None:
        if self._windows_alive():
            self.desktop.traffic.launch(cart)

    def _show_run(self, run: roads.HandlerRun, name: str) -> None:
        if self._windows_alive():
            if run.outcome == "error":
                self.desktop.traffic.mark_error(run.target, list(run.roads))
            if run.cost_usd:
                self.desktop.traffic.flash_coin(run.target)
        if run.outcome == "error" and self.is_running:
            self.notify(f"{name}: {run.error}", title="Handler", severity="warning")

    def _refresh_loot(self) -> None:
        loot_win = self.desktop.get_window("loot") if self._windows_alive() else None
        if loot_win is None:
            return
        try:
            from orkcraft.screens.loot_view import LootView
            loot_win.query_one(LootView).refresh_view()
        except Exception:
            pass
