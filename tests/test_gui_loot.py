"""📦 Loot Vault in the GUI (docs/design/building-views.md §3): its card, its detail and every act,
through the host, with no window."""
from __future__ import annotations

from pathlib import Path

import pytest

from orkcraft.core import buildings
from orkcraft.core.workers.loot import LootWorker
from orkcraft.gui.host import CommandError, Host
from orkcraft.realm import checkpoint, feedback, gate, pipes


@pytest.fixture
def loot(fake_repo: Path):
    checkpoint.ensure(fake_repo)
    host = Host(fake_repo, auto_commit=False)
    spec = buildings.type_spec(host.town, "loot")
    spec["config"] = {**(spec.get("config") or {}), "review": "always", "max_rework": 1}
    built = buildings.raise_spec(host.town, spec)
    return host, built.id, host.town.worker(built.id)


def act(host: Host, bid: str, name: str, **args):
    return host.command("act", {"id": bid, "act": name, "args": args})


def cart(value: str, ref: str, cost: float = 0.05) -> pipes.Payload:
    trail = (pipes.hop("pit"), pipes.hop("camp", "grub", "agent", 4000, cost, outcome="done"))
    return pipes.Payload(pipes.TEXT, value, "camp", "pool.done", f"Doc {ref}", trail, ref)


def test_the_card_counts_what_waits_and_what_it_cost(loot):
    host, bid, w = loot
    card = lambda: next(b for b in host.snapshot()["buildings"] if b["id"] == bid)["card"]
    assert card() == {"to_review": 0, "needs_you": 0, "files": 0, "passed": 0, "cost": "", "latest": "", "at": ""}
    w.receive(cart("one", "A"), "Doc A", "one")
    w.receive(cart("two", "B", 0.10), "Doc B", "two")
    assert card()["to_review"] == 2 and card()["cost"] == "8.0k tok $0.15"
    d = host.detail(bid)["data"]
    assert d["counts"]["held"] == 2 and d["waiting_cost"] == "8.0k tok $0.15"
    it = d["queue"][0]
    assert it["label"] == "Doc A" and it["spent"] == "4.0k tok $0.05" and it["why"]
    assert [h["building"] for h in it["chain"]] == ["pit", "camp"] and it["chain"][1]["spent"] == "4.0k tok $0.05"
    assert act(host, bid, "accept_all") == 2
    assert card()["passed"] == 2 and card()["to_review"] == 0 and len(card()["at"]) == 5     # HH:MM: today


def test_a_cart_is_edited_in_lake_then_accepted_as_the_person_s(loot):
    host, bid, w = loot
    w.receive(cart("## Plan\n\n- a", "A"), "Doc A", "## Plan\n\n- a")
    [item] = w.queue.open()
    d = act(host, bid, "edit", item=item.id)
    draft = host.town.repo_root / d["path"]
    assert draft.read_text() == "## Plan\n\n- a"
    draft.write_text("## Today\n\n- a")                        # the person's edit, in Lake
    assert host.detail(bid)["data"]["queue"][0]["edited"]
    act(host, bid, "accept", item=item.id)
    assert w.stored[0].title == "Doc A" and "## Today" in (host.town.repo_root / w.stored[0].path).read_text()
    assert not draft.exists() and feedback.incidents(host.town.repo_root)[0].source.startswith("loot.re")


def test_rework_needs_a_reason_and_goes_back_to_who_takes_it(loot):
    host, bid, w = loot
    w.receive(cart("draft", "A"), "Doc A", "draft")
    [item] = w.queue.open()
    with pytest.raises(CommandError):
        act(host, bid, "rework", item=item.id)                  # no reason
    with pytest.raises(CommandError):
        act(host, bid, "rework", item=item.id, tag="nope")
    back = []
    w.rework_back = lambda source, payload: back.append((source, payload)) or "camp"
    assert act(host, bid, "rework", item=item.id, tag="incomplete", reason="no dates") == gate.REWORK
    assert back[0][0] == "camp" and "incomplete: no dates" in back[0][1].value
    w.rework_back = None                                        # nobody in this town takes work back
    w.receive(cart("draft 2", "A"), "Doc A", "draft 2")
    assert act(host, bid, "rework", item=item.id, reason="still") == gate.NEEDS_YOU
    assert host.detail(bid)["data"]["counts"]["needs_you"] == 1
    with pytest.raises(CommandError):
        act(host, bid, "rework", item=item.id, reason="again")  # only a held cart goes back
    act(host, bid, "drop", item=item.id)
    assert w.queue.open() == []


def test_changed_files_are_accepted_rejected_and_restored(loot):
    host, bid, w = loot
    root = host.town.repo_root
    (root / "src" / "gen.py").write_text("one\n")
    w.refresh()
    assert any(f["path"] == "src/gen.py" and not f["reviewed"] for f in host.detail(bid)["data"]["files"])
    assert "one" in act(host, bid, "preview", path="src/gen.py")["text"]
    act(host, bid, "file_reject", path="src/gen.py")
    assert not (root / "src" / "gen.py").exists() and host.detail(bid)["data"]["rejected"][0]["path"] == "src/gen.py"
    act(host, bid, "file_restore", index=0)
    assert (root / "src" / "gen.py").read_text() == "one\n"
    act(host, bid, "file_accept", path="src/gen.py")
    with pytest.raises(CommandError):
        act(host, bid, "preview", path="README.md")             # not a changed file


def test_the_worker_registers_itself():
    from orkcraft.core import workers
    assert workers.registry()["loot"] is LootWorker
