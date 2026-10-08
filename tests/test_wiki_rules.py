"""Rules for AI tools (docs/design/wiki-folders-rules.md §3): RULES.md, the blocks every tool reads, what
a person wrote kept as it was, and when they are written: after an approved review, when asked, never."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from orkcraft.core import buildings
from orkcraft.gui.host import CommandError, Host
from orkcraft.realm import checkpoint, wikirules
from orkcraft.settings import ToolChoice


def test_a_block_is_set_replaced_and_taken_out_leaving_the_rest():
    mine = "# My rules\n\nUse tabs.\n"
    once = wikirules.merge(mine, "s1", "first")
    assert once.startswith(mine) and "<!-- orkcraft:wiki:s1 -->\nfirst\n<!-- /orkcraft:wiki:s1 -->" in once
    twice = wikirules.merge(once, "s1", "second")
    assert "first" not in twice and twice.count("orkcraft:wiki:s1 -->") == 2
    both = wikirules.merge(twice, "s2", "other")
    assert wikirules.strip(both, "s1") == (wikirules.merge(mine, "s2", "other"), True)
    assert wikirules.strip(wikirules.strip(both, "s1")[0], "s2") == (mine, True)
    assert wikirules.strip(mine, "s1") == (mine, False)
    assert wikirules.strip(wikirules.merge("", "s1", "x"), "s1") == ("", True)


def test_which_files_the_tools_read():
    assert wikirules.targets([]) == ["CLAUDE.md"]
    assert wikirules.targets(["claude"]) == ["CLAUDE.md"]
    assert wikirules.targets(["codex", "pi"]) == ["AGENTS.md"]
    assert wikirules.targets(["claude", "cursor"]) == ["CLAUDE.md", "AGENTS.md", "cursor"]
    assert wikirules.mode_of({}) == "ask" and wikirules.mode_of({"agent_rules": "loud"}) == "ask"


def test_the_structure_is_the_wikis_or_the_usual_one(tmp_path: Path):
    assert [n for n, _ in wikirules.structure(tmp_path, [])] == [n for n, _ in wikirules.USUAL]
    (tmp_path / "pages" / "people").mkdir(parents=True)
    (tmp_path / "pages" / "modules").mkdir()
    (tmp_path / "pages" / "modules" / "index.md").write_text("# Modules\n\nOne page per module.\n")
    got = wikirules.structure(tmp_path, [("people", "who is who")])
    assert got == [("modules", "One page per module."), ("people", "who is who")]
    text = wikirules.rules_text("llm-wiki/general", got, "notes/inbox")
    assert "`llm-wiki/general/index.md`" in text and "- `pages/people/` — who is who" in text
    assert "notes/inbox/" in text and "Do not make up" in text and "pages/decisions/" in text


def test_write_and_remove_keep_what_people_wrote(tmp_path: Path):
    (tmp_path / "CLAUDE.md").write_text("# Ours\n\nKeep it short.\n")
    changed = wikirules.write(tmp_path, "s1", ["claude", "codex", "cursor"], "llm-wiki/general/RULES.md")
    assert {p.name for p in changed} == {"CLAUDE.md", "AGENTS.md", "orkcraft-wiki-s1.mdc"}
    claude = (tmp_path / "CLAUDE.md").read_text()
    assert claude.startswith("# Ours\n\nKeep it short.\n") and "@llm-wiki/general/RULES.md" in claude
    assert "llm-wiki/general/RULES.md" in (tmp_path / "AGENTS.md").read_text()
    assert "alwaysApply: true" in (tmp_path / ".cursor" / "rules" / "orkcraft-wiki-s1.mdc").read_text()
    assert wikirules.write(tmp_path, "s1", ["claude", "codex", "cursor"], "llm-wiki/general/RULES.md") == []
    assert wikirules.written(tmp_path, "s1") == ["CLAUDE.md", "AGENTS.md", ".cursor/rules/orkcraft-wiki-s1.mdc"]
    wikirules.write(tmp_path, "s1", ["claude"], "llm-wiki/general/RULES.md")      # Codex and Cursor turned off
    assert not (tmp_path / "AGENTS.md").exists() and not (tmp_path / ".cursor" / "rules" / "orkcraft-wiki-s1.mdc").exists()
    wikirules.remove(tmp_path, "s1")
    assert (tmp_path / "CLAUDE.md").read_text() == "# Ours\n\nKeep it short.\n"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout


def _wiki_building(fake_repo: Path, **config) -> tuple[Host, str]:
    checkpoint.ensure(fake_repo)
    host = Host(fake_repo, auto_commit=False)
    host.town.machine.tools = {t: ToolChoice(enabled=t in ("claude", "codex")) for t in host.town.machine.tools}
    spec = buildings.type_spec(host.town, "scrolls")
    spec["config"] = {**(spec.get("config") or {}), "auto_ingest": False, "sources": ["docs"], **config}
    bid = buildings.raise_spec(host.town, spec).id
    w = host.town.worker(bid)
    (w.wiki_root / "pages" / "concepts").mkdir(parents=True)
    (w.wiki_root / "pages" / "concepts" / "roads.md").write_text("# Roads\n")
    w.refresh()
    return host, bid


def test_an_approved_review_writes_the_rules_as_the_setting_says(fake_repo: Path, tmp_path: Path):
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    (fake_repo / "CLAUDE.md").write_text("# Project rules\n")
    _git(fake_repo, "add", "CLAUDE.md")
    _git(fake_repo, "commit", "-qm", "rules")
    host, bid = _wiki_building(fake_repo, agent_rules="review", rules_in=[outside.as_posix()])
    w = host.town.worker(bid)
    w.record_verdict("Rework: the page is thin", "spot-check", approved=False)
    assert not (w.wiki_root / "RULES.md").exists()                                  # sent back: nothing
    w.record_verdict("Approved", "spot-check", approved=True)
    assert "Rules for AI tools" in (w.wiki_root / "RULES.md").read_text()
    assert (fake_repo / "CLAUDE.md").read_text().startswith("# Project rules\n")
    assert "@llm-wiki/general/RULES.md" in (fake_repo / "CLAUDE.md").read_text()
    assert "llm-wiki/general/RULES.md" in (fake_repo / "AGENTS.md").read_text()
    assert str(w.wiki_root / "RULES.md") in (outside / "AGENTS.md").read_text()      # outside: the full path
    committed = _git(fake_repo, "show", "--name-only", "--format=%an", "HEAD")
    assert "Scroll Scrapper" in committed and "CLAUDE.md" in committed and "AGENTS.md" in committed
    view = host.detail(bid)["data"]["rules"]
    assert view["mode"] == "review" and not view["ready"] and view["written"]
    assert set(view["files"]) >= {"CLAUDE.md", "AGENTS.md", (outside / "AGENTS.md").as_posix()}
    assert host.command("act", {"id": bid, "act": "remove_rules", "args": {}})
    assert (fake_repo / "CLAUDE.md").read_text() == "# Project rules\n" and not (outside / "AGENTS.md").exists()
    assert host.detail(bid)["data"]["rules"]["files"] == []


def test_ask_me_keeps_them_ready_and_off_writes_nothing(fake_repo: Path):
    (fake_repo / "AGENTS.md").write_text("# Mine, not committed yet\n")
    host, bid = _wiki_building(fake_repo, commit=True)
    w = host.town.worker(bid)
    w.approved()
    assert host.detail(bid)["data"]["rules"]["ready"] and not (fake_repo / "AGENTS.md").read_text().count("orkcraft")
    written = host.command("act", {"id": bid, "act": "write_rules", "args": {}})
    assert "AGENTS.md" in written and "CLAUDE.md" in written
    assert not host.detail(bid)["data"]["rules"]["ready"]
    status = _git(fake_repo, "status", "--porcelain")
    assert "?? AGENTS.md" in status and "CLAUDE.md" not in status               # a person's file stays theirs to commit
    assert host.command("act", {"id": bid, "act": "rules_mode", "args": {"mode": "off"}}) == "off"
    host.command("act", {"id": bid, "act": "remove_rules", "args": {}})
    w.approved()
    assert not host.detail(bid)["data"]["rules"]["ready"] and not (fake_repo / "CLAUDE.md").exists()
    with pytest.raises(CommandError):
        host.command("act", {"id": bid, "act": "rules_mode", "args": {"mode": "always"}})
