"""The GUI's side of the town: it owns the `Town`, keeps its clocks and answers the page's commands.

The TUI's app does this for Textual (its timers, its `_wire_bus`); the host does it for the page,
with no toolkit at all. Everything here runs on one thread, the server's event loop: the town's
`call` hops back to it from a worker's thread, so services never race the page.

    host = Host(repo_root)
    host.on_change = lambda: ...       # the town changed: send a fresh snapshot
    host.on_toast = lambda data: ...   # a toast to show
    host.tick()                        # once a second: the roster, the roads, the treasury
    host.command("hut.move", {"id": "lake", "x": 0.4, "y": 0.2})
    host.on_detail = lambda building_id: ...   # an open building's own state changed
    host.detail("lake")                # what its window draws (gui/views/)
    host.command("act", {"id": "lake", "act": "edit"})
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

from orkcraft.core import bus
from orkcraft.core.roster import Muster
from orkcraft.core.town import Town
from orkcraft.core.treasury import Treasury
from orkcraft.design import ui
from orkcraft.gui import state, views
from orkcraft.realm import catalog, modes

TELEMETRY_REFRESH_S = 5.0       # as the TUI (tui/base.py)


class CommandError(Exception):
    """A command the page sent that the host refuses; its text is shown to the person."""


class Host:
    def __init__(self, repo_root: Path | None = None, auto_commit: bool | None = None,
                 layout_file: Path | None = None, demo: bool = False) -> None:
        self.town = Town(repo_root, auto_commit, layout_file, demo=demo)
        self.treasury = Treasury(self.town)
        self.muster = Muster(self.town)
        self.town.budget_ok = lambda: not self.town.demo and not self.treasury.exhausted()
        self.on_change: Callable[[], None] = lambda: None
        self.on_toast: Callable[[dict], None] = lambda data: None
        self.on_detail: Callable[[str], None] = lambda building_id: None
        self._telemetry_at = 0.0
        self._refreshed: dict[str, float] = {}     # building id → when its worker last looked again
        self.town.bus.subscribe(bus.ANY, self._event)
        self.commands: dict[str, Callable[[dict], Any]] = {
            "orkspace.select": self._select_orkspace,
            "hut.move": self._move_hut,
            "building.open": self._open_building,
            "halt": self._halt,
            "act": self._act,
        }
        for bs in self.town.scroll.buildings:      # a building with a worker works from the start
            if not bs.demolished:
                self.town.worker(bs.id)

    # -- what the page sees --------------------------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        return state.snapshot(self.town, self.muster, self.treasury)

    def _event(self, event: bus.Event) -> None:
        if event.topic == bus.TOAST:
            data = {k: event.data.get(k) for k in ("message", "title", "severity", "timeout")}
            data["message_plain"] = modes.strip_emoji(str(data["message"] or ""))
            data["title_plain"] = modes.strip_emoji(str(data["title"] or ""))
            self.on_toast(data)
            return
        if event.topic in (bus.WORKER, bus.SPEC, bus.UI) and event.data.get("building"):
            self.on_detail(str(event.data["building"]))
        self.on_change()

    def type_of(self, building_id: str) -> str:
        spec = self.town.spec_of(building_id)
        return catalog.type_of(spec).id if spec else building_id

    def detail(self, building_id: str) -> dict[str, Any] | None:
        """What a building's window draws: its UI document and, for a type the GUI draws, its worker's
        state (gui/views/). None for a building that is gone."""
        bs = self.town.scroll.building(building_id)
        if bs is None or bs.demolished:
            return None
        type_id = self.type_of(building_id)
        view, worker = views.of(type_id), self.town.worker(building_id)
        data = view.detail(worker) if view is not None and worker is not None else None
        return {"id": building_id, "type": type_id, "ui": ui.current(bs, type_id), "data": data}

    # -- the clocks ----------------------------------------------------------------------------

    def tick(self, now: float | None = None) -> None:
        """Once a second: the roads' timers, the roster (and its questions), the treasury every 5 s."""
        now = time.monotonic() if now is None else now
        try:
            self.town.roads.tick()
        except Exception as e:                     # a road's timer never stops the clock
            self.town.toast(str(e), title="Roads", severity="error")
        if now - self._telemetry_at >= TELEMETRY_REFRESH_S:
            self._telemetry_at = now
            self.treasury.refresh()
        for bid, w in list(self.town.workers.items()):     # the workers that look again by themselves
            view = views.of(self.type_of(bid))
            every = getattr(view, "REFRESH_S", 0)
            if every and now - self._refreshed.get(bid, -every) >= every:
                self._refreshed[bid] = now
                try:
                    view.refresh(w)
                except Exception as e:                 # one building's look never stops the clock
                    self.town.toast(f"{type(e).__name__}: {e}", title=self.town.title_of(bid), severity="error")
        self.muster.rebuild([])
        self.on_change()

    def close(self) -> None:
        """The window closed: what an editor holds is written, what runs stops, the scroll is kept."""
        for bid, w in list(self.town.workers.items()):
            flush = getattr(views.of(self.type_of(bid)), "flush", None)
            if flush is not None:
                try:
                    flush(w)
                except Exception:
                    pass
        self.town.halt()
        self.town.save()

    # -- the page's commands -------------------------------------------------------------------

    def command(self, name: str, args: dict | None = None) -> Any:
        fn = self.commands.get(name)
        if fn is None:
            raise CommandError(f"Unknown command: {name}")
        return fn(dict(args or {}))

    def _spec(self, args: dict):
        bs = self.town.scroll.building(str(args.get("id", "")))
        if bs is None or bs.demolished:
            raise CommandError(f"No building {args.get('id')!r}")
        return bs

    def _select_orkspace(self, args: dict) -> None:
        oid = str(args.get("id", ""))
        if not any(o.id == oid for o in self.town.scroll.orkspaces):
            raise CommandError(f"No orkspace {oid!r}")
        self.town.scroll.active_orkspace_id = oid
        self.town.save()
        self.on_change()

    def _move_hut(self, args: dict) -> None:
        """A hut dragged on the town: its spot as fractions of the canvas, the person's own."""
        bs = self._spec(args)
        try:
            x, y = float(args["x"]), float(args["y"])
        except (KeyError, TypeError, ValueError):
            raise CommandError("A hut's spot is two numbers") from None
        bs.hut = [round(min(max(x, 0.0), 1.0), 4), round(min(max(y, 0.0), 1.0), 4)]
        self.town.save()
        self.on_change()

    def _open_building(self, args: dict) -> dict:
        bs = self._spec(args)
        w = self.town.worker(bs.id)
        return {"id": bs.id, "has_worker": w is not None}

    def _act(self, args: dict) -> Any:
        """One of a building's own acts (gui/views/<type>.py `ACTS`), done by its worker."""
        bs = self._spec(args)
        view, worker = views.of(self.type_of(bs.id)), self.town.worker(bs.id)
        fn = (view.ACTS.get(str(args.get("act", ""))) if view is not None and worker is not None else None)
        if fn is None:
            raise CommandError(f"{bs.title} cannot {args.get('act')!r} here")
        try:
            return fn(worker, dict(args.get("args") or {}))
        except views.ActError as e:
            raise CommandError(str(e)) from None

    def _halt(self, args: dict) -> int:
        stopped = self.town.halt()
        self.town.toast(f"Stopped {stopped} building{'s' if stopped != 1 else ''}" if stopped
                        else "Nothing was running", title="Halt All")
        return stopped
