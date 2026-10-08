"""The newest model of a family, asked of the tool (realm/model_families.py), and prices by family."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from orkcraft.realm import harnesses, model_families
from orkcraft.sources import pricing

AGY_LIST = """gemini-3.7-flash-high Gemini 3.7 Flash (High)
gemini-3.8-flash-high Gemini 3.8 Flash (High)
gemini-3.8-flash-low Gemini 3.8 Flash (Low)
gemini-3.10-flash-low-preview Gemini 3.10 Flash (Low, preview)
gemini-3.1-pro-high Gemini 3.1 Pro (High)
claude-opus-4-6-thinking Claude Opus 4.6 (Thinking)
"""


def fake_agy(tmp_path: Path, monkeypatch, listing: str | None = AGY_LIST) -> Path:
    """An `agy` on ORKCRAFT_AGY_BIN: `agy models` prints `listing` (fails when None) and counts its calls."""
    calls = tmp_path / "agy-calls"
    script = tmp_path / "agy"
    script.write_text(f"""#!{sys.executable}
import sys
open({str(calls)!r}, "a").write(" ".join(sys.argv[1:]) + "\\n")
listing = {listing!r}
if sys.argv[1:] == ["models"]:
    if listing is None:
        sys.exit(1)
    print(listing, end="")
""", encoding="utf-8")
    script.chmod(0o755)
    monkeypatch.setenv("ORKCRAFT_AGY_BIN", str(script))
    monkeypatch.delenv("ORKCRAFT_MODEL_LIST", raising=False)
    model_families.forget()
    return calls


def test_the_newest_of_a_family_by_its_version():
    models = ["gemini-3.7-flash-high", "gemini-3.10-flash-high", "gemini-3.8-flash-high", "gemini-3.10-flash-low",
              "gemini-3.11-flash-high-preview", "gemini-3.11-flash-high"]
    assert model_families.newest("gemini-flash-high", models) == "gemini-3.11-flash-high"   # a release over its preview
    assert model_families.newest("gpt-sol", ["gpt-6-sol", "gpt-6.1-sol", "gpt-5.6-sol", "gpt-6-astra"]) == "gpt-6.1-sol"
    assert model_families.newest("gpt-terra", ["gpt-6-sol"]) == ""
    assert model_families.is_family("gemini-pro-high") and not model_families.is_family("gemini-3.1-pro-high")
    assert not model_families.is_family("opus")                        # a tool's alias, not a family


def test_a_tools_list_is_read():
    assert model_families.parse_agy(AGY_LIST)[:2] == ["gemini-3.7-flash-high", "gemini-3.8-flash-high"]
    codex = json.dumps({"models": [{"slug": "gpt-6-astra", "visibility": "list"},
                                   {"slug": "gpt-daybreak-blue-latest", "visibility": "hide"}]})
    assert model_families.parse_codex(codex) == ["gpt-6-astra"]
    assert model_families.parse_codex("not json") == []


def test_a_run_names_the_newest_model_and_the_list_is_kept_a_day(tmp_path, monkeypatch):
    calls = fake_agy(tmp_path, monkeypatch)
    agy = harnesses.need("agy")
    argv = agy.ask("hi", tmp_path, "elder")
    assert argv[argv.index("--model") + 1] == "gemini-3.1-pro-high"
    argv = agy.ask("hi", tmp_path)                                       # its default family
    assert argv[argv.index("--model") + 1] == "gemini-3.8-flash-high"
    assert agy.pick("laborer") == "gemini-3.10-flash-low-preview"         # 3.10 is past 3.8, a preview too
    assert calls.read_text().splitlines() == ["models"]                  # asked once
    cached = json.loads(model_families.cache_file().read_text())["agy"]
    assert "gemini-3.8-flash-high" in cached["models"]

    model_families.forget()                                              # a new run of the app: the cache
    assert agy.pick("warrior") == "gemini-3.8-flash-high" and calls.read_text().count("models") == 1
    later = cached["at"] + model_families.TTL_S + 1
    assert model_families.listed("agy", [[str(tmp_path / "agy"), "models"]], model_families.parse_agy, now=later)
    assert calls.read_text().count("models") == 2                       # a day on: asked again


def test_no_list_no_model_flag(tmp_path, monkeypatch):
    fake_agy(tmp_path, monkeypatch, listing=None)
    argv = harnesses.need("agy").ask("hi", tmp_path, "elder")
    assert "--model" not in argv                                         # the tool's own default
    fake_agy(tmp_path, monkeypatch, listing="gemini-3.8-flash-low x\n")
    model_families.cache_file().unlink()
    assert "--model" not in harnesses.need("agy").ask("hi", tmp_path, "elder")   # no pro in the list
    monkeypatch.setenv("ORKCRAFT_CODEX_BIN", str(tmp_path / "no-such-codex"))
    assert "--model" not in harnesses.need("codex").read("hi", tmp_path, "elder")


def test_a_chosen_model_wins(tmp_path, monkeypatch):
    calls = fake_agy(tmp_path, monkeypatch)
    agy = harnesses.need("agy")
    for chosen in ("gemini-3.1-pro-low", "my-own-model"):               # an older scroll's version, a model of its own
        argv = agy.work("hi", tmp_path, chosen)
        assert argv[argv.index("--model") + 1] == chosen
    assert not calls.exists()                                            # nothing to resolve: never asked
    assert harnesses.need("claude").pick("elder") == "opus"              # Claude Code's alias: already the newest


def test_a_family_reads_with_the_version_it_runs_on(tmp_path, monkeypatch):
    fake_agy(tmp_path, monkeypatch)
    assert model_families.label("gemini-flash-high") == "Gemini Flash High"   # nothing listed yet
    harnesses.need("agy").pick("warrior")
    assert model_families.label("gemini-flash-high") == "Gemini Flash High (3.8)"
    assert model_families.label("gpt-astra") == "GPT Astra"
    assert model_families.label("gemini-3.1-pro-high") == "gemini-3.1-pro-high"


def test_an_api_call_names_a_model_even_without_a_list():
    assert model_families.for_api("gemini-flash-tts", ["gemini-3.9-flash-tts-preview", "gemini-3.1-flash-tts-preview"]) \
        == "gemini-3.9-flash-tts-preview"
    assert model_families.for_api("gemini-flash-tts") == model_families.FALLBACK["gemini-flash-tts"]
    assert model_families.for_api("gemini-2.5-flash-preview-tts") == "gemini-2.5-flash-preview-tts"


def test_a_price_by_family_when_the_version_is_not_in_the_table():
    assert pricing.price_for("claude-opus-5-7") == pricing.PRICES["claude-opus-5-5"]     # the nearest version
    assert pricing.price_for("claude-sonnet-4-7") == pricing.PRICES["claude-sonnet-4-6"]
    assert pricing.price_for("opus") == pricing.PRICES["claude-opus-5-5"]                # no version: the newest
    assert pricing.price_for("claude-haiku-4-5-20251001") == pricing.PRICES["claude-haiku-4-5"]
    assert pricing.price_for("claude-unknown-1") is None and pricing.price_for("gemini-3.8-flash") is None


def test_a_codex_price_by_family(monkeypatch):
    monkeypatch.setattr(pricing, "OPENAI_PRICES", {"gpt-6-luna": pricing.OpenAIPrice(2, 0.5, 10),
                                                   "gpt-5.6-luna": pricing.OpenAIPrice(1, 0.1, 5)})
    assert pricing.openai_price_for("gpt-6.2-luna") == pricing.OPENAI_PRICES["gpt-6-luna"]
    assert pricing.openai_price_for("gpt-luna") == pricing.OPENAI_PRICES["gpt-6-luna"]
    assert pricing.openai_price_for("gpt-6-astra") is None              # no astra priced: unknown, never $0
    assert pricing.codex_usage_cost("gpt-luna", {"input_tokens": 1_000_000}) == pytest.approx(2)
