"""An AI tool that fails (realm/tool_errors.py, gui/failures.py): what kind of failure it is, the event on
the bus, and the toast's Switch to another installed tool, Retry and Details."""
from __future__ import annotations

import threading
from pathlib import Path

import pytest

from orkcraft import settings
from orkcraft.core import bus, runners
from orkcraft.gui.host import CommandError, Host
from orkcraft.realm import builders, checkpoint, roads, tool_errors
from orkcraft.realm.tool_errors import LIMIT, LOGIN, MISSING, NETWORK, OTHER, ToolError


@pytest.mark.parametrize("text, code, kind", [
    ("claude not found", None, MISSING),
    ("/bin/sh: 1: codex: command not found", 127, MISSING),
    ("anything", 127, MISSING),
    ("Invalid API key · Please run /login", 1, LOGIN),
    ("OAuth token has expired. Please obtain a new token or refresh your existing token.", 1, LOGIN),
    ("Error: 401 Unauthorized", 1, LOGIN),
    ("API Error: 429 {\"type\":\"rate_limit_error\"}", 1, LIMIT),
    ("API Error: 529 Overloaded", 1, LIMIT),
    ("usage limit reached", 1, LIMIT),
    ("request to https://api.anthropic.com failed, reason: getaddrinfo ENOTFOUND api.anthropic.com", 1, NETWORK),
    ("Error: connect ECONNREFUSED 127.0.0.1:443", 1, NETWORK),
    ("Traceback (most recent call last): KeyError: 'x'", 1, OTHER),
    ("", 1, OTHER),
])
def test_a_failure_is_classified_by_what_the_tool_said(text, code, kind):
    assert tool_errors.classify(text, code) == kind


def test_a_tool_error_keeps_its_old_line_and_its_whole_words():
    long = "429 rate limit " + "x" * 1000
    e = ToolError("claude", long, 1)
    assert isinstance(e, RuntimeError)                     # every caller that catches RuntimeError still does
    assert str(e).startswith("claude exited with 1: 429 rate limit") and len(str(e)) < 400
    assert e.kind == LIMIT and e.detail == long             # Details keeps it whole
    assert tool_errors.taken() is e and tool_errors.taken() is None


def _which(*found):
    return lambda name: f"/usr/bin/{name}" if name in found else None


def test_switch_is_offered_only_for_another_installed_tool():
    e = ToolError("claude", "API Error: 529 Overloaded", 1)
    r = tool_errors.report(e, ["claude", "codex"], "claude", "Recruiter", which=_which("claude", "codex", "pi"))
    assert r["title"] == "Claude Code hit an error"
    assert r["line"] == "Claude Code hit a usage limit or its service is overloaded."
    assert r["detail"] == "API Error: 529 Overloaded" and r["where"] == "Recruiter"
    assert [o["id"] for o in r["switch"]] == ["codex", "pi"]    # the ones on first; never the one that failed
    assert r["mark"] == "✻" and [o["mark"] for o in r["switch"]] == ["⌬", "π"]   # the harness icons the toast draws
    assert r["hint"] == ""


def test_with_no_other_tool_the_toast_says_how_to_get_one():
    e = ToolError("claude", "Invalid API key · Please run /login", 1)
    r = tool_errors.report(e, ["claude"], "claude", which=_which("claude"))
    assert r["switch"] == [] and r["kind"] == LOGIN
    assert r["hint"].startswith("No other AI tool is installed. To have one to switch to, install Antigravity")
    assert r["action"] == "Sign in again in a terminal: claude  (then /login)"


def test_a_tool_that_does_not_start_is_not_offered_and_a_pinned_one_is_changed_in_its_building():
    e = ToolError("codex", "boom", 1)
    r = tool_errors.report(e, ["claude", "codex"], "codex", which=_which("claude", "codex"), broken=["claude"])
    assert r["switch"] == []
    r = tool_errors.report(e, ["claude", "codex"], "claude", which=_which("claude", "codex"))
    assert r["switch"] == [] and "building's settings" in r["hint"] and not r["main"]


def _fake_tool(tmp_path: Path, name: str, said: str, code: int = 1) -> Path:
    bins = tmp_path / "bin"
    bins.mkdir(exist_ok=True)
    tool = bins / name
    tool.write_text(f"#!/bin/sh\necho '{said}' >&2\nexit {code}\n")
    tool.chmod(0o755)
    return tool


def test_a_failing_run_raises_a_tool_error_of_its_kind(tmp_path, monkeypatch):
    monkeypatch.setenv("ORKCRAFT_CLAUDE_BIN", str(_fake_tool(tmp_path, "claude", "API Error: 429 rate_limit_error")))
    with pytest.raises(ToolError) as caught:
        roads.run_agent("claude", "hi", tmp_path, {}, threading.Event())
    assert caught.value.kind == LIMIT and caught.value.code == 1
    with pytest.raises(ToolError) as caught:
        builders.ask("claude", "hi")
    assert caught.value.kind == LIMIT
    monkeypatch.setenv("ORKCRAFT_CLAUDE_BIN", str(tmp_path / "nowhere" / "claude"))
    with pytest.raises(ToolError) as caught:
        roads.run_agent("claude", "hi", tmp_path, {}, threading.Event())
    assert caught.value.kind == MISSING
    with pytest.raises(ToolError) as caught:
        builders.ask("claude", "hi")
    assert caught.value.kind == MISSING


# -- the GUI ---------------------------------------------------------------------------------------

def _host(repo: Path, tools_on=("claude", "codex")) -> Host:
    m = settings.load()
    for t in tools_on:
        m.tools[t] = settings.ToolChoice(enabled=True)
    m.main_tool = tools_on[0]
    settings.save(m)
    checkpoint.ensure(repo)
    return Host(repo, auto_commit=False)


def _wait_for(pred):
    import time
    for _ in range(100):
        if pred():
            return
        time.sleep(0.05)
    raise AssertionError("never happened")


def _on_path(monkeypatch, bins: Path) -> None:
    """Only the fake tools in `bins` are installed, whatever this machine has (git and the rest still run)."""
    monkeypatch.setattr(tool_errors.shutil, "which", lambda name: str(bins / name) if (bins / name).exists() else None)


@pytest.fixture
def installed(tmp_path, monkeypatch):
    """Claude Code that answers 429, and Codex on PATH (it answers, the Recruiter's way)."""
    _fake_tool(tmp_path, "claude", "API Error: 429 rate_limit_error")
    _fake_tool(tmp_path, "codex", "")
    _on_path(monkeypatch, tmp_path / "bin")
    return tmp_path / "bin"


def test_a_failed_job_says_it_on_the_bus_and_switch_retries_on_the_other_tool(fake_repo, installed, monkeypatch):
    used: list[str] = []

    def recruiter(prompt, model=None):        # the main tool as it is when the call runs, as builders.main_runner
        tool = builders.main_tool()
        used.append(tool)
        if tool == "claude":
            raise ToolError("claude", "API Error: 429 rate_limit_error", 1)
        raise RuntimeError("no answer in tests")
    monkeypatch.setattr(runners, "RECRUIT_RUNNER", recruiter)
    host = _host(fake_repo)
    events, toasts = [], []
    host.town.bus.subscribe(bus.TOOL_ERROR, events.append)
    host.on_toast = toasts.append
    jid = host.command("building.recruit_ask", {"id": "town_hall", "prompt": "show finished tasks"})
    _wait_for(lambda: events)
    e = events[0].data
    assert e["harness"] == "claude" and e["kind"] == LIMIT and e["retry"]
    assert [o["id"] for o in e["switch"]] == ["codex"]
    t = toasts[-1]
    assert t["severity"] == "error" and t["title"] == "Claude Code hit an error"
    assert t["tool"]["detail"] == "API Error: 429 rate_limit_error" and t["tool"]["switch"][0]["title"] == "Codex"
    assert host.console.jobs[jid]["state"] == "failed"

    out = host.command("tool_error.switch", {"to": "codex", "retry": e["retry"]})
    assert out == {"main": "codex", "retried": True}
    assert settings.load().main_tool == "codex"
    _wait_for(lambda: used == ["claude", "codex"])          # the same job ran again, on Codex
    with pytest.raises(CommandError):                       # a Retry runs once
        host.command("tool_error.retry", {"retry": e["retry"]})


def test_with_no_other_tool_installed_there_is_no_switch(fake_repo, tmp_path, monkeypatch):
    _fake_tool(tmp_path, "claude", "Invalid API key · Please run /login")
    _on_path(monkeypatch, tmp_path / "bin")
    monkeypatch.setattr(runners, "RECRUIT_RUNNER",
                        lambda prompt, model=None: (_ for _ in ()).throw(ToolError("claude", "Invalid API key", 1)))
    host = _host(fake_repo, ("claude",))
    toasts = []
    host.on_toast = toasts.append
    host.command("building.recruit_ask", {"id": "town_hall", "prompt": "show finished tasks"})
    _wait_for(lambda: toasts)
    tool = toasts[-1]["tool"]
    assert tool["switch"] == [] and tool["kind"] == LOGIN and tool["hint"].startswith("No other AI tool is installed")
    with pytest.raises(CommandError):
        host.command("tool_error.switch", {"to": "codex"})   # not installed: nothing changes
    assert settings.load().main_tool == "claude"


def test_a_road_handler_that_fails_on_its_tool_says_so_once(fake_repo, installed):
    host = _host(fake_repo)
    toasts = []
    host.on_toast = toasts.append
    run = roads.HandlerRun("town_hall", "crier", "agent", "r1", 0.0, outcome="error",
                           failure=ToolError("claude", "getaddrinfo ENOTFOUND api.anthropic.com", 1))
    from orkcraft.core import delivery
    delivery.ran(host.town, run)
    delivery.ran(host.town, run)                            # the same failure again: one toast, not a stream
    assert len(toasts) == 1
    tool = toasts[0]["tool"]
    assert tool["kind"] == NETWORK and not tool["retry"]          # a road run is not retried from here
    assert toasts[0]["message"].endswith("could not reach its service. Check the internet connection.")
