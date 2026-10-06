"""🏕 Barracks under load and under failure: several orcs at once, agents that crash or stop,
worktrees that cannot be made, a budget that runs out mid-run."""
from __future__ import annotations

import threading
from pathlib import Path

import pytest

from orkcraft import scroll as ts
from orkcraft.app import OrkcraftApp
from orkcraft.core import bus
from orkcraft.core.workers.barracks import BarracksWorker
from orkcraft.realm import barracks as bk
from orkcraft.realm import masonry, pipes
from orkcraft.screens.typed.pool_view import PoolView
from tests.pool_fakes import FakeGit, Steward

SIZE = (200, 46)


@pytest.fixture(autouse=True)
def fake_git_and_steward(monkeypatch):
    monkeypatch.setattr(BarracksWorker, "git", FakeGit())
    monkeypatch.setattr(BarracksWorker, "steward_runner", Steward())


def spec(**config) -> dict:
    return {"id": "camp", "title": "Camp", "icon": "🏕", "orc": {"name": "Foreman"}, "type": "barracks",
            "config": {"max_orcs": 3, "providers": ["claude"], **config}}


class Crew:
    """A fake harness: each run blocks until the test finishes it — with a result or an error."""

    def __init__(self, cost: float = 0.1):
        self.calls, self.cost = [], cost
        self.lock = threading.Lock()
        self.running = self.peak = 0

    def __call__(self, harness, prompt, workdir, cancel, model, env, resume):
        call = {"prompt": prompt, "workdir": workdir, "resume": resume, "env": env,
                "gate": threading.Event(), "error": None}
        with self.lock:
            self.calls.append(call)
            self.running += 1
            self.peak = max(self.peak, self.running)
        try:
            while not call["gate"].wait(0.02):
                if cancel.is_set():
                    raise InterruptedError("stopped")
            if call["error"] is not None:
                raise call["error"]
            return "ok", self.cost, 100, resume or f"s{len(self.calls)}"   # a resumed session keeps its id
        finally:
            with self.lock:
                self.running -= 1

    def finish(self, i: int, error: Exception | None = None) -> None:
        self.calls[i]["error"] = error
        self.calls[i]["gate"].set()


async def _until(pilot, cond, n=150):
    for _ in range(n):
        if cond():
            return True
        await pilot.pause(0.02)
    return cond()


async def _open(pilot, app):
    await pilot.pause()
    view = app.desktop.get_window("camp").query_one(PoolView)
    sent = []
    app.roads.emit = lambda payload, meta=None: sent.append(payload) or []
    return view, sent


def _arrive(app, value):
    app.deliver_payload("camp", pipes.Payload(pipes.NODE, value, "loot", "on_selection_change", value), value, value)


def _app(repo: Path, monkeypatch, crew, maker=None, **config) -> OrkcraftApp:
    monkeypatch.setattr(BarracksWorker, "work_runner", staticmethod(crew))
    monkeypatch.setattr(BarracksWorker, "worktree_maker",
                        staticmethod(maker or (lambda r, bid, orc: (r, f"pool/{bid}/{orc.lower()}"))))
    assert masonry.save_spec(repo, spec(**config)) == []
    app = OrkcraftApp(repo_root=repo, auto_commit=False)
    for event in ("pool.assigned", "pool.done", "pool.failed", "pool.question", "pool.idle"):     # emit() sends only what is heard
        ts.subscribe(app.scroll, "town_hall", "camp", event)
    return app


@pytest.mark.asyncio
async def test_three_orcs_work_at_once_and_the_rest_queue(fake_repo: Path, monkeypatch):
    crew = Crew()
    app = _app(fake_repo, monkeypatch, crew)
    async with app.run_test(size=SIZE) as pilot:
        view, sent = await _open(pilot, app)
        for i in range(1, 7):
            _arrive(app, f"T10{i:02d}")
        assert await _until(pilot, lambda: crew.running == 3)
        st = view.state
        assert [o.name for o in st.orcs] == ["Grub", "Mogka", "Thrak"]                 # never a 4th
        assert all(o.status == "working" for o in st.orcs) and len(st.queue) == 3
        assert view.hut_lines([16] * 6)[0] == "active: 3/3"
        assert {c["env"]["ORKCRAFT_ORC"] for c in crew.calls} == {"camp/grub", "camp/mogka", "camp/thrak"}

        for i in range(6):                                                             # finish them as they come
            assert await _until(pilot, lambda: len(crew.calls) > i)
            crew.finish(i)
        assert await _until(pilot, lambda: not st.queue and all(o.status == "idle" for o in st.orcs))
        assert crew.peak == 3 and len(crew.calls) == 6
        assert sum(o.done for o in st.orcs) == 6 and st.stats["claude:haiku"] == {"runs": 6, "ok": 6, "cost": 0.6, "tokens": 600}
        modes = [p.mode for p in sent]
        assert modes.count("pool.assigned") == 6 and modes.count("pool.done") == 6 and modes.count("pool.idle") == 1


@pytest.mark.asyncio
async def test_a_crashing_agent_fails_its_task_only(fake_repo: Path, monkeypatch):
    crew = Crew()
    app = _app(fake_repo, monkeypatch, crew, max_orcs=2)
    async with app.run_test(size=SIZE) as pilot:
        view, sent = await _open(pilot, app)
        runs = []
        app.core.bus.subscribe(bus.RUN, lambda e: runs.append(e.data["run"]))
        for t in ("T2001", "T2002", "T2003"):
            _arrive(app, t)
        assert await _until(pilot, lambda: len(crew.calls) == 2)
        st = view.state

        crash = RuntimeError("claude exited with 1: rate limited " + "x" * 500)
        crew.finish(0, crash)
        assert await _until(pilot, lambda: len(crew.calls) == 3)                      # a crash is tried once more
        assert "T2001" in crew.calls[2]["prompt"] and any(d.action == "retry" for d in st.decisions())
        assert not any(p.mode == "pool.failed" for p in sent)
        crew.finish(2, crash)
        assert await _until(pilot, lambda: len(crew.calls) == 4)                      # Grub takes T2003 anyway
        failed = next(t for t in st.tasks if t.key == "T2001")
        assert failed.status == "failed" and failed.error.startswith("claude exited with 1")
        assert len(failed.error) == 300                                               # cut, not the whole log
        grub = st.orc("Grub")
        assert grub.failed == 2 and grub.done == 0 and st.task(grub.task).key == "T2003"
        assert st.orc("Mogka").status == "working"                                    # the other orc never noticed
        fail = next(p for p in sent if p.mode == "pool.failed")
        assert "rate limited" in fail.value and "Grub" in fail.value
        assert runs[-1].outcome == "error" and "rate limited" in runs[-1].error

        crew.finish(1)
        crew.finish(3)
        assert await _until(pilot, lambda: all(o.status == "idle" for o in st.orcs))
        assert st.stats["claude:haiku"]["runs"] == 4 and st.stats["claude:haiku"]["ok"] == 2
        assert "✗ T2001 — Grub" in str(view.query_one("#pool-detail").render())

        _arrive(app, "T2001")                                                          # a retry goes back to Grub
        assert await _until(pilot, lambda: len(crew.calls) == 5)
        assert st.orc("Grub").status == "working" and crew.calls[4]["resume"] == "s4"
        crew.finish(4)
        assert await _until(pilot, lambda: st.orc("Grub").status == "idle")


@pytest.mark.asyncio
async def test_closing_the_building_stops_its_orcs(fake_repo: Path, monkeypatch):
    crew = Crew()
    app = _app(fake_repo, monkeypatch, crew, max_orcs=2)
    async with app.run_test(size=SIZE) as pilot:
        view, sent = await _open(pilot, app)
        runs = []
        app.core.bus.subscribe(bus.RUN, lambda e: runs.append(e.data["run"]))
        _arrive(app, "T3001")
        _arrive(app, "T3002")
        assert await _until(pilot, lambda: crew.running == 2)
        st = view.state
        view.on_unmount()                                                              # cancels every running job
        assert await _until(pilot, lambda: crew.running == 0 and all(o.status == "idle" for o in st.orcs))
        assert {t.error for t in st.tasks} == {"stopped"}
        assert runs == []                                                              # a stop is not a failed run
    again = bk.Barracks(fake_repo / ".orkcraft" / "pool" / "camp")
    assert all(o.status == "idle" for o in again.orcs)


@pytest.mark.asyncio
async def test_no_worktree_no_orc_and_the_task_is_not_lost(fake_repo: Path, monkeypatch):
    crew = Crew()
    tries = []

    def maker(repo, bid, orc):
        tries.append(orc)
        if len(tries) == 1:
            raise RuntimeError("fatal: 'pool/camp/grub' is already checked out")
        return repo, f"pool/{bid}/{orc.lower()}"

    app = _app(fake_repo, monkeypatch, crew, maker=maker)
    async with app.run_test(size=SIZE) as pilot:
        view, sent = await _open(pilot, app)
        _arrive(app, "T4001")
        await pilot.pause(0.1)
        st = view.state
        assert st.orcs == [] and crew.calls == []
        assert [t.key for t in st.queue] == ["T4001"]                                  # still waiting, not dropped

        view.worker.tick()                                                             # the next tick tries again
        assert await _until(pilot, lambda: len(crew.calls) == 1)
        assert st.orcs[0].branch and st.task(st.orcs[0].task).key == "T4001"
        crew.finish(0)
        assert await _until(pilot, lambda: st.orcs[0].status == "idle")


@pytest.mark.asyncio
async def test_the_budget_stops_hiring_mid_run(fake_repo: Path, monkeypatch):
    crew = Crew(cost=0.6)
    app = _app(fake_repo, monkeypatch, crew, budget_usd=1.0)
    async with app.run_test(size=SIZE) as pilot:
        view, sent = await _open(pilot, app)
        _arrive(app, "T5001")
        _arrive(app, "T5002")
        assert await _until(pilot, lambda: len(crew.calls) == 2)
        crew.finish(0)
        crew.finish(1)
        st = view.state
        assert await _until(pilot, lambda: st.spent >= 1.2)                          # the steward costs too
        _arrive(app, "T5003")
        await pilot.pause(0.1)
        assert len(crew.calls) == 2 and st.queue[-1].decided.startswith("budget:")
        assert st.decisions(1)[0].action == "budget"


# -- context reuse -----------------------------------------------------------------------------------


def test_the_foreman_prefers_the_orc_that_knows_the_work():
    f = bk.Foreman({"max_orcs": 3})
    grub = bk.PoolOrc("Grub", "claude", recent=["Add the login page — form and validation"])
    mogka = bk.PoolOrc("Mogka", "claude", recent=["Parser: tokenizer for quoted strings — done"])
    t = bk.PoolTask("t", "Parser: handle escapes in quoted strings", "the tokenizer drops backslashes")
    d = f.decide(t, [grub, mogka], [], 0.0)
    assert (d.action, d.orc) == ("reuse", "Mogka") and "knows this work" in d.why
    assert f.decide(bk.PoolTask("u", "Bump the version", "x"), [grub, mogka], [], 0.0).orc == "Grub"   # no fit → first
    queue = [bk.PoolTask("a", "Bump the version", "x"), t]
    assert f.next_for(mogka, queue).id == t.id and f.next_for(grub, queue).id == "a"
    far = [bk.PoolTask(str(i), f"chore {i}", "x") for i in range(bk.LOOKAHEAD)] + [t]
    assert f.next_for(mogka, far).id == "0"                                    # no jumping the whole queue
    mogka.session, mogka.session_tasks = "s1", 4
    assert f.can_resume(mogka)
    mogka.session_tasks = f.session_tasks
    assert not f.can_resume(mogka)                                             # rolled over
    assert not f.can_resume(bk.PoolOrc("Snaga", "agy", session="x"))          # agy cannot resume


@pytest.mark.asyncio
async def test_related_work_resumes_the_session_and_sends_only_the_task(fake_repo: Path, monkeypatch):
    crew = Crew()
    app = _app(fake_repo, monkeypatch, crew, max_orcs=1, session_tasks=2, orders="Use type hints everywhere.")
    async with app.run_test(size=SIZE) as pilot:
        view, sent = await _open(pilot, app)
        st = view.state
        say = lambda title, body: view.add_task(title, body)                               # noqa: E731

        say("Parser: tokenizer for quoted strings", "split the input into tokens")
        assert await _until(pilot, lambda: len(crew.calls) == 1)
        first = crew.calls[0]["prompt"]
        assert "Use type hints" in first and crew.calls[0]["resume"] == "" and "recent work" not in first
        crew.finish(0)
        assert await _until(pilot, lambda: st.orcs[0].status == "idle")
        assert st.orcs[0].recent and st.orcs[0].session_tasks == 1

        say("Parser: escapes in quoted strings", "the tokenizer drops backslashes")       # related → warm
        assert await _until(pilot, lambda: len(crew.calls) == 2)
        warm = crew.calls[1]
        assert warm["resume"] == "s1" and warm["prompt"].startswith("## Task")
        assert "Use type hints" not in warm["prompt"] and len(warm["prompt"]) < len(first) / 2
        crew.finish(1)
        assert await _until(pilot, lambda: st.orcs[0].status == "idle")
        assert st.orcs[0].session_tasks == 2 and st.tasks[-1].warm

        say("Parser: tokenizer errors for quoted strings", "report the column")           # related, but rolled over
        assert await _until(pilot, lambda: len(crew.calls) == 3)
        cold = crew.calls[2]
        assert cold["resume"] == "" and "Use type hints" in cold["prompt"]
        assert "## Your recent work" in cold["prompt"] and "escapes in quoted strings" in cold["prompt"]
        crew.finish(2)
        assert await _until(pilot, lambda: st.orcs[0].status == "idle")
        assert st.orcs[0].session_tasks == 1                                               # a fresh session

        say("Bump the version", "0.2.0")                                                   # unrelated → no history
        assert await _until(pilot, lambda: len(crew.calls) == 4)
        assert crew.calls[3]["resume"] == "" and "recent work" not in crew.calls[3]["prompt"]
        crew.finish(3)
        assert await _until(pilot, lambda: st.orcs[0].status == "idle")
        assert st.orcs[0].tokens == 400 and st.stats["claude:haiku"]["tokens"] == 400
        assert "♻" in str(view.query_one("#pool-detail").render())


# -- the steward: questions, reviews, reworks, the PR -------------------------------------------------


class Asker(Crew):
    """A crew whose run ends with the text the test gives (a QUESTION, a report)."""

    def finish_with(self, i: int, text: str) -> None:
        self.calls[i]["text"] = text
        self.calls[i]["gate"].set()

    def __call__(self, harness, prompt, workdir, cancel, model, env, resume):
        text, cost, tokens, session = super().__call__(harness, prompt, workdir, cancel, model, env, resume)
        return self.calls[-1].get("text", text), cost, tokens, session


def _calls_done(crew, n):
    return lambda: len(crew.calls) >= n


@pytest.mark.asyncio
async def test_each_task_has_its_branch_and_an_accepted_one_gets_a_pr(fake_repo: Path, monkeypatch):
    crew, git = Crew(), FakeGit(pr="https://github.com/o/r/pull/7")
    monkeypatch.setattr(BarracksWorker, "git", git)
    app = _app(fake_repo, monkeypatch, crew, max_orcs=1)
    async with app.run_test(size=SIZE) as pilot:
        view, sent = await _open(pilot, app)
        st = view.state
        _arrive(app, "T6001")
        _arrive(app, "T6002")
        assert await _until(pilot, lambda: len(crew.calls) == 1)
        crew.finish(0)
        assert await _until(pilot, lambda: len(crew.calls) == 2)                       # the same orc, a new branch
        crew.finish(1)
        assert await _until(pilot, lambda: all(t.status == "done" for t in st.tasks) and len(st.tasks) == 2)
        assert [b for b, _ in git.prepared] == ["pool/camp/t6001", "pool/camp/t6002"]
        assert [b for b, *_ in git.published] == ["pool/camp/t6001", "pool/camp/t6002"]
        assert all(t.pr == "https://github.com/o/r/pull/7" for t in st.tasks)
        done = [p.value for p in sent if p.mode == "pool.done"]
        assert len(done) == 2 and "pull/7" in done[0]
        assert "Work on the branch `pool/camp/t6001`" in crew.calls[0]["prompt"]


@pytest.mark.asyncio
async def test_the_barracks_decides_who_needs_a_pull_request(fake_repo: Path, monkeypatch):
    """Code always goes out reviewed as a PR; a meeting's document never; other documents as the steward says."""
    crew, git = Crew(), FakeGit(pr="https://github.com/o/r/pull/9", files=("docs/notes.md",))
    steward = Steward(verdicts=["ACCEPT\nSCOPE: local", "ACCEPT", "ACCEPT"])
    monkeypatch.setattr(BarracksWorker, "git", git)
    monkeypatch.setattr(BarracksWorker, "steward_runner", steward)
    app = _app(fake_repo, monkeypatch, crew, max_orcs=1)
    async with app.run_test(size=SIZE) as pilot:
        view, sent = await _open(pilot, app)
        st = view.state
        _arrive(app, "T7001")                                    # docs only, the steward: local → no PR
        assert await _until(pilot, lambda: len(crew.calls) == 1)
        crew.finish(0)
        assert await _until(pilot, lambda: st.tasks and st.tasks[0].status == "done")
        assert "Only documents changed" in steward.prompts[-1]                # the steward decides
        assert git.published == [] and st.tasks[0].scope == bk.LOCAL
        assert "a local document: no pull request" in next(p.value for p in sent if p.mode == "pool.done")

        _arrive(app, "T7002")                                    # docs only, the steward says nothing: PR
        assert await _until(pilot, lambda: len(crew.calls) == 2)
        crew.finish(1)
        assert await _until(pilot, lambda: len(st.tasks) == 2 and st.tasks[1].status == "done")
        assert [b for b, *_ in git.published] == ["pool/camp/t7002"] and st.tasks[1].scope == bk.EXTERNAL

        git.commits = 0                                          # a meeting's prep: no commit needed, no PR
        view.add_task("Prep the sync [meet:abc123]", "the agenda and open items [meet:abc123]")
        assert await _until(pilot, lambda: len(crew.calls) == 3)
        assert "local document for a meeting" in crew.calls[2]["prompt"]
        crew.finish(2)
        assert await _until(pilot, lambda: len(st.tasks) == 3 and st.tasks[2].status == "done")
        assert len(git.published) == 1 and st.tasks[2].scope == bk.LOCAL
        assert "Only documents changed" not in steward.prompts[-1]          # the rule decided, not the steward


def test_code_is_always_external():
    assert bk.scope_rule(["src/app.py", "README.md"], meeting=True) == bk.EXTERNAL
    assert bk.scope_rule(["docs/a.md"], meeting=True) == bk.LOCAL
    assert bk.scope_rule(["docs/a.md"], meeting=False) == ""
    assert bk.scope_of("ACCEPT\nscope: Local") == bk.LOCAL and bk.scope_of("ACCEPT") == bk.EXTERNAL
    assert bk.changed_files("diff --git a/x.md b/y.md\n+1\ndiff --git a/z.py b/z.py\n") == ["x.md", "y.md", "z.py"]


@pytest.mark.asyncio
async def test_rework_goes_back_to_the_same_orc_at_most_three_times(fake_repo: Path, monkeypatch):
    crew = Crew()
    steward = Steward(verdicts=["REWORK: add a test"] * 4)
    monkeypatch.setattr(BarracksWorker, "steward_runner", steward)
    app = _app(fake_repo, monkeypatch, crew, max_orcs=2)
    async with app.run_test(size=SIZE) as pilot:
        view, sent = await _open(pilot, app)
        st = view.state
        _arrive(app, "T7001")
        for i in range(4):                                                             # 1 run + 3 reworks
            assert await _until(pilot, _calls_done(crew, i + 1))
            if i:
                assert "sent it back\n\nadd a test" in crew.calls[i]["prompt"]
                assert crew.calls[i]["resume"]                                         # in the orc's session
            crew.finish(i)
        task = st.tasks[0]
        assert await _until(pilot, lambda: task.status == "asked")
        assert len(crew.calls) == 4 and {o.name for o in st.orcs} == {"Grub"}        # never another orc
        assert "Rejected after 3 reworks" in task.question and "add a test" in task.question
        assert "pool.failed" in [p.mode for p in sent] and "pool.question" in [p.mode for p in sent]
        assert view.hut_lines([16] * 6)[0] == "🔥 Foreman asks"
        assert "🔥 1 asks" in str(view.query_one("#pool-orcs").get_option_at_index(0).prompt)

        steward.verdicts = ["ACCEPT"]
        view.answer(task.id, "skip the test, document it instead", propose=False)      # a new round
        assert await _until(pilot, _calls_done(crew, 5))
        assert "skip the test" in crew.calls[4]["prompt"]
        crew.finish(4)
        assert await _until(pilot, lambda: task.status == "done")


@pytest.mark.asyncio
async def test_failing_tests_send_it_back_without_asking_the_model(fake_repo: Path, monkeypatch):
    crew, steward = Crew(), Steward()
    monkeypatch.setattr(BarracksWorker, "git", FakeGit(tests=(False, "FAILED test_login - assert 1 == 2")))
    monkeypatch.setattr(BarracksWorker, "steward_runner", steward)
    app = _app(fake_repo, monkeypatch, crew, max_orcs=1, test_cmd="pytest -q", max_reworks=1)
    async with app.run_test(size=SIZE) as pilot:
        view, sent = await _open(pilot, app)
        _arrive(app, "T8001")
        assert await _until(pilot, _calls_done(crew, 1))
        crew.finish(0)
        assert await _until(pilot, _calls_done(crew, 2))
        assert "FAILED test_login" in crew.calls[1]["prompt"] and steward.prompts == []
        crew.finish(1)
        assert await _until(pilot, lambda: view.state.tasks[0].status == "asked")


@pytest.mark.asyncio
async def test_nothing_committed_goes_to_the_steward_who_sends_a_change_back(fake_repo: Path, monkeypatch):
    crew, steward = Crew(), Steward(verdicts=["REWORK: commit the change"])
    git = FakeGit(commits=0)
    monkeypatch.setattr(BarracksWorker, "git", git)
    monkeypatch.setattr(BarracksWorker, "steward_runner", steward)
    app = _app(fake_repo, monkeypatch, crew, max_orcs=1, max_reworks=0)
    async with app.run_test(size=SIZE) as pilot:
        view, sent = await _open(pilot, app)
        _arrive(app, "T8101")
        assert await _until(pilot, _calls_done(crew, 1))
        crew.finish(0)
        assert await _until(pilot, lambda: view.state.tasks[0].status == "asked")
        assert "commit the change" in view.state.tasks[0].question
        assert "nothing committed" in steward.prompts[-1] and git.published == []


@pytest.mark.asyncio
async def test_a_question_answered_in_the_report_is_done_without_a_commit(fake_repo: Path, monkeypatch):
    """"Find me what is known about Shakira": the report is the answer — accepted, no pull request, no rework."""
    crew = Crew()
    git = FakeGit(commits=0)
    monkeypatch.setattr(BarracksWorker, "git", git)
    app = _app(fake_repo, monkeypatch, crew, max_orcs=1)
    async with app.run_test(size=SIZE) as pilot:
        view, sent = await _open(pilot, app)
        _arrive(app, "T8102")
        assert await _until(pilot, _calls_done(crew, 1))
        assert "needs no commit" in crew.calls[0]["prompt"]
        crew.finish(0)
        assert await _until(pilot, lambda: view.state.tasks[0].status == "done")
        task = view.state.tasks[0]
        assert task.attempts == 1 and task.scope == "local" and task.pr == "" and git.published == []


@pytest.mark.asyncio
async def test_the_steward_answers_from_its_rules_or_asks_the_operator(fake_repo: Path, monkeypatch):
    crew = Asker()
    steward = Steward(answers=["PostgreSQL — rule 2"])
    monkeypatch.setattr(BarracksWorker, "steward_runner", steward)
    app = _app(fake_repo, monkeypatch, crew, max_orcs=1, orders="1. Type hints.\n2. The database is PostgreSQL.")
    async with app.run_test(size=SIZE) as pilot:
        view, sent = await _open(pilot, app)
        st = view.state
        view.add_task("Add the users table", "a migration")
        assert await _until(pilot, _calls_done(crew, 1))
        crew.finish_with(0, "Looked around.\nQUESTION: which database?")
        assert await _until(pilot, _calls_done(crew, 2))                               # answered by the steward
        assert "The database is PostgreSQL" in steward.prompts[0] and "which database?" in steward.prompts[0]
        assert "answers your question: PostgreSQL" in crew.calls[1]["prompt"] and crew.calls[1]["resume"] == "s1"
        crew.finish_with(1, "QUESTION: which colour for the admin badge?")              # not in the rules
        task = st.tasks[0]
        assert await _until(pilot, lambda: task.status == "asked")
        assert task.question == "which colour for the admin badge?"
        assert st.orcs[0].status == "idle"                                             # the orc is free meanwhile
        orc_row = str(view.query_one("#pool-orcs").get_option_at_index(1).prompt)
        assert orc_row.endswith(" ?") or " ? " in orc_row                              # a quiet mark on the orc
        assert [q for q, *_ in task.qa] == ["which database?"]

        view.answer(task.id, "green", propose=False)
        assert await _until(pilot, _calls_done(crew, 3))
        assert crew.calls[2]["resume"] == "s1" and "admin badge? → green" in crew.calls[2]["prompt"]
        crew.finish(2)
        assert await _until(pilot, lambda: task.status == "done")
        assert [a for _, a, who in task.qa] == ["PostgreSQL — rule 2", "green"]
        review = steward.prompts[-1]
        assert "which colour for the admin badge? → green" in review

        assert view.add_rule("- admin badge → green")                                   # the proposal, kept
        assert "admin badge → green" in view.orders and "PostgreSQL" in view.orders


@pytest.mark.asyncio
async def test_a_restart_picks_the_interrupted_work_up_again(fake_repo: Path, monkeypatch):
    st = bk.Barracks(fake_repo / ".orkcraft" / "pool" / "camp")
    st.orcs = [bk.PoolOrc("Grub", "claude", status="working", task="t1", worktree=str(fake_repo))]
    st.tasks = [bk.PoolTask("t1", "Do it", "Do it", status="working", orc="Grub", attempts=1)]
    st.save()
    crew = Crew()
    app = _app(fake_repo, monkeypatch, crew, max_orcs=1)
    async with app.run_test(size=SIZE) as pilot:
        view, sent = await _open(pilot, app)
        assert await _until(pilot, _calls_done(crew, 1))                              # nothing new had to arrive
        crew.finish(0)
        assert await _until(pilot, lambda: view.state.tasks[0].status == "done")


@pytest.mark.asyncio
async def test_a_freed_orc_takes_nothing_over_the_budget(fake_repo: Path, monkeypatch):
    crew = Crew(cost=0.6)
    app = _app(fake_repo, monkeypatch, crew, max_orcs=1, budget_usd=0.5)
    async with app.run_test(size=SIZE) as pilot:
        view, sent = await _open(pilot, app)
        _arrive(app, "T9001")
        _arrive(app, "T9002")                                                          # queued behind the first
        assert await _until(pilot, _calls_done(crew, 1))
        crew.finish(0)
        st = view.state
        assert await _until(pilot, lambda: st.orcs[0].status == "idle")
        await pilot.pause(0.1)
        assert len(crew.calls) == 1 and [t.key for t in st.queue] == ["T9002"]


# -- the real git ------------------------------------------------------------------------------------


def _git(cwd: Path, *args: str) -> str:
    import subprocess
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


def test_task_git_cuts_reuses_and_publishes_branches(fake_repo: Path, tmp_path: Path, monkeypatch):
    from orkcraft.realm import jobs
    import shutil
    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "--bare", str(origin))
    base = _git(fake_repo, "rev-parse", "--abbrev-ref", "HEAD")
    _git(fake_repo, "remote", "add", "origin", str(origin))
    _git(fake_repo, "push", "-u", "origin", base)
    git = jobs.TaskGit()
    assert git.base_of(fake_repo) == base and git.base_of(fake_repo, "develop") == "develop"
    wt, _ = jobs.add_worktree(fake_repo, "camp", "Grub")

    git.prepare(wt, "pool/camp/t1", base)
    assert _git(wt, "branch", "--show-current") == "pool/camp/t1"
    assert git.diff(wt, base, "pool/camp/t1") == (0, "")
    (wt / "feature.py").write_text("x = 1\n")
    _git(wt, "add", ".")
    _git(wt, "commit", "-m", "feature")
    commits, diff = git.diff(wt, base, "pool/camp/t1")
    assert commits == 1 and "+x = 1" in diff
    (wt / "scratch.txt").write_text("left behind")                                    # leftovers get stashed

    git.prepare(wt, "pool/camp/t2", base)                                             # another task, fresh from base
    assert not (wt / "feature.py").exists() and not (wt / "scratch.txt").exists()
    git.prepare(wt, "pool/camp/t1", base)                                             # its follow-up: same branch
    assert (wt / "feature.py").exists()

    monkeypatch.setattr(shutil, "which", lambda name: None)                           # no gh here
    url, note = git.publish(wt, "pool/camp/t1", base, "Feature", "body")
    assert url == "" and note == "pushed; no gh to open the pull request"
    assert "pool/camp/t1" in _git(origin, "branch", "--list", "pool/camp/t1")

    _git(fake_repo, "merge", "--ff-only", "pool/camp/t1")                             # merged upstream …
    _git(fake_repo, "push", "origin", base)
    git.prepare(wt, "pool/camp/t1", base)                                             # … so a new follow-up starts anew
    assert git.diff(wt, base, "pool/camp/t1")[0] == 0

    ok, out = git.test(wt, "python -c \"import sys; print('boom'); sys.exit(1)\"", threading.Event())
    assert not ok and "boom" in out
    assert git.test(wt, "python -c \"print('fine')\"", threading.Event())[0]


@pytest.mark.asyncio
async def test_a_real_orc_commits_on_its_task_branch(fake_repo: Path, monkeypatch):
    """Real worktrees and real git; only the agent and the steward are fakes."""
    monkeypatch.setattr(BarracksWorker, "git", None)

    def coder(harness, prompt, workdir, cancel, model, env, resume):
        name = prompt.split("## Task", 1)[1].splitlines()[0].split(":")[-1].strip()
        (workdir / f"{name}.txt").write_text(name)
        _git(workdir, "add", ".")
        _git(workdir, "commit", "-m", name)
        return f"added {name}.txt", 0.0, 10, ""

    monkeypatch.setattr(BarracksWorker, "work_runner", staticmethod(coder))
    monkeypatch.setattr(BarracksWorker, "worktree_maker", None)
    assert masonry.save_spec(fake_repo, spec(max_orcs=2)) == []
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        view, _ = await _open(pilot, app)
        view.add_task("alpha", "make alpha")
        view.add_task("beta", "make beta")
        st = view.state
        assert await _until(pilot, lambda: len(st.tasks) == 2 and all(t.status == "done" for t in st.tasks), n=300)
        for t in st.tasks:
            assert t.branch == f"pool/camp/{t.id}"
            files = _git(fake_repo, "show", "--name-only", "--format=", t.branch)
            assert files == f"{t.title}.txt"                                           # one task, one branch
