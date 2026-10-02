"""The base of every typed building's view.

A typed view is still a CustomBuildingView, so everything the app does with custom buildings —
deliveries along roads, the 📥 note, refresh — keeps working. On top it has:

    config          the spec's settings for its type
    state_dir       `.orkcraft/<type>/<building id>/`, where it keeps what it learns
    emit(...)       sends one of its type's events down the roads that carry it
    receive(...)    what a delivery means to it (run, enqueue, …)
    quick_action    the hut buttons and [ / ]
    mini_status     the hut lines
"""
from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult

from orkcraft.realm import catalog, masonry, pipes
from orkcraft.screens.custom_view import CustomBuildingView

STATE_ROOT = Path(".orkcraft")


class TypedView(CustomBuildingView):
    TYPE = ""

    DEFAULT_CSS = """
    TypedView .typed-list { width: 2fr; height: 1fr; border: round $surface-lighten-1; }
    TypedView .typed-detail { width: 3fr; height: 1fr; border: round $surface-lighten-1; padding: 0 1; }
    TypedView .typed-head { height: auto; padding: 0 1; color: $text-muted; }
    TypedView .typed-row { height: 1fr; }
    """

    def __init__(self, spec: dict, repo_root: Path | None = None, graph=None, id: str | None = None) -> None:
        super().__init__(spec, repo_root, graph, id)
        self.incoming_title = ""

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
        root = self._get_repo_root() / STATE_ROOT
        here = root / self.TYPE / self.building_id
        if not here.exists():                        # T1107: a building of an old type keeps what it learned
            for old, new in catalog.ALIASES.items():
                legacy = root / old / self.building_id
                if new == self.TYPE and legacy.is_dir():
                    here.parent.mkdir(parents=True, exist_ok=True)
                    legacy.rename(here)
                    break
        return here

    # -- the view -----------------------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield from self.compose_body()

    def compose_body(self) -> ComposeResult:
        yield from ()

    def on_mount(self) -> None:
        self.refresh_data()

    def refresh_data(self) -> None:
        pass

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

    def show_incoming(self, title: str, markdown: str) -> None:
        self.incoming_title = title

    def receive(self, payload: pipes.Payload, title: str, markdown: str) -> None:
        """A cart arrived. Most types only note it; some act on it (Agent runs, Barracks enqueues)."""

    def emit(self, event_id: str, value: str, title: str = "") -> bool:
        """Send `event_id` (one this building declares) down its roads. True when a road took it."""
        app = getattr(self, "app", None)
        emit = getattr(app, "emit_typed", None)
        return bool(emit(self.building_id, event_id, value, title)) if emit is not None else False

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
