"""Improve Orkline (docs/design/improve-buildings.md §14): comments on any part of the window for the Alchemist and the
Mechanic's code findings, each written as a fix in a copy of Orkline's source — a worktree of the checkout it runs
from, else the package as installed — shown, previewed and sent as a pull request. No agent and no GitHub run here."""
from __future__ import annotations

import subprocess
import time
from pathlib import Path

import pytest

from orkcraft.design import agents
from orkcraft.realm import day_review, fixes, work_copy


def test_a_worktree_of_the_checkout_holds_the_whole_repository(fake_repo, tmp_path):
    copy = work_copy.make(tmp_path / "copies" / "f1", fake_repo)
    top = Path(copy["top"])
    assert copy["kind"] == "worktree" and (top / "README.md").is_file() and (top / "src" / "app.py").is_file()
    (top / "README.md").write_text("# Demo project\n\nBetter words.\n", encoding="utf-8")
    (top / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n\0\0")
    (top / "docs" / "notes.md").unlink()
    work_copy.allow_tests(top, "/py/bin/python")                                   # the copy's own: never a change
    assert "Bash(/py/bin/python -m pytest:*)" in (top / work_copy.SETTINGS).read_text()
    assert work_copy.changed(top, copy["base"]) == ["README.md", "logo.png"]
    assert work_copy.deleted(top, copy["base"]) == ["docs/notes.md"]
    got = work_copy.files(top, copy["base"])
    assert got["README.md"] == ("# Demo project\n\nA small project for the tests.\n", "# Demo project\n\nBetter words.\n")
    assert got["logo.png"] == (b"", b"\x89PNG\r\n\x1a\n\0\0")                     # a picture: bytes
    assert "+Better words." in work_copy.diff(top, copy["base"])
    assert subprocess.run(["git", "status", "--porcelain"], cwd=fake_repo, capture_output=True,
                          text=True).stdout == ""                                 # the checkout itself: untouched
    work_copy.drop(top, fake_repo)
    assert not top.exists()
    listed = subprocess.run(["git", "worktree", "list"], cwd=fake_repo, capture_output=True, text=True).stdout
    assert str(top) not in listed


def test_without_a_checkout_the_package_as_installed_is_copied(tmp_path):
    copy = work_copy.make(tmp_path / "f2", None)
    top = Path(copy["top"])
    assert copy["kind"] == "package" and (top / "orkcraft" / "gui" / "static" / "app.js").is_file()
    assert not (top / "tests").exists() and work_copy.changed(top, copy["base"]) == []
    js = top / "orkcraft" / "gui" / "static" / "app.js"
    js.write_text(js.read_text(encoding="utf-8") + "// the Alchemist was here\n", encoding="utf-8")
    assert work_copy.changed(top, copy["base"]) == ["orkcraft/gui/static/app.js"]
    work_copy.drop(top)
    assert not top.exists()


def test_comments_and_fixes_are_kept_and_a_fix_left_writing_is_said(tmp_path):
    store = fixes.Store(tmp_path)
    with pytest.raises(ValueError):
        store.comment("  ")
    c = store.comment("The button says nothing", {"selector": "div > button.ok-btn", "html": "x" * 5000,
                                                 "window": "Agent pool", "secret": "never kept"})
    assert c.where["html"] == "x" * 1500 and "secret" not in c.where
    f = store.fix("alchemist", [c.text], fixes.comments_about([c]))
    c.fix = f.id
    store.save()
    again = fixes.Store(tmp_path)
    assert again.waiting() == [] and again.get(f.id).state == "failed" and "closed" in again.get(f.id).error
    again.drop(f.id)
    assert fixes.Store(tmp_path).comments == [] and fixes.Store(tmp_path).fixes == []


def test_the_agent_is_asked_with_its_persona_the_rules_and_the_comments(tmp_path):
    store = fixes.Store(tmp_path)
    c = store.comment("Make the Send button say what it sends", {"selector": "button.ok-btn", "window": "Loot",
                                                                   "html": "<button class=\"ok-btn\">Send</button>"})
    f = store.fix("alchemist", [c.text], fixes.comments_about([c]))
    f.base = "abc123def456"
    text = fixes.prompt(f, "worktree", "/py/bin/python")
    assert agents.persona("alchemist") in text and "CLAUDE.md" in text
    assert "/py/bin/python -m pytest -q tests/test_architecture.py tests/test_gui_wording.py" in text
    assert "“Make the Send button say what it sends”" in text and "Window: Loot" in text and "<button" in text
    assert "Change only `orkcraft/`" in fixes.prompt(f, "package", "python")
    assert "asks for more now:\n“and bigger”" in fixes.prompt(f, "worktree", "python", "and bigger")
    assert fixes.title(f) == "UX: Make the Send button say what it sends"
    f.said, f.kind = "Renamed the button.", "worktree"
    body = fixes.body(f, ["orkcraft/gui/static/js/loot.js"], [c], ["old.txt"])
    assert "“Make the Send button say what it sends” — on Loot" in body and "Renamed the button." in body
    assert "`orkcraft/gui/static/js/loot.js`" in body and "`old.txt`" in body and "from a git checkout" in body


@pytest.fixture
def host(fake_repo, isolated_layout_file, monkeypatch):
    from orkcraft.core import running
    from orkcraft.gui.host import Host
    from orkcraft.realm import checkpoint
    checkpoint.ensure(fake_repo)
    monkeypatch.setattr(running, "checkout", lambda: fake_repo)      # Orkline "runs from" this checkout
    h = Host(fake_repo, auto_commit=False)
    monkeypatch.setattr(h.town, "call", lambda fn, *a: fn(*a))
    yield h
    h.close()


def _wait(host, fid, state="ready"):
    for _ in range(500):
        if host.fixes.store.get(fid).state == state:
            return host.fixes.store.get(fid)
        time.sleep(0.01)
    raise AssertionError(host.fixes.store.get(fid))


def test_a_comment_becomes_a_fix_previewed_and_sent_as_a_pull_request(host, monkeypatch):
    from orkcraft.gui import server
    from orkcraft.realm import github_app, jobs
    asked = []

    def agent(tool, prompt, workdir, cancel, model="", **kw):
        asked.append((prompt, workdir))
        page = workdir / "orkcraft" / "gui" / "static"
        page.mkdir(parents=True, exist_ok=True)
        (page / "app.js").write_text("// laid out again\n", encoding="utf-8")
        return "Moved the button.", None, None, ""

    monkeypatch.setattr(jobs, "run_work", agent)
    said = host.command("fixes.comment", {"text": "The button is lost", "where": {"selector": "button", "window": "Loot"}})
    assert "The Alchemist has it" in said["said"] and host.snapshot()["fixes"]["comments"] == 1
    state = host.command("fixes.ask", {})
    [row] = state["fixes"]
    f = _wait(host, row["id"])
    [(prompt, workdir)] = asked
    assert "“The button is lost”" in prompt and (workdir / "README.md").is_file()      # a worktree of the checkout
    assert f.files == ["orkcraft/gui/static/app.js"] and f.said == "Moved the button."
    shown = host.command("fixes.state")
    assert shown["comments"] == [] and shown["fixes"][0]["page"] and "+// laid out again" in shown["fixes"][0]["diff"]

    assert host.command("fixes.preview", {"id": f.id})["reload"] is True
    assert server.resolve("/static/app.js", host.fixes.preview_dir()).read_text() == "// laid out again\n"
    assert server.resolve("/static/town.css", host.fixes.preview_dir()) == server.STATIC.resolve() / "town.css"
    host.command("fixes.preview", {"id": ""})
    assert host.fixes.preview_dir() is None

    pr = host.command("fixes.pr", {"id": f.id})
    assert pr["title"] == "UX: The button is lost" and "“The button is lost” — on Loot" in pr["body"]
    with pytest.raises(Exception, match="Connect GitHub first"):
        host.command("fixes.send", {"id": f.id})
    sent = []
    monkeypatch.setattr(github_app, "account", lambda: {"login": "orkfan", "token": "t"})
    monkeypatch.setattr(github_app, "send", lambda changes, title, body, branch: sent.append((changes, branch))
                        or "https://github.com/orkcraft/orkcraft/pull/7")
    host.command("fixes.send", {"id": f.id})
    f = _wait(host, f.id, "sent")
    [(changes, branch)] = sent
    assert changes == {"orkcraft/gui/static/app.js": ("", "// laid out again\n")} and branch.startswith("improve/alchemist-")
    assert f.pr.endswith("/pull/7")
    host.command("fixes.drop", {"id": f.id})
    assert host.command("fixes.state")["fixes"] == [] and not Path(f.top).exists()


def test_the_mechanic_writes_a_code_finding_as_a_fix(host, monkeypatch):
    from orkcraft.realm import jobs
    review = day_review.Review("2026-10-12", hotspots=[{"id": "H1", "said": "a call of Agent pool failed (exit 1)"}],
                               findings=[day_review.Finding("mechanic", "pool", "it crashes on an empty card",
                                                            "every empty card fails", "code",
                                                            "skip an empty card in the worker", ["H1"])])
    day_review.save(host.town.repo_root, review)
    asked = []

    def agent(tool, prompt, workdir, cancel, model="", **kw):
        asked.append(prompt)
        return "Nothing needed.", None, None, ""

    monkeypatch.setattr(jobs, "run_work", agent)
    said = host.command("fixes.finding", {"day": "2026-10-12", "n": 0})
    f = _wait(host, said["id"], "empty")
    assert agents.persona("mechanic") in asked[0] and "H1: a call of Agent pool failed" in asked[0]
    assert "skip an empty card in the worker" in asked[0] and f.who == "mechanic"
    with pytest.raises(Exception, match="That finding is gone"):
        host.command("fixes.finding", {"day": "2026-10-12", "n": 5})
