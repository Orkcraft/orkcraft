"""A building's inputs (docs/design/improve-buildings.md §3): every quick action is an input or says it only changes
what the window shows; a press ends in the act a person's form ends in, and is published to be recorded."""
from __future__ import annotations

from pathlib import Path

import pytest

from orkcraft.core import bus, buildings, inputs
from orkcraft.core.workers import registry
from orkcraft.gui import views
from orkcraft.gui.host import CommandError, Host
from orkcraft.realm import catalog, checkpoint


def _host(repo: Path) -> Host:
    checkpoint.ensure(repo)
    return Host(repo, auto_commit=False)


def _raised(host: Host, type_id: str) -> str:
    built = buildings.raise_spec(host.town, buildings.type_spec(host.town, type_id))
    assert built is not None
    host.refresh_roster()
    return built.id


def test_every_quick_action_says_whether_it_is_an_input():
    actions = {a.id for t in catalog.TYPES.values() for a in t.actions}
    assert set(catalog.QUICK_INPUTS) == actions


@pytest.mark.parametrize("type_id", sorted(t.id for t in catalog.TYPES.values() if t.actions))
def test_every_input_ends_in_a_real_act(type_id: str):
    acts = getattr(views.of(type_id), "ACTS", {})
    worker = registry().get(type_id)
    for a in catalog.TYPES[type_id].actions:
        how = catalog.QUICK_INPUTS[a.id]
        if how is None:
            continue
        act, arg, fixed = how
        assert act in acts if act else worker is not None and "quick_action" in vars(worker), a.id
        assert isinstance(fixed, dict) and (not arg or arg not in fixed), a.id


def test_a_buildings_inputs_are_its_road_and_its_quick_actions(fake_repo, isolated_layout_file):
    host = _host(fake_repo)
    board, bench = _raised(host, "fields"), _raised(host, "ux_lab")
    got = {i["id"]: i for i in host.command("building.inputs", {"id": board})}
    assert list(got)[0] == inputs.ROAD and "text" in got[inputs.ROAD]["takes"]
    assert got["tasks.new"]["takes"] == "text" and got["tasks.new"]["label"]
    assert host.command("building.inputs", {"id": bench}) == []          # no road, no quick action


def test_a_press_ends_in_the_act_a_persons_form_ends_in(fake_repo, isolated_layout_file):
    host = _host(fake_repo)
    board = _raised(host, "fields")
    heard = []
    host.town.bus.subscribe(bus.INPUT, lambda e: heard.append(e.data))
    host.command("building.input", {"id": board, "input": "tasks.new", "value": "Fix the login page", "by": "bench"})
    worker = host.town.worker(board)
    assert any("Fix the login page" in (c.title + c.body) for c in worker.cards)
    assert heard == [{"building": board, "input": "tasks.new", "value": "Fix the login page", "by": "bench"}]
    with pytest.raises(CommandError, match="say what it takes"):
        host.command("building.input", {"id": board, "input": "tasks.new", "value": "  "})
    with pytest.raises(CommandError, match="no input"):
        host.command("building.input", {"id": board, "input": "files.open"})


def test_a_town_with_no_face_presses_nothing(fake_repo, isolated_layout_file):
    host = _host(fake_repo)
    board = _raised(host, "fields")
    host.town.presser = None
    with pytest.raises(inputs.InputError, match="Nothing here presses"):
        inputs.press(host.town, board, "tasks.new", "A task")
