"""A map goes back as a whole (docs/design/projects.md §6): an orkspace and its buildings as they were at one of
its checkpoints. Other orkspaces are never touched: a building lives on one map, so a building that has moved to
another map since stays where it is, and is said so.

    history(town, "shop")                  # the map's checkpoints, newest first
    revert(town, "shop", sha)              # the map as it was at `sha`; one checkpoint of its own

Its buildings get back their spec, scripts and blueprints, and their scroll entry (orks, roads from buildings that
still exist, settings, place); their level stays what they reached. A building raised since is demolished (kept in
the history like any other); one demolished since stands again. The orkspace gets back its name, biome, order and
project (while that project is still in the town).
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from orkcraft import scroll as ts
from orkcraft.core import bus
from orkcraft.core.town import Town
from orkcraft.realm import catalog, checkpoint, pipes
from orkcraft.realm.buildings import TOWN_HALL, custom_building


class MapError(Exception):
    """Why a map cannot go back: said to the person as it is."""


@dataclass
class Reverted:
    back: list[str] = field(default_factory=list)       # buildings put back as they were
    removed: list[str] = field(default_factory=list)    # raised since: demolished
    elsewhere: list[str] = field(default_factory=list)  # moved to another map since: left there
    sha: str | None = None                               # the revert's own checkpoint


def history(town: Town, orkspace_id: str, limit: int = 50) -> list[checkpoint.Checkpoint]:
    return checkpoint.history(town.repo_root, orkspace=orkspace_id, limit=limit)


def when(at: str) -> str:
    """A checkpoint's time as the person reads it: `14:32`, or `Oct 9, 14:32` on another day."""
    try:
        t = dt.datetime.fromisoformat(at).astimezone()
    except ValueError:
        return at
    return f"{t:%H:%M}" if t.date() == dt.datetime.now().astimezone().date() else f"{t:%b} {t.day}, {t:%H:%M}"


def _entry(data: dict) -> ts.BuildingSpec:
    return ts.TownScroll.from_dict({"active_orkspace_id": "x", "orkspaces": [], "buildings": [data]}).buildings[0]


def revert(town: Town, orkspace_id: str, sha: str) -> Reverted:
    ork = town.scroll.orkspace(orkspace_id)
    if ork is None:
        raise MapError(f"No orkspace {orkspace_id!r}")
    then = checkpoint.orkspace_at(town.repo_root, sha, orkspace_id)
    if then is None:
        raise MapError("This orkspace did not exist at that checkpoint")
    entry, entries, specs, files = then
    done = Reverted()
    wanted: list[str] = []
    for bid in entry.get("buildings", []):
        other = town.scroll.orkspace_of(bid)
        if other is not None and other.id != orkspace_id:
            done.elsewhere.append(bid)
        elif bid in entries:
            wanted.append(bid)
    for bid in list(ork.buildings):
        bs = town.scroll.building(bid)
        if bid not in wanted and bid != TOWN_HALL and bs is not None and not bs.demolished:
            worker = town.workers.get(bid)
            if worker is not None:
                worker.halt()
            bs.demolished = True
            town.record(bid, "building_demolished")
            done.removed.append(bid)
    known = {b.id for b in town.scroll.buildings} | set(wanted)
    for bid in wanted:
        if bid == TOWN_HALL:
            continue                                   # the town's own building stands as it is
        spec = specs.get(bid)
        checkpoint.restore_files(town.repo_root, bid, spec, files.get(bid, {}))
        old = _entry(entries[bid])
        old.roads = [r for r in old.roads if r.source in known]
        current = town.scroll.building(bid)
        if current is None:
            town.scroll.buildings.append(old)
        else:
            old.level = current.level                  # what it reached stays its own
            town.scroll.buildings[town.scroll.buildings.index(current)] = old
        if spec is not None:
            spec = catalog.migrate(spec)
            if bid not in town.custom_specs:
                town.buildings.append(custom_building(spec))
            town.custom_specs[bid] = spec
            pipes.set_typed(bid, catalog.events_of(spec), catalog.accepts(spec))
            town.publish(bus.SPEC, building=bid, spec=spec, refresh=True)
        town.worker(bid)
        done.back.append(bid)
    ork.name = str(entry.get("name") or ork.name)
    ork.biome = entry.get("biome") if entry.get("biome") in ts.BIOMES else ork.biome
    ork.buildings = wanted + [b for b in ork.buildings if b not in wanted and b not in done.elsewhere]
    ork.window_order = [b for b in entry.get("window_order", []) if b in wanted]
    ork.active_building = entry.get("active_building") if entry.get("active_building") in wanted else None
    project = entry.get("project") or None
    if project is None or town.scroll.project(project) is not None:
        ork.project = project
    town.publish(bus.ROADS)
    town.publish(bus.ROSTER)
    town.save()
    at = checkpoint.at_of(town.repo_root, sha)
    done.sha = town.checkpoint("revert", "", f"{ork.name} back to {when(at) if at else sha[:8]}", orkspace=orkspace_id)
    return done
