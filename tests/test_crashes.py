"""Crash reports (core/crashes.py, docs/crash-reports.md): sent only after the usage stats' yes, only
where in Orkcraft's code it broke, each run a Sentry session; the proxy (tools/usage-worker/) checks
every field again and writes the Sentry envelope."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
from pathlib import Path

import pytest

from orkcraft import settings
from orkcraft.core import crashes, usage

WORKER = Path(__file__).resolve().parents[1] / "tools" / "usage-worker" / "worker.js"


@pytest.fixture
def sharing(monkeypatch):
    for name in ("ORKCRAFT_NO_USAGE", "DO_NOT_TRACK", "CI", "ORKCRAFT_USAGE_DEBUG"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("ORKCRAFT_USAGE_URL", "https://usage.example/v1/events")


def _reporter(sent: list, share: bool | None = True, demo: bool = False) -> crashes.Reporter:
    machine = settings.MachineSettings()
    if share is not None:
        usage.share(machine, share)
    return crashes.Reporter(machine, demo=demo, send=lambda url, data: sent.append((url, json.loads(data))))


def _boom(path: str = "/home/someone/secret-project/plan.md"):
    raise FileNotFoundError(f"[Errno 2] No such file or directory: '{path}'")


def _caught() -> BaseException:
    try:
        _boom()
    except Exception as e:
        return e
    raise AssertionError


def _wait(sent: list, n: int) -> None:
    for t in threading.enumerate():
        if t.name == "crash-report":
            t.join(5)
    assert len(sent) >= n, sent


def test_nothing_is_sent_without_a_yes_but_the_traceback_stays_here(sharing, tmp_path):
    sent: list = []
    r = _reporter(sent, share=None)
    r.capture(_caught(), "command")
    r.start()
    r.close()
    assert sent == []
    (kept,) = (tmp_path / "crashes").glob("crash-*.txt")
    assert "secret-project" in kept.read_text()                      # the full traceback, on this machine only


def test_a_report_says_where_in_orkcraft_it_broke_and_nothing_of_the_person(sharing):
    sent: list = []
    r = _reporter(sent)
    r.capture(_caught(), "command", command="town.build")
    _wait(sent, 1)
    (url, body), = sent
    assert url == "https://usage.example/v1/crash"
    (event,) = body["items"]
    assert event["type"] == "event" and event["where"] == "command" and event["command"] == "town.build"
    (exc,) = event["exceptions"]
    assert exc["type"] == "FileNotFoundError" and exc["value"] == "[Errno 2] No such file or directory: '…'"
    text = json.dumps(body)
    assert "secret-project" not in text and "someone" not in text and str(Path.home()) not in text
    assert all(f["file"] == "<other>" or not f["file"].startswith("/") for f in exc["frames"])
    assert body["install_id"] == r.machine.install_id


def test_orkcraft_frames_keep_their_path_in_the_package():
    f = crashes.frame(str(crashes.PACKAGE / "core" / "town.py"), "toast", 93)
    assert f == {"file": "orkcraft/core/town.py", "function": "toast", "line": 93, "in_app": True}
    assert crashes.frame("/home/me/project/build.py", "my_secret_function", 3) == \
        {"file": "<other>", "function": "?", "line": None, "in_app": False}
    lib = crashes.frame("/x/lib/python3.12/site-packages/websockets/server.py", "serve", 10)
    assert lib["file"] == "websockets/server.py" and not lib["in_app"]


@pytest.mark.parametrize("raw, said", [
    ("No such file: '/Users/ann/clients/acme.txt'", "No such file: '…'"),
    ("cannot open /var/folders/x/y.json now", "cannot open <path> now"),
    ("GET https://api.example.com/v1?token=abc failed", "GET <url> failed"),
    ("mail ann@acme.io bounced", "mail <email> bounced"),
    ('KeyError: "Acme launch plan"', "KeyError: '…'"),
    ("C:\\Users\\ann\\a.txt is locked", "<path> is locked"),
    ("list index out of range", "list index out of range"),
])
def test_scrub_takes_out_what_could_be_the_persons(raw, said):
    assert crashes.scrub(raw) == said


def test_the_same_error_goes_once_and_a_run_sends_a_few_at_most(sharing):
    sent: list = []
    r = _reporter(sent)
    e = _caught()
    for _ in range(5):
        r.capture(e, "clock")
    _wait(sent, 1)
    assert len(sent) == 1 and r.errors == 5
    for i in range(crashes.MAX_EVENTS + 5):
        r._event([{"type": "E", "value": "", "frames": [{"file": "orkcraft/x.py", "function": "f", "line": i,
                                                          "in_app": True}]}], "python", "clock", True, False, "")
    _wait(sent, crashes.MAX_EVENTS)
    assert len(sent) == crashes.MAX_EVENTS


def test_each_run_is_a_session_and_one_that_died_ends_as_abnormal(sharing, tmp_path):
    folder = tmp_path / "crashes"
    folder.mkdir()
    dead = _dead_pid()
    (folder / ("session-" + "a" * 32 + ".json")).write_text(json.dumps({"sid": "a" * 32, "started": 1.0, "pid": dead}))
    (folder / ("session-" + "b" * 32 + ".json")).write_text(json.dumps({"sid": "b" * 32, "started": 1.0,
                                                                         "pid": os.getpid()}))   # another window, alive
    sent: list = []
    r = _reporter(sent)
    r.start()
    _wait(sent, 2)
    items = [b["items"][0] for _, b in sent]
    assert [(i["sid"], i["status"], i["init"]) for i in items] == [("a" * 32, "abnormal", False), (r.sid, "ok", True)]
    assert (folder / ("session-" + "b" * 32 + ".json")).exists()
    r.crashed = True
    r.close()
    _wait(sent, 3)
    assert sent[-1][1]["items"][0]["status"] == "crashed"
    assert not (folder / f"session-{r.sid}.json").exists()


def _dead_pid() -> int:
    p = subprocess.Popen(["true"])
    p.wait()
    return p.pid


def test_an_error_on_a_thread_is_reported_and_the_hooks_go_with_the_reporter(sharing, monkeypatch):
    sent: list = []
    r = _reporter(sent)
    monkeypatch.setattr(threading, "excepthook", lambda args: None)     # the error this test raises on purpose
    before = threading.excepthook
    r.install()
    try:
        t = threading.Thread(target=_boom)
        t.start()
        t.join()
    finally:
        r.uninstall()
    assert threading.excepthook is before
    _wait(sent, 1)
    event = sent[0][1]["items"][0]
    assert event["where"] == "thread" and event["handled"] is False
    assert any(f["file"] == "tests/test_crashes.py" or f["function"] == "_boom" or f["file"] == "<other>"
               for f in event["exceptions"][0]["frames"])


def test_the_window_reports_its_errors_by_its_own_scripts(sharing, fake_repo):
    from orkcraft.gui.host import Host
    host = Host(fake_repo, auto_commit=False)
    try:
        sent: list = []
        host.crashes.machine.usage, host.crashes.machine.install_id = True, "0" * 32
        host.crashes._send = lambda url, data: sent.append(json.loads(data))
        host.command("crash.window", {"message": "TypeError: b.card is undefined for '/Users/ann/x'",
                                      "stack": "Hut@http://127.0.0.1:5000/static/js/hut.js:120:7\n"
                                               "render@http://127.0.0.1:5000/static/js/vendor/preact.js:1:9\n"
                                               "evil@file:///Users/ann/x.js:1:1"})
        _wait(sent, 1)
        event = sent[0]["items"][0]
        assert event["platform"] == "javascript" and event["where"] == "window"
        assert event["exceptions"][0]["type"] == "TypeError"
        assert event["exceptions"][0]["value"] == "b.card is undefined for '…'"
        assert [f["file"] for f in event["exceptions"][0]["frames"]] == ["static/js/vendor/preact.js", "static/js/hut.js"]
        assert "ann" not in json.dumps(sent)
    finally:
        host.close()


def test_a_broken_command_is_reported_with_its_name(sharing, fake_repo):
    from orkcraft.gui.server import Server
    from orkcraft.gui.host import Host
    host = Host(fake_repo, auto_commit=False)
    try:
        sent: list = []
        host.crashes.machine.usage, host.crashes.machine.install_id = True, "0" * 32
        host.crashes._send = lambda url, data: sent.append(json.loads(data))
        host.commands["town.build"] = lambda a: 1 / 0
        reply = Server(host)._handle(json.dumps({"t": "cmd", "id": 1, "name": "town.build", "args": {}}))
        assert reply["ok"] is False and "ZeroDivisionError" in reply["error"]
        _wait(sent, 1)
        event = sent[0]["items"][0]
        assert event["command"] == "town.build" and event["exceptions"][0]["type"] == "ZeroDivisionError"
        assert any(f["file"] == "orkcraft/gui/server.py" for f in event["exceptions"][0]["frames"])
    finally:
        host.close()


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_the_proxy_writes_a_sentry_envelope_of_only_what_it_checked(tmp_path):
    module = tmp_path / "worker.mjs"
    module.write_text(WORKER.read_text(encoding="utf-8"), encoding="utf-8")
    script = tmp_path / "run.mjs"
    script.write_text("""
import worker from "./worker.mjs";
const calls = [];
globalThis.fetch = async (url, init) => { calls.push({ url, init }); return new Response(null, { status: 200 }); };
const env = { SENTRY_DSN: "https://pubkey@o1.ingest.us.sentry.io/42" };
const body = { install_id: "0".repeat(32), app_version: "0.2.7", os: "darwin", python: "3.12", items: [
  { type: "event", event_id: "1".repeat(32), time: Date.now(), platform: "python", where: "command", handled: true,
    level: "error", face: "gui", environment: "production", command: "town.build",
    exceptions: [{ type: "KeyError", value: "'…'", frames: [
      { file: "orkcraft/gui/host.py", function: "command", line: 12, in_app: true },
      { file: "/Users/ann/x.py", function: "f", line: 1, in_app: true }] }] },
  { type: "session", sid: "2".repeat(32), init: true, status: "ok", started: Date.now(), duration: 0, errors: 0,
    environment: "production" },
  { type: "event", event_id: "nope", where: "command", exceptions: [] }] };
const res = await worker.fetch(new Request("https://w.example/v1/crash", { method: "POST",
  headers: { "User-Agent": "orkcraft/0.2.7", "Content-Type": "application/json" }, body: JSON.stringify(body) }), env);
const plain = await worker.fetch(new Request("https://w.example/v1/crash", { method: "POST",
  headers: { "User-Agent": "curl/8" }, body: "{}" }), env);
console.log(JSON.stringify({ status: res.status, refused: plain.status, calls: calls.map((c) => ({ url: c.url,
  auth: c.init.headers["X-Sentry-Auth"], body: c.init.body })) }));
""", encoding="utf-8")
    out = json.loads(subprocess.run(["node", str(script)], capture_output=True, text=True, check=True,
                                    timeout=30).stdout)
    assert out["status"] == 204 and out["refused"] == 403
    (call,) = out["calls"]
    assert call["url"] == "https://o1.ingest.us.sentry.io/api/42/envelope/"
    assert "sentry_key=pubkey" in call["auth"]
    lines = [json.loads(x) for x in call["body"].strip().split("\n")]
    assert [x.get("type") for x in lines[1::2]] == ["event", "session"]
    event, session = lines[2], lines[4]
    assert event["release"] == "orkcraft@0.2.7" and event["user"] == {"id": "0" * 32, "ip_address": None}
    assert [f["filename"] for f in event["exception"]["values"][0]["stacktrace"]["frames"]] == ["orkcraft/gui/host.py"]
    assert event["tags"]["command"] == "town.build" and event["exception"]["values"][0]["mechanism"]["type"] == "command"
    assert session["did"] == "0" * 32 and session["attrs"]["release"] == "orkcraft@0.2.7"
