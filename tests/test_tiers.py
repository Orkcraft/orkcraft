"""Orc tiers: 🔮 elder · ⚔ warrior · ⛏ laborer — the model follows the tier, the icon the model,
and a steward shows none."""
from __future__ import annotations

import pytest

from orkcraft import scroll as ts
from orkcraft.realm import barracks, team, tiers
from orkcraft.realm.orcs import RESIDENT, Orc
from orkcraft.realm.unit_info import models_of
from tests.test_road_engine import PRESETS, Rig, node, wait_for


def test_tier_of_a_model():
    assert [tiers.tier_of_model(m) for m in ("claude-opus-4-1", "gemini-3.1-pro-high")] == ["elder", "elder"]
    assert [tiers.tier_of_model(m) for m in ("sonnet", "gemini-3.8-flash-high")] == ["warrior", "warrior"]
    assert [tiers.tier_of_model(m) for m in ("haiku", "gemini-3.8-flash-low")] == ["laborer", "laborer"]
    assert tiers.tier_of_model("") is None and tiers.tier_of_model("gpt-x") is None


def test_the_model_follows_the_tier_and_a_named_model_wins():
    assert tiers.step_model({"harness": "claude", "tier": "elder"}) == "opus"
    assert tiers.step_model({"harness": "agy", "tier": "laborer"}) == "gemini-3.8-flash-low"
    assert tiers.step_model({"harness": "claude", "tier": "elder", "model": "haiku"}) == "haiku"
    assert tiers.step_model({"harness": "claude"}) == ""                   # the CLI's own default
    assert tiers.step_tier({"harness": "agy"}) == "warrior"                 # agy defaults to flash-high
    assert tiers.with_tier([{"role": "run", "harness": "claude", "model": "x"}], "laborer") == \
        [{"role": "run", "harness": "claude", "tier": "laborer"}]
    assert tiers.with_tier([{"role": "run", "harness": "claude", "tier": "elder"}], None) == \
        [{"role": "run", "harness": "claude"}]


def test_an_orc_shows_its_heaviest_tier_but_a_steward_none():
    steps = [{"role": "write", "harness": "agy", "tier": "laborer"},
             {"role": "review", "harness": "claude", "tier": "elder"}]
    handler = Orc("Smith", "code", RESIDENT, harness=steps)
    assert handler.tier == "elder" and handler.tier_icon == "🔮"
    assert handler.badge.startswith("🧌 🔮 Smith")
    steward = Orc("Chief", "keeps it", RESIDENT, lead=True, harness=steps)
    assert steward.tier == "elder" and steward.tier_icon == "" and steward.badge.startswith("🧌 Chief")
    assert Orc("Scribe", "", RESIDENT, kind="chain").tier_icon == ""
    assert [label for _, _, label in models_of(handler)] == ["write · gemini 3.8 flash", "review · opus"]


def test_the_scroll_keeps_a_tier_and_recruit_sets_it():
    scroll = ts.default_scroll(PRESETS)
    orc = ts.recruit(scroll, "scrying", "Grunt", tier="laborer")
    assert orc.harness == [{"role": "run", "harness": "claude", "tier": "laborer"}]
    assert ts.validate(scroll.to_dict()) == []
    ts.update_orc(scroll, "scrying", orc.id, harness=tiers.with_tier(orc.harness, "warrior"))
    again = ts.TownScroll.from_dict(scroll.to_dict())
    assert next(o for o in again.building("scrying").garrison.members if o.id == orc.id).harness[0]["tier"] == "warrior"
    with pytest.raises(ValueError):
        ts.update_orc(scroll, "scrying", orc.id, harness=[{"role": "run", "harness": "claude", "tier": "wizard"}])


def test_the_engine_runs_a_step_on_its_tiers_model():
    scroll = ts.default_scroll(PRESETS)
    ts.add_handler(scroll, "scrying", "Seer", orders="summarise", run={"quiet_s": 0},
                   harness=[{"role": "run", "harness": "claude", "tier": "laborer"}])
    ts.subscribe(scroll, "scrying", "forge", "on_selection_change", handler="seer")
    models: list[str] = []
    rig = Rig(scroll, lambda harness, prompt, repo, env, cancel, model="": (models.append(model) or "ok", 0.0))
    rig.engine.emit(node("T1001"))
    rig.engine.tick()
    wait_for(lambda: rig.runs)
    assert models == ["haiku"]


def test_barracks_and_council_take_a_tier_for_a_model():
    assert barracks.parse_provider("claude:elder") == ("claude", "opus")
    assert barracks.PoolOrc("Grok", "agy", "gemini-3.8-flash-low").tier_icon == "⛏"
    member = team.parse_member("Critic:claude:elder")
    assert member is not None and member.model == "opus" and member.tier_icon == "🔮"
    assert team.parse_member("Author:claude").tier_icon == ""


@pytest.mark.asyncio
async def test_recruit_by_hand_with_a_tier_shows_its_icon_in_the_roster(fake_repo):
    from textual.widgets import Input, OptionList, Select

    from orkcraft.app import OrkcraftApp
    from orkcraft.screens.garrison_modal import GarrisonModal

    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=(200, 50)) as pilot:
        for _ in range(3):
            await pilot.pause()
        await pilot.press(str(app.desktop.get_window("town_hall").number))
        await pilot.pause()
        await pilot.press("R")
        await pilot.pause()
        assert isinstance(app.screen, GarrisonModal)
        assert app.screen.query_one("#recruit-tier", Select).value == "warrior"     # the default
        app.screen.query_one("#recruit-name", Input).value = "Sage"
        app.screen.query_one("#recruit-tier", Select).value = "elder"
        await pilot.click("#recruit-submit")
        for _ in range(3):
            await pilot.pause()
        sage = next(o for o in app.scroll.building("town_hall").garrison.handlers if o.name == "Sage")
        assert sage.harness == [{"role": "run", "harness": "claude", "tier": "elder"}]
        app.refresh_roster()
        await pilot.pause()
        lst = app.screen.query_one("#roster-list", OptionList)
        rows = [str(lst.get_option_at_index(i).prompt) for i in range(lst.option_count)]
        assert any("🔮 Sage" in r for r in rows)
        assert not any("★ 🔮" in r or "★ ⚔" in r or "★ ⛏" in r for r in rows)      # the steward: none
        app.open_unit(app.desktop.get_window("town_hall"), sage)                     # orders: change the tier
        await pilot.pause()
        assert app.screen.query_one("#unit-tier", Select).value == "elder"
        app.screen.query_one("#unit-tier", Select).value = "laborer"
        await pilot.click("#unit-save")
        await pilot.pause()
        assert sage.harness == [{"role": "run", "harness": "claude", "tier": "laborer"}]
        steward = app.scroll.building("town_hall").garrison.steward
        app.open_unit(app.desktop.get_window("town_hall"), steward)                  # a steward: no picker
        await pilot.pause()
        assert not app.screen.query("#unit-tier")
