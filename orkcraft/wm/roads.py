"""Roads on the desktop: planning and drawing them, their traffic, and rally mode.

A part of `Desktop` (desktop.py): its methods run with the desktop as `self`.
"""
from __future__ import annotations

from textual import events

from orkcraft import scroll
from orkcraft.realm import pipes
from orkcraft.widgets.carts import FPS as CART_FPS
from orkcraft.widgets.road_layer import (ENTRY_GLYPH, EXIT_GLYPH, ROAD_SELECTED, RoadGate, RoadLabel, RoadRun,
                                         road_key, runs)
from orkcraft.wm import roadmap
from orkcraft.wm.geometry import Geom


class RoadsMixin:
    """Roads, traffic and rally mode."""

    # -- roads -------------------------------------------------------------------

    def replan_roads(self) -> None:
        """Re-plan the roads after the current refresh (at most once per refresh)."""
        if self._replan_pending or not self.is_attached:
            return
        self._replan_pending = True
        self.call_after_refresh(self._replan_now)

    def select_road(self, key: str | None) -> None:
        if key != self.selected_road:
            self.selected_road = key
            self._render_roads()

    def _visible_geoms(self) -> dict[str, Geom]:
        if self.single:
            return {}
        if self.town_active:   # roads join the huts, so expanding a building never moves them
            return {bid: h.geom for bid, h in self.huts.items() if h.display}
        return {w.window_id: w.geom for w in self.windows if self.in_view(w) and not w.hidden}

    def _replan_now(self) -> None:
        self._replan_pending = False
        if not self.is_attached or self.scroll is None:
            return
        width, height = self.dims
        geoms = self._visible_geoms()
        roads = [(road_key(b.id, r.id), r.source, b.id) for b in self.scroll.buildings for r in b.roads
                 if b.id in geoms and r.source in geoms]
        anchors = {bid: h.body_geom for bid, h in self.huts.items() if bid in geoms} if self.town_active else None
        self.road_paths = roadmap.plan(geoms, roads, width, height, anchors) if roads else {}
        if self.selected_road is not None and self.selected_road not in self.road_paths:
            self.selected_road = None
        self._render_roads()
        self.traffic.replaced()

    def _road_label(self, key: str) -> str:
        from orkcraft.widgets.road_layer import split_key
        target_id, road_id = split_key(key)
        if self.scroll is None:
            return key
        found = scroll.find_road(self.scroll, road_id, target_id)
        if found is None:
            return key
        target, road = found
        src = self.scroll.building(road.source)
        orc = target.garrison.handler(road.handler) if road.handler else None
        who = f"{orc.avatar} {orc.name}" if orc else "plain"
        src_label = f"{src.icon} {src.title}".strip() if src else road.source
        signal = f" ({road.label})" if road.label else ""
        return f"{who} · {src_label} → {f'{target.icon} {target.title}'.strip()}{signal}"

    def _render_roads(self) -> None:
        """Gap cells to the Terrain, gates and the selected road to the `roads` layer."""
        if not self.is_attached:
            return
        mode = self.scroll.preferences.get("roads", "faint") if self.scroll is not None else "faint"
        focus = self.active.window_id if self.active is not None and not self.active.hidden else None
        cells: dict[tuple[int, int], tuple[str, str]] = {}
        for key, p in self.road_paths.items():
            selected = key == self.selected_road
            bright = selected or (focus is not None and focus in (p.source, p.target))
            if mode == "off" and not bright:
                continue
            for x, y, ch in p.glyphs:
                if (x, y) not in p.covered:
                    cells[(x, y)] = (ch, "selected" if selected else "bright" if bright else "faint")
        self.terrain.set_roads(cells)
        biome = self.look
        signature = (tuple(sorted((k, p.exit, p.entry, tuple(p.cells)) for k, p in self.road_paths.items())),
                     self.selected_road, biome.name, self._handler_keys())
        if signature == self._road_signature:
            return
        self._road_signature = signature
        for piece in list(self.query(".road-gate, .road-run, .road-label")):
            piece.remove()
        pieces = []
        handled = self._handler_keys()
        for key, p in self.road_paths.items():
            colour = biome.border_focus if key in handled else biome.border
            gate_style = f"bold {colour} on {biome.window_bg}"
            pieces.append(RoadGate(key, EXIT_GLYPH[p.exit.side], p.exit.x, p.exit.y, gate_style))
            pieces.append(RoadGate(key, ENTRY_GLYPH, p.entry.x, p.entry.y, gate_style))
        p = self.road_paths.get(self.selected_road) if self.selected_road else None
        if p is not None:
            style = f"bold {ROAD_SELECTED} on {biome.canvas}"
            covered = [c for c in p.glyphs if (c[0], c[1]) in p.covered]
            for run in runs(covered):
                pieces.append(RoadRun(p.road_id, run, style))
            label = self._road_label(p.road_id)
            mx, my, _ = p.glyphs[len(p.glyphs) // 2] if p.glyphs else (p.exit.x, p.exit.y, "")
            width = self.dims[0]
            lx = max(0, min(mx - (len(label) + 2) // 2, width - len(label) - 2))
            ly = my - 1 if my > 0 else my + 1
            pieces.append(RoadLabel(p.road_id, label, lx, ly, f"bold #1a1206 on {ROAD_SELECTED}"))
        if pieces:
            self.mount_all(pieces)

    def traffic_changed(self) -> None:
        """Carts or coins appeared: run the 8 fps timer only while something moves."""
        if self._traffic_timer is None:
            self._traffic_timer = self.set_interval(1 / CART_FPS, self._traffic_tick)
        else:
            self._traffic_timer.resume()

    def _traffic_tick(self) -> None:
        self.traffic.tick()
        if not self.traffic.busy and self._traffic_timer is not None:
            self._traffic_timer.pause()

    def _handler_keys(self) -> frozenset[str]:
        if self.scroll is None:
            return frozenset()
        return frozenset(road_key(b.id, r.id) for b in self.scroll.buildings for r in b.roads if r.handler)

    # -- rally mode --------------------------------------------------------------

    def enter_rally_mode(self, anchor_id: str, candidates: set[str] | None = None) -> None:
        """Pick a window by its number. `candidates` are highlighted (default: the rally-pipe
        targets of `anchor_id`); `Y` passes the possible road sources of the receiver."""
        self.rally_mode = True
        self.rally_source = anchor_id
        for w in self.windows:
            if self.in_view(w) and w.window_id != anchor_id:
                ok = (w.window_id in candidates) if candidates is not None else bool(pipes.modes_for(anchor_id, w.window_id))
                w.set_class(ok, "-rally-target")
            else:
                w.remove_class("-rally-target")
            if (hut := self.huts.get(w.window_id)) is not None:
                hut.set_class(w.has_class("-rally-target"), "-rally-target")
        self.can_focus = True
        self.focus()
        self.post_message(self.LayoutChanged())

    def exit_rally_mode(self) -> None:
        if not self.rally_mode:
            return
        self.rally_mode = False
        self.rally_source = None
        for w in self.windows:
            w.remove_class("-rally-target")
        for hut in self.huts.values():
            hut.remove_class("-rally-target")
        self.can_focus = False
        if self.active is not None and not self.active.hidden:
            self.focus_window(self.active)
        self.post_message(self.LayoutChanged())

    def on_key(self, event: events.Key) -> None:
        if self.rally_mode:
            app = self.app
            if event.key in "123456789":
                if hasattr(app, "rally_pick_number"):
                    app.rally_pick_number(int(event.key))
            else:
                self.exit_rally_mode()
            event.stop()
            event.prevent_default()
