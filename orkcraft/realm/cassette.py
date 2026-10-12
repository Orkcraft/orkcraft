"""MCP cassettes for a Test bench's runs (docs/design/improve-buildings.md §5.2, stage 3b): the person's MCP servers
answered once and played back after, so both sides of a comparison see the same world and nothing outside is touched
or paid for twice.

A run's AI tool is started with an MCP configuration of the bench's only (`config`): every server the person has is
`orkcraft mcp-cassette --server <name>`, a stdio proxy (`proxy`). **Recording** (the set's first run), it starts the
real server (realm/mcp.py `launch`), passes each message both ways and writes every request with its answer to the
set's cassette. **Replaying** (every run after), it never starts the server: `initialize` and the lists are answered
from the cassette, a call by its method and arguments; one not in it is answered "not recorded" and noted.

The cassette stays on this machine (`<the bench's state>/cassettes/<set>.jsonl`): what the servers said may be the
person's. Only Claude Code takes a configuration of the bench's (`--strict-mcp-config`); the other tools run with
their own servers, as before.

    cassette.config(["github"], path, repo) → {"mcpServers": …}   cassette.mode(path) → "record" | "replay"
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import threading
from pathlib import Path
from typing import IO

BY_METHOD = ("initialize", "tools/list", "resources/list", "resources/templates/list", "prompts/list")
NOT_RECORDED = -32001
_VOLATILE = ("_meta", "progressToken", "clientInfo", "capabilities", "protocolVersion")


def key(method: str, params) -> str:
    """What a request is known by: its method and its arguments, never what changes from one run to the next."""
    if method in BY_METHOD:
        return method
    clean = {k: v for k, v in (params or {}).items() if k not in _VOLATILE} if isinstance(params, dict) else params
    return method + ":" + hashlib.sha256(json.dumps(clean, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:24]


def mode(path: Path) -> str:
    return "replay" if path.is_file() and path.stat().st_size > 0 else "record"


def config(servers: list[str], path: Path, repo: Path | None = None) -> dict:
    """The MCP configuration a run's AI tool gets: each server a cassette proxy of it."""
    args = lambda name: ["-m", "orkcraft", *(["--repo", str(repo)] if repo else []), "mcp-cassette",
                         "--server", name, "--cassette", str(path), "--mode", mode(path)]
    return {"mcpServers": {name: {"command": sys.executable, "args": args(name)} for name in servers}}


class Tape:
    """The cassette file: one recorded exchange a line ({server, key, method, result | error})."""

    def __init__(self, path: Path, server: str) -> None:
        self.path, self.server = path, server
        self.lock = threading.Lock()
        self.known: dict[str, dict] = {}
        if path.is_file():
            for line in path.read_text(encoding="utf-8").splitlines():
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                if isinstance(e, dict) and e.get("server") == server:
                    self.known.setdefault(e.get("key", ""), e)

    def get(self, method: str, params) -> dict | None:
        return self.known.get(key(method, params))

    def add(self, method: str, params, answer: dict) -> None:
        k = key(method, params)
        entry = {"server": self.server, "key": k, "method": method,
                 **({"error": answer["error"]} if "error" in answer else {"result": answer.get("result")})}
        with self.lock:
            if k in self.known:
                return
            self.known[k] = entry
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def missed(self, method: str, params) -> None:
        with self.lock, self.path.with_suffix(".missed").open("a", encoding="utf-8") as f:
            f.write(json.dumps({"server": self.server, "method": method, "params": params}, ensure_ascii=False) + "\n")


def _write(out: IO[str], msg: dict, lock: threading.Lock) -> None:
    with lock:
        out.write(json.dumps(msg, ensure_ascii=False) + "\n")
        out.flush()


def replay(tape: Tape, stdin: IO[str], stdout: IO[str]) -> None:
    """Answer every request from the cassette; the real server is never started."""
    lock = threading.Lock()
    for line in stdin:
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        if not isinstance(msg, dict) or "id" not in msg or "method" not in msg:
            continue                                     # a notification, or a client's answer: nothing to say
        got = tape.get(msg["method"], msg.get("params"))
        if got is None:
            tape.missed(msg["method"], msg.get("params"))
            _write(stdout, {"jsonrpc": "2.0", "id": msg["id"], "error": {
                "code": NOT_RECORDED, "message": f"not recorded in this case set's cassette ({tape.server})"}}, lock)
            continue
        answer = {"error": got["error"]} if "error" in got else {"result": got.get("result")}
        _write(stdout, {"jsonrpc": "2.0", "id": msg["id"], **answer}, lock)


def record(tape: Tape, command: list[str], env: dict, stdin: IO[str], stdout: IO[str]) -> int:
    """Pass every message both ways to the real server, and keep each request with its answer."""
    proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, env=env, bufsize=1)
    pending: dict = {}
    lock = threading.Lock()

    def back() -> None:
        for line in proc.stdout:
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            if isinstance(msg, dict) and "id" in msg and ("result" in msg or "error" in msg):
                asked = pending.pop(json.dumps(msg["id"]), None)
                if asked is not None:
                    tape.add(asked[0], asked[1], msg)
            _write(stdout, msg, lock)

    reader = threading.Thread(target=back, daemon=True)
    reader.start()
    for line in stdin:
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        if isinstance(msg, dict) and "id" in msg and "method" in msg:
            pending[json.dumps(msg["id"])] = (msg["method"], msg.get("params"))
        proc.stdin.write(json.dumps(msg, ensure_ascii=False) + "\n")
        proc.stdin.flush()
    proc.stdin.close()
    reader.join(5)
    return proc.wait(10)
