"""A map goes back as a whole (docs/design/projects.md §6): every checkpoint names the orkspace it happened in, so
an orkspace has a history of its own; going back to one of its checkpoints puts its buildings back as they were,
demolishes what was raised since, and never touches another orkspace."""
from __future__ import annotations

import pytest

from orkcraft.core import maps
from orkcraft.gui.host import CommandError, Host
from orkcraft.realm import checkpoint


@pytest.fixture
def host(fake_repo, isolated_layout_file):
    checkpoint.ensure(fake_repo)
    h = Host(fake_repo, auto_commit=False)
    yield h
    h.close()


def _orders(host, bid: str, text: str) -> None:
    host.town.scroll.building(bid).garrison.steward.orders = text
    host.town.checkpoint("update", bid, "new orders")


def test_every_checkpoint_names_its_orkspace(host, fake_repo):
    main = host.town.scroll.active_orkspace_id
    shop = host.command("orkspace.new", {"name": "Shop", "project": "town"})
    pit = host.command("town.build", {"type": "pit"})
    rows = checkpoint.history(fake_repo, orkspace=shop)
    assert [r.orkspace for r in rows] == [shop, shop]
    assert rows[0].building == pit and "new orkspace Shop" in rows[1].message
    assert all(r.orkspace != shop for r in checkpoint.history(fake_repo, orkspace=main))
    host.command("orkspace.rename", {"id": shop, "name": "Store"})
    assert "renamed Store" in checkpoint.history(fake_repo, orkspace=shop)[0].message


def test_a_map_goes_back_and_other_maps_stay(host, fake_repo):
    main = host.town.scroll.active_orkspace_id
    other = host.command("town.build", {"type": "pit"})                     # on the first map
    shop = host.command("orkspace.new", {"name": "Shop", "project": "town"})
    kept = host.command("town.build", {"type": "pit"})
    _orders(host, kept, "first orders")
    moment = checkpoint.history(fake_repo, orkspace=shop)[0].sha
    _orders(host, kept, "second orders")
    later = host.command("town.build", {"type": "pit"})
    host.command("orkspace.rename", {"id": shop, "name": "Store"})
    host.command("orkspace.select", {"id": main})
    _orders(host, other, "the first map's own")
    host.command("orkspace.select", {"id": shop})

    host.command("history.revert", {"orkspace": shop, "sha": moment})
    scroll = host.town.scroll
    assert scroll.building(kept).garrison.steward.orders == "first orders"
    assert scroll.building(later).demolished and not scroll.building(kept).demolished
    assert scroll.orkspace(shop).name == "Shop"
    assert scroll.building(other).garrison.steward.orders == "the first map's own"     # another map: untouched
    assert scroll.orkspace_of(other).id == main
    top = checkpoint.history(fake_repo, orkspace=shop)[0]
    assert top.message.startswith("revert(") and "Shop back to" in top.message

    newest = checkpoint.history(fake_repo, orkspace=shop)[1].sha                     # going back is undone the same way
    host.command("history.revert", {"orkspace": shop, "sha": newest})
    assert host.town.scroll.building(kept).garrison.steward.orders == "second orders"


def test_a_building_moved_to_another_map_since_stays_there(host, fake_repo):
    from orkcraft import scroll as ts
    main = host.town.scroll.active_orkspace_id
    shop = host.command("orkspace.new", {"name": "Shop", "project": "town"})
    pit = host.command("town.build", {"type": "pit"})
    moment = checkpoint.history(fake_repo, orkspace=shop)[0].sha
    ts.move_building(host.town.scroll, pit, main)
    host.town.checkpoint("update", pit, "moved")
    done = maps.revert(host.town, shop, moment)
    assert done.elsewhere == [pit] and host.town.scroll.orkspace_of(pit).id == main


def test_the_history_reads_as_the_person_says_it_and_refuses_what_it_cannot(host):
    shop = host.command("orkspace.new", {"name": "Shop", "project": "town"})
    host.command("town.build", {"type": "pit"})
    rows = host.command("history.list", {"orkspace": shop})
    assert rows[0]["kind"] == "create" and rows[0]["building"] and ":" in rows[0]["when"]
    assert rows[-1]["what"] == "new orkspace Shop" and rows[-1]["building"] == ""
    with pytest.raises(CommandError, match="did not exist"):
        host.command("history.revert", {"orkspace": shop, "sha": "0" * 40})
    with pytest.raises(CommandError, match="No orkspace"):
        host.command("history.list", {"orkspace": "nowhere"})
