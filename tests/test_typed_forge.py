"""⚒️ The Forge merges (T1107 stage 7): tests, conflicts, squash, the checked-out base, confirm."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


from orkcraft.realm import forge


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


def test_a_test_command_that_needs_a_shell_gets_one(fake_repo: Path):
    assert forge.test_argv("pytest -q") == ["pytest", "-q"]
    assert forge.test_argv("pytest -q && ruff check .") == ["sh", "-c", "pytest -q && ruff check ."]
    import threading
    from orkcraft.realm import jobs
    passed, out = jobs.TaskGit().test(fake_repo, "true && echo both ran", threading.Event())
    assert passed and "both ran" in out
    assert jobs.TaskGit().test(fake_repo, "true && false", threading.Event())[0] is False
