"""🧭 The Barracks' steward plans (docs/design/barracks-planning.md): simple tasks to a light ork, hard
ones into parts — in parallel by the graph, merged into one branch, the whole reviewed; personas by
autonomy; a failed try goes up one tier; a plan that does not fit the budget is trimmed."""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

import pytest

from orkcraft import autonomy, schedule, settings
from orkcraft.core.workers.barracks import BarracksWorker
from orkcraft.realm import barracks as bk
from orkcraft.realm import jobs, personas, plans
from tests.pool_fakes import FakeGit, Steward
from tests.test_pool_failures import Crew, _app, _arrive, _open, _until

SIZE = (200, 46)
HARD = ("Build the export\n\n- an API endpoint that returns CSV\n- a button in the UI\n- docs for both\n\n"
        "The endpoint must stream; the button shows progress.")


def plan(*subs: dict) -> str:
    return json.dumps({"subtasks": list(subs)})


def sub(sid: str, tier: str = "warrior", after=(), touches=(), persona: str = "", prompt: str = "",
        cheaper_ok: bool = False) -> dict:
    return {"id": sid, "title": sid.title(), "brief": f"do {sid}", "tier": tier, "after": list(after),
            "touches": list(touches), "persona": persona, "persona_prompt": prompt, "cheaper_ok": cheaper_ok}


@pytest.fixture
def steward(monkeypatch):
    def use(**kw) -> Steward:
        s = Steward(**kw)
        monkeypatch.setattr(BarracksWorker, "steward_runner", s)
        return s
    return use


@pytest.fixture
def git(monkeypatch) -> FakeGit:
    g = FakeGit()
    monkeypatch.setattr(BarracksWorker, "git", g)
    return g


def _hard(view, title: str = "Build the export", text: str = HARD) -> None:
    view.worker.new_task(title, text)


def _title(call: dict) -> str:
    return call["prompt"].split("## Task", 1)[1].splitlines()[0]


# -- the rules ---------------------------------------------------------------------------------------

def test_the_rules_judge_what_is_clearly_simple():
    assert plans.clearly_simple("Fix the typo", "Fix the typo in the README title")
    assert not plans.clearly_simple("Build it", HARD)                                   # three steps
    assert not plans.clearly_simple("All of them", "T1001 T1002 T1003 in one go")        # three tickets
    assert not plans.clearly_simple("Long", "x " * 400)


def test_a_plan_is_read_and_checked():
    assert plans.parse("SIMPLE — one agent will do") == (None, [])
    subs, errors = plans.parse("Here:\n```json\n" + plan(sub("api"), sub("ui", after=["api"])) + "\n```")
    assert errors == [] and [s.id for s in subs] == ["api", "ui"] and subs[1].after == ["api"]
    assert plans.parse("ACCEPT")[1] == ["the answer is neither SIMPLE nor a JSON plan"]
    _, errors = plans.parse(plan(sub("a", after=["b"]), sub("b", after=["a"])))
    assert errors == ["`after` makes a cycle"]
    _, errors = plans.parse(plan(sub("A b"), sub("c", tier="titan", after=["zzz"])))
    assert any("lowercase" in e for e in errors) and any("tier" in e for e in errors) and any("zzz" in e for e in errors)
    _, errors = plans.parse(plan(*[sub(f"s{i}") for i in range(plans.MAX_SUBTASKS + 1)]))
    assert any("at most" in e for e in errors)


def test_tiers_shift_by_the_goal_and_go_up_after_a_failure():
    assert plans.shift("warrior", -1) == "laborer" and plans.shift("laborer", -1) == "laborer"
    assert plans.shift("warrior", 1) == "elder" and plans.shift("elder", 1) == "elder"
    assert plans.up("laborer") == "warrior" and plans.up("elder") is None
    assert plans.goal_of("thrift").parallel == 2 and plans.goal_of("quality").simple == "warrior"
    assert plans.goal_of("nonsense") == plans.GOALS["balance"]


def test_only_ready_parts_start():
    def t(sid, status="blocked", after=(), touches=()):
        return bk.PoolTask(sid, sid, sid, status=status, sub=sid, after=list(after), touches=list(touches))
    kids = [t("api", touches=["src/api/"]), t("ui", touches=["src/ui/"]), t("docs", after=["api"]),
            t("api2", touches=["src/api/x.py"])]
    assert [k.sub for k in plans.ready(kids, 0)] == ["api", "ui"]        # docs waits for api; api2 shares files
    assert [k.sub for k in plans.ready(kids, 1)] == ["api"]
    kids[0].status = "done"
    assert [k.sub for k in plans.ready(kids, 0)] == ["ui", "docs", "api2"]


def test_a_plan_is_trimmed_to_the_budget_never_cut():
    subs = [plans.Sub("a", "A", "a", "elder", cheaper_ok=True), plans.Sub("b", "B", "b", "warrior")]
    costs = plans.tier_costs({})
    assert plans.trim(subs, None, costs) == (True, [])
    fits, notes = plans.trim(subs, 0.7, costs)
    assert fits and notes == ["a: elder → warrior"] and subs[0].tier == "warrior"
    assert plans.trim(subs, 0.1, costs)[0] is False and len(subs) == 2
    assert plans.tier_costs({"claude:haiku": {"runs": 4, "cost": 0.4}})["laborer"] == pytest.approx(0.1)


def test_the_steward_names_the_part_to_send_back():
    assert plans.rework_of("api: the stream is buffered", ["api", "ui"]) == ("api", "the stream is buffered")
    assert plans.rework_of("new: no docs at all", ["api"]) == ("", "no docs at all")
    assert plans.rework_of("it is all wrong", ["api"]) == ("", "it is all wrong")


def test_personas_are_kept_as_files(tmp_path: Path):
    assert personas.load(tmp_path, "backend") is None
    personas.save(tmp_path, personas.Persona("backend", "You build APIs.\nSmall commits.", "elder"))
    p = personas.load(tmp_path, "backend")
    assert (p.prompt, p.tier, p.approved) == ("You build APIs.\nSmall commits.", "elder", False)
    assert personas.listing(tmp_path) == []                                 # only the approved are offered
    p.approved = True
    personas.save(tmp_path, p)
    assert personas.listing(tmp_path) == [("backend", "elder", "You build APIs.")]
    with pytest.raises(ValueError):
        personas.save(tmp_path, personas.Persona("../x", "no"))


def test_parts_merge_without_a_checkout(fake_repo: Path):
    g = jobs.TaskGit()
    run = lambda *a: subprocess.run(["git", *a], cwd=fake_repo, check=True, capture_output=True, text=True)  # noqa: E731
    base = g.base_of(fake_repo)
    g.cut(fake_repo, "pool/camp/x", base)
    for name, path, line in (("a", "src/a.py", "a = 1\n"), ("b", "docs/b.md", "# B\n")):
        run("checkout", "-q", "-b", f"pool/camp/x--{name}", "pool/camp/x")
        (fake_repo / path).write_text(line, encoding="utf-8")
        run("add", ".")
        run("commit", "-qm", name)
    run("checkout", "-q", base)
    assert g.merge(fake_repo, "pool/camp/x", "pool/camp/x--a", "merge a") == (True, "merged")
    assert g.merge(fake_repo, "pool/camp/x", "pool/camp/x--b", "merge b") == (True, "merged")
    assert g.merge(fake_repo, "pool/camp/x", "pool/camp/x--b", "again") == (True, "already merged")
    files = run("ls-tree", "-r", "--name-only", "pool/camp/x").stdout.split()
    assert "src/a.py" in files and "docs/b.md" in files
    for name in ("c", "d"):                                                  # both change the same line
        run("checkout", "-q", "-b", f"pool/camp/x--{name}", "pool/camp/x")
        (fake_repo / "src" / "app.py").write_text(f"print('{name}')\n", encoding="utf-8")
        run("commit", "-qam", name)
    run("checkout", "-q", base)
    assert g.merge(fake_repo, "pool/camp/x", "pool/camp/x--c", "merge c")[0]
    ok, note = g.merge(fake_repo, "pool/camp/x", "pool/camp/x--d", "merge d")
    assert not ok and "src/app.py" in note
    passed, _ = g.check(fake_repo, "pool/camp/x", "test -f src/a.py", __import__("threading").Event(),
                        fake_repo / ".orkcraft" / "pool" / "camp" / "steward")
    assert passed


# -- the barracks ---------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_a_simple_task_goes_whole_to_a_light_ork(fake_repo: Path, monkeypatch, steward, git):
    s = steward()
    crew = Crew()
    app = _app(fake_repo, monkeypatch, crew)
    async with app.run_test(size=SIZE) as pilot:
        view, sent = await _open(pilot, app)
        _arrive(app, "T5001")
        assert await _until(pilot, lambda: len(crew.calls) == 1)
        st = view.state
        assert st.orcs[0].label == "claude:haiku" and st.queue == []
        assert not any("PLAN the task" in p for p in s.prompts)              # the rules were sure: no plan
        crew.finish(0)
        assert await _until(pilot, lambda: any(p.mode == "pool.done" for p in sent))
        assert s.models == ["sonnet"]                                         # a warrior reads a simple task


@pytest.mark.asyncio
async def test_a_hard_task_is_planned_run_in_parallel_merged_and_reviewed_whole(fake_repo: Path, monkeypatch,
                                                                                steward, git):
    git.pr = "https://github.com/o/r/pull/7"
    s = steward(plans=[plan(sub("api", "elder", touches=["src/api/"]), sub("ui", "laborer", touches=["src/ui/"]),
                            sub("docs", "laborer", after=["api", "ui"], touches=["docs/"]))])
    crew = Crew()
    app = _app(fake_repo, monkeypatch, crew, test_cmd="pytest -q")
    async with app.run_test(size=SIZE) as pilot:
        view, sent = await _open(pilot, app)
        _hard(view)
        assert await _until(pilot, lambda: len(crew.calls) == 2)              # api and ui at once, docs waits
        st = view.state
        parent = next(t for t in st.tasks if t.plan)
        assert parent.status == "planned" and parent.branch == f"pool/camp/{parent.id}"
        assert git.cuts == [(parent.branch, "main")]
        assert s.models[0] == "opus"                                          # an elder plans
        assert sorted(o.label for o in st.orcs) == ["claude:haiku", "claude:opus"]
        kids = {k.sub: k for k in view.worker.children(parent)}
        assert kids["docs"].status == "blocked" and kids["api"].base == parent.branch
        assert kids["api"].branch == f"{parent.branch}--api"
        assert "## The whole task" in crew.calls[0]["prompt"]
        assert [p.mode for p in sent] == ["pool.assigned", "pool.assigned", "pool.assigned"]
        crew.finish(0)
        crew.finish(1)
        assert await _until(pilot, lambda: len(crew.calls) == 3)              # both merged: docs starts
        assert sorted(git.merges) == sorted([(parent.branch, f"{parent.branch}--api"),
                                             (parent.branch, f"{parent.branch}--ui")])
        assert "Docs" in _title(crew.calls[2])
        assert not any(p.mode == "pool.done" for p in sent)                   # a part makes no pull request
        crew.finish(2)
        assert await _until(pilot, lambda: parent.status == "done")
        assert git.checks == [parent.branch]                                  # the tests of the merged whole
        assert git.published == [(parent.branch, "main", "Build the export")]
        done = [p for p in sent if p.mode == "pool.done"]
        assert len(done) == 1 and "3 parts" in done[0].value and "pull/7" in done[0].value
        last = next(p for p in s.prompts if "judge the WHOLE" in p)
        assert "## The operator's request: Build the export" in last and HARD in last
        assert s.models[-1] == "opus"                                         # ⚖️ balance: an elder looks at the whole


@pytest.mark.asyncio
async def test_the_whole_sent_back_names_its_part(fake_repo: Path, monkeypatch, steward, git):
    s = steward(plans=[plan(sub("api", touches=["src/"]), sub("docs", touches=["docs/"]))],
                verdicts=["ACCEPT", "ACCEPT", "REWORK: api: the stream is buffered", "ACCEPT", "ACCEPT"])
    crew = Crew()
    app = _app(fake_repo, monkeypatch, crew)
    async with app.run_test(size=SIZE) as pilot:
        view, sent = await _open(pilot, app)
        _hard(view)
        assert await _until(pilot, lambda: len(crew.calls) == 2)
        crew.finish(0)
        crew.finish(1)
        assert await _until(pilot, lambda: len(crew.calls) == 3)              # api goes back to its ork
        st = view.state
        parent = next(t for t in st.tasks if t.plan)
        assert parent.status == "planned" and parent.attempts == 1
        assert "the stream is buffered" in crew.calls[2]["prompt"] and "Api" in _title(crew.calls[2])
        crew.finish(2)
        assert await _until(pilot, lambda: parent.status == "done")
        assert len([p for p in s.prompts if "judge the WHOLE" in p]) == 2


@pytest.mark.asyncio
async def test_a_part_that_does_not_merge_goes_back(fake_repo: Path, monkeypatch, steward, git):
    steward(plans=[plan(sub("a", touches=["src/a/"]), sub("b", touches=["src/b/"]))])
    crew = Crew()
    app = _app(fake_repo, monkeypatch, crew)
    async with app.run_test(size=SIZE) as pilot:
        view, _sent = await _open(pilot, app)
        _hard(view)
        assert await _until(pilot, lambda: len(crew.calls) == 2)
        parent = next(t for t in view.state.tasks if t.plan)
        git.conflicts = {f"{parent.branch}--b"}
        crew.finish(0)
        crew.finish(1)
        assert await _until(pilot, lambda: len(crew.calls) == 3)
        assert f"does not merge into `{parent.branch}`" in crew.calls[2]["prompt"]


@pytest.mark.asyncio
async def test_the_steward_may_say_simple_and_a_bad_plan_runs_whole(fake_repo: Path, monkeypatch, steward, git):
    s = steward(plans=["SIMPLE", "nonsense", "still nonsense"])
    crew = Crew()
    app = _app(fake_repo, monkeypatch, crew)
    async with app.run_test(size=SIZE) as pilot:
        view, _sent = await _open(pilot, app)
        _hard(view)
        assert await _until(pilot, lambda: len(crew.calls) == 1)
        assert view.state.orcs[0].label == "claude:haiku"                    # simple: a laborer
        _hard(view, "Build the import")
        assert await _until(pilot, lambda: len(crew.calls) == 2)
        assert view.state.task(view.state.orcs[1].task).tier == "warrior"   # tried twice: whole, on a warrior
        assert len([p for p in s.prompts if "PLAN the task" in p]) == 3
        assert "## Your last plan did not hold" in s.prompts[-1]


@pytest.mark.asyncio
async def test_a_plan_that_does_not_fit_the_budget_is_trimmed(fake_repo: Path, monkeypatch, steward, git):
    steward(plans=[plan(sub("a", "elder", cheaper_ok=True), sub("b", "elder")),
                   plan(sub("c", "elder"), sub("d", "elder"))])
    crew = Crew(cost=0.0)
    app = _app(fake_repo, monkeypatch, crew, budget_usd=1.9)
    async with app.run_test(size=SIZE) as pilot:
        view, _sent = await _open(pilot, app)
        _hard(view)
        assert await _until(pilot, lambda: len(crew.calls) == 2)
        st = view.state
        parent = next(t for t in st.tasks if t.plan)
        assert {k.sub: k.tier for k in view.worker.children(parent)} == {"a": "warrior", "b": "elder"}
        assert any(d.action == "trim" and "a: elder → warrior" in d.why for d in st.decisions())
        _hard(view, "Build the import")
        assert await _until(pilot, lambda: any("does not fit" in d.why for d in st.decisions()))
        assert sum(1 for t in st.tasks + st.queue if t.plan) == 1           # the second runs whole


@pytest.mark.asyncio
async def test_thrift_lets_the_tests_judge_a_part_and_runs_two_at_once(fake_repo: Path, monkeypatch, steward, git):
    from orkcraft import scroll as ts
    s = steward(plans=[plan(*(sub(f"p{i}", touches=[f"src/p{i}/"]) for i in range(3)))])
    crew = Crew()
    app = _app(fake_repo, monkeypatch, crew)
    ts_building = app.scroll.building("camp")
    ts_building.goal = "thrift"
    async with app.run_test(size=SIZE) as pilot:
        view, _sent = await _open(pilot, app)
        _hard(view)
        assert await _until(pilot, lambda: len(crew.calls) == 2)
        await pilot.pause(0.1)
        assert len(crew.calls) == 2                                          # 🪙: two at once, not three
        assert {o.label for o in view.state.orcs} == {"claude:haiku"}       # warrior → laborer
        crew.finish(0)
        assert await _until(pilot, lambda: len(crew.calls) == 3)
        assert not any("## The orc's report" in p for p in s.prompts)       # no read of a part: the tests
        for i in (1, 2):
            crew.finish(i)
        parent = next(t for t in view.state.tasks if t.plan)
        assert await _until(pilot, lambda: parent.status == "done")
        assert s.models[-1] == "sonnet"                                      # 🪙: a warrior looks at the whole
    assert ts.GOALS


@pytest.mark.asyncio
async def test_a_failed_try_goes_up_one_tier(fake_repo: Path, monkeypatch, steward, git):
    steward(verdicts=["REWORK: the test is missing", "ACCEPT"])
    crew = Crew()
    app = _app(fake_repo, monkeypatch, crew)
    async with app.run_test(size=SIZE) as pilot:
        view, _sent = await _open(pilot, app)
        _arrive(app, "T5002")
        assert await _until(pilot, lambda: len(crew.calls) == 1)
        crew.finish(0)
        assert await _until(pilot, lambda: len(crew.calls) == 2)
        st = view.state
        assert st.orcs[0].label == "claude:sonnet" and len(st.orcs) == 1    # the same ork, one tier up
        assert crew.calls[1]["resume"] == "s1"                               # its session goes on
        assert any(d.action == "escalate" and "laborer → warrior" in d.why for d in st.decisions())
        crew.finish(1)
        assert await _until(pilot, lambda: st.orcs[0].status == "idle")


# -- personas and autonomy ------------------------------------------------------------------------

def _level(level: int, quiet: bool, monkeypatch) -> None:
    settings.save(settings.MachineSettings(onboarded=True, autonomy=level, autonomy_wait=5,
                                           quiet=schedule.DEFAULT_QUIET))
    monkeypatch.setattr(schedule, "quiet_now", lambda m, now=None: quiet)


NEW_PERSONA = plan(sub("api", touches=["src/"], persona="streamer", prompt="You write streaming endpoints."),
                   sub("docs", touches=["docs/"]))


@pytest.mark.asyncio
async def test_chains_a_new_persona_waits_for_the_operator(fake_repo: Path, monkeypatch, steward, git):
    _level(autonomy.CHAINS, False, monkeypatch)
    steward(plans=[NEW_PERSONA])
    crew = Crew()
    app = _app(fake_repo, monkeypatch, crew)
    async with app.run_test(size=SIZE) as pilot:
        view, sent = await _open(pilot, app)
        _hard(view)
        assert await _until(pilot, lambda: len(crew.calls) == 1)             # docs runs, api waits
        st = view.state
        waiting = st.asked[0]
        assert waiting.persona_waits == "streamer" and "You write streaming endpoints." in waiting.question
        assert any(p.mode == "pool.question" for p in sent)
        assert not view.worker.tick_personas(now=time.time() + 3600)        # ⛓️: no timer
        view.worker.answer(waiting.id, "yes")
        assert await _until(pilot, lambda: len(crew.calls) == 2)
        assert "## Who you are: streamer" in crew.calls[1]["prompt"]
        assert personas.load(view.worker.state_dir, "streamer").approved
        assert next(o for o in st.orcs if o.task == waiting.id).persona == "streamer"


@pytest.mark.asyncio
async def test_timer_a_new_persona_is_approved_when_nobody_answers(fake_repo: Path, monkeypatch, steward, git):
    _level(autonomy.TIMER, False, monkeypatch)
    steward(plans=[NEW_PERSONA])
    crew = Crew()
    app = _app(fake_repo, monkeypatch, crew)
    async with app.run_test(size=SIZE) as pilot:
        view, _sent = await _open(pilot, app)
        _hard(view)
        assert await _until(pilot, lambda: len(crew.calls) == 1)
        st = view.state
        assert "approved by itself in 5 min" in st.asked[0].question
        assert not view.worker.tick_personas(now=time.time() + 60)          # still the operator's
        assert view.worker.tick_personas(now=time.time() + 301)
        assert await _until(pilot, lambda: len(crew.calls) == 2)
        assert any(d.action == "persona" and "nobody answered in 5 min" in d.why for d in st.decisions())


@pytest.mark.asyncio
async def test_free_orks_and_quiet_hours_do_not_wait(fake_repo: Path, monkeypatch, steward, git):
    _level(autonomy.TIMER, True, monkeypatch)                                # ⏳ in quiet hours: no wait
    steward(plans=[NEW_PERSONA])
    crew = Crew()
    app = _app(fake_repo, monkeypatch, crew)
    async with app.run_test(size=SIZE) as pilot:
        view, _sent = await _open(pilot, app)
        _hard(view)
        assert await _until(pilot, lambda: len(crew.calls) == 2)
        assert view.state.asked == []


@pytest.mark.asyncio
async def test_the_operator_may_rewrite_or_refuse_a_persona(fake_repo: Path, monkeypatch, steward, git):
    _level(autonomy.CHAINS, False, monkeypatch)
    steward(plans=[NEW_PERSONA, plan(sub("x", touches=["a/"], persona="tidy", prompt="You tidy."),
                                     sub("y", touches=["b/"]))])
    crew = Crew()
    app = _app(fake_repo, monkeypatch, crew, max_orcs=4)
    async with app.run_test(size=SIZE) as pilot:
        view, _sent = await _open(pilot, app)
        _hard(view)
        assert await _until(pilot, lambda: len(view.state.asked) == 1)
        view.worker.answer(view.state.asked[0].id, "You write small, streaming endpoints with tests.")
        assert await _until(pilot, lambda: len(crew.calls) == 2)
        p = personas.load(view.worker.state_dir, "streamer")
        assert p.approved and p.by == "operator" and p.prompt.startswith("You write small")
        _hard(view, "Build the import")
        assert await _until(pilot, lambda: len(view.state.asked) == 1)
        refused = view.state.asked[0]
        view.worker.answer(refused.id, "no")
        assert await _until(pilot, lambda: len(crew.calls) == 4)
        assert refused.persona == "" and not personas.load(view.worker.state_dir, "tidy").approved


def test_no_hand_hiring():
    assert not hasattr(BarracksWorker, "hire_by_hand")
    from orkcraft.gui.views import barracks as gui
    from orkcraft.realm import catalog
    assert "hire" not in gui.ACTS
    actions = {a.id for a in catalog.TYPES["barracks"].actions}
    assert "pool.hire" not in actions and "pool.answer" in actions


@pytest.mark.asyncio
async def test_a_plan_fits_what_is_left_of_the_quota(fake_repo: Path, monkeypatch, steward, git):
    from orkcraft.core.workers import barracks_plan
    from orkcraft.realm import pressure
    settings.save(settings.MachineSettings(onboarded=True))                    # claude on a subscription
    machine = settings.load()
    machine.tools["claude"].enabled = True
    settings.save(machine)
    camp = pressure.Camp(left=200_000, limit="claude 5h", hours=2.0)
    monkeypatch.setattr(barracks_plan.pressure, "measure", lambda *a, **k: camp)
    steward(plans=[plan(sub("a", "elder", cheaper_ok=True), sub("b", "elder", cheaper_ok=True))])
    crew = Crew(cost=0.0)
    app = _app(fake_repo, monkeypatch, crew)
    async with app.run_test(size=SIZE) as pilot:
        view, _sent = await _open(pilot, app)
        view.worker.town.limits = ["a read"]
        _hard(view)
        assert await _until(pilot, lambda: len(crew.calls) == 2)
        st = view.state
        parent = next(t for t in st.tasks if t.plan)
        # 2 × 80k on elders > 100k (half of what is left): both go down to warriors (2 × 60k), then one more
        assert sorted(k.tier for k in view.worker.children(parent)) == ["laborer", "warrior"]
        trim = next(d for d in st.decisions() if d.action == "trim")
        assert "~200k tokens left of claude 5h" in trim.why
        assert any(d.action == "plan" and "k tokens" in d.why for d in st.decisions())


@pytest.mark.asyncio
async def test_a_tight_quota_makes_the_barracks_thrifty(fake_repo: Path, monkeypatch, steward, git):
    from orkcraft.core.workers import barracks_plan
    from orkcraft.realm import pressure
    machine = settings.MachineSettings(onboarded=True)
    machine.tools["claude"].enabled = True
    settings.save(machine)
    monkeypatch.setattr(barracks_plan.pressure, "measure",
                        lambda *a, **k: pressure.Camp(left=10_000_000, limit="claude week", tight=True))
    steward(plans=[plan(sub("a", touches=["a/"]), sub("b", touches=["b/"]), sub("c", touches=["c/"]))])
    crew = Crew(cost=0.0)
    app = _app(fake_repo, monkeypatch, crew)
    async with app.run_test(size=SIZE) as pilot:
        view, _sent = await _open(pilot, app)
        view.worker.town.limits = ["a read"]
        _hard(view)
        assert await _until(pilot, lambda: len(crew.calls) == 2)
        await pilot.pause(0.1)
        assert len(crew.calls) == 2 and {o.label for o in view.state.orcs} == {"claude:haiku"}
        assert any("the quota is tight" in d.why for d in view.state.decisions())
