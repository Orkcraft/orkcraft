"""A hut folded to its title bar (docs/design/folded-cards.md): the Town Scroll keeps it, the catalog says
which types are built folded, `building.fold` toggles it and the snapshot says it."""
from __future__ import annotations

from pathlib import Path

import pytest

from orkcraft import scroll as ts
from orkcraft.core import buildings
from orkcraft.gui.host import CommandError, Host
from orkcraft.realm import catalog, checkpoint, lexicon
from orkcraft.realm.buildings import TOWN_HALL


def _host(repo: Path) -> Host:
    checkpoint.ensure(repo)
    return Host(repo, auto_commit=False)


def _hut(host: Host, bid: str) -> dict:
    return next(b for b in host.snapshot()["buildings"] if b["id"] == bid)


def test_the_scroll_keeps_a_fold_and_an_old_scroll_loads_open():
    scroll = ts.default_scroll({}, ())
    scroll.buildings.append(ts.BuildingSpec(id="pit", preset_ref="custom:pit", title="The Pit", folded=True))
    data = scroll.to_dict()
    back = ts.TownScroll.from_dict(data)
    assert back.buildings[-1].folded is True
    del data["buildings"][-1]["folded"]
    assert ts.TownScroll.from_dict(data).buildings[-1].folded is False


def test_quiet_types_are_built_folded_the_rest_open(fake_repo, isolated_layout_file):
    assert {t.id for t in catalog.TYPES.values() if t.folded} == {"pit", "signpost", "mill"}
    host = _host(fake_repo)
    pit = buildings.raise_spec(host.town, buildings.type_spec(host.town, "pit")).id
    pool = buildings.raise_spec(host.town, buildings.type_spec(host.town, "barracks")).id
    assert _hut(host, pit)["folded"] is True
    assert _hut(host, pool)["folded"] is False


def test_fold_toggles_saves_and_is_recorded_but_the_town_hall_never_folds(fake_repo, isolated_layout_file):
    host = _host(fake_repo)
    pool = buildings.raise_spec(host.town, buildings.type_spec(host.town, "barracks")).id
    assert host.command("building.fold", {"id": pool}) is True
    assert _hut(host, pool)["folded"] is True
    assert host.town.scroll.building(pool).folded is True
    assert host.command("history", {"id": pool})["events"][0]["text"] == "card folded"
    assert host.command("building.fold", {"id": pool}) is False
    assert _hut(host, pool)["folded"] is False
    with pytest.raises(CommandError):
        host.command("building.fold", {"id": TOWN_HALL})


def test_fold_has_its_word():
    assert lexicon.term("fold") == "Fold"
