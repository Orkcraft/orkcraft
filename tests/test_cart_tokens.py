"""What a cart costs in a prompt: its body once, no ids a model does not need, no work quoted back to the
session that wrote it."""
from __future__ import annotations

from orkcraft.realm import barracks as bk
from orkcraft.realm import chains, roads
from orkcraft.realm.pipes import Payload


def test_a_road_record_gives_its_body_once():
    rec = chains.record_of("r1", Payload("text", "x" * 100, "pit", "pit.item", ""))
    got = roads.prompt_record(rec)
    assert got == {"source": "pit", "event": "pit.item", "text": "x" * 100}
    node = roads.prompt_record(chains.record_of("r2", Payload("node", "T1", "a", "on_selection_change", "Ship"),
                                                {"status": "done"}))
    assert node == {"source": "a", "event": "on_selection_change", "title": "Ship", "id": "T1", "status": "done"}
    long = roads.prompt_record(chains.record_of("r3", Payload("text", "y" * (roads.SNAPSHOT_CHARS + 50), "a", "e")))
    assert len(long["text"]) == roads.SNAPSHOT_CHARS + 1 and long["text"].endswith("…")


def test_a_task_body_does_not_say_its_title_again():
    t = bk.PoolTask("1", "Fix the login", "# Fix the login\n\nIt fails on Safari.")
    assert bk.body_of(t) == "It fails on Safari."
    assert bk.body_of(bk.PoolTask("2", "Fix the login", "Fix the login")) == "Fix the login"   # nothing else to say
    assert bk.body_of(bk.PoolTask("3", "Login", "Fix the login\n\nmore")) == "Fix the login\n\nmore"


def test_a_rework_into_a_warm_session_does_not_quote_its_own_report():
    report = "Changed auth.py, tests pass."
    text = f"## Sent back for rework by Loot (round 2)\n\n**Why:** no tests\n\n---\n\n**Fix** — Grub (x)\n\n{report}\n"
    got = bk.without_own_work(text, report)
    assert "**Why:** no tests" in got and report not in got and "in this session already" in got
    assert bk.without_own_work(text, "something else") == text
    assert bk.without_own_work("plain\n\n---\n\nrule", "") == "plain\n\n---\n\nrule"
