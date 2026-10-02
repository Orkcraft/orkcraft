"""Hut v2 (T1105 stage 2): a hut's size from its type, its roof, quick actions on the hut."""
from __future__ import annotations

from pathlib import Path

import pytest

from orkcraft import scroll as ts
from orkcraft.app import OrkcraftApp
from orkcraft.realm import catalog, huts, masonry
from orkcraft.widgets.hut import LEGACY_SIZE, Hut
from orkcraft.wm import geometry as geo

SIZE = (200, 50)


@pytest.fixture
def town(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ts, "DEFAULT_VIEW", "town")


async def _settle(pilot, n: int = 4) -> None:
    for _ in range(n):
        await pilot.pause()


def _spec(bid: str, type_: str, **kw) -> dict:
    base = {"id": bid, "title": bid.title(), "icon": "🏗", "orc": {"name": "Peon"}, "type": type_}
    if type_ == "mail":
        base["config"] = {"host": "imap.example.com", "user_env": "U", "password_env": "P"}
    return {**base, **kw}


def test_shape_from_the_type():
    assert huts.shape_for(None) == (LEGACY_SIZE, (), [])                         # built-ins keep T1102's hut
    assert huts.shape_for({"id": "x"})[0] == LEGACY_SIZE                           # custom of old too
    size, roof, actions = huts.shape_for(_spec("t", "tasks"))
    assert size == catalog.SIZES["M"] and roof == () and [a.id for a in actions] == ["tasks.new"]
    assert huts.shape_for(_spec("t", "tasks", size="L"))[0] == catalog.SIZES["L"]
    assert huts.shape_for(_spec("t", "tasks", quick_actions=[]))[2] == []


def test_hut_layout_rows_buttons_and_hits(monkeypatch):
    acts = catalog.quick_actions_of(_spec("a", "crag"))                           # ⇅ Flip, ⟳ Next source
    hut = Hut("a", huts.art("workshop"), size=catalog.SIZES["S"], actions=acts)
    assert (hut.geom.w, hut.geom.h) == catalog.SIZES["S"]
    assert hut.status_lines == catalog.SIZES["S"][1] - 3                          # fence 2 + action row
    hut.set_status(["last run ok · 2 min ago", "skill: review diffs", "x", "y", "z"])
    lines = str(hut.render()).splitlines()
    assert len(lines) == hut.geom.h - 2 and lines[-1].startswith("[⇅")           # buttons on the last row
    assert all(len(s) <= hut.inner_w for s in hut.status)
    x0, x1, first = hut._buttons[0]
    assert first == "crag.flip" and hut.action_at(x0, hut.geom.h - 3) == "crag.flip"
    assert hut.action_at(x0, 0) is None and hut.action_at(hut._buttons[1][0], hut.geom.h - 3) == "crag.next"
    # wide enough: labels; narrow: glyphs only
    wide = Hut("w", (), size=catalog.SIZES["L"], actions=acts)
    assert "Flip" in str(wide.render()).splitlines()[-1]
    small = Hut("s", (), size=(10, 7), actions=acts)
    assert str(small.render()).splitlines()[-1].strip() == "[⇅] [⟳]"
    # a roof adds its rows on top
    monkeypatch.setitem(huts.ROOFS, "gable", ("  /\\  ", " /__\\ "))
    roofed = Hut("r", (), size=catalog.SIZES["S"], roof=huts.roof("gable"), actions=acts)
    assert roofed.geom.h == catalog.SIZES["S"][1] + 2
    assert str(roofed.render()).splitlines()[0].strip() == "/\\"


def test_ten_roofs_fit_every_hut_size():
    assert len(huts.ROOFS) == 10
    for name in huts.ROOFS:
        for size in catalog.SIZES.values():
            lines = huts.roof(name, size[0] - 4)
            assert 2 <= len(lines) <= 3 and all(len(ln) <= size[0] - 4 for ln in lines), (name, size)
    assert huts.roof("gable", 14)[0].strip() == "/\\" and huts.roof("nope", 14) == ()
    size, roof, _ = huts.shape_for(_spec("t", "tasks", roof="snow"))
    assert roof == huts.roof("snow", size[0] - 4)
    assert catalog.validate(_spec("t", "tasks", roof="tower"))[0].startswith("roof: no 'tower'")


def test_a_narrow_hut_clips_the_name_before_it_drops_it():
    hut = Hut("a", (), size=(14, 7))                         # room for 9 cells
    hut.set_title(4, "🤖 Reviewer")
    assert hut.border_title.startswith("4 🤖 R") and hut.border_title.endswith("…")
    wide = Hut("w", (), size=(26, 7))
    wide.set_title(4, "🤖 Reviewer")
    assert wide.border_title == "4 🤖 Reviewer"
    tiny = Hut("t", (), size=(8, 5))
    tiny.set_title(12, "🤖 Reviewer")
    assert "Reviewer" not in tiny.border_title and "🤖" in tiny.border_title


@pytest.mark.asyncio
async def test_town_with_typed_huts_and_quick_actions(fake_repo: Path, town):
    from orkcraft.screens.console import Console

    for s in (_spec("inbox", "mail"), _spec("todo", "tasks"), _spec("drop", "dropzone"), _spec("cal", "calendar")):
        assert masonry.save_spec(fake_repo, s) == []
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    ran: list[tuple[str, str]] = []
    async with app.run_test(size=SIZE) as pilot:
        await _settle(pilot)
        desk = app.desktop
        assert (desk.huts["todo"].geom.w, desk.huts["todo"].geom.h) == catalog.SIZES["M"]
        assert (desk.huts["drop"].geom.w, desk.huts["drop"].geom.h) == catalog.SIZES["XS"]
        assert (desk.huts["cal"].geom.w, desk.huts["cal"].geom.h) == catalog.SIZES["L"]
        assert (desk.huts["loot"].geom.w, desk.huts["loot"].geom.h) == LEGACY_SIZE
        geoms = [h.geom for h in desk.huts.values() if h.display]
        assert all(not geo.overlaps(a, b) for i, a in enumerate(geoms) for b in geoms[i + 1:])
        room_w, room_h = desk.hut_room
        assert all(g.x + g.w <= room_w and g.y + g.h <= room_h for g in geoms)

        # a click on the button runs the action and does not open the building
        from orkcraft.screens.dialogs import TextPrompt
        hut = desk.huts["todo"]
        bx = hut._buttons[0][0]
        await pilot.click(hut, offset=(2 + bx, hut.geom.h - 2))       # border + padding, last content row
        await _settle(pilot)
        assert desk.active is None and isinstance(app.screen, TextPrompt)    # + New task asks for its title
        await pilot.press("escape")
        await _settle(pilot)
        # a click elsewhere opens it
        await pilot.click(hut, offset=(3, 1))
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
