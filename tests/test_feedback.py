"""👍 / 👎 on a steward (T1108 stage 7): references, the questionnaire, the cascade, incidents."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from orkcraft.realm import feedback


def _scroll(edges: dict[str, list[str]]):
    """target → sources, as roads."""
    return NS(buildings=[NS(id=t, roads=[NS(source=s) for s in srcs]) for t, srcs in edges.items()])


def test_broken_inputs_cascade_upstream_and_logic_stays_local(tmp_path: Path):
    scroll = _scroll({"report": ["mill"], "mill": ["pit", "watch"], "pit": ["drop"], "drop": ["far"]})
    assert feedback.suppliers(tmp_path, scroll, "report") == [("mill", 1), ("pit", 2), ("watch", 2), ("drop", 3)]
    assert feedback.blame(tmp_path, scroll, "report", "inputs") == {"mill": 1.0, "pit": 0.5, "watch": 0.5, "drop": 0.25}
    assert feedback.blame(tmp_path, scroll, "report", "logic") == {"report": 1.0}
    feedback.record_delivery(tmp_path, "report", "watch")                # the session: only watch delivered
    assert feedback.suppliers(tmp_path, scroll, "report") == [("watch", 1)]
    feedback.start_session(tmp_path)
    assert feedback.suppliers(tmp_path, scroll, "report")[0] == ("mill", 1)


def test_like_keeps_a_reference_and_dislike_writes_an_incident(tmp_path: Path):
    scroll = _scroll({"report": ["mill"]})
    assert feedback.like(tmp_path, "report") is None                     # nothing to rate yet
    feedback.record_output(tmp_path, "report", "workshop.done", "42 words")
    assert feedback.like(tmp_path, "report")["value"] == "42 words"
    assert feedback.references(tmp_path, "report")[0]["value"] == "42 words"
    inc = feedback.dislike(tmp_path, scroll, "report", "inputs", "the paste was cut")
    assert inc.blamed == {"mill": 1.0} and inc.output == "42 words" and inc.note == "the paste was cut"
    feedback.dislike(tmp_path, scroll, "report", "logic")
    s = feedback.scores(tmp_path)
    assert s["report"] == {"likes": 1, "dislikes": 2, "penalty": 1.0} and s["mill"]["penalty"] == 1.0
    assert [i.kind for i in feedback.incidents(tmp_path)] == ["logic", "inputs"]


@pytest.mark.asyncio
async def test_k_and_f_on_a_building(fake_repo: Path):
    from orkcraft.app import OrkcraftApp
    from orkcraft.screens.feedback_modal import DislikeModal

    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.pause()
        assert app.build_from_type("pit") and app.build_from_type("mill")
        app.add_road("mill", "pit", "pit.text", None)
        await pilot.pause()
        app.emit_typed("mill", "mill.done", "clean text")
        app.set_focus_state("building", building_id="mill")
        await pilot.pause()
        await pilot.press("K")
        await pilot.pause()
        assert feedback.scores(fake_repo)["mill"]["likes"] == 1
        await pilot.press("F")
        await pilot.pause()
        assert isinstance(app.screen, DislikeModal) and "The Pit −1" in " ".join(str(w.render()) for w in app.screen.query("Static"))
        await pilot.press("1")
        await pilot.pause()
        inc = feedback.incidents(fake_repo)[0]
        assert inc.building == "mill" and inc.kind == "inputs" and inc.blamed == {"pit": 1.0}
        assert inc.output == "clean text"


@pytest.mark.asyncio
async def test_the_rating_buttons_sit_beside_the_steward(fake_repo: Path):
    from orkcraft.app import OrkcraftApp
    from orkcraft.screens.feedback_modal import DislikeModal

    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.pause()
        assert app.build_from_type("mill")
        app.emit_typed("mill", "mill.done", "clean text")
        app.set_focus_state("building", building_id="mill")
        for _ in range(3):
            await pilot.pause()
        bar = app.screen.query_one("#roster-rate")
        assert bar.display
        await pilot.click("#rate-like")
        await pilot.pause()
        assert feedback.scores(fake_repo)["mill"]["likes"] == 1
        await pilot.click("#rate-dislike")
        await pilot.pause()
        assert isinstance(app.screen, DislikeModal)
        await pilot.press("escape")
        j = feedback.journal(fake_repo, "mill")
        assert j["results"] == 1 and j["likes"] == 1 and j["events"] == ["mill.done"]
        app.set_focus_state("neutral")
        await pilot.pause()
        assert not app.screen.query_one("#roster-rate").display


def test_liked_results_reach_the_prompts():
    from orkcraft.realm import roads, workshop
    from orkcraft import scroll as ts

    p = workshop.steward_prompt("say it", {"value": "x"}, "", ["42 words"])
    assert "RESULTS THE OPERATOR LIKED" in p and "42 words" in p
    orc = ts.OrcSpec("seer", "Seer", orders="go")
    b = NS(title="Hall")
    assert "42 words" in roads.agent_prompt(orc, b, [], "run", liked=["42 words"])
    assert "liked" not in roads.agent_prompt(orc, b, [], "run")
