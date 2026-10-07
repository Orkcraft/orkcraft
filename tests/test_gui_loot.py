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
    assert card() == {"to_review": 0, "needs_you": 0, "files": 0, "passed": 0, "cost": "", "latest": "", "at": "", "first": None, "pics": []}
    w.receive(cart("one", "A"), "Doc A", "one")
    w.receive(cart("two", "B", 0.10), "Doc B", "two")
    assert card()["to_review"] == 2 and card()["cost"] == "8.0k tok $0.15"
    d = host.detail(bid)["data"]
    assert d["counts"]["held"] == 2 and d["waiting_cost"] == "8.0k tok $0.15"
    assert d["rules"][1] == "Every cart waits for you."                    # the fixture's review: always
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


def test_each_cart_says_what_it_is_and_a_picture_shows_closed(loot):
    host, bid, w = loot
    root = host.town.repo_root
    (root / "art").mkdir()
    (root / "art" / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\0" * 32)
    w.receive(pipes.Payload(pipes.FILE, "art/logo.png", "camp", "pool.done", "The logo", (), "L"), "The logo", "")
    w.receive(pipes.Payload(pipes.TEXT, "Wrote it.\n\nPUBLISH: Slack #release\n\nv2 is out", "camp", "pool.question",
                            "Release note", (), "M"), "Release note", "")
    queue = {i["label"]: i["what"] for i in host.detail(bid)["data"]["queue"]}
    assert queue["The logo"]["type"] == "image" and queue["The logo"]["images"] == ["art/logo.png"]
    msg = queue["Release note"]
    assert (msg["type"], msg["where"], msg["body"], msg["lines"]) == ("message", "Slack #release", "v2 is out", ["v2 is out"])
    card = next(b for b in host.snapshot()["buildings"] if b["id"] == bid)["card"]
    assert card["first"]["type"] == "image" and [p["path"] for p in card["pics"]] == ["art/logo.png"]
    assert msg["html"] == "<p>v2 is out</p>\n"                  # Markdown, as HTML
    assert queue["The logo"]["html"] == ""                      # a file is not prose
    item = next(i for i in w.queue.open() if i.ref == "L")
    assert act(host, bid, "thumb", item=item.id, path="art/logo.png").startswith("data:image/png;base64,")
    assert act(host, bid, "thumb", item=item.id, path="README.md") == ""          # not a picture
    assert act(host, bid, "thumb", item=item.id, path="../logo.png") == ""        # not the cart's


def test_accept_all_takes_the_person_s_edits_and_lets_drafts_be_published(loot):
    host, bid, w = loot
    w.receive(cart("## Plan\n\n- a", "A"), "Doc A", "## Plan\n\n- a")
    draft = (pipes.hop("camp", "grub", "agent", 3000, 0.07, outcome=gate.APPROVAL),)
    w.receive(pipes.Payload(pipes.TEXT, "Did it.\n\nPUBLISH: message, Slack #release\n\nv2 is out", "camp",
                            "pool.question", "Release note", draft, "M"), "Release note", "")
    a = next(i for i in w.queue.open() if i.ref == "A")
    path = host.town.repo_root / act(host, bid, "edit", item=a.id)["path"]
    path.write_text("## Today\n\n- a")                          # the person's edit, in Lake
    plan = {x["label"]: x for x in act(host, bid, "accept_all_plan")["items"]}
    assert plan["Doc A"]["edited"] and not plan["Doc A"]["out"]
    assert plan["Release note"]["out"] and plan["Release note"]["type"] == "message"
    published = []
    w.approved_back = lambda source, payload: published.append(payload.ref) or "camp"
    assert act(host, bid, "accept_all", items=[x["id"] for x in plan.values()]) == 2
    kept = {x.title: (host.town.repo_root / x.path).read_text() for x in w.stored}
    assert "## Today" in kept["Doc A"] and not path.exists()
    assert published == ["M"]


def test_accept_all_accepts_only_what_the_person_saw(loot):
    host, bid, w = loot
    w.receive(cart("one", "A"), "Doc A", "one")
    seen = [x["id"] for x in act(host, bid, "accept_all_plan")["items"]]
    w.receive(cart("two", "B"), "Doc B", "two")                 # it came while the dialog was open
    assert act(host, bid, "accept_all", items=seen) == 1
    assert [i.ref for i in w.queue.open()] == ["B"]
    with pytest.raises(CommandError):
        act(host, bid, "accept_all", items="B")
    assert act(host, bid, "accept_all") == 1                     # the Steward's and the TUI's: every held one


def test_a_waiting_cart_makes_its_ork_ask_the_person(loot):
    host, bid, w = loot
    assert w.orders_alert() is None
    w.receive(cart("one", "A"), "Doc A", "one")
    w.receive(cart("two", "B"), "Doc B", "two")
    host.refresh_roster()
    building = next(b for b in host.snapshot()["buildings"] if b["id"] == bid)
    assert building["alert"] and building["alert"]["title"].startswith("2 carts wait for review — Doc A")
    alert = next(a for a in host.snapshot()["alerts"] if a["ref"] == bid)
    assert alert["options"] == [["1", "Stop asking until another cart comes first"]] and alert["context"][1].startswith("Doc B")
    host.command("orders.answer", {"id": alert["id"], "key": "1"})                  # put away
    assert not next(b for b in host.snapshot()["buildings"] if b["id"] == bid)["alert"]
    act(host, bid, "accept_all")
    assert w.orders_alert() is None


def test_why_a_cart_waits_names_buildings_by_their_titles():
    trail = (pipes.hop("camp", "grub", "agent", outcome="error"),)
    payload = pipes.Payload(pipes.TEXT, "x", "camp", "pool.done", "X", trail, "X")
    why = gate.reasons(payload, {"sources": ["camp"]}, None, {"camp": "Agent pool"})
    assert why == ["from Agent pool", "Agent pool ended error"]
    assert gate.reasons(payload, {"sources": ["camp"]}) == ["from camp", "camp ended error"]   # no names: ids
