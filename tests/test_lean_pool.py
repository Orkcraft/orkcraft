"""🏕 The lean Agent pool (docs/specs/28-lean-pool.md, decisions-2026-10.md §40): the cold prompt's stable part first,
at most one light steward answer, tests as the review of code, few and short roles, a full context rolls over, and
the waybill says where the tokens went."""
from __future__ import annotations

import threading
from pathlib import Path

import pytest

from orkcraft.core.workers.barracks import BarracksWorker, RunOutcome
from orkcraft.gui import waybill
from orkcraft.realm import barracks as bk
from orkcraft.realm import personas, pipes, plans, pool_spend
from tests.pool_fakes import FakeGit, Steward
from tests.test_gui_pool_clan import _host, _raised, _until

REVIEW = "Judge whether the task is done"          # the steward's review prompt (realm/barracks.py review_prompt)


@pytest.fixture
def steward(monkeypatch):
    s = Steward()
    monkeypatch.setattr(BarracksWorker, "steward_runner", s)
    return s


def _pool(fake_repo, monkeypatch, runner, **config):
    monkeypatch.setattr(BarracksWorker, "work_runner", staticmethod(runner))
    host = _host(fake_repo)
    bid = _raised(host, "barracks", worktrees=False, providers=["claude"], max_orcs=1, plan=False, **config)
    return host, bid, host.town.worker(bid)


def _reviews(s: Steward) -> int:
    return sum(REVIEW in p for p in s.prompts)


# -- 1. the stable part first -------------------------------------------------------------------------------------

def test_the_cold_prompt_s_stable_part_is_the_same_for_every_ork_and_task_and_comes_first(fake_repo, monkeypatch,
                                                                                          steward):
    host, bid, w = _pool(fake_repo, monkeypatch, lambda *a: ("ok", 0.0, 0, ""), orders="- Write tests first.")
    personas.save(w.state_dir, personas.Persona("backend", "You build APIs.", "warrior", True))
    grub = bk.PoolOrc("Grub", "claude", persona="backend")
    mogka = bk.PoolOrc("Mogka", "claude")
    one = bk.PoolTask("t1", "Fix the login", "the form hangs", branch="pool/camp/t1")
    two = bk.PoolTask("t2", "Write the changelog", "for v0.2", qa=[["which version?", "0.2", "operator"]])
    a, b = w._prompt(one, grub, False, False), w._prompt(two, mogka, True, False)
    stable_a, _, own_a = a.partition("You are Grub.")
    stable_b, _, own_b = b.partition("You are Mogka.")
    assert own_a and own_b and stable_a == stable_b                                 # byte for byte
    assert stable_a.startswith("You are one of several agents working in parallel, each in its own git worktree.")
    assert "Write tests first." in stable_a and bk.OUTSIDE_RULE in stable_a and bk.ANSWER_RULE in stable_a
    assert stable_a.index("Write tests first.") < stable_a.index(bk.OUTSIDE_RULE) < stable_a.index(bk.ANSWER_RULE)
    for own in ("Grub", "Mogka", "backend", "Fix the login", "pool/camp/t1", "which version?"):
        assert own not in stable_a                                                  # nothing of one task or ork
    assert own_a.index("You build APIs.") < own_a.index("pool/camp/t1") < own_a.index("## Task: Fix the login")


# -- 2. one light answer -------------------------------------------------------------------------------------------

def test_a_second_question_in_one_run_goes_to_the_person_not_to_the_steward(fake_repo, monkeypatch):
    s = Steward(answers=["Postgres", "port 5432"])
    monkeypatch.setattr(BarracksWorker, "steward_runner", s)
    runs = []

    def work(harness, prompt, workdir, cancel, model, env, resume):
        runs.append(prompt)
        return ("QUESTION: which database?" if len(runs) == 1 else "QUESTION: which port?"), 0.1, 10, "s1"

    host, bid, w = _pool(fake_repo, monkeypatch, work)
    w.new_task("Set up the database", "")
    assert _until(lambda: w.state.asked)
    asked = w.state.asked[0]
    assert asked.question.startswith("which port?") and asked.qa == [["which database?", "Postgres", w.keeper]]
    assert sum("asks\n\n" in p for p in s.prompts) == 1 and len(runs) == 2


def test_the_steward_s_answer_is_light_and_holds_the_card_the_decisions_and_the_question_only(fake_repo,
                                                                                             monkeypatch, steward):
    calls = []
    real = BarracksWorker._steward

    def spy(self, prompt, workdir, cancel, out, use="review", light=False):
        calls.append((use, light, prompt))
        return real(self, prompt, workdir, cancel, out, use, light)

    monkeypatch.setattr(BarracksWorker, "_steward", spy)
    host, bid, w = _pool(fake_repo, monkeypatch, lambda *a: ("ok", 0.0, 0, ""))
    task = bk.PoolTask("t1", "Fix the login", "the form hangs", qa=[["which page?", "/login", "operator"]])
    out = RunOutcome(text="diff --git a/x b/x")
    w._steward_answer(task, "which test runner?", fake_repo, threading.Event(), out)
    (use, light, prompt), = calls
    assert use == "answer" and light is True
    assert "## The task: Fix the login" in prompt and "which page? → /login" in prompt and "which test runner?" in prompt
    assert "diff" not in prompt.lower() and "do not run commands" in prompt


# -- 3. the tests are the review of code ---------------------------------------------------------------------------

def _review(w, git: FakeGit) -> RunOutcome:
    task = bk.PoolTask("t1", "Fix the login", "the form hangs", branch="pool/camp/t1", base="main")
    out = RunOutcome(text="Fixed the form.")
    w._review(task, w.code_root, git, threading.Event(), out)
    return out


def test_green_tests_are_the_review_and_no_steward_reads_the_diff(fake_repo, monkeypatch, steward):
    host, bid, w = _pool(fake_repo, monkeypatch, lambda *a: ("ok", 0.0, 0, ""), test_cmd="pytest -q")
    git = FakeGit(tests=(True, "1 passed"))
    out = _review(w, git)
    assert out.accepted is True and _reviews(steward) == 0 and "passes" in out.notes
    assert out.scope == bk.EXTERNAL and git.published == [("pool/camp/t1", "main", "Fix the login")]   # to the gate


def test_failing_tests_no_tests_or_review_by_the_steward_keep_the_steward_s_review(fake_repo, monkeypatch, steward):
    host, bid, w = _pool(fake_repo, monkeypatch, lambda *a: ("ok", 0.0, 0, ""), test_cmd="pytest -q")
    out = _review(w, FakeGit(tests=(False, "1 failed")))
    assert out.accepted is False and "1 failed" in out.notes and _reviews(steward) == 0   # back to its ork, as today
    w.save_config({"test_cmd": ""})
    _review(w, FakeGit())
    assert _reviews(steward) == 1                                                       # no tests: the steward reads it
    w.save_config({"test_cmd": "pytest -q", "review": "steward"})
    out = _review(w, FakeGit(tests=(True, "1 passed")))
    assert _reviews(steward) == 2 and out.accepted is True and w.review_by == "steward"


# -- 4. few and short roles ----------------------------------------------------------------------------------------

def test_a_persona_is_cut_to_600_characters_at_a_sentence_end(tmp_path: Path):
    long = " ".join(f"Rule {i} keeps the API small." for i in range(60))
    personas.save(tmp_path, personas.Persona("backend", long, "warrior", True))
    p = personas.load(tmp_path, "backend")
    assert len(p.prompt) <= personas.MAX_CHARS and p.prompt.endswith("small.") and long.startswith(p.prompt)
    assert len((tmp_path / "personas" / "backend.md").read_text(encoding="utf-8").split("---\n\n", 1)[1].strip()) <= 600
    (tmp_path / "personas" / "old.md").write_text(f"---\ntier: warrior\napproved: true\n---\n\n{long}\n", encoding="utf-8")
    assert len(personas.load(tmp_path, "old").prompt) <= personas.MAX_CHARS            # an old long one, when read


def test_without_new_roles_the_planner_writes_no_persona(fake_repo, monkeypatch, steward):
    host, bid, w = _pool(fake_repo, monkeypatch, lambda *a: ("ok", 0.0, 0, ""))
    new = plans.Sub("api", "The API", "do it", persona="api-smith", persona_prompt="You forge APIs.")
    assert w.new_roles is False and w._persona_of(new) == "" and personas.load(w.state_dir, "api-smith") is None
    prompt = plans.plan_prompt("Foreman", "", "t", "x", "balance", 3, [], new_roles=False)
    assert "no new ones" in prompt and "a new name with `persona_prompt`" not in prompt
    w.save_config({"new_roles": True})
    assert w._persona_of(new) == "api-smith" and personas.load(w.state_dir, "api-smith") is not None


def test_removing_a_persona_frees_its_ork(fake_repo, monkeypatch, steward):
    host, bid, w = _pool(fake_repo, monkeypatch, lambda *a: ("ok", 0.0, 0, ""))
    personas.save(w.state_dir, personas.Persona("backend", "You build APIs.", "warrior", True))
    w.state.orcs.append(bk.PoolOrc("Grub", "claude", persona="backend", session="s1", session_tasks=2))
    assert [p["name"] for p in host.detail(bid)["data"]["personas"]] == ["backend"]
    assert host.command("act", {"id": bid, "act": "remove_persona", "args": {"name": "backend"}}) is True
    grub = w.state.orc("Grub")
    assert personas.load(w.state_dir, "backend") is None and (grub.persona, grub.session) == ("", "")
    assert personas.remove(w.state_dir, "backend") is False


# -- 5. a full context rolls over ----------------------------------------------------------------------------------

def test_a_run_over_60_percent_of_lumber_makes_the_next_task_cold(fake_repo, monkeypatch, steward):
    resumes, tokens = [], []

    def work(harness, prompt, workdir, cancel, model, env, resume):
        resumes.append(resume)
        return "done", 0.1, tokens.pop(0), resume or f"s{len(resumes)}"

    host, bid, w = _pool(fake_repo, monkeypatch, work)
    limit = host.town.scroll.budget.lumber_context_limit_tokens
    assert w.foreman.context_limit == limit
    tokens[:] = [int(limit * 0.5), int(limit * 0.7), 10]
    for i in range(3):                                   # the same ticket: a follow-up of the same ork each time
        w.new_task(f"ABC-12 part {i}", f"ABC-12: step {i}")
        assert _until(lambda: len(resumes) == i + 1 and all(o.status == "idle" for o in w.state.orcs))
    assert resumes == ["", "s1", ""]                     # under 60 %: resumed; over: a fresh session
    assert any(d.action == "rollover" for d in w.state.decisions(30))
    f = bk.Foreman({}, context_limit=1000)
    assert f.can_resume(bk.PoolOrc("G", "claude", session="s", context=600))
    assert not f.can_resume(bk.PoolOrc("G", "claude", session="s", context=601))


# -- 6. where the tokens went --------------------------------------------------------------------------------------

def test_the_waybill_shows_the_ork_s_and_the_steward_s_spend_split(fake_repo, monkeypatch):
    s = Steward(answers=["Postgres"])
    monkeypatch.setattr(BarracksWorker, "steward_runner",
                        lambda h, p, w, c, m: (*s(h, p, w, c, m), 300 if "asks\n\n" in p else 500))
    runs = []

    def work(harness, prompt, workdir, cancel, model, env, resume):
        runs.append(prompt)
        return ("QUESTION: which database?" if len(runs) == 1 else "done"), 0.25, 1200, "s1"

    host, bid, w = _pool(fake_repo, monkeypatch, work)
    task = w.new_task("Set up the database", "")
    assert _until(lambda: w.state.task(task.id) is not None and w.state.task(task.id).status == "done")
    split = waybill.waybill(host.town, building=bid, task=task.id)["stops"][-1]["split"]
    assert split == [{"part": "ork", "tokens": 2400, "cost": 0.5}, {"part": "answers", "tokens": 300, "cost": 0.01},
                     {"part": "review", "tokens": 500, "cost": 0.01}]
    hop = w._trail(w.state.task(task.id), w.state.orcs[0], "done")[-1]
    assert dict((p, t) for p, t, _ in hop.spend) == {"ork": 2400, "answers": 300, "review": 500}
    again = pipes.trail_of([hop.as_dict()])[0]                            # as it is kept on the cart, and read back
    assert again.spend == hop.spend and waybill._stop(host.town, again)["split"] == split
    assert pool_spend.part_of("triage") == pool_spend.part_of("plan") == "planning"
