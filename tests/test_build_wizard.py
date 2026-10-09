"""The build wizard (T1105 stage 3): type → description → Foreman's prefilled spec → review → raise."""
from __future__ import annotations

import json
from pathlib import Path


from orkcraft.realm import builders

SIZE = (160, 50)

TASKS = {"type": "fields", "id": "release_todo", "title": "Release tasks", "icon": "📋", "summary": "release checklist",
         "orc": {"name": "Smith", "role": "keeps the release list"}, "size": "M",
         "events": ["tasks.status_changed", "tasks.created"], "quick_actions": ["tasks.new"],
         "config": {"path": "docs/release.md"}}


def runner_of(*answers):
    queue = list(answers)
    prompts: list[str] = []

    def run(prompt: str):
        prompts.append(prompt)
        a = queue.pop(0) if len(queue) > 1 else queue[0]
        return (a if isinstance(a, str) else json.dumps(a)), 0.01
    run.prompts = prompts
    return run


# -- the Foreman --------------------------------------------------------------------------------------

def test_the_foreman_knows_the_roofs_and_a_wrong_one_is_refused(fake_repo: Path):
    run = runner_of(dict(TASKS, roof="tower"), dict(TASKS, roof="pagoda"))
    result = builders.propose("a release checklist", fake_repo, "tasks", runner=run)
    assert "gable, thatch, tiles" in run.prompts[0]
    assert result.spec["roof"] == "pagoda" and "roof: no 'tower'" in run.prompts[1]


def test_propose_prefills_a_checked_spec(fake_repo: Path):
    run = runner_of(TASKS)
    r = builders.propose("a release checklist", fake_repo, "tasks", runner=run)
    assert r.ok and r.spec["type"] == "fields" and len(r.attempts) == 1 and r.cost_usd == 0.01
    assert "Its type is fixed: fields." in run.prompts[0] and "tasks.status_changed" in run.prompts[0]
    assert "mail.received" not in run.prompts[0]                      # only the chosen type's catalog


def test_propose_retries_with_feedback_and_the_pick_wins(fake_repo: Path):
    bad = {**TASKS, "events": ["mail.received"], "type": "watchtower"}      # wrong type and a foreign event
    run = runner_of(bad, TASKS)
    r = builders.propose("a release checklist", fake_repo, "tasks", runner=run)
    assert r.ok and len(r.attempts) == 2
    assert "REJECTED" in run.prompts[1] and "does not send 'mail.received'" in run.prompts[1]


def test_auto_type_and_custom_is_not_built_anew(fake_repo: Path):
    """Custom (panes) left the catalog: the Foreman never offers it and never hands over to Mason & Artisan."""
    run = runner_of(TASKS)
    r = builders.propose("a release checklist", fake_repo, None, runner=run)
    assert r.ok and "Pick the type" in run.prompts[0] and "mail.received" in run.prompts[0]
    assert "Custom (panes)" not in run.prompts[0]
    run2 = runner_of({"type": "custom"}, TASKS)                       # the model asks for panes anyway
    r2 = builders.propose("a release checklist", fake_repo, None, runner=run2)
    assert r2.ok and r2.spec["type"] == "fields" and len(r2.attempts) == 2
    assert "'custom' is not offered" in run2.prompts[1] and not any(p.startswith("You are Mason") for p in run2.prompts)
    run3 = runner_of(TASKS)                                           # a picked custom type: refused, no model call
    r3 = builders.propose("recent commits", fake_repo, "custom", runner=run3)
    assert not r3.ok and "no longer built" in r3.error and run3.prompts == []


def test_propose_reports_cli_failure(fake_repo: Path):
    def boom(prompt):
        raise RuntimeError("Claude Code CLI not found")
    r = builders.propose("x", fake_repo, "tasks", runner=boom)
    assert not r.ok and "not found" in r.error


# -- the screens --------------------------------------------------------------------------------------

async def _settle(pilot, n: int = 4) -> None:
    for _ in range(n):
        await pilot.pause()


async def _until(pilot, cond, tries: int = 80) -> bool:
    for _ in range(tries):
        await pilot.pause(0.05)
        if cond():
            return True
    return False
