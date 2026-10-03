"""🧭 Onboarding: tools → mode → town → raising it (docs/design/onboarding.md)."""
from __future__ import annotations

from pathlib import Path

import pytest
from textual.widgets import Button, Checkbox, Input, OptionList, Select

from orkcraft import settings, tools
from orkcraft import app as app_mod
from orkcraft.app import OrkcraftApp
from orkcraft.realm import town_presets
from orkcraft.realm.buildings import TOWN_HALL
from orkcraft.screens import onboarding
from orkcraft.screens.onboarding import ModeStep, RaiseBar, ToolsStep, TownStep
from orkcraft.wm import Window

SIZE = (160, 50)


def _statuses() -> list[tools.ToolStatus]:
    by_id = {t.id: t for t in tools.TOOLS}
    return [tools.ToolStatus(by_id["claude"], found=True, path="/usr/bin/claude", version="2.1.4", logged_in=True),
            tools.ToolStatus(by_id["agy"], found=False),
            tools.ToolStatus(by_id["codex"])]


@pytest.fixture
def onboard(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORKCRAFT_ONBOARDING", "1")
    monkeypatch.setattr(onboarding, "STEP_PAUSE_S", 0)
    monkeypatch.setattr(tools, "detect", lambda *a, **k: _statuses())

    def no_model(prompt, model=None):
        raise RuntimeError("no model in tests")
    monkeypatch.setattr(app_mod, "BUILD_RUNNER", no_model)


async def _settle(pilot, n: int = 6) -> None:
    for _ in range(n):
        await pilot.pause()


async def _until(pilot, cond, n: int = 60) -> None:
    for _ in range(n):
        if cond():
            return
        await pilot.pause(0.05)
    assert cond()


async def _press(app, pilot, button_id: str) -> None:
    app.screen.query_one(f"#{button_id}", Button).press()
    await _settle(pilot)


def test_every_domain_has_four_stub_presets_and_a_mascot():
    assert [d.mascot for d in town_presets.DOMAINS] == ["orc", "elf", "knight", "skeleton"]
    for d in town_presets.DOMAINS:
        found = town_presets.of_domain(d.id)
        assert len(found) == 4 and all(p.stub for p in found), d.id
        assert len({len(line) for line in d.art}) == 1
    assert town_presets.buildings_of("solo_forge") == ()


def test_the_order_waits_until_seen(tmp_path: Path):
    assert town_presets.pending_order(tmp_path) is None
    town_presets.save_order(tmp_path, "  a town for my podcast  ", "indie")
    order = town_presets.pending_order(tmp_path)
    assert order["prompt"] == "a town for my podcast" and order["domain"] == "indie" and not order["seen"]
    town_presets.mark_order_seen(tmp_path)
    assert town_presets.pending_order(tmp_path)["seen"]


def test_raising_steps_are_real_work():
    assert onboarding.raising_steps({"preset": "empty", "warder": False}) == [
        "Opening the camp's records", "Raising the buildings"]
    assert onboarding.raising_steps({"preset": "custom", "warder": True}) == [
        "Opening the camp's records", "Installing the 🛡 Warder", "Raising the buildings",
        "Leaving your order in the Town Hall"]


def test_the_mode_cards_show_the_same_rows():
    rich, plain = onboarding.card_art(False).plain, onboarding.card_art(True).plain
    assert "tests: 42 ok" in rich and "tests: 42 ok" in plain
    assert "oOO" in rich and "oOO" not in plain


@pytest.mark.asyncio
async def test_the_whole_flow_on_a_new_machine(fake_repo: Path, onboard):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await _until(pilot, lambda: isinstance(app.screen, ToolsStep) and app.screen.statuses is not None)
        await _settle(pilot)
        step = app.screen
        assert step.query_one("#ob-tool-claude", Checkbox).value                 # found: checked
        assert step.query_one("#ob-tool-agy", Checkbox).disabled                 # missing: greyed
        assert step.query_one("#ob-tool-codex", Checkbox).disabled               # coming soon
        step.query_one("#ob-billing-claude", Select).value = "api"
        await _press(app, pilot, "ob-next")

        assert isinstance(app.screen, ModeStep) and app.screen.mode == "camp"
        app.screen.pick("office")
        await _press(app, pilot, "ob-next")
        machine = settings.load()
        assert machine.onboarded and machine.mode == "office"
        assert machine.tools["claude"].enabled and machine.tools["claude"].billing == "api"
        assert app.desktop.plain

        assert isinstance(app.screen, TownStep)
        town = app.screen
        assert town.query_one("#ob-warder", Checkbox).value
        town.query_one("#ob-domain", Select).value = "design"
        await _settle(pilot)
        ids = [town.query_one("#ob-presets", OptionList).get_option_at_index(i).id
               for i in range(town.query_one("#ob-presets", OptionList).option_count)]
        assert ids == ["mockup_grove", "design_system", "asset_pipeline", "critique_circle", "custom"]
        assert "ELF" in str(town.query_one("#ob-mascot").render())
        assert not town.query_one("#ob-prompt", Input).display
        await _press(app, pilot, "ob-build")

        await _until(pilot, lambda: (fake_repo / ".orkcraft" / ".git").exists() and app.query(RaiseBar)
                     and "stands" in str(app.query_one("#raise-label").render()))
        assert (fake_repo / ".claude" / "settings.json").exists()                # the Warder
        assert Path(app.config.layout_file).exists()                              # the Town Scroll
        assert not isinstance(app.screen, (ToolsStep, ModeStep, TownStep))


@pytest.mark.asyncio
async def test_a_town_in_words_waits_in_the_town_hall(fake_repo: Path, onboard):
    settings.save(settings.MachineSettings(onboarded=True,
                                           tools={**settings.MachineSettings().tools,
                                                  "agy": settings.ToolChoice(enabled=True)}))
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await _until(pilot, lambda: isinstance(app.screen, TownStep) and app.screen.query("#ob-presets")
                     and app.screen.query_one("#ob-presets", OptionList).option_count)
        town = app.screen
        assert not town.query(".ob-buttons #ob-back")                            # nothing before it
        assert not town.query_one("#ob-warder", Checkbox).display                # no claude: no Warder
        lst = town.query_one("#ob-presets", OptionList)
        lst.highlighted = lst.option_count - 1
        await _settle(pilot)
        assert town.query_one("#ob-prompt", Input).display
        await _press(app, pilot, "ob-build")
        assert isinstance(app.screen, TownStep)                                  # empty prompt: refused
        town.query_one("#ob-prompt", Input).value = "a town for my podcast"
        await _press(app, pilot, "ob-build")
        await _until(pilot, lambda: town_presets.pending_order(fake_repo) is not None and app.order_burning)
        assert not (fake_repo / ".claude" / "settings.json").exists()
        app.refresh_roster()
        hall = app.desktop.get_window(TOWN_HALL)
        assert "🔥" in hall.badge
        app.desktop.post_message(Window.Activated(hall))                          # opened, as a click does
        await _settle(pilot)
        assert not app.order_burning and town_presets.pending_order(fake_repo)["seen"]


@pytest.mark.asyncio
async def test_skip_gives_an_empty_town_and_no_warder(fake_repo: Path, onboard):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await _until(pilot, lambda: isinstance(app.screen, ToolsStep) and app.screen.statuses is not None)
        await _settle(pilot)
        await _press(app, pilot, "ob-skip")
        await _until(pilot, lambda: Path(app.config.layout_file).exists())
        machine = settings.load()
        assert machine.onboarded and machine.mode == "camp" and machine.tools["claude"].enabled
        assert not (fake_repo / ".claude" / "settings.json").exists()


@pytest.mark.asyncio
async def test_back_goes_to_the_previous_step(fake_repo: Path, onboard):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await _until(pilot, lambda: isinstance(app.screen, ToolsStep) and app.screen.statuses is not None)
        await _settle(pilot)
        await _press(app, pilot, "ob-next")
        await _press(app, pilot, "ob-next")
        assert isinstance(app.screen, TownStep)
        await _press(app, pilot, "ob-back")
        assert isinstance(app.screen, ModeStep)
        await _press(app, pilot, "ob-back")
        await _until(pilot, lambda: isinstance(app.screen, ToolsStep) and app.screen.statuses is not None)


@pytest.mark.asyncio
async def test_f10_redoes_only_the_machine_steps(fake_repo: Path, onboard, monkeypatch):
    monkeypatch.setenv("ORKCRAFT_ONBOARDING", "0")
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await _settle(pilot)
        assert not isinstance(app.screen, ToolsStep)
        app.start_onboarding(machine_steps=True, town_step=False)
        await _until(pilot, lambda: isinstance(app.screen, ToolsStep) and app.screen.statuses is not None)
        await _settle(pilot)
        await _press(app, pilot, "ob-next")
        await _press(app, pilot, "ob-next")
        assert not isinstance(app.screen, (ToolsStep, ModeStep, TownStep))
        assert settings.load().onboarded


def test_no_onboarding_for_a_project_with_a_town(fake_repo: Path, onboard):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    Path(app.config.layout_file).write_text("{}", encoding="utf-8")
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    assert not app.first_run


@pytest.mark.asyncio
async def test_the_hud_shows_limits_for_a_subscription(fake_repo: Path):
    choice = settings.MachineSettings(onboarded=True)
    choice.tools["claude"] = settings.ToolChoice(enabled=True, billing="subscription")
    settings.save(choice)
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await _settle(pilot)
        app.refresh_hud()
        r = app._hud.resources
        assert r.quota == "claude —" and not r.show_gold
        app.desktop.machine.tools["agy"] = settings.ToolChoice(enabled=True, billing="api")
        app.refresh_hud()
        assert app._hud.resources.show_gold


@pytest.mark.asyncio
async def test_a_town_in_words_goes_to_the_town_builder(fake_repo: Path, onboard, monkeypatch):
    from orkcraft.screens.town_plan import TownPlanReview
    from tests.test_town_builder import GOOD, _runner
    monkeypatch.setattr(app_mod, "BUILD_RUNNER", _runner(GOOD))
    settings.save(settings.MachineSettings(onboarded=True))
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await _until(pilot, lambda: isinstance(app.screen, TownStep) and app.screen.query("#ob-presets")
                     and app.screen.query_one("#ob-presets", OptionList).option_count)
        lst = app.screen.query_one("#ob-presets", OptionList)
        lst.highlighted = lst.option_count - 1
        await _settle(pilot)
        app.screen.query_one("#ob-prompt", Input).value = "a town for my podcast"
        await _press(app, pilot, "ob-build")
        await _until(pilot, lambda: isinstance(app.screen, TownPlanReview), n=120)
