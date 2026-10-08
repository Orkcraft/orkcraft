"""Git worktrees for orkspaces (real git in a temporary repository)."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from orkcraft import scroll as ts
from orkcraft.realm import worktrees as wt

PRESETS = {"forge": {"title": "Forge", "icon": "⚒️", "orc": "Smith", "role": "kanban", "category": "core"}}


def _git(repo, *args):
    subprocess.run(["git", "-c", "user.email=a@b", "-c", "user.name=a", *args], cwd=repo, check=True,
                   capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    (r / ".gitignore").write_text(".orkcraft/\n", encoding="utf-8")
    (r / "a.md").write_text("a\n", encoding="utf-8")
    _git(r, "add", ".")
    _git(r, "commit", "-qm", "init")
    return r


def test_create_link_status_remove(repo: Path):
    path = wt.create(repo, "auth_core", "feat/auth")
    assert path == repo / ".orkcraft" / "worktrees" / "auth_core" and (path / "a.md").exists()
    assert wt.status(path).branch == "feat/auth" and not wt.status(path).dirty
    scroll = ts.default_scroll(PRESETS)
    lab = ts.new_orkspace(scroll, "Auth Core", "void")
    wt.link(scroll, lab.id, repo, path, "feat/auth")
    assert (lab.git.enabled, lab.git.mode, lab.git.path, lab.git.branch) == \
        (True, "worktree", "./.orkcraft/worktrees/auth_core", "feat/auth")
    assert ts.validate(scroll.to_dict()) == []
    assert wt.cwd_for(scroll, lab.id, repo) == path.resolve()
    assert wt.cwd_for(scroll, "main_camp", repo) == repo

    (path / "b.md").write_text("new\n", encoding="utf-8")
    assert wt.status(path).dirty and wt.status(path).changes == 1
    with pytest.raises(wt.WorktreeError, match="uncommitted"):
        wt.remove(repo, path)
    wt.remove(repo, path, force=True)
    assert not path.exists() and wt.branch_exists(repo, "feat/auth")      # the branch stays
    wt.unlink(scroll, lab.id)
    assert wt.cwd_for(scroll, lab.id, repo) == repo


def test_existing_branch_is_reused_and_bad_input_refused(repo: Path):
    _git(repo, "branch", "fix/login")
    path = wt.create(repo, "fix", "fix/login")
    assert wt.status(path).branch == "fix/login"
    for oid, branch, base in (("fix", "other", "HEAD"), ("x2", "bad..name", "HEAD"), ("x3", "-rf", "HEAD"),
                              ("x4", "ok", "--upload-pack=evil"), ("../escape", "ok", "HEAD")):
        with pytest.raises(wt.WorktreeError):
            wt.create(repo, oid, branch, base)
    with pytest.raises(wt.WorktreeError, match="not an orkcraft worktree"):
        wt.remove(repo, repo)


def test_cwd_ignores_a_link_outside_the_worktrees_folder(repo: Path):
    scroll = ts.default_scroll(PRESETS)
    camp = scroll.orkspaces[0]
    camp.git = ts.GitLink(True, "worktree", "../../etc", "x")
    assert wt.cwd_for(scroll, camp.id, repo) == repo


def test_warder_events_become_the_warder_orcs_alert(tmp_path: Path):
    import datetime as dt
    import json
    from orkcraft.realm import council, roster as rs
    from orkcraft.realm.orcs import COUNCIL, Orc

    repo = tmp_path / "repo"
    (repo / ".orkcraft").mkdir(parents=True)
    now = dt.datetime.now()
    old = (now - dt.timedelta(hours=30)).isoformat(timespec="seconds")
    fresh = (now - dt.timedelta(minutes=5)).isoformat(timespec="seconds")
    lines = [
        {"ts": old, "decision": "deny", "tool": "Bash", "reason": "old", "subject": "x"},
        {"ts": fresh, "decision": "error", "reason": "boom"},
        {"ts": fresh, "decision": "deny", "tool": "Bash", "reason": "secret", "subject": "cat .env"},
    ]
    (repo / council.WARDER_LOG).write_text("\n".join(json.dumps(l) for l in lines) + "\nnot json\n", encoding="utf-8")
    events = council.warder_events(repo)
    assert [e.reason for e in events] == ["secret"]
    orcs = [Orc("Warder", "security", COUNCIL, status="draft"), Orc("Keeper", "health", COUNCIL, status="draft")]
    rs._warder_watch(repo, orcs, set())
    assert orcs[0].status == "alert" and orcs[0].alert.source == "warder"
    assert "cat .env" in orcs[0].alert.context[0] and orcs[1].status == "draft"
    orcs = [Orc("Warder", "security", COUNCIL, status="draft")]
    rs._warder_watch(repo, orcs, {events[0].id})
    assert orcs[0].status == "idle" and orcs[0].alert is None          # dismissed: live, quiet
