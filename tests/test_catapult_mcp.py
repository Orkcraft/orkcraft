"""🎯 The Catapult in `mode: mcp`, end to end through the GUI host (docs/design/catapult-mcp.md): the first
shot carried by the tool that has the server, the path learned from it, the direct path proved and
used, a refused token holding the queue, a refused call carried once and learned again."""
from __future__ import annotations

import io
import json
import subprocess
import sys
import time
import urllib.error
from pathlib import Path

import pytest

from orkcraft import settings
from orkcraft.core import buildings
from orkcraft.core.workers.catapult import CatapultWorker
from orkcraft.gui.host import CommandError, Host
from orkcraft.realm import audit, catapult_mcp as cm, checkpoint, pipes


def wait(cond, seconds: float = 10.0) -> None:
    end = time.monotonic() + seconds
    while not cond():
        assert time.monotonic() < end, "timed out"
        time.sleep(0.02)


def _stream(name: str, args: dict, result: str = "ok", error: bool = False) -> str:
    events = [{"type": "system", "subtype": "init", "mcp_servers": [{"name": "slack", "status": "connected"}]},
              {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "t1", "name": name, "input": args}]}},
              {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t1",
                                                        "content": [{"type": "text", "text": result}], "is_error": error}]}},
              {"type": "result", "total_cost_usd": 0.001}]
    return "\n".join(json.dumps(e) for e in events)


class Carrier:
    """A fake Claude Code carrying: it posts the cart's notes to C01 (or does what `answer` says)."""

    def __init__(self) -> None:
        self.argv: list[list[str]] = []
        self.answer = None

    def __call__(self, argv, cwd, env):
        self.argv.append(argv)
        allow = argv[argv.index("--allowedTools") + 1]
        if self.answer:
            return subprocess.CompletedProcess(argv, 0, self.answer(argv), "")
        if allow == "mcp__slack":                        # a learning shot: it picks the tool itself
            cart = json.loads(argv[2].split("<cart>\n", 1)[1].split("\n</cart>")[0])
            return subprocess.CompletedProcess(argv, 0, _stream("mcp__slack__post_message",
                                                                {"channel_id": "C01", "text": cart["notes"]}), "")
        args = json.loads(argv[2].split("<arguments>\n", 1)[1].split("\n</arguments>")[0])
        return subprocess.CompletedProcess(argv, 0, _stream(allow, args), "")


class Net:
    def __init__(self) -> None:
        self.requests, self.answer, self.error = [], b'{"ok": true, "ts": "1"}', 0

    def __call__(self, req, timeout=None):
        self.requests.append(req)
        if self.error:
            raise urllib.error.HTTPError(req.full_url, self.error, "no", {}, io.BytesIO(b"{}"))
        return _Resp(self.answer)


class _Resp:
    def __init__(self, data: bytes) -> None:
        self.f, self.status = io.BytesIO(data), 200

    def __enter__(self):
        return self

    def __exit__(self, *a) -> None:
        pass

    def read(self, *a):
        return self.f.read(*a)


@pytest.fixture
def slack(fake_repo: Path, tmp_path: Path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    (home / ".claude.json").write_text(json.dumps({"mcpServers": {"slack": {"type": "http", "url": "https://mcp.slack.com"}}}))
    machine = settings.MachineSettings()
    machine.tools["claude"].enabled = True
    settings.save(machine)
    carrier, net = Carrier(), Net()
    monkeypatch.setattr(CatapultWorker, "carry_runner", staticmethod(carrier))
    monkeypatch.setattr(CatapultWorker, "opener", staticmethod(net))
    monkeypatch.setattr(CatapultWorker, "mcp_home", home)
    monkeypatch.setattr(CatapultWorker, "learn_runner", staticmethod(lambda p, m=None: ("{}", 0.0)))
    monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
    checkpoint.ensure(fake_repo)
    host = Host(fake_repo, auto_commit=False)
    spec = buildings.type_spec(host.town, "catapult")
    spec["config"] = {"mode": "mcp", "to": "slack", "goal": "post the release notes to #releases"}
    built = buildings.raise_spec(host.town, spec)
    return host, built.id, host.town.worker(built.id), carrier, net, monkeypatch


def act(host: Host, bid: str, name: str, **args):
    return host.command("act", {"id": bid, "act": name, "args": args})


def card(host: Host, bid: str) -> dict:
    return next(b for b in host.snapshot()["buildings"] if b["id"] == bid)["card"]


def cart(w, notes: str) -> None:
    w.receive(pipes.Payload(pipes.TEXT, json.dumps({"notes": notes}), "notes", "mill.done", "notes"), "", "")


def test_the_first_shot_is_carried_asked_and_learned(slack):
    host, bid, w, carrier, net, _ = slack
    cart(w, "v0.2: roofs")
    d = host.detail(bid)["data"]
    assert d["asking"] and "via Claude Code" in d["asking"]["title"] and "first shot" in d["asking"]["text"]
    assert d["mcp"]["track"] == "carrier" and d["mcp"]["carrier"] == "Claude Code" and not carrier.argv
    act(host, bid, "answer", yes=True)
    wait(lambda: not w.firing and w.shots)
    s = host.detail(bid)["data"]["shots"][0]
    assert s["ok"] and s["track"] == "carrier" and "via Claude Code" in s["url"]
    assert carrier.argv[0][carrier.argv[0].index("--allowedTools") + 1] == "mcp__slack"   # learning: the whole server
    route = cm.load(w.repo_root, bid)
    assert route["tool"] == "mcp__slack__post_message" and route["args"] == {"channel_id": "C01", "text": {"$": "notes"}}
    m = host.detail(bid)["data"]["mcp"]
    assert m["tool"] == "post_message" and [o["title"] for o in m["options"]] == ["Slack API", "Slack webhook"]
    assert m["options"][0]["missing"] == ["SLACK_BOT_TOKEN"] and not m["on"]
    cart(w, "v0.3: roads")                               # the same carrier, a learned call: no question
    wait(lambda: not w.firing and len(w.shots) == 2)
    allow = carrier.argv[1][carrier.argv[1].index("--allowedTools") + 1]
    assert allow == "mcp__slack__post_message" and '"v0.3: roads"' in carrier.argv[1][2] and not net.requests


def test_the_direct_path_is_proved_once_then_needs_no_model(slack):
    host, bid, w, carrier, net, mp = slack
    cart(w, "v0.2")
    act(host, bid, "answer", yes=True)
    wait(lambda: not w.firing and w.shots)
    assert act(host, bid, "use_direct", pick=0) is True
    assert host.detail(bid)["data"]["mcp"]["track"] == "carrier"           # its token is not set yet
    mp.setenv("SLACK_BOT_TOKEN", "xoxb-1")
    act(host, bid, "dry_run")
    dry = host.detail(bid)["data"]["shots"][0]
    assert dry["dry"] and "Slack API" in dry["answer"] and "the proof" in dry["answer"] and "xoxb" not in dry["answer"]
    cart(w, "v0.3")
    d = host.detail(bid)["data"]
    assert d["mcp"]["track"] == "direct" and d["asking"] and "Slack API" in d["asking"]["title"]   # proved once, asked
    act(host, bid, "answer", yes=True)
    wait(lambda: not w.firing and net.requests)
    assert json.loads(net.requests[0].data) == {"channel": "C01", "text": "v0.3"} and len(carrier.argv) == 1
    wait(lambda: cm.load(w.repo_root, bid).get("proven"))
    cart(w, "v0.4")                                                        # proved: no question, no model
    wait(lambda: len(net.requests) == 2 and not w.firing)
    assert host.detail(bid)["data"]["shots"][0]["track"] == "direct" and len(carrier.argv) == 1


def test_a_refused_token_holds_the_queue_and_a_refused_call_is_learned_again(slack):
    host, bid, w, carrier, net, mp = slack
    cart(w, "v0.2")
    act(host, bid, "answer", yes=True)
    wait(lambda: not w.firing and w.shots)
    act(host, bid, "use_direct", pick=0)
    mp.setenv("SLACK_BOT_TOKEN", "xoxb-1")
    route = cm.load(w.repo_root, bid)
    route["proven"] = True
    cm.save(w.repo_root, bid, route)
    net.answer = b'{"ok": false, "error": "token_revoked"}'
    cart(w, "v0.3")
    wait(lambda: w.login_needed)
    d = host.detail(bid)["data"]
    assert d["queued"] == 1 and "token_revoked" in d["login"] and card(host, bid)["line"] == "token refused"
    key, title, context, options = w.orders_alert()                       # the hut burns: it asks in Answers
    assert key == "mcp" and "token is refused" in title and options[0][0] == "1"
    net.answer = b'{"ok": true}'
    assert act(host, bid, "resume") is True
    assert w.orders_alert() is None
    wait(lambda: not w.firing and not len(w.queue) and len(net.requests) == 2 and host.detail(bid)["data"]["shots"][0]["ok"])
    assert not w.login_needed
    net.answer = b'{"ok": false, "error": "channel_not_found"}'          # the channel moved: carried once, learned
    carrier.answer = lambda argv: _stream("mcp__slack__post_message", {"channel_id": "C02", "text": "v0.4"})
    cart(w, "v0.4")
    wait(lambda: not w.firing and len(carrier.argv) == 2)
    wait(lambda: cm.load(w.repo_root, bid)["args"]["channel_id"] == "C02")
    route = cm.load(w.repo_root, bid)
    assert route["on"] and not route["proven"] and route["options"][0]["body"]["channel"] == "C02"


def test_no_carrier_means_the_shot_waits_and_says_why(slack):
    host, bid, w, carrier, net, _ = slack
    machine = settings.load(settings.path())
    machine.tools["claude"].enabled = False
    settings.save(machine)
    from orkcraft.realm import builders
    builders._SETTINGS.clear()
    cart(w, "v0.2")
    d = host.detail(bid)["data"]
    assert d["queued"] == 1 and "off" in d["mcp"]["waiting"] and not carrier.argv
    assert card(host, bid)["line"].startswith("waits")
    with pytest.raises(CommandError):
        act(host, bid, "use_direct", pick=0)                              # nothing learned yet


def test_keep_the_carrier_and_the_audit_asks_for_confirm(slack):
    host, bid, w, carrier, net, _ = slack
    cart(w, "v0.2")
    act(host, bid, "answer", yes=True)
    wait(lambda: not w.firing and w.shots)
    assert act(host, bid, "keep_carrier") is True and host.detail(bid)["data"]["mcp"]["kept"]
    findings = [f.text for f in audit._security(w.repo_root, host.town.custom_specs) if "slack" in f.text]
    assert any("unasked" in t for t in findings)


SERVER = r'''
import json, sys
for line in sys.stdin:
    msg = json.loads(line)
    if msg.get("method") == "initialize":
        print(json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": {"capabilities": {}}}), flush=True)
    elif msg.get("method") == "tools/call":
        a = msg["params"]["arguments"]
        print(json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": {"content": [{"type": "text", "text": "local " + a["text"]}]}}), flush=True)
'''


def test_a_local_server_you_allowed_needs_no_model(slack, tmp_path: Path):
    host, bid, w, carrier, net, _ = slack
    (tmp_path / "srv.py").write_text(SERVER)
    (w.mcp_home / ".claude.json").write_text(json.dumps({"mcpServers": {"slack": {"command": sys.executable,
                                                                                    "args": [str(tmp_path / "srv.py")]}}}))
    cart(w, "v0.2")
    act(host, bid, "answer", yes=True)
    wait(lambda: not w.firing and w.shots)
    m = host.detail(bid)["data"]["mcp"]
    assert m["launch"]["where"] == "~/.claude.json" and not m["local"]
    assert act(host, bid, "allow_local", on=True) is True
    cart(w, "v0.3")
    d = host.detail(bid)["data"]
    assert d["mcp"]["track"] == "local" and d["asking"]                   # the first local shot asks
    act(host, bid, "answer", yes=True)
    wait(lambda: not w.firing and len(w.shots) == 2)
    s = host.detail(bid)["data"]["shots"][0]
    assert s["ok"] and s["track"] == "local" and s["answer"] == "local v0.3" and len(carrier.argv) == 1
