"""Recorded answers played back (docs/design/check.md §11): a real check's model calls answer the buildings again, so
their whole way runs on every commit for free. tests/recordings/check-mail is a check of the mail scenario on Claude
(2026-10-11), its session ids and trails taken out."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from orkcraft import cli
from orkcraft.realm import call_log, check, harnesses, road_agents

RECORDED = Path(__file__).parent / "recordings" / "check-mail"


@pytest.fixture
def recorded(fake_repo, monkeypatch):
    def no_tool(*a, **k):
        raise AssertionError("an AI tool was started while answers are played back")

    monkeypatch.setenv("ORKCRAFT_COUNCIL_LLM", "1")       # the light model the Listener judges with, answered from the recording
    monkeypatch.setattr(road_agents, "run_proc", no_tool)
    from orkcraft.realm import builders
    monkeypatch.setattr(builders, "_call", no_tool)
    folder = fake_repo / check.DIR / "20261011-181700"
    shutil.copytree(RECORDED, folder)
    return folder


def test_the_mail_runs_come_out_as_they_did_on_their_recorded_answers(fake_repo, recorded, capsys):
    assert cli.main(["--repo", str(fake_repo), "check", "--replay", "20261011-181700"]) == 0
    out = capsys.readouterr().out
    assert "**SAME**: 3 of 3 runs came out as they did" in out and "customer-orders | run-1 | passed, 4 of 4 checks" in out


def test_a_building_that_now_sorts_differently_is_said_changed(fake_repo, recorded, capsys):
    call = recorded / "runs/mail/on-call/run-1/calls/building-001-claude--p.json"
    data = json.loads(call.read_text())
    envelope = json.loads(data["stdout"])
    said = json.loads(envelope["result"])
    said["keep"] = said["keep"][:2]                                         # now it lets the customer's mail go
    envelope["result"] = json.dumps(said)
    data["stdout"] = json.dumps(envelope)
    call.write_text(json.dumps(data))
    assert cli.main(["--repo", str(fake_repo), "check", "--replay", "20261011-181700"]) == 1
    out = capsys.readouterr().out
    assert "**CHANGED**" in out and "| on-call | run-1 |" in out


def test_a_call_with_no_answer_left_is_said(tmp_path):
    (tmp_path / "building-001-x.json").write_text(json.dumps({"line": {"mode": "ask", "purpose": "work"},
                                                              "prompt": "sort these", "stdout": "{}"}))
    with call_log.replaying(tmp_path):
        assert call_log.answer("ask", "sort those") == (0, "{}", "")
        with pytest.raises(call_log.Unrecorded):
            call_log.answer("ask", "sort more")
    assert call_log.answer("ask", "outside") is None                           # not played back: the tool is called
    assert harnesses.get("claude") is not None
