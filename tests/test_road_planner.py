"""Listen in words: the receiver's steward turns what the person wants into roads to lay
(realm/road_planner.py), and the GUI lays the one they pick (gui/road_planner.py)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from orkcraft.core import buildings, runners
from orkcraft.core import roads as core_roads
from orkcraft.gui.host import Host
from orkcraft.realm import checkpoint, road_planner
from orkcraft.realm.road_planner import Event, Source, Target

INBOX = Source("tower", "Inbox", plain=(Event("mail.received", "new mail"), Event("watch.mention", "mention")),
               ruled=(Event("mail.received", "new mail"),))
FIELDS = Target("fields", "To Do", "anything: the cart becomes a card")


def _answer(*options, missing=""):
    return lambda prompt: (json.dumps({"options": list(options), "missing": missing}), 0.01)


def test_a_plain_road_with_a_filter_passes_and_an_invented_event_is_dropped():
    plan = road_planner.plan("unread mail into my to-do", FIELDS, [INBOX], runner=_answer(
        {"from": "tower", "event": "mail.made_up", "say": "never"},
        {"from": "tower", "event": "mail.received", "match": "(?i)unread", "say": "When mail comes, a card"}))
    assert plan.ok and len(plan.options) == 1
    o = plan.options[0]
    assert (o.source, o.event, o.filter, o.rule) == ("tower", "mail.received", {"match": "(?i)unread"}, "")


def test_nothing_that_holds_goes_back_with_its_problems_then_gives_up():
    prompts: list[str] = []

    def runner(prompt):
        prompts.append(prompt)
        return json.dumps({"options": [{"from": "nowhere", "event": "mail.received"}]}), None

    plan = road_planner.plan("mail", FIELDS, [INBOX], runner=runner)
    assert not plan.ok and len(prompts) == road_planner.MAX_ATTEMPTS
    assert "'nowhere' is not one of the sources" in prompts[-1] and "nowhere" in plan.error


def test_a_rule_needs_an_event_a_handler_can_take_and_drops_the_match():
    plan = road_planner.plan("only what my boss writes, shortened", FIELDS, [INBOX], runner=_answer(
        {"from": "tower", "event": "mail.received", "match": "boss", "rule": "keep my boss's mail, one line each"}))
    o = plan.options[0]
    assert o.rule.startswith("keep my boss") and o.match == "" and o.filter == {}


def test_a_bad_regex_is_a_problem_and_missing_is_said_when_nothing_fits():
    bad = road_planner.plan("x", FIELDS, [INBOX], runner=_answer({"from": "tower", "event": "mail.received",
                                                                 "match": "(unclosed"}))
    assert not bad.ok and "match" in bad.error
    none = road_planner.plan("listen to my phone calls", FIELDS, [INBOX],
                             runner=_answer(missing="nothing here hears phone calls"))
    assert not none.ok and none.missing == "nothing here hears phone calls" and not none.error


def test_one_source_when_the_road_was_drawn_and_no_call_without_words():
    seen: list[str] = []
    road_planner.plan("mail", FIELDS, [INBOX], runner=lambda p: (seen.append(p) or "{}", None))
    assert "the operator drew the road from it" in seen[0]
    assert road_planner.plan("  ", FIELDS, [INBOX], runner=lambda p: 1 / 0).error


def _host(repo: Path) -> Host:
    checkpoint.ensure(repo)
    return Host(repo, auto_commit=False)


def _wait(host, jid):
    import time
    for _ in range(100):
        job = host.console.jobs.get(jid)
        if job is None or job["state"] in ("ready", "verdict", "failed"):
            return job
        time.sleep(0.05)
    raise AssertionError(f"job {jid} still {host.console.jobs[jid]['state']}")


def test_listen_in_words_lays_the_road_the_person_picks(fake_repo, monkeypatch):
    host = _host(fake_repo)
    tower = buildings.raise_spec(host.town, buildings.type_spec(host.town, "watchtower")).id
    fields = buildings.raise_spec(host.town, buildings.type_spec(host.town, "fields")).id
    target, sources = core_roads.contract(host.town, fields)
    src = next(s for s in sources if s.id == tower)
    assert "mail.received" in {e.id for e in src.plain} and target.takes
    asked: list[str] = []
    monkeypatch.setattr(runners, "ROAD_RUNNER", lambda p: (asked.append(p) or json.dumps({"options": [
        {"from": tower, "event": "mail.received", "match": "(?i)unread", "say": "When unread mail comes, a to-do"}]}),
        0.02))
    jid = host.command("roads.plan", {"to": fields, "prompt": "хочу слушать непрочитанные и делать to-do"})
    job = _wait(host, jid)
    assert job["state"] == "ready" and job["view"]["options"][0]["say"].startswith("When unread mail")
    assert "непрочитанные" in asked[0]
    key = host.command("job.accept", {"job": jid, "index": 0})
    road = host.town.scroll.building(fields).road(key.split(":", 1)[1])
    assert (road.source, road.event, road.filter, road.handler) == (tower, "mail.received", {"match": "(?i)unread"}, None)
    assert jid not in host.console.jobs


def test_a_road_with_a_rule_goes_on_to_the_recruiter(fake_repo, monkeypatch):
    host = _host(fake_repo)
    tower = buildings.raise_spec(host.town, buildings.type_spec(host.town, "watchtower")).id
    fields = buildings.raise_spec(host.town, buildings.type_spec(host.town, "fields")).id
    monkeypatch.setattr(runners, "ROAD_RUNNER", _answer(
        {"from": tower, "event": "mail.received", "rule": "only my boss's mail", "say": "When the boss writes…"}))
    asked: list[str] = []
    monkeypatch.setattr(runners, "RECRUIT_RUNNER", lambda p: (asked.append(p) or "{}", None))
    jid = host.command("roads.plan", {"to": fields, "from": tower, "prompt": "boss mail"})
    assert _wait(host, jid)["view"]["from"] == tower
    rid = host.command("job.accept", {"job": jid, "index": 0})
    assert rid.startswith("recruit-") and _wait(host, rid) is not None
    assert "only my boss's mail" in asked[0] and "mail.received" in asked[0]


@pytest.mark.asyncio
async def test_the_tui_finds_the_road_in_words_and_lays_it(fake_repo, monkeypatch):
    from textual.widgets import Input, OptionList

    from orkcraft.app import OrkcraftApp
    from orkcraft.screens.road_modal import WORDS, RoadPlanModal

    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=(200, 50)) as pilot:
        await pilot.pause()
        tower = buildings.raise_spec(app.core, buildings.type_spec(app.core, "watchtower")).id
        fields = buildings.raise_spec(app.core, buildings.type_spec(app.core, "fields")).id
        await pilot.pause()
        monkeypatch.setattr(runners, "ROAD_RUNNER", _answer(
            {"from": tower, "event": "mail.received", "match": "(?i)unread", "say": "When unread mail comes, a to-do"}))
        assert WORDS == "+words"
        app.road_in_words(fields, tower)
        await pilot.pause()
        app.screen.query_one(Input).value = "непрочитанные → to-do"
        await pilot.press("enter")
        for _ in range(50):
            await pilot.pause(0.05)
            if isinstance(app.screen, RoadPlanModal):
                break
        assert isinstance(app.screen, RoadPlanModal)
        assert "When unread mail comes" in str(app.screen.query_one(OptionList).get_option_at_index(0).prompt)
        await pilot.press("enter")
        for _ in range(40):
            await pilot.pause(0.05)
            if app.scroll.building(fields).roads:
                break
        road = app.scroll.building(fields).roads[0]
        assert (road.source, road.event, road.filter) == (tower, "mail.received", {"match": "(?i)unread"})


def test_the_receivers_steward_finds_the_road_on_its_own_tool_and_tier(fake_repo, monkeypatch):
    from orkcraft import scroll as ts
    from orkcraft.realm import builders, steward

    host = _host(fake_repo)
    tower = buildings.raise_spec(host.town, buildings.type_spec(host.town, "watchtower")).id
    fields = buildings.raise_spec(host.town, buildings.type_spec(host.town, "fields")).id
    b = host.town.scroll.building(fields)
    b.garrison.steward = ts.OrcSpec("keeper", "Grunts", harness=[{"role": "run", "harness": "claude"}])
    steward.set_models(b, {"roads": "laborer"})
    calls: list[tuple[str, str | None]] = []
    rule = {"from": tower, "event": "mail.received", "rule": "only my boss's mail", "say": "When the boss writes…"}
    monkeypatch.setattr(builders, "ask", lambda tool, prompt, model=None: calls.append((tool, model)) or (
        json.dumps({"options": [rule]}) if "Recruiter" not in prompt else "{}", None))
    jid = host.command("roads.plan", {"to": fields, "from": tower, "prompt": "boss mail"})
    assert _wait(host, jid)["state"] == "ready"
    rid = host.command("job.accept", {"job": jid, "index": 0})
    _wait(host, rid)
    assert calls[0] == ("claude", "laborer") and ("claude", "laborer") in calls[1:]    # the planner, then the Recruiter
    assert "roads" in steward.uses("fields")
