"""The town view: every building a hut, the active one open over the map, and the ghost of a building being placed.

A part of `Desktop` (desktop.py): its methods run with the desktop as `self`.
"""
from __future__ import annotations

from orkcraft import schedule, settings
from orkcraft.realm import catalog, modes
from orkcraft.realm.buildings import TOWN_HALL
from orkcraft.tui import silhouettes
from orkcraft.widgets.ghost import Ghost
from orkcraft.widgets.hut import Hut
from orkcraft.wm import geometry as geo
from orkcraft.wm.geometry import Geom
from orkcraft.wm.window import Window


class TownViewMixin:
    """Town view, huts and the ghost."""

    # -- town view ----------------------------------------------------------

    @property
    def town_active(self) -> bool:
        """Huts on the map: the town view, unless Minimal mode shows one window full size."""
        return self.town and not self.single and self.scroll is not None

    def anchor_geom(self, building_id: str) -> Geom | None:
        """Where a building sits on the map: its hut in the town view, else its window."""
        if self.town_active:
            hut = self.huts.get(building_id)
            return hut.geom if hut is not None and hut.display else None
        w = self.get_window(building_id)
        return w.geom if w is not None and not w.hidden and self.in_view(w) else None

    @property
    def mode(self) -> str:
        """🧌 camp · 👔 office · 🧌/👔 shift: the project's `preferences.mode` over the machine's (settings.py)."""
        pref = self.scroll.preferences.get("mode") if self.scroll is not None else None
        return settings.mode_of(pref) or self.machine.mode

    @property
    def look_mode(self) -> str:
        """What the town looks like now (realm/modes.py): office when the buildings are frames —
        Office, or Shift in office hours — else the camp."""
        return modes.OFFICE if self.plain else modes.CAMP

    def _wear_mode(self) -> None:
        """Every widget draws the current look (the HUD, the carts, the badges read `modes.current`)."""
        modes.set_current(self.look_mode)
        self.set_class(self.plain, "-office")
        self._paint()
        for w in self.windows:
            w.refresh_badge()

    @property
    def plain(self) -> bool:
        """Huts are only frames now: Office, or Shift in office hours; else they wear their ASCII."""
        if getattr(self, "machine", None) is None:          # still being built
            return False
        return schedule.plain_now(self.machine, mode=self.mode)

    @property
    def quiet(self) -> bool:
        """🌙 Do-not-disturb hours: fires do not flicker, a waiting orc shows ❓."""
        return getattr(self, "machine", None) is not None and schedule.quiet_now(self.machine)

    def set_mode(self, mode: str | bool) -> None:
        """Set the machine's mode (F10; True / False: office / camp); the project's override is
        dropped so the choice shows here too."""
        if isinstance(mode, bool):
            mode = "office" if mode else "camp"
        if self.scroll is None or (mode == self.machine.mode and "mode" not in self.scroll.preferences):
            return
        self.machine.mode = mode
        settings.save(self.machine)
        self.scroll.preferences.pop("mode", None)
        self.save()
        self.apply_schedule(force=True)

    def apply_schedule(self, force: bool = False) -> None:
        """Bring the town to the hour: the look (Shift turns Office on and off by itself) and the quiet."""
        plain, quiet = self.plain, self.quiet
        if force or (plain != (modes.current() == modes.OFFICE)):
            self._wear_mode()
            for hut in self.huts.values():
                if hut.set_plain(plain) and hut.display:
                    self._settle(hut)
            self.refresh_huts()
            self.replan_roads()
            self.traffic.restyle()
            dress = getattr(self.app, "wear_mode", None)
            if dress is not None:
                dress()                 # the HUD, the footer, the console and the taskbar
            self.post_message(self.LayoutChanged())
        for hut in self.huts.values():
            hut.set_quiet(quiet)
        if quiet:
            for hut in self.huts.values():
                hut.remove_class("-flame")

    def set_town(self, on: bool) -> None:
        if on == self.town:
            return
        self.town = on
        if self.scroll is not None:
            self.scroll.preferences["view"] = "town" if on else "tiles"
        self.sync_huts()
        self._apply_town()
        if not on and self.active is None:
            top = self._top_visible()
            if top is not None:
                self.focus_window(top)
        self.replan_roads()
        self.save()
        self.post_message(self.LayoutChanged())

    def set_reserves(self, hut: int, open_: int, right: int = 0) -> None:
        if (hut, open_, right) == (self.hut_reserve, self.open_reserve, self.open_right):
            return
        moved = hut != self.hut_reserve
        if moved:
            self.capture()                   # spots as fractions of the old room
        self.hut_reserve, self.open_reserve, self.open_right = hut, open_, right
        if moved:
            self.sync_huts()
            self.replan_roads()
        self._apply_town()

    @property
    def hut_room(self) -> tuple[int, int]:
        """The part of the canvas the huts live in: all of it but the floating console's strip."""
        width, height = self.dims
        return width, max(height - self.hut_reserve, 1)

    def sync_huts(self) -> None:
        """One hut per shown building of this canvas, at its spot; the rest are hidden."""
        if not self.is_attached:
            return
        width, height = self.hut_room
        on = self.town_active and self.dims[0] > 0 and self.dims[1] > 0
        wanted = [w for w in self.by_number() if self.in_view(w) and not w.hidden] if on else []
        ids = {w.window_id for w in wanted}
        for bid, hut in self.huts.items():
            if bid not in ids:
                hut.display = False
        placed: list[Geom] = []
        new: list[tuple[Window, Hut]] = []
        for w in wanted:
            hut = self.huts.get(w.window_id)
            spec = self.app.spec_of(w.window_id) if hasattr(self.app, "spec_of") else None
            sil, actions = silhouettes.of(spec, w.window_id), catalog.quick_actions_of(spec) if spec else []
            if hut is None:
                hut = Hut(w.window_id, sil, actions)
                self.huts[w.window_id] = hut
                self.mount(hut, after=self.terrain)
            hut.display = True
            hut.plain = self.plain
            hut.quiet = self.quiet
            hut.set_silhouette(sil, actions)
            hut.set_title(w.number, w.window_title)
            hut.set_badge(w.badge)
            hut.set_class(w is self.active, "-expanded")
            hw, hh = hut.geom.w, hut.geom.h
            if w.window_id == TOWN_HALL:     # fixed in the bottom-right corner, on the very bottom of the screen
                hut.fixed = True
                hut.place(Geom(max(width - hw, 0), max(self.dims[1] - hh, 0), hw, hh))
                placed.append(hut.geom)
                continue
            spec = self.scroll.building(w.window_id) if self.scroll is not None else None
            if spec is not None and spec.hut and len(spec.hut) == 2:
                hut.place(geo.hut_from_frac(float(spec.hut[0]), float(spec.hut[1]), width, height, hw, hh))
                placed.append(hut.geom)
            else:
                new.append((w, hut))
        # New huts take their place on shelves cut for the sizes of all of them (each row spread over
        # the width, the rows over the height); a spot that is taken falls back to the first free one.
        shown = [self.huts[w.window_id] for w in wanted]
        cells = geo.hut_shelves(width, height, [(h.geom.w, h.geom.h) for h in shown])
        index = {w.window_id: i for i, w in enumerate(wanted)}
        for w, hut in new:
            hw, hh = hut.geom.w, hut.geom.h
            x, y = cells[index[w.window_id]]
            spot = Geom(x, y, hw, hh)
            if any(geo.overlaps(spot, p, 1, 0) for p in placed):
                spot = geo.first_free(width, height, hw, hh, placed) or geo.clamp(Geom(x + 2, y + 1, hw, hh), width, height)
            hut.place(spot)
            placed.append(spot)

    # -- the ghost of a building being placed ---------------------------------------

    def start_ghost(self, label: str, size: tuple[int, int], on_done) -> bool:
        """Walk a ghost hut over the town; `on_done((fx, fy))` where it settles, `on_done(None)` on
        Esc. False when there is no town on screen to place it in (tiles, Minimal)."""
        if not self.town_active or self.dims[0] <= 0 or self.dims[1] <= 0 or self.ghost is not None:
            return False
        width, height = self.hut_room
        w, h = size
        taken = [hut.geom for hut in self.huts.values() if hut.display]
        start = Geom(max((width - w) // 2, 0), max((height - h) // 2, 0), w, h)   # the middle of the town
        self.ghost = Ghost(label, start, (width, height), taken)
        self._ghost_done = on_done
        self.mount(self.ghost)
        self.ghost.focus()
        self.ghost.capture_mouse()
        return True

    def on_ghost_done(self, message: Ghost.Done) -> None:
        message.stop()
        ghost, done = self.ghost, self._ghost_done
        self.ghost, self._ghost_done = None, None
        if ghost is not None:
            ghost.release_mouse()
            ghost.remove()
        if done is not None:
            g = message.geom
            done(geo.hut_to_frac(g.x, g.y, *self.hut_room, g.w, g.h) if g is not None else None)

    def _settle(self, hut: Hut) -> None:
        """A hut that changed size stays on the canvas and off its neighbours: it keeps its spot when
        that is free, else takes the nearest free one (and the town keeps it)."""
        width, height = self.hut_room
        others = [h.geom for h in self.huts.values() if h is not hut and h.display]
        g = hut.geom
        g = Geom(min(max(g.x, 0), max(width - g.w, 0)), min(max(g.y, 0), max(height - g.h, 0)), g.w, g.h)
        if any(geo.overlaps(g, o, 1, 0) for o in others):
            g = geo.first_free(width, height, g.w, g.h, others) or g
        if g != hut.geom:
            hut.place(g)
        self.post_message(Hut.Moved(hut))

    def refresh_huts(self) -> None:
        """Live status lines: each building's view says what its hut shows (`hut_lines`, else `mini_status`)."""
        for bid, hut in self.huts.items():
            if not hut.display:
                continue
            w = self.get_window(bid)
            body = next(iter(w.children), None) if w is not None else None
            lines_of = getattr(body, "hut_lines", None)
            status = getattr(body, "mini_status", None)
            try:
                if hut.base.grow and lines_of is not None:   # a chart or a preview takes the rows it needs
                    probe = lines_of(silhouettes.fit(hut.base, silhouettes.GROW_ROWS[hut.base.grow][1]).live_widths)
                    if hut.set_rows(silhouettes.rows_needed(hut.base, probe)):
                        self._settle(hut)
                lines = lines_of(hut.live_widths) if lines_of is not None else status() if status is not None else []
            except Exception:   # a status line must never take the town down
                lines = []
            hut.set_status(lines)
            if w is not None:
                hut.set_badge(w.badge)
                hut.set_title(w.number, w.window_title)

    def flicker_fires(self, now: float | None = None) -> None:
        """A hut whose orc waits for orders burns: its fence flickers, turns red, then its roof burns.
        In the office look it only stands red; in 🌙 quiet hours nothing burns (a ❓ instead)."""
        if self.quiet:
            for hut in self.huts.values():
                if hut.has_class("-flame"):
                    hut.remove_class("-flame")
            return
        for hut in self.huts.values():
            if hut.display and hut.has_class("-alert") and not self.plain:
                hut.update_fire(now)
                hut.toggle_class("-flame")
                hut.refresh()
            else:
                hut.update_fire(now)
                if hut.has_class("-flame"):
                    hut.remove_class("-flame")

    def _rally_click(self, w: Window) -> bool:
        """Road mode: a click on a building picks it as the source."""
        if not self.rally_mode:
            return False
        pick = getattr(self.app, "rally_pick_number", None)
        if pick is not None and w.window_id != self.rally_source:
            pick(w.number)
        return True

    def on_hut_clicked(self, message: Hut.Clicked) -> None:
        w = self.get_window(message.hut.building_id)
        if w is None or self._rally_click(w):
            return
        if w is self.active:
            self.post_message(self.CanvasClicked())   # a click on an open building collapses it
            return
        if self.town_active and self.selected_hut != w.window_id:
            # The first click only selects: the console turns to the building, the map stays.
            self.set_active(None)
            self.select_hut(w.window_id)
            self.post_message(self.HutSelected(w.window_id))
            return
        self.focus_window(w)                          # the second click opens it
        self.post_message(Window.Activated(w))

    def on_hut_action_pressed(self, message: Hut.ActionPressed) -> None:
        message.stop()
        run = getattr(self.app, "run_quick_action", None)
        if run is not None:
            run(message.hut.building_id, message.action_id)

    def on_hut_moved(self, message: Hut.Moved) -> None:
        self.save()
        self.replan_roads()

    def _apply_town(self) -> None:
        """Town view: only the active building is shown, opened over the map; tiles: all of them."""
        if self.single or not self.is_attached:
            return
        on = self.town_active
        width, height = self.dims
        for w in self.windows:
            if not self.in_view(w):
                continue
            if not on:
                if w.has_class("-town-open") or w.styles.visibility == "hidden":
                    w.remove_class("-town-open")
                    w.styles.visibility = "visible"
                    w.title_width = None
                    w.apply_geom(w.geom, w.frac)
                    w._update_title()
                continue
            if w is self.active and not w.hidden and width > 0 and height > 0:
                g = geo.frac_to_geom(geo.TOWN_SLOT, width, max(height - self.open_reserve, geo.MIN_H + 2))
                if self.open_right and g.x + g.w > width - self.open_right:   # clear of the orc's chat
                    g = Geom(g.x, g.y, max(width - self.open_right - g.x - 1, geo.MIN_W), g.h)
                w.add_class("-town-open")
                w.styles.visibility = "visible"
                w.styles.offset = (g.x, g.y)
                w.styles.width, w.styles.height = g.w, g.h
                if w.title_width != g.w:
                    w.title_width = g.w
                    w._update_title()
            else:
                w.remove_class("-town-open")
                w.styles.visibility = "hidden"
        for bid, hut in self.huts.items():
            hut.set_class(on and self.active is not None and self.active.window_id == bid, "-expanded")
