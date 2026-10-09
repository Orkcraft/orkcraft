"""📦 The Loot checkpoint: rules, the queue, rework rounds, needs-you, restore."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from orkcraft.realm import gate, generated, pipes

NOW = dt.datetime(2026, 10, 4, 12, 0)
SIZE = (200, 46)


def cart(value="the doc", source="barracks", ref="", trail=(), kind=pipes.TEXT) -> pipes.Payload:
    return pipes.Payload(kind, value, source, "pool.done", "Docs", tuple(trail), ref)


def test_rules_decide_what_waits():
    cheap = (pipes.hop("barracks", "scribe", "agent", 1000, 0.02, outcome="done", now=NOW),)
    dear = (pipes.hop("barracks", "scribe", "agent", 90000, 1.20, outcome="done", now=NOW),)
    assert gate.reasons(cart(trail=cheap), {}) == []
    assert gate.reasons(cart(), {"review": "always"}) and gate.reasons(cart(), {"review": "never", "sources": ["barracks"]}) == []
    assert gate.reasons(cart(), {"sources": ["barracks"]}) == ["from barracks"]
    assert gate.reasons(cart(trail=dear), {"max_cost_usd": 1}) == ["cost $1.20 > $1.00"]
    assert gate.reasons(cart(trail=dear), {"max_tokens": 50000}) == ["90000 tokens > 50000"]
    assert gate.reasons(cart(trail=cheap), {"max_cost_usd": 1, "max_tokens": 50000}) == []
    failed = (pipes.hop("barracks", "scribe", "agent", outcome="error", now=NOW),)
    assert gate.reasons(cart(trail=failed), {}) == ["barracks ended error"]
    assert gate.reasons(cart(trail=failed), {"on_failed": False}) == []
    redone = failed + (pipes.hop("barracks", "scribe", "agent", outcome="done", now=NOW),
                       pipes.hop("fire", "clan", "team", outcome="approved", now=NOW))
    assert gate.reasons(cart(trail=redone), {}) == []          # failed once, redone and approved: clean
    assert gate.reasons(cart("auth/login.py", kind=pipes.FILE), {"paths": ["auth/**"]}) == ["touches auth/login.py"]
    ctx = gate.Context(files=["migrations/0001.sql", "a.py", "b.py"], external=True)
    assert gate.reasons(cart(), {"paths": ["migrations"], "max_files": 2, "external": True}, ctx) == \
        ["touches migrations/0001.sql", "3 files > 2", "leaves the town"]


def test_rework_rounds_end_with_the_person(tmp_path: Path):
    q = gate.Queue(tmp_path / "q")
    item = q.arrive(cart(ref="D-1"), ["from barracks"], NOW)
    assert (item.status, item.ref, item.attempts) == (gate.HELD, "D-1", 0)
    for n in (1, 2, 3):
        assert q.can_rework(item, {}) == (True, "")
        q.rework(item, f"fix {n}", NOW)
        again = q.arrive(cart("better", ref="D-1"), ["back"], NOW)
        assert again is item and (item.status, item.attempts, item.value) == (gate.HELD, n, "better")
    assert q.can_rework(item, {}) == (False, "sent back 3 times")
    assert q.can_rework(item, {"max_rework": 5})[0]
    q.needs_you(item, "no more rounds", NOW)
    assert q.open()[0] is item and item.status == gate.NEEDS_YOU
    assert gate.Queue(tmp_path / "q").get(item.id).notes == ["fix 1", "fix 2", "fix 3", "no more rounds"]  # saved
    q.accept(item, "fixed by hand", NOW)
    assert (item.status, item.value) == (gate.PASSED, "fixed by hand") and q.open() == []
    big = q.arrive(cart(ref="D-2", trail=(pipes.hop("x", tokens=5000, now=NOW),)), ["held"], NOW)
    assert q.can_rework(big, {"rework_tokens": 4000}) == (False, "the chain spent 5000 tokens")
    assert q.arrive(cart(), ["held"], NOW).ref.startswith("loot-")        # no ref: one is given


def test_rejected_files_come_back_and_odd_names_work(fake_repo: Path):
    (fake_repo / "src" / "макет 1.svg").write_text("<svg/>\n")
    (fake_repo / "loot" / "new-report.md").write_text("# kept by Loot\n")
    rv = generated.Review(fake_repo, fake_repo / ".orkcraft" / "generator" / "g")
    assert [g.path for g in rv.files()] == ["src/макет 1.svg"]           # unescaped; Loot's own folder skipped
    assert rv.preview("src/макет 1.svg") == "<svg/>"
    rv.reject("src/макет 1.svg")
    assert not (fake_repo / "src" / "макет 1.svg").exists() and [r["path"] for r in rv.rejected()] == ["src/макет 1.svg"]
    rv.restore("src/макет 1.svg")
    assert (fake_repo / "src" / "макет 1.svg").read_text() == "<svg/>\n" and rv.rejected() == []
    with pytest.raises(ValueError):
        rv.restore("src/макет 1.svg")


def test_the_rules_read_out_in_plain_words():
    say = gate.describe({"review": "rules", "sources": ["camp"], "paths": ["auth/**"], "max_cost_usd": 0.2,
                         "max_rework": 1, "rework_tokens": 50000}, {"camp": "Agent pool"})
    assert say[0] == "A draft an ork wants to publish always waits for your approval."
    assert "A cart from Agent pool waits." in say and "A cart that touches auth/** waits." in say
    assert "A cart whose chain cost more than $0.20 waits." in say
    assert "A cart from a run that did not finish clean waits." in say          # on by default
    assert say[-2:] == ["Anything else passes by itself.",
                        "A cart goes back for rework at most 1 time, and not once its chain spent 50,000 tokens; "
                        "then it needs you."]
    assert gate.describe({"review": "always"})[1] == "Every cart waits for you."
    assert gate.describe({"review": "never"}) == ["A draft an ork wants to publish always waits for your approval.",
                                                  "Every other cart passes by itself."]
