"""The Catapult's own MCP client, for a local (stdio) server you allowed it to start: no model.

    call(mcp.launch("slack", home, repo), "post_message", {"channel": "C01", "text": "…"}) → Called

It starts the server as your tool's config says (its `${VAR}` filled from the environment), says
hello (`initialize`), makes one `tools/call` and stops the server. JSON-RPC over stdin and stdout,
one message a line (the MCP stdio transport). 🛑 Stop all kills it.
"""
from __future__ import annotations

import json
import os
import queue
import re
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from orkcraft import __version__
from orkcraft.realm import halt
from orkcraft.realm.mcp import Launch

PROTOCOL = "2025-06-18"
CALL_TIMEOUT_S = 60


@dataclass
class Called:
    ok: bool
    answer: str = ""
    error: str = ""
    kind: str = ""                # "" ok, "path" the tool refused it, "other" the server itself


def expand(value: str, environ) -> str:
    """`${VAR}` and `${VAR:-default}` as Claude Code fills them in .mcp.json."""
    def one(m: re.Match) -> str:
        name, _, default = m.group(1).partition(":-")
        return str(environ.get(name, default))
    return re.sub(r"\$\{([^}]+)\}", one, value)


def _text(result: dict) -> str:
    parts = [str(b.get("text", "")) for b in result.get("content") or [] if isinstance(b, dict) and b.get("type") == "text"]
    if parts:
        return "\n".join(parts)
    if result.get("structuredContent") is not None:
        return json.dumps(result["structuredContent"], ensure_ascii=False)
    return ""


class _Pipe:
    def __init__(self, proc: subprocess.Popen) -> None:
        self.proc, self.lines, self.next_id = proc, queue.Queue(), 1
        threading.Thread(target=self._read, daemon=True, name="catapult-mcp-read").start()

    def _read(self) -> None:
        for line in self.proc.stdout:
            self.lines.put(line)
        self.lines.put(None)

    def send(self, message: dict) -> None:
        self.proc.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
        self.proc.stdin.flush()

    def ask(self, method: str, params: dict, deadline: float) -> dict:
        mid, self.next_id = self.next_id, self.next_id + 1
        self.send({"jsonrpc": "2.0", "id": mid, "method": method, "params": params})
        while True:
            left = deadline - time.monotonic()
            if left <= 0:
                raise TimeoutError(f"no answer to {method} within {CALL_TIMEOUT_S} s")
            try:
                line = self.lines.get(timeout=left)
            except queue.Empty:
                continue
            if line is None:
                raise ConnectionError("the server stopped")
            try:
                msg = json.loads(line)
            except ValueError:
                continue                                  # a server's own chatter on stdout
            if isinstance(msg, dict) and msg.get("id") == mid and "method" not in msg:
                return msg


def call(launch: Launch, tool: str, args: dict, cwd: Path | None = None, environ=None,
         timeout: float = CALL_TIMEOUT_S) -> Called:
    environ = dict(os.environ if environ is None else environ)
    env = {k: v for k, v in environ.items() if not k.startswith("ORKCRAFT_")}
    env.update({k: expand(v, environ) for k, v in launch.env})
    argv = [expand(launch.command, environ), *(expand(a, environ) for a in launch.args)]
    try:
        proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                text=True, encoding="utf-8", env=env, cwd=str(cwd) if cwd else None,
                                start_new_session=True)
    except OSError as e:
        return Called(False, error=f"{launch.server} did not start ({launch.command}): {e}"[:300], kind="other")
    deadline = time.monotonic() + timeout
    try:
        with halt.running(proc):
            pipe = _Pipe(proc)
            try:
                hello = pipe.ask("initialize", {"protocolVersion": PROTOCOL, "capabilities": {},
                                                "clientInfo": {"name": "orkcraft-catapult", "version": __version__}}, deadline)
                if "error" in hello:
                    return Called(False, error=f"{launch.server}: {hello['error'].get('message', 'no hello')}"[:300], kind="other")
                pipe.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
                answer = pipe.ask("tools/call", {"name": tool, "arguments": args}, deadline)
            except (TimeoutError, ConnectionError, BrokenPipeError, OSError) as e:
                return Called(False, error=f"{launch.server}: {e}"[:300], kind="other")
            finally:
                try:
                    proc.stdin.close()
                except OSError:
                    pass
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
    except halt.Halted:
        return Called(False, error="stopped by Stop all", kind="other")
    if "error" in answer:
        err = answer["error"] if isinstance(answer["error"], dict) else {}
        return Called(False, error=str(err.get("message") or "the call was refused")[:300], kind="path")
    result = answer.get("result") if isinstance(answer.get("result"), dict) else {}
    text = _text(result)
    if result.get("isError"):
        return Called(False, text, (text or "the tool refused the call")[:300], "path")
    return Called(True, text)
