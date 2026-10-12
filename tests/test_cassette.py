"""MCP cassettes (docs/design/improve-buildings.md §5.2, stage 3b): `orkcraft mcp-cassette` records a real stdio MCP
server's answers on a case set's first run and plays them back after, never starting it; a call not recorded is said
so and noted. A run's Claude Code gets the bench's configuration only."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

from orkcraft.realm import cassette, harnesses

SERVER = textwrap.dedent('''
    import json, sys
    calls = 0
    for line in sys.stdin:
        msg = json.loads(line)
        if "id" not in msg:
            continue
        m = msg["method"]
        if m == "initialize":
            result = {"protocolVersion": "2025-06-18", "serverInfo": {"name": "echo"}, "capabilities": {"tools": {}}}
        elif m == "tools/list":
            result = {"tools": [{"name": "echo", "inputSchema": {"type": "object"}}]}
        else:
            calls += 1
            result = {"content": [{"type": "text", "text": f"echo {msg['params']['arguments']['x']} (call {calls})"}]}
        print(json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": result}), flush=True)
''')


def _talk(repo: Path, tape: Path, mode: str, messages: list[dict], home: Path) -> list[dict]:
    env = {**os.environ, "HOME": str(home), "PYTHONPATH": str(Path(__file__).resolve().parents[1])}
    out = subprocess.run([sys.executable, "-m", "orkcraft", "--repo", str(repo), "mcp-cassette", "--server", "echo",
                          "--cassette", str(tape), "--mode", mode],
                         input="".join(json.dumps(m) + "\n" for m in messages), capture_output=True, text=True,
                         env=env, timeout=60)
    assert out.returncode == 0, out.stderr
    return [json.loads(line) for line in out.stdout.splitlines() if line.strip()]


def _call(n: int, x: int) -> dict:
    return {"jsonrpc": "2.0", "id": n, "method": "tools/call", "params": {"name": "echo", "arguments": {"x": x},
                                                                         "_meta": {"progressToken": n}}}


def test_a_server_is_recorded_once_and_played_back_without_it(tmp_path):
    repo, home = tmp_path / "project", tmp_path / "home"
    repo.mkdir()
    home.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    (tmp_path / "echo.py").write_text(SERVER, encoding="utf-8")
    (repo / ".mcp.json").write_text(json.dumps({"mcpServers": {"echo": {"command": sys.executable,
                                                                        "args": [str(tmp_path / "echo.py")]}}}))
    tape = tmp_path / "cassettes" / "set.jsonl"
    hello = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"clientInfo": {"name": "claude"}}},
             {"jsonrpc": "2.0", "method": "notifications/initialized"},
             {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}]
    assert cassette.mode(tape) == "record"
    first = _talk(repo, tape, "record", [*hello, _call(3, 1)], home)
    assert [m["id"] for m in first] == [1, 2, 3] and first[2]["result"]["content"][0]["text"] == "echo 1 (call 1)"
    assert cassette.mode(tape) == "replay" and len(tape.read_text().splitlines()) == 3
    (tmp_path / "echo.py").unlink()                                    # the server is gone: playback needs none
    again = _talk(repo, tape, "replay", [{**hello[0], "params": {"clientInfo": {"name": "claude", "version": "2"}}},
                                         *hello[1:], _call(7, 1), _call(8, 2)], home)
    assert again[0]["result"]["serverInfo"] == {"name": "echo"} and again[1]["result"]["tools"][0]["name"] == "echo"
    assert again[2] == {"jsonrpc": "2.0", "id": 7, "result": first[2]["result"]}       # the same answer, the same call
    assert again[3]["error"]["code"] == cassette.NOT_RECORDED
    assert json.loads(tape.with_suffix(".missed").read_text())["params"]["arguments"] == {"x": 2}


def test_a_runs_claude_gets_the_benchs_servers_only(tmp_path, monkeypatch):
    tape = tmp_path / "set.jsonl"
    conf = cassette.config(["github", "jira"], tape, tmp_path)
    assert set(conf["mcpServers"]) == {"github", "jira"}
    args = conf["mcpServers"]["github"]["args"]
    assert args[args.index("mcp-cassette") + 1:] == ["--server", "github", "--cassette", str(tape), "--mode", "record"]
    h = harnesses.get("claude")
    assert "--strict-mcp-config" not in h.read("hi", tmp_path, "", False)
    monkeypatch.setenv("ORKCRAFT_MCP_CONFIG", str(tmp_path / "mcp.json"))
    for cmd in (h.read("hi", tmp_path, "", False), h.work("hi", tmp_path, "", "")):
        assert cmd[-3:] == ["--mcp-config", str(tmp_path / "mcp.json"), "--strict-mcp-config"]
    assert cassette.key("tools/call", {"name": "a", "_meta": {"progressToken": 1}}) == \
        cassette.key("tools/call", {"name": "a", "_meta": {"progressToken": 2}})
