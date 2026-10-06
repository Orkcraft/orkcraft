"""The desktop's layout: placing windows, the orkspace canvases and their Town Scroll, the biome and terrain.

A part of `Desktop` (desktop.py): its methods run with the desktop as `self`.
"""
from __future__ import annotations

from textual import events

from orkcraft import scroll, theme
from orkcraft.realm.buildings import TOWN_HALL
from orkcraft.wm import geometry as geo
from orkcraft.wm.geometry import SNAP_SLOTS, Frac, Geom
from orkcraft.wm.window import Window


class LayoutMixin:
    """Layout, orkspaces, saving, biome and terrain."""

    # -- layout ----------------------------------------------------------------

    def on_resize(self, event: events.Resize) -> None:
        width, height = self.dims
        if width <= 0 or height <= 0:
            return
        if not self._laid_out:
            self._laid_out = True
            if self.scroll is not None:
                self.apply_orkspace(self.scroll.active_orkspace_id)
                # Write the v2 scroll at once: a first start and a migrated v1 file land on disk.
                self.save()
            else:
                self.apply_default_layout()
            return
        for w in self.windows:
            if w.frac is not None:
                w.apply_geom(geo.frac_to_geom(w.frac, width, height), w.frac)
            else:
                w.apply_geom(geo.clamp(w.geom, width, height), None)
        self._apply_single()
        self.sync_huts()
        self._apply_town()
        self.replan_roads()

    def place(self, w: Window, frac: Frac) -> None:
        w.apply_geom(geo.frac_to_geom(frac, *self.dims), frac)

    def apply_default_layout(self) -> None:
        width, height = self.dims
        defaults = geo.default_fracs()
        active_buildings = (
            set(self.scroll.active_orkspace.buildings)
            if self.scroll is not None
            else {w.window_id for w in self.windows}
        )
        for w in self.windows:
            if w.window_id not in active_buildings:
                continue
            frac = defaults.get(w.window_id, SNAP_SLOTS["center"])
            w.display = frac is not None
            if w.pinned:
                continue  # a pinned window keeps its slot even through a reset
            w.set_restore(None)
            self.place(w, frac or SNAP_SLOTS["center"])
        self.preview_linked = True
        self.solid_black = False
        self.remove_class("-solid-black")
        if self.scroll is not None:
            self.set_biome(self.scroll.active_orkspace.biome)
        else:
            self.set_biome(theme.DEFAULT_BIOME)
        first = self.get_window(self.home_id) if self.in_view(self.get_window(self.home_id)) else None
        if first is None:
            first = self._top_visible()
        if self.scroll is not None:
            for b in self.scroll.buildings_in(self.scroll.active_orkspace_id):
                b.hut = None   # the town is laid out again too
        self.sync_huts()
        if self.town_active:
            first = None   # the town starts with every building collapsed
        if first is not None:
            self.focus_window(first)
        else:
            self.set_active(None)
        self.post_message(self.LayoutChanged())

    def renumber_orkspace(self, orkspace_id: str) -> None:
        if self.scroll is None:
            return
        ork = self.scroll.orkspace(orkspace_id)
        if ork is None:
            return
        for n, bid in enumerate(ork.buildings, 1):
            w = self.get_window(bid)
            if w is not None:
                w.set_number(n)
        other_n = len(ork.buildings) + 1
        for w in self.windows:
            if w.window_id not in ork.buildings:
                w.set_number(other_n)
                other_n += 1

    def apply_orkspace(self, orkspace_id: str) -> None:
        if self.scroll is None:
            return
        ork = self.scroll.orkspace(orkspace_id)
        if ork is None:
            return
        self.renumber_orkspace(orkspace_id)
        width, height = self.dims
        defaults = geo.default_fracs()
        for w in self.windows:
            if w.window_id in ork.buildings or w.window_id == TOWN_HALL:
                spec = self.scroll.building(w.window_id)
                demolished = spec.demolished if spec is not None else False
                if spec is not None and spec.frac is not None:
                    frac = tuple(float(v) for v in spec.frac)
                    if len(frac) == 4 and width > 0 and height > 0:
                        w.apply_geom(geo.frac_to_geom(frac, width, height), frac)
                elif spec is not None and spec.bounds is not None:
                    b = spec.bounds
                    g = Geom(int(b.get("x", 0)), int(b.get("y", 0)), int(b.get("width", 40)), int(b.get("height", 12)))
                    if width > 0 and height > 0:
                        w.apply_geom(geo.clamp(g, width, height), None)
                else:
                    slot = defaults.get(w.window_id)
                    if slot is None:
                        if spec is None or spec.preset_ref.startswith("custom:"):
                            slot = SNAP_SLOTS["center"]
                        else:
                            demolished = True
                            slot = SNAP_SLOTS["center"]
                    if width > 0 and height > 0:
                        self.place(w, slot)
                w.set_restore(None)
                w.display = not demolished
                if spec is not None:
                    w.set_pinned(bool(spec.pinned))
            else:
                w.display = False

        for window_id in ork.window_order:
            w = self.get_window(window_id)
            if w is not None and w.window_id in ork.buildings:
                self.raise_window(w)

        self.solid_black = bool(self.scroll.preferences.get("terrain_solid_black", False))
        if self.solid_black:
            self.add_class("-solid-black")
        else:
            self.remove_class("-solid-black")
        self.set_biome(ork.biome)
        self._wear_mode()
        self.preview_linked = bool(self.scroll.preferences.get("preview_linked", True))

        active = None
        if ork.active_building:
            target = self.get_window(ork.active_building)
            if target is not None and target.window_id in ork.buildings and not target.hidden:
                active = target
        self.sync_huts()
        if active is None and not self.town_active:
            # Fresh canvas (no stored active window): the home building, as the default layout does.
            home = self.get_window(self.home_id)
            if home is not None and home.window_id in ork.buildings and not home.hidden:
                active = home
            if active is None:
                active = self._top_visible()
        if active is not None:
            self.focus_window(active)
        else:
            self.set_active(None)
        self._apply_town()   # windows were just placed in their tile slots

        self.replan_roads()
        self.post_message(self.LayoutChanged())

    def capture(self) -> None:
        if self.scroll is None or not self._laid_out:
            return   # before the first layout every window still shows: nothing true to record
        active_ork = self.scroll.active_orkspace
        if active_ork is None:
            return
        for bid in active_ork.buildings:
            w = self.get_window(bid)
            spec = self.scroll.building(bid)
            if w is None or spec is None:
                continue
            g, frac = w.restore if w.restore is not None else (w.geom, w.frac)
            spec.bounds = {"x": g.x, "y": g.y, "width": g.w, "height": g.h}
            spec.frac = list(frac) if frac is not None else None
            spec.pinned = bool(w.pinned)
            spec.demolished = bool(w.hidden)
            hut = self.huts.get(bid)
            if hut is not None and hut.display and self.dims[0] > 0:
                spec.hut = list(geo.hut_to_frac(hut.geom.x, hut.geom.y, *self.hut_room, hut.geom.w, hut.geom.h))
        active_ork.window_order = [w.window_id for w in self.windows if w.window_id in active_ork.buildings]
        active_ork.active_building = (
            self.active.window_id
            if self.active is not None and self.active.window_id in active_ork.buildings and not self.active.hidden
            else None
        )
        active_ork.biome = self.biome
        self.scroll.preferences["preview_linked"] = bool(self.preview_linked)
        self.scroll.preferences["terrain_solid_black"] = bool(self.solid_black)

    def save(self) -> bool:
        if self.scroll_path is None or not self._laid_out or not self.windows or self.scroll is None:
            return False
        self.capture()
        problems = scroll.save(self.scroll_path, self.scroll)
        if problems:
            self.app.notify("\n".join(problems), title="Town Scroll Save Refused", severity="error")
            return False
        return True

    def switch_orkspace(self, orkspace_id: str) -> None:
        if self.scroll is None or self.scroll.active_orkspace_id == orkspace_id:
            return
        if self.scroll.orkspace(orkspace_id) is None:
            return
        self.capture()
        self.scroll.active_orkspace_id = orkspace_id
        self.apply_orkspace(orkspace_id)
        self.save()
        self.post_message(self.OrkspaceChanged(orkspace_id))

    # -- biome & terrain ---------------------------------------------------------

    @property
    def look(self) -> theme.Biome:
        """What the canvas wears: the orkspace's biome, or the office's black and grey in the office mode."""
        return theme.OFFICE if self.plain else theme.BIOMES.get(self.biome, theme.BIOMES[theme.DEFAULT_BIOME])

    def set_biome(self, name: str) -> None:
        """Switch desktop biome. Unknown names fall back to DEFAULT_BIOME. The office mode keeps it but
        wears the office look (the biome comes back with the camp)."""
        if name not in theme.BIOMES:
            name = theme.DEFAULT_BIOME
        self.biome = name
        self._paint()

    def _paint(self) -> None:
        look = self.look
        for b in theme.LOOKS:
            self.remove_class(f"biome-{b}")
        self.add_class(f"biome-{look.name}")
        self.styles.background = theme.SOLID_BLACK if self.solid_black else look.canvas
        if hasattr(self, "terrain"):
            self.terrain.set_biome(look, self.solid_black)

    def toggle_terrain(self) -> None:
        """Toggle solid black canvas on/off and save layout."""
        self.solid_black = not self.solid_black
        if self.solid_black:
            self.add_class("-solid-black")
        else:
            self.remove_class("-solid-black")
        self._paint()
        self.save()
