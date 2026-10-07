"""Quick note for the Wiki (docs/design/wiki-librarian.md §4): what the wiki suggests for a note, by rules,
in any script; the note's file in the inbox, the inbox a source; the same note from the Task board."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from orkcraft.core import buildings
from orkcraft.gui.host import CommandError, Host
from orkcraft.realm import checkpoint, quicknote, wiki
from orkcraft.realm.shelves import read_note


def _wiki(repo: Path) -> Path:
    root = repo / "llm-wiki" / "team"
    for rel, text in {
        "pages/people/sergey.md": "---\nkind: person\naliases: [Сергей, Serge]\n---\n# Sergey\n\nOwns billing.\n",
        "pages/product/pricing-tiers.md": "---\nkind: product\naliases:\n  - tiers\n---\n# Pricing tiers\n\n"
                                          "Free, Team, Business.\n",
        "pages/process/releases.md": "# Releases\n\nEvery second Tuesday.\n",
    }.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")
    return root


def _pages(repo: Path, root: Path):
    return [read_note(p, repo) for p in sorted((root / "pages").rglob("*.md"))]


def test_front_matter_reads_inline_and_dash_lists():
    text = "---\nkind: note\ntags: [a, 'b c']\nlinks:\n  - x.md\n  - \"y.md\"\nwhen: 2026-10-08 11:00 # tomorrow\n---\nbody"
    assert quicknote.front_matter(text) == {"kind": "note", "tags": ["a", "b c"], "links": ["x.md", "y.md"],
                                            "when": "2026-10-08 11:00"}
    assert quicknote.front_matter("no front matter") == {}


def test_relevant_finds_pages_in_any_script_and_any_inflection(tmp_path: Path):
    root = _wiki(tmp_path)
    found = wiki.relevant(tmp_path, _pages(tmp_path, root), "Обсудить с Сергеем новые тарифы")
    assert [n.title for n in found] == ["Sergey"]                         # Сергеем finds the alias Сергей
    assert wiki.relevant(tmp_path, _pages(tmp_path, root), "the release train")[0].title == "Releases"
    assert wiki.relevant(tmp_path, _pages(tmp_path, root), "и или но") == []


def test_suggest_gives_the_section_the_tags_and_the_links(tmp_path: Path):
    root = _wiki(tmp_path)
    hint = quicknote.suggest("Discuss the pricing tiers with Сергей tomorrow", tmp_path, _pages(tmp_path, root),
                             wiki.sections(root, "team"))
    titles = [x["title"] for x in hint.links]
    assert set(titles) == {"Pricing tiers", "Sergey"} and hint.section in ("product", "people")
    assert "pricing tiers" in hint.tags and "сергей" in hint.tags
    assert all(x["path"].startswith("llm-wiki/team/pages/") for x in hint.links)
    assert quicknote.suggest("   ", tmp_path, _pages(tmp_path, root), []).as_dict() == \
        {"section": "", "tags": [], "links": []}


def test_the_note_file_keeps_what_was_confirmed(tmp_path: Path):
    now = dt.datetime(2026, 10, 7, 15, 42)
    path = quicknote.write(tmp_path, "notes/inbox", "Обсудить тарифы с Сергеем завтра", "people",
                           ["сергей", "pricing, tiers"], ["llm-wiki/team/pages/people/sergey.md"], "warchief", now)
    assert path == "notes/inbox/2026-10-07-обсудить-тарифы-с-сергеем-завтра.md"
    text = (tmp_path / path).read_text(encoding="utf-8")
    assert quicknote.front_matter(text) == {"kind": "note", "section": "people", "tags": ["сергей", "pricing tiers"],
                                            "links": ["llm-wiki/team/pages/people/sergey.md"], "from": "warchief",
                                            "written": "2026-10-07 15:42"}
    assert text.rstrip().endswith("Обсудить тарифы с Сергеем завтра")
    again = quicknote.write(tmp_path, "notes/inbox", "Обсудить тарифы с Сергеем завтра", now=now)
    assert again != path and again.endswith("~2.md")                     # never over another note
    with pytest.raises(ValueError):
        quicknote.write(tmp_path, "notes/inbox", "  ")
    with pytest.raises(ValueError):
        quicknote.write(tmp_path, "../outside", "a note")


def _host(repo: Path) -> Host:
    checkpoint.ensure(repo)
    return Host(repo, auto_commit=False)


def _raised(host: Host, type_id: str, **config) -> str:
    spec = buildings.type_spec(host.town, type_id)
    if config:
        spec["config"] = {**(spec.get("config") or {}), **config}
    built = buildings.raise_spec(host.town, spec)
    assert built is not None
    host.town.worker(built.id)
    return built.id


def test_the_wiki_keeps_a_quick_note_and_reads_its_inbox(fake_repo: Path):
    _wiki(fake_repo)
    host = _host(fake_repo)
    bid = _raised(host, "scrolls", paths=["docs"], topic="team", auto_ingest=False)
    data = host.detail(bid)["data"]
    assert data["inbox"] == "notes/inbox" and {"people", "product", "process"} <= set(data["sections"])
    hint = host.command("act", {"id": bid, "act": "suggest", "args": {"text": "pricing tiers for Sergey"}})
    assert {x["title"] for x in hint["links"]} == {"Pricing tiers", "Sergey"}
    path = host.command("act", {"id": bid, "act": "note", "args": {
        "text": "Discuss the pricing tiers with Sergey", "section": hint["section"], "tags": hint["tags"],
        "links": [x["path"] for x in hint["links"]], "take_in": False}})
    assert path.startswith("notes/inbox/") and (fake_repo / path).is_file()
    w = host.town.worker(bid)
    assert w.config["paths"] == ["docs", "notes/inbox"]                  # the inbox became a source
    assert path in w.pending.new and not w.running                       # waits for the take-in it was not asked for
    assert any(s["path"] == "notes/inbox" for s in host.detail(bid)["data"]["sources"])
    host.command("act", {"id": bid, "act": "note", "args": {"text": "a second one", "take_in": False}})
    assert w.config["paths"] == ["docs", "notes/inbox"]                  # added once
    with pytest.raises(CommandError):
        host.command("act", {"id": bid, "act": "note", "args": {"text": "  "}})


def test_a_note_on_the_task_board_goes_to_the_wiki(fake_repo: Path):
    _wiki(fake_repo)
    host = _host(fake_repo)
    fields = _raised(host, "fields")
    assert host.detail(fields)["data"]["wiki"] is False
    with pytest.raises(CommandError):
        card = host.command("act", {"id": fields, "act": "add", "args": {"lane": "notes", "title": "Pricing tiers"}})
        host.command("act", {"id": fields, "act": "to_wiki", "args": {"card": card}})
    bid = _raised(host, "scrolls", topic="team", auto_ingest=False)
    assert host.detail(fields)["data"]["wiki"] is True
    card = host.command("act", {"id": fields, "act": "add", "args": {"lane": "notes", "title": "Pricing tiers with Sergey"}})
    path = host.command("act", {"id": fields, "act": "to_wiki", "args": {"card": card}})
    meta = quicknote.front_matter((fake_repo / path).read_text(encoding="utf-8"))
    assert meta["from"] == "task board" and "llm-wiki/team/pages/product/pricing-tiers.md" in meta["links"]
    assert host.town.worker(bid).inbox == "notes/inbox"
