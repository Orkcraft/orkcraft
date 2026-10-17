"""The git of an idea's tasks (realm/idea_git.py): the gate's files, the fast-forward, the secrets."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from orkcraft.realm import idea_git
from orkcraft.realm.idea_git import IdeaGit


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    git(r, "init", "-b", "main")
    git(r, "config", "user.email", "t@x")
    git(r, "config", "user.name", "T")
    (r / ".gitignore").write_text(".orkcraft/\n")
    (r / "a.txt").write_text("a\n")
    git(r, "add", "-A")
    git(r, "commit", "-m", "start")
    return r


def commit_in(path: Path, name: str, text: str) -> None:
    (path / name).write_text(text)
    git(path, "add", "-A")
    git(path, "commit", "-m", f"edit {name}")


def test_the_gate_runs_the_critical_tests_and_those_of_touched_modules(tmp_path):
    (tmp_path / "tests").mkdir()
    for name in ("test_architecture.py", "test_cli.py", "test_updates.py", "test_ideas.py", "test_x.py"):
        (tmp_path / "tests" / name).write_text("")
    files = idea_git.test_files(["orkcraft/realm/ideas.py", "orkcraft/gone.py", "tests/test_x.py", "README.md",
                                 "orkcraft/__init__.py"], tmp_path)
    assert files == [*idea_git.CRITICAL_TESTS, "tests/test_ideas.py", "tests/test_x.py"]


def test_a_task_branch_lands_on_main_checked_out_and_its_files_follow(repo):
    g = IdeaGit(repo)
    path, branch = g.prepare("demo", "k1", "main")
    assert branch == "idea/demo/k1" and git(path, "rev-parse", "--abbrev-ref", "HEAD") == branch
    commit_in(path, "b.txt", "b\n")
    commit, subjects, note = g.land(path, branch, "main", push=True)
    assert commit == git(repo, "rev-parse", "main") and subjects == ["edit b.txt"] and note == ""
    assert (repo / "b.txt").read_text() == "b\n"


def test_main_checked_out_with_the_touched_file_dirty_is_left_as_it_was(repo):
    g = IdeaGit(repo)
    path, branch = g.prepare("demo", "k1", "main")
    commit_in(path, "a.txt", "task\n")
    (repo / "a.txt").write_text("the owner's own edit\n")
    before = git(repo, "rev-parse", "main")
    with pytest.raises(RuntimeError, match="uncommitted changes in a.txt"):
        g.land(path, branch, "main")
    assert git(repo, "rev-parse", "main") == before
    assert (repo / "a.txt").read_text() == "the owner's own edit\n"


def test_an_unrelated_dirty_file_does_not_stop_the_fast_forward(repo):
    g = IdeaGit(repo)
    path, branch = g.prepare("demo", "k1", "main")
    commit_in(path, "b.txt", "b\n")
    (repo / "a.txt").write_text("the owner's own edit\n")
    g.land(path, branch, "main")
    assert (repo / "b.txt").exists() and (repo / "a.txt").read_text() == "the owner's own edit\n"


def test_a_second_prepare_cuts_the_branch_anew(repo):
    g = IdeaGit(repo)
    path, branch = g.prepare("demo", "k1", "main")
    commit_in(path, "b.txt", "old try\n")
    path, _ = g.prepare("demo", "k1", "main")
    assert git(path, "rev-parse", "HEAD") == git(repo, "rev-parse", "main")
    assert not (path / "b.txt").exists()


def test_a_push_failure_is_a_note_not_a_failure(repo, tmp_path):
    git(repo, "remote", "add", "origin", str(tmp_path / "nowhere.git"))
    g = IdeaGit(repo)
    path, branch = g.prepare("demo", "k1", "main")
    commit_in(path, "b.txt", "b\n")
    _commit, _subjects, note = g.land(path, branch, "main", push=True)
    assert note.startswith("push failed")


def test_one_lock_per_repository(repo):
    assert idea_git.lock_of(repo) is idea_git.lock_of(repo / ".") is IdeaGit(repo).lock


def test_secrets_are_read_from_the_state_file(tmp_path):
    (tmp_path / "secrets.json").write_text(json.dumps({"ideas/demo/t1": "v1", "other": {"t2": "v2"}}))
    assert idea_git.read_secret(tmp_path, "demo", "t1") == "v1"
    assert idea_git.read_secret(tmp_path, "other", "t2") == "v2"
    assert idea_git.read_secret(tmp_path, "demo", "nope") is None
    assert idea_git.read_secret(tmp_path / "missing", "demo", "t1") is None


def test_the_env_name_comes_from_the_todos_title():
    assert idea_git.env_name("Add API_KEY for the mailer") == "API_KEY"
    assert idea_git.env_name("The STRIPE token: STRIPE_SECRET") == "STRIPE_SECRET"
    assert idea_git.env_name("GITHUB token") == "GITHUB"
    assert idea_git.env_name("a key") == ""
