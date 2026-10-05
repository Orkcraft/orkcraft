"""The base of every typed building's view.

A typed view is still a CustomBuildingView, so everything the app does with custom buildings —
deliveries along roads, the 📥 note, refresh — keeps working. On top it has:

    config          the spec's settings for its type
    state_dir       `.orkcraft/<type>/<building id>/`, where it keeps what it learns
    emit(...)       sends one of its type's events down the roads that carry it
    receive(...)    what a delivery means to it (run, enqueue, …)
    worker          its worker in the core (core/workers), for a type that has one: the view
                    draws the worker's state (`redraw`, on every `WORKER`) and calls its acts
    quick_action    the hut buttons and [ / ]
    mini_status     the hut lines
"""
from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult

from orkcraft.core import workers
from orkcraft.realm import catalog, masonry, pipes
from orkcraft.screens.custom_view import CustomBuildingView

STATE_ROOT = workers.STATE_ROOT


class TypedView(CustomBuildingView):
    TYPE = ""
    TAKES_REWORK = False      # a delivered cart is work it redoes (a Loot checkpoint may send one back)
    # Which widget draws each pane of its UI contract (design/buildings/<type>.json): pane id → CSS
    # selector inside the view. A type without a contract is one pane, `main`: the view itself.
    UI_PANES: dict[str, str] = {}

    DEFAULT_CSS = """
    TypedView .typed-list { width: 2fr; height: 1fr; border: round $surface-lighten-1; }
    TypedView .typed-detail { width: 3fr; height: 1fr; border: round $surface-lighten-1; padding: 0 1; }
    TypedView .typed-head { height: auto; padding: 0 1; color: $text-muted; }
    TypedView .typed-row { height: 1fr; }
    """

    def __init__(self, spec: dict, repo_root: Path | None = None, graph=None, id: str | None = None) -> None:
        super().__init__(spec, repo_root, graph, id)
        self.incoming_title = ""
        self.incoming_trail: tuple[pipes.Hop, ...] = ()   # what the last cart went through
        self.incoming_ref = ""

    # -- what it is ---------------------------------------------------------------------------------

    @property
    def building_id(self) -> str:
        return str(self.spec.get("id", ""))

    @property
    def config(self) -> dict:
        return dict(self.spec.get("config") or {})

    @property
    def btype(self) -> catalog.BuildingType:
        return catalog.type_of(self.spec)

    @property
    def simulated(self) -> bool:
        """The showcase sandbox (`orkcraft --demo`): agents never run there, their answers are simulated."""
        return bool(getattr(getattr(self, "app", None), "demo", False))

    @property
    def state_dir(self) -> Path:
        return workers.state_dir(self._get_repo_root(), self.TYPE, self.building_id)

    @property
    def worker(self):
        """Its worker (core/workers): the building's state and acts; None for a type without one."""
        try:
            town = getattr(self.app, "core", None)
        except Exception:                            # not mounted in an app
            return None
        return town.worker(self.building_id) if town is not None else None

    # -- the view -----------------------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield from self.compose_body()

    def compose_body(self) -> ComposeResult:
        yield from ()

    def on_mount(self) -> None:
        self.refresh_data()
        self.apply_ui()

    def refresh_data(self) -> None:
        pass

    def ui_document(self) -> dict:
        """Its UI document: what the Town Scroll keeps for it, else its type's default."""
        from orkcraft.design import ui
        town = getattr(getattr(self, "app", None), "scroll", None)
        return ui.current(town.building(self.building_id) if town is not None else None, self.btype.id)

    def apply_ui(self, doc: dict | None = None) -> None:
        """Lay the window out as its UI document says (docs/design-system.md)."""
        from orkcraft.tui import ui_apply
        try:
            ui_apply.apply(self, doc or self.ui_document(), self.UI_PANES)
        except Exception:      # a layout never takes a building down: it keeps the one it had
            pass

    def redraw(self) -> None:
        """Its worker's state changed: draw it again (a view whose type has a worker overrides it)."""

    def restart(self) -> None:
        """After the weekly self-audit changed it: pick up the new settings."""
        self.refresh_data()

    def mini_status(self) -> list[str]:
        return [self.btype.preview]

    def hut_lines(self, widths: list[int]) -> list[str]:
        """What the silhouette's live slots show (`widths`: the width of each). A view with more to
        say than `mini_status` overrides this; the default is the three short lines."""
        return self.mini_status()

    def quick_action(self, action_id: str) -> bool:
        return False

    # -- roads --------------------------------------------------------------------------------------

    def show_incoming(self, title: str, markdown: str, trail: tuple = (), ref: str = "") -> None:
        self.incoming_title, self.incoming_trail, self.incoming_ref = title, tuple(trail), ref

    def receive(self, payload: pipes.Payload, title: str, markdown: str) -> None:
        """A cart arrived. Most types only note it; some act on it (Agent runs, Barracks enqueues)."""

    def out_of_gold(self, what: str = "") -> bool:
        """The run's 🪙 limit is reached: no model call starts (the operator is told when `what` says what waits)."""
        app = self.app
        if not getattr(app, "gold_exhausted", lambda: False)():
            return False
        if what:
            try:
                app.notify(f"🪙 budget exhausted — {what} waits", title=self.spec.get("title", self.building_id),
                           severity="warning")
            except Exception:
                pass
        return True

    def emit(self, event_id: str, value: str, title: str = "", trail: tuple = (), ref: str = "") -> bool:
        """Send `event_id` (one this building declares) down its roads. True when a road took it.
        A building that passes on what it received gives its `trail` and `ref` so they travel on."""
        app = getattr(self, "app", None)
        emit = getattr(app, "emit_typed", None)
        if emit is None:
            return False
        extra = {k: v for k, v in (("trail", tuple(trail)), ("ref", ref)) if v}
        return bool(emit(self.building_id, event_id, value, title, **extra))

    def save_config(self, changes: dict) -> bool:
        """Change the building's settings and save its spec (it is checked like any spec)."""
        spec = dict(self.spec, config={**self.config, **changes})
        app = self.app
        others = set(getattr(app, "custom_specs", {})) - {self.building_id}
        problems = masonry.save_spec(self._get_repo_root(), spec, existing_ids=others)
        if problems:
            app.notify("\n".join(problems), title="Not saved", severity="error")
            return False
        self.spec = spec
        if hasattr(app, "custom_specs"):
            app.custom_specs[self.building_id] = spec
        mark = getattr(app, "checkpoint", None)
        if mark is not None:
            mark("update", self.building_id, "settings: " + ", ".join(sorted(changes)))
        return True
