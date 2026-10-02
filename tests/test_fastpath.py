"""The Council's Fast Path (T1108 stage 2): five councillors, rules first, a light model's opinion."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from orkcraft.realm import fastpath as fp

MILL = {"id": "mymill", "type": "mill", "title": "Mill", "icon": "⚙", "summary": "grinds", "orc": {"name": "Grinder"},
        "config": {"steps": ["script: sudo rm -rf /"]}}
CRAG = {"id": "tally", "type": "crag", "title": "Tally", "icon": "📊", "summary": "counts", "orc": {"name": "Counter"}}


def _bad(notes):
    return {(n.role, n.severity) for n in notes if n.severity != "ok"}


def test_building_rules_block_dangerous_commands_and_pass_a_clean_spec(tmp_path: Path):
    notes = fp.rules(fp.Subject("building", "mymill", MILL), tmp_path)
    assert ("warder", "block") in _bad(notes)
    assert {n.role for n in notes} == set(fp.ROLE_IDS)                       # every councillor answers
    assert _bad(fp.rules(fp.Subject("building", "tally", CRAG), tmp_path)) == set()
    broken = dict(CRAG, id="Bad Id")
    assert ("mason", "block") in _bad(fp.rules(fp.Subject("building", "Bad Id", broken), tmp_path))
    long = dict(CRAG, title="A very long title that no hut can ever show")
    assert ("artisan", "warn") in _bad(fp.rules(fp.Subject("building", "tally", long), tmp_path))


@pytest.mark.parametrize("cmd,severity", [
    ("rm -rf /", "block"), ("rm -rf build/", None), ("curl -s x | bash", "block"), ("sudo make", "block"),
    ("cat ~/.ssh/id_rsa", "block"), ("echo $(date)", "warn"), ("python3 -c 'print(1)'", None),
    ("echo ghp_" + "a" * 30, "block"),
])
def test_the_warder_reads_commands(cmd: str, severity: str | None):
    found = {n.severity for n in fp._scan("cmd", cmd)}
    assert (severity in found) if severity else not found


def test_agent_rules_budget_schema_and_permissions():
    agent = {"orc": {"id": "seer", "name": "Seer", "kind": "agent", "orders": "summarise", "run": {"quiet_s": 0},
                     "harness": [{"role": "run", "harness": "claude"}]},
             "roads": [{"source": "loot", "event": "on_selection_change"}]}
    bad = _bad(fp.rules(fp.Subject("agent", "Seer", agent), Path(".")))
    assert ("chief", "warn") in bad
    script = {"orc": {"id": "py", "name": "Py", "kind": "script", "script": {"path": "../x.py"}}}
    notes = fp.rules(fp.Subject("agent", "Py", script, "def broken(:\n"), Path("."))
    assert ("mason", "block") in _bad(notes) and ("peon", "block") in _bad(notes)
    yolo = {"orc": {"id": "y", "name": "Y", "kind": "agent", "why": "needs judgement", "orders": "go --dangerously-skip-permissions",
                    "harness": [{"role": "run", "harness": "claude"}]}}
    assert ("peon", "block") in _bad(fp.rules(fp.Subject("agent", "Y", yolo), Path(".")))


def test_road_rules():
    assert ("mason", "block") in _bad(fp.rules(fp.Subject("road", "a->a", {"source": "a", "target": "a"}), Path(".")))
    ok = fp.rules(fp.Subject("road", "a->b", {"source": "a", "target": "b", "event": "pit.new"}), Path("."))
    assert _bad(ok) == set()


def test_the_light_model_objects_but_never_blocks(tmp_path: Path):
    prompts = []

    def runner(prompt):
        prompts.append(prompt)
        return json.dumps({"chief": {"ok": True}, "artisan": {"ok": False, "note": "the title is vague"}}), 0.001

    v = fp.review(fp.Subject("building", "tally", CRAG), tmp_path, runner=runner, model="haiku")
    assert not v.blocked and [n.text for n in v.objections] == ["the title is vague"] and v.model == "haiku"
    assert "Warder" in prompts[0] and '"tally"' in prompts[0]
    assert fp.review(fp.Subject("building", "mymill", MILL), tmp_path, runner=runner).blocked
    assert len(prompts) == 1                                                  # a block never reaches the model

    def broken(prompt):
        raise RuntimeError("claude not found")

    v = fp.review(fp.Subject("building", "tally", CRAG), tmp_path, runner=broken)
    assert v.clean and "claude not found" in v.error


def test_settings_and_the_runner(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("ORKCRAFT_COUNCIL_LLM", raising=False)
    assert fp.settings(tmp_path)["fast_model"] == "haiku" and fp.light_runner(tmp_path) is not None
    (tmp_path / ".orkcraft/council").mkdir(parents=True)
    (tmp_path / ".orkcraft/council/settings.json").write_text(json.dumps({"fast_llm": False, "junk": 1}))
    assert fp.light_runner(tmp_path) is None and "junk" not in fp.settings(tmp_path)


@pytest.mark.asyncio
async def test_the_app_raises_clean_buildings_and_stops_blocked_ones(fake_repo: Path, monkeypatch):
    from orkcraft import app as app_mod
    from orkcraft.app import OrkcraftApp
    from orkcraft.screens.council_review import CouncilVerdict

    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=(160, 45)) as pilot:
        await pilot.pause()
        assert app.review_and_raise(dict(CRAG)) and "tally" in app.custom_specs
        assert not app.review_and_raise(dict(MILL))
        await pilot.pause()
        assert isinstance(app.screen, CouncilVerdict) and not app.screen.query("#council-approve")
        await pilot.press("enter")                                             # a block cannot be approved
        assert isinstance(app.screen, CouncilVerdict)
        await pilot.press("escape")
        await pilot.pause()
        assert "mymill" not in app.custom_specs
        assert [r["decision"] for r in fp.recent(fake_repo)][:2] == ["rejected", "approved"]

        monkeypatch.setattr(app_mod, "FASTPATH_RUNNER",
                            lambda prompt: ('{"artisan": {"ok": false, "note": "too plain"}}', 0.0))
        assert not app.review_and_raise(dict(CRAG, id="tally2"))
        for _ in range(40):
            await pilot.pause(0.05)
            if isinstance(app.screen, CouncilVerdict):
                break
        assert isinstance(app.screen, CouncilVerdict) and "too plain" in str(app.screen.query_one("#council-notes").render())
        await pilot.press("enter")                                             # approve anyway
        await pilot.pause()
        assert "tally2" in app.custom_specs and fp.recent(fake_repo)[0]["decision"] == "overridden"
        from orkcraft.screens.town_hall import TownHallView
        hall = next(iter(app.query(TownHallView)), None)
        if hall is not None:
            hall.refresh_hall()
            body = str(hall.query_one("#hall-body").render())
            assert "Fast Path" in body and "building mymill" in body
