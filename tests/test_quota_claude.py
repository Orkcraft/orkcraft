"""
tests/test_claude_quota.py

Tests for orkcraft.quota.claude_quota using pytest.
All tests use fixtures or mock runners; real CLI commands are never executed.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from orkcraft.quota.claude_quota import get_claude_quota

_FIXTURES_DIR = Path(__file__).parent / "fixtures"
_CLAUDE_FIXTURE = _FIXTURES_DIR / "claude_usage.json"


def test_claude_quota_from_fixture() -> None:
    raw_fixture = _CLAUDE_FIXTURE.read_text(encoding="utf-8")
    # Simulate now around the fixture capture date: 2026-09-26 12:00:00 UTC
    simulated_now = datetime(2026, 9, 26, 12, 0, 0, tzinfo=timezone.utc)
    statuses = get_claude_quota(
        runner=lambda cmd, **kwargs: raw_fixture,
        now=simulated_now,
    )

    assert len(statuses) == 2
    for s in statuses:
        assert s.provider == "claude"
        assert s.error is None

    session = statuses[0]
    assert session.group == "session"
    assert session.window == "session"
    # 14% used -> 0.86 remaining
    assert session.remaining_fraction == pytest.approx(0.86, rel=1e-4)
    # Sep 26 at 4:20pm (Europe/Warsaw) -> 16:20 in UTC+2 (summer time) -> 14:20 UTC
    expected_session_reset = datetime(2026, 9, 26, 16, 20, tzinfo=ZoneInfo("Europe/Warsaw")).astimezone(timezone.utc)
    assert session.reset_time == expected_session_reset

    week = statuses[1]
    assert week.group == "week (all models)"
    assert week.window == "weekly"
    # 89% used -> 0.11 remaining
    assert week.remaining_fraction == pytest.approx(0.11, rel=1e-4)
    # Sep 30 at 1pm (Europe/Warsaw) -> 13:00 in Europe/Warsaw
    expected_week_reset = datetime(2026, 9, 30, 13, 0, tzinfo=ZoneInfo("Europe/Warsaw")).astimezone(timezone.utc)
    assert week.reset_time == expected_week_reset


def test_claude_multiple_week_lines() -> None:
    """Synthetic test: handles multiple week lines (including 'Sonnet only')."""
    result_text = (
        "Current session: 20% used · resets Sep 26 at 4:00pm (Europe/Warsaw)\n"
        "Current week (all models): 80% used · resets Sep 30 at 1pm (Europe/Warsaw)\n"
        "Current week (Sonnet only): 45% used · resets Sep 30 at 1pm (Europe/Warsaw)\n"
    )
    payload = json.dumps({"result": result_text})
    statuses = get_claude_quota(
        runner=lambda cmd, **kwargs: payload,
        now=datetime(2026, 9, 26, 12, 0, 0, tzinfo=timezone.utc),
    )

    assert len(statuses) == 3
    assert statuses[0].group == "session"
    assert statuses[0].remaining_fraction == pytest.approx(0.80)

    assert statuses[1].group == "week (all models)"
    assert statuses[1].window == "weekly"
    assert statuses[1].remaining_fraction == pytest.approx(0.20)

    assert statuses[2].group == "week (Sonnet only)"
    assert statuses[2].window == "weekly"
    assert statuses[2].remaining_fraction == pytest.approx(0.55)


def test_claude_year_inference_across_new_year() -> None:
    """
    Synthetic test: reset happens in January when now is end of December.
    The year must be inferred as the next year (not in the past).
    """
    result_text = "Current week (all models): 10% used · resets Jan 2 at 3pm (UTC)\n"
    payload = json.dumps({"result": result_text})
    now = datetime(2026, 12, 31, 22, 0, 0, tzinfo=timezone.utc)

    statuses = get_claude_quota(runner=lambda cmd, **kwargs: payload, now=now)
    assert len(statuses) == 1
    s = statuses[0]
    assert s.error is None
    assert s.reset_time == datetime(2027, 1, 2, 15, 0, 0, tzinfo=timezone.utc)


def test_claude_year_inference_recent_past_across_new_year() -> None:
    """
    Synthetic test: reset was 2 hours ago across New Year (not more than 1 day in past).
    """
    result_text = "Current session: 99% used · resets Dec 31 at 11:30pm (UTC)\n"
    payload = json.dumps({"result": result_text})
    now = datetime(2027, 1, 1, 1, 30, 0, tzinfo=timezone.utc)

    statuses = get_claude_quota(runner=lambda cmd, **kwargs: payload, now=now)
    assert len(statuses) == 1
    s = statuses[0]
    assert s.error is None
    assert s.reset_time == datetime(2026, 12, 31, 23, 30, 0, tzinfo=timezone.utc)


def test_claude_cli_not_found() -> None:
    def runner(cmd, **kwargs):
        raise FileNotFoundError("claude not found")

    statuses = get_claude_quota(runner=runner)
    assert len(statuses) == 1
    s = statuses[0]
    assert s.provider == "claude"
    assert s.error is not None
    assert "CLI not found" in s.error
    assert s.remaining_fraction is None


def test_claude_cli_timeout() -> None:
    def runner(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=30)

    statuses = get_claude_quota(runner=runner)
    assert len(statuses) == 1
    s = statuses[0]
    assert s.provider == "claude"
    assert s.error is not None
    assert "timed out" in s.error


def test_claude_cli_nonzero_exit() -> None:
    def runner(cmd, **kwargs):
        raise subprocess.CalledProcessError(returncode=127, cmd=cmd, stderr="Command not found")

    statuses = get_claude_quota(runner=runner)
    assert len(statuses) == 1
    s = statuses[0]
    assert s.provider == "claude"
    assert s.error is not None
    assert "exit 127" in s.error


def test_claude_garbage_json() -> None:
    statuses = get_claude_quota(runner=lambda cmd, **kwargs: "not json at all!")
    assert len(statuses) == 1
    s = statuses[0]
    assert s.provider == "claude"
    assert s.error is not None
    assert "Failed to parse JSON" in s.error


def test_claude_no_quota_lines_in_output() -> None:
    payload = json.dumps({"result": "Some general output without any quota information."})
    statuses = get_claude_quota(runner=lambda cmd, **kwargs: payload)
    assert len(statuses) == 1
    s = statuses[0]
    assert s.provider == "claude"
    assert s.error is not None
    assert "No quota lines found" in s.error


def test_claude_runner_receives_correct_args_and_temp_cwd() -> None:
    captured = {}

    def runner(cmd, timeout=None, cwd=None):
        captured["cmd"] = cmd
        captured["timeout"] = timeout
        captured["cwd"] = cwd
        return _CLAUDE_FIXTURE.read_text(encoding="utf-8")

    get_claude_quota(claude_bin="/custom/claude", timeout=25, runner=runner)
    assert captured["cmd"] == [
        "/custom/claude",
        "-p",
        "/usage",
        "--output-format",
        "json",
        "--no-session-persistence",
    ]
    assert captured["timeout"] == 25
    assert captured["cwd"] == tempfile.gettempdir()
