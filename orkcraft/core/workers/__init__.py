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

import time
from pathlib import Path
from typing import Any

from orkcraft.core import bus
from orkcraft.realm import catalog, masonry, pressure

STATE_ROOT = Path(".orkcraft")
QUOTA_READ_S = 60.0                 # how long one measure of the quota is good for


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
    # Its ERROR says its own work failed (core/wakes.py wakes a script-first building's ork on it); False for a
    # building whose ERROR is a reading it shows (a Metrics over its red line): that is its work, not a failure.
    ERROR_IS_FAILURE = True

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

    # -- its goal and the quota --------------------------------------------------------------------

    @property
    def aim(self) -> str:
        """Its building's goal (docs/design/retros-and-goals.md §3), balance when none is set."""
        scroll = getattr(self.town, "scroll", None)
        b = scroll.building(self.building_id) if scroll is not None else None
        return b.aim if b is not None else "balance"

    @property
    def aim_now(self) -> str:
        """The goal in force: its own, 🪙 thrift whatever it is while the camp's quota is tight."""
        camp = self.quota()
        return "thrift" if camp is not None and camp.tight else self.aim

    def quota(self) -> pressure.Camp | None:
        """What is left of the binding subscription quota (realm/pressure.py, from the town's last quota
        read); None with no read, no subscription or nothing spent yet. Measured once a minute."""
        from orkcraft.core import treasury
        now = time.monotonic()
        cached = getattr(self, "_quota_cache", None)
        if cached is not None and now - cached[0] < QUOTA_READ_S:
            return cached[1]
        camp = None
        machine = getattr(self.town, "machine", None)
        subs = treasury.subscriptions(machine) if machine is not None else []
        limits = getattr(self.town, "limits", None) or []
        if subs and limits and not self.simulated:
            try:
                camp = pressure.measure(self.repo_root, limits, providers=subs)
            except Exception:  # a quota that cannot be measured never stops the work
                camp = None
        camp = camp if camp is not None and camp.left is not None else None
        self._quota_cache = (now, camp)
        return camp

    # -- its steward's model -------------------------------------------------------------------------

    def _steward_of(self):
        """Its steward's spec and its tool: the one its steward names, else (none, or `main`) the main tool of
        the machine's settings as the town holds them."""
        from orkcraft.realm import builders, harnesses, steward
        scroll = getattr(self.town, "scroll", None)
        b = scroll.building(self.building_id) if scroll is not None else None
        tool = steward.harness_for(b)
        machine = getattr(self.town, "machine", None)
        if tool in ("", harnesses.MAIN) and machine is not None:
            tool = builders.main_tool(machine)
        return b, tool

    def steward_pick(self, use: str, setting: str = ""):
        """The model of its steward's `use` now (realm/steward.py `pick`: a tier picked for it, else the
        building's `setting`, else for its work the goal in force)."""
        from orkcraft.realm import steward
        b, tool = self._steward_of()
        return steward.pick(b, use, tool, type_id=self.TYPE or self.btype.id, goal=self.aim_now, setting=setting)

    def steward_runner(self, use: str, setting: str = ""):
        """Its steward's model call for `use` on the model `steward_pick` names, on its steward's tool. Every
        model call that makes the building's results goes through here (tests/test_steward_work.py)."""
        from orkcraft.realm import builders
        _b, tool = self._steward_of()
        p = self.steward_pick(use, setting)
        return builders.runner_for(tool, p.tier or p.model or None)

    # -- its life -------------------------------------------------------------------------------

    def start(self) -> None:
        """Made: pick up what it had (the town calls it once)."""

    def receive(self, payload, title: str, markdown: str) -> None:
        """A cart arrived along a road."""

    def halt(self) -> int:
        """🛑 Halt All: stop its own work (queues wait). How many things it stopped."""
        return 0

    def close(self) -> int:
        """The window closes: stop its own work like 🛑 Halt All, but leave nothing paused that the
        operator did not pause — the next launch takes up the work again. How many things it stopped."""
        return self.halt()

    def status(self) -> str:
        """One word for its state (WORKING, ERROR, …); "" when it has nothing to say."""
        return ""

    def orders_alert(self):
        """A question this building asks the person — (key, title, context, [(answer key, words)]) — which sets its
        hut on fire and waits in Answers; None when it asks nothing (the GUI's roster reads it: gui/host.py)."""
        return None

    def loose_ends(self) -> list[dict]:
        """Its ways out that no road takes yet — [{"route", "name", "event"}] — drawn on the map as a stub to pull a
        road from; the road pulled is laid on `event` at once (gui/static/js/town.js LooseEnds)."""
        return []

    def answer_alert(self, key: str) -> str | None:
        """The person picked answer `key` to `orders_alert()`; "dismiss" to put the question away."""
        return None

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
        """Change the building's settings and save its spec (checked like any spec); a None takes a setting out."""
        spec = dict(self.spec, config={k: v for k, v in {**self.config, **changes}.items() if v is not None})
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
