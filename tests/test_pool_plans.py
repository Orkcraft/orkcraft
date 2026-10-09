"""🧭 The Barracks' steward plans (docs/design/barracks-planning.md): simple tasks to a light ork, hard
ones into parts — in parallel by the graph, merged into one branch, the whole reviewed; personas by
autonomy; a failed try goes up one tier; a plan that does not fit the budget is trimmed."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from orkcraft import schedule, settings
from orkcraft.core.workers.barracks import BarracksWorker
from orkcraft.realm import barracks as bk
from orkcraft.realm import jobs, personas, plans
from orkcraft.realm import steward as steward_mod
from tests.pool_fakes import FakeGit, Steward

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


# -- personas and autonomy ------------------------------------------------------------------------

def _level(level: int, quiet: bool, monkeypatch) -> None:
    settings.save(settings.MachineSettings(onboarded=True, autonomy=level, autonomy_wait=5,
                                           quiet=schedule.DEFAULT_QUIET))
    monkeypatch.setattr(schedule, "quiet_now", lambda m, now=None: quiet)


NEW_PERSONA = plan(sub("api", touches=["src/"], persona="streamer", prompt="You write streaming endpoints."),
                   sub("docs", touches=["docs/"]))


def test_no_hand_hiring():
    assert not hasattr(BarracksWorker, "hire_by_hand")
    from orkcraft.gui.views import barracks as gui
    from orkcraft.realm import catalog
    assert "hire" not in gui.ACTS
    actions = {a.id for a in catalog.TYPES["barracks"].actions}
    assert "pool.hire" not in actions and "pool.answer" in actions


# -- what waits for the operator: the clock -------------------------------------------------------


# -- the triage --------------------------------------------------------------------------------------

def test_a_sort_is_read_and_checked():
    t = plans.parse_triage('ok: {"kind": "single", "tier": "elder", "why": "tricky locking"}')
    assert (t.kind, t.tier, t.why) == ("single", "elder", "tricky locking")
    assert plans.parse_triage('{"kind": "single", "tier": "huge"}').tier == "warrior"      # an unknown tier
    assert plans.parse_triage('{"kind": "plan", "tier": "elder"}').tier == ""
    assert plans.parse_triage("ACCEPT") is None and plans.parse_triage('{"kind": "maybe"}') is None
    assert [steward_mod.goal_tier("barracks", "plan", g) for g in ("thrift", "balance", "quality")] == \
        ["warrior", "warrior", "elder"]
