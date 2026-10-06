"""Workers: a building's job without its face.

A typed building both shows things and does things: takes carts, runs its librarian, keeps a
board. The doing is its worker's — one per building, made by `Town.worker(id)` the first time it
is asked for, living as long as the town. A worker keeps the building's state, does its acts and
says when it changed (`WORKER` on the bus); a face draws that state and calls the acts.

A worker runs slow work in threads of its own. Whatever it hands back to the town from there
goes through `town.call` (the TUI hops to its UI thread), and so do `changed()` and `toast()`.

    class LakeWorker(Worker):
        TYPE = "lake"
        def receive(self, payload, title, markdown): ...
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from orkcraft.core import bus
from orkcraft.realm import catalog, masonry

STATE_ROOT = Path(".orkcraft")


def state_dir(repo_root: Path, type_id: str, building_id: str) -> Path:
    """`.orkcraft/<type>/<building id>/`, where a building keeps what it learns (a building of an
    old type's name keeps what it learned there: T1107)."""
    root = repo_root / STATE_ROOT
    here = root / type_id / building_id
    if not here.exists():
        for old, new in catalog.ALIASES.items():
            legacy = root / old / building_id
            if new == type_id and legacy.is_dir():
                here.parent.mkdir(parents=True, exist_ok=True)
                legacy.rename(here)
                break
    return here


def type_id(spec: dict | None) -> str:
    return catalog.type_of(spec).id


class Worker:
    TYPE = ""

    def __init__(self, town, building_id: str) -> None:
        self.town = town
        self.building_id = building_id

    # -- what it is -----------------------------------------------------------------------------

    @property
    def spec(self) -> dict:
        return self.town.custom_specs.get(self.building_id) or {"id": self.building_id, "type": self.TYPE}

    @property
    def config(self) -> dict:
        return dict(self.spec.get("config") or {})

    @property
    def btype(self) -> catalog.BuildingType:
        return catalog.type_of(self.spec)

    @property
    def title(self) -> str:
        return str(self.spec.get("title") or self.building_id)

    @property
    def repo_root(self) -> Path:
        return self.town.repo_root

    @property
    def simulated(self) -> bool:
        """The showcase sandbox (`orkcraft --demo`): agents never run there."""
        return bool(self.town.demo)

    @property
    def state_dir(self) -> Path:
        return state_dir(self.repo_root, self.TYPE or self.btype.id, self.building_id)

    # -- its life -------------------------------------------------------------------------------

    def start(self) -> None:
        """Made: pick up what it had (the town calls it once)."""

    def receive(self, payload, title: str, markdown: str) -> None:
        """A cart arrived along a road."""

    def halt(self) -> int:
        """🛑 Halt All: stop its own work (queues wait). How many things it stopped."""
        return 0

    def status(self) -> str:
        """One word for its state (WORKING, ERROR, …); "" when it has nothing to say."""
        return ""

    # -- telling the town -----------------------------------------------------------------------

    def changed(self) -> None:
        """Its state changed: the faces draw it again."""
        self.town.call(lambda: self.town.publish(bus.WORKER, building=self.building_id))

    def emit(self, event_id: str, value: str, title: str = "", trail: tuple = (), ref: str = "",
             route: str = "") -> bool:
        """Send `event_id` (one its building declares) down the roads. True when a road took it; `route`
        names who takes it on (a road that waits for routes takes only its own)."""
        args = (route,) if route else ()
        return bool(self.town.emit_typed(self.building_id, event_id, value, title, tuple(trail), ref, *args))

    def toast(self, message: str, title: str = "", severity: str = "information",
              timeout: float | None = None) -> None:
        self.town.call(self.town.toast, message, title or self.title, severity, timeout)

    def out_of_gold(self, what: str = "") -> bool:
        """The run's 🪙 limit is reached: no model call starts (the person is told when `what` says what waits)."""
        if self.town.budget_ok() or self.simulated:
            return False
        if what:
            self.toast(f"🪙 budget exhausted — {what} waits", severity="warning")
        return True

    def save_config(self, changes: dict[str, Any]) -> bool:
        """Change the building's settings and save its spec (checked like any spec)."""
        spec = dict(self.spec, config={**self.config, **changes})
        others = set(self.town.custom_specs) - {self.building_id}
        problems = masonry.save_spec(self.repo_root, spec, existing_ids=others)
        if problems:
            self.toast("\n".join(problems), title="Not saved", severity="error")
            return False
        self.town.custom_specs[self.building_id] = spec
        self.town.publish(bus.SPEC, building=self.building_id, spec=spec)
        self.town.checkpoint("update", self.building_id, "settings: " + ", ".join(sorted(changes)))
        return True


def registry() -> dict[str, type[Worker]]:
    """The type id → its worker's class: every `Worker` with a `TYPE` in a module of this package
    registers itself (a new worker is one new file, no list to edit). Types without one keep their
    work in their views."""
    import importlib
    import pkgutil
    out: dict[str, type[Worker]] = {}
    for info in pkgutil.iter_modules(__path__):
        module = importlib.import_module(f"{__name__}.{info.name}")
        for value in vars(module).values():
            if isinstance(value, type) and issubclass(value, Worker) and value.TYPE and value.__module__ == module.__name__:
                out[value.TYPE] = value
    return out
