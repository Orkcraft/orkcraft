"""Finding in the Wiki, and the light model's word on a Quick note the rules found nothing for
(docs/design/wiki-librarian.md §4, §7)."""
from __future__ import annotations

import time
from pathlib import Path

from orkcraft.core import buildings, runners
from orkcraft.gui.host import Host
from orkcraft.realm import checkpoint, quicknote, wikifind


def _wiki(repo: Path) -> None:
    pages = repo / "llm-wiki" / "general" / "pages"
    for rel, text in {"concepts/roads.md": "---\nkind: concept\naliases: [дороги]\n---\n# Roads\n\nA road carries carts.\n"
                                           "Roads never loop.\n",
                      "concepts/carts.md": "---\nkind: concept\n---\n# Carts\n\nWhat a road carries between buildings.\n",
                      "people/sergey.md": "---\nkind: person\naliases: [Сергей]\n---\n# Sergey\n\nOwns billing.\n"}.items():
        (pages / rel).parent.mkdir(parents=True, exist_ok=True)
        (pages / rel).write_text(text, encoding="utf-8")
    (repo / "docs").mkdir(exist_ok=True)
    (repo / "docs" / "billing.md").write_text("# Billing\n\nInvoices go out on the first.\n", encoding="utf-8")


def test_find_puts_names_first_and_says_the_line(fake_repo: Path):
    _wiki(fake_repo)
    host = Host(fake_repo, auto_commit=False)
    spec = buildings.type_spec(host.town, "scrolls")
    spec["config"] = {**(spec.get("config") or {}), "paths": ["docs"], "auto_ingest": False}
    bid = buildings.raise_spec(host.town, spec).id
    host.town.worker(bid)
    hits = host.command("act", {"id": bid, "act": "find", "args": {"query": "road"}})
    assert [h["title"] for h in hits][:2] == ["Roads", "Carts"] and hits[0]["page"] is True
    assert hits[0]["line"] == "A road carries carts."
    assert host.command("act", {"id": bid, "act": "find", "args": {"query": "дороги"}})[0]["title"] == "Roads"
    billing = host.command("act", {"id": bid, "act": "find", "args": {"query": "invoices"}})
    assert billing[0]["path"] == "docs/billing.md" and billing[0]["page"] is False
    assert host.command("act", {"id": bid, "act": "find", "args": {"query": "  "}}) == []


def test_parse_model_keeps_only_what_fits():
    got = wikifind.parse_model('Sure! {"section": "people", "tags": ["Billing", "Q4  plan", "", "a", "b"], '
                               '"people": ["Sergey", "Nobody"]}', ["concepts", "people"], ["Sergey"])
    assert got == {"section": "people", "tags": ["billing", "q4 plan", "a"], "people": ["Sergey"]}
    assert wikifind.parse_model("no json", ["x"], []) == {"section": "", "tags": [], "people": []}
    assert wikifind.parse_model('{"section": "made-up"}', ["x"], [])["section"] == ""
    assert not wikifind.worth_asking("too short", quicknote.Suggestion())
    assert wikifind.worth_asking("a note with enough words", quicknote.Suggestion())


def test_the_light_model_speaks_only_when_the_rules_found_nothing(fake_repo: Path, monkeypatch):
    _wiki(fake_repo)
    asked = []

    def light(prompt):
        asked.append(prompt)
        return ('{"section": "people", "tags": ["billing"], "people": ["Sergey"]}', None)

    monkeypatch.setattr(runners, "FASTPATH_RUNNER", light)
    checkpoint.ensure(fake_repo)
    host = Host(fake_repo, auto_commit=False)
    spec = buildings.type_spec(host.town, "scrolls")
    spec["config"] = {**(spec.get("config") or {}), "auto_ingest": False}
    bid = buildings.raise_spec(host.town, spec).id
    host.town.worker(bid)
    rules = host.command("act", {"id": bid, "act": "suggest", "args": {"text": "roads and carts"}})
    assert rules["links"] and rules["thinking"] is False and not asked              # the rules had a word
    text = "ping the finance folks before payday"
    hint = host.command("act", {"id": bid, "act": "suggest", "args": {"text": text}})
    assert hint["thinking"] is True and not hint["links"]
    end = time.monotonic() + 5
    while time.monotonic() < end and host.detail(bid)["data"]["model_hint"].get("text") != text:
        time.sleep(0.02)
    assert host.detail(bid)["data"]["model_hint"] == {"text": text, "section": "people", "tags": ["billing"],
                                                       "people": ["Sergey"]}
    assert '"Sergey"' in asked[0] and text in asked[0]
    again = host.command("act", {"id": bid, "act": "suggest", "args": {"text": text}})
    assert again["thinking"] is False and len(asked) == 1                          # once per note
