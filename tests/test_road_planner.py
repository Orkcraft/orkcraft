"""Listen in words: the receiver's steward turns what the person wants into roads to lay
(realm/road_planner.py), and the GUI lays the one they pick (gui/road_planner.py)."""
from __future__ import annotations

import json
from pathlib import Path


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


def test_a_rule_from_the_planner_ends_as_the_stewards_rule(fake_repo, monkeypatch):
    """docs/design/steward-listens.md stage 2: the planner's rule → the Recruiter offers `steward` → the Council
    reviews it → it is hired as a road rule with no tools of its own."""
    host = _host(fake_repo)
    tower = buildings.raise_spec(host.town, buildings.type_spec(host.town, "watchtower")).id
    fields = buildings.raise_spec(host.town, buildings.type_spec(host.town, "fields")).id
    monkeypatch.setattr(runners, "ROAD_RUNNER", _answer(
        {"from": tower, "event": "mail.received", "rule": "only my boss's mail; decide what to do", "say": "When the boss writes…"}))
    monkeypatch.setattr(runners, "RECRUIT_RUNNER", lambda p: (json.dumps({
        "name": "Boss's mail", "role": "to-dos from the boss", "kind": "steward",
        "why": "Deciding what a letter asks for needs judgement.", "orders": "Only my boss's mail; one to-do per letter.",
        "roads": [{"from": tower, "event": "mail.received"}]}), 0.02))
    reviewed: list[str] = []
    monkeypatch.setattr(runners, "FASTPATH_RUNNER", lambda p: (reviewed.append(p) or "{}", 0.0))
    jid = host.command("roads.plan", {"to": fields, "from": tower, "prompt": "boss mail"})
    _wait(host, jid)
    rid = host.command("job.accept", {"job": jid, "index": 0})
    job = _wait(host, rid)
    assert job["view"]["kind"] == "steward" and job["view"]["kind_label"] == "road rule"
    assert "the steward's listen tier" in job["view"]["tier"]
    host.command("job.accept", {"job": rid})
    for _ in range(100):
        if rid not in host.console.jobs:
            break
        import time
        time.sleep(0.05)
    b = host.town.scroll.building(fields)
    rule = next(h for h in b.garrison.handlers if h.kind == "steward")
    assert rule.orders.startswith("Only my boss's mail") and rule.harness == []
    assert [(r.source, r.event) for r in b.roads_of(rule.id)] == [(tower, "mail.received")]
    assert reviewed and "Only my boss's mail" in reviewed[0]
