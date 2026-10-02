"""⎇ Git Branches (T1105 stage 5): branches, PRs, change counts, events between looks."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from orkcraft import scroll as ts
from orkcraft.app import OrkcraftApp
from orkcraft.realm import gitinfo, masonry
from orkcraft.screens.typed.git_view import GitView

SIZE = (200, 46)
SPEC = {"id": "branches", "title": "Branches", "icon": "⎇", "orc": {"name": "Engineer"}, "type": "git"}


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout


def feature(repo: Path, name: str = "feature", lines: int = 3) -> None:
    git(repo, "checkout", "-q", "-b", name)
    (repo / "src" / f"{name}.py").write_text("".join(f"x{i} = {i}\n" for i in range(lines)))
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", f"add {name}")
    git(repo, "checkout", "-q", "-")


def gh(rows: list[dict]):
    return lambda *a, **kw: SimpleNamespace(returncode=0, stdout=json.dumps(rows), stderr="")


def test_snapshot_reads_branches_change_counts_and_prs(fake_repo: Path):
    feature(fake_repo, "feature", 3)
    snap = gitinfo.snapshot(fake_repo, pr_runner=gh([
        {"number": 7, "state": "OPEN", "headRefName": "feature", "url": "https://x/7", "title": "Add feature",
         "isDraft": False},
        {"number": 3, "state": "MERGED", "headRefName": "feature", "url": "https://x/3", "title": "old"}]))
    assert snap.base in ("main", "master") and not snap.error and snap.prs_known
    f = next(b for b in snap.branches if b.name == "feature")
    assert (f.ahead, f.behind, f.files, f.added, f.removed) == (1, 0, 1, 3, 0)
    assert f.pr is not None and f.pr.number == 7 and f.pr.badge == "◯#7"          # the newest PR wins
    assert f.change == "+3−0"
    assert "add feature" in gitinfo.detail(fake_repo, snap.base, "feature")


def test_no_gh_means_no_prs_and_no_pr_events(fake_repo: Path):
    fail = lambda *a, **kw: SimpleNamespace(returncode=1, stdout="", stderr="not logged in")
    snap = gitinfo.snapshot(fake_repo, pr_runner=fail)
    assert not snap.prs_known and all(b.pr is None for b in snap.branches)
    assert gitinfo.parse_shortstat(" 2 files changed, 5 insertions(+), 1 deletion(-)") == (2, 5, 1)
    assert gitinfo.parse_shortstat(" 1 file changed, 2 deletions(-)") == (1, 0, 2)


def test_changes_between_looks(fake_repo: Path):
    feature(fake_repo, "feature")
    before = gitinfo.snapshot(fake_repo, pr_runner=gh([]))
    assert gitinfo.changes(None, before) == []                                   # the first look: baseline
    git(fake_repo, "checkout", "-q", "feature")
    (fake_repo / "more.txt").write_text("more\n")
    git(fake_repo, "add", ".")
    git(fake_repo, "commit", "-q", "-m", "more work")
    opened = gitinfo.snapshot(fake_repo, pr_runner=gh([
        {"number": 9, "state": "OPEN", "headRefName": "feature", "url": "u", "title": "Feature"}]))
    evs = gitinfo.changes(before, opened)
    assert ("git.commit", "feature: more work") in evs and ("git.pr_opened", "feature: #9 Feature") in evs
    merged = gitinfo.snapshot(fake_repo, pr_runner=gh([
        {"number": 9, "state": "MERGED", "headRefName": "feature", "url": "u", "title": "Feature"}]))
    assert gitinfo.changes(opened, merged) == [("git.pr_merged", "feature: #9 Feature")]


@pytest.mark.asyncio
async def test_the_git_building_lists_branches_and_sends_commits(fake_repo: Path, monkeypatch):
    monkeypatch.setattr(gitinfo, "pull_requests", lambda repo, runner=None: None)
    feature(fake_repo, "feature", 4)
    assert masonry.save_spec(fake_repo, SPEC) == []
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    ts.subscribe(app.scroll, "loot", "branches", "git.commit")
    async with app.run_test(size=SIZE) as pilot:
        view = app.desktop.get_window("branches").query_one(GitView)
        for _ in range(30):
            await pilot.pause(0.05)
            if view.snap is not None:
                break
        assert view.snap is not None
        assert any("feature" in line and "+4−0" in line for line in view.mini_status())
        assert view.query_one("#git-branches").option_count == 2
        assert "PRs: install" in str(view.query_one("#git-head").render())

        sent = []
        monkeypatch.setattr(app.roads, "emit", lambda payload, meta=None: sent.append(payload) or [])
        git(fake_repo, "checkout", "-q", "feature")
        (fake_repo / "b.txt").write_text("b\n")
        git(fake_repo, "add", ".")
        git(fake_repo, "commit", "-q", "-m", "second step")
        view.apply_snapshot(gitinfo.snapshot(fake_repo, with_prs=False))
        assert [(p.mode, p.value) for p in sent] == [("git.commit", "feature: second step")]

        notes = []
        monkeypatch.setattr(app, "notify", lambda msg, **kw: notes.append(msg))
        assert view.quick_action("git.open_pr") and "no pull request" in notes[-1]
