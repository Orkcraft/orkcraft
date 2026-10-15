"""Camp's town in v3 in a real browser (js/camp/, docs/design/design-system-v3.md §3–§4): the buildings on rows with a
line of track under each, the lookout in the back wall and the catapult at the buffer stop, carts on the lines only,
a stopped cart standing at its building's stop with its flag and chip; the wheel steps the zoom and a drag pans; a click
selects a building and a second enters it. Office draws the same town as cards (tests/test_gui_browser.py)."""
from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api")

from orkcraft.realm import pipes  # noqa: E402
from tests.test_gui_browser import WAIT_MS, camp_look, gui, page  # noqa: E402,F401  (fixtures)

pytestmark = pytest.mark.browser

LINK = "import('/static/js/link.js')"


def _call(pg, name, args):
    return pg.evaluate(f"([n, a]) => {LINK}.then(m => m.command(n, a))", [name, args])


def _building(pg, bid):
    return pg.locator(f'.gui-camp__building[data-id="{bid}"]')


def _clear(pg):
    pg.evaluate(f"""() => {LINK}.then(async (m) => {{
      for (const b of m.town.value.buildings) if (b.id !== 'town_hall') await m.command('town.demolish', {{ id: b.id }});
    }})""")


def test_the_town_stands_on_rows_and_lines_with_the_lookout_and_the_catapult_in_the_wall(camp_look):
    pg = camp_look
    _clear(pg)
    tower = _call(pg, "town.build", {"type": "watchtower"})
    board = _call(pg, "town.build", {"type": "fields"})
    pool = _call(pg, "town.build", {"type": "barracks"})
    out = _call(pg, "town.build", {"type": "catapult"})
    pg.keyboard.press("Escape")
    for bid in (tower, board, pool, out):
        _building(pg, bid).wait_for(state="visible", timeout=WAIT_MS)
    assert pg.locator(".gui-hut").count() == 0                              # no cards in Camp: v3's sprites
    src = _building(pg, pool).locator("img").get_attribute("src")
    assert src.endswith("/ds/sprites/v3/buildings/depot.png")                 # the Agent pool is the depot (§4d)
    assert "Agent pool" in _building(pg, pool).inner_text()                 # its name, in today's word
    tiles = pg.locator(".gui-camp__layer.is-track img")
    assert tiles.count() > 6
    names = tiles.evaluate_all("els => els.map(e => e.src.split('/').pop())")
    assert names.count("stop-e.png") == 2                                   # the line's buffer, the Task board's siding
    box = lambda bid: _building(pg, bid).bounding_box()                     # noqa: E731
    t, b, p, c = box(tower), box(board), box(pool), box(out)
    assert t["x"] < b["x"] < p["x"] < c["x"]                                # the way in left, the way out right
    assert t["y"] + t["height"] < b["y"] + b["height"]                      # the lookout stands in the back wall
    assert pg.locator(".gui-camp__siding").count() == 1                     # the dispatcher's booth has its siding
    for bid in (tower, board, pool, out):
        _call(pg, "town.demolish", {"id": bid})


def test_a_stopped_cart_stands_at_its_stop_with_its_flag_and_chip(camp_look, gui, monkeypatch):
    from orkcraft.gui import state
    from orkcraft.realm import roads as realm_roads
    server, _ = gui
    pg = camp_look
    _clear(pg)
    a, b = _call(pg, "town.build", {"type": "forge"}), _call(pg, "town.build", {"type": "forge"})
    choice = next(c for c in _call(pg, "roads.choices", {"from": a, "to": b}) if not c.get("handler"))
    _call(pg, "roads.lay", {"from": a, "to": b, "event": choice["event"], "handler": None})
    pg.keyboard.press("Escape")
    road = next(r for x in server.host.town.scroll.buildings if x.id == b for r in x.roads if r.source == a)
    now = time.monotonic()
    monkeypatch.setattr(state, "_asking", lambda muster: ({"7"}, set()))
    for i, (status, ref) in enumerate([("held", "5"), ("held", "6"), ("sent", "7")]):
        payload = pipes.Payload(kind="text", value="x", source=a, mode=road.event, title="Fix the login form for good",
                                ref=ref, want="change")
        server.host.town.roads.carts.append(realm_roads.Cart(road_id=road.id, source=a, target=b, status=status,
                                                             payload=payload, at=now - 60 + i))
    pg.reload()                                                 # carts put in by hand: no event sends the town again
    stand = pg.locator(f'.gui-camp__stand[data-id="{b}"]')
    stand.wait_for(state="attached", timeout=WAIT_MS)
    assert "is-ask" in stand.get_attribute("class")                           # the loudest flag in front
    assert stand.locator(".gui-camp__cart[data-load='code']").count() == 3
    assert stand.locator(".gui-camp__flag").count() == 1
    assert stand.locator(".gui-camp__chip").inner_text() == "#7 · Fix the login form…"
    # it stands on b's line, under b, never on a path
    s, h = stand.bounding_box(), _building(pg, b).bounding_box()
    assert abs((s["x"]) - (h["x"] + h["width"] / 2)) < 4 and s["y"] > h["y"] + h["height"]
    # a cart pressed: the task's history (its stops, tokens, time; nothing recorded is said so)
    stand.locator(".gui-camp__cart img").first.click()
    bill = pg.locator(".gui-camp__waybill")
    bill.wait_for(state="visible", timeout=WAIT_MS)
    bill.get_by_text("Now:").first.wait_for(state="visible", timeout=WAIT_MS)
    assert "Fix the login form" in bill.inner_text() and "Now:" in bill.inner_text()
    assert "not recorded" in bill.inner_text()
    pg.keyboard.press("Escape")
    bill.wait_for(state="detached", timeout=WAIT_MS)
    # its steward pressed (its Smith rests, no session): its steward's console, saying plainly what is not known
    pg.locator('.gui-camp__layer.is-orks .gui-camp__ork').first.evaluate("e => e.click()")
    console = pg.locator(".gui-camp__steward")
    console.wait_for(state="visible", timeout=WAIT_MS)
    console.get_by_text("This week").wait_for(timeout=WAIT_MS)
    assert "terminal to show" in console.inner_text() and "Smith" in console.inner_text()     # what is not known, said
    assert console.get_by_role("button", name="Enter").count() == 1
    pg.keyboard.press("Escape")
    console.wait_for(state="detached", timeout=WAIT_MS)
    server.host.town.roads.carts.clear()
    for bid in (a, b):
        _call(pg, "town.demolish", {"id": bid})


def test_the_wheel_steps_the_zoom_a_drag_pans_and_a_click_selects_then_enters(camp_look):
    pg = camp_look
    _clear(pg)
    forge = _call(pg, "town.build", {"type": "forge"})
    pg.keyboard.press("Escape")
    house = _building(pg, forge)
    house.wait_for(state="visible", timeout=WAIT_MS)
    town = pg.locator(".gui-camp")
    step = town.get_attribute("data-step")
    w = house.bounding_box()["width"]
    tb = town.bounding_box()
    pg.mouse.move(tb["x"] + 300, tb["y"] + 300)
    assert step == "1/1"                                                      # the default: the art at its own pixel
    pg.mouse.wheel(0, 120)                                                    # further: the overview, ×0.5
    pg.wait_for_function("() => document.querySelector('.gui-camp').dataset.step === '0.5/0.5'", timeout=WAIT_MS)
    assert house.bounding_box()["width"] == w / 2
    pg.wait_for_timeout(300)
    pg.mouse.wheel(0, -120)                                                   # back
    pg.wait_for_function("s => document.querySelector('.gui-camp').dataset.step === s", arg=step, timeout=WAIT_MS)
    before = house.bounding_box()
    pg.mouse.move(tb["x"] + tb["width"] / 2, tb["y"] + 60)                   # clear of the War Map and the line
    pg.mouse.down()
    pg.mouse.move(tb["x"] + tb["width"] / 2 + 120, tb["y"] + 120, steps=6)
    pg.mouse.up()
    after = house.bounding_box()
    assert round(after["x"] - before["x"]) == 120 and round(after["y"] - before["y"]) == 60
    assert pg.locator(".gui-camp__building.is-selected").count() == 0         # a drag selects nothing
    corner = {"x": 6, "y": house.bounding_box()["height"] * 0.55}            # its side: clear of its steward's bubble
    house.click(position=corner)
    pg.locator(f'.gui-camp__building.is-selected[data-id="{forge}"]').wait_for(timeout=WAIT_MS)
    assert pg.locator(".gui-panel").count() == 0
    house.click(position=corner)                                              # the second click enters it
    pg.locator(".gui-panel").wait_for(state="visible", timeout=WAIT_MS)
    pg.keyboard.press("Escape")
    pg.keyboard.press("Escape")
    _call(pg, "town.demolish", {"id": forge})


def test_build_in_camp_takes_its_place_on_the_line(camp_look):
    pg = camp_look
    _clear(pg)
    pg.evaluate("() => import('/static/js/build.js').then(m => m.place({ id: 'forge', title: 'Branches & PRs' }))")
    bands = pg.locator(".gui-camp__placing .gui-camp__band")
    bands.first.wait_for(state="visible", timeout=WAIT_MS)
    assert [b.inner_text() for b in bands.all()] == ["Top row", "Bottom row"]    # no free placement: a row
    bands.first.click()
    first = pg.locator(".gui-camp__building[data-type='forge']")
    first.wait_for(state="visible", timeout=WAIT_MS)
    pg.wait_for_selector(".gui-town__raising", state="detached", timeout=WAIT_MS)
    one = first.get_attribute("data-id")
    first = pg.locator(f'.gui-camp__building[data-id="{one}"]')
    pg.evaluate("() => import('/static/js/build.js').then(m => m.place({ id: 'forge', title: 'Branches & PRs' }))")
    pg.locator(".gui-camp__band", has_text="Bottom row").click()
    second = pg.locator(f'.gui-camp__building[data-type="forge"]:not([data-id="{one}"])')
    second.wait_for(state="visible", timeout=WAIT_MS)
    pg.wait_for_selector(".gui-town__raising", state="detached", timeout=WAIT_MS)
    assert second.bounding_box()["y"] > first.bounding_box()["y"] + first.bounding_box()["height"]   # a row of its own, below
    for h in (first, second):
        _call(pg, "town.demolish", {"id": h.get_attribute("data-id")})


def test_a_buildings_error_or_held_ork_shows_over_it_as_a_badge(camp_look, monkeypatch):
    """design-system-v3.md §5, town-readability.md §4: an ork's own error is a red `!` over its building, held for a
    limit ⏳; only while the host says so (the building's `signal`, gui/state.py); signals are UI, never in the art."""
    from orkcraft.gui import state
    said: dict = {}

    def signals(found, rows):
        for b in found:
            b["signal"] = said.get(b["id"])

    monkeypatch.setattr(state, "signals", signals)
    pg = camp_look
    _clear(pg)
    forge = _call(pg, "town.build", {"type": "forge"})
    pg.keyboard.press("Escape")
    _building(pg, forge).wait_for(state="visible", timeout=WAIT_MS)
    assert pg.locator(".gui-camp__badge").count() == 0                         # nothing to say: no badge
    said[forge] = {"kind": "error", "key": "f/grunt", "name": "Grunt", "line": "Grunt · error: boom"}
    _call(pg, "building.fold", {"id": forge, "value": False})                  # a new snapshot
    badge = pg.locator(".gui-camp__badge.is-fire")
    badge.wait_for(state="visible", timeout=WAIT_MS)
    assert badge.inner_text() == "!"
    said[forge] = {**said[forge], "kind": "held", "line": "Grunt · held for a limit"}
    _call(pg, "building.fold", {"id": forge, "value": False})
    pg.locator(".gui-camp__badge.is-held svg").wait_for(state="visible", timeout=WAIT_MS)   # ⏳ drawn, not the emoji
    _call(pg, "town.demolish", {"id": forge})


def test_the_mouse_brings_the_steward_out_a_click_grows_its_scroll_and_a_second_click_enters(camp_look):
    """decisions-2026-10.md §13.1: hover — its steward out of the door with a thought bubble, a small scroll with its
    status; click — the scroll grows, its quick actions at its foot; a second click enters the building."""
    pg = camp_look
    _clear(pg)
    board = _call(pg, "town.build", {"type": "fields"})
    pg.keyboard.press("Escape")
    house = _building(pg, board)
    house.wait_for(state="visible", timeout=WAIT_MS)
    pg.mouse.move(2, 400)
    assert pg.locator(".gui-camp__scroll").count() == 0                      # nobody out, no scroll
    house.hover()
    scroll = pg.locator(f'.gui-camp__scroll[data-id="{board}"]')
    scroll.wait_for(state="visible", timeout=WAIT_MS)
    assert "Task board" in scroll.inner_text() and "is-grown" not in scroll.get_attribute("class")
    assert pg.locator(".gui-camp__bubble").first.inner_text().strip()       # its thought, in a few words
    assert pg.locator(".gui-camp__door, .gui-camp__ork.is-out").count() == 1   # its steward out of the door
    pg.mouse.move(2, 400)
    scroll.wait_for(state="detached", timeout=WAIT_MS)
    house.click()                                                            # selected: the scroll grows
    grown = pg.locator(f'.gui-camp__scroll.is-grown[data-id="{board}"]')
    grown.wait_for(state="visible", timeout=WAIT_MS)
    acts = grown.locator(".gui-camp__scroll-acts button")
    names = [a.get_attribute("aria-label") or a.text_content() for a in acts.all()]
    assert names == ["Enter"]                                                # its quick actions: the bottom bar's alone
    assert pg.locator(".gui-warchief__act", has_text="New task").count() == 1
    assert "Taskmaster" in grown.inner_text()                                # its steward by its orkish name
    box = grown.bounding_box()
    assert box["y"] >= 0                                                     # inside the window
    house.click()                                                            # the second click enters it
    pg.locator(f'.gui-inside[data-id="{board}"]').wait_for(state="visible", timeout=WAIT_MS)   # the Task board: its inside
    pg.keyboard.press("Escape")
    house.wait_for(state="visible", timeout=WAIT_MS)
    _call(pg, "town.demolish", {"id": board})


def test_the_task_board_is_entered_its_cards_move_between_boards_and_exit_goes_back(camp_look, gui):
    """decisions-2026-10.md §13.2 (I2): the second click enters the Task board — the dispatcher's booth from inside,
    three boards (To do, Doing, Done) with its cards pinned, the Taskmaster walking with its bubble, its settings on
    the right in plain words; a card dragged to another board moves there; a to-do's flag ticks it off; Exit and Esc
    go back to the camp. Office keeps the card."""
    server, _ = gui
    pg = camp_look
    _clear(pg)
    board = _call(pg, "town.build", {"type": "fields"})
    pg.keyboard.press("Escape")
    w = server.host.town.worker(board)
    task = w.add("Fix the login form", "todo")
    w.add("Write the release notes", "in_progress")
    mine = w.todos[0].id if w.todos else w.add("Call the printer", w.todo_lane().id).id
    house = _building(pg, board)
    house.wait_for(state="visible", timeout=WAIT_MS)
    house.click()
    house.click()                                                            # the second click enters it
    room = pg.locator(f'.gui-inside[data-id="{board}"]')
    room.wait_for(state="visible", timeout=WAIT_MS)
    assert pg.locator(".gui-camp").count() == 0                              # a screen of its own
    room.locator(".fields-in__plaque").first.wait_for(state="visible", timeout=WAIT_MS)
    plaques = room.locator(".fields-in__plaque span").all_inner_texts()
    assert plaques[:3] == ["To do", "Doing", "Done"]
    todo = room.locator('.fields-in__board[data-lane="todo"]')
    sheet = todo.locator(f'.fields-in__card.is-sheet[data-card="{task.id}"]')
    sheet.wait_for(state="visible", timeout=WAIT_MS)
    assert "Fix the login form" in sheet.inner_text()
    assert room.locator(".fields-in__ork.is-steward").count() == 1
    assert "Taskmaster" in room.locator(".fields-in__ork.is-steward").inner_text()
    assert room.locator(".fields-in__ork.is-steward .fields-in__bubble").inner_text().strip()
    # the boards hang on the wall above the floor; the floor stays in sight and the Taskmaster walks on it, in the room
    pane = room.locator(".gui-inside__room").bounding_box()
    boards = room.locator(".fields-in__boards").bounding_box()
    floor = room.locator(".fields-in__floor").bounding_box()
    steward = room.locator(".fields-in__ork.is-steward").bounding_box()
    assert boards["y"] + boards["height"] <= floor["y"] + 1 and floor["height"] >= 100
    assert floor["y"] + floor["height"] <= pane["y"] + pane["height"] + 1               # no scrolling to find the floor
    assert steward["x"] >= pane["x"] and steward["x"] + steward["width"] <= pane["x"] + pane["width"]
    assert floor["y"] - 60 <= steward["y"] and steward["y"] + steward["height"] <= pane["y"] + pane["height"] + 1
    shop = room.locator(".gui-inside__shop")
    assert "Settings" in shop.inner_text() and "Task board" in shop.inner_text()
    # the description folds at a word with "more" and unfolds whole; the runs line wraps, never cut
    about = shop.locator(".gui-info__about").first
    assert about.inner_text().rstrip().endswith("more")
    about.get_by_role("button", name="more").click()
    assert "moving into a status lane" in about.inner_text()
    assert all(t.evaluate("e => e.scrollWidth <= e.clientWidth") for t in shop.locator(".gui-info__text").all())
    exit_ = room.get_by_role("button", name="Exit")
    box, frame = exit_.bounding_box(), room.bounding_box()
    assert box["x"] + box["width"] > frame["x"] + frame["width"] - 40 and box["y"] < frame["y"] + 40   # top right
    shots = os.environ.get("ORKCRAFT_SHOTS")
    if shots:
        pg.wait_for_timeout(600)
        pg.screenshot(path=str(Path(shots) / "i2-task-board-inside.png"))
    # a card dragged to Doing moves there, as moving a card does
    sheet.drag_to(room.locator('.fields-in__board[data-lane="in_progress"]'))
    room.locator(f'.fields-in__board[data-lane="in_progress"] [data-card="{task.id}"]').wait_for(state="visible", timeout=WAIT_MS)
    assert w.card(task.id).column == "in_progress"
    # a to-do's flag ticks it off: it goes to Done, its flag raised
    slab = room.locator(f'.fields-in__card.is-slab[data-card="{mine}"]')
    if slab.count():
        slab.get_by_role("button", name="Tick it off").click()
        room.locator(f'.fields-in__board[data-lane="done"] [data-card="{mine}"] .fields-in__flag.is-up').wait_for(timeout=WAIT_MS)
    if shots:
        pg.screenshot(path=str(Path(shots) / "i2-card-moved-to-do-ticked.png"))
    exit_.click()                                                            # Exit: back to the camp
    house.wait_for(state="visible", timeout=WAIT_MS)
    assert pg.locator(".gui-inside").count() == 0
    house.click()                                                            # selected still: entered again
    room.wait_for(state="visible", timeout=WAIT_MS)
    pg.keyboard.press("Escape")                                              # Esc: back too
    house.wait_for(state="visible", timeout=WAIT_MS)
    _call(pg, "town.demolish", {"id": board})


def test_a_launched_cart_flies_with_its_cost_and_the_hud_shows_the_score(camp_look, gui):
    """the-score.md, v3-prompts §13.4: each cart the catapult launches shows its wood as it flies (its share of the
    window not recorded yet, said so); the HUD shows the wood per accepted result with the quality guard beside it."""
    from orkcraft.realm import roads as realm_roads
    server, _ = gui
    pg = camp_look
    _clear(pg)
    a, out = _call(pg, "town.build", {"type": "forge"}), _call(pg, "town.build", {"type": "catapult"})
    choices = _call(pg, "roads.choices", {"from": a, "to": out})
    choice = next((c for c in choices if not c.get("handler")), choices[0])
    _call(pg, "roads.lay", {"from": a, "to": out, "event": choice["event"], "handler": choice.get("handler")})
    pg.keyboard.press("Escape")
    road = next(r for x in server.host.town.scroll.buildings if x.id == out for r in x.roads if r.source == a)
    payload = pipes.Payload(kind="text", value="x", source=a, mode=road.event, title="Release notes", ref="9",
                            trail=(pipes.Hop(a, tokens=12000, cost=0.2),))
    server.host.town.roads.carts.append(realm_roads.Cart(road_id=road.id, source=a, target=out, status="delivered",
                                                         payload=payload, at=time.monotonic()))
    pg.reload()
    fly = pg.locator(".gui-camp__launch")
    fly.wait_for(state="attached", timeout=WAIT_MS)
    assert fly.text_content().strip() == "🪵 12k · $0.20"          # only what was recorded (it waits hidden till it arrives)
    score = pg.locator(".gui-score")
    assert score.count() == 1 and "per result" in score.inner_text()
    assert "👎" not in score.inner_text() and "—" not in score.inner_text()   # nothing accepted yet: nothing made up
    assert "Not measured yet" in score.get_attribute("title")
    server.host.town.roads.carts.clear()
    for bid in (a, out):
        _call(pg, "town.demolish", {"id": bid})


def test_a_buildings_renown_and_goal_show_on_it(camp_look, gui):
    """growth.md §5, v3-prompts §13.4: no mark before renown; a goal other than balance builds its annex at once;
    renown I–III a stone footing and a banner on the roof."""
    server, _ = gui
    pg = camp_look
    _clear(pg)
    forge = _call(pg, "town.build", {"type": "forge"})
    pg.keyboard.press("Escape")
    _building(pg, forge).wait_for(state="visible", timeout=WAIT_MS)
    marks = pg.locator(f'.gui-camp__growth[data-id="{forge}"]')
    assert marks.count() == 0
    _call(pg, "building.goal", {"id": forge, "value": "thrift"})
    pg.wait_for_function("id => [...document.querySelectorAll(`.gui-camp__growth[data-id=\"${id}\"]`)]"
                         ".some(e => e.src.endsWith('/growth/annex-thrift.png'))", arg=forge, timeout=WAIT_MS)
    server.host.town.scroll.building(forge).level = 3
    _call(pg, "building.goal", {"id": forge, "value": "quality"})            # a new snapshot
    pg.wait_for_function("id => [...document.querySelectorAll(`.gui-camp__growth[data-id=\"${id}\"]`)].map(e => e.src.split('/').pop())"
                         ".sort().join() === 'annex-quality.png,banner-3.png,footing-3.png'", arg=forge, timeout=WAIT_MS)
    assert "Renown III" in (marks.first.get_attribute("title") or "") + (marks.nth(1).get_attribute("title") or "")
    _call(pg, "town.demolish", {"id": forge})


def test_the_persons_home_stands_by_the_review_gate_and_opens_their_own(camp_look):
    """design-system-v3.md §4.13, v3-prompts §13: the person's home (their kin's) east of the Review gate; a click opens
    since your last look, their profile and deeds, the town's settings."""
    pg = camp_look
    _clear(pg)
    gate = _call(pg, "town.build", {"type": "loot"})
    pg.keyboard.press("Escape")
    _building(pg, gate).wait_for(state="visible", timeout=WAIT_MS)
    home = pg.locator(".gui-camp__home")
    home.wait_for(state="visible", timeout=WAIT_MS)
    kin = home.get_attribute("data-kin")
    assert home.locator("img").get_attribute("src").endswith(f"/ds/sprites/v3/homes/{kin}.png")
    g, h = _building(pg, gate).bounding_box(), home.bounding_box()
    assert g["x"] + g["width"] <= h["x"] + 1 and abs((g["y"] + g["height"]) - (h["y"] + h["height"])) < g["height"]
    assert home.locator(".gui-camp__name").inner_text() == "Home"          # its name on it, as a building's
    shots = os.environ.get("ORKCRAFT_SHOTS")
    if shots:
        pg.screenshot(path=str(Path(shots) / "i1-home.png"))
    home.click()
    menu = pg.locator(".gui-menu")
    assert menu.locator(".gui-menu__item").all_inner_texts() == ["Since your last look", "You: profile and deeds",
                                                                 "Town settings…"]
    menu.get_by_text("Since your last look").click()
    pg.locator(".gui-lastlook").wait_for(state="visible", timeout=WAIT_MS)
    pg.locator(".gui-lastlook").get_by_role("button", name="Back to the camp").click()
    pg.locator(".gui-lastlook").wait_for(state="hidden", timeout=WAIT_MS)
    home.click()
    menu.get_by_text("You: profile and deeds").click()
    pg.locator(".gui-portrait__menu").wait_for(state="visible", timeout=WAIT_MS)
    pg.keyboard.press("Escape")
    _call(pg, "town.demolish", {"id": gate})


def test_an_item_dragged_from_the_inventory_snaps_to_the_grass_and_stays_after_a_reload(camp_look, gui):
    """v3-prompts §14: the inventory lists the starter set; an item dragged onto the camp shows the grid where it fits,
    snaps to a cell on grass (never on track, paths or against a building), is kept in the town file, and still
    stands after a reload; dragged back to the panel it is put away. Office draws no items."""
    server, _ = gui
    pg = camp_look
    _clear(pg)
    pool = _call(pg, "town.build", {"type": "barracks"})
    pg.keyboard.press("Escape")
    _building(pg, pool).wait_for(state="visible", timeout=WAIT_MS)
    assert pg.locator(".gui-items").count() == 0                         # closed: nothing nags
    pg.get_by_role("button", name="Items", exact=True).click()
    row = pg.locator('.gui-items__row[data-item="tree"]')
    row.wait_for(state="visible", timeout=WAIT_MS)
    b, r = _building(pg, pool).bounding_box(), row.bounding_box()
    pg.mouse.move(r["x"] + 20, r["y"] + 20)
    pg.mouse.down()
    pg.mouse.move(b["x"] + b["width"] / 2, b["y"] + b["height"] / 2, steps=4)   # over the building: no fit
    assert pg.locator(".gui-items__grid").count() == 1                         # the grid shows while dragging
    assert pg.locator(".gui-items__ghost.is-ok").count() == 0
    h = pg.locator(".gui-camp__home").bounding_box()
    target = (h["x"] + h["width"] + 120, h["y"] + h["height"] - 12)            # the row's open grass past the home
    pg.mouse.move(*target, steps=6)
    pg.locator(".gui-items__ghost.is-ok").wait_for(state="visible", timeout=WAIT_MS)
    pg.mouse.up()
    placed = pg.locator('.gui-items__placed[data-item="tree"]')
    placed.wait_for(state="visible", timeout=WAIT_MS)
    assert pg.locator(".gui-items__grid").count() == 0
    kept = [p for p in server.host.town.scroll.items if p["item"] == "tree"]
    assert len(kept) == 1
    import json
    saved = json.loads(server.host.town.config.layout_file.read_text(encoding="utf-8"))   # the town file
    assert any(p["item"] == "tree" for p in saved.get("items", []))
    pg.reload()
    placed.wait_for(state="visible", timeout=WAIT_MS)                          # still there
    box = placed.bounding_box()
    assert abs(box["y"] + box["height"] - target[1]) <= 32                   # its feet in the cell it was dropped on
    _call(pg, "you.look", {"look": "office"})                                  # Office draws no items
    pg.wait_for_function("() => document.documentElement.dataset.look === 'office'", timeout=WAIT_MS)
    assert pg.locator(".gui-items__placed").count() == 0 and pg.get_by_role("button", name="Items", exact=True).count() == 0
    _call(pg, "you.look", {"look": "camp"})
    placed.wait_for(state="visible", timeout=WAIT_MS)
    pg.get_by_role("button", name="Items", exact=True).click()
    panel = pg.locator(".gui-items")
    panel.wait_for(state="visible", timeout=WAIT_MS)
    p = panel.bounding_box()
    pg.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    pg.mouse.down()
    pg.mouse.move(p["x"] + p["width"] / 2, p["y"] + p["height"] / 2, steps=6)
    pg.mouse.up()
    placed.wait_for(state="detached", timeout=WAIT_MS)                         # put back in the inventory
    assert not [x for x in server.host.town.scroll.items if x["item"] == "tree"]
    pg.get_by_role("button", name="Items", exact=True).click()
    _call(pg, "town.demolish", {"id": pool})


def test_a_building_that_takes_an_items_cell_sends_it_back_with_a_line_in_the_panel(camp_look, gui):
    """The PM, 2026-10-14: a new building takes a placed item's cell → the item goes back to the inventory quietly; a
    line waits in the Items panel only, said once it is opened."""
    server, _ = gui
    pg = camp_look
    _clear(pg)
    pool = _call(pg, "town.build", {"type": "barracks"})
    pg.keyboard.press("Escape")
    _building(pg, pool).wait_for(state="visible", timeout=WAIT_MS)
    pg.get_by_role("button", name="Items", exact=True).click()
    r = pg.locator('.gui-items__row[data-item="bush-small"]').bounding_box()
    pg.mouse.move(r["x"] + 20, r["y"] + 20)
    pg.mouse.down()
    h = pg.locator(".gui-camp__home").bounding_box()
    pg.mouse.move(h["x"] + h["width"] + 90, h["y"] + h["height"] - 40, steps=6)   # the row's grass past the home
    pg.locator(".gui-items__ghost.is-ok").wait_for(state="visible", timeout=WAIT_MS)
    pg.mouse.up()
    pg.locator('.gui-items__placed[data-item="bush-small"]').wait_for(state="visible", timeout=WAIT_MS)
    pg.get_by_role("button", name="Items", exact=True).click()                   # closed
    bench = _call(pg, "town.build", {"type": "lab"})                              # joins the row: the home moves on
    pg.keyboard.press("Escape")
    _building(pg, bench).wait_for(state="visible", timeout=WAIT_MS)
    pg.locator('.gui-items__placed[data-item="bush-small"]').wait_for(state="detached", timeout=WAIT_MS)
    assert not [p for p in server.host.town.scroll.items if p["item"] == "bush-small"]
    assert pg.locator(".gui-items__note").count() == 0                          # nothing said until the panel opens
    pg.get_by_role("button", name="Items", exact=True).click()
    note = pg.locator(".gui-items__note")
    note.wait_for(state="visible", timeout=WAIT_MS)
    assert "The Small bush went back to your items when the Test bench was built" in note.inner_text()
    pg.get_by_role("button", name="Items", exact=True).click()                   # seen once closed
    pg.wait_for_function("() => import('/static/js/link.js').then(m => !m.town.value.growth.items.notes.length)", timeout=WAIT_MS)
    for bid in (pool, bench):
        _call(pg, "town.demolish", {"id": bid})


def test_the_camps_bottom_line_stands_above_the_quest_log(camp_look):
    """A panel that stays over the Workchief's line (the quest log, a setup: js/inset.js) is the camp's bottom inset:
    the work is centred above it, and a camp taller than what is left shows its last line, where the carts run."""
    pg = camp_look
    _clear(pg)
    ids = [_call(pg, "town.build", {"type": "forge"}) for _ in range(10)]
    pg.keyboard.press("Escape")
    for bid in ids:
        _building(pg, bid).wait_for(state="visible", timeout=WAIT_MS)
    inset = "import('/static/js/inset.js')"
    lowest = "() => Math.max(...[...document.querySelectorAll('.gui-camp__layer.is-track img, .gui-camp__building img')].map(e => e.getBoundingClientRect().bottom))"
    try:
        pg.evaluate(f"() => {inset}.then(m => {{ m.coverTop.value = 420; }})")
        pg.wait_for_function(f"() => ({lowest})() <= 420", timeout=WAIT_MS)
    finally:
        pg.evaluate(f"() => {inset}.then(m => {{ m.coverTop.value = null; }})")
    pg.wait_for_function(f"() => ({lowest})() > 420", timeout=WAIT_MS)      # no panel: the work is centred again
    for bid in ids:
        _call(pg, "town.demolish", {"id": bid})
