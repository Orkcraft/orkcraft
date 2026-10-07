"""Growth (docs/design/growth.md) and the biomes (docs/design/war-map.md §3): a building's level from what
its orks learned, the operator's deeds and mascot stage, the news, and the orkspaces' grounds."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from orkcraft import scroll as ts
from orkcraft import settings
from orkcraft.realm import biomes, evolution, feedback, growth
from orkcraft.scroll import BuildingSpec, Orkspace, TownScroll

NOW = dt.datetime(2026, 10, 6, 12, 0)


def _ago(days: float) -> str:
    return (NOW - dt.timedelta(days=days)).isoformat(timespec="seconds")


def _kept(root: Path, building: str, days: float, by: str = "orcs", status: str = "kept") -> evolution.Change:
    return evolution.record(root, evolution.Change(building, "shrink", "daily", "a shorter prompt", by=by,
                                                   status=status, ts=_ago(days)))


def _like(root: Path, building: str, n: int = 1) -> None:
    for _ in range(n):
        feedback.like(root, building, out={"value": "good"})


def _town(*ids: str) -> TownScroll:
    buildings = [BuildingSpec(i, f"core:{i}", i.title()) for i in ("town_hall", *ids)]
    return TownScroll("main", [Orkspace("main", "Main", buildings=[b.id for b in buildings])], buildings)


def test_a_building_without_kept_changes_has_no_level(tmp_path: Path):
    _like(tmp_path, "brief", 5)
    assert growth.earned(tmp_path, "brief", now=NOW) == 0


def test_one_kept_change_and_a_like_after_it_is_level_one(tmp_path: Path):
    _kept(tmp_path, "brief", 3)
    assert growth.earned(tmp_path, "brief", now=dt.datetime.now()) == 0     # kept, but nobody liked it since
    _like(tmp_path, "brief")
    assert growth.earned(tmp_path, "brief", now=dt.datetime.now()) == 1


def test_three_and_five_kept_changes_climb_to_two_and_three(tmp_path: Path):
    now = dt.datetime.now()
    for d in (40, 35, 32):
        evolution.record(tmp_path, evolution.Change("brief", "shrink", "daily", "s", status="kept",
                                                    ts=(now - dt.timedelta(days=d)).isoformat(timespec="seconds")))
    _like(tmp_path, "brief", 2)
    assert growth.earned(tmp_path, "brief", now=now) == 2
    for d in (31, 30.5):
        evolution.record(tmp_path, evolution.Change("brief", "chain", "daily", "s", status="kept",
                                                    ts=(now - dt.timedelta(days=d)).isoformat(timespec="seconds")))
    assert growth.earned(tmp_path, "brief", now=now) == 3
    assert growth.next_step(tmp_path, "brief", 3) == ""


def test_a_recent_revert_holds_a_building_back(tmp_path: Path):
    now = dt.datetime.now()
    for d in (40, 35, 32):
        evolution.record(tmp_path, evolution.Change("brief", "shrink", "daily", "s", status="kept",
                                                    ts=(now - dt.timedelta(days=d)).isoformat(timespec="seconds")))
    evolution.record(tmp_path, evolution.Change("brief", "enrich", "daily", "s", status="reverted",
                                                ts=(now - dt.timedelta(days=2)).isoformat(timespec="seconds")))
    _like(tmp_path, "brief", 2)
    assert growth.earned(tmp_path, "brief", now=now) == 1


def test_the_operators_own_edit_counts_only_when_a_like_follows_it(tmp_path: Path):
    evolution.record(tmp_path, evolution.Change("brief", "set_config", "steward", "by hand", by="you",
                                                ts=_ago(1)))
    assert growth.kept(tmp_path, "brief") == []
    _like(tmp_path, "brief")
    assert len(growth.kept(tmp_path, "brief")) == 1


def test_settle_raises_levels_never_lowers_them_and_says_so_once(tmp_path: Path):
    town = _town("brief")
    machine = settings.MachineSettings()
    machine.growth = {"stage": 1, "deeds": {}}               # not the first look: deeds are news
    _kept(tmp_path, "brief", 2)
    _like(tmp_path, "brief")
    fresh = growth.settle(town, tmp_path, machine)
    assert town.building("brief").level == 1
    assert any(n.kind == "level" and "Brief grew to ⚖️ I" in n.text for n in fresh)
    assert [n.kind for n in growth.settle(town, tmp_path, machine)] == []      # nothing new
    town.building("brief").level = 3                          # reached once, kept whatever the ratings say
    growth.settle(town, tmp_path, machine)
    assert town.building("brief").level == 3


def test_the_first_look_records_deeds_without_news_and_later_ones_are_news(tmp_path: Path):
    town = _town("pit")
    machine = settings.MachineSettings()
    fresh = growth.settle(town, tmp_path, machine)
    assert "town" in machine.growth["deeds"] and machine.growth["stage"] == 1
    assert not [n for n in fresh if n.kind == "deed"]
    town.building("pit").roads.append(ts.Road("r1", "town_hall"))
    fresh = growth.settle(town, tmp_path, machine)
    assert [n.text for n in fresh if n.kind == "deed"] == ["A deed: First road"]
    assert growth.news(tmp_path) and growth.news(tmp_path)[-1].text == "A deed: First road"
    growth.seen(tmp_path, growth.news(tmp_path)[-1].id)
    assert all(n.text != "A deed: First road" for n in growth.news(tmp_path))


def test_the_mascot_stage_follows_the_camp_and_is_named_by_kin_and_role(tmp_path: Path):
    town = _town("brief", "forge", "pit")
    machine = settings.MachineSettings()
    machine.profile = {"role": "eng_manager"}
    machine.autonomy = 0                                     # the town keeps its orks in chains
    assert growth.stage_of(town, {}, machine) == 1
    assert growth.stage_of(town, {"week": "2026-10-01"}, machine) == 2
    town.building("brief").level = 2
    assert growth.stage_of(town, {}, machine) == 3
    for b in ("brief", "forge", "pit"):
        town.building(b).level = 3
    assert growth.stage_of(town, {}, machine) == 3          # three at III, none deciding by itself
    town.building("forge").autonomy = "free"
    assert growth.stage_of(town, {}, machine) == 4
    assert growth.kin_of(machine.profile) == "lich"
    assert [growth.stage_name(machine.profile, s) for s in (1, 2, 3, 4)] == [
        "Standup Zombie", "The Jira Lich", "Lich of Sprints", "Release Night King"]


def test_a_review_answered_by_a_kept_change_closes_its_loop(tmp_path: Path):
    from dataclasses import asdict
    town = _town("brief")
    now = dt.datetime.now()
    feedback._append(tmp_path / feedback.DIR / "incidents.jsonl", asdict(feedback.Incident(
        (now - dt.timedelta(minutes=2)).isoformat(timespec="seconds"), "brief", "logic",
        "too long, skip the commit list", "x")))
    c = evolution.record(tmp_path, evolution.Change("brief", "shrink", "daily", "a shorter brief", status="kept",
                                                    ts=(now - dt.timedelta(minutes=1)).isoformat(timespec="seconds")))
    assert growth.loops(tmp_path, town, set()) == []           # not proved yet: nobody rated it since
    _like(tmp_path, "brief")
    found = growth.loops(tmp_path, town, set())
    assert [cid for cid, _ in found] == [c.id]
    assert "too long, skip the commit list" in found[0][1].text and "1 👍" in found[0][1].text
    assert growth.loops(tmp_path, town, {c.id}) == []


def test_machine_settings_keep_the_growth(tmp_path: Path):
    s = settings.MachineSettings()
    s.growth = {"stage": 3, "deeds": {"road": "2026-10-01"}, "junk": 1}
    settings.save(s, tmp_path / "s.json")
    assert settings.load(tmp_path / "s.json").growth == {"stage": 3, "deeds": {"road": "2026-10-01"}}
    assert settings.clean_growth({"stage": 9}) == {}


def test_a_level_and_the_new_biomes_round_trip_the_scroll(tmp_path: Path):
    from tests.test_scroll import PRESETS
    scroll = ts.default_scroll(PRESETS)
    scroll.buildings[0].level = 2
    scroll.orkspaces[0].biome = "lava"
    path = tmp_path / ".orkcraft.json"
    assert ts.save(path, scroll) == []
    loaded, problems = ts.load(path, PRESETS)
    assert problems == [] and loaded.buildings[0].level == 2 and loaded.orkspaces[0].biome == "lava"
    assert "level" not in loaded.to_dict()["buildings"][1]


def test_a_new_orkspace_gets_a_free_biome_then_one_unlike_its_neighbour():
    assert biomes.pick([]) == "dirt"
    assert biomes.pick(["dirt", "forest"]) == "ice"
    full = list(biomes.ORDER)
    assert biomes.pick(full) != full[-1]
    assert biomes.pick(full, upper="dirt") != "dirt"


def test_the_old_default_is_spread_once_and_chosen_biomes_stay():
    camp = TownScroll("a", [Orkspace("a", "A", "forest"), Orkspace("b", "B", "ice"), Orkspace("c", "C", "forest")], [])
    assert biomes.settle(camp) is True
    assert [o.biome for o in camp.orkspaces] == ["dirt", "ice", "forest"]
    camp.orkspaces[0].biome = "forest"
    assert biomes.settle(camp) is False and camp.orkspaces[0].biome == "forest"


def test_each_kin_has_a_home_and_a_new_camp_opens_on_it():
    """docs/design/war-map.md §3.3: the onboarding's role gives the kin, the kin its home ground."""
    assert biomes.home_of({"role": "eng_manager"}) == "ice"           # a lich: the frozen north
    assert biomes.home_of({"role": "founder"}) == "meadow"            # a knight: the open field
    assert biomes.home_of({"role": "designer"}) == "forest"
    assert biomes.home_of({"role": "engineer"}) == "dirt"
    assert biomes.home_of({}) == "dirt"                               # no role yet: the camp's own ground
    assert set(biomes.HOMES.values()) == set(biomes.ORDER)            # every biome is someone's home
    camp = TownScroll("a", [Orkspace("a", "A", "forest"), Orkspace("b", "B", "forest")], [])
    assert biomes.settle(camp, home="ice") is True
    assert [o.biome for o in camp.orkspaces] == ["ice", "dirt"]       # the first on the home, the next by pick
    taken = TownScroll("a", [Orkspace("a", "A", "forest"), Orkspace("b", "B", "ice")], [])
    biomes.settle(taken, home="ice")                                   # the home already chosen elsewhere
    assert [o.biome for o in taken.orkspaces] == ["dirt", "ice"]
