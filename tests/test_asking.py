"""❓ The way to ask and to mark (realm/asking.py, core/workers/barracks_asks.py): a run's `asks` block read, its
questions pinned on top of the task with their answers, its assumptions on the result, every one counted locally."""
from __future__ import annotations

from orkcraft.core.workers.barracks import BarracksWorker
from orkcraft.realm import asking, event_log
from tests.pool_fakes import Steward
from tests.test_gui_pool_clan import _host, _raised, _until

BLOCK = """I set up the server.

```asks
QUESTION: Which port should the dev server use?
- 8080
- 3000
ASSUMED: The API keeps its v1 paths.
ASSUMED: Tests run with pytest.
```
"""


def test_the_block_is_read_and_taken_off_the_text():
    found = asking.parse(BLOCK)
    assert found.via == "block" and found.body == "I set up the server."
    assert [q.as_dict() for q in found.questions] == [{"text": "Which port should the dev server use?",
                                                       "options": ["8080", "3000"]}]
    assert found.assumptions == ["The API keeps its v1 paths.", "Tests run with pytest."]


def test_only_assumptions_a_question_on_two_lines_and_the_last_block_counts():
    text = "```asks\nQUESTION: one\n```\nmore\n~~~asks\nQUESTION: Keep the old\nendpoint too?\nASSUMED: x\n~~~"
    found = asking.parse(text)
    assert [q.text for q in found.questions] == ["Keep the old endpoint too?"] and found.assumptions == ["x"]
    assert "QUESTION: one" in found.body
    assert asking.parse("done.\n```asks\nASSUMED: y\n```").questions == []


def test_the_older_line_still_reads_and_plain_text_asks_nothing():
    found = asking.parse("I looked.\nQUESTION: which database?")
    assert found.via == "line" and found.questions[0].text == "which database?" and found.body == "I looked."
    plain = asking.parse("all done")
    assert plain.via == "" and plain.body == "all done" and not plain.questions
    assert asking.question_line(asking.parse(BLOCK)) == "Which port should the dev server use?"


def test_a_claude_ork_is_told_the_block_others_the_line(fake_repo, monkeypatch):
    monkeypatch.setattr(BarracksWorker, "steward_runner", Steward())
    host = _host(fake_repo)
    w = host.town.worker(_raised(host, "barracks", worktrees=False))
    assert "```asks" in w.ask_rule("claude") and "ASSUMED:" in w.ask_rule("claude")
    assert "`QUESTION: …`" in w.ask_rule("codex") and "```asks" not in w.ask_rule("codex")


def test_a_question_is_pinned_with_its_answers_and_everything_is_counted(fake_repo, monkeypatch):
    runs = []

    def work(harness, prompt, workdir, cancel, model, env, resume):
        runs.append((prompt, resume))
        return (BLOCK if len(runs) == 1 else "Done on 3000.\n```asks\nASSUMED: Port 3000 is free.\n```"), 0.1, 10, "s1"

    monkeypatch.setattr(BarracksWorker, "work_runner", staticmethod(work))
    monkeypatch.setattr(BarracksWorker, "steward_runner", Steward())        # the steward cannot answer: the person
    host = _host(fake_repo)
    bid = _raised(host, "barracks", worktrees=False, providers=["claude"])
    w = host.town.worker(bid)
    task = host.command("act", {"id": bid, "act": "task", "args": {"title": "Set up the dev server"}})
    assert _until(lambda: w.state.asked)
    assert "```asks" in runs[0][0]                                           # Claude Code is told the block
    asked = host.detail(bid)["data"]["asked"][0]
    assert asked["questions"] == [{"text": "Which port should the dev server use?", "options": ["8080", "3000"]}]
    assert asked["assumptions"] == ["The API keeps its v1 paths.", "Tests run with pytest."]
    assert asked["question"] == "Which port should the dev server use?" and "```asks" not in asked["report"]

    host.command("act", {"id": bid, "act": "answer", "args": {"task": task, "text": "3000"}})
    assert _until(lambda: any(t.status == "done" for t in w.state.tasks))
    assert runs[1][1] == "s1" or "3000" in runs[1][0]                         # the answer goes back to the ork
    done = next(t for t in host.detail(bid)["data"]["tasks"] if t["id"] == task)
    assert done["questions"] == [] and done["assumptions"][-1] == "Port 3000 is free." and len(done["assumptions"]) == 3

    c = event_log.counts(fake_repo)
    assert (c["question_asked"], c["assumption_marked"], c["run_stopped_on_question"], c["question_answered"]) == (1, 3, 1, 1)
    [answered] = [r for r in event_log.read(fake_repo) if r["event"] == "question_answered"]
    assert answered["who"] == "person" and answered["task"] == task and isinstance(answered["waited_s"], int)


def test_the_steward_answers_what_its_rules_settle_and_that_is_counted(fake_repo, monkeypatch):
    runs = []

    def work(harness, prompt, workdir, cancel, model, env, resume):
        runs.append(prompt)
        return (BLOCK if len(runs) == 1 else "done"), 0.1, 10, "s1"

    monkeypatch.setattr(BarracksWorker, "work_runner", staticmethod(work))
    monkeypatch.setattr(BarracksWorker, "steward_runner", Steward(answers=["8080, the house rule"]))
    host = _host(fake_repo)
    bid = _raised(host, "barracks", worktrees=False, providers=["claude"])
    w = host.town.worker(bid)
    host.command("act", {"id": bid, "act": "task", "args": {"title": "Set up the dev server"}})
    assert _until(lambda: any(t.status == "done" for t in w.state.tasks))
    rows = event_log.read(fake_repo)
    assert [r["who"] for r in rows if r["event"] == "question_answered"] == ["steward"]
    assert not any(r["event"] == "run_stopped_on_question" for r in rows)
