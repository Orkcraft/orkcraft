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


@pytest.mark.asyncio
async def test_the_inventory_shows_the_model_and_the_tools_and_changes_the_tier(fake_repo):
    import json

    from textual.widgets import OptionList, Select

    from orkcraft.app import OrkcraftApp
    from orkcraft.realm import feedback
    from orkcraft.screens.chronicles_view import UnitChronicles
    from orkcraft.screens.console import orc_key
    from orkcraft.screens.garrison_modal import OrcModelModal

    transcript = fake_repo / "t1.jsonl"
    rows = [{"type": "assistant", "timestamp": f"2026-10-01T10:0{i}:00Z",
             "message": {"id": f"m{i}", "role": "assistant",
                         "content": [{"type": "tool_use", "id": f"t{i}", "name": name, "input": {"command": "x"}}]}}
            for i, name in enumerate(("Bash", "mcp__github__get_file_contents", "Bash"))]
    transcript.write_text("\n".join(json.dumps(r) for r in rows))
    (fake_repo / ".orkcraft").mkdir(exist_ok=True)
    (fake_repo / ".orkcraft" / "sessions.jsonl").write_text(json.dumps(
        {"ts": "2026-10-01T10:00:00", "harness": "claude", "event": "SessionStart", "session": "s1", "tickets": [],
         "cwd": str(fake_repo), "transcript": str(transcript), "prompt": "go", "orc": "town_hall/sage"}) + "\n")
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    ts.add_handler(app.scroll, "town_hall", "Sage", harness=[{"role": "run", "harness": "claude", "tier": "elder"}])
    async with app.run_test(size=(200, 50)) as pilot:
        for _ in range(3):
            await pilot.pause()
        orc = next(o for o in app.roster.orcs if o.ref == "town_hall/sage")
        app.set_focus_state("unit", orc_key_val=orc_key(orc), building_id="town_hall")
        await pilot.pause()
        lst = app.screen.query_one("#roster-list", OptionList)
        prompts = [str(lst.get_option_at_index(i).prompt) for i in range(lst.option_count)]
        assert prompts[0].startswith("🔮 opus") and "⇄" in prompts[0]
        assert "🔧 Bash ×2" in prompts
        assert any(p.startswith("🔧 github·get") and p.endswith("×1") for p in prompts)     # cut to the column
        # a tool: its history, only the runs and calls with it
        lst.focus()
        lst.highlighted = next(i for i, p in enumerate(prompts) if "github" in p)
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, UnitChronicles) and app.screen.tool == "mcp__github__get_file_contents"
        steps = app.screen.query_one("#protocol-steps", OptionList)
        assert steps.option_count == 1
        await pilot.press("escape")
        await pilot.pause()
        # the model button: elder → laborer on agy
        lst.highlighted = 0
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, OrcModelModal)
        app.screen.query_one("#step-harness-0", Select).value = "agy"
        app.screen.query_one("#step-tier-0", Select).value = "laborer"
        await pilot.click("#model-save")
        await pilot.pause()
        sage = next(o for o in app.scroll.building("town_hall").garrison.handlers if o.name == "Sage")
        assert sage.harness == [{"role": "run", "harness": "agy", "tier": "laborer"}]
        # its own 👍
        await pilot.click("#io-like")
        await pilot.pause()
        assert feedback.scores(fake_repo)["town_hall/sage"]["likes"] == 1
