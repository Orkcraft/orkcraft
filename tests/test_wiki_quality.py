"""The Wiki's quality check (docs/design/wiki-librarian.md §8): what rules find at every look, what the
lint wrote, and the schedule that starts the lint — never at once, never twice for one period."""
from __future__ import annotations

import datetime as dt
import os
from pathlib import Path

import pytest

from orkcraft.core import buildings
from orkcraft.core.workers.scrolls import ScrollsWorker
from orkcraft.gui.host import CommandError, Host
from orkcraft.realm import checkpoint, wikicheck

NOW = dt.datetime(2026, 10, 7, 9, 0)


def _wiki(repo: Path) -> Path:
    root = repo / "llm-wiki" / "general"
    pages = root / "pages" / "concepts"
    pages.mkdir(parents=True)
    (pages / "index.md").write_text("# Concepts\n\n- [Roads](roads.md)\n- [Carts](carts.md)\n")
    (pages / "roads.md").write_text("---\nkind: concept\n---\n# Roads\n\nCarry [carts](carts.md), see "
                                    "[the bus](../modules/bus.md) and [docs](https://example.com).\n")
    (pages / "carts.md").write_text("# Carts\n\nWhat a road carries.\n")
    (pages / "orphan.md").write_text("---\nsources: []\n---\n# Orphan\n")
    return root


def test_the_rules_find_links_indexes_and_front_matter(tmp_path: Path):
    root = _wiki(tmp_path)
    found = {(p.kind, p.page, p.text) for p in wikicheck.rule_problems(root)}
    assert found == {
        ("link", "pages/concepts/roads.md", "links to `../modules/bus.md`, which is not there"),
        ("structure", "pages/concepts/carts.md", "no front matter: add kind, aliases, sources, updated"),
        ("structure", "pages/concepts/orphan.md", "no `kind` in its front matter"),
        ("structure", "pages/concepts/orphan.md", "missing from `pages/concepts/index.md`"),
    }


def test_the_lint_lines_and_the_schedule(tmp_path: Path):
    root = _wiki(tmp_path)
    (root / "lint.md").write_text("# Lint 2026-10-07\n\n- [contradiction] pages/concepts/roads.md — says 4, "
                                  "carts says 6\n- [weird] pages/x.md — what\n- something loose\n")
    got = [(p.kind, p.page, p.by) for p in wikicheck.lint_problems(root)]
    assert got == [("contradiction", "pages/concepts/roads.md", "lint"), ("other", "pages/x.md", "lint"),
                   ("other", "", "lint")]
    (root / "lint.md").write_text("# Lint\n\n- none\n")
    assert wikicheck.lint_problems(root) == []
    assert not wikicheck.due("weekly", None, NOW)                                   # the clock starts first
    assert not wikicheck.due("weekly", NOW - dt.timedelta(days=6), NOW)
    assert wikicheck.due("weekly", NOW - dt.timedelta(days=7), NOW)
    assert wikicheck.due("daily", NOW - dt.timedelta(days=1), NOW) and not wikicheck.due("off", NOW - dt.timedelta(days=99), NOW)
    assert wikicheck.schedule_of({}) == "off" and wikicheck.schedule_of({"check": "hourly"}) == "off"   # on only when asked


def test_the_check_runs_on_its_schedule_and_fixes_what_rules_found(fake_repo: Path, monkeypatch):
    clock = {"now": NOW}
    monkeypatch.setattr(ScrollsWorker, "clock", staticmethod(lambda: clock["now"]))
    prompts = []

    def runner(harness, prompt, workdir, cancel, model, env, resume):
        prompts.append(prompt)
        return "done", 0.05, None, ""

    monkeypatch.setattr(ScrollsWorker, "work_runner", staticmethod(runner))
    _wiki(fake_repo)
    checkpoint.ensure(fake_repo)
    host = Host(fake_repo, auto_commit=False)
    spec = buildings.type_spec(host.town, "scrolls")
    spec["config"] = {**(spec.get("config") or {}), "auto_ingest": False, "commit": False}
    bid = buildings.raise_spec(host.town, spec).id
    w = host.town.worker(bid)
    w.refresh()
    assert not w.running and w.load_quality()["seen"] == "2026-10-07T09:00:00"     # seen: nothing spent
    assert host.detail(bid)["data"]["quality"]["check"] == "off"                   # off until the person turns it on
    assert host.command("act", {"id": bid, "act": "check", "args": {"check": "weekly"}}) == "weekly"
    q = host.detail(bid)["data"]["quality"]
    assert q["check"] == "weekly" and q["next"] == "2026-10-14 09:00" and q["total"] == 4 and q["fixable"] == 4
    assert q["counts"]["link"] == 1 and q["counts"]["structure"] == 3

    clock["now"] = NOW + dt.timedelta(days=7)
    w.refresh()
    _wait(w)
    assert "- [kind] pages/<section>/<page>.md — what to do" in prompts[-1]
    assert w.load_quality()["last"] == "2026-10-14T09:00:00"
    w.refresh()
    assert not w.running and len(prompts) == 1                                     # once for the week
    clock["now"] = NOW + dt.timedelta(days=14)
    w.refresh()
    assert not w.running and len(prompts) == 1                                     # due, but no page changed
    page = fake_repo / w.pages[0].path
    os.utime(page, (page.stat().st_atime, page.stat().st_mtime + 60))
    w.refresh()
    _wait(w)
    assert len(prompts) == 2                                                       # a page changed: checked
    assert host.detail(bid)["data"]["quality"]["cost"] == 0.05

    assert host.command("act", {"id": bid, "act": "fix", "args": {}})
    _wait(w)
    assert "missing from `pages/concepts/index.md`" in prompts[-1] and "links to `../modules/bus.md`" in prompts[-1]

    assert host.command("act", {"id": bid, "act": "check", "args": {"check": "daily"}}) == "daily"
    assert w.config["check"] == "daily"
    with pytest.raises(CommandError):
        host.command("act", {"id": bid, "act": "check", "args": {"check": "hourly"}})
    host.tick()
    assert next(b for b in host.snapshot()["buildings"] if b["id"] == bid)["card"]["quality"] == 4


def _wait(w, seconds: float = 5.0) -> None:
    import time
    end = time.monotonic() + seconds
    while w.running and time.monotonic() < end:
        time.sleep(0.02)
