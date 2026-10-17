"""Spec 34 on the host: a goal by dialog and read at once, an idea read now or later, the keeper's priority and place,
the agents' roles and the task types, each with its event. The model call is stubbed (`jobs.run_read`)."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest

from orkcraft.gui import mobile
from orkcraft.gui.host import CommandError, Host
from orkcraft.realm import checkpoint, event_log, ideas, jobs

NEW_COMMANDS = {"ideas.goal_save", "ideas.goal", "ideas.read_now", "ideas.roles", "ideas.role_save", "ideas.role_drop",
                "ideas.kind_set"}
GOAL = {"title": "Grow installs", "about": "More people try Orkline.", "priority": "high", "deadline": "2026-12-01",
        "metrics": [{"name": "weekly installs", "target": "50"}, {"name": "", "target": "x"}],
        "links": ["docs/specs/34-v1-round-2.md", "https://example.com/post", "docs/specs/34-v1-round-2.md"]}


@pytest.fixture
def host(fake_repo) -> Host:
    checkpoint.ensure(fake_repo)
    h = Host(fake_repo, auto_commit=False)
    yield h
    sys.modules.pop("orkcraft.core.idea_runner", None)


@pytest.fixture
def model(monkeypatch):
    """A stubbed keeper: answers by what it is asked; `seen` holds every call."""
    seen = []
    answers = {"goal": {"summary": "Installs are the first step.\nCount them weekly.", "questions": ["Which channel first?"],
                        "metrics": [{"name": "weekly installs", "how": "npm downloads, per week"}], "reply": "Noted."},
               "idea": {"gist": "Dark mode.\nIt glares at night.", "why": "Moves weekly installs.", "size": "S",
                        "priority": "high", "priority_why": "Helps night users stay.", "before": "", "questions": []}}

    def run_read(harness, prompt, workdir, cancel, model="", env=None, resume="", timeout_s=0):
        kind = "goal" if "saved a goal" in prompt else "idea"
        seen.append({"kind": kind, "model": model, "prompt": prompt, "env": env})
        return json.dumps(answers[kind]), 0.01, 10, "s-1"

    monkeypatch.setattr(jobs, "run_read", run_read)
    run_read.seen, run_read.answers = seen, answers
    return run_read


def _wait(host, slug="", goal=False):
    k = host.ideas.keeper
    for _ in range(400):
        if not (k.busy_goal(slug) if goal else k.busy(slug)):
            return
        time.sleep(0.01)
    raise AssertionError("the keeper never finished")


def _events(host, name):
    return [r for r in event_log.read(Path(host.town.repo_root)) if r["event"] == name]


def test_the_new_commands_are_the_hosts_and_a_phones(host):
    assert NEW_COMMANDS <= set(host.commands) and NEW_COMMANDS <= set(mobile.COMMANDS)
    assert all(mobile.allowed(host, c, {}) for c in NEW_COMMANDS)


def test_a_goal_saved_is_read_by_the_keeper_at_once_and_written(host, model):
    slug = host.command("ideas.goal_save", GOAL)["slug"]
    assert slug == "grow-installs"
    _wait(host, slug, goal=True)
    (call,) = model.seen
    assert call["model"] == "sonnet" or "sonnet" in call["model"]                 # the warrior tier
    assert "More people try Orkline." in call["prompt"] and "weekly installs" in call["prompt"]
    assert "Write the specs" in call["prompt"] or "34-v1-round-2" in call["prompt"]            # a linked file is read …
    assert "https://example.com/post (a web link: not fetched)" in call["prompt"]            # … a URL only named
    g = host.command("ideas.goal", {"slug": slug})
    assert g["state"] == "asks" and g["priority"] == "high" and g["deadline"] == "2026-12-01"
    assert g["summary"].startswith("Installs are the first step.") and g["questions"] == ["Which channel first?"]
    assert g["metrics"] == [{"name": "weekly installs", "target": "50", "how": "npm downloads, per week"}]
    assert g["links"] == ["docs/specs/34-v1-round-2.md", "https://example.com/post"] and g["description"] == "More people try Orkline."
    text = (Path(host.town.repo_root) / "llm-wiki/general/pages/tracks/grow-installs.md").read_text()
    assert "priority: high" in text and "## Summary" in text and "## Metrics" in text and "## Open questions" in text
    board = host.command("ideas.board")
    row = next(t for t in board["tracks"] if t["slug"] == slug)
    assert row["state"] == "asks" and row["priority"] == "high" and row["metrics"] and row["links"]
    assert {"idea": "", "goal": slug, "kind": "goal", "title": "Grow installs", "text": "Which channel first?"} in board["today"]["needs_you"]
    saved = _events(host, "goal_saved")[0]
    assert saved["goal"] == slug and saved["new"] is True and saved["priority"] == "high" and saved["device"] == "desktop"
    assert saved["metrics"] == ["weekly installs"] and len(saved["links"]) == 2
    read = _events(host, "goal_read")[0]
    assert read["goal"] == slug and read["state"] == "asks" and read["seconds"] is not None


def test_editing_a_goal_sends_it_again_and_keeps_what_the_keeper_wrote(host, model):
    slug = host.command("ideas.goal_save", GOAL)["slug"]
    _wait(host, slug, goal=True)
    model.answers["goal"] = {"summary": "Second reading.", "questions": [], "metrics": []}
    host.command("ideas.goal_save", {**GOAL, "slug": slug, "title": "Grow installs fast", "priority": "low"})
    _wait(host, slug, goal=True)
    assert len(model.seen) == 2
    g = host.command("ideas.goal", {"slug": slug})
    assert g["state"] == "ready" and g["summary"] == "Second reading." and g["title"] == "Grow installs fast"
    assert g["metrics"][0]["how"] == "npm downloads, per week"           # how it is counted stays until the keeper says otherwise
    assert [e["new"] for e in _events(host, "goal_saved")] == [True, False]


def test_a_goal_is_checked_and_listed_by_priority(host, model):
    with pytest.raises(CommandError, match="title"):
        host.command("ideas.goal_save", {"title": " "})
    with pytest.raises(CommandError, match="Priority"):
        host.command("ideas.goal_save", {"title": "X", "priority": "urgent"})
    with pytest.raises(CommandError, match="deadline"):
        host.command("ideas.goal_save", {"title": "X", "deadline": "soon"})
    low = host.command("ideas.goal_save", {"title": "Later thing", "priority": "low"})["slug"]
    high = host.command("ideas.goal_save", {"title": "Urgent thing", "priority": "high"})["slug"]
    normal = host.command("ideas.goal_save", {"title": "Plain thing"})["slug"]
    for s in (low, high, normal):
        _wait(host, s, goal=True)
    assert [t["slug"] for t in host.command("ideas.board")["tracks"]] == [high, normal, low]


def test_the_answer_to_a_goals_question_is_the_same_talk_on_the_goal(host, model):
    slug = host.command("ideas.goal_save", GOAL)["slug"]
    _wait(host, slug, goal=True)
    model.answers["goal"] = {"summary": "Clear now.", "questions": [], "reply": "Thanks, npm first."}
    assert host.command("ideas.say", {"slug": slug, "text": "npm first"}) == {"ok": True}
    _wait(host, slug, goal=True)
    g = host.command("ideas.goal", {"slug": slug})
    assert g["state"] == "ready" and [(t["who"], t["text"]) for t in g["talk"]] == [("you", "npm first"), ("keeper", "Thanks, npm first.")]
    assert "npm first" in model.seen[-1]["prompt"]


def test_an_idea_added_now_is_read_at_once_later_waits_for_the_batch(host, model):
    later = host.command("ideas.add", {"text": "wait for the batch", "now": False})["slug"]
    now = host.command("ideas.add", {"text": "dark mode please", "now": True})["slug"]
    _wait(host, now)
    assert [c["kind"] for c in model.seen] == ["idea"] and "dark mode please" in model.seen[0]["prompt"]
    assert ideas.state(host.ideas.state_dir, later)["state"] == "raw"
    assert ideas.state(host.ideas.state_dir, now)["state"] == "ready"
    assert [e["now"] for e in _events(host, "idea_added")] == [False, True]
    host.command("ideas.read_now", {"slug": later})                      # the card's Process now
    _wait(host, later)
    assert len(model.seen) == 2 and ideas.state(host.ideas.state_dir, later)["state"] == "ready"
    with pytest.raises(CommandError, match="read this idea already"):
        host.command("ideas.read_now", {"slug": later})


def test_the_keeper_fills_an_ideas_priority_with_one_line_why_and_proposes_its_place(host, model):
    first = host.command("ideas.add", {"text": "first idea"})["slug"]
    second = host.command("ideas.add", {"text": "second idea"})["slug"]
    model.answers["idea"]["before"] = first
    host.command("ideas.read_now", {"slug": second})
    _wait(host, second)
    page = host.command("ideas.page", {"slug": second})
    why = next(s["text"] for s in page["sections"] if s["name"] == "Why")
    assert "Priority: High — Helps night users stay." in why
    board = host.command("ideas.board")
    assert [(i["slug"], i["priority"]) for i in board["ideas"]] == [(second, "high"), (first, "normal")]


def test_the_persons_drag_wins_over_the_keepers_place(host, model):
    a = host.command("ideas.add", {"text": "alpha idea"})["slug"]
    b = host.command("ideas.add", {"text": "beta idea"})["slug"]
    host.command("ideas.move", {"slug": b})                              # the person drags b to the end: theirs now
    model.answers["idea"]["before"] = a
    host.command("ideas.read_now", {"slug": b})
    _wait(host, b)
    assert [i["slug"] for i in host.command("ideas.board")["ideas"]] == [a, b]


def test_roles_are_made_edited_dropped_and_the_built_ins_refused(host):
    got = host.command("ideas.roles")
    assert [r["slug"] for r in got["roles"]] == ["taskmaster", "grunt"] and all(r["spend_today"] == 0 for r in got["roles"])
    assert [(k["kind"], k["label"], k["role"]) for k in got["kinds"]] == [
        ("code", "Code", "grunt"), ("tests", "Tests", "grunt"), ("docs", "Docs", "grunt"),
        ("text", "Text for people", "grunt"), ("research", "Research", "grunt")]
    assert {"opus", "sonnet", "haiku"} <= {m["id"] for m in got["models"]}
    slug = host.command("ideas.role_save", {"name": "Docs scribe", "model": "laborer", "max_parallel": 2,
                                            "instruction": "Write plainly."})["slug"]
    assert host.command("ideas.kind_set", {"kind": "docs", "role": slug}) == {"ok": True}
    got = host.command("ideas.roles")
    assert next(r for r in got["roles"] if r["slug"] == slug)["instruction"] == "Write plainly."
    assert next(k for k in got["kinds"] if k["kind"] == "docs")["role"] == slug
    host.command("ideas.role_save", {"slug": slug, "name": "Scribe", "model": "warrior", "max_parallel": 3, "instruction": ""})
    assert next(r for r in host.command("ideas.roles")["roles"] if r["slug"] == slug)["name"] == "Scribe"
    for slug_ in ("taskmaster", "grunt"):
        with pytest.raises(CommandError, match="edited, not deleted"):
            host.command("ideas.role_drop", {"slug": slug_})
    with pytest.raises(CommandError, match="at once"):
        host.command("ideas.role_save", {"name": "Bad", "model": "warrior", "max_parallel": 99})
    assert host.command("ideas.role_drop", {"slug": slug}) == {"ok": True}
    assert next(k for k in host.command("ideas.roles")["kinds"] if k["kind"] == "docs")["role"] == "grunt"
    saved, dropped, kind = (_events(host, n) for n in ("role_saved", "role_dropped", "kind_set"))
    assert [(e["role"], e["model"], e["max_parallel"], e["new"]) for e in saved] == [
        (slug, "laborer", 2, True), (slug, "warrior", 3, False)]
    assert dropped[0]["role"] == slug and dropped[0]["kinds"] == ["docs"] and kind[0]["kind"] == "docs"


def test_agents_is_a_block_per_role_and_spend_is_summed_by_role(host):
    slug = host.command("ideas.role_save", {"name": "Scribe", "model": "laborer", "max_parallel": 1})["slug"]
    idea = host.command("ideas.add", {"text": "an idea with work"})["slug"]
    state = host.ideas.state_dir
    task = lambda tid, role, cost: {"id": tid, "title": tid, "brief": "b", "tier": "laborer", "kind": "docs", "role": role,  # noqa: E731
                                    "after": [], "state": "running", "started": time.strftime("%Y-%m-%dT%H:%M:%S"), "cost": cost}
    ideas.save_plan(state, idea, {"idea": idea, "made_at": "x", "passed_at": None, "todos": [],
                                  "tasks": [task("k1", slug, 0.25), task("k2", slug, 0.5), task("k3", "grunt", 1.0)]})
    ideas.save_state(state, idea, state="working")
    blocks = {b["role"]: b for b in host.command("ideas.agents")["roles"]}
    assert list(blocks) == ["taskmaster", "grunt", slug]
    assert [c["task"] for c in blocks[slug]["chips"]] == ["k1", "k2"] and blocks[slug]["chips"][0]["role"] == slug
    assert [c["task"] for c in blocks["grunt"]["chips"]] == ["k3"]
    assert blocks[slug]["spend_today"] == 0.75 and blocks["grunt"]["spend_today"] == 1.0
    spent = {r["slug"]: r["spend_today"] for r in host.command("ideas.roles")["roles"]}
    assert spent[slug] == 0.75


def test_the_plan_marks_each_task_with_its_type():
    from orkcraft.core import idea_keeper
    plan = idea_keeper.make_plan("x", {"tasks": [
        {"title": "a", "brief": "b", "kind": "docs"}, {"title": "c", "brief": "d"}, {"title": "e", "brief": "f", "kind": "poetry"}]})
    assert [t["kind"] for t in plan["tasks"]] == ["docs", "code", "code"]


def test_the_keepers_talk_and_plans_run_on_the_taskmasters_model(host, model):
    slug = host.command("ideas.add", {"text": "talk to me"})["slug"]
    model.answers["idea"] = {"reply": "ok", "sections": {}, "questions": []}
    host.command("ideas.say", {"slug": slug, "text": "hello"})
    _wait(host, slug)
    assert "opus" in model.seen[-1]["model"]                                         # the Taskmaster's default: the elder tier
    host.command("ideas.role_save", {"slug": "taskmaster", "name": "Taskmaster", "model": "haiku", "max_parallel": 1})
    host.command("ideas.say", {"slug": slug, "text": "again"})
    _wait(host, slug)
    assert "haiku" in model.seen[-1]["model"]
