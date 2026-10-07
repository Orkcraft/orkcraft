"""🌾 Task Fields: a card's context from the wikis (📜, no model), a to-do's plan (🧭, a light model, what
leaves shown first and cleaned) and personal cards that never reach a model (docs/design/fields-board.md §5b)."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from orkcraft.core import buildings, runners
from orkcraft.core.workers import scrolls
from orkcraft.gui.host import CommandError, Host
from orkcraft.realm import checkpoint, privacy


def test_privacy_takes_out_what_has_a_shape_and_puts_it_back():
    s = privacy.scrub("Позвонить Анне +49 151 2345 6789 до 2026-10-07, почта anna@example.org, "
                      "карта 4111 1111 1111 1111, ключ ghp_abcdefgh12345678, docs/design/gui-migration-and-more.md")
    assert "[phone-1]" in s.text and "[email-1]" in s.text and "[card-1]" in s.text and "[token-1]" in s.text
    assert "2026-10-07" in s.text and "docs/design/gui-migration-and-more.md" in s.text     # a date, a path stay
    assert "anna@" not in s.text and "4111" not in s.text
    assert privacy.said(s.found) == "1 e-mail, 1 card number, 1 phone number, 1 secret"
    again = privacy.scrub("write to anna@example.org", s)                                  # the same mark across texts
    assert again.text == "write to [email-1]"
    assert privacy.restore("1. Написать [email-1]\n2. [phone-9]", s.table) == "1. Написать anna@example.org\n2. [phone-9]"


def _host(repo: Path) -> Host:
    checkpoint.ensure(repo)
    return Host(repo, auto_commit=False)


def _raised(host: Host, type_id: str, **config) -> str:
    spec = buildings.type_spec(host.town, type_id)
    spec["config"] = {**(spec.get("config") or {}), **config}
    built = buildings.raise_spec(host.town, spec)
    assert built is not None
    host.town.worker(built.id)
    return built.id


def _wiki(repo: Path) -> Path:
    page = repo / "llm-wiki" / "general" / "pages" / "money" / "bank.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text("# Банк\n\nКарту блокируют по телефону банка; номер договора в папке Документы.\n", encoding="utf-8")
    (repo / "llm-wiki" / "general" / "pages" / "release.md").write_text("# Release\n\nTag it, then push.\n",
                                                                          encoding="utf-8")
    return page


def _act(host, bid, act, **args):
    return host.command("act", {"id": bid, "act": act, "args": args})


def _todo(host, bid, title):
    return next(c for c in host.detail(bid)["data"]["todos"]["cards"] if c["title"] == title)


def _board(fake_repo, monkeypatch, **config):
    monkeypatch.setattr(scrolls, "SETTLE_S", 3600)             # the librarian never starts by itself
    page = _wiki(fake_repo)
    host = _host(fake_repo)
    kb = _raised(host, "scrolls", sources=[])
    host.town.worker(kb).refresh()
    bid = _raised(host, "fields", **config)
    return host, bid, kb, page


def test_a_card_gets_its_context_from_the_wiki_without_a_model(fake_repo, monkeypatch):
    asked = []
    monkeypatch.setattr(runners, "FASTPATH_RUNNER", lambda prompt: (asked.append(prompt), ("Title", 0.0))[1])
    host, bid, kb, page = _board(fake_repo, monkeypatch)
    assert _act(host, bid, "add", lane="mine", title="Позвонить в банк про карту") == "позвонить-в-банк-про-карту"
    card = _todo(host, bid, "Позвонить в банк про карту")
    assert [p["title"] for p in card["pages"]] == ["Банк"] and not card["stale"]      # "банк", "карту" by their start
    assert not asked                                                                  # no model looked
    assert host.town.worker(kb).lent["by"] == bid                                     # the wiki's card says it lent
    _act(host, bid, "add", lane="ideas", title="Something unrelated entirely")
    note = next(c for ln in host.detail(bid)["data"]["lanes"] for c in ln["cards"] if c["title"].startswith("Something"))
    assert note["pages"] == []                                                        # nothing found: no context
    # the page changes: the context is stale till it is looked up again
    page.write_text(page.read_text(encoding="utf-8") + "\nНовое.\n", encoding="utf-8")
    os.utime(page, (time.time() + 5, time.time() + 5))
    assert _todo(host, bid, "Позвонить в банк про карту")["stale"]
    assert _act(host, bid, "context", card="позвонить-в-банк-про-карту") == 1
    assert not _todo(host, bid, "Позвонить в банк про карту")["stale"]
    # an edit renames the card (its id follows its title): its context follows it
    _act(host, bid, "edit", card="позвонить-в-банк-про-карту", text="Позвонить в банк сегодня")
    assert [p["title"] for p in _todo(host, bid, "Позвонить в банк сегодня")["pages"]] == ["Банк"]
    # `wikis: []` turns the context off
    off = _raised(host, "fields", path="OFF.md", wikis=[])
    _act(host, off, "add", lane="mine", title="Позвонить в банк")
    assert _todo(host, off, "Позвонить в банк")["pages"] == []


def _wait(host, bid, title, key="plan"):
    for _ in range(200):
        card = _todo(host, bid, title)
        if card[key] and not card["planning"]:
            return card
        time.sleep(0.02)
    raise AssertionError(f"no {key} for {title!r}")


def test_a_to_dos_plan_shows_what_leaves_cleans_it_and_logs_no_text(fake_repo, monkeypatch):
    asked = []

    def model(prompt):
        asked.append(prompt)
        return "1. Найти номер договора\n2. Написать на [email-1]\n3. Позвонить в банк", 0.001
    monkeypatch.setattr(runners, "FASTPATH_RUNNER", model)
    host, bid, kb, page = _board(fake_repo, monkeypatch)
    _act(host, bid, "add", lane="mine", title="Карта банка: написать support@bank.example")
    card = _todo(host, bid, "Карта банка: написать support@bank.example")
    preview = _act(host, bid, "plan_preview", card=card["id"])
    assert preview["allowed"] and preview["asked"] and preview["taken_out"] == "1 e-mail"
    assert "[email-1]" in preview["text"] and "support@" not in preview["text"]
    assert [p["title"] for p in preview["pages"]] == ["Банк"]
    with pytest.raises(CommandError):
        _act(host, bid, "plan_preview", card="nope")
    assert _act(host, bid, "plan", card=card["id"], pages=[p["path"] for p in preview["pages"]], trust=True)
    planned = _wait(host, bid, card["title"])
    assert planned["plan"] == ["Найти номер договора", "Написать на support@bank.example", "Позвонить в банк"]
    sent = asked[0]
    assert "support@" not in sent and "[email-1]" in sent and "Карту блокируют" in sent      # the page went along
    log = (host.town.worker(bid).state_dir / "sent.jsonl").read_text(encoding="utf-8")
    line = json.loads(log.splitlines()[-1])
    assert line["card"] == card["id"] and line["taken_out"] == {"email": 1} and "Карта" not in log
    assert host.detail(bid)["data"]["plan_ok"] and not _act(host, bid, "plan_preview", card=card["id"])["asked"]
    # the steps become to-dos of their own
    assert _act(host, bid, "plan_steps", card=card["id"]) == 3
    titles = [c["title"] for c in host.detail(bid)["data"]["todos"]["cards"]]
    assert "Найти номер договора" in titles and "Написать на support@bank.example" in titles
    # a plan is only for a to-do
    _act(host, bid, "add", lane="todo", title="Ship the bank page")
    assert not _act(host, bid, "plan_preview", card="ship-the-bank-page")["allowed"]


def test_a_personal_card_never_reaches_a_model(fake_repo, monkeypatch):
    asked = []
    monkeypatch.setattr(runners, "FASTPATH_RUNNER", lambda prompt: (asked.append(prompt), ("1. x", 0.0))[1])
    host, bid, kb, page = _board(fake_repo, monkeypatch)
    long = "записаться к врачу по поводу анализов\nдиагноз не писать сюда"
    added = _act(host, bid, "add", lane="mine", text=long, private=True)
    assert added and not asked                                       # its title is its first words, no model
    card = _todo(host, bid, "Записаться к врачу по")
    assert card["private"] and card["body"] == long
    preview = _act(host, bid, "plan_preview", card=card["id"])
    assert not preview["allowed"] and "personal" in preview["why"]
    with pytest.raises(CommandError):
        _act(host, bid, "plan", card=card["id"])
    assert not asked
    assert _act(host, bid, "private", card=card["id"]) is False       # the person takes it back
    assert _act(host, bid, "plan_preview", card=card["id"])["allowed"]
    # private_todos: every to-do of their own is personal
    host2, bid2, *_ = host, _raised(host, "fields", path="MINE.md", private_todos=True), None
    _act(host2, bid2, "add", lane="mine", title="Оплатить счёт")
    assert _todo(host2, bid2, "Оплатить счёт")["private"]
    _act(host2, bid2, "add", lane="mine", text="позвонить маме вечером после работы обязательно")
    assert not asked
    # a removed card leaves nothing behind
    _act(host, bid, "remove", card=card["id"])
    assert card["id"] not in json.loads((host.town.worker(bid).state_dir / "cards.json").read_text(encoding="utf-8"))
