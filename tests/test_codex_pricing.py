"""🪙 Codex: `codex exec` runs and War Tent sessions priced from the model and the tokens
(docs/design/codex-limits.md §5.2). The prices below are made-up test numbers, not OpenAI's."""
from __future__ import annotations

import datetime as dt
import json
import threading
from pathlib import Path

import pytest

from orkcraft.realm import harnesses, jobs, roads
from orkcraft.sources import pricing, telemetry

FIXTURE = Path(__file__).parent / "fixtures" / "codex_exec.jsonl"
RESUMED = Path(__file__).parent / "fixtures" / "codex_exec_resumed.jsonl"
THREAD = "01a10872-003f-76b1-84f2-bc6657c93545"
M = 1_000_000

# $ / MTok — round numbers to check the arithmetic with
TEST_PRICE = pricing.OpenAIPrice(input=2, cached_input=0.5, output=10, cache_write=3,
                                 long_input=4, long_cached=1, long_output=20, long_from_tokens=100_000)


@pytest.fixture
def priced(monkeypatch):
    monkeypatch.setattr(pricing, "OPENAI_PRICES", {"gpt-6-luna": TEST_PRICE})
    monkeypatch.setenv("CODEX_HOME", "/nonexistent-codex-home")    # no config.toml model


def test_the_shipped_table_carries_its_source_and_date():
    """A price goes in only with the date a person read it on OpenAI's page; none has been yet."""
    assert pricing.OPENAI_PRICES_SOURCE.startswith("https://developers.openai.com/")
    assert not pricing.OPENAI_PRICES or pricing.OPENAI_PRICES_AS_OF
    assert pricing.codex_usage_cost("gpt-6-luna", {"input_tokens": M}) is None or pricing.OPENAI_PRICES


def test_codex_usage_cost_counts_cached_and_written_input_inside_the_input(priced):
    # openai/codex: 100 in = 40 cached + 60 written; reasoning is part of the output
    usage = {"input_tokens": 100 * M, "cached_input_tokens": 40 * M, "cache_write_input_tokens": 50 * M,
             "output_tokens": M, "reasoning_output_tokens": M}
    assert pricing.codex_usage_cost("gpt-6-luna", usage) == pytest.approx(10 * 2 + 40 * 0.5 + 50 * 3 + 10)
    assert pricing.codex_usage_cost("GPT-6-Luna", {"input_tokens": M}) == pytest.approx(2)
    assert pricing.codex_usage_cost("gpt-6-astra", usage) is None            # not in the table: unknown, never $0
    assert pricing.codex_usage_cost("", usage) is None
    assert pricing.codex_usage_cost("gpt-6-luna", {"input_tokens": 5, "cached_input_tokens": 9}) == pytest.approx(9 * 0.5 / M)


def test_long_context_prices_one_request_only(priced):
    big = {"input_tokens": 200_000, "output_tokens": 0}
    assert pricing.codex_usage_cost("gpt-6-luna", big, one_request=True) == pytest.approx(200_000 * 4 / M)
    assert pricing.codex_usage_cost("gpt-6-luna", big) == pytest.approx(200_000 * 2 / M)   # a run's total


def test_an_exec_run_is_priced_from_the_model_it_was_asked_for(priced):
    out = FIXTURE.read_text(encoding="utf-8")
    text, cost, tokens, _ = roads.result_of("codex", out, model="gpt-6-luna")
    assert text == "done" and tokens == 34612 + 121
    assert cost == pytest.approx(((34612 - 30080) * 2 + 30080 * 0.5 + 121 * 10) / M)
    assert roads.result_of("codex", out, model="laborer")[1] == pytest.approx(cost)   # a tier word: its model
    assert roads.result_of("codex", out)[1] is None                    # no model anywhere: unpriced
    assert roads.result_of("codex", out, model="gpt-6-astra")[1] is None


def test_without_a_model_the_one_in_codex_config_counts(priced, tmp_path, monkeypatch):
    home = tmp_path / "codex-home"
    home.mkdir()
    (home / "config.toml").write_text('model = "gpt-6-luna"\n[profiles.x]\nmodel = "gpt-6-astra"\n', encoding="utf-8")
    monkeypatch.setenv("CODEX_HOME", str(home))
    assert harnesses.codex_config_model() == "gpt-6-luna"
    assert roads.result_of("codex", FIXTURE.read_text(encoding="utf-8"))[1] is not None
    (home / "config.toml").write_text("model = [", encoding="utf-8")
    assert harnesses.codex_config_model() == ""


def test_a_resumed_run_is_priced_for_its_own_usage_only(priced):
    out = RESUMED.read_text(encoding="utf-8")
    before = {"input_tokens": 34612, "cached_input_tokens": 30080, "output_tokens": 121}
    _, cost, tokens, _ = roads.result_of("codex", out, before, "gpt-6-luna")
    assert tokens == 52450 - 34733
    fresh = (52000 - 41000) - (34612 - 30080)
    assert cost == pytest.approx((fresh * 2 + (41000 - 30080) * 0.5 + (450 - 121) * 10) / M)
    assert roads.result_of("codex", out, 34733, "gpt-6-luna")[1] is None   # only a count before: unpriced


def test_run_work_charges_a_priced_codex_worker(priced, tmp_path, monkeypatch):
    from tests.test_codex import fake_codex
    fake_codex(tmp_path, monkeypatch)                     # 10 in (8 cached), 2 out
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "none"))
    telemetry.reset_charges()
    _, cost, tokens, _ = jobs.run_work("codex", "do it", tmp_path, threading.Event(), model="gpt-6-luna",
                                       env={"ORKCRAFT_RUN": ""})
    assert tokens == 12 and cost == pytest.approx((2 * 2 + 8 * 0.5 + 2 * 10) / M)
    assert [c[1] for c in telemetry.charges(dt.datetime.min.replace(tzinfo=dt.timezone.utc))] == [pytest.approx(cost)]
    telemetry.reset_charges()


# -- the War Tent: a Codex session's rollout ------------------------------------------------------------

def _line(kind: str, payload: dict, ts: str) -> str:
    return json.dumps({"timestamp": ts, "type": kind, "payload": payload}) + "\n"


def _count(last: dict, running: int, ts: str) -> str:
    return _line("event_msg", {"type": "token_count", "info": {"last_token_usage": last,
                                                                "total_token_usage": {"total_tokens": running}}}, ts)


def test_a_codex_session_in_the_war_tent_is_metered(priced, tmp_path):
    repo = tmp_path / "repo"
    (repo / ".orkcraft").mkdir(parents=True)
    rollout = tmp_path / f"rollout-2026-10-05T09-00-00-{THREAD}.jsonl"
    one = {"input_tokens": 50_000, "cached_input_tokens": 0, "output_tokens": 0}   # short context: $0.10
    rollout.write_text(
        _line("turn_context", {"model": "gpt-6-luna"}, "2026-10-05T08:00:00Z")
        + _count(one, 1, "2026-10-05T08:00:01Z")                  # before this run: context yes, spend no
        + _count(one, 2, "2026-10-05T09:05:00Z")
        + _count(one, 2, "2026-10-05T09:05:01Z")                  # the same count again
        + _line("event_msg", {"type": "token_count", "info": None}, "2026-10-05T09:05:02Z"),
        encoding="utf-8")
    run_id = telemetry.new_run_id()
    (repo / ".orkcraft" / "sessions.jsonl").write_text(json.dumps(
        {"harness": "codex", "session": THREAD, "run": run_id, "terminal": "new:codex:1",
         "transcript": str(rollout)}) + "\n", encoding="utf-8")
    t = telemetry.Telemetry(repo, run_id, dt.datetime(2026, 10, 5, 9, 0, tzinfo=dt.timezone.utc))
    snap = t.refresh()
    assert snap.spent_usd == pytest.approx(0.1) and snap.unpriced == set()
    assert snap.model_by_terminal == {"new:codex:1": "gpt-6-luna"}
    assert snap.context_by_terminal == {"new:codex:1": 50_000}
    with rollout.open("a", encoding="utf-8") as f:
        f.write(_line("turn_context", {"model": "gpt-6-astra"}, "2026-10-05T09:06:00Z"))
        f.write(_count(one, 3, "2026-10-05T09:06:01Z"))
    snap = t.refresh()
    assert snap.spent_usd == pytest.approx(0.1) and snap.unpriced == {"gpt-6-astra"}   # no price: unpriced


def test_a_codex_session_without_a_rollout_stays_unpriced(tmp_path):
    repo = tmp_path / "repo"
    (repo / ".orkcraft").mkdir(parents=True)
    run_id = telemetry.new_run_id()
    (repo / ".orkcraft" / "sessions.jsonl").write_text(json.dumps(
        {"harness": "codex", "session": "th", "run": run_id, "terminal": "new:codex:1"}) + "\n", encoding="utf-8")
    assert telemetry.Telemetry(repo, run_id).refresh().unpriced == {"codex"}
