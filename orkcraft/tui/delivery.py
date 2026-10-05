"""Delivery: what roads carry — payloads into buildings' views, handler results, carts on the map, the runs they report.

A part of `OrkcraftApp` (app.py): its methods run with the app as `self`.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path

from textual import events

from orkcraft import scroll
from orkcraft.realm import feedback, metrics, catalog, chronicles, pipes, roads
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
        if payload.kind == pipes.FILE:
            return pipes.read_file_payload(self.repo_root, payload.value)
        return payload.title or "report", payload.value

    def on_paste(self, event: events.Paste) -> None:
        """A file dragged onto the terminal while a Drop Zone is selected is a drop."""
        bid = self.focus_state.building_id if self.focus_state.mode == "building" else None
        drop = getattr(self._custom_view(bid), "drop", None) if bid else None
        if drop is not None:
            event.stop()
            drop(event.text)

    def emit_typed(self, building_id: str, event_id: str, value: str, title: str = "",
                   trail: tuple = (), ref: str = "") -> bool:
        """A typed building sends one of its events: only when a road carries it (with the trail of
        what it passes on, when it gives one)."""
        spec = self.custom_specs.get(building_id)
        ev = catalog.type_of(spec).event(event_id) if spec else None
        if ev is not None:
            feedback.record_output(self.repo_root, building_id, event_id, value)      # what 👍 / 👎 rate
        if ev is None or self.scroll is None or not scroll.has_outgoing(self.scroll, building_id, event_id):
            return False
        self.roads.emit(pipes.Payload(ev.kind, value, building_id, event_id, title, tuple(trail), ref))
        return True

    def deliver_payload(self, target_id: str, payload: pipes.Payload, title: str = "", markdown: str = "") -> None:
        feedback.record_delivery(self.repo_root, target_id, payload.source)            # the session's graph
        view = self._custom_view(target_id)
        if view is not None:
            t, md = (title, markdown) if markdown else self._payload_markdown(payload)
            src = self.scroll.building(payload.source) if self.scroll is not None else None
            view.show_incoming(f"{src.title if src else payload.source} → {t}", md, payload.trail, payload.ref)
            receive = getattr(view, "receive", None)
            if receive is not None:
                receive(payload, t, md)
        if target_id == "loot":
            if payload.kind == pipes.TEXT:
                t = title or payload.title
                md = markdown or payload.value
                path = pipes.write_loot(self.repo_root, payload.source, t, md)
                loot_win = self.desktop.get_window("loot")
                if loot_win is not None:
                    try:
                        from orkcraft.screens.loot_view import LootView
                        loot_view = loot_win.query_one(LootView)
                        loot_view.refresh_view()
                    except Exception:
                        pass
                self.notify(f"📦 report saved: loot/pipes/{path.name}", title="Loot")
        try:
            src_spec = self.scroll.building(payload.source) if self.scroll is not None else None
            src_title = src_spec.title if src_spec and src_spec.title else payload.source
            chronicles.record(self.repo_root, self.scroll, target_id, "payload_received",
                              kind=payload.kind, source=src_title)
        except OSError:
            pass

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
        """Type / status / subtype of the Markdown item a payload names (the source filter and the
        personal guard). Only the showcase sandbox indexes items; elsewhere the dict is empty and road
        filters on node_type / node_status do not match."""
        if self.graph is None:
            return {}
        ident = payload.value if payload.kind == pipes.NODE else ""
        if payload.kind == pipes.FILE and payload.value.endswith(".md"):
            ident = Path(payload.value).stem
        entity = self.graph.get_entity(ident) if ident else None
        if entity is None:
            return {}
        return {"type": entity.type, "status": entity.status, "title": entity.title,
                "subtype": "personal" if entity.is_personal else entity.subtype}

    def deliver_handler_output(self, target_id: str, orc: scroll.OrcSpec, title: str, markdown: str,
                               trail: tuple = (), ref: str = "") -> None:
        """A handler's result: shown by a receiver that renders text, otherwise kept as a Loot report.
        `trail` is every hop the result went through, the handler's own last."""
        if not self._windows_alive():
            return
        view = self._custom_view(target_id)
        if view is not None:
            view.show_incoming(title, markdown, tuple(trail), ref)
        else:
            path = pipes.write_loot(self.repo_root, target_id, title, markdown)
            self.notify(f"📦 {title}: loot/pipes/{path.name}", title="Handler")

    def on_road_cart(self, cart: roads.Cart) -> None:
        if self._windows_alive():
            self.desktop.traffic.launch(cart)

    def on_cart_clicked(self, message: CartClicked) -> None:
        cart = message.cart
        payload = getattr(cart, "payload", None)
        what = "a failed run" if payload is None else (
            f"{payload.kind} {payload.title or payload.value[:80]}".strip())
        detail = f" — {cart.detail}" if getattr(cart, "detail", "") else ""
        self.notify(f"🛒 {cart.status}: {what}{detail}", title=f"Cart · {cart.source} → {cart.target}")

    def on_handler_run(self, run: roads.HandlerRun) -> None:
        if run.outcome in ("done", "error"):         # every run of the camp, for the Tally Crag
            try:
                metrics.record_run(self.repo_root, run.target, run.outcome, run.cost_usd, run.tokens)
            except OSError:
                pass
        if self._windows_alive():
            if run.outcome == "error":
                self.desktop.traffic.mark_error(run.target, list(run.roads))
            if run.cost_usd:
                self.desktop.traffic.flash_coin(run.target)
        b_spec = self.scroll.building(run.target) if self.scroll is not None else None
        orc = b_spec.garrison.orc(run.orc_id) if b_spec else None
        name = orc.name if orc else run.orc_id
        try:
            chronicles.record(self.repo_root, self.scroll, run.target, "handler_ran", by=name, orc=name,
                              outcome=run.outcome, roads=len(run.roads))
        except OSError:
            pass
        if run.outcome == "error" and self.is_running:
            self.notify(f"{name}: {run.error}", title="Handler", severity="warning")
