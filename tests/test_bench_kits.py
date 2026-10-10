"""The Test bench for External listeners, the Task board and the Calendar (realm/bench_kits.py, core/bench_kits.py):
the case's input given to the building in a town of its own and to the bare AI tool, both results through one check.
The models are faked; the buildings, their towns and their roads are real."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from orkcraft.core import bench as building_bench
from orkcraft.core import runners
from orkcraft.core.workers.barracks import BarracksWorker
from orkcraft.core.workers.watchtower import WatchtowerWorker
from orkcraft.realm import bench, bench_kits
from tests.pool_fakes import Steward


@pytest.fixture(autouse=True)
def quick(monkeypatch, isolated_layout_file):
    from orkcraft.core import bench_kits as building_kits
    monkeypatch.setattr(building_kits, "POLL_S", 0.05)


FIRST = {"watchtower": "feedback-inbox", "fields": "titles-and-plans", "war_drum": "two-briefs"}


def _case(type_id: str) -> bench.Case:
    c = bench.case(Path("/nonexistent"), type_id, FIRST[type_id])
    assert c is not None
    return c


def _bare(answer: dict):
    seen = []

    def run(tool, prompt, workdir, cancel, model):
        seen.append((prompt, model, Path(workdir)))
        return json.dumps(answer), 0.01, 300, ""
    return run, seen


# -- the checks ----------------------------------------------------------------------------------------------

def test_words_are_found_by_their_stem_or_as_they_are():
    assert bench_kits.has("Call about the bookings page", "booking")
    assert bench_kits.has("Policy 4471-B", [["x"], "4471"][1]) and not bench_kits.has("Policy 4471", "4472")
    assert bench_kits.has("Café déjà vu", "cafe") and bench_kits.has("Договор в папке", "договора")
    assert bench_kits.has("Dana from Northwind", ["Mia", "Dana"]) and not bench_kits.has("nobody", ["Mia", "Dana"])


def test_a_listeners_result_is_checked_message_by_message():
    c = _case("watchtower")
    keep = {1, 3, 5, 8}
    right = {"messages": [{"n": n, "kept": n in keep, "importance": "high" if n == 5 else "normal", "answer": ""}
                          for n in range(1, 9)]}
    checks = bench_kits.KITS["watchtower"].check(c, right)
    assert len(checks) == 9 and all(x["ok"] for x in checks)                       # 8 kept-or-not, 1 importance
    wrong = {"messages": [dict(r, kept=True) for r in right["messages"]][:7]}       # keeps all, misses the last
    bad = [x["name"] for x in bench_kits.KITS["watchtower"].check(c, wrong) if not x["ok"]]
    assert any("SaaS Weekly" in n for n in bad) and any(n.startswith("#8") for n in bad)


# -- External listeners -------------------------------------------------------------------------------------

def test_external_listeners_judge_the_inbox_in_a_town_of_their_own(tmp_path, monkeypatch):
    prompts = []

    def judge(prompt):
        prompts.append(prompt)
        listed = re.findall(r"^\[(\d+)\] \w+ · (.+)$", prompt, re.M)        # the tower judges as they come, in batches
        rows = []
        for n, title in listed:
            if "charged me twice" in title:
                rows.append({"n": int(n), "why": "double charge", "asks": "action", "urgency": "now", "risk": "high",
                             "tone": "angry", "agent": False})
            elif any(w in title for w in ("crashes", "Calendar sync", "reminders")):
                rows.append({"n": int(n), "why": "feedback"})
        return json.dumps({"keep": rows}), 0.0
    monkeypatch.setattr(WatchtowerWorker, "judge_runner", staticmethod(judge))
    bare_runner, seen = _bare({"messages": [{"n": n, "keep": n != 2, "importance": "normal"} for n in range(1, 9)]})
    c = _case("watchtower")
    report, folder = building_bench.run(tmp_path, c, bare_runner=bare_runner)
    b = report.building
    assert b.error == "" and b.passed is True, b.checks
    assert "INTENT: feedback from the users" in prompts[0] and any("Love the reminders" in p for p in prompts)
    assert any(h.startswith("#5: kept · high") for h in b.how)
    assert report.bare.passed is False and sum(not x["ok"] for x in report.bare.checks) == 4   # kept 3 it should not, #5 not high
    assert "SaaS Weekly" in seen[0][0] and "Answer with JSON only" in seen[0][0]
    assert not (tmp_path / ".orkcraft" / "watchtower").exists()                    # the town it came from: untouched
    assert "passed, 9 of 9 checks" in bench.render(report, "External listeners")


# -- Task board -----------------------------------------------------------------------------------------------

def test_the_task_board_names_cards_and_plans_with_the_wikis_pages(tmp_path, monkeypatch):
    asked = []

    def fast(prompt, model=None):
        asked.append(prompt)
        if prompt.startswith("Name this task"):
            return ("Car insurance renewal" if "insurance" in prompt else "Dishwasher leak"), 0.0
        if "Renew the car insurance" in prompt:
            return "1. Find policy 4471-B\n2. Get two quotes to compare\n3. Call Ann at Northgate", 0.0
        return "1. Find the Currys receipt\n2. Check the warranty\n3. Book the repair", 0.0
    monkeypatch.setattr(runners, "FASTPATH_RUNNER", fast)
    bare_runner, seen = _bare({"titles": [{"n": 1, "title": "Insurance"}, {"n": 2, "title": "Fix dishwasher leak"}],
                               "plans": [{"n": 1, "steps": ["Shop around", "Switch"]},
                                         {"n": 2, "steps": ["Call a plumber", "Pay", "Done"]}]})
    report, _ = building_bench.run(tmp_path, _case("fields"), bare_runner=bare_runner)
    b = report.building
    assert b.error == "" and b.passed is True, [x for x in b.checks if not x["ok"]]
    plan = next(p for p in asked if "Renew the car insurance" in p)
    assert "4471-B" in plan                                                      # the wiki page went with it
    assert any("Car insurance" in h for h in b.how if "context" in h)
    assert report.bare.passed is False
    failed = {x["name"] for x in report.bare.checks if not x["ok"]}
    assert "title #1: 2–4 words" in failed and any("4471" in n for n in failed)
    assert (seen[0][2] / "llm-wiki" / "general" / "pages" / "car-insurance.md").is_file()   # the bare tool could read it


# -- Calendar ---------------------------------------------------------------------------------------------------

def test_the_calendar_gets_its_briefs_from_the_agent_pool_along_its_roads(tmp_path, monkeypatch):
    asked = []

    def work(harness, prompt, workdir, cancel, model, env, resume):
        asked.append(prompt)
        if "Northwind" in prompt:
            brief = ("# Client call: Northwind\n\n## Agenda\n- the renewal in December\n- SSO and an audit log\n\n"
                     "## People\n- Dana Holt\n\n## Questions to ask\n- What would make them renew?")
        else:
            brief = ("# Design review\n\n## Agenda\n- the new booking page\n- email reminders\n\n## People\n"
                     "- Mia Chen\n- Sam Patel\n\n## Questions to ask\n- Payments now or later?")
        return brief, 0.05, 900, "s1"
    monkeypatch.setattr(BarracksWorker, "work_runner", staticmethod(work))
    monkeypatch.setattr(BarracksWorker, "steward_runner", Steward())
    bare_runner, _ = _bare({"briefs": [{"n": 1, "text": "## Agenda\nThe booking page with Mia and Sam, reminders."},
                                       {"n": 2, "text": "Talk to them."}]})
    report, _ = building_bench.run(tmp_path, _case("war_drum"), bare_runner=bare_runner)
    b = report.building
    assert b.error == "" and b.passed is True, [x for x in b.checks if not x["ok"]] or b.how
    assert any("Who: Mia Chen, Sam Patel" in p and "the new booking page" in p for p in asked)   # the invitation's text
    assert any("## Agenda, ## People and ## Questions to ask" in p for p in asked)               # the case's orders
    assert b.orks >= 1 and "Dana Holt" in b.text
    assert report.bare.passed is False
    assert {x["name"] for x in report.bare.checks if not x["ok"]} >= {"brief of “Client call: Northwind” says “SSO”"}


def test_a_kit_case_needs_no_task_and_its_bare_side_runs_on_the_buildings_tier(tmp_path, monkeypatch):
    monkeypatch.setattr(WatchtowerWorker, "judge_runner", staticmethod(lambda p: ('{"keep": []}', 0.0)))
    bare_runner, seen = _bare({"messages": []})
    c = _case("watchtower")
    assert c.task == "" and c.inputs["intent"]
    report, _ = building_bench.run(tmp_path, c, tier="warrior", bare_runner=bare_runner)
    assert seen[0][1] == "sonnet" or seen[0][1]                                  # the tier picked, as a model
    assert report.bare.model == "warrior"
    assert re.search(r"failed, \d+ of 9 checks", bench.verdict(report.building))


# -- Research ---------------------------------------------------------------------------------------------------

def test_research_finds_the_facts_on_the_web_and_the_bare_tool_is_judged_the_same(tmp_path, monkeypatch):
    from orkcraft.realm import roads
    calls = []

    def agents(tool, prompt, workdir, env, cancel, model="", web=False, **_):
        calls.append((tool, web))
        if "Do not search" in prompt:
            return json.dumps({"plan": [{"q": "When did it enter into force?"}, {"q": "When do the bans apply?"},
                                        {"q": "When do the GPAI rules apply?"}]}), 0.01, 100
        if '"groups"' in prompt:
            return json.dumps({"groups": [[1], [2], [3]], "conflicts": []}), 0.01, 100
        found = [("The AI Act entered into force on 1 August 2024.", "https://eur-lex.europa.eu/eli/reg/2024/1689"),
                 ("Its bans apply from 2 February 2025.", "https://digital-strategy.ec.europa.eu/ai-act"),
                 ("The GPAI obligations apply from 2 August 2025.", "https://artificialintelligenceact.eu/timeline")]
        return json.dumps({"findings": [{"sub": n, "claim": c, "sources": [{"url": u, "quote": c}]}
                                        for n, (c, u) in enumerate(found, 1)]}), 0.05, 2000
    monkeypatch.setattr(roads, "run_agent", agents)
    bare_runner, seen = _bare({"findings": [{"sub": 1, "claim": "It entered into force in August 2024.",
                                             "sources": [{"url": "https://example.com/a"}]}]})
    c = next(x for x in bench.cases(Path("/x"), "mine") if x.id == "eu-ai-act-dates")
    report, _ = building_bench.run(tmp_path, c, tool="claude", bare_runner=bare_runner)
    b = report.building
    assert b.error == "" and b.passed is True, [x for x in b.checks if not x["ok"]] or b.how
    assert ("claude", True) in calls and b.orks == 1
    assert any(h.startswith("single: The AI Act entered") for h in b.how)          # one tool: one source, no rounds
    assert "1 August 2024" in b.text or b.text.startswith("#")
    assert report.bare.passed is False and "When did the EU AI Act" in seen[0][0]
    assert {x["name"] for x in report.bare.checks if not x["ok"]} >= {"sources on at least 2 sites"}


# -- Review board -------------------------------------------------------------------------------------------------

def test_the_review_board_sends_back_the_planted_flaws(tmp_path, monkeypatch):
    from orkcraft.core.workers.council import CouncilWorker
    from orkcraft.realm import team as tm
    asked = []

    def board(harness, prompt, model):
        asked.append(prompt)
        if prompt.startswith("You are the steward"):
            return "DECISION: REWORK\nHash with argon2, not MD5; reset links must expire; limit login attempts.", 0.02
        role = tm._ROLE.match(prompt).group(1)
        if role == "Security reviewer":
            return "VETO — MD5 is broken; the reset token never expires; no rate limit on /login.", 0.03
        return "CHANGES — backups on the same server; no feature flag.", 0.03
    monkeypatch.setattr(CouncilWorker, "runner", staticmethod(board))
    bare_runner, _ = _bare({"verdict": "approve", "notes": "Looks fine.", "route": ""})
    c = next(x for x in bench.cases(Path("/x"), "council") if x.id == "planted-flaws")
    report, _ = building_bench.run(tmp_path, c, bare_runner=bare_runner)
    b = report.building
    assert b.error == "" and b.passed is True, [x for x in b.checks if not x["ok"]] or b.how
    assert any(p.startswith("You are Security reviewer") for p in asked)                        # the case's roles
    assert b.orks == 2 and any(h.startswith("steward: rework") for h in b.how)
    assert report.bare.passed is False and len([x for x in report.bare.checks if not x["ok"]]) == 4


def test_the_review_board_routes_a_bug_to_development(tmp_path, monkeypatch):
    from orkcraft.core.workers.council import CouncilWorker

    def board(harness, prompt, model):
        if prompt.startswith("You are the steward"):
            assert "`development`" in prompt                                            # the case's exits, by id
            return "DECISION: APPROVE\nEXIT: development\nTASK: fix the CSV export error", 0.02
        return "APPROVE — a clear bug report.", 0.02
    monkeypatch.setattr(CouncilWorker, "runner", staticmethod(board))
    bare_runner, seen = _bare({"verdict": "approve", "notes": "", "route": "reply"})
    c = next(x for x in bench.cases(Path("/x"), "council") if x.id == "route-a-request")
    report, _ = building_bench.run(tmp_path, c, bare_runner=bare_runner)
    assert report.building.passed is True, report.building.checks or report.building.how
    assert report.bare.passed is False and "`development`" in seen[0][0]


# -- every shipped case of a kit is one its check can pass and fail ---------------------------------------------------

def _ideal(c: bench.Case) -> dict:
    """The answer a case asks for, built from its own expectations: every check should pass on it."""
    def words(groups) -> str:
        return " ".join(g if isinstance(g, str) else g[0] for g in groups or [])
    if c.type == "watchtower":
        return {"messages": [{"n": n, "kept": m["expect"].get("kept", True), "importance": m["expect"].get("importance", ""),
                              "answer": m["expect"].get("answer", "")} for n, m in enumerate(c.inputs["messages"], 1)]}
    if c.type == "fields":
        return {"titles": [{"n": n, "title": f"{words(t.get('expect_words'))} card"[:60]}
                           for n, t in enumerate(c.inputs.get("titles") or [], 1)],
                "plans": [{"n": n, "steps": [words(p.get("expect_words")), "then the second step", "and the last one"]}
                          for n, p in enumerate(c.inputs.get("plans") or [], 1)]}
    heads = c.inputs.get("expect_headings") or []
    return {"briefs": [{"n": n, "text": "\n".join(f"## {h}\n{words(e.get('expect_words'))}" for h in heads or ["Brief"])}
                       for n, e in enumerate(c.inputs["events"], 1)]}


@pytest.mark.parametrize("case", [c for t in ("watchtower", "fields", "war_drum") for c in bench.cases(Path("/x"), t)],
                         ids=lambda c: f"{c.type}-{c.id}")
def test_every_kit_case_can_be_passed_and_failed(case):
    kit = bench_kits.KITS[case.type]
    assert case.level in bench.LEVELS and case.title and case.expect
    good = kit.check(case, _ideal(case))
    assert good and all(x["ok"] for x in good), [x for x in good if not x["ok"]]
    assert not any(x["ok"] for x in kit.check(case, kit.parse("{}")) if "words" not in x["name"])
    assert kit.prompt(case)                                                     # the bare tool's ask builds


def test_the_kits_have_a_case_of_every_level():
    for t in ("watchtower", "fields", "war_drum"):
        assert {c.level for c in bench.cases(Path("/x"), t)} == set(bench.LEVELS), t


def test_a_board_with_plans_only_and_a_calendar_of_one_meeting_run_too(tmp_path, monkeypatch):
    plans = []

    def fast(prompt, model=None):
        plans.append(prompt)
        return "1. Подать заявление на Госуслугах\n2. Сделать фото 35×45\n3. Оплатить госпошлину 6000 ₽", 0.0
    monkeypatch.setattr(runners, "FASTPATH_RUNNER", fast)
    bare_runner, _ = _bare({"titles": [], "plans": [{"n": 1, "steps": ["Сходить в МФЦ"]}]})
    c = bench.case(Path("/x"), "fields", "russian-passport")
    report, _ = building_bench.run(tmp_path, c, bare_runner=bare_runner)
    assert report.building.passed is True, report.building.checks
    assert "Госуслуги" in plans[0] and report.bare.passed is False

    monkeypatch.setattr(BarracksWorker, "work_runner", staticmethod(
        lambda h, p, w, c, m, e, r: ("## Agenda\n- Alex's promotion\n- Q4 goals\n\n## Questions to ask\n- ?", 0.0, 0, "")))
    monkeypatch.setattr(BarracksWorker, "steward_runner", Steward())
    report, _ = building_bench.run(tmp_path, bench.case(Path("/x"), "war_drum", "one-to-one"),
                                   bare_runner=_bare({"briefs": []})[0])
    assert report.building.passed is True, report.building.checks or report.building.how


# -- a chain of buildings -------------------------------------------------------------------------------------------

def test_a_chain_runs_in_a_copy_from_its_first_building_to_what_comes_back(tmp_path, monkeypatch):
    from orkcraft.core.workers.council import CouncilWorker
    from orkcraft.realm import team as tm
    asked = []

    def board(harness, prompt, model):
        if prompt.startswith("You are the steward"):
            return "DECISION: APPROVE\nGo on, but the card numbers must leave the logs.", 0.01
        return "CHANGES — the full card number and CVV in logs breaks PCI.", 0.01

    def work(harness, prompt, workdir, cancel, model, env, resume):
        asked.append(prompt)
        return "Masked the card number and dropped the CVV from the payment logs (PCI).", 0.02, 300, ""

    monkeypatch.setattr(CouncilWorker, "runner", staticmethod(board))
    monkeypatch.setattr(BarracksWorker, "work_runner", staticmethod(work))
    monkeypatch.setattr(BarracksWorker, "steward_runner", Steward())
    spec = {"id": "chain:b:p", "first": "b", "last": "p", "back_event": "pool.done", "back_filter": {},
            "about": "Review board, then Agent pool",
            "buildings": [{"id": "b", "type": "council", "title": "Board", "config": {"max_cycles": 2}},
                          {"id": "p", "type": "barracks", "title": "Pool", "config": {"worktrees": False, "plan": False}}],
            "roads": [{"target": "p", "source": "b", "event": "team.approved", "filter": {}, "handler": None}]}
    bare_runner, seen = _bare({})
    c = bench.case(Path("/x"), "chain", "board-review-route")
    report, _ = building_bench.run(tmp_path, c, chain=spec, bare_runner=lambda *a: ("Looks fine.", 0.0, 0, ""))
    b = report.building
    assert b.error == "" and b.passed is True, [x for x in b.checks if not x["ok"]] or b.how
    assert report.subject == "chain:b:p" and b.orks == 2
    assert any("logs/payments.log" in p for p in asked)                        # the case went in at the board
    assert "Masked the card number" in b.text
    assert report.bare.passed is False
    with pytest.raises(ValueError, match="needs the chain"):
        building_bench.run(tmp_path, c)


def test_a_lab_case_goes_into_its_entry_and_a_blind_judge_scores_both_sides(tmp_path, monkeypatch):
    from orkcraft.realm import lab_cases

    def work(harness, prompt, workdir, cancel, model, env, resume):
        return "slugify: lowercases, joins words with a dash, drops punctuation", 0.02, 300, ""

    monkeypatch.setattr(BarracksWorker, "work_runner", staticmethod(work))
    monkeypatch.setattr(BarracksWorker, "steward_runner", Steward())
    spec = {"id": "p", "first": "p", "last": "p", "back_events": ["pool.done", "pool.failed"], "back_filter": {},
            "about": "Agent pool", "roads": [],
            "buildings": [{"id": "p", "type": "barracks", "title": "Pool", "config": {"worktrees": False, "plan": False}}]}
    c = lab_cases.to_case(lab_cases.new_case("Slugify", "Write slugify(text)", "p", ["dash"]), "Agent pool", True, "quality")
    report, _ = building_bench.run(tmp_path, c, chain=spec, bare_runner=lambda *a: ("No idea.", 0.0, 0, ""),
                                   judge_runner=lambda prompt: '{"a": 7, "b": 7}')
    assert report.building.error == "" and report.building.passed is True
    assert report.bare.passed is False
    assert report.building.score == 7.0 and report.bare.score == 7.0


def test_on_the_bench_s_tool_each_task_keeps_its_steward_s_tier(monkeypatch):
    # `--tool agy` with no tier: the steward's call goes to agy on the tier it picks for the task, never agy's default
    from orkcraft.core import bench_kits as code_kits
    from orkcraft.realm import builders, steward_models
    seen = []
    monkeypatch.setattr(builders, "runner_for", lambda tool, model=None: seen.append((tool, model)) or (lambda p, m=None: ("", 0)))

    class W:
        TYPE, building_id = "watchtower", "w"
        steward_pick = staticmethod(lambda use, setting="": steward_models.Pick("gemini-flash-low", "laborer", "level"))
    w = W()
    code_kits.on_tool(w, "agy", "")
    w.steward_runner("judge")
    code_kits.on_tool(w, "agy", "elder")
    w.steward_runner("judge")
    assert seen == [("agy", "laborer"), ("agy", "elder")]
