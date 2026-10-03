"""Huts: every camp building has its own silhouette; the name stands above it, the buttons under it."""
from __future__ import annotations

from pathlib import Path

import pytest

from orkcraft import scroll as ts
from orkcraft.app import OrkcraftApp
from orkcraft.realm import catalog, huts, masonry, silhouettes as sil
from orkcraft.widgets.hut import Hut, footprint
from orkcraft.wm import geometry as geo

SIZE = (200, 56)

# the design: (footprint width, the widths of the text slots) per building
DESIGN = {
    "mill": (15, [8]), "catapult": (17, [8]), "horn": (14, [8]), "pit": (9, [1]), "totem": (10, [2, 4]), "watchtower": (10, [8] * 4),
    "fields": (18, [16] * 7), "barracks": (18, [16] * 7), "council": (18, [16] * 7), "forge": (18, [16] * 7),
    "scrolls": (18, [16] * 7), "war_drum": (26, [24] * 9), "forest": (26, [24] * 9), "loot": (26, [24] * 9),
    "crag": (26, [24] * 9), "lake": (60, [58] + [28, 24] * 6 + [58]),
}


@pytest.fixture
def town(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ts, "DEFAULT_VIEW", "town")


async def _settle(pilot, n: int = 4) -> None:
    for _ in range(n):
        await pilot.pause()


def _spec(bid: str, type_: str, **kw) -> dict:
    base = {"id": bid, "title": bid.title(), "icon": "🏗", "orc": {"name": "Peon"}, "type": type_}
    if type_ == "watchtower":
        base["config"] = {"github": "a/b"}
    return {**base, **kw}


def test_every_camp_building_has_the_designed_silhouette():
    camp = {t for t in catalog.TYPES if t not in catalog.SYSTEM_TYPES | catalog.SCRATCH_TYPES and t != "custom"}
    assert camp == set(DESIGN)
    for tid, (width, slots) in DESIGN.items():
        s = sil.of(_spec("x", tid))
        assert s.id == tid and s.width == width, tid
        assert [w for _, _, w in s.slots] == slots, tid
        assert all(len(line) <= s.width for line in s.lines), tid
        drawn = ["".join(t for t, _ in row) for row in s.draw(["a"] * 20)]
        assert len(drawn) == s.height and all(len(row) == s.width for row in drawn), tid
    assert sil.of(_spec("t", "town_hall")).id == "town_hall" and sil.of(_spec("t", "workshop")).id == "workshop"
    assert sil.of(None, "loot").id == "loot" and sil.of(None, "systems").id.startswith("frame")


def test_slots_headings_live_lines_and_fallbacks():
    barracks = sil.SILHOUETTES["barracks"]
    assert barracks.texts(["active: 1/3", "idle: 2"])[:3] == ["WORKER POOL", "active: 1/3", "idle: 2"]
    assert len(barracks.texts([])) == 7 and len(barracks.live_widths) == 6
    mill = sil.SILHOUETTES["mill"]
    assert mill.texts([]) == ["WORKTREE"] and mill.texts(["✓ 05:01"]) == ["✓ 05:01"]
    pit = sil.SILHOUETTES["pit"]
    assert pit.texts(["📄 a.txt"]) == ["█"] and pit.caption_text(["📄 a.txt", "3 in the pit"]) == "📄 a.txt"
    row = "".join(t for t, _ in barracks.draw(["a very long live line that cannot fit"])[3])
    assert row.endswith("…│") and len(row) == barracks.width                 # clipped, the frame intact
    roles = [r for _, r in barracks.draw(["x"])[2]]
    assert "head" in roles and "frame" in roles and "live" in barracks.draw(["x"])[3][1][1]


def test_the_label_is_one_line_with_one_icon_and_one_blank_row():
    one = sil.label(7, "🌾 Task Fields", 18)
    assert one.text == ("7 🌾 Task fields",) and one.lines == ("7 🌾 Task fields", "")
    long = sil.label(3, "🪨 A very long name that has to wrap around", 10)
    assert len(long.text) == 2 and long.text[-1].endswith("…") and long.head.startswith("3 🪨 A very")
    assert sil.label(1, "🔮 Scrying Spire · Diff Inspector", 18).head == "1 🔮 Diff inspector"
    assert sil.label(2, "Plain", 18).head == "2 Plain"                      # no icon


def test_the_hut_stands_label_over_building_buttons_under():
    acts = catalog.quick_actions_of(_spec("a", "crag"))                      # ⇅ Flip, ⟳ Next source
    hut = Hut("a", sil.of(_spec("a", "crag")), acts)
    hut.set_title(5, "🪨 Tally Crag")
    s = hut.sil
    assert (hut.geom.w, hut.geom.h) == (s.width, 2 + s.height + 1) == footprint(s, hut.label, len(acts))
    hut.set_status(["spend 4.04 $", "TOKENS ▇▅▃"])
    lines = str(hut.render()).splitlines()
    assert lines[0].strip() == "5 🪨 Tally crag" and lines[1].strip() == ""     # one line, one blank row
    assert "TELEMETRY & TELEGRAPHS" in lines[3] and "spend 4.04 $" in lines[4]
    assert "Flip" in lines[-1] and "Next" in lines[-1]                       # wide enough: the labels
    x0, _, first = hut._buttons[0]
    assert first == "crag.flip" and hut.action_at(x0, hut.geom.h - 1) == "crag.flip"
    assert hut.action_at(x0, 0) is None and hut.action_at(hut._buttons[1][0], hut.geom.h - 1) == "crag.next"
    small = Hut("s", sil.of(_spec("s", "pit")), acts)                        # 9 wide: glyphs only
    small.set_title(1, "🕳️ The Pit")
    assert str(small.render()).splitlines()[-1].strip() == "[⇅] [⟳]"
    assert small.geom.h == 2 + 3 + 1 + 1                                     # label and gap, silhouette, caption, buttons
    shown = Hut("c", sil.of(_spec("c", "pit")))
    shown.set_status(["📄 a.txt", "3 in the pit"])
    assert str(shown.render()).splitlines()[-1].strip() == "📄 a.txt"


def test_a_custom_building_keeps_a_frame_and_its_roof(monkeypatch):
    monkeypatch.setitem(huts.ROOFS, "gable", ("  /\\  ", " /__\\ "))
    plain = sil.of({"id": "x", "type": "custom", "size": "M"})
    assert plain.width == 18 and plain.grow == "frame" and len(plain.slots) == 3
    roofed = sil.of({"id": "x", "type": "custom", "size": "M", "roof": "gable"})
    assert roofed.height == plain.height + 2 and roofed.lines[0].strip() == "/\\"
    grown = sil.fit(roofed, 6)
    assert len(grown.slots) == 6 and grown.lines[0].strip() == "/\\" and grown.height == 6 + 2 + 2


def test_growing_buildings_follow_their_content_up_to_a_maximum():
    lake = sil.LAKE
    assert len(lake.slots) == 2 + 2 * 6 and sil.fit(lake, 1).height == lake.height   # never below the design
    big = sil.fit(lake, 99)
    assert len(big.slots) == 2 + 2 * sil.GROW_ROWS["lake"][1] and big.height > lake.height
    assert sil.fit(sil.CRAG, 7).height == 7 + 2 and sil.fit(sil.CRAG, 99).height == sil.GROW_ROWS["crag"][1] + 2
    assert sil.fit(sil.MILL, 9) is sil.MILL                                          # a fixed shape stays
    assert sil.rows_needed(sil.LAKE, ["a", "b", "", "", "c", "", "", "", "", "", "", "", "last"]) == 3
    assert sil.rows_needed(sil.CRAG, ["x", "", "y", ""]) == 3


def test_a_hut_that_grows_changes_its_footprint():
    hut = Hut("l", sil.LAKE)
    before = hut.geom.h
    assert hut.set_rows(12) and hut.geom.h == before + 6 and len(hut.live_widths) == 2 * 12 + 1
    hut.set_silhouette(sil.LAKE)                      # a refresh of the spec keeps the grown size
    assert hut.geom.h == before + 6
    assert not Hut("m", sil.MILL).set_rows(9)


def test_ten_roofs_fit_every_frame_size():
    assert len(huts.ROOFS) == 10
    for name in huts.ROOFS:
        for size in catalog.SIZES.values():
            lines = huts.roof(name, size[0] - 4)
            assert 2 <= len(lines) <= 3 and all(len(ln) <= size[0] - 4 for ln in lines), (name, size)
    assert huts.roof("gable", 14)[0].strip() == "/\\" and huts.roof("nope", 14) == ()
    assert catalog.validate(_spec("t", "fields", roof="tower"))[0].startswith("roof: no 'tower'")


def test_shelves_hold_huts_of_every_size_inside_and_apart():
    sizes = [(15, 4), (60, 16), (9, 7), (26, 15), (18, 13), (10, 12), (26, 12), (17, 5), (18, 11)]
    for room in ((200, 50), (140, 40), (100, 30)):
        spots = geo.hut_shelves(*room, sizes)
        assert len(spots) == len(sizes)
        geoms = [geo.Geom(x, y, w, h) for (x, y), (w, h) in zip(spots, sizes)]
        assert all(0 <= g.x and g.x + g.w <= room[0] for g in geoms), room
        if room[0] >= 140:
            assert all(not geo.overlaps(a, b) for i, a in enumerate(geoms) for b in geoms[i + 1:]), room
    taken = [geo.Geom(0, 0, 50, 50)]
    free = geo.first_free(100, 50, 20, 10, taken)
    assert free is not None and not geo.overlaps(free, taken[0], 1, 0)


@pytest.mark.asyncio
async def test_town_with_typed_huts_and_quick_actions(fake_repo: Path, town):
    from orkcraft.screens.console import Console

    for s in (_spec("inbox", "watchtower"), _spec("todo", "fields"), _spec("drop", "pit"), _spec("cal", "war_drum")):
        assert masonry.save_spec(fake_repo, s) == []
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    ran: list[tuple[str, str]] = []
    async with app.run_test(size=SIZE) as pilot:
        await _settle(pilot)
        desk = app.desktop
        for bid, sid in (("todo", "fields"), ("drop", "pit"), ("cal", "war_drum"), ("inbox", "watchtower"),
                         ("loot", "loot"), ("town_hall", "town_hall")):
            hut = desk.huts[bid]
            assert hut.sil.id == sid, bid
            assert (hut.geom.w, hut.geom.h) == footprint(hut.sil, hut.label, len(hut.actions)), bid
        geoms = [h.geom for h in desk.huts.values() if h.display]
        assert all(not geo.overlaps(a, b) for i, a in enumerate(geoms) for b in geoms[i + 1:])
        room_w, room_h = desk.hut_room
        assert all(g.x + g.w <= room_w and g.y + g.h <= room_h for g in geoms if g != desk.huts["town_hall"].geom)
        assert "TODO" in str(desk.huts["todo"].render()) and "WORKER" not in str(desk.huts["todo"].render())

        # a click on the button runs the action and does not open the building
        from orkcraft.screens.dialogs import TextPrompt
        hut = desk.huts["todo"]
        bx = hut._buttons[0][0]
        await pilot.click(hut, offset=(bx, hut.geom.h - 1))                  # the last row: the buttons
        await _settle(pilot)
        assert desk.active is None and isinstance(app.screen, TextPrompt)    # + New task asks for its title
        await pilot.press("escape")
        await _settle(pilot)
        # a click elsewhere opens it
        await pilot.click(hut, offset=(3, 4))
        await _settle(pilot)
        assert desk.active is not None and desk.active.window_id == "todo"
        # the selected building: [ runs its first quick action, the Command Card lists it
        app.run_quick_action = lambda b, a: ran.append((b, a))
        await pilot.press("left_square_bracket")
        await _settle(pilot)
        assert ran == [("todo", "tasks.new")]
        card = app.screen.query_one(Console).query_one("#command-actions")
        rows = [str(card.get_option_at_index(i).prompt) for i in range(card.option_count)]
        assert rows[0] == "[[] + New task"


@pytest.mark.asyncio
async def test_a_lake_grows_with_its_content_and_stays_off_its_neighbours(fake_repo: Path, town):
    from orkcraft.realm import lake as lake_logic

    for s in (_spec("view", "lake"), _spec("todo", "fields"), _spec("drop", "pit"), _spec("cal", "war_drum")):
        assert masonry.save_spec(fake_repo, s) == []
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await _settle(pilot)
        desk = app.desktop
        hut = desk.huts["view"]
        small = hut.geom.h
        body = next(iter(desk.get_window("view").children))
        body.show(lake_logic.View("text", "notes.txt", text="\n".join(f"line {i}" for i in range(40))))
        desk.refresh_huts()
        await _settle(pilot)
        maxed = sil.GROW_ROWS["lake"][1]
        assert hut.geom.h > small and len(hut.sil.slots) == 2 + 2 * maxed          # taller, capped at the maximum
        geoms = [h.geom for h in desk.huts.values() if h.display]
        assert all(not geo.overlaps(a, b) for i, a in enumerate(geoms) for b in geoms[i + 1:])
        room_w, room_h = desk.hut_room
        assert all(g.x + g.w <= room_w and g.y + g.h <= room_h for g in geoms if g != desk.huts["town_hall"].geom)
        body.show(lake_logic.View("text", "short.txt", text="one\ntwo"))
        desk.refresh_huts()
        await _settle(pilot)
        assert hut.geom.h == small                                                 # and back to the design


def test_plain_mode_is_only_a_frame_with_the_same_text_slots():
    for sid, full in sil.SILHOUETTES.items():
        plain = sil.plain(full)
        assert len(plain.slots) == len(full.slots) and plain.width <= full.width, sid
        assert plain.lines[0] == "┌" + "─" * (plain.width - 2) + "┐", sid
        assert plain.lines[-1] == "└" + "─" * (plain.width - 2) + "┘", sid
        assert all(ln[0] == "│" and ln[-1] == "│" for ln in plain.lines[1:-1]), sid
        assert not set("/\\_(@~") & set("".join(plain.lines)), sid                   # no roofs, sails or waves
    assert sil.styled(sil.MILL, False) is sil.MILL and sil.styled(sil.MILL, True).width == 10


@pytest.mark.asyncio
async def test_the_menu_switches_between_immersion_and_plain(fake_repo: Path, town):
    from orkcraft.screens.system_menu import SystemMenu

    for s in (_spec("todo", "fields"), _spec("mill", "mill"), _spec("view", "lake")):
        assert masonry.save_spec(fake_repo, s) == []
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await _settle(pilot)
        desk = app.desktop
        assert not desk.plain and desk.huts["mill"].geom.w == 15
        app.action_system_menu()
        await _settle(pilot)
        assert isinstance(app.screen, SystemMenu)
        ids = [app.screen.query_one("#system-menu-list").get_option_at_index(i).id
               for i in range(app.screen.query_one("#system-menu-list").option_count)]
        assert ids[3:5] == ["immersion", "plain"]
        await pilot.press("5")                                                    # [5] plain
        await _settle(pilot)
        assert desk.plain and desk.scroll.preferences["mode"] == "plain"
        assert desk.huts["mill"].geom.w == 10 and desk.huts["mill"].sil.id.endswith("-plain")
        assert "/" not in str(desk.huts["todo"].render()) and "┌────────────────┐" in str(desk.huts["todo"].render())
        geoms = [h.geom for h in desk.huts.values() if h.display]
        assert all(not geo.overlaps(a, b) for i, a in enumerate(geoms) for b in geoms[i + 1:])
        desk.set_mode(False)
        await _settle(pilot)
        assert not desk.plain and desk.huts["mill"].geom.w == 15
        geoms = [h.geom for h in desk.huts.values() if h.display]
        assert all(not geo.overlaps(a, b) for i, a in enumerate(geoms) for b in geoms[i + 1:])


def test_emoji_in_live_lines_do_not_push_the_frame_out():
    from rich.cells import cell_len
    hut = Hut("h", sil.TOWN_HALL, [])
    hut.set_status(["🛡 all quiet", "🪙 $0.00 / $5", "plain"])
    rows = [ln for ln in str(hut.render()).splitlines() if ln.startswith("│") or ln.lstrip().startswith("│")]
    assert rows and {cell_len(ln.strip()) for ln in rows} == {sil.TOWN_HALL.width}


@pytest.mark.parametrize("sid", sorted(sil.SILHOUETTES))
def test_the_orc_stands_in_the_middle_of_the_edge_and_keeps_the_corners(sid):
    from rich.cells import cell_len
    shape = sil.SILHOUETTES[sid]
    hut = Hut("h", shape, [])
    hut.badge = "🧌 Smith 💤"
    bottom = "".join(p for p, _ in shape.draw([])[-1])
    pieces = hut._orc_in_frame(shape.draw([])[-1])
    (left, _), (mark, role), (right, _) = pieces
    assert role == "orc" and cell_len(left + mark + right) == cell_len(bottom)
    assert left[:1] == bottom[:1] and right == bottom[len(bottom) - len(right):]   # corners, sails and chutes stay
    lead, tail = len(left) - len(left.rstrip("─~_═")), len(right) - len(right.lstrip("─~_═"))
    assert abs(lead - tail) <= (1 if sid == "pit" else 0)                         # a 3-cell pit cannot be exact


@pytest.mark.parametrize("sid", ["fields", "forest", "loot", "town_hall", "workshop", "barracks"])
def test_the_roof_is_symmetric_over_the_frame(sid):
    """(the council is not here: an orc of one cell over a tent of two stands on its left slope)"""
    shape = sil.SILHOUETTES[sid]
    for line in shape.lines:
        if sil.SLOT in line:
            break
        line = line.ljust(shape.width)
        marks = [i for i, ch in enumerate(line) if ch not in " ─┌┐"]
        assert not marks or marks[0] + marks[-1] == shape.width - 1, line
