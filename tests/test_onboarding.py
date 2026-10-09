"""🧭 Onboarding: orkestration → who you are (and your day) → your AI tools → the town (→ the interview)
→ camp rules (docs/design/onboarding.md)."""
from __future__ import annotations

from pathlib import Path


from orkcraft import settings, tools
from orkcraft.realm import intents, interview, lexicon, town_builder, town_presets, watch

SIZE = (160, 50)


def _statuses() -> list[tools.ToolStatus]:
    by_id = {t.id: t for t in tools.TOOLS}
    return [tools.ToolStatus(by_id["claude"], found=True, path="/usr/bin/claude", version="2.1.4", logged_in=True),
            tools.ToolStatus(by_id["agy"], found=False),
            tools.ToolStatus(by_id["codex"])]


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


async def _on(pilot, app, screen_type) -> None:
    await _until(pilot, lambda: isinstance(app.screen, screen_type))
    await _settle(pilot)


def _title(app) -> str:
    return str(app.screen.query_one(".build-title").render())


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
        assert r.nick and set(r.sources) <= sources and set(r.outputs) <= outputs, r.id
    for extra in intents.INDUSTRY_SOURCES.values():
        assert set(extra) <= sources


def test_who_is_which_mascot():
    kin = {r.id: r.mascot for r in intents.ROLES}
    assert kin["engineer"] == kin["qa"] == "orc"                         # orks
    assert kin["eng_manager"] == kin["product_manager"] == "lich"       # management is undead
    assert kin["designer"] == kin["game_designer"] == "elf"
    assert kin["marketing"] == kin["aso_manager"] == "gnome"
    assert kin["data_analyst"] == "goblin" and kin["founder"] == "knight"
    assert intents.nick("eng_manager") == "The Jira Lich" and intents.nick("founder") == "Indie Knight"
    assert "ORK" in "\n".join(intents.mascot("engineer"))


def test_a_day_is_asked_in_the_role_s_words():
    assert [c.id for c in interview.day_options("engineer")][:3] == ["code", "tests", "deploys"]
    assert [c.id for c in interview.day_options("designer")][:3] == ["mockups", "design_system", "playtests"]
    assert [c.id for c in interview.day_options("other")] == [c.id for c in interview.DAY]
    assert intents.for_role("eng_manager", ["status"])[0].id == "team_pulse"      # status updates count as reports


def test_the_intents_that_fit_the_day_come_first():
    assert intents.for_role("aso_manager")[0].id == "review_desk"
    assert intents.for_role("aso_manager", ["metrics"])[0].id == "keyword_tracker"


def test_a_ready_town_says_itself_in_today_s_words():
    for it in intents.INTENTS:
        texts = [it.title, it.blurb, it.plan["summary"], *(r["why"] for r in it.plan["roads"]),
                 *(t for b in it.plan["buildings"] for t in (b["title"], b["why"]))]
        assert all(lexicon.words(t) == t for t in texts), (it.id, [t for t in texts if lexicon.words(t) != t])


def test_a_role_s_three_towns_are_its_day_its_week_and_its_month():
    for r in intents.ROLES:
        assert [i.rhythm for i in intents.for_role(r.id)] == list(intents.RHYTHMS), r.id
    for it in intents.INTENTS:
        if it.rhythm == "day":
            continue
        towers = {b["key"]: b for b in it.plan["buildings"] if b["type"] == "watchtower"}
        starts = [r for r in it.plan["roads"] if r["event"] == "watch.cron" and r["from"] in towers]
        assert starts, it.id                                                 # it runs by itself
        cron = towers[starts[0]["from"]]["config"]["cron"]
        assert watch.schedule_ok(cron), (it.id, cron)
        assert ("weekly" in cron) == (it.rhythm == "week"), (it.id, cron)


def test_the_role_s_common_options_come_first():
    page = interview.INTERVIEW[0]
    opts = page.options(page.questions[0], "aso_manager", "gaming")
    common = [c.id for c, mine in opts if mine]
    assert common[:3] == ["app_store", "google_play", "aso_tools"] and "analytics" in common
    assert len(opts) == len(interview.SOURCES)
    assert [q.id for p in interview.INTERVIEW for q in p.questions] == ["sources", "outputs", "pains"]


def test_the_summary_is_what_the_operator_said():
    profile = {"role": intents.OTHER, "role_other": "podcast host", "industry": "media",
               "day": ["research"], "day_other": "editing all afternoon", "orchestration": "new",
               "ai_tools": {"claude": {"title": "Claude Code", "like": True, "good": "docs",
                                       "dislike": True, "weak": "tickets"},
                            "cursor": {"title": "Cursor", "like": True}}}
    text = interview.summary(profile, {"sources": ["gdrive"], "sources_other": "Riverside",
                                       "pains": ["reports_slow"]})
    assert text.splitlines()[0] == "I am podcast host in Media and content."
    assert "orkestration: new to it" in text and "Research; editing all afternoon" in text
    assert "Google Drive / Docs; Riverside" in text and "Reports take hours" in text
    assert "AI tools I use: Claude Code — 👍 documentation, 👎 tickets; Cursor — 👍." in text


def test_the_profile_is_kept_and_cleaned(tmp_path: Path):
    f = tmp_path / "s.json"
    settings.save(settings.MachineSettings(profile={
        "role": "qa", "day": ["build", 3], "secret": "x",
        "ai_tools": {"cursor": {"title": "Cursor", "like": 1, "good": "code", "x": "y"}, "bad": 1}}), f)
    assert settings.load(f).profile == {"role": "qa", "day": ["build"], "ai_tools": {
        "cursor": {"title": "Cursor", "like": True, "dislike": False, "good": "code"}}}


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
    assert "their AI tools" in town_builder.ADAPT


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
    assert "START FROM A TEMPLATE" in run.calls[0] and "Review Lodge" in run.calls[0]
    town_builder.plan("I am ASO manager.", tmp_path, set(), run)
    assert "START FROM A TEMPLATE" not in run.calls[1]


# -- the flows -------------------------------------------------------------------------------------
