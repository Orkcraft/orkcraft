"""⚒️ The Forge merges (T1107 stage 7): tests, conflicts, squash, the checked-out base, confirm."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from orkcraft import scroll as ts
from orkcraft.app import OrkcraftApp
from orkcraft.realm import forge, masonry, pipes
from orkcraft.screens.dialogs import Confirm
from orkcraft.screens.typed.git_view import GitView


def git(repo: Path, *a: str) -> str:
    return subprocess.run(["git", *a], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


def branch(repo: Path, name: str, files: dict[str, str]) -> None:
    git(repo, "checkout", "-q", "-b", name)
    for path, text in files.items():
        (repo / path).write_text(text)
        git(repo, "add", path)
        git(repo, "commit", "-q", "-m", f"{name}: {path}")
    git(repo, "checkout", "-q", "-")


def base_of(repo: Path) -> str:
    return git(repo, "symbolic-ref", "--short", "HEAD")


def test_squash_merge_into_the_checked_out_base(fake_repo: Path):
    base = base_of(fake_repo)
    branch(fake_repo, "feat", {"src/a.py": "A = 1\n", "src/b.py": "B = 2\n"})
    res = forge.merge(fake_repo, "feat", base)
    assert res.ok and res.message.startswith("squash: feat (2 commits)") and "- feat: src/a.py" in res.message
    assert (fake_repo / "src" / "a.py").read_text() == "A = 1\n"            # the checkout moved too
    assert git(fake_repo, "log", "-1", "--format=%s") == "squash: feat (2 commits)"
    assert git(fake_repo, "rev-list", "--count", f"HEAD^..HEAD") == "1"
    again = forge.merge(fake_repo, "feat", base)
    assert not again.ok and "nothing" in again.error


def test_conflicts_dirty_tree_tests_and_a_base_not_checked_out(fake_repo: Path):
    base = base_of(fake_repo)
    branch(fake_repo, "clash", {"README.md": "theirs\n"})
    (fake_repo / "README.md").write_text("ours\n")
    assert "uncommitted" in forge.merge(fake_repo, "clash", base).error  # a dirty checked-out base
    git(fake_repo, "commit", "-qam", "ours")
    res = forge.merge(fake_repo, "clash", base)
    assert not res.ok and res.conflicts == ["README.md"] and (fake_repo / "README.md").read_text() == "ours\n"
    branch(fake_repo, "red", {"src/c.py": "C = 3\n"})
    fail = f"{sys.executable} -c \"raise SystemExit('boom')\""
    res = forge.merge(fake_repo, "red", base, fail)
    assert not res.ok and res.error == "tests failed" and "boom" in res.tests
    ok = f"{sys.executable} -c \"import pathlib; assert pathlib.Path('src/c.py').exists()\""
    git(fake_repo, "checkout", "-q", "-b", "elsewhere")                    # the base is not checked out
    res = forge.merge(fake_repo, "red", base, ok)
    assert res.ok and git(fake_repo, "log", "-1", "--format=%s", base) == "squash: red (1 commit)"
    assert not (fake_repo / "src" / "c.py").exists()                       # this checkout untouched
    assert len(git(fake_repo, "worktree", "list").splitlines()) == 1       # the test worktree is gone


@pytest.mark.asyncio
async def test_the_forge_merges_at_once_or_after_a_yes(fake_repo: Path, monkeypatch):
    base = base_of(fake_repo)
    branch(fake_repo, "feat", {"src/a.py": "A = 1\n"})
    branch(fake_repo, "more", {"src/m.py": "M = 1\n"})
    spec = {"id": "smithy", "title": "Forge", "icon": "⚒️", "orc": {"name": "Smith"}, "type": "forge"}
    assert masonry.save_spec(fake_repo, spec) == []
    monkeypatch.setattr("orkcraft.realm.gitinfo.pull_requests", lambda repo, runner=None: None)
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    ts.subscribe(app.scroll, "town_hall", "smithy", "forge.merged")
    async with app.run_test(size=(200, 46)) as pilot:
        view = app.desktop.get_window("smithy").query_one(GitView)
        for _ in range(40):
            await pilot.pause(0.05)
            if view.snap is not None:
                break
        sent = []
        monkeypatch.setattr(app.roads, "emit", lambda payload, meta=None: sent.append(payload) or [])
        app.deliver_payload("smithy", pipes.Payload(pipes.TEXT, "done\n\n_branch:_ `feat`", "camp", "pool.done", "Login"))
        for _ in range(60):
            await pilot.pause(0.05)
            if view.last_merge is not None:
                break
        assert view.last_merge.ok and [p.mode for p in sent] == ["forge.merged"]   # no question asked
        assert "✓ feat merged" in view.mini_status()
        app.desktop.focus_window(app.desktop.get_window("smithy"))
        await pilot.pause()
        await pilot.press("c")                                          # confirmation on
        await pilot.pause()
        assert app.custom_specs["smithy"]["config"]["confirm"] is True
        assert view.merge("more")
        await pilot.pause()
        assert isinstance(app.screen, Confirm)
        await pilot.press("n")
        await pilot.pause()
        assert git(fake_repo, "log", "-1", "--format=%s", base).startswith("squash: feat")    # nothing merged
        view.merge("more")
        await pilot.pause()
        await pilot.press("y")
        for _ in range(60):
            await pilot.pause(0.05)
            if view.last_merge.branch == "more":
                break
        assert git(fake_repo, "log", "-1", "--format=%s", base) == "squash: more (1 commit)"
