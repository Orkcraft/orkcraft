"""The town without a face: one project's state, the bus, and the few acts every service needs.

A face (the TUI today, the GUI later) builds one `Town`, registers how it saves (`saver`: the TUI's
desktop records window and hut positions first), subscribes to the bus and calls the services in
`core/`. Nothing here draws or asks: it changes the town and publishes what changed.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from orkcraft import scroll
from orkcraft.config import Config, find_project_root
from orkcraft.core import bus as b
from orkcraft.realm import catalog, checkpoint, chronicles, masonry, pipes
from orkcraft.realm.buildings import BUILTIN_SPECS, TOWN_HALL, Building, custom_building, presets, registry
from orkcraft.sources import telemetry


class Town:
    def __init__(
        self,
        repo_root: Path | None = None,
        auto_commit: bool | None = None,
        layout_file: Path | None = None,
        reset_layout: bool = False,
        demo: bool = False,
    ) -> None:
        # The showcase sandbox (orkcraft --demo): simulated data, agent handlers never run.
        self.demo = demo
        self.repo_root = repo_root or find_project_root()
        self.config = Config(repo_root=self.repo_root)
        if auto_commit is not None:
            self.config.auto_commit = auto_commit
        if layout_file is not None:
            self.config.layout_file = layout_file
        target_layout = self.config.layout_file
        if reset_layout and target_layout is not None:
            target_layout.unlink(missing_ok=True)
        if demo:
            from orkcraft.demo.graph import Graph
            self.graph = Graph(self.repo_root)
        else:
            self.graph = None
        self.bus = b.Bus()
        self.saver: Callable[[], bool] | None = None
        self.buildings: list[Building] = registry()
        specs, self.mason_problems = masonry.load_specs(self.repo_root)
        self.custom_specs: dict[str, dict] = {s["id"]: s for s in specs}
        pipes.TYPED.clear()                               # one town at a time (tests open several)
        for s in specs:                                   # what each typed building sends
            pipes.set_typed(s["id"], catalog.events_of(s))
        # Presets are the core registry only: a custom building is registered as `custom:<id>`
        # below, never as a preset (ensure_presets would add it demolished, as `legacy:<id>`).
        preset_specs = presets(self.buildings)
        for s in specs:
            self.buildings.append(custom_building(s))
        # 🧭 Onboarding runs for a project with no Town Scroll yet.
        self.first_run = False
        if target_layout is None:
            self.scroll, self.scroll_problems = scroll.default_scroll(preset_specs), []
        else:
            legacy = [target_layout.with_name(".orcraft.json")] if target_layout.name == ".orkcraft.json" else []
            self.first_run = not demo and not target_layout.exists() and not any(p.exists() for p in legacy)
            self.scroll, self.scroll_problems = scroll.load(target_layout, preset_specs, legacy=legacy)
        scroll.ensure_presets(self.scroll, preset_specs)
        hall = self.scroll.building(TOWN_HALL)
        if hall is not None:
            hall.demolished = False          # the town's own building: always standing, on every canvas
        for s in specs:
            if self.scroll.building(s["id"]) is None:
                scroll.add_custom_building(self.scroll, s)
        self.scroll_problems.extend(self.mason_problems)
        # 🪙 / 🪵: sessions this run starts are tagged with its id (sources/telemetry.py).
        self.run_id = telemetry.new_run_id()
        self.telemetry = telemetry.Telemetry(self.repo_root, self.run_id)
        self.snapshot = telemetry.Snapshot()

    # -- telling the faces -----------------------------------------------------------------------

    def toast(self, message: str, title: str = "", severity: str = "information", timeout: float | None = None) -> None:
        self.bus.publish(b.TOAST, message=message, title=title, severity=severity, timeout=timeout)

    def publish(self, topic: str, **data: Any) -> None:
        self.bus.publish(topic, **data)

    # -- looking things up -----------------------------------------------------------------------

    def building(self, building_id: str) -> Building | None:
        return next((x for x in self.buildings if x.id == building_id), None)

    def spec_of(self, building_id: str | None) -> dict | None:
        """A building's spec: a custom one's file, or the catalog type a built-in wears."""
        if not building_id:
            return None
        return self.custom_specs.get(building_id) or BUILTIN_SPECS.get(building_id)

    def title_of(self, building_id: str) -> str:
        """`🌊 Lake of Insight`: the icon and the title the scroll knows, else the id."""
        bs = self.scroll.building(building_id) if self.scroll is not None else None
        return f"{bs.icon} {bs.title}".strip() if bs else building_id

    def taken_ids(self) -> set[str]:
        """Ids a new building may not take: loaded buildings and every building the scroll remembers
        (a custom building whose spec file was deleted still has its scroll entry)."""
        return {x.id for x in self.buildings} | {x.id for x in self.scroll.buildings}

    # -- the acts every service needs ------------------------------------------------------------

    def save(self) -> bool:
        """Save the Town Scroll: through the face when it registered one (it records what it laid out)."""
        if self.saver is not None:
            return bool(self.saver())
        if self.config.layout_file is None:
            return False
        problems = scroll.save(self.config.layout_file, self.scroll)
        if problems:
            self.toast("\n".join(problems), title="Town Scroll Save Refused", severity="error")
        return not problems

    def checkpoint(self, kind: str, building: str, reason: str) -> str | None:
        """Save the scroll and commit the change in the camp's own git (never in the demo)."""
        if self.demo:
            return None
        try:
            self.save()
        except Exception:
            pass
        return checkpoint.commit(self.repo_root, kind, building, reason, self.config.layout_file)

    def record(self, building_id: str, kind: str, /, **data: Any) -> None:
        """A line in the building's chronicle; a full disk never stops the work it records."""
        try:
            chronicles.record(self.repo_root, self.scroll, building_id, kind, **data)
        except OSError:
            pass
