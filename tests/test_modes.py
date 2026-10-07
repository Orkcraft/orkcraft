"""The town's one look: fire, rocks and gold in the terminal, and one word for each concept."""
from __future__ import annotations

from pathlib import Path

import pytest
from rich.cells import cell_len

from orkcraft import scroll as ts
from orkcraft.app import OrkcraftApp
from orkcraft.realm import masonry, modes
from orkcraft.tui import silhouettes as sil
from orkcraft.widgets import carts
from orkcraft.widgets.hud import Hud
from orkcraft.widgets.hut import FIRE, FIRE_GROUND, Hut

SIZE = (200, 56)
ASKING = "🧌 Peon 🔨 🔥"


def test_the_fire_goes_orange_then_red_then_takes_the_roof():
    assert modes.fire_stage(0) == ("orange", 0.0)
    assert modes.fire_stage(modes.FIRE_RED_S) == ("red", 0.0)
    stage, half = modes.fire_stage((modes.FIRE_ROOF_S + modes.FIRE_ROOF_FULL_S) / 2)
    assert stage == "red" and half == pytest.approx(0.5)
    assert modes.fire_stage(modes.FIRE_ROOF_FULL_S * 10) == ("red", 1.0)

    roof = ["    /\\    ", "   /  \\   ", " _/____\\_ "]
    assert modes.burn(roof, 0) == roof
    some, more, all_ = modes.burn(roof, 0.3), modes.burn(roof, 0.7), modes.burn(roof, 1.0)
    count = lambda lines: sum(ln.count("🔥") for ln in lines)                      # noqa: E731
    assert 0 < count(some) < count(more) < count(all_)
    assert all(cell_len(ln) == len(r) for ln, r in zip(all_, roof))               # the width stays
    assert not any(set(ln) - set("🔥 ") for ln in all_)                           # nothing left unburnt
    lit = {(r, c) for r, ln in enumerate(some) for c, ch in enumerate(ln) if ch == "🔥"}
    assert lit and modes.burn(roof, 0.3) == some                                  # the same every redraw


def _roof(hut: Hut) -> str:
    return "\n".join(str(hut.render()).splitlines()[len(hut.label.lines):len(hut.label.lines) + 3])


def _styles(hut: Hut) -> set[str]:
    return {str(span.style) for span in hut.render().spans}


def test_a_hut_left_waiting_burns_and_the_whole_card_takes_the_colour():
    hut = Hut("w", sil.WATCHTOWER, [])
    hut.set_title(1, "🗼 Tower")
    hut.set_badge(ASKING, now=0.0)
    assert hut.on_fire and hut.has_class("-alert") and not hut.has_class("-burning")
    name = hut.render().spans[0]
    assert str(name.style) == FIRE[0]                                            # the name: orange letters only
    assert _styles(hut) == {FIRE[0], f"{FIRE[0]} on {FIRE_GROUND[0]}"}            # the building: on an orange ground
    hut.update_fire(now=modes.FIRE_RED_S + 1)
    assert hut.has_class("-burning") and "🔥" not in _roof(hut)
    assert _styles(hut) == {f"bold {FIRE[1]}", f"bold {FIRE[1]} on {FIRE_GROUND[1]}"}
    hut.update_fire(now=(modes.FIRE_ROOF_S + modes.FIRE_ROOF_FULL_S) / 2)
    half = _roof(hut).count("🔥")
    hut.update_fire(now=modes.FIRE_ROOF_FULL_S)
    assert 0 < half < _roof(hut).count("🔥")
    assert "/" not in _roof(hut)                                                 # the roof is all fire
    assert "│" in str(hut.render())                                             # the walls still stand

    hut.set_badge("🧌 Peon 🔨 💤")                                               # answered: the fire is out
    assert not hut.on_fire and not hut.has_class("-burning") and "🔥" not in str(hut.render())


def test_carts_are_rocks_on_the_ground_of_their_status():
    assert carts.cart_look("sent").plain == carts.cart_look("error").plain == "🪨"
    assert "#7f1d1d" in str(carts.cart_look("error").style)


@pytest.mark.asyncio
async def test_the_hud_shows_gold_lumber_and_meat(fake_repo: Path):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        hud = app.query_one(Hud)
        hud.resources.alerts = 2
        hud.update_hud()
        text = str(hud.render())
        assert "🪙" in text and "🪵" in text and "🥩" in text and "🔥 2 awaiting an answer" in text and "🧌" in text


@pytest.mark.asyncio
async def test_a_scroll_with_an_old_look_opens_in_the_one_look(fake_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(ts, "DEFAULT_VIEW", "town")
    assert masonry.save_spec(fake_repo, {"id": "mill", "title": "Mill", "icon": "🏗", "orc": {"name": "Peon"},
                                         "type": "mill"}) == []
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        data = app.desktop.scroll.to_dict()
        data["preferences"]["mode"] = "plain"                     # an older scroll's look
        back = ts.TownScroll.from_dict(data)
        assert "mode" not in back.preferences and "mode" not in back.to_dict()["preferences"]
        hut = app.desktop.huts["mill"]
        assert hut.sil is sil.MILL and not hut.sil.id.endswith("-plain")       # the building wears its ASCII


def test_emoji_go_and_the_text_stays():
    assert modes.strip_emoji("🌾 Task fields") == "Task fields"
    assert modes.strip_emoji("[🪙 $1 / $5]") == "[$1 / $5]"
    assert modes.strip_emoji("✓ all reviewed · 02:15 → done") == "✓ all reviewed · 02:15 → done"
    assert modes.strip_emoji(" 👍 ") == "+1" and modes.strip_emoji(" 🗑 ") == "Delete"
    assert modes.strip_emoji("🗑️ Scroll dump") == "Scroll dump"
    assert modes.strip_emoji("0 results · 👍 3 👎 1") == "0 results · +3 −1"                    # an icon in a name just goes
    assert modes.plain("🌾 Fields") == "Fields" and modes.plain("🗼 Watchtower") == "External listeners"


def test_a_hut_says_todays_words_and_keeps_its_icons():
    from orkcraft.realm.catalog import ActionDef
    hut = Hut("w", sil.WATCHTOWER, [ActionDef("a", "Preset", "📜", "")])
    hut.set_title(9, "🗼 Watchtower")
    hut.set_status(["🛡 all quiet", "🪙 gold $1"])
    hut.set_badge("🧌 Peon 🔨 💤")
    out = hut.render().plain
    assert "🗼 External listeners" in out and "Watchtower" not in out                # the name in today's words
    assert "🪙 spend $1" in out and "🛡 all quiet" in out and "[📜 Preset]" in out and "🧌" in out


@pytest.mark.asyncio
async def test_a_question_on_another_orkspace_lights_its_row_and_opens_on_arrival(
        fake_repo: Path, monkeypatch: pytest.MonkeyPatch):
    from textual.widgets import OptionList

    from orkcraft.realm.orcs import Alert, Orc
    from orkcraft.realm.roster import Roster
    from orkcraft.screens.console import orc_key
    from orkcraft.screens.orders import AwaitingOrdersModal

    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        ts.new_orkspace(app.scroll, "Lab", "ice")
        ts.move_building(app.scroll, "loot", "lab")
        old = Alert("q-old", "Merge the hotfix?", options=[("1", "Yes"), ("2", "No")])
        new = Alert("q-new", "Which branch?")
        roster = Roster(orcs=[Orc("Smith", "resident", "resident", status="alert", building="loot", alert=new, ref="loot/smith"),
                              Orc("Grok", "resident", "resident", status="alert", building="loot", alert=old, ref="loot/grok")],
                        alerts=[new, old])
        # the questions stay while the roster is rebuilt each second (the timer holds the real refresh_roster)
        monkeypatch.setattr(app.muster, "rebuild", lambda *a, **k: setattr(app.muster, "roster", roster))
        app.alert_first_seen.update({"q-old": 1.0, "q-new": 2.0})                  # Grok has waited longer
        app.refresh_roster()
        app._console.refresh_state(app.focus_state, app.roster)
        await pilot.pause()

        rows = app.query_one("#warmap-list", OptionList)
        lab = next(rows.get_option_at_index(i) for i in range(rows.option_count)
                   if rows.get_option_at_index(i).id == "orkspace:lab")
        assert "#ff8c1a" in str(lab.prompt.style) and "🔥" in lab.prompt.plain       # the row is on fire

        app.desktop.switch_orkspace("lab")
        for _ in range(4):
            await pilot.pause()
        assert isinstance(app.screen, AwaitingOrdersModal)
        assert [a.id for a in app.screen.alerts] == ["q-old", "q-new"]               # all of them, the oldest first
        assert app.focus_state.mode == "unit" and app.focus_state.building_id == "loot"
        assert app.focus_state.orc_key == orc_key(roster.orcs[1])                   # the orc who has waited longest
        assert app.desktop.selected_hut in ("loot", None)                            # selected when the town shows it

        await pilot.press("escape")
        await pilot.pause()
        app.desktop.switch_orkspace("main_camp")
        await pilot.pause()
        assert not isinstance(app.screen, AwaitingOrdersModal)                      # nothing asks on the main camp
