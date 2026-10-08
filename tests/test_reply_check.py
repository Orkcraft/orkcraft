"""The Reply check (docs/design/barracks-flows.md stage 3, §6.2): a Review board preset — Tone and Facts, Facts
checked against the Wiki's lent pages, one rework round; the External listeners' carts carry the kind their
source is set to; the intents set it on the towers they lay."""
from __future__ import annotations

from pathlib import Path

import pytest

from orkcraft import scroll as ts
from orkcraft.core import buildings
from orkcraft.gui.host import Host
from orkcraft.realm import catalog, checkpoint, intents, paths, pipes, watch
from orkcraft.realm import team as tm


@pytest.fixture
def host(fake_repo, isolated_layout_file):
    checkpoint.ensure(fake_repo)
    h = Host(fake_repo, auto_commit=False)
    yield h
    h.close()


def _raised(host: Host, type_id: str, **config) -> str:
    spec = buildings.type_spec(host.town, type_id)
    spec["config"] = {**(spec.get("config") or {}), **config}
    built = buildings.raise_spec(host.town, spec)
    assert built is not None
    host.town.worker(built.id)
    return built.id


def test_the_reply_check_is_a_preset_of_two_members_and_one_rework():
    p = tm.PRESETS["reply_check"]
    assert p.title == "Reply check" and [m[0] for m in p.members] == ["Tone", "Facts"] and p.max_cycles == 2 and p.wiki
    assert "No promise of a date, a price" in p.members[0][1] and "Wiki" in p.members[1][1]


def test_a_board_is_set_up_as_a_reply_check_in_one_click(host):
    wiki = _raised(host, "scrolls")
    bid = _raised(host, "council")
    w = host.town.worker(bid)
    host.command("act", {"id": bid, "act": "setup_open", "args": {}})
    assert any(p["id"] == "reply_check" for p in host.detail(bid)["data"]["setup"]["presets"])
    assert host.command("act", {"id": bid, "act": "setup_preset", "args": {"preset": "reply_check"}})
    c = w.config
    assert c["members"] == ["Tone:main:laborer", "Facts:main:laborer"] and c["max_cycles"] == 2
    assert c["notes"] == [wiki] and "exits" not in c and w.set_up and not w.named
    assert "No promise of a date" in w.role_file("Tone").read_text(encoding="utf-8")
    assert catalog.validate({**host.town.custom_specs[bid]}) == []


def test_the_members_check_facts_against_the_wikis_pages(host, monkeypatch):
    from orkcraft.realm import shelves
    wiki = _raised(host, "scrolls")
    page = Path(host.town.repo_root) / "billing.md"
    page.write_text("# Billing\n\nThe September invoice goes out on the 28th.\n", encoding="utf-8")
    monkeypatch.setattr(type(host.town.worker(wiki)), "look_up",
                        lambda self, task, by="", title="", **k: [shelves.Note("billing.md", "Billing")], raising=False)
    bid = _raised(host, "council", notes=[wiki])
    notes = host.town.worker(bid).wiki_notes("Invoice", "When does it go out?")
    assert "`billing.md` — Billing" in notes and "goes out on the 28th" in notes
    d = tm.new("Invoice", "Hi Lee, the 28th.")
    d.notes = notes
    prompt = tm.review_prompt(d, tm.Member("Facts", "main"), [tm.Member("Facts", "main")])
    assert "## Notes from the Wiki — check its claims against these" in prompt and "the 28th" in prompt
    assert "Notes from the Wiki" not in tm.review_prompt(tm.new("x", "y"), tm.Member("Tone", "main"), [])


def test_a_towers_carts_carry_the_kind_its_source_is_set_to(host, monkeypatch):
    sent: list[pipes.Payload] = []
    monkeypatch.setattr(host.town.roads, "emit", lambda payload, meta=None: sent.append(payload) or [])
    monkeypatch.setattr(ts, "has_outgoing", lambda *a, **k: True)
    bid = _raised(host, "watchtower", wants={"mail": "reply", "jira": "change"})
    w = host.town.worker(bid)
    w.add_signal(watch.Signal("2026-10-08T09:00:00", "mail", "Lee: the invoice?", "When?", "1"))
    w.add_signal(watch.Signal("2026-10-08T09:01:00", "jira", "WEB-3 Fix login", "Broken", "https://x/WEB-3"))
    w.add_signal(watch.Signal("2026-10-08T09:02:00", "slack", "Ann: hi", "", "https://s/1"))
    kinds = {p.title.split(" · ")[-1]: p.want for p in sent}
    assert kinds == {"Lee: the invoice?": "reply", "WEB-3 Fix login": "change", "Ann: hi": ""}


def test_a_tower_set_up_before_names_no_kind():
    assert paths.source_want({}, "mail") == "" and paths.source_want({"wants": {"mail": "nonsense"}}, "mail") == ""
    assert paths.source_of("gmail") == "mail" and paths.SOURCE_DEFAULTS["jira"] == "change"
    spec = {"id": "t", "type": "watchtower", "title": "T", "icon": "🗼"}
    assert catalog.validate({**spec, "config": {"wants": {"mail": "reply"}}}) == []
    assert catalog.validate({**spec, "config": {"wants": {"mail": "anything"}}})


def test_the_intents_set_what_their_towers_sources_want():
    def wants(intent_id: str) -> dict:
        plan = intents.intent(intent_id).plan
        return next(b["config"]["wants"] for b in plan["buildings"] if b["type"] == "watchtower")
    assert wants("task_desk") == {"mail": "reply"} and wants("solo_forge") == {"jira": "change", "github": "change"}
    assert wants("review_desk") == {"webhook": "reply", "mail": "reply"}
    assert wants("inbox_keep") == {"mail": "reply", "github": "change"}
    for it in intents.INTENTS:                           # every plan still checks as the Town Builder's answer
        for b in it.plan["buildings"]:
            spec = {"id": b["key"], "type": b["type"], "title": b["title"], "icon": b["icon"], "config": b.get("config") or {}}
            assert catalog.validate(spec) == [], (it.id, b["key"])
