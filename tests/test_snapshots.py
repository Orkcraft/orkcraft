"""Snapshots of a project's files (docs/design/projects.md §7): before and after an ork works in a project, the
working tree is kept in a hidden ref; the person's branch, index and log never move. Going back restores what
changed, removes what was added, never touches what git ignores, and is undone the same way. One History shows the
map's changes and the files' snapshots together."""
from __future__ import annotations

import subprocess
import time
from pathlib import Path

import pytest

from orkcraft.core import timeline
from orkcraft.gui.host import CommandError, Host
from orkcraft.realm import checkpoint, projects, snapshots


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


@pytest.fixture
def repo(tmp_path) -> Path:
    r = tmp_path / "shop"
    r.mkdir()
    (r / "app.py").write_text("print('v1')\n", encoding="utf-8")
    (r / ".gitignore").write_text("secret.env\n", encoding="utf-8")
    _git(r, "init", "-q", "-b", "main")
    _git(r, "add", "-A")
    _git(r, "-c", "user.email=t@t", "-c", "user.name=T", "commit", "-qm", "init")
    return r


def test_a_snapshot_keeps_the_tree_and_moves_nothing_of_the_persons(repo):
    (repo / "app.py").write_text("print('v2')\n", encoding="utf-8")
    (repo / "new.txt").write_text("untracked\n", encoding="utf-8")
    _git(repo, "add", "app.py")
    head, status, branch = _git(repo, "rev-parse", "HEAD"), _git(repo, "status", "--porcelain"), _git(repo, "branch")
    snap = snapshots.take(repo, "shop", "before Grom: Login form")
    assert snap is not None and snap.why == "before Grom: Login form"
    assert _git(repo, "rev-parse", "HEAD") == head and _git(repo, "status", "--porcelain") == status
    assert _git(repo, "branch") == branch and _git(repo, "stash", "list") == ""
    assert _git(repo, "log", "--oneline").count("\n") == 0                         # the person's log: one commit
    files = _git(repo, "ls-tree", "-r", "--name-only", snap.sha).splitlines()
    assert "new.txt" in files and "app.py" in files
    assert _git(repo, "show", f"{snap.sha}:app.py") == "print('v2')"
    assert snapshots.take(repo, "shop", "again") is None                            # nothing changed
    assert [s.sha for s in snapshots.listed(repo, "shop")] == [snap.sha]
    assert snapshots.listed(repo, "other") == []


def test_going_back_restores_removes_keeps_ignored_and_can_be_undone(repo):
    (repo / ".orkcraft").mkdir()                                                  # the camp's own git, inside
    _git(repo / ".orkcraft", "init", "-q")
    first = snapshots.take(repo, "shop", "before")
    assert not any(p.startswith(".orkcraft") for p in _git(repo, "ls-tree", "-r", "--name-only", first.sha).splitlines())
    (repo / ".orkcraft" / "state.json").write_text("{}", encoding="utf-8")
    (repo / "app.py").write_text("print('broken')\n", encoding="utf-8")
    (repo / "pkg").mkdir()
    (repo / "pkg" / "added.py").write_text("x = 1\n", encoding="utf-8")
    (repo / "secret.env").write_text("TOKEN=1\n", encoding="utf-8")
    index = (repo / ".git" / "index").read_bytes()
    safety = snapshots.restore(repo, "shop", first.sha)
    assert (repo / "app.py").read_text(encoding="utf-8") == "print('v1')\n"
    assert not (repo / "pkg").exists()
    assert (repo / "secret.env").exists()                                           # ignored: never touched
    assert (repo / ".orkcraft" / "state.json").exists()                             # the town's own: never touched
    assert (repo / ".git" / "index").read_bytes() == index                          # the person's index as it was
    assert safety is not None and safety.why == "before going back"
    snapshots.restore(repo, "shop", safety.sha)                                     # and back again
    assert (repo / "app.py").read_text(encoding="utf-8") == "print('broken')\n" and (repo / "pkg" / "added.py").exists()
    assert snapshots.changed(repo, safety.sha, first.sha) == ["app.py", "pkg/added.py"]
    with pytest.raises(snapshots.SnapshotError):
        snapshots.restore(repo, "shop", "0" * 40)


def test_old_snapshots_are_dropped(repo, monkeypatch):
    monkeypatch.setattr(snapshots, "KEEP_MAX", 2)
    for i in range(4):
        (repo / "app.py").write_text(f"print({i})\n", encoding="utf-8")
        snapshots.take(repo, "shop", f"step {i}")
    assert [s.why for s in snapshots.listed(repo, "shop")] == ["step 3", "step 2"]


def test_no_git_no_worktree_no_demo_no_snapshot(tmp_path, repo, fake_repo, isolated_layout_file):
    plain = tmp_path / "plain"
    plain.mkdir()
    assert snapshots.take(plain, "shop", "x") is None
    with pytest.raises(snapshots.SnapshotError):
        snapshots.take(repo, "../evil", "x")
    host = Host(fake_repo, auto_commit=False)
    try:
        oid = host.town.scroll.active_orkspace_id
        assert timeline.folder_for(host.town, oid, fake_repo) == fake_repo
        assert timeline.folder_for(host.town, oid, fake_repo / ".orkcraft" / "worktrees" / "x") is None
        host.town.demo = True
        assert timeline.folder_for(host.town, oid, fake_repo) is None
    finally:
        host.town.demo = False
        host.close()


def _until(cond, seconds: float = 10.0) -> bool:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.05)
    return cond()


def test_a_session_in_the_project_is_snapshotted_before_and_after(repo, fake_repo, isolated_layout_file):
    host = Host(fake_repo, auto_commit=False)
    try:
        oid = host.town.scroll.active_orkspace_id
        projects.link(host.town.scroll, oid, projects.add(host.town.scroll, "Shop", repo).id)
        (repo / "app.py").write_text("print('mine')\n", encoding="utf-8")
        s = host.sessions.open("t1", ["sh", "-c", "echo made > made.txt"], "bash", "Grom")
        assert s.cwd == str(repo.resolve()) and s.orkspace == oid
        assert _until(lambda: len(snapshots.listed(repo, oid)) == 2)
        after, before = snapshots.listed(repo, oid)
        assert before.why == "before Grom" and after.why == "after Grom"
        assert snapshots.changed(repo, after.sha, before.sha) == ["made.txt"]
    finally:
        host.sessions.close()
        host.close()


def test_one_history_shows_the_map_and_the_files_and_takes_the_files_back(repo, fake_repo, isolated_layout_file):
    checkpoint.ensure(fake_repo)
    host = Host(fake_repo, auto_commit=False)
    try:
        oid = host.command("orkspace.new", {"name": "Shop", "project": "town"})
        projects.link(host.town.scroll, oid, projects.add(host.town.scroll, "Shop", repo).id)
        first = snapshots.take(repo, oid, "before Grom: Login form")
        host.command("town.build", {"type": "pit"})                           # the same second: still after it
        (repo / "app.py").write_text("print('broken')\n", encoding="utf-8")
        snapshots.take(repo, oid, "after Grom: Login form")
        listed = host.command("history.list", {"orkspace": oid})
        assert listed["files"] is True
        kinds = [r["type"] for r in listed["rows"]]
        assert kinds[0] == "files" and "map" in kinds
        newest = listed["rows"][0]
        assert newest["changed"] == ["app.py"] and newest["changed_n"] == 1
        built = next(r for r in listed["rows"] if r["type"] == "map" and r["kind"] == "create")
        assert built["files"] == first.sha                                    # the files as they were at that moment
        r = host.command("history.revert", {"orkspace": oid, "sha": first.sha, "what": "files"})
        assert r["files"] is True and (repo / "app.py").read_text(encoding="utf-8") == "print('v1')\n"
        with pytest.raises(CommandError, match="Nothing to go back"):
            host.command("history.revert", {"orkspace": oid, "sha": first.sha, "what": "everything"})
        s = host.sessions.open("t2", ["sh", "-c", "sleep 5"], "bash", "Busy")
        assert s.cwd == str(repo.resolve())
        with pytest.raises(CommandError, match="An ork is at work"):
            host.command("history.revert", {"orkspace": oid, "sha": first.sha, "what": "files"})
    finally:
        host.sessions.close()
        host.close()
