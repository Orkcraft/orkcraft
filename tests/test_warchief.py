"""The Warchief delegates (core/warchief.py, docs/design/calm-town.md §5–§7): his answer's DO line becomes a
card — the Town Builder's plan, reviewed by the Council and raised on Build (or at once when unchained, with
Undo), one building of the catalog, or a face's job (the road planner, the Recruiter, a keeper)."""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from orkcraft import autonomy
from orkcraft.core import bus, runners, warchief
from orkcraft.core.town import Town
from orkcraft.core.workers.town_hall import TOWN_HALL
from tests.test_town_builder import GOOD, _runner

TYPES = {"pit", "fields", "lake", "scrolls"}
HERE = {"forge", "pit_1"}


@pytest.mark.parametrize("answer, order", [
    ("Plain words.", None),
    ('I give it to the Town Builder.\nDO: {"plan": "podcast flow"}', {"kind": "plan", "order": "podcast flow"}),
    ('A board.\nDO: {"build": "fields"}', {"kind": "build", "type": "fields"}),
    ("A board.\nBUILD: fields", {"kind": "build", "type": "fields"}),               # an older answer's line
    ('DO: {"build": "spaceship"}', None),                                           # never a made-up type
    ('DO: {"road": "forge", "from": "pit_1", "order": "the pasted links"}',
     {"kind": "road", "building": "forge", "order": "the pasted links", "source": "pit_1"}),
    ('DO: {"road": "forge", "from": "nowhere", "order": "x"}', {"kind": "road", "building": "forge", "order": "x"}),
    ('DO: {"recruit": "ghost", "order": "x"}', None),                               # never a made-up building
    ('DO: {"keeper": "forge", "order": ""}', None),                                 # an order says what to do
    ("DO: {not json}", None),
])
def test_the_do_line_is_an_order_or_nothing(answer, order):
    text, got = warchief.parse(answer, TYPES, HERE)
    assert got == order and "DO:" not in text and "BUILD:" not in text


def _town(repo: Path, monkeypatch, answer: str) -> Town:
    monkeypatch.setattr(runners, "WARCHIEF_RUNNER", lambda prompt: (answer, 0.01))
    monkeypatch.setattr(runners, "FASTPATH_RUNNER", None)
    return Town(repo, auto_commit=False)


def _wait(w, pred, what: str):
    for _ in range(500):
        if pred():
            return
        time.sleep(0.01)
    raise AssertionError(f"never: {what}")


def test_a_plan_is_the_town_builders_reviewed_by_the_council_and_raised_on_build(fake_repo, monkeypatch, isolated_layout_file):
    monkeypatch.setattr(runners, "BUILD_RUNNER", _runner(GOOD))
    town = _town(fake_repo, monkeypatch, 'The Town Builder plans it.\nDO: {"plan": "episodes from notes to release"}')
    town.machine.autonomy = autonomy.CLOCK
    w = town.worker(TOWN_HALL)
    asked = []
    monkeypatch.setattr(runners, "WARCHIEF_RUNNER", lambda prompt: asked.append(prompt) or (
        'The Town Builder plans it.\nDO: {"plan": "episodes from notes to release"}', 0.01))
    assert w.ask("I make a podcast", about=["town_hall"]) == ""
    _wait(w, lambda: w.chat and w.chat[-1].get("card", {}).get("state") == "ready", "a ready plan")
    assert "DO:" in asked[0] and "The person points at" in asked[0]                # how to delegate, and what is pointed at
    c = w.chat[-1]["card"]
    assert c["kind"] == "plan" and [s["state"] for s in c["steps"]] == ["done", "done"]   # the Town Builder, the Council
    assert [b["title"] for b in c["plan"]["buildings"]] == ["Episode Drops", "Episode Preview", "Show Notes"]
    assert "DO:" not in w.chat[-1]["text"] and not town.scroll.building("inbox")           # nothing stands before Build
    assert w.card_act(c["id"], "build")
    assert w.chat[-1]["card"]["state"] == "done"
    made = w.chat[-1]["card"]["made"]
    assert set(made["buildings"]) == {"inbox", "board", "notes"} and len(made["roads"]) == 1
    assert not w.card_act(c["id"], "build")                                                 # once
    assert w.card_act(c["id"], "undo") and w.chat[-1]["card"]["state"] == "undone"
    assert all(town.scroll.building(i) is None or town.scroll.building(i).demolished for i in made["buildings"])


def test_the_town_builder_plans_on_the_tool_that_is_on(fake_repo, monkeypatch, isolated_layout_file):
    from orkcraft import settings
    from orkcraft.realm import builders
    monkeypatch.setattr(runners, "BUILD_RUNNER", None)
    called = []
    monkeypatch.setitem(builders.RUNNERS, "claude", lambda p: (_ for _ in ()).throw(AssertionError("claude was called")))
    monkeypatch.setitem(builders.RUNNERS, "codex", lambda p: called.append("codex") or _runner(GOOD)(p))
    town = _town(fake_repo, monkeypatch, 'The Town Builder plans it.\nDO: {"plan": "episodes from notes to release"}')
    town.machine.autonomy = autonomy.CLOCK
    town.machine.tools = {**town.machine.tools, "claude": settings.ToolChoice(enabled=False),
                          "agy": settings.ToolChoice(enabled=True), "codex": settings.ToolChoice(enabled=True)}
    w = town.worker(TOWN_HALL)
    w.ask("I make a podcast", about=["town_hall"])
    _wait(w, lambda: w.chat and w.chat[-1].get("card", {}).get("state") == "ready", "a ready plan")
    assert called == ["codex"]                                                 # Codex before agy, Claude off


def test_unchained_the_warchief_builds_at_once_and_offers_undo(fake_repo, monkeypatch, isolated_layout_file):
    town = _town(fake_repo, monkeypatch, 'A board keeps them.\nDO: {"build": "fields"}')
    town.machine.autonomy = autonomy.FREE
    w = town.worker(TOWN_HALL)
    assert w.ask("Where do my tasks go?") == ""
    _wait(w, lambda: w.chat and w.chat[-1].get("card", {}).get("state") == "done", "a building raised")
    built = w.chat[-1]["card"]["made"]["buildings"][0]
    assert town.scroll.building(built) is not None
    assert w.card_act(w.chat[-1]["card"]["id"], "undo") and town.scroll.building(built).demolished


def test_a_cancelled_card_raises_nothing(fake_repo, monkeypatch, isolated_layout_file):
    town = _town(fake_repo, monkeypatch, 'DO: {"build": "fields"}')
    town.machine.autonomy = autonomy.CHAINS
    w = town.worker(TOWN_HALL)
    before = len([b for b in town.scroll.buildings if not b.demolished])
    w.ask("a board")
    _wait(w, lambda: w.chat and "card" in w.chat[-1], "a card")
    c = w.chat[-1]["card"]
    assert c["state"] == "ready" and w.card_act(c["id"], "cancel") and w.chat[-1]["card"]["state"] == "dropped"
    assert not w.card_act(c["id"], "build") and len([b for b in town.scroll.buildings if not b.demolished]) == before


def test_a_road_an_ork_or_a_change_goes_out_as_an_order_a_face_runs(fake_repo, monkeypatch):
    town = _town(fake_repo, monkeypatch, 'The road planner looks.\nDO: {"road": "town_hall", "order": "unread mail"}')
    heard = []
    town.bus.subscribe(bus.ORDER, lambda e: heard.append(e.data))
    w = town.worker(TOWN_HALL)
    w.ask("tell the hall when mail comes")
    _wait(w, lambda: heard, "an order on the bus")
    c = w.chat[-1]["card"]
    assert heard[0]["kind"] == "road" and heard[0]["building"] == "town_hall" and heard[0]["card"] == c["id"]
    assert c["state"] == "sent" and c["steps"][0]["who"] == "Road planner"
    w.card_failed(c["id"], "No such building")
    assert w.chat[-1]["card"]["state"] == "failed" and w.chat[-1]["card"]["error"] == "No such building"


def test_the_gui_host_runs_the_order_as_the_consoles_job(fake_repo, monkeypatch, isolated_layout_file):
    from orkcraft.gui.host import Host
    from orkcraft.realm import checkpoint
    checkpoint.ensure(fake_repo)
    monkeypatch.setattr(runners, "WARCHIEF_RUNNER", lambda prompt: (
        'The keeper changes it.\nDO: {"keeper": "town_hall", "order": "fewer audits"}', 0.01))
    host = Host(fake_repo, auto_commit=False)
    host.command("act", {"id": TOWN_HALL, "act": "ask", "args": {"text": "audit less", "about": [TOWN_HALL]}})
    hall = host.town.worker(TOWN_HALL)
    _wait(hall, lambda: hall.chat and hall.chat[-1].get("card", {}).get("state") == "failed", "the keeper's refusal")
    assert "keeps no rules" in hall.chat[-1]["card"]["error"]          # the hall has no keeper: said on the card
    d = host.detail(TOWN_HALL)["data"]["chat"][-1]["card"]
    json.dumps(d)
    assert d["kind"] == "keeper" and d["building_title"] and "plan" not in d
