"""The cart's waybill, minimal (gui/waybill.py, docs/design/cart-waybill.md §2): a task's stops, the ork, tokens, spend
and time at each, read from the cart's own trail; what no hop recorded stays None."""
from __future__ import annotations

from types import SimpleNamespace

from orkcraft.gui import state, waybill
from orkcraft.realm import pipes
from orkcraft.realm import roads as realm_roads
from orkcraft.scroll import road_key


def _town(carts):
    blds = [SimpleNamespace(id="in", title="External listeners", roads=[]), SimpleNamespace(id="pool", title="Agent pool", roads=[]),
            SimpleNamespace(id="gate", title="Review gate", roads=[])]
    return SimpleNamespace(scroll=SimpleNamespace(buildings=blds), roads=SimpleNamespace(carts=carts), workers={})


def _cart(target, at, trail, road="r1", source="pool"):
    p = pipes.Payload(kind="text", value="x", source=source, mode="on_x", title="Fix the login", ref="42", trail=tuple(trail))
    return realm_roads.Cart(road_id=road, source=source, target=target, status="delivered", payload=p, at=at)


def test_a_carts_waybill_is_its_trail_with_tokens_spend_and_time_and_where_it_is_now():
    trail = [pipes.Hop("in", orc="Lookout", kind="script", at="2026-10-14T10:00:00", ms=1200),
             pipes.Hop("pool", orc="Grub", kind="agent", tokens=12000, cost=0.21, at="2026-10-14T10:05:00", ms=240000)]
    c = _cart("gate", 100.0, trail)
    d = waybill.waybill(_town([c]), cart=f"{road_key('gate', 'r1')}@100.000")
    assert [s["title"] for s in d["stops"]] == ["External listeners", "Agent pool"]
    assert d["stops"][0]["tokens"] is None and d["stops"][0]["at"] == "10:00"     # a script spends no tokens: not made up
    assert d["stops"][1]["ork"] == "Grub" and d["stops"][1]["cost"] == 0.21
    assert (d["tokens"], d["cost"], d["ms"]) == (12000, 0.21, 241200)
    assert d["now"] == {"building": "gate", "title": "Review gate", "status": "delivered"} and d["ref"] == "42"


def test_a_buildings_bubble_opens_its_newest_cart_and_an_unknown_one_is_none():
    old, new = _cart("gate", 1.0, []), _cart("gate", 2.0, [pipes.Hop("pool")])
    d = waybill.waybill(_town([old, new]), building="gate")
    assert len(d["stops"]) == 1 and d["tokens"] is None and d["ms"] is None        # nothing recorded: None, never 0
    assert waybill.waybill(_town([old]), cart="nope@1.000") is None
    assert waybill.waybill(_town([]), building="gate") is None


def test_the_snapshots_carts_carry_their_spend_so_far():
    c = _cart("gate", 0.0, [pipes.Hop("pool", tokens=5000, cost=0.1)])
    town = SimpleNamespace(roads=SimpleNamespace(carts=[c]), custom_specs={})
    got = state.carts(town, now=1.0)
    assert (got[0]["tokens"], got[0]["cost"]) == (5000, 0.1)
