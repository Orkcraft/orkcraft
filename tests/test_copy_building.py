"""Copy to orkspace (docs/design/projects.md §5): a building lives on one map, so a building wanted on another is
copied. The copy is a building of its own: its own id, spec, orks and their instructions, scripts and blueprints;
roads only from buildings on that map (the rest are named); its history, level and place stay with the original."""
from __future__ import annotations

import hashlib

import pytest

from orkcraft import scroll as ts
from orkcraft.core import buildings
from orkcraft.gui.host import CommandError, Host
from orkcraft.realm import checkpoint, chronicles, workshop


def _scroll() -> ts.TownScroll:
    s = ts.default_scroll({})
    s.buildings += [ts.BuildingSpec("mail", "custom:mail", "Mail"), ts.BuildingSpec("board", "custom:board", "Board"),
                    ts.BuildingSpec("pool", "custom:pool", "Pool", level=2, pinned=True, hut=[0.4, 0.5], goal="quality")]
    s.orkspaces[0].buildings += ["mail", "board", "pool"]
    ts.new_orkspace(s, "Shop")
    return s


def test_the_copy_takes_its_orks_and_settings_and_only_the_roads_from_its_new_map():
    s = _scroll()
    shop = s.orkspaces[1]
    ts.move_building(s, "board", shop.id)
    ts.add_handler(s, "pool", "Scribe", kind="chain", chain=[{"op": "pick", "fields": ["id"]}])
    ts.subscribe(s, "pool", "mail", "on_task_completed")
    ts.subscribe(s, "pool", "board", "on_task_completed")
    copy, left = ts.copy_building(s, "pool", shop.id, "pool_2")
    assert left == ["mail"]
    assert [r.source for r in copy.roads] == ["board"]
    assert [h.name for h in copy.garrison.handlers] == ["Scribe"] and copy.goal == "quality"
    assert copy.level is None and copy.hut is None and not copy.pinned
    assert copy.preset_ref == "custom:pool_2"
    assert s.orkspace_of("pool_2") is shop and s.orkspace_of("pool").id == s.orkspaces[0].id
    copy.garrison.handlers[0].orders = "changed"                              # its own orks, not the original's
    assert s.building("pool").garrison.handlers[0].orders != "changed"
    assert ts.validate(s.to_dict()) == []
    with pytest.raises(ValueError):
        ts.copy_building(s, "pool", shop.id, "pool_2")                         # the id is taken
    with pytest.raises(ValueError):
        ts.copy_building(s, "pool", "nowhere", "pool_3")


@pytest.fixture
def host(fake_repo, isolated_layout_file):
    checkpoint.ensure(fake_repo)
    h = Host(fake_repo, auto_commit=False)
    yield h
    h.close()


def test_a_copy_has_its_own_spec_scripts_and_history(host, fake_repo):
    town = host.town
    bid = buildings.raise_spec(town, buildings.type_spec(town, "barracks")).id
    shop = host.command("orkspace.new", {"name": "Shop", "project": "town"})
    script = f".orkcraft/scripts/{bid}-scribe.py".replace("_", "-")
    (fake_repo / script).parent.mkdir(parents=True, exist_ok=True)
    (fake_repo / script).write_text("print('hi')\n", encoding="utf-8")
    sha = hashlib.sha256((fake_repo / script).read_bytes()).hexdigest()
    town.scroll.building(bid).garrison.handlers.append(
        ts.OrcSpec("scribe", "Scribe", kind="script", script={"path": script, "sha256": sha, "reviewed": True}))
    (fake_repo / workshop.BLUEPRINTS / bid).mkdir(parents=True)
    (fake_repo / workshop.BLUEPRINTS / bid / "plan.md").write_text("# plan\n", encoding="utf-8")
    town.record(bid, "pinned")
    new_id = host.command("building.copy", {"id": bid, "orkspace": shop})
    assert new_id == f"{bid}_2" and town.scroll.orkspace_of(new_id).id == shop
    assert town.custom_specs[new_id]["id"] == new_id and (fake_repo / ".orkcraft" / "buildings" / f"{new_id}.json").is_file()
    assert (fake_repo / workshop.BLUEPRINTS / new_id / "plan.md").is_file()
    orc = town.scroll.building(new_id).garrison.handlers[-1]
    assert orc.script["path"] == f".orkcraft/scripts/{new_id}-scribe.py".replace("_", "-")
    assert (fake_repo / orc.script["path"]).read_bytes() == (fake_repo / script).read_bytes() and orc.script["reviewed"]
    assert [e["type"] for e in chronicles.history(fake_repo, new_id)] == ["building_copied"]   # not the original's
    assert any("copied from" in c.message for c in checkpoint.history(fake_repo, new_id))
    assert host.command("building.copy", {"id": bid, "orkspace": shop}) == f"{bid}_3"
    assert host.command("building.copy", {"id": new_id, "orkspace": shop}) == f"{bid}_4"
    with pytest.raises(CommandError, match="cannot be copied"):
        host.command("building.copy", {"id": "town_hall", "orkspace": shop})
    with pytest.raises(CommandError, match="No orkspace"):
        host.command("building.copy", {"id": bid, "orkspace": "nowhere"})
