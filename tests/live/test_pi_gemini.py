"""pi on Gemini Flash, for real: what orkcraft starts, the tool runs, and orkcraft reads back.

The tests check the shape of what comes back (an answer, its price, its tokens, its session; a file made
or not made), never a model's wording beyond one word it is told to say.
"""
from __future__ import annotations

import subprocess
import sys
import threading
from pathlib import Path

import pytest

from orkcraft.realm import builders, harnesses, jobs, roads
from tests.live.conftest import run, spend

pytestmark = pytest.mark.live


def _clean(repo: Path) -> bool:
    return not subprocess.run(["git", "status", "--porcelain"], cwd=repo, capture_output=True,
                              text=True).stdout.strip()


def test_a_bad_key_says_why(pi_bin, monkeypatch):
    """No key needed: the provider refuses, pi ends with 0, orkcraft says why in one line."""
    monkeypatch.setenv("GEMINI_API_KEY", "not-a-key")
    with pytest.raises(RuntimeError, match="API key not valid"):
        builders.ask("pi", "Say pong.", "google/gemini-flash-lite-latest")


def test_an_answer_comes_back_with_its_price(gemini, tmp_path, record):
    h = harnesses.need("pi")
    out = run(h.ask("Reply with the single word: pong", tmp_path, gemini), tmp_path)
    record("pi_json_ask", out)
    text, cost, tokens, session = h.result(out, 0)
    spend(cost)
    assert "pong" in text.lower() and tokens and session and not h.error(out)


def test_a_decision_runs_on_pi(gemini):
    text, cost = builders.ask("pi", "Reply with the single word: pong", gemini)
    spend(cost)
    assert "pong" in text.lower()


def test_a_reading_agent_reads_the_repository_and_writes_nothing(gemini, fake_repo):
    text, cost, _ = roads.run_agent("pi", "Read README.md and reply with its first line, exactly as written.",
                                    fake_repo, {}, threading.Event(), model=gemini)
    spend(cost)
    assert "Demo project" in text
    text, cost, _ = roads.run_agent("pi", "Create a file made.txt containing `hi`. If you have no tool that "
                                    "can, reply NO TOOL.", fake_repo, {}, threading.Event(), model=gemini)
    spend(cost)
    assert not (fake_repo / "made.txt").exists() and _clean(fake_repo)


def test_a_worker_edits_its_worktree_and_resumes_its_session(gemini, fake_repo):
    """A Barracks task in small: its branch, the work, a follow-up in the same session, the check, the diff."""
    git, cancel = jobs.TaskGit(), threading.Event()
    base = git.base_of(fake_repo)
    git.prepare(fake_repo, "pool/live/add", base)
    _, cost, _, session = jobs.run_work(
        "pi", "In src/app.py add a function `add(a, b)` that returns a + b. Keep the existing line. "
        "Then commit the change with git (message: Add add). Reply DONE when it is committed.",
        fake_repo, cancel, gemini)
    spend(cost)
    assert session, "pi named no session: the follow-up cannot resume it"
    _, cost, _, _ = jobs.run_work(
        "pi", "Now also add `sub(a, b)` returning a - b next to the function you added, and commit it "
        "(message: Add sub). Reply DONE.", fake_repo, cancel, gemini, resume=session)
    spend(cost)
    check = f"{sys.executable} -c \"import sys; sys.path.insert(0, 'src'); import app; " \
            "assert app.add(2, 3) == 5 and app.sub(5, 3) == 2\""
    passed, tail = git.test(fake_repo, check, cancel)
    assert passed, tail
    commits, diff = git.diff(fake_repo, base, "pool/live/add")
    assert commits >= 1 and "src/app.py" in diff and _clean(fake_repo)
