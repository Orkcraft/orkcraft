"""🪔 The Review board (docs/design/review-board.md): a purpose, a clan, named exits; the verdict on every exit; the
person picks the exit when asked (the building burns, Answers holds the question); no state is a dead end; the setup
proposes the clan from the purpose."""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from orkcraft import scroll as ts
from orkcraft.core.workers.council import CouncilWorker
from orkcraft.gui.host import CommandError, Host
from orkcraft.realm import checkpoint, masonry
from orkcraft.realm import team as tm

PRD = "# PRD: Onboarding v2\n\nNew users reach a working town in five minutes."
EXITS = ["To development: the scope is clear and no risk is open", "To the designer: the flows are unclear"]


def _until(check, seconds: float = 10.0) -> bool:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if check():
            return True
        time.sleep(0.02)
    return check()


class Clan:
    """A fake clan: each member says its line, the steward its decision (by role), every call recorded."""

    def __init__(self, steward: str, said: dict | None = None) -> None:
        self.steward, self.said, self.prompts = steward, said or {}, []

    def __call__(self, harness, prompt, model):
        self.prompts.append(prompt)
        if prompt.startswith("You are the steward"):
            return self.steward, 0.05
        role = tm._ROLE.match(prompt).group(1)
        return self.said.get(role, "APPROVE — fine."), 0.05


def _board(repo: Path, **config) -> None:
    spec = {"id": "board", "title": "PRD review", "icon": "🪔", "orc": {"name": "Reviewers"}, "type": "council",
            "config": {"members": ["Product critic:claude", "Risks analyzer:claude"], "veto": ["Risks analyzer"],
                       "exits": EXITS, **config}}
    assert masonry.save_spec(repo, spec) == []
    dev = {"id": "dev", "title": "Dev", "icon": "🏕", "orc": {"name": "Grunts"}, "type": "barracks"}
    assert masonry.save_spec(repo, dev) == []


@pytest.fixture
def host(fake_repo, monkeypatch):
    _board(fake_repo)
    checkpoint.ensure(fake_repo)
    h = Host(fake_repo, auto_commit=False)
    ts.subscribe(h.town.scroll, "dev", "board", "team.routed", filter={"route": ["to-development"]})
    sent: list = []
    monkeypatch.setattr(h.town.roads, "emit", lambda payload, meta=None: sent.append(payload) or [])
    h.sent = sent
    return h


def _act(h, name, **args):
    return h.command("act", {"id": "board", "act": name, "args": args})


# -- the exits ---------------------------------------------------------------------------------------------

def test_exits_are_parsed_and_the_steward_is_told_their_rules():
    exits = tm.exits_of({"exits": EXITS + ["Back: no", "To the designer: twice"]})
    assert [(e.id, e.name) for e in exits] == [("to-development", "To development"), ("to-the-designer", "To the designer")]
    assert tm.exits_of({"routes": ["human", "agent"]})[1] == tm.Exit("agent", "agent")      # boards of old
    d = tm.new("PRD", PRD)
    prompt = tm.decide_prompt(d, tm.Steward("PRD review"), set(), 3, exits=exits)
    assert "`EXIT: <its id>`" in prompt and "- `to-development` — To development: the scope is clear" in prompt
    tm.run(d, tm.members_of({}), tm.Steward(), set(), 3, 2.0, Clan("DECISION: approve\nEXIT: to-development\nShip it."),
           exits=exits)
    assert (d.outcome, d.route, d.decision) == ("approved", "to-development", "Ship it.")


def test_the_verdict_travels_on_top_of_the_document():
    d = tm.new("PRD", PRD)
    d.turns = [tm.Turn("Product critic", "review", "The metric needs a baseline.", "changes"),
               tm.Turn("Risks analyzer", "review", "Fine.", "approve")]
    d.decision = "Watch the migration."
    out = tm.verdict_markdown(d, "To development")
    assert out.startswith("## Review notes — To development · cycle 1 · 1 ✓ 1 ✗")
    assert "**Keep in mind:** Watch the migration." in out and "**Product critic — changes:** The metric" in out
    assert "Risks analyzer — approve." in out and out.endswith(PRD)
    back = tm.verdict_markdown(d, "Back to the author", back=True)
    assert "**What to fix:**" in back and "send it back under the same title" in back
    d.when = "tomorrow 11:00"
    assert tm.verdict_markdown(d, "To a person").startswith("When: tomorrow 11:00\n\n## Review notes")


def test_a_board_sends_the_document_down_its_exit_with_the_verdict(host, monkeypatch):
    monkeypatch.setattr(CouncilWorker, "runner", staticmethod(
        Clan("DECISION: approve\nEXIT: to-development\nWatch the migration.",
             {"Product critic": "CHANGES: the metric needs a baseline"})))
    w = host.town.worker("board")
    assert w.review(PRD, "PRD: Onboarding v2")
    assert _until(lambda: [p for p in host.sent if p.mode == "team.routed"] and w.history)
    routed = [p for p in host.sent if p.mode == "team.routed"]
    assert routed and routed[0].route == "to-development"
    assert routed[0].value.startswith("## Review notes — To development") and routed[0].value.endswith(PRD)
    assert "the metric needs a baseline" in routed[0].value
    assert w.current.exit == "To development" and w.history[0].out.startswith("## Review notes")
    d = host.detail("board")["data"]
    assert d["current"]["exit"] == "To development" and d["exits"][0] == {
        "id": "to-development", "name": "To development", "when": "the scope is clear and no risk is open", "connected": True}
    assert d["exits"][1]["connected"] is False


def test_an_exit_with_no_road_is_never_taken_the_board_asks(host, monkeypatch):
    monkeypatch.setattr(CouncilWorker, "runner", staticmethod(Clan("DECISION: approve\nEXIT: to-the-designer\nFlows.")))
    w = host.town.worker("board")
    w.review(PRD, "PRD")
    assert _until(lambda: not w.busy and w.current.outcome == "asked" and w.history)
    assert "has no road" in w.current.question and not [p for p in host.sent if p.mode == "team.routed"]


# -- asking: the fire, the exits as answers --------------------------------------------------------------

def test_asked_the_building_burns_and_an_exit_answers_it(host, monkeypatch):
    monkeypatch.setattr(CouncilWorker, "runner", staticmethod(Clan("DECISION: ask\nShip now or after the audit?")))
    w = host.town.worker("board")
    w.review(PRD, "PRD")
    assert _until(lambda: not w.busy and w.current.outcome == "asked" and w.history)
    assert w.status() == "ASKS"
    hut = lambda: next(b for b in host.snapshot()["buildings"] if b["id"] == "board")
    assert _until(lambda: hut()["alert"] is not None)                       # its hut burns
    alert = host.muster.alert(hut()["alert"]["id"])
    assert [words for _k, words in alert.options] == ["To development", "Back to the author"]   # no road: not offered
    with pytest.raises(CommandError, match="has no road"):
        _act(host, "decide", exit="to-the-designer", comment="")
    assert [a["words"] for a in host.detail("board")["data"]["answers"]][0] == "To development"
    host.command("orders.answer", {"id": alert.id, "key": "1"})            # from Answers: the first exit
    assert w.current.outcome == "approved" and w.current.exit == "To development"
    assert _until(lambda: hut()["alert"] is None)


def test_the_person_picks_the_exit_with_a_comment_and_a_veto_leaves_only_back(host, monkeypatch):
    monkeypatch.setattr(CouncilWorker, "runner", staticmethod(
        Clan("DECISION: ask\nVetoed: send it back?", {"Risks analyzer": "VETO: hooks are written without asking"})))
    w = host.town.worker("board")
    w.review(PRD, "PRD")
    assert _until(lambda: not w.busy and w.current.outcome == "asked" and w.history)
    assert [a["id"] for a in host.detail("board")["data"]["answers"]] == ["back"]
    with pytest.raises(CommandError, match="Vetoed"):
        _act(host, "decide", exit="to-development", comment="")
    assert _act(host, "decide", exit="back", comment="Add a consent step") == "Back to the author"
    out = w.current.out                                                      # what went back (no road here: kept)
    assert out.startswith("## Review notes — Back to the author") and "**What to fix:** Add a consent step" in out
    assert w.current.exit == "Back to the author" and w.current.outcome == "rework"


# -- no dead ends --------------------------------------------------------------------------------------------

def test_out_of_its_budget_it_goes_on_with_the_budget_doubled(host, monkeypatch):
    monkeypatch.setattr(CouncilWorker, "runner", staticmethod(Clan("DECISION: approve\nEXIT: to-development\nok")))
    w = host.town.worker("board")
    w.save_config({"budget_usd": 0.05})
    w.review(PRD, "PRD")
    assert _until(lambda: not w.busy and w.current.outcome == "budget" and w.history)
    assert _act(host, "go_on") and _until(lambda: [p for p in host.sent if p.mode == "team.routed"])
    assert w.budget > 0.05


def test_a_document_that_comes_without_budget_waits_in_line(host, monkeypatch):
    monkeypatch.setattr(CouncilWorker, "runner", staticmethod(Clan("DECISION: approve\nEXIT: to-development\nok")))
    w = host.town.worker("board")
    monkeypatch.setattr(host.town, "budget_ok", lambda: False)
    assert not w.review(PRD, "PRD") and [x[0] for x in w.waiting] == ["PRD"]          # kept, not dropped
    monkeypatch.setattr(host.town, "budget_ok", lambda: True)
    assert _act(host, "review_next") and _until(lambda: [p for p in host.sent if p.mode == "team.routed"])
    assert w.waiting == []


def test_while_it_reviews_the_hut_spins_and_says_reading_or_deciding(host, monkeypatch):
    import threading
    gate = threading.Event()

    def slow(harness, prompt, model):
        gate.wait(5)
        return Clan("DECISION: approve\nEXIT: to-development\nok")(harness, prompt, model)

    monkeypatch.setattr(CouncilWorker, "runner", staticmethod(slow))
    w = host.town.worker("board")
    w.review(PRD, "PRD")
    assert w.status() == "WORKING" and w.phase() == "reading"
    gate.set()
    assert _until(lambda: not w.busy)


# -- the setup ------------------------------------------------------------------------------------------------

def test_a_new_board_is_set_up_from_its_purpose(fake_repo, monkeypatch):
    spec = {"id": "fresh", "title": "Review board", "icon": "🪔", "orc": {"name": "Reviewers"}, "type": "council"}
    assert masonry.save_spec(fake_repo, spec) == []
    checkpoint.ensure(fake_repo)
    h = Host(fake_repo, auto_commit=False)
    act = lambda name, **args: h.command("act", {"id": "fresh", "act": name, "args": args})
    w = h.town.worker("fresh")
    assert not w.set_up and h.detail("fresh")["data"]["set_up"] is False
    proposal = {"members": [{"role": "Product critic", "checks": "Is the scope the smallest.", "tier": "warrior"},
                            {"role": "Risks analyzer", "checks": "What breaks.", "tier": "elder", "veto": True}],
                "exits": [{"name": "To development", "when": "ready to build"}]}
    monkeypatch.setattr(CouncilWorker, "setup_runner", staticmethod(lambda prompt: ("```json\n" + json.dumps(proposal) + "\n```", 0.01)))
    act("setup_open")
    act("propose", purpose="PRDs before development: scope, risks")
    assert _until(lambda: w.setup.step == "clan" and not w.setup.busy)
    s = h.detail("fresh")["data"]["setup"]
    assert [m["role"] for m in s["members"]] == ["Product critic", "Risks analyzer"] and s["members"][1]["veto"]
    assert act("setup_save", purpose=s["purpose"], members=s["members"], exits=s["exits"] + [{"name": "Backlog", "when": ""}])
    c = w.config
    assert c["purpose"] == "PRDs before development: scope, risks" and c["veto"] == ["Risks analyzer"]
    assert c["exits"] == ["To development: ready to build", "Backlog"] and len(c["members"]) == 2
    assert "What breaks." in w.role_file("Risks analyzer").read_text() and w.set_up
    assert h.detail("fresh")["data"]["setup"] is None


def test_without_a_model_the_clan_is_picked_by_the_purposes_words(fake_repo):
    from orkcraft.core.workers import council_setup as cs
    members, exits = cs.picked("Triage the support inbox")
    assert [m["role"] for m in members] == ["Risk", "Tone", "Priority"] and [e["name"] for e in exits] == ["To an agent", "To a person"]
    members, _ = cs.picked("Review PRDs before development")
    assert [m["veto"] for m in members] == [False, True, False]


def test_an_exit_with_no_road_is_a_loose_end_and_its_road_says_its_name(host):
    """The map draws each exit no road takes as a stub; laying it offers the exit by name; the road's sign says it."""
    from orkcraft.core import roads
    from orkcraft.gui import state
    w = host.town.worker("board")
    assert w.loose_ends() == [{"route": "to-the-designer", "name": "To the designer", "event": "team.routed#to-the-designer"}]
    choices = roads.choices(host.town, "board", "dev")
    assert ("team.routed#to-the-designer", None, "plain · exit To the designer") in choices
    road = next(r for r in state.roads(host.town) if r["from"] == "board" and r["to"] == "dev")
    assert road["sign"] == "To development"
    from orkcraft.core.roads import _exit_name
    assert _exit_name(host.town, "board", "to-the-designer") == "exit To the designer"
    built = next(b for b in state.buildings(host.town, host.muster) if b["id"] == "board")
    assert built["loose"] == w.loose_ends()
