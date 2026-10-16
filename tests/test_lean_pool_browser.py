"""The lean Agent pool in a real browser (docs/specs/28-lean-pool.md §6): a cart from the pool at the Review gate opens
its waybill, and the pool's stop says where its tokens went — the ork's work, the steward's answers, review and
planning. Screenshots go to docs/design/img/lean-pool/ when ORKCRAFT_SHOTS is set."""
from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api")

from orkcraft.realm import pipes  # noqa: E402
from orkcraft.realm import roads as realm_roads  # noqa: E402
from orkcraft.realm import personas  # noqa: E402
from tests.test_gui_browser import WAIT_MS, _hut, _panel, camp_look, gui, page  # noqa: E402,F401  (fixtures)
from tests.test_gui_camp_browser import _call, _clear  # noqa: E402

pytestmark = pytest.mark.browser

SHOTS = Path(__file__).resolve().parent.parent / "docs" / "design" / "img" / "lean-pool"


def test_a_pool_cart_s_waybill_at_the_review_gate_says_where_its_tokens_went(camp_look, gui):
    server, _ = gui
    pg = camp_look
    _clear(pg)
    pool, gate = _call(pg, "town.build", {"type": "barracks"}), _call(pg, "town.build", {"type": "loot"})
    choice = next(c for c in _call(pg, "roads.choices", {"from": pool, "to": gate}) if not c.get("handler"))
    _call(pg, "roads.lay", {"from": pool, "to": gate, "event": choice["event"], "handler": None})
    pg.keyboard.press("Escape")
    road = next(r for x in server.host.town.scroll.buildings if x.id == gate for r in x.roads if r.source == pool)
    hop = pipes.hop(pool, "Grub", "agent", 2400, 0.52, outcome="done",
                    spend=(("ork", 2400, 0.5), ("answers", 300, 0.01), ("review", 500, 0.01)))
    payload = pipes.Payload(kind="text", value="done", source=pool, mode=road.event, title="Set up the database",
                            ref="9", trail=(hop,))
    server.host.town.roads.carts.append(realm_roads.Cart(road_id=road.id, source=pool, target=gate, status="held",
                                                         payload=payload, at=time.monotonic() - 30))
    pg.reload()                                                 # a cart put in by hand: no event sends the town again
    cart = pg.locator(f'.gui-camp__stand[data-id="{gate}"] .gui-camp__cart img').first
    cart.wait_for(state="attached", timeout=WAIT_MS)
    cart.click()
    bill = pg.locator(".gui-camp__waybill")
    bill.wait_for(state="visible", timeout=WAIT_MS)
    split = bill.locator(".gui-camp__waybill-split")
    split.wait_for(state="visible", timeout=WAIT_MS)
    line = split.inner_text()
    assert "The ork's work 2.4k tokens, $0.50" in line and "the steward's answers 300 tokens, $0.01" in line
    assert "its review 500 tokens, $0.01" in line and "its planning none" in line
    if os.environ.get("ORKCRAFT_SHOTS"):
        SHOTS.mkdir(parents=True, exist_ok=True)
        bill.screenshot(path=str(SHOTS / "waybill-split.png"))
    pg.keyboard.press("Escape")
    bill.wait_for(state="detached", timeout=WAIT_MS)
    server.host.town.roads.carts.clear()
    for bid in (pool, gate):
        _call(pg, "town.demolish", {"id": bid})


def test_a_role_is_removed_from_the_pool_s_settings_and_its_ork_takes_any_work(page, gui):
    server, _ = gui
    pg = page
    bid = pg.evaluate("() => import('/static/js/link.js').then(m => m.command('town.build', { type: 'barracks' }))")
    pg.evaluate("id => import('/static/js/link.js').then(m => m.act(id, 'pause'))", bid)   # nothing runs here
    w = server.host.town.worker(bid)
    personas.save(w.state_dir, personas.Persona("backend", "You build APIs. " * 60, "warrior", True))
    _hut(pg, bid).wait_for(state="visible", timeout=WAIT_MS)
    _hut(pg, bid).locator(".gui-hut__title").dblclick()
    _hut(pg, bid).locator(".pool-large").wait_for(state="visible", timeout=WAIT_MS)
    _hut(pg, bid).locator(".gui-hut__title").click()                               # opened again: its Info
    _panel(pg, "Info")
    rules = pg.locator(".gui-panel .gui-type-settings .pool-rules")
    rules.locator("summary").click()
    roles = rules.locator(".pool-roles")
    roles.get_by_text("backend").wait_for(state="visible", timeout=WAIT_MS)
    assert "Seasoned" in roles.inner_text()
    if os.environ.get("ORKCRAFT_SHOTS"):
        SHOTS.mkdir(parents=True, exist_ok=True)
        roles.screenshot(path=str(SHOTS / "roles.png"))
    roles.get_by_role("button", name="Remove backend").click()
    roles.get_by_text("None yet: every ork takes any work.").wait_for(state="visible", timeout=WAIT_MS)
    assert personas.load(w.state_dir, "backend") is None
    _call(pg, "town.demolish", {"id": bid})
