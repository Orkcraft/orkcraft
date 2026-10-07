"""Anonymous usage stats (core/usage.py, docs/usage-stats.md): off until the operator says yes, only
the listed events and properties, and the proxy (tools/usage-worker/) knows the same list."""
from __future__ import annotations

import json
import re
import urllib.error
from pathlib import Path

import pytest

from orkcraft import settings
from orkcraft.core import usage
from orkcraft.realm import catalog, growth

WORKER = Path(__file__).resolve().parents[1] / "tools" / "usage-worker" / "worker.js"


@pytest.fixture
def sharing(monkeypatch):
    """Usage stats allowed here (conftest turns them off), a proxy address, no CI."""
    for name in ("ORKCRAFT_NO_USAGE", "DO_NOT_TRACK", "CI", "ORKCRAFT_USAGE_DEBUG"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("ORKCRAFT_USAGE_URL", "https://usage.example/v1/events")


def _usage(sent: list, share: bool | None = True, demo: bool = False) -> usage.Usage:
    machine = settings.MachineSettings()
    if share is not None:
        usage.share(machine, share)
    return usage.Usage(machine, demo=demo, send=lambda url, data: sent.append((url, json.loads(data))))


def _flush(u: usage.Usage) -> None:
    u.flush(wait=5)


def test_nothing_is_sent_until_the_operator_says_yes(sharing):
    sent: list = []
    u = _usage(sent, share=None)
    assert u.should_ask() and not u.enabled()
    u.track("road_laid")
    _flush(u)
    assert sent == []


def test_a_yes_sends_only_the_listed_properties(sharing):
    sent: list = []
    u = _usage(sent)
    u.track("building_built", type="lake", title="My secret project", path="/home/me")
    u.track("building_built", type="../../etc")          # not a catalog type: the event goes, the value not
    u.track("prompt_typed", text="hello")                # not an event at all
    _flush(u)
    (url, body), = sent
    assert url == "https://usage.example/v1/events"
    assert [e["props"] for e in body["events"]] == [{"type": "lake"}, {}]
    assert re.fullmatch(r"[0-9a-f]{32}", body["install_id"]) and body["app_version"]
    assert "My secret project" not in json.dumps(body) and "/home/me" not in json.dumps(body)


@pytest.mark.parametrize("env", [{"DO_NOT_TRACK": "1"}, {"ORKCRAFT_NO_USAGE": "1"}, {"CI": "true"}])
def test_do_not_track_ci_and_the_switch_stop_it_whatever_was_answered(sharing, monkeypatch, env):
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    sent: list = []
    u = _usage(sent)
    assert usage.blocked() and not u.enabled() and not u.should_ask()
    u.track("road_laid")
    _flush(u)
    assert sent == []


def test_the_demo_and_a_build_without_a_proxy_send_nothing(sharing, monkeypatch):
    sent: list = []
    assert not _usage(sent, demo=True).enabled()
    monkeypatch.delenv("ORKCRAFT_USAGE_URL")
    monkeypatch.setattr(usage, "ENDPOINT", "")
    u = _usage(sent)
    assert not u.enabled() and not u.should_ask()


def test_debug_prints_the_batch_instead_of_sending_it(sharing, monkeypatch, capsys):
    monkeypatch.setenv("ORKCRAFT_USAGE_DEBUG", "1")
    sent: list = []
    u = _usage(sent)
    u.track("session_opened", harness="codex")
    _flush(u)
    assert sent == [] and '"harness": "codex"' in capsys.readouterr().err


def test_an_unreachable_proxy_keeps_the_batch_for_later_a_refusal_drops_it(sharing):
    def down(url, data):
        raise OSError("no network")

    u = _usage([])
    u._send = down
    u.track("road_laid")
    _flush(u)
    assert len(u._queue) == 1

    def refuses(url, data):
        raise urllib.error.HTTPError(url, 400, "bad", {}, None)

    u._send = refuses
    _flush(u)
    assert u._queue == []


def test_no_forgets_the_install_id_and_the_settings_keep_the_answer(tmp_path):
    m = settings.MachineSettings()
    assert m.usage is None
    usage.share(m, True)
    first = m.install_id
    file = tmp_path / "s.json"
    settings.save(m, file)
    again = settings.load(file)
    assert again.usage is True and again.install_id == first
    usage.share(again, False)
    assert again.install_id == "" and settings.MachineSettings.from_dict(again.to_dict()).usage is False


def test_counts_and_minutes_are_buckets():
    assert [usage.count(n) for n in (0, 1, 4, 9, 40)] == ["0", "1", "2-5", "6-10", "11+"]
    assert usage.minutes(60) == "<5" and usage.minutes(3600) == "30-120"


def test_the_proxy_knows_the_same_events_types_and_deeds():
    js = WORKER.read_text(encoding="utf-8")
    block = js[js.index("const EVENTS = {"):]
    block = block[:block.index("\n};")]
    assert set(re.findall(r"^\s+(\w+): \{", block, re.M)) == set(usage.EVENTS)
    listed = lambda name: set(re.findall(r'"(\w+)"', re.search(rf"const {name} = \[(.*?)\];", js, re.S).group(1)))
    assert listed("TYPES") == set(catalog.TYPES)
    assert listed("DEEDS") == {d.id for d in growth.DEEDS}
    assert listed("TOOLS") == set(settings.TOOLS)


def test_the_window_counts_a_road_and_a_building_and_asks_once(sharing, fake_repo):
    from orkcraft.gui.host import Host
    host = Host(fake_repo, auto_commit=False)
    assert host.snapshot()["usage_ask"] is True
    sent: list = []
    host.usage._send = lambda url, data: sent.append(json.loads(data))
    host.command("usage.share", {"share": True})
    assert host.snapshot()["usage_ask"] is False
    host.command("town.build", {"type": "forge"})
    host.command("halt")
    host.close()
    events = [e for b in sent for e in b["events"]]
    assert [e["event"] for e in events] == ["app_opened", "building_built", "halted", "app_closed"]
    assert events[1]["props"] == {"type": "forge"}
    assert set(events[0]["props"]) == {"face", "mode", "tools", "buildings", "roads"}
