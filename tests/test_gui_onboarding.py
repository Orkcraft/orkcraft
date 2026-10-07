"""The onboarding in the window (gui/onboarding.py, docs/design/gui-onboarding.md): the steps the snapshot
says, each skipped when its answer is known, and the town going up one step a tick."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from orkcraft import settings, tools
from orkcraft.core import runners
from orkcraft.gui import onboarding
from orkcraft.gui.host import CommandError, Host
from orkcraft.realm import mcp, town_presets


def _statuses() -> list[tools.ToolStatus]:
    by_id = {t.id: t for t in tools.TOOLS}
    return [tools.ToolStatus(by_id["claude"], found=True, path="/usr/bin/claude", version="2.1.4", logged_in=True),
            tools.ToolStatus(by_id["agy"], found=False),
            tools.ToolStatus(by_id["codex"], found=True, path="/usr/bin/codex", version="0.46", logged_in=True,
                             billing="api")]


@pytest.fixture
def onboard(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ORKCRAFT_ONBOARDING", "1")
    monkeypatch.setattr(tools, "detect", lambda *a, **k: _statuses())
    monkeypatch.setattr(tools, "detect_others", lambda *a, **k: [o for o in tools.OTHERS if o.id == "cursor"])
    monkeypatch.setattr(mcp, "found", lambda *a, **k: [mcp.Server("github", "GitHub", ("claude", "codex"), "github"),
                                                       mcp.Server("amplitude", "Amplitude", ("codex",))])

    def no_model(prompt, model=None):
        raise RuntimeError("no model in tests")
    monkeypatch.setattr(runners, "BUILD_RUNNER", no_model)


def _host(repo: Path) -> Host:
    host = Host(repo, auto_commit=False)
    host.onboarding._finder.join(5)
    return host


def _raise_all(host: Host) -> dict:
    now = 1000.0
    for _ in range(60):
        now += onboarding.RAISE_STEP_S
        host.tick(now)
        o = host.snapshot()["onboarding"]
        if o["raising"]["phase"] in ("done", "failed"):
            return o
    raise AssertionError("the town never stood")


def test_a_gnome_s_whole_path(fake_repo: Path, onboard):
    host = _host(fake_repo)
    o = host.snapshot()["onboarding"]
    json.dumps(o)                                                         # it crosses the socket as it is
    assert o["step"] == "tools" and o["steps"] == ["tools", "who", "mcp", "town"]
    assert [r["id"] for r in o["tools"]["rows"]] == ["claude", "codex"]   # only what is installed
    assert o["tools"]["missing"] == ["Antigravity"] and o["tools"]["others"] == []
    # Cursor's editor without cursor-agent: the CLI is what the orks run on, not "can't run on these yet"
    assert o["tools"]["cli"] == [{"id": "cursor", "title": "Cursor", "bin": "cursor-agent"}]

    host.command("onboarding.tools", {"tools": {"codex": {"enabled": False, "billing": "api"}}})
    o = host.command("onboarding.tools", {"next": True})
    assert o["step"] == "who"
    classes = {c["id"]: c for c in o["classes"]}                          # every class at once, both gnomes too
    assert len(classes) == 11 and classes["aso_manager"]["nick"] == "Keyword Gnome"
    assert classes["aso_manager"]["sprite"] == "aso_manager" and classes["marketing"]["sprite"] == "marketing"
    sprites = Path(__file__).parents[1] / "design-system" / "sprites" / "mascots"
    assert all((sprites / f"{c['sprite']}-1@2x.png").is_file() for c in classes.values())   # each its own head
    assert classes["marketing"]["biome"] == "lava"
    o = host.command("onboarding.role", {"role": "marketing"})
    assert o["step"] == "mcp" and o["kin"] == "gnome" and o["mcp"]["on"] == ["github", "amplitude"]
    o = host.command("onboarding.mcp", {"on": ["amplitude", "nope"], "next": True})
    assert o["step"] == "town" and o["mcp"]["on"] == ["amplitude"] and o["biome"] == "lava"
    towns = {t["id"]: t for t in o["towns"]}
    assert set(towns) == {"campaign_report", "content_mill", "launch_crypt"}
    pullers = next(b for b in towns["campaign_report"]["buildings"] if b["type"] == "barracks")
    assert pullers["badges"] == ["amplitude"]                              # the MCP shows on the agents' building
    assert all(not b["badges"] for b in towns["campaign_report"]["buildings"] if b["type"] == "loot")

    o = host.command("onboarding.town", {"preset": "campaign_report"})
    assert o["step"] == "raising" and o["raising"]["steps"][0]["state"] == "now"
    machine = settings.load()
    assert machine.onboarded and machine.profile["role"] == "marketing" and machine.profile["kin"] == "gnome"
    assert machine.profile["mcp"] == ["amplitude"] and not machine.tools["codex"].enabled
    assert all(b["state"] == "planned" for b in o["raising"]["buildings"])
    assert [b["hut"] for b in o["raising"]["buildings"]][:2] == [[0.0, 0.0], [0.333, 0.0]]   # spots known first
    space = host.town.scroll.orkspaces[0]
    assert space.biome == "lava"                                            # the gnomes' ground at once

    host.tick(1000.0 + onboarding.RAISE_STEP_S)                            # one step a tick: the map fills
    assert host.snapshot()["onboarding"]["raising"]["steps"][0]["state"] == "done"
    o = _raise_all(host)
    assert o["raising"]["phase"] == "done"
    assert all(b["state"] == "standing" for b in o["raising"]["buildings"])
    assert host.town.scroll.building("analysts").hut == [0.333, 0.0]          # each stands where it was planned
    raised = {b.id for b in host.town.scroll.buildings}
    assert {"schedule", "analysts", "report", "reports"} <= raised
    assert (fake_repo / ".claude" / "settings.json").exists()               # the Security reviewer
    host.command("onboarding.close")
    assert host.snapshot()["onboarding"] is None


def test_the_landing_page_s_class_skips_who_you_are(fake_repo: Path, onboard):
    settings.preset_role("marketing")
    host = _host(fake_repo)
    o = host.snapshot()["onboarding"]
    assert o["steps"] == ["tools", "mcp", "town"] and o["nick"] == "Growth-Hack Gnome"


def test_the_landing_page_s_gnome_shows_only_the_two_gnomes(fake_repo: Path, onboard):
    settings.preset_role("marketing", kin="gnome")                        # orkcraft --role gnome
    host = _host(fake_repo)
    o = host.snapshot()["onboarding"]
    assert o["steps"] == ["tools", "who", "mcp", "town"] and o["only_kin"] == "gnome" and o["role"] == ""
    assert [c["id"] for c in o["classes"]] == ["aso_manager", "marketing"] and o["kin_word"] == "gnomes"
    host.command("onboarding.tools", {"next": True})
    o = host.command("onboarding.role", {"role": "aso_manager"})
    assert o["step"] == "mcp" and o["nick"] == "Keyword Gnome"


def test_a_known_machine_is_not_asked_again(fake_repo: Path, onboard):
    settings.preset_role("marketing", kin="gnome")
    m = settings.load()
    m.onboarded = True
    settings.save(m)
    o = _host(fake_repo).snapshot()["onboarding"]
    assert "who" not in o["steps"] and o["role"] == "marketing"


def test_a_class_that_is_not_one(fake_repo: Path, onboard):
    host = _host(fake_repo)
    host.command("onboarding.tools", {"next": True})
    with pytest.raises(CommandError, match="No such role"):
        host.command("onboarding.role", {"role": "wizard"})


def test_back_and_skip(fake_repo: Path, onboard):
    host = _host(fake_repo)
    host.command("onboarding.tools", {"next": True})
    assert host.command("onboarding.back", {})["step"] == "tools"
    o = host.command("onboarding.skip", {})
    assert o["step"] == "raising" and o["raising"]["title"] == "An empty town"
    o = _raise_all(host)
    assert not (fake_repo / ".claude" / "settings.json").exists()           # skip: no Security reviewer
    assert settings.load().tools["claude"].enabled                          # the tools found stay on
    with pytest.raises(CommandError, match="not open"):
        host.command("onboarding.role", {"role": "engineer"})


def test_doesn_t_fit_one_question_and_the_planner(fake_repo: Path, onboard, monkeypatch):
    from tests.test_town_builder import GOOD, _runner
    run = _runner(GOOD)
    monkeypatch.setattr(runners, "BUILD_RUNNER", run)
    settings.preset_role("marketing")
    host = _host(fake_repo)
    host.command("onboarding.tools", {"next": True})
    host.command("onboarding.mcp", {"on": ["github", "amplitude"], "next": True})
    o = host.command("onboarding.town", {"custom": True})
    s = o["survey"]
    assert o["step"] == "survey" and len(s["starters"]) == 3                 # the class's own examples
    uses = [u["id"] for u in s["uses"]]
    # the MCP servers on first, then the class's usual: Amplitude's MCP stands for "Amplitude / Mixpanel / GA",
    # one Slack, no more than six
    assert uses == ["mcp:github", "mcp:amplitude", "src:gsheets", "src:crm", "src:slack", "src:notion"]
    with pytest.raises(CommandError, match="what the town should do"):
        host.command("onboarding.survey", {"words": " ", "keep": uses})
    keep = [u for u in uses if u not in ("mcp:github", "src:notion")]       # two left out
    o = host.command("onboarding.survey", {"words": s["starters"][0], "keep": keep, "extra": ["Looker"]})
    assert o["raising"]["phase"] in ("planning", "raising") and o["mcp"]["on"] == ["amplitude"]
    host.onboarding._planner.join(10)                                       # the planner draws on a thread
    o = _raise_all(host)
    assert o["raising"]["phase"] == "done"
    prompt = run.calls[0]
    assert s["starters"][0] in prompt and "MCP servers the orks may use: amplitude." in prompt
    assert "Google Sheets" in prompt and "Notion" not in prompt and "Also: Looker." in prompt
    assert settings.load().profile["mcp"] == ["amplitude"]
    assert town_presets.pending_order(fake_repo) is None                     # the order was answered


def test_quiet_hours_on_the_autonomy_card(fake_repo: Path, onboard):
    host = _host(fake_repo)
    host.command("onboarding.skip", {})
    assert host.command("onboarding.quiet", {"on": True})["quiet"] and settings.load().quiet is not None
    assert not host.command("onboarding.quiet", {"on": False})["quiet"] and settings.load().quiet is None


def test_set_up_again_from_the_map(fake_repo: Path, onboard, monkeypatch):
    host = _host(fake_repo)
    host.command("onboarding.skip", {})
    _raise_all(host)
    host.command("onboarding.close", {})
    assert host.snapshot()["onboarding"] is None
    standing = len(host.town.scroll.buildings)
    host.command("onboarding.start", {})                                     # the map's menu → Set up again
    host.onboarding._finder.join(5)
    o = host.snapshot()["onboarding"]
    assert o["again"] and o["steps"] == ["tools", "who", "mcp"]              # never a town step
    assert o["tools"]["rows"][0]["enabled"]                                  # what was chosen stays
    host.command("onboarding.tools", {"tools": {"codex": {"enabled": False}}, "next": True})
    host.command("onboarding.role", {"role": "data_analyst"})
    assert host.command("onboarding.mcp", {"on": ["github"], "next": True}) is None   # saved, closed
    m = settings.load()
    assert m.profile["role"] == "data_analyst" and m.profile["mcp"] == ["github"] and not m.tools["codex"].enabled
    assert host.snapshot()["onboarding"] is None and len(host.town.scroll.buildings) == standing   # no town
    host.command("onboarding.start", {})
    host.command("onboarding.skip", {})                                      # Cancel: nothing saved
    assert host.snapshot()["onboarding"] is None and settings.load().profile["role"] == "data_analyst"


def test_the_planner_needs_an_ai_tool_on(fake_repo: Path, onboard, monkeypatch):
    monkeypatch.setattr(runners, "BUILD_RUNNER", None)
    host = _host(fake_repo)
    assert host.snapshot()["onboarding"]["planner"]
    host.command("onboarding.tools", {"tools": {"claude": {"enabled": False}, "codex": {"enabled": False}}})
    assert not host.snapshot()["onboarding"]["planner"]
    with pytest.raises(CommandError, match="AI tool"):
        host.command("onboarding.town", {"custom": True})


def test_a_tool_request_is_an_issue_the_person_sends(fake_repo: Path, onboard):
    host = _host(fake_repo)
    url = host.command("onboarding.request", {"name": "Aider", "link": "https://aider.chat", "note": "cheap refactors"})["url"]
    assert url.startswith(onboarding.ISSUES)
    q = parse_qs(urlsplit(url).query)
    assert q["title"] == ["Support Aider"] and "https://aider.chat" in q["body"][0]
    with pytest.raises(CommandError, match="Name"):
        host.command("onboarding.request", {"name": " "})


def test_no_onboarding_when_turned_off_or_in_a_town(fake_repo: Path, onboard, monkeypatch):
    monkeypatch.setenv("ORKCRAFT_ONBOARDING", "0")
    assert Host(fake_repo, auto_commit=False).snapshot()["onboarding"] is None


def test_cursor_found_is_not_named_again_below_the_table(fake_repo: Path, onboard, monkeypatch: pytest.MonkeyPatch):
    found = [*_statuses(), tools.ToolStatus({t.id: t for t in tools.TOOLS}["cursor"], found=True,
                                            path="/usr/bin/cursor-agent", version="2026.09", logged_in=True)]
    monkeypatch.setattr(tools, "detect", lambda *a, **k: found)
    monkeypatch.setattr(tools, "detect_others", lambda *a, **k: [o for o in tools.OTHERS if o.id in ("cursor", "aider")])
    t = _host(fake_repo).snapshot()["onboarding"]["tools"]
    assert "cursor" in [r["id"] for r in t["rows"]]
    assert t["others"] == [{"id": "aider", "title": "Aider"}] and t["cli"] == [] and "Cursor" not in t["missing"]
