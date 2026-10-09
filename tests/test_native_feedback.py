"""What the operator does with results, read as 👍 / 👎: edits, Loot decisions, a Lake's files,
pull requests, Z, results nobody opened — weighted, so a quiet signal alone moves nothing."""
from __future__ import annotations

import datetime as dt
from pathlib import Path


from orkcraft import scroll as ts
from orkcraft.realm import edits, evolution, feedback, gitinfo, lake, optimize, pipes

SIZE = (200, 46)
DAILY = "# Daily 2026-10-05\n\n## Plan\n- \n\n## Notes\n\nMood:\n- [ ] standup\n"


# -- the edit ----------------------------------------------------------------------------------------

def test_filling_a_template_in_is_not_a_complaint_and_changing_its_format_is():
    filled = ("# Daily 2026-10-05\n\n## Plan\n- ship the signals\n- review the PR\n\n## Notes\nmet the team\n\n"
              "Mood: fine\n- [x] standup\n")
    e = edits.classify(DAILY, filled)
    assert (e.kind, e.removed) == (edits.FILLED, 0) and e.added >= 4
    renamed = DAILY.replace("## Plan", "## Today")
    e = edits.classify(DAILY, renamed)
    assert e.kind == edits.RESHAPED and e.headings == ["Plan"] and "format" in e.summary
    moved = "# Daily 2026-10-05\n\n## Notes\n\nMood:\n- [ ] standup\n\n## Plan\n- \n"
    assert edits.classify(DAILY, moved).kind == edits.RESHAPED
    brief = "\n".join(f"point {i} of the brief" for i in range(10))
    assert edits.classify(brief, brief.replace("point 3 of", "point three of")).kind == edits.TOUCHED
    assert edits.classify(brief, "something else\nentirely").kind == edits.REWRITTEN
    assert edits.classify(brief, brief + "\n\n").kind == edits.SAME


# -- weights -----------------------------------------------------------------------------------------

def test_quiet_signals_weigh_less_than_a_button(tmp_path: Path):
    feedback.signal(tmp_path, "brief", True, "loot.accepted", value="good brief")
    assert not feedback.rated_since(tmp_path, "2000-01-01")                  # 0.34: not a rating yet
    feedback.signal(tmp_path, "brief", False, "loot.rework", value="vague", note="incomplete: no dates",
                    tag="incomplete")
    feedback.signal(tmp_path, "brief", False, "loot.rework", value="vague again")
    assert feedback.disliked(tmp_path, "brief") == 1.0 and feedback.liked(tmp_path, "brief") == 0.34
    assert feedback.rated_since(tmp_path, "2000-01-01")
    row = feedback.scores(tmp_path)["brief"]
    assert (row["likes"], row["dislikes"]) == (0, 0)                         # the buttons were never pressed
    assert row["disliked"] == 1.0 and row["by"] == {"loot.accepted": 0.34, "loot.rework": -1.0}
    inc = feedback.incidents(tmp_path)[-1]
    assert (inc.source, inc.weight, inc.tag, inc.blamed) == ("loot.rework", 0.5, "incomplete", {"brief": 0.5})
    feedback.like(tmp_path, "brief", {"event": "x", "value": "v"})
    assert feedback.scores(tmp_path)["brief"]["by"]["explicit"] == 1.0


def test_broken_inputs_are_blamed_along_the_cart_s_own_trail():
    trail = (pipes.hop("pit"), pipes.hop("mill"), pipes.hop("barracks"), pipes.hop("fire"))
    assert feedback.maker(trail, "x") == "fire" and feedback.maker((), "x") == "x"
    assert feedback.trail_blame(trail, "barracks", "logic") == {"barracks": 1.0}
    assert feedback.trail_blame(trail, "barracks", "inputs") == {"mill": 1.0, "pit": 0.5}
    assert feedback.trail_blame((), "barracks", "inputs") == {"barracks": 1.0}     # nobody before it
    assert feedback.reason_tag("what came in was wrong: the ticket was empty") == ("inputs", "inputs")
    assert feedback.reason_tag("meh") == ("", "logic")


def test_broken_inputs_weigh_on_the_suppliers_not_on_the_building(tmp_path: Path):
    trail = (pipes.hop("pit"), pipes.hop("mill"), pipes.hop("brief"))
    feedback.signal(tmp_path, "brief", False, "loot.rework", value="x", kind="inputs",
                    blamed=feedback.trail_blame(trail, "brief", "inputs"))
    assert feedback.disliked(tmp_path, "brief") == 0                         # it passed on what it got
    assert (feedback.disliked(tmp_path, "mill"), feedback.disliked(tmp_path, "pit")) == (0.5, 0.25)
    assert [i.building for i in feedback.blaming(tmp_path, "mill")] == ["brief"]
    assert feedback.scores(tmp_path)["mill"]["by"] == {"loot.rework": -0.5}
    feedback.dislike(tmp_path, None, "alone", "inputs")                      # nobody feeds it: it pays itself
    assert feedback.disliked(tmp_path, "alone") == 1.0
    # the mill's change on probation goes back when what it fed adds up to a 👎
    change = evolution.Change("mill", "shrink", "daily", "shorter prompt", ts="2000-01-01T00:00:00")
    assert evolution.verdict(tmp_path, change, dt.datetime(2000, 1, 2)) is None
    feedback.signal(tmp_path, "brief", False, "loot.rework", value="y", kind="inputs",
                    blamed=feedback.trail_blame(trail, "brief", "inputs"))
    assert "downstream at brief" in evolution.verdict(tmp_path, change, dt.datetime(2000, 1, 2))
    assert "fed it broken inputs" in optimize._incident_line(feedback.blaming(tmp_path, "mill")[0], "mill")


def test_the_maker_is_the_ork_that_wrote_not_the_one_that_reviewed_or_carried():
    trail = (pipes.hop("pit"), pipes.hop("camp", "grub", "agent"), pipes.hop("fire", "clan", "team"),
             pipes.hop("grinder", "miller", "script"))
    assert feedback.maker(trail) == "camp"
    assert feedback.maker((pipes.hop("grinder", "miller", "chain"),)) == "grinder"   # nobody wrote: the last hop
    assert feedback.maker(()) == "" and feedback.maker((), "pit") == "pit"
    assert feedback.trail_blame(trail, "camp", "inputs") == {"pit": 1.0}


def test_examples_put_corrections_and_likes_before_quiet_acceptances(tmp_path: Path):
    feedback.like(tmp_path, "brief", {"event": "x", "value": "liked by hand"})
    feedback.signal(tmp_path, "brief", True, "loot.reshaped", value="the operator's version", weight=0.0)
    feedback.signal(tmp_path, "brief", True, "pr.merged", value="merged")
    for n in range(5):
        feedback.signal(tmp_path, "brief", True, "loot.accepted", value=f"accepted {n}")
    assert [r["value"] for r in feedback.examples(tmp_path, "brief")] == \
        ["the operator's version", "liked by hand", "merged"]
    assert feedback.liked(tmp_path, "brief", strong=True) == 2.0              # 👍 and the merge shield it
    assert feedback.liked(tmp_path, "brief") == 3.7


def test_too_expensive_is_no_reason_to_spend_more_on_quality(tmp_path: Path):
    feedback.signal(tmp_path, "gem", False, "loot.rework", value="x", tag="cost", note="too expensive for what it is")
    feedback.signal(tmp_path, "gem", False, "loot.rework", value="x", tag="cost")
    assert feedback.disliked(tmp_path, "gem") == 1.0 and feedback.disliked(tmp_path, "gem", quality=True) == 0
    from orkcraft.realm import metrics
    metrics.record_run(tmp_path, "gem", "done", 0.01, 10, now=dt.datetime.now() - dt.timedelta(hours=1))
    assert optimize.leader(tmp_path, goals={"gem": "quality"}) is None     # 💎 is not enriched for costing much


def test_a_result_nobody_opened_for_a_day(tmp_path: Path):
    feedback.await_view(tmp_path, "lake", "brief", "Monday brief")
    feedback.await_view(tmp_path, "vault", "digest", "Digest")
    assert feedback.viewed(tmp_path, "lake") == 1                            # opened: seen
    assert feedback.sweep_unseen(tmp_path) == []                             # not a day yet
    later = dt.datetime.now() + dt.timedelta(hours=25)
    [gone] = feedback.sweep_unseen(tmp_path, later)
    assert gone["by"] == "digest" and feedback.incidents(tmp_path)[0].source == "usage.ignored"
    assert feedback.disliked(tmp_path, "digest") == 0                        # not opened is not bad: it is unused
    assert feedback.scores(tmp_path)["digest"]["by"] == {"usage.ignored": -0.1}
    assert "disliked" not in feedback.scores(tmp_path)["digest"]
    assert feedback.sweep_unseen(tmp_path, later) == []                      # counted once


def test_probation_takes_a_change_back_only_when_quiet_signals_add_up(tmp_path: Path):
    change = evolution.Change("brief", "shrink", "daily", "shorter prompt", ts="2000-01-01T00:00:00")
    feedback.signal(tmp_path, "brief", False, "lake.reshaped", value="x")
    assert evolution.verdict(tmp_path, change, dt.datetime(2000, 1, 2)) is None
    feedback.signal(tmp_path, "brief", False, "loot.rework", value="x", note="still too long")
    assert "loot.rework" in evolution.verdict(tmp_path, change, dt.datetime(2000, 1, 2))


# -- the Loot ----------------------------------------------------------------------------------------

def cart(value: str, trail=(), ref: str = "") -> pipes.Payload:
    return pipes.Payload(pipes.TEXT, value, "camp", "pool.done", "Docs", tuple(trail), ref)


# -- the Lake ----------------------------------------------------------------------------------------

def test_a_lake_judges_an_ork_s_file_against_the_ork_s_own_text(tmp_path: Path):
    f = tmp_path / "daily.md"
    f.write_text(DAILY)
    origins = lake.Origins(tmp_path / "state")
    origins.remember(str(f), "brief", "2026-10-05T09:00:00")
    filled = DAILY.replace("Mood:", "Mood: fine").replace("## Notes\n", "## Notes\nmy own note\n")
    who, e = origins.judge(str(f), filled)
    assert (who, e.kind) == ("brief", edits.FILLED)
    assert origins.judge(str(f), filled.replace("my own note\n", "")) is None    # the person's own line: not the ork's
    who, e = origins.judge(str(f), filled.replace("## Plan", "## Today"))
    assert e.kind == edits.RESHAPED
    assert origins.judge(str(f), filled.replace("## Plan", "## Today ")) is None  # judged once
    assert origins.judge(str(tmp_path / "other.md"), "x") is None                # not an ork's file
    assert lake.personal("---\nsubtype: personal\n---\n# me") and not lake.personal("# me")


def test_a_committed_file_an_ork_only_pointed_at_is_not_its_own(fake_repo: Path):
    import subprocess
    (fake_repo / "notes.md").write_text("# my notes\n")
    subprocess.run(["git", "-C", str(fake_repo), "add", "notes.md"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(fake_repo), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "n"],
                   check=True, capture_output=True)
    origins = lake.Origins(fake_repo / ".orkcraft" / "lake")
    origins.remember(str(fake_repo / "notes.md"), "brief", "2026-10-05T09:00:00")
    assert origins.judge(str(fake_repo / "notes.md"), "# Notes, renamed\n") is None
    (fake_repo / "fresh.md").write_text("# made by an ork\n")                # untracked: the ork's
    origins.remember(str(fake_repo / "fresh.md"), "brief", "2026-10-05T09:00:00")
    assert origins.judge(str(fake_repo / "fresh.md"), "# renamed\n")[1].kind == edits.REWRITTEN


# -- pull requests and Z -------------------------------------------------------------------------------


def test_gh_s_labels_are_read():
    import json as _json
    import subprocess
    row = {"number": 4, "state": "CLOSED", "headRefName": "b", "url": "u", "title": "t", "labels": [{"name": "Duplicate"}]}
    run = lambda *a, **k: subprocess.CompletedProcess(a, 0, _json.dumps([row]), "")
    assert gitinfo.pull_requests(Path("."), runner=run)["b"].labels == ("duplicate",)


# -- the cascade in the Building retro and the calibration --------------------------------------------

def test_a_supplier_that_keeps_breaking_inputs_is_due_whatever_it_spends(tmp_path: Path):
    from orkcraft.realm import metrics
    now = dt.datetime.now()
    metrics.record_run(tmp_path, "big", "done", 0.01, 10_000, now=now)
    metrics.record_run(tmp_path, "feeder", "done", 0.01, 10, now=now)             # far under MIN_SHARE
    feedback.record_output(tmp_path, "big", "mill.done", "fine")
    feedback.like(tmp_path, "big")
    assert optimize.leader(tmp_path, now, goals={"big": "thrift", "feeder": "thrift"}) is None
    trail = (pipes.hop("feeder", "w", "agent"), pipes.hop("writer", "w", "agent"))
    blamed = feedback.trail_blame(trail, "writer", "inputs")
    feedback.signal(tmp_path, "writer", False, "loot.rework", value="x", kind="inputs", blamed=blamed)
    assert optimize.leader(tmp_path, now, goals={"big": "thrift", "feeder": "thrift"}) is None   # 0.5: not yet
    feedback.signal(tmp_path, "writer", False, "loot.dropped", value="y", kind="inputs", blamed=blamed)
    cand = optimize.leader(tmp_path, now, goals={"big": "thrift", "feeder": "thrift"})
    assert (cand.building, cand.goal, cand.fed) == ("feeder", "balance", 1) and "broken inputs" in cand.reason
    assert "enrich" in cand.actions
    assert optimize.leader(tmp_path, now, goals={"big": "thrift"}) is None       # gone from the town


def test_calibration_measures_quiet_signals_against_the_buttons(tmp_path: Path):
    from orkcraft.realm import calibrate
    for i in range(6):
        feedback.signal(tmp_path, "a", True, "loot.accepted", value=f"ok {i}")
        feedback.signal(tmp_path, "a", False, "lake.touched", value=f"meh {i}")
    feedback.record_output(tmp_path, "a", "mill.done", "fine")
    feedback.like(tmp_path, "a")
    feedback.like(tmp_path, "a")
    feedback.signal(tmp_path, "b", False, "loot.dropped", value="z")                # no button near it
    rows = {r.source: r for r in calibrate.report(tmp_path)}
    acc, touched = rows["loot.accepted"], rows["lake.touched"]
    assert (acc.count, acc.matched, acc.agreed) == (6, 6, 6) and acc.suggested is not None and acc.suggested > 0.34
    assert (touched.matched, touched.agreed, touched.suggested) == (6, 0, calibrate.FLOOR)
    assert (rows["loot.dropped"].count, rows["loot.dropped"].matched, rows["loot.dropped"].suggested) == (1, 0, None)
    assert "usage.ignored" not in rows and "loot.accepted" in calibrate.render(list(rows.values()))
    assert calibrate.suggest(3, 4) is None and calibrate.suggest(50, 50) > calibrate.suggest(5, 5)
