"""What the operator does with results, read as 👍 / 👎: edits, Loot decisions, a Lake's files,
pull requests, Z, results nobody opened — weighted, so a quiet signal alone moves nothing."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from orkcraft import scroll as ts
from orkcraft.app import OrkcraftApp
from orkcraft.realm import barracks as bk
from orkcraft.realm import checkpoint, edits, evolution, feedback, gate, gitinfo, lake, masonry, optimize, pipes
from orkcraft.screens.typed.generator_view import GeneratorView

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


def test_a_result_nobody_opened_for_a_day(tmp_path: Path):
    feedback.await_view(tmp_path, "lake", "brief", "Monday brief")
    feedback.await_view(tmp_path, "vault", "digest", "Digest")
    assert feedback.viewed(tmp_path, "lake") == 1                            # opened: seen
    assert feedback.sweep_unseen(tmp_path) == []                             # not a day yet
    later = dt.datetime.now() + dt.timedelta(hours=25)
    [gone] = feedback.sweep_unseen(tmp_path, later)
    assert gone["by"] == "digest" and feedback.disliked(tmp_path, "digest") == 0.1
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


@pytest.mark.asyncio
async def test_what_the_person_does_in_a_loot_teaches_the_maker(fake_repo: Path, monkeypatch):
    spec = {"id": "gate", "title": "Docs Gate", "icon": "📦", "orc": {"name": "Quartermaster"}, "type": "loot",
            "config": {"review": "always", "max_rework": 1}}
    assert masonry.save_spec(fake_repo, spec) == []
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        monkeypatch.setattr(app.roads, "emit", lambda payload, meta=None: [])
        monkeypatch.setattr(app, "return_for_rework", lambda src, p: "camp")
        view = app.desktop.get_window("gate").query_one(GeneratorView)
        trail = (pipes.hop("pit"), pipes.hop("camp", "grub", "agent", outcome="done"))

        view.receive(cart("as it should be", trail, "A"), "Docs", "as it should be")
        view.accept_item(view.queue.open()[0])                              # as it was: a light 👍
        assert feedback.liked(fake_repo, "camp") == 0.34

        view.receive(cart(DAILY, trail, "B"), "Docs", DAILY)
        view.accept_item(view.queue.open()[0], DAILY.replace("Mood:", "Mood: fine"))   # only filled in: 👍
        assert feedback.liked(fake_repo, "camp") == 0.68 and feedback.disliked(fake_repo, "camp") == 0

        view.receive(cart(DAILY, trail, "C"), "Docs", DAILY)
        mine = DAILY.replace("## Plan", "## Today")
        view.accept_item(view.queue.open()[0], mine)                         # the format changed: 👎 + an example
        inc = feedback.incidents(fake_repo)[0]
        assert (inc.building, inc.source, inc.tag) == ("camp", "loot.reshaped", "format") and "+## Today" in inc.edit
        assert feedback.references(fake_repo, "camp", 1)[0]["value"] == mine     # what it should have been
        assert feedback.liked(fake_repo, "camp") == 0.68                     # the example weighs nothing

        view.receive(cart("garbage", trail, "D"), "Docs", "garbage")
        item = view.queue.open()[0]
        view.rework_item(item, "what came in was wrong: the ticket was empty", "inputs")
        inc = feedback.incidents(fake_repo)[0]
        assert (inc.building, inc.kind, inc.tag, inc.blamed) == ("camp", "inputs", "inputs", {"pit": 0.5})
        view.receive(cart("garbage 2", trail, "D"), "Docs", "garbage 2")
        assert view.rework_item(item, "still wrong") == gate.NEEDS_YOU    # max_rework 1: past the limit
        assert [i.source for i in feedback.incidents(fake_repo, 2)] == ["loot.needs_you", "loot.rework"]
        monkeypatch.setattr(view, "selected_item", lambda: item)
        view.action_drop()                                                   # d: thrown away
        assert feedback.incidents(fake_repo, 1)[0].source == "loot.dropped"


@pytest.mark.asyncio
async def test_the_rework_modal_picks_a_reason_and_a_note(fake_repo: Path):
    from orkcraft.screens.feedback_modal import ReworkModal
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        got = []
        app.push_screen(ReworkModal("↩ Send back"), got.append)
        await pilot.pause()
        await pilot.press("3")                                               # a chip, then the note
        await pilot.press(*"no headings")
        await pilot.press("enter")
        await pilot.pause()
        assert got == [("format", "wrong format or style: no headings")]


@pytest.mark.asyncio
async def test_a_cart_that_passes_and_stays_waits_to_be_opened(fake_repo: Path, monkeypatch):
    spec = {"id": "gate", "title": "Docs Gate", "icon": "📦", "orc": {"name": "Quartermaster"}, "type": "loot",
            "config": {"review": "never"}}
    assert masonry.save_spec(fake_repo, spec) == []
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        view = app.desktop.get_window("gate").query_one(GeneratorView)
        view.receive(cart("the digest", (pipes.hop("camp"),)), "Docs", "the digest")
        assert [r["by"] for r in feedback._views(fake_repo)] == ["camp"]
        app.set_focus_state("building", building_id="gate")                # the operator opens the Loot
        assert feedback._views(fake_repo) == []


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


@pytest.mark.asyncio
async def test_reshaping_an_ork_s_file_in_the_lake_is_a_dislike(fake_repo: Path, monkeypatch):
    from orkcraft.screens.typed.lake_view import LakeView
    spec = {"id": "insight", "title": "Lake", "icon": "🌊", "orc": {"name": "Seer"}, "type": "lake"}
    assert masonry.save_spec(fake_repo, spec) == []
    (fake_repo / "daily.md").write_text(DAILY)
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        view = app.desktop.get_window("insight").query_one(LakeView)
        monkeypatch.setattr(app.roads, "emit", lambda payload, meta=None: [])
        app.deliver_payload("insight", pipes.Payload(pipes.FILE, "daily.md", "brief", "mill.done", "Daily",
                                                     (pipes.hop("brief", "scribe", "agent"),)))
        for _ in range(40):
            await pilot.pause(0.05)
            if view.view is not None:
                break
        view.action_edit()
        editor = view.query_one("#lake-edit")
        editor.load_text(DAILY.replace("Mood:", "Mood: fine"))              # filled in: nothing said
        view.action_leave_edit()
        assert feedback.incidents(fake_repo) == []
        view.action_edit()
        editor.load_text(DAILY.replace("Mood:", "Mood: fine").replace("## Notes", "## Log"))
        view.action_leave_edit()
        [inc] = feedback.incidents(fake_repo)
        assert (inc.building, inc.source, inc.tag) == ("brief", "lake.reshaped", "format") and "## Log" in inc.edit


# -- pull requests and Z -------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_a_merged_pull_request_is_a_like_and_a_closed_one_a_dislike(fake_repo: Path):
    from orkcraft.screens.typed.pool_view import PoolView
    spec = {"id": "camp", "title": "Camp", "icon": "🏕", "orc": {"name": "Foreman"}, "type": "pool"}
    assert masonry.save_spec(fake_repo, spec) == []
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        view = app.desktop.get_window("camp").query_one(PoolView)
        view.state.tasks = [bk.PoolTask("t1", "Login page", "x", status="done", branch="pool/camp/t1",
                                        pr="https://github.com/o/r/pull/1", result="added it"),
                            bk.PoolTask("t2", "Logout", "x", status="done", branch="pool/camp/t2",
                                        pr="https://github.com/o/r/pull/2"),
                            bk.PoolTask("t3", "Docs", "x", status="done", branch="pool/camp/t3",
                                        pr="https://github.com/o/r/pull/3")]
        prs = {"pool/camp/t1": gitinfo.PR(1, "MERGED", "https://github.com/o/r/pull/1"),
               "pool/camp/t2": gitinfo.PR(2, "CLOSED", "https://github.com/o/r/pull/2"),
               "pool/camp/t3": gitinfo.PR(3, "OPEN", "https://github.com/o/r/pull/3")}
        assert view.settle_prs(prs) == 2 and view.settle_prs(prs) == 0        # each once
        assert feedback.liked(fake_repo, "camp") == 1.0 and feedback.disliked(fake_repo, "camp") == 1.0
        assert [t.pr_state for t in view.state.tasks] == ["MERGED", "CLOSED", ""]
        assert bk.Barracks(view.state_dir).tasks[0].pr_state == "MERGED"      # saved


@pytest.mark.asyncio
async def test_z_on_a_retro_s_change_is_a_dislike_and_on_your_own_is_not(fake_repo: Path, monkeypatch):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        monkeypatch.setattr(app, "revert_building", lambda bid: True)
        last = [checkpoint.Checkpoint("abc", "2026-10-05T06:20:00", "update(brief): settings: model", "brief")]
        monkeypatch.setattr(checkpoint, "history", lambda root, b=None, limit=50: last)
        assert app.revert_by_you("brief") and feedback.incidents(fake_repo) == []
        last[0] = checkpoint.Checkpoint("abd", "2026-10-05T06:21:00", "auto-improve(brief): steward: shrink", "brief")
        assert app.revert_by_you("brief")
        [inc] = feedback.incidents(fake_repo)
        assert (inc.building, inc.source, inc.weight) == ("brief", "revert", 1.0) and "auto-improve" in inc.note
