"""🧭 Onboarding: who you are → your day → the town → (the interview) → tools → autonomy → the look
(docs/design/onboarding.md)."""
from __future__ import annotations

from pathlib import Path

import pytest
from textual.widgets import Button, Checkbox, Input, OptionList, Select, SelectionList

from orkcraft import settings, tools
from orkcraft import app as app_mod
from orkcraft.app import OrkcraftApp
from orkcraft.realm import intents, interview, town_builder, town_presets
from orkcraft.realm.buildings import TOWN_HALL
from orkcraft.screens import onboarding
from orkcraft.screens.autonomy import AutonomySlider, AutonomyStep
from orkcraft.screens.onboarding import (AiToolsStep, IntentStep, ModeStep, PersonStep, QuestionsStep, RaiseBar,
                                         ToolsStep, XpStep)
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


async def _xp(app, pilot, level: str = "some") -> None:
    await _on(pilot, app, XpStep)
    await _pick(app, pilot, "ob-xp", level)
    await _press(app, pilot, "ob-next")


async def _who(app, pilot, role: str = "aso_manager", industry: str = "gaming", level: str = "some") -> None:
    await _xp(app, pilot, level)
    await _on(pilot, app, PersonStep)
    await _pick(app, pilot, "ob-role", role)
    await _pick(app, pilot, "ob-industry", industry)
    await _press(app, pilot, "ob-next")


async def _day_and_ai(app, pilot) -> None:
    await _on(pilot, app, QuestionsStep)
    await _press(app, pilot, "ob-next")
    await _on(pilot, app, AiToolsStep)
    await _press(app, pilot, "ob-next")


async def _select(app, pilot, question: str, *ids: str) -> None:
    lst = app.screen.query_one(f"#ob-q-{question}", SelectionList)
    for i in ids:
        lst.select(i)
    await _settle(pilot)


# -- the data -------------------------------------------------------------------------------------

def test_every_intent_is_a_town_the_builder_would_accept(tmp_path: Path):
    for it in intents.INTENTS:
        plan, problems = town_builder.check(it.plan, tmp_path, set())
        assert not problems, (it.id, problems)
        assert len(plan.specs) >= 2
        assert set(it.day) <= {c.id for c in interview.DAY}, it.id


def test_every_role_has_intents_a_mascot_and_known_suggestions():
    sources = {c.id for c in interview.SOURCES}
    outputs = {c.id for c in interview.OUTPUTS}
    for r in intents.ROLES:
        assert len(intents.for_role(r.id)) == 3, r.id
        assert len({len(line) for line in intents.mascot(r.id)}) == 1
        assert set(r.sources) <= sources and set(r.outputs) <= outputs, r.id
    for extra in intents.INDUSTRY_SOURCES.values():
        assert set(extra) <= sources


def test_the_intents_that_fit_the_day_come_first():
    assert intents.for_role("aso_manager")[0].id == "keyword_tracker"
    assert intents.for_role("aso_manager", ["users"])[0].id == "review_desk"


def test_the_role_s_common_options_come_first():
    page = interview.INTERVIEW[0]
    opts = page.options(page.questions[0], "aso_manager", "gaming")
    common = [c.id for c, mine in opts if mine]
    assert common[:3] == ["app_store", "google_play", "aso_tools"] and "analytics" in common
    assert len(opts) == len(interview.SOURCES)


def test_the_summary_is_what_the_operator_said():
    profile = {"role": intents.OTHER, "role_other": "podcast host", "industry": "media",
               "day": ["research"], "day_other": "editing all afternoon", "rhythm": ["weekly"]}
    text = interview.summary(profile, {"sources": ["gdrive"], "sources_other": "Riverside",
                                       "pains": ["reports_slow"], "ai_used": ["none"]})
    assert text.splitlines()[0] == "I am podcast host in Media and content."
    assert "Research and competitors; editing all afternoon" in text and "A weekly report or sync" in text
    assert "Google Drive / Docs; Riverside" in text and "Reports take hours" in text


def test_the_profile_is_kept_and_cleaned(tmp_path: Path):
    f = tmp_path / "s.json"
    settings.save(settings.MachineSettings(profile={"role": "qa", "day": ["build", 3], "secret": "x",
                                                    "ai_tools": {"cursor": {"skill": "basic"}, "x": 1}}), f)
    assert settings.load(f).profile == {"role": "qa", "day": ["build"],
                                        "ai_tools": {"cursor": {"skill": "basic", "freq": "never"}}}


def test_growth_zones_are_where_experience_and_use_differ():
    zones = interview.growth({"cursor": {"skill": "basic", "freq": "daily"},
                              "claude_code": {"skill": "expert", "freq": "monthly"},
                              "chatgpt": {"skill": "confident", "freq": "daily"},
                              "copilot": {"skill": "none", "freq": "weekly"},
                              "unknown": {"skill": "none", "freq": "daily"}})
    assert zones == ["📈 Cursor: daily, but basic experience — worth learning deeper",
                     "💤 Claude Code: expert, but used monthly — a skill you barely use",
                     "📈 GitHub Copilot: weekly, but no experience — worth learning deeper"]


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


def test_raising_steps_are_real_work():
    assert onboarding.raising_steps({"preset": "empty", "warder": False}) == ["Opening the camp's records"]
    assert onboarding.raising_steps({"preset": "custom", "warder": True}) == [
        "Opening the camp's records", "Installing the 🛡 Warder", "Leaving your order in the Town Hall"]


def test_the_order_keeps_the_role_and_the_answers(tmp_path: Path):
    assert town_presets.pending_order(tmp_path) is None
    town_presets.save_order(tmp_path, "  I am ASO manager.  ", "aso_manager", {"sources": ["app_store"]})
    order = town_presets.pending_order(tmp_path)
    assert order["prompt"] == "I am ASO manager." and order["role"] == "aso_manager" and not order["seen"]
    assert order["answers"] == {"sources": ["app_store"]}
    town_presets.mark_order_seen(tmp_path)
    assert town_presets.pending_order(tmp_path)["seen"]


def test_the_builder_starts_from_the_role_s_templates(tmp_path: Path):
    from tests.test_town_builder import GOOD, _runner
    run = _runner(GOOD)
    town_builder.plan("I am ASO manager.", tmp_path, set(), run, templates=intents.templates_text("aso_manager"))
    assert "START FROM A TEMPLATE" in run.calls[0] and "Review Desk" in run.calls[0]
    town_builder.plan("I am ASO manager.", tmp_path, set(), run)
    assert "START FROM A TEMPLATE" not in run.calls[1]


def test_the_mode_cards_show_the_same_rows():
    rich, plain = onboarding.card_art(False).plain, onboarding.card_art(True).plain
    assert "tests: 42 ok" in rich and "tests: 42 ok" in plain
    assert "oOO" in rich and "oOO" not in plain


# -- the flows -------------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_the_whole_flow_with_an_intent(fake_repo: Path, onboard):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await _on(pilot, app, XpStep)
        assert "step 1 of 8" in str(app.screen.query_one(".build-title").render())   # the full path first
        await _xp(app, pilot, "some")
        await _on(pilot, app, PersonStep)
        assert "step 2 of 8" in str(app.screen.query_one(".build-title").render())
        assert app.screen.query_one("#ob-skip").display
        await _press(app, pilot, "ob-next")
        assert isinstance(app.screen, PersonStep)                                 # no role: refused
        assert "Pick your role" in str(app.screen.query_one("#ob-who-note").render())
        await _pick(app, pilot, "ob-role", "aso_manager")
        assert not str(app.screen.query_one("#ob-who-note").render())          # gone once a role is picked
        await _pick(app, pilot, "ob-industry", "gaming")
        await _press(app, pilot, "ob-next")

        await _on(pilot, app, QuestionsStep)                                     # your day
        await _select(app, pilot, "day", "users", "metrics")
        await _select(app, pilot, "rhythm", "weekly")
        await _press(app, pilot, "ob-next")

        await _on(pilot, app, AiToolsStep)                                       # experience × use
        app.screen.query_one("#ob-skill-cursor", Select).value = "basic"
        app.screen.query_one("#ob-freq-cursor", Select).value = "daily"
        await _settle(pilot)
        assert "Cursor: daily, but basic" in str(app.screen.query_one("#ob-growth").render())
        await _press(app, pilot, "ob-next")

        await _on(pilot, app, IntentStep)
        await _until(pilot, lambda: app.screen.query_one("#ob-presets", OptionList).option_count)
        lst = app.screen.query_one("#ob-presets", OptionList)
        assert [lst.get_option_at_index(i).id for i in range(lst.option_count)] == [
            "keyword_tracker", "review_desk", "listing_lab", "custom"]
        assert "★" in str(lst.get_option_at_index(0).prompt) and "★" not in str(lst.get_option_at_index(2).prompt)
        assert "GOBLIN" in str(app.screen.query_one("#ob-mascot").render())
        assert not app.screen.query_one("#ob-warder", Checkbox).display          # it is on the tools step
        await _pick(app, pilot, "ob-presets", "review_desk")
        await _press(app, pilot, "ob-next")

        await _until(pilot, lambda: isinstance(app.screen, ToolsStep) and app.screen.statuses is not None)
        await _settle(pilot)
        step = app.screen
        assert step.query_one("#ob-warder", Checkbox).display and step.query_one("#ob-warder", Checkbox).value
        assert step.query_one("#ob-tool-agy", Checkbox).disabled
        step.query_one("#ob-billing-claude", Select).value = "api"
        await _press(app, pilot, "ob-next")

        await _on(pilot, app, AutonomyStep)
        app.screen.query_one(AutonomySlider).set_level(2)
        await _press(app, pilot, "au-back")                                      # Back keeps the tools
        await _until(pilot, lambda: isinstance(app.screen, ToolsStep) and app.screen.statuses is not None)
        await _settle(pilot)
        assert app.screen.query_one("#ob-billing-claude", Select).value == "api"
        await _press(app, pilot, "ob-next")
        await _on(pilot, app, AutonomyStep)
        app.screen.query_one(AutonomySlider).set_level(2)
        await _press(app, pilot, "au-next")

        await _on(pilot, app, ModeStep)
        app.screen.pick("office")
        await _press(app, pilot, "ob-next")

        await _until(pilot, lambda: app.scroll.building("replies") is not None
                     and any(r.source == "writers" for r in app.scroll.building("replies").roads)
                     and not app.query(RaiseBar), n=200)
        machine = settings.load()
        assert machine.onboarded and machine.mode == "office" and machine.autonomy == 2
        assert machine.tools["claude"].billing == "api"
        assert machine.profile == {"orchestration": "some", "role": "aso_manager", "industry": "gaming",
                                   "day": ["users", "metrics"], "rhythm": ["weekly"],
                                   "ai_tools": {"cursor": {"skill": "basic", "freq": "daily"}}}
        assert (fake_repo / ".claude" / "settings.json").exists()                # the Warder
        assert any(r.source == "writers" for r in app.scroll.building("replies").roads)
        assert town_presets.pending_order(fake_repo) is None                     # no model was asked


@pytest.mark.asyncio
async def test_none_fits_the_interview_and_the_builder(fake_repo: Path, onboard, monkeypatch):
    from orkcraft.screens.town_plan import TownPlanReview
    from tests.test_town_builder import GOOD, _runner
    run = _runner(GOOD)
    monkeypatch.setattr(app_mod, "BUILD_RUNNER", run)
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await _who(app, pilot, level="new")
        await _on(pilot, app, QuestionsStep)
        assert not app.screen.query_one("#ob-skip").display                      # a newcomer is walked through
        await _press(app, pilot, "ob-next")
        await _on(pilot, app, AiToolsStep)
        app.screen.query_one("#ob-skill-chatgpt", Select).value = "basic"
        app.screen.query_one("#ob-freq-chatgpt", Select).value = "daily"
        await _press(app, pilot, "ob-next")
        await _on(pilot, app, IntentStep)
        await _until(pilot, lambda: app.screen.query_one("#ob-presets", OptionList).option_count)
        await _pick(app, pilot, "ob-presets", "custom")
        await _press(app, pilot, "ob-next")

        await _on(pilot, app, QuestionsStep)                                     # sources
        assert app.screen.page.id == "sources" and "step 6 of 12" in str(app.screen.query_one(".build-title").render())
        await _select(app, pilot, "sources", "app_store", "jira")
        app.screen.query_one("#ob-q-sources-other", Input).value = "AppFollow"
        await _press(app, pilot, "ob-next")
        await _on(pilot, app, QuestionsStep)                                     # outputs
        await _select(app, pilot, "outputs", "asana", "figma")
        await _press(app, pilot, "ob-back")                                      # back keeps the answers
        await _on(pilot, app, QuestionsStep)
        assert app.screen.page.id == "sources"
        assert set(app.screen.query_one("#ob-q-sources", SelectionList).selected) == {"app_store", "jira"}
        await _press(app, pilot, "ob-next")
        await _on(pilot, app, QuestionsStep)
        await _select(app, pilot, "outputs", "asana")
        await _press(app, pilot, "ob-next")
        await _on(pilot, app, QuestionsStep)                                     # problems
        await _select(app, pilot, "pains", "reports_slow", "copy_paste")
        await _press(app, pilot, "ob-next")
        await _on(pilot, app, QuestionsStep)                                     # what went wrong with AI
        await _select(app, pilot, "ai_problems", "no_data")
        await _press(app, pilot, "ob-next")

        await _until(pilot, lambda: isinstance(app.screen, ToolsStep) and app.screen.statuses is not None)
        await _settle(pilot)
        await _press(app, pilot, "ob-next")
        await _on(pilot, app, AutonomyStep)
        await _press(app, pilot, "au-next")
        await _on(pilot, app, ModeStep)
        await _press(app, pilot, "ob-next")

        await _until(pilot, lambda: isinstance(app.screen, TownPlanReview), n=200)
        order = town_presets.pending_order(fake_repo)
        assert order["role"] == "aso_manager" and order["answers"]["sources"] == ["app_store", "jira"]
        assert order["answers"]["sources_other"] == "AppFollow"
        prompt = run.calls[0]
        assert "I am ASO manager in Gaming." in prompt and "App Store Connect; Jira; AppFollow" in prompt
        assert "Results go to: Asana." in prompt and "Reports take hours" in prompt
        assert "No access to my data and tools" in prompt and "orchestration: new to it" in prompt
        assert "ChatGPT (basic, daily)" in prompt and "Growth zones: ChatGPT: daily" in prompt
        assert "EVERY WEBHOOK COMES IN THROUGH A WATCHTOWER" in prompt
        assert "START FROM A TEMPLATE" in prompt and "Keyword Tracker" in prompt


@pytest.mark.asyncio
async def test_a_known_operator_starts_at_the_town(fake_repo: Path, onboard):
    settings.save(settings.MachineSettings(onboarded=True, profile={"orchestration": "some", "role": "engineer",
                                                                    "day": ["firefight"]},
                                           tools={**settings.MachineSettings().tools,
                                                  "claude": settings.ToolChoice(enabled=True)}))
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await _on(pilot, app, IntentStep)
        await _until(pilot, lambda: app.screen.query_one("#ob-presets", OptionList).option_count)
        town = app.screen
        assert not town.query(".ob-buttons #ob-back")                            # nothing before it
        assert "step" not in str(town.query_one(".build-title").render())       # no "step 1 of 1"
        assert town.query_one("#ob-warder", Checkbox).display                    # claude on: here
        assert str(town.query_one("#ob-next", Button).label) == "Build"
        lst = town.query_one("#ob-presets", OptionList)
        assert lst.get_option_at_index(0).id == "bug_hunt"                       # fits the day
        town.query_one("#ob-role-browse", Select).value = "designer"             # other roles' towns
        await _settle(pilot)
        assert town.query_one("#ob-presets", OptionList).get_option_at_index(0).id == "mockup_grove"
        assert "ELF" in str(town.query_one("#ob-mascot").render())
        await _press(app, pilot, "ob-empty")
        await _until(pilot, lambda: Path(app.config.layout_file).exists())
        assert (fake_repo / ".claude" / "settings.json").exists()


@pytest.mark.asyncio
async def test_an_existing_machine_without_a_profile_is_asked_who_first(fake_repo: Path, onboard):
    settings.save(settings.MachineSettings(onboarded=True))
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await _who(app, pilot, "qa", "fintech")
        await _day_and_ai(app, pilot)
        await _on(pilot, app, IntentStep)
        assert "step 5 of 5" in str(app.screen.query_one(".build-title").render())
        assert settings.load().profile == {}                                     # nothing before the end
        await _press(app, pilot, "ob-skip")
        await _until(pilot, lambda: Path(app.config.layout_file).exists())
        assert settings.load().profile["role"] == "qa"


@pytest.mark.asyncio
async def test_a_town_in_words_waits_in_the_town_hall(fake_repo: Path, onboard):
    settings.save(settings.MachineSettings(onboarded=True, profile={"orchestration": "some", "role": "founder"},
                                           tools={**settings.MachineSettings().tools,
                                                  "agy": settings.ToolChoice(enabled=True)}))
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await _on(pilot, app, IntentStep)
        await _until(pilot, lambda: app.screen.query_one("#ob-presets", OptionList).option_count)
        assert not app.screen.query_one("#ob-warder", Checkbox).display          # no claude: no Warder
        await _pick(app, pilot, "ob-presets", "custom")
        await _press(app, pilot, "ob-next")
        for _ in interview.INTERVIEW:
            await _on(pilot, app, QuestionsStep)
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
async def test_a_punk_orc_skips_the_interview_and_builds_the_town(fake_repo: Path, onboard):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await _xp(app, pilot, "expert")
        await _until(pilot, lambda: isinstance(app.screen, ToolsStep) and app.screen.statuses is not None)
        await _settle(pilot)
        assert "step 2 of 4" in str(app.screen.query_one(".build-title").render())
        await _press(app, pilot, "ob-next")
        await _on(pilot, app, AutonomyStep)
        await _press(app, pilot, "au-next")
        await _on(pilot, app, ModeStep)
        await _press(app, pilot, "ob-next")
        await _until(pilot, lambda: Path(app.config.layout_file).exists() and not app.query(RaiseBar), n=200)
        assert settings.load().profile == {"orchestration": "expert"}
        assert (fake_repo / ".claude" / "settings.json").exists()                # the Warder, as checked
        assert town_presets.pending_order(fake_repo) is None
        planned = {b["key"] for it in intents.INTENTS for b in it.plan["buildings"]} - {"loot"}
        assert not any(app.scroll.building(k) for k in planned)                  # nothing raised for them


@pytest.mark.asyncio
async def test_a_known_punk_orc_gets_an_empty_town_without_questions(fake_repo: Path, onboard):
    settings.save(settings.MachineSettings(onboarded=True, profile={"orchestration": "expert"}))
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await _until(pilot, lambda: Path(app.config.layout_file).exists() and not app.query(RaiseBar), n=200)
        assert not isinstance(app.screen, (XpStep, IntentStep, ToolsStep))
        assert not (fake_repo / ".claude" / "settings.json").exists()            # never unasked


@pytest.mark.asyncio
async def test_skip_gives_an_empty_town_and_no_warder(fake_repo: Path, onboard):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await _on(pilot, app, XpStep)
        await _press(app, pilot, "ob-skip")
        await _until(pilot, lambda: Path(app.config.layout_file).exists())
        machine = settings.load()
        assert machine.onboarded and machine.mode == "camp" and machine.profile == {}
        assert not (fake_repo / ".claude" / "settings.json").exists()
        assert app.scroll.building("reviews") is None


@pytest.mark.asyncio
async def test_back_goes_to_the_previous_step(fake_repo: Path, onboard):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await _who(app, pilot, "designer", "saas")
        await _day_and_ai(app, pilot)
        await _on(pilot, app, IntentStep)
        await _press(app, pilot, "ob-back")
        await _on(pilot, app, AiToolsStep)
        await _press(app, pilot, "ob-back")
        await _on(pilot, app, QuestionsStep)
        await _press(app, pilot, "ob-back")
        await _on(pilot, app, PersonStep)
        await _until(pilot, lambda: app.screen.query_one("#ob-role", OptionList).highlighted is not None)
        assert onboarding._highlighted_id(app.screen.query_one("#ob-role", OptionList)) == "designer"


@pytest.mark.asyncio
async def test_f10_asks_who_and_the_machine_steps_not_the_town(fake_repo: Path, onboard, monkeypatch):
    monkeypatch.setenv("ORKCRAFT_ONBOARDING", "0")
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await _settle(pilot)
        assert not isinstance(app.screen, XpStep)
        app.start_onboarding(machine_steps=True, town_step=False)
        await _who(app, pilot, "data_analyst", "ecommerce")
        await _day_and_ai(app, pilot)
        await _until(pilot, lambda: isinstance(app.screen, ToolsStep) and app.screen.statuses is not None)
        await _settle(pilot)
        assert not app.screen.query_one("#ob-warder", Checkbox).display
        await _press(app, pilot, "ob-next")
        await _on(pilot, app, AutonomyStep)
        await _press(app, pilot, "au-next")
        await _on(pilot, app, ModeStep)
        await _press(app, pilot, "ob-next")
        await _settle(pilot)
        assert not isinstance(app.screen, (ToolsStep, AutonomyStep, ModeStep, IntentStep))
        assert settings.load().onboarded and settings.load().profile["role"] == "data_analyst"


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
