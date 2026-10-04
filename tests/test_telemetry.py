"""🪙 / 🪵: prices from the official table, transcript metering, HUD and the budget gate."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

from orkcraft.sources import pricing, telemetry
from orkcraft.sources import transcripts as tr


def test_prices_match_the_published_table():
    # Spot checks against https://platform.claude.com/docs/en/about-claude/pricing (2026-09-29).
    assert pricing.price_for("claude-opus-5-5") == pricing.Price(4, 5, 8, 0.20, 20, fast_input=8, fast_output=40)
    assert pricing.price_for("claude-fable-5-1").cache_read == 0.25
    assert pricing.price_for("claude-sonnet-4-5-20250929").input == 3          # dated id
    assert pricing.price_for("claude-opus-4-5@20251101").output == 25          # Vertex spelling
    assert pricing.price_for("us.anthropic.claude-haiku-4-5-20251001-v1:0").input == 1   # Bedrock
    assert pricing.price_for("claude-opus-5-5[1m]").input == 4                 # Claude Code suffix
    assert pricing.price_for("claude-sonnet-4-0").input == 3                   # alias
    assert pricing.price_for("gemini-3.8-flash") is None
    assert pricing.price_for(None) is None
    # every write/read price is the documented multiple of the base input price
    for model, p in pricing.PRICES.items():
        assert p.cache_5m == pytest.approx(p.input * 1.25), model
        assert p.cache_1h == pytest.approx(p.input * 2), model


def test_usage_cost_cache_ttl_fast_and_geo():
    m = 1_000_000
    usage = {"input_tokens": m, "output_tokens": m, "cache_read_input_tokens": m,
             "cache_creation_input_tokens": 2 * m,
             "cache_creation": {"ephemeral_5m_input_tokens": m, "ephemeral_1h_input_tokens": m}}
    # Opus 5.5: 4 in + 20 out + 0.20 read + 5 (5m write) + 8 (1h write)
    assert pricing.usage_cost("claude-opus-5-5", usage) == pytest.approx(37.20)
    no_split = {"cache_creation_input_tokens": m}
    assert pricing.usage_cost("claude-sonnet-5-5", no_split) == pytest.approx(2.50)   # counts as 5-minute
    fast = {"input_tokens": m, "output_tokens": m, "cache_read_input_tokens": m, "speed": "fast"}
    assert pricing.usage_cost("claude-opus-5-5", fast) == pytest.approx(8 + 40 + 0.40)
    assert pricing.usage_cost("claude-opus-4-7", fast) == pytest.approx(5 + 25 + 0.50)  # no fast mode: standard
    geo = {"input_tokens": m, "inference_geo": "us"}
    assert pricing.usage_cost("claude-sonnet-4-6", geo) == pytest.approx(3.3)
    assert pricing.usage_cost("claude-sonnet-4-5", geo) == pytest.approx(3.0)            # pre-4.6: no multiplier
    assert pricing.usage_cost("gpt-9", {"input_tokens": m}) is None
    assert pricing.context_of({"input_tokens": 5, "cache_read_input_tokens": 90, "cache_creation_input_tokens": 10}) == 105


def _assistant(mid, model, usage, ts="2026-09-29T10:00:00Z"):
    return json.dumps({"type": "assistant", "timestamp": ts,
                       "message": {"id": mid, "model": model, "usage": usage, "content": []}}) + "\n"


def test_run_cost_and_last_turn_context(tmp_path: Path):
    path = tmp_path / "t.jsonl"
    u1 = {"input_tokens": 1000, "output_tokens": 100, "cache_read_input_tokens": 50_000}
    u2 = {"input_tokens": 2000, "output_tokens": 200, "cache_read_input_tokens": 90_000}
    path.write_text(_assistant("m1", "claude-opus-5-5", u1) + _assistant("m1", "claude-opus-5-5", u1)
                    + _assistant("m2", "claude-opus-5-5", u2)
                    + _assistant("m3", "<synthetic>", {"input_tokens": 0, "output_tokens": 0}), encoding="utf-8")
    run = tr.read_run(path)
    expected = (pricing.usage_cost("claude-opus-5-5", u1) + pricing.usage_cost("claude-opus-5-5", u2))
    assert run.cost == pytest.approx(expected)
    assert run.context_tokens == 0          # the synthetic last message read nothing
    path.write_text(_assistant("m1", "claude-opus-5-5", u1) + _assistant("m2", "claude-opus-5-5", u2), encoding="utf-8")
    assert tr.read_run(path).context_tokens == 92_000   # the last turn, not the 143k sum
    path.write_text(_assistant("x", "mystery-model", u1), encoding="utf-8")
    run = tr.read_run(path)
    assert run.cost is None and run.unpriced == {"mystery-model"}


def test_meter_counts_this_run_only_and_reads_incrementally(tmp_path: Path):
    repo = tmp_path / "repo"
    (repo / ".orkcraft").mkdir(parents=True)
    transcript = tmp_path / "s.jsonl"
    run_id = telemetry.new_run_id()
    started = dt.datetime(2026, 9, 29, 10, 0, tzinfo=dt.timezone.utc)
    u = {"input_tokens": 1_000_000, "output_tokens": 0, "cache_read_input_tokens": 0}
    transcript.write_text(
        _assistant("old", "claude-sonnet-5-5", u, ts="2026-09-29T09:00:00Z")   # resumed history: not this run
        + _assistant("new", "claude-sonnet-5-5", u, ts="2026-09-29T10:05:00Z"), encoding="utf-8")
    log = repo / ".orkcraft" / "sessions.jsonl"
    log.write_text(
        json.dumps({"harness": "claude", "session": "s", "run": run_id, "terminal": "new:claude:1",
                    "transcript": str(transcript)}) + "\n"
        + json.dumps({"harness": "claude", "session": "z", "run": "0" * 32, "terminal": "x",
                      "transcript": str(transcript)}) + "\n"                # another run
        + json.dumps({"harness": "agy", "session": "g", "run": run_id, "terminal": "new:agy:1"}) + "\n",
        encoding="utf-8")
    t = telemetry.Telemetry(repo, run_id, started)
    snap = t.refresh()
    assert snap.spent_usd == pytest.approx(2.0)          # one Sonnet 5.5 message, $2 / MTok
    assert snap.sessions == 1 and snap.unpriced == {"agy"}
    assert snap.context_by_terminal == {"new:claude:1": 1_000_000}
    with transcript.open("a", encoding="utf-8") as f:
        f.write(_assistant("more", "claude-sonnet-5-5", u, ts="2026-09-29T10:06:00Z"))
        f.write('{"type": "assistant", "partial')          # an unfinished line is left for later
    assert t.refresh().spent_usd == pytest.approx(4.0)
    assert t._meters[str(transcript)].offset < transcript.stat().st_size


def test_levels_and_units():
    assert telemetry.level(15.99, 20) == "ok" and telemetry.level(16, 20) == "warn"
    assert telemetry.level(20, 20) == "over" and telemetry.level(5, 0) == "ok"
    assert telemetry.fmt_tokens(131072) == "128k" and telemetry.fmt_tokens(512) == "512"


@pytest.mark.asyncio
async def test_hud_gold_lumber_and_the_budget_gate(fake_repo: Path):
    from orkcraft.app import OrkcraftApp
    from orkcraft.widgets.hud import Hud

    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=(200, 50)) as pilot:
        await pilot.pause()
        hud = app.screen.query_one("#hud", Hud)
        assert "$— / $20.00" in str(hud.render()) and "— / 128k" in str(hud.render())
        app.telemetry.refresh = lambda: telemetry.Snapshot(  # type: ignore[method-assign]
            spent_usd=21.5, sessions=1, context_by_terminal={"new:claude:1": 140_000})
        app.refresh_telemetry()
        app.refresh_roster()
        await pilot.pause()
        text = str(hud.render())
        assert "$21.50 / $20.00" in text and "136k / 128k" in text
        assert hud.resources.gold_level == "over" and hud.resources.lumber_level == "over"
        started = []
        app.chat.action_new_session = lambda harness: started.append(harness)  # type: ignore[method-assign]
        app.action_spawn_orc()
        assert started == []                                   # held: the treasury is empty
        assert app.gold_exhausted() is True


def test_hook_records_run_and_terminal(tmp_path, monkeypatch):
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "session_hook", Path(__file__).resolve().parents[1] / "orkcraft" / "hooks" / "session.py")
    hook = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hook)
    monkeypatch.setattr(hook, "LOG", tmp_path / "sessions.jsonl")
    run = "a" * 32
    e = hook.record("claude", {"session_id": "s"}, env={"ORKCRAFT_RUN": run, "ORKCRAFT_TERMINAL": "new:claude:1"})
    assert (e["run"], e["terminal"]) == (run, "new:claude:1")
    e = hook.record("claude", {"session_id": "s"}, env={"ORKCRAFT_RUN": "nope", "ORKCRAFT_TERMINAL": "x"})
    assert "run" not in e and "terminal" not in e
    e = hook.record("claude", {"session_id": "s"}, env={"ORKCRAFT_RUN": run, "ORKCRAFT_TERMINAL": "a b;rm"})
    assert e["run"] == run and "terminal" not in e


def test_model_calls_with_no_transcript_count_in_the_run(tmp_path: Path):
    telemetry.reset_charges()
    telemetry.charge(0.5, "before the run")
    meter = telemetry.Telemetry(tmp_path, "run1", started=dt.datetime.now().astimezone() + dt.timedelta(seconds=1))
    import time
    time.sleep(1.1)
    telemetry.charge(0.25, "claude -p haiku")
    telemetry.charge(0.10, "claude -p haiku")
    telemetry.charge(None, "agy agent")
    telemetry.charge(-1, "nonsense")
    snap = meter.refresh()
    assert snap.side_usd == pytest.approx(0.35) and snap.spent_usd == pytest.approx(0.35)
    assert snap.side_by_source == {"claude -p haiku": pytest.approx(0.35)} and "agy agent" in snap.unpriced
    assert telemetry.charged({"ORKCRAFT_RUN": "x"}) and not telemetry.charged({}) and not telemetry.charged(None)
    telemetry.reset_charges()


def test_the_light_calls_charge_the_ledger(monkeypatch):
    import subprocess
    from orkcraft.realm import builders
    telemetry.reset_charges()
    since = dt.datetime.now().astimezone()
    answer = json.dumps({"result": "ok", "total_cost_usd": 0.02})
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0, answer, ""))
    assert builders.claude_runner("hi", model="haiku") == ("ok", 0.02)
    assert [(usd, src) for _, usd, src in telemetry.charges(since)] == [(0.02, "claude -p haiku")]
    telemetry.reset_charges()
