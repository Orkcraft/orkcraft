"""The Lookout's refinement (docs/design/barracks-flows.md §6.1): in the call it already makes for the intent,
the light model may name the kind of work of each kept message — only among the kinds its source allows."""
from __future__ import annotations

import json
import time

import pytest

from orkcraft import scroll as ts
from orkcraft.core import buildings
from orkcraft.core.workers.watchtower import WatchtowerWorker
from orkcraft.gui.host import Host
from orkcraft.realm import catalog, checkpoint, lookout, paths, pipes, watch


def sig(title: str, source: str = "slack", body: str = "") -> watch.Signal:
    return watch.Signal("2026-10-08T09:00:00", source, title, body, f"/{title}")


def answering(keep: list[dict], asked: list[str]):
    def run(prompt, model=None):
        asked.append(prompt)
        return json.dumps({"keep": keep}), 0.0
    return run


def test_the_kind_is_chosen_only_among_the_sources_kinds():
    asked: list[str] = []
    allowed = {"slack": ("reply", "change"), "mail": ("reply",)}
    keep = [{"n": 1, "why": "a bug report", "kind": "change"}, {"n": 2, "why": "asks for a doc", "kind": "doc"},
            {"n": 3, "why": "mail", "kind": "change"}]
    verdicts, problem = lookout.judge("work for us", [sig("fix login"), sig("write the spec"), sig("hi", "mail")],
                                      answering(keep, asked), lambda s: allowed[s.source])
    assert problem == "" and [(v.kept, v.kind) for v in verdicts] == [(True, "change"), (True, ""), (True, "")]
    assert "kinds: reply, change" in asked[0] and '"kind"' in asked[0]
    assert asked[0].count("· kinds:") == 2                 # the mail allows one kind: nothing to choose


def test_with_one_kind_per_source_the_prompt_is_as_before():
    asked: list[str] = []
    verdicts, _ = lookout.judge("x", [sig("a")], answering([{"n": 1, "why": "y", "kind": "change"}], asked),
                                lambda s: ("reply",))
    assert verdicts[0].kind == "" and '"kind"' not in asked[0] and "kinds" not in asked[0]
    verdicts, _ = lookout.judge("x", [sig("a")], answering([{"n": 1, "why": "y"}], asked))
    assert verdicts[0].kept and verdicts[0].kind == ""


def test_a_source_may_list_its_kinds_default_first():
    config = {"wants": {"slack": ["reply", "change", "nonsense", "reply"], "mail": "reply", "jira": []}}
    assert paths.source_wants(config, "slack") == ("reply", "change") and paths.source_want(config, "slack") == "reply"
    assert paths.source_wants(config, "mail") == ("reply",) and paths.source_wants(config, "jira") == ()
    assert paths.source_wants({}, "slack") == () and paths.source_want({}, "slack") == ""
    spec = {"id": "t", "type": "watchtower", "title": "T", "icon": "🗼"}
    assert catalog.validate({**spec, "config": {"wants": {"slack": ["reply", "change"]}}}) == []
    assert catalog.validate({**spec, "config": {"wants": {"slack": ["reply", "anything"]}}})
    assert catalog.validate({**spec, "config": {"wants": {"slack": []}}})


@pytest.fixture
def host(fake_repo, isolated_layout_file):
    checkpoint.ensure(fake_repo)
    h = Host(fake_repo, auto_commit=False)
    yield h
    h.close()


def test_the_lookouts_kind_goes_on_the_cart(host, monkeypatch):
    sent: list[pipes.Payload] = []
    monkeypatch.setattr(host.town.roads, "emit", lambda payload, meta=None: sent.append(payload) or [])
    monkeypatch.setattr(ts, "has_outgoing", lambda *a, **k: True)
    def judge(prompt, model=None):                      # every message kept; "change" for any that says broken or fix
        lines = [x for x in prompt.split("<messages>\n")[1].splitlines() if x.startswith("[")]
        return json.dumps({"keep": [{"n": i + 1, "why": "work", "kind": "change" if "broken" in x or "fix" in x
                                     else "reply"} for i, x in enumerate(lines)]}), 0.0
    monkeypatch.setattr(WatchtowerWorker, "judge_runner", staticmethod(judge))
    spec = buildings.type_spec(host.town, "watchtower")
    spec["config"] = {**(spec.get("config") or {}), "intent": "work for us",
                      "wants": {"slack": ["reply", "change"], "mail": "reply"}}
    built = buildings.raise_spec(host.town, spec)
    w = host.town.worker(built.id)
    for s in (sig("Ann: login is broken"), sig("Ann: when is the demo?"), sig("Lee: please fix it", "mail")):
        w.add_signal(s)
    for _ in range(200):
        if len(sent) == 3:
            break
        time.sleep(0.02)
    kinds = {p.title.split(" · ")[-1]: p.want for p in sent}
    assert kinds == {"Ann: login is broken": "change", "Ann: when is the demo?": "reply", "Lee: please fix it": "reply"}


def test_an_alert_the_intent_asks_for_is_rated_by_the_model(host, monkeypatch):
    # a machine's mail is sorted low by code, but an on-call intent listens for exactly that: the model's rating stands
    def judge(prompt, model=None):
        return json.dumps({"keep": [{"n": 1, "why": "production down", "asks": "action", "urgency": "now",
                                     "risk": "high", "tone": "urgent", "agent": False}]}), 0.0
    monkeypatch.setattr(WatchtowerWorker, "judge_runner", staticmethod(judge))
    spec = buildings.type_spec(host.town, "watchtower")
    spec["config"] = {**(spec.get("config") or {}), "intent": "production is down", "triage": True}
    w = host.town.worker(buildings.raise_spec(host.town, spec).id)
    alert = watch.Signal(watch.now_iso(), "mail", "Monitor is DOWN: checkout", "HTTP 502", "/a",
                         sender="alerts@uptime-robot.com")
    w.add_signal(alert)
    for _ in range(200):
        if alert.kept is not None:
            break
        time.sleep(0.02)
    assert alert.kept and alert.importance == "high"
