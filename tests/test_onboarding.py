"""🧭 Onboarding for an indie maker: your AI tools → your day → the town (docs/design/onboarding.md)."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from textual.widgets import Button, Checkbox, Input, OptionList, Select

from orkcraft import autonomy, schedule, settings, tools
from orkcraft import app as app_mod
from orkcraft.app import OrkcraftApp
from orkcraft.realm import intents, interview, town_builder, town_presets
from orkcraft.realm.buildings import TOWN_HALL
from orkcraft.screens import onboarding
from orkcraft.screens.onboarding import IntentStep, ModeStep, RaiseBar, ToolsStep
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
    monkeypatch.setattr(tools, "detect_others", lambda *a, **k: [o for o in tools.OTHERS if o.id == "cursor"])

    def no_model(prompt, model=None):
        raise RuntimeError("no model in tests")
    monkeypatch.setattr(app_mod, "BUILD_RUNNER", no_model)


def _on_github(repo: Path) -> None:
    subprocess.run(["git", "remote", "add", "origin", "https://github.com/me/thing.git"], cwd=str(repo), check=True,
                   capture_output=True)


async def _settle(pilot, n: int = 6) -> None:
    for _ in range(n):
        await pilot.pause()


async def _until(pilot, cond, n: int = 80) -> None:
    for _ in range(n):
        try:
            if cond():
                return
        except Exception:                 # a screen's children may not be in yet
            pass
        await pilot.pause(0.05)
    assert cond()


async def _press(app, pilot, button_id: str) -> None:
    app.screen.query_one(f"#{button_id}", Button).press()
    await _settle(pilot)


async def _on(pilot, app, screen_type) -> None:
    await _until(pilot, lambda: isinstance(app.screen, screen_type))
    await _settle(pilot)


async def _pick(app, pilot, list_id: str, option_id: str) -> None:
    onboarding._highlight(app.screen.query_one(f"#{list_id}", OptionList), option_id)
    await _settle(pilot)


def _title(app) -> str:
    return str(app.screen.query_one(".build-title").render())


async def _tools_ready(app, pilot) -> None:
    await _until(pilot, lambda: isinstance(app.screen, ToolsStep) and app.screen.detected is not None)
    await _settle(pilot)


async def _town_ready(app, pilot) -> None:
    await _on(pilot, app, IntentStep)
    await _until(pilot, lambda: app.screen.query_one("#ob-presets", OptionList).option_count)


def _presets(app) -> list[str]:
    lst = app.screen.query_one("#ob-presets", OptionList)
    return [lst.get_option_at_index(i).id for i in range(lst.option_count)]


# -- the data -------------------------------------------------------------------------------------

def test_every_intent_is_a_town_the_builder_would_accept(tmp_path: Path):
    for it in intents.INTENTS:
        plan, problems = town_builder.check(it.plan, tmp_path, set())
        assert not problems, (it.id, problems)
        assert len(plan.specs) >= 2


def test_the_indie_maker_is_the_one_role_for_now():
    assert [r.id for r in intents.ROLES] == [intents.FOUNDER]
    assert [i.id for i in intents.for_role(intents.FOUNDER)] == ["one_skeleton_studio", "inbox_keep", "side_quest"]
    assert intents.nick(intents.FOUNDER) == "Indie Knight" and "KNIGHT" in "\n".join(intents.mascot("founder"))
    assert intents.role("aso_manager").id == intents.FOUNDER                     # a profile kept from before
    assert len({len(line) for line in intents.mascot(intents.FOUNDER)}) == 1


def test_the_stars_come_from_the_project(tmp_path: Path):
    assert intents.project_fit(tmp_path) == {"side_quest": "★ the project is just starting"}
    (tmp_path / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    (tmp_path / "CLAUDE.md").write_text("# notes\n", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text('[remote "origin"]\n\turl = git@github.com:me/x.git\n', encoding="utf-8")
    assert intents.project_fit(tmp_path) == {"one_skeleton_studio": "★ code and CLAUDE.md here",
                                             "inbox_keep": "★ the project is on GitHub"}
    assert intents.signs_text(tmp_path) == "code (pyproject.toml), notes for agents (CLAUDE.md), GitHub"
    assert intents.project_fit(tmp_path / "missing") == {} and intents.project_fit(None) == {}


def test_a_folder_with_things_in_it_but_no_code_gets_no_star(tmp_path: Path):
    for name in ("notes.md", "todo.txt", "ideas", "drafts"):
        (tmp_path / name).write_text("", encoding="utf-8")
    assert intents.project_fit(tmp_path) == {}


def test_the_summary_is_what_the_operator_said():
    text = interview.summary({"role": "founder"}, "  triage GitHub issues and draft release notes. ",
                             "code (pyproject.toml), GitHub")
    assert text.splitlines() == ["I am Founder / indie maker, and I already work with AI agents.",
                                 "In this project: code (pyproject.toml), GitHub.",
                                 "The town should: triage GitHub issues and draft release notes."]


def test_the_profile_is_kept_and_cleaned(tmp_path: Path):
    f = tmp_path / "s.json"
    settings.save(settings.MachineSettings(profile={
        "role": "founder", "orchestration": "some", "industry": "media", "day": ["build"], "secret": "x",
        "ai_tools": {"cursor": {"title": "Cursor", "like": 1}}}), f)
    assert settings.load(f).profile == {"role": "founder"}                       # the old answers are let go


def test_other_ai_tools_are_found_on_disk_without_running_them(tmp_path: Path):
    (tmp_path / ".cursor").mkdir()
    (tmp_path / ".vscode" / "extensions" / "github.copilot-1.2").mkdir(parents=True)
    found = tools.detect_others(which=lambda b: "/usr/bin/aider" if b == "aider" else None, home=tmp_path,
                                apps=tmp_path / "Applications")
    assert [o.id for o in found] == ["cursor", "copilot", "aider"]


def test_apps_are_looked_up_in_the_given_applications_folder(tmp_path: Path):
    apps = tmp_path / "Applications"
    assert tools.detect_others(which=lambda b: None, home=tmp_path, apps=apps) == []
    (apps / "ChatGPT.app").mkdir(parents=True)
    assert [o.id for o in tools.detect_others(which=lambda b: None, home=tmp_path, apps=apps)] == ["chatgpt"]


def test_every_webhook_comes_in_through_a_watchtower():
    for it in intents.INTENTS:
        types = {b["key"]: b["type"] for b in it.plan["buildings"]}
        for b in it.plan["buildings"]:
            if "webhook" in b["why"].lower():
                assert b["type"] == "watchtower", (it.id, b["key"])
        for r in it.plan["roads"]:
            if r["event"].startswith("watch."):
                assert types[r["from"]] == "watchtower", (it.id, r)
    assert "EVERY WEBHOOK COMES IN THROUGH A WATCHTOWER" in town_builder.ADAPT
    assert "what the project shows" in town_builder.ADAPT


def test_raising_steps_are_real_work():
    assert onboarding.raising_steps({"preset": "empty", "warder": False}) == ["Opening the camp's records"]
    assert onboarding.raising_steps({"preset": "custom", "warder": True}) == [
        "Opening the camp's records", "Installing the 🛡 Warder", "Leaving your order in the Town Hall"]


def test_the_order_keeps_the_role(tmp_path: Path):
    assert town_presets.pending_order(tmp_path) is None
    town_presets.save_order(tmp_path, "  I am Founder / indie maker.  ", "founder")
    order = town_presets.pending_order(tmp_path)
    assert order["prompt"] == "I am Founder / indie maker." and order["role"] == "founder" and not order["seen"]
    town_presets.mark_order_seen(tmp_path)
    assert town_presets.pending_order(tmp_path)["seen"]


def test_the_builder_starts_from_the_templates(tmp_path: Path):
    from tests.test_town_builder import GOOD, _runner
    run = _runner(GOOD)
    town_builder.plan("I am an indie maker.", tmp_path, set(), run, templates=intents.templates_text("founder"))
    assert "START FROM A TEMPLATE" in run.calls[0] and "Inbox Keep" in run.calls[0]
    town_builder.plan("I am an indie maker.", tmp_path, set(), run)
    assert "START FROM A TEMPLATE" not in run.calls[1]


def test_the_mode_cards_show_the_same_rows():
    rich, plain = onboarding.card_art(False).plain, onboarding.card_art(True).plain
    assert "tests: 42 ok" in rich and "tests: 42 ok" in plain
    assert "oOO" in rich and "oOO" not in plain


# -- the flows -------------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_the_whole_flow_with_an_intent(fake_repo: Path, onboard):
    (fake_repo / "CLAUDE.md").write_text("# notes for agents\n", encoding="utf-8")
    _on_github(fake_repo)
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await _tools_ready(app, pilot)                                           # only what is installed
        step = app.screen
        assert "step 1 of 3" in _title(app) and "AI tools" in _title(app)
        assert step.query("#ob-tool-claude") and not step.query("#ob-tool-agy")
        assert "Cursor" in "".join(str(w.render()) for w in step.query(".ob-tool-name"))
        assert not step.query("#ob-like-claude") and "👍" not in str(step.query_one(".ob-head").render())
        assert "Antigravity" in str(step.query_one("#ob-tools-missing").render())
        assert step.query_one("#ob-warder", Checkbox).display and step.query_one("#ob-warder", Checkbox).value
        step.query_one("#ob-billing-claude", Select).value = "api"
        await _press(app, pilot, "ob-next")

        await _on(pilot, app, ModeStep)                                          # the day
        assert "step 2 of 3" in _title(app) and "office hours" in _title(app) and "do not disturb" in _title(app)
        app.screen.pick("shift")
        app.screen.query_one("#ob-quiet", Checkbox).value = True
        await _settle(pilot)
        assert app.screen.bar.show_office                                        # Shift: the office hours on the bar
        await _press(app, pilot, "ob-next")

        await _town_ready(app, pilot)
        assert "step 3 of 3" in _title(app)
        assert _presets(app) == ["one_skeleton_studio", "inbox_keep", "side_quest", "custom"]
        lst = app.screen.query_one("#ob-presets", OptionList)
        assert "★" in str(lst.get_option_at_index(0).prompt) and "★" in str(lst.get_option_at_index(1).prompt)
        assert "★" not in str(lst.get_option_at_index(2).prompt)
        assert "code and CLAUDE.md here" in str(app.screen.query_one("#ob-blurb").render())
        assert not app.screen.query_one("#ob-wish", Input).display               # a ready town: no phrase
        assert "KNIGHT" in str(app.screen.query_one("#ob-mascot").render())
        assert str(app.screen.query_one("#ob-next", Button).label) == "Build"
        await _press(app, pilot, "ob-back")                                      # Back keeps the day
        await _on(pilot, app, ModeStep)
        assert app.screen.mode == "shift" and app.screen.bar.quiet == schedule.DEFAULT_QUIET
        await _press(app, pilot, "ob-back")                                      # …and the tools
        await _tools_ready(app, pilot)
        assert app.screen.query_one("#ob-billing-claude", Select).value == "api"
        await _press(app, pilot, "ob-next")
        await _on(pilot, app, ModeStep)
        await _press(app, pilot, "ob-next")
        await _town_ready(app, pilot)
        await _pick(app, pilot, "ob-presets", "inbox_keep")
        await _press(app, pilot, "ob-next")

        await _until(pilot, lambda: app.scroll.building("sort") is not None and not app.query(RaiseBar), n=200)
        machine = settings.load()
        assert machine.onboarded and machine.mode == "shift" and machine.quiet == schedule.DEFAULT_QUIET
        assert machine.autonomy == autonomy.DEFAULT_LEVEL                         # not asked: F10
        assert machine.tools["claude"].billing == "api" and machine.tools["claude"].enabled
        assert machine.profile == {"role": "founder"}
        assert (fake_repo / ".claude" / "settings.json").exists()                # the Warder
        assert town_presets.pending_order(fake_repo) is None                     # no model was asked


@pytest.mark.asyncio
async def test_none_fits_a_phrase_for_the_builder(fake_repo: Path, onboard, monkeypatch):
    from orkcraft.screens.town_plan import TownPlanReview
    from tests.test_town_builder import GOOD, _runner
    run = _runner(GOOD)
    monkeypatch.setattr(app_mod, "BUILD_RUNNER", run)
    _on_github(fake_repo)
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await _tools_ready(app, pilot)
        await _press(app, pilot, "ob-next")
        await _on(pilot, app, ModeStep)
        await _press(app, pilot, "ob-next")
        await _town_ready(app, pilot)
        await _pick(app, pilot, "ob-presets", "custom")
        assert app.screen.query_one("#ob-wish", Input).display
        await _press(app, pilot, "ob-next")
        assert "Say in a phrase" in str(app.screen.query_one("#ob-town-note").render())   # a phrase is needed
        assert isinstance(app.screen, IntentStep)
        app.screen.query_one("#ob-wish", Input).value = "triage GitHub issues and draft release notes"
        await _press(app, pilot, "ob-next")

        await _until(pilot, lambda: isinstance(app.screen, TownPlanReview), n=200)
        order = town_presets.pending_order(fake_repo)
        assert order["role"] == "founder"
        prompt = run.calls[0]
        assert "I am Founder / indie maker, and I already work with AI agents." in prompt
        assert "In this project: code (src), GitHub." in prompt
        assert "The town should: triage GitHub issues and draft release notes." in prompt
        assert "EVERY WEBHOOK COMES IN THROUGH A WATCHTOWER" in prompt
        assert "START FROM A TEMPLATE" in prompt and "Inbox Keep" in prompt


@pytest.mark.asyncio
async def test_a_known_operator_starts_at_the_town(fake_repo: Path, onboard):
    settings.save(settings.MachineSettings(onboarded=True, profile={"orchestration": "expert", "role": "engineer"},
                                           tools={**settings.MachineSettings().tools,
                                                  "claude": settings.ToolChoice(enabled=True)}))
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await _town_ready(app, pilot)
        town = app.screen
        assert not town.query(".ob-buttons #ob-back")                            # nothing before it
        assert "step" not in _title(app)                                         # no "step 1 of 1"
        assert town.query_one("#ob-warder", Checkbox).display                    # claude on: here
        assert str(town.query_one("#ob-next", Button).label) == "Build"
        assert _presets(app)[0] == "one_skeleton_studio"                         # ★ src here
        await _press(app, pilot, "ob-empty")
        await _until(pilot, lambda: Path(app.config.layout_file).exists())
        assert (fake_repo / ".claude" / "settings.json").exists()
        assert settings.load().profile == {"role": "founder"}                    # an older profile, now an indie maker's


@pytest.mark.asyncio
async def test_without_claude_code_none_fits_is_closed(fake_repo: Path, onboard):
    settings.save(settings.MachineSettings(onboarded=True, profile={"role": "founder"},
                                           tools={**settings.MachineSettings().tools,
                                                  "agy": settings.ToolChoice(enabled=True)}))
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await _town_ready(app, pilot)
        lst = app.screen.query_one("#ob-presets", OptionList)
        custom = lst.get_option_at_index(lst.option_count - 1)
        assert custom.id == "custom" and custom.disabled and "needs Claude Code" in str(custom.prompt)
        assert "Claude Code" in str(app.screen.query_one("#ob-town-note").render())
        assert not app.screen.query_one("#ob-warder", Checkbox).display          # no claude: no Warder


@pytest.mark.asyncio
async def test_the_town_builder_never_calls_claude_code_when_it_is_off(fake_repo: Path, onboard, monkeypatch):
    monkeypatch.setattr(app_mod, "BUILD_RUNNER", None)
    monkeypatch.setattr(app_mod.builders, "claude_runner",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("claude was called")))
    monkeypatch.setenv("ORKCRAFT_ONBOARDING", "0")
    settings.save(settings.MachineSettings(onboarded=True))
    town_presets.save_order(fake_repo, "a town for my podcast", "founder")
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await _settle(pilot)
        app.build_town_from_order()
        await _settle(pilot)
        assert not app.query(RaiseBar) and town_presets.pending_order(fake_repo) is not None


@pytest.mark.asyncio
async def test_a_town_in_words_waits_in_the_town_hall(fake_repo: Path, onboard):
    settings.save(settings.MachineSettings(onboarded=True, profile={"role": "founder"},
                                           tools={**settings.MachineSettings().tools,
                                                  "claude": settings.ToolChoice(enabled=True)}))
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await _town_ready(app, pilot)
        app.screen.query_one("#ob-warder", Checkbox).value = False               # the Warder declined
        await _pick(app, pilot, "ob-presets", "custom")
        app.screen.query_one("#ob-wish", Input).value = "a town for my podcast"
        await _press(app, pilot, "ob-next")
        await _until(pilot, lambda: town_presets.pending_order(fake_repo) is not None and app.order_burning)
        assert not (fake_repo / ".claude" / "settings.json").exists()
        assert town_presets.pending_order(fake_repo)["role"] == "founder"
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
        await _tools_ready(app, pilot)
        await _press(app, pilot, "ob-skip")
        await _until(pilot, lambda: Path(app.config.layout_file).exists())
        machine = settings.load()
        assert machine.onboarded and machine.mode == "camp" and machine.profile == {"role": "founder"}
        assert machine.tools["claude"].enabled                                   # the CLIs found are kept on
        assert not (fake_repo / ".claude" / "settings.json").exists()
        assert app.scroll.building("crew") is None


@pytest.mark.asyncio
async def test_f10_asks_the_tools_and_the_day_not_the_town(fake_repo: Path, onboard, monkeypatch):
    monkeypatch.setenv("ORKCRAFT_ONBOARDING", "0")
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await _settle(pilot)
        assert not isinstance(app.screen, ToolsStep)
        app.start_onboarding(machine_steps=True, town_step=False)
        await _tools_ready(app, pilot)
        assert "step 1 of 2" in _title(app)
        assert not app.screen.query_one("#ob-warder", Checkbox).display          # no town: no Warder
        await _press(app, pilot, "ob-next")
        await _on(pilot, app, ModeStep)
        assert str(app.screen.query_one("#ob-next", Button).label) == "Done"
        assert not app.screen.query_one("#ob-cards").display                    # 50 rows: the buttons, not the cards
        app.screen.pick("office")
        await _press(app, pilot, "ob-next")
        await _settle(pilot)
        assert not isinstance(app.screen, (ToolsStep, ModeStep, IntentStep))
        machine = settings.load()
        assert machine.onboarded and machine.mode == "office" and machine.profile == {"role": "founder"}


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
async def test_the_focused_mode_radio_keeps_its_label(fake_repo: Path, monkeypatch):
    monkeypatch.setenv("ORKCRAFT_ONBOARDING", "0")
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await _settle(pilot)
        app.push_screen(ModeStep(standalone=True))
        await _settle(pilot)
        camp = app.screen.query_one("#ob-mode-camp")
        camp.focus()
        await _settle(pilot)
        assert camp.region.height == 1
