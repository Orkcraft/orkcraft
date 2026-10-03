"""The AI CLIs orkcraft can lead, as onboarding finds them (design: docs/design/onboarding.md).

    for t in tools.detect():                # blocking (a `--version` each): call from a worker thread
        t.id, t.found, t.version, t.logged_in, t.billing

Nothing here spends quota or reads a key: a CLI is looked up on PATH, asked for its version, and
its login is guessed from what it leaves on disk or in the environment. `logged_in` is None when
it cannot be told without a model call. `billing` is a guess the operator may override.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from orkcraft.sources.sessions import agy_bin, claude_bin

VERSION_TIMEOUT_S = 5


@dataclass(frozen=True)
class Tool:
    id: str
    title: str
    install: str           # how to get it, shown when it is missing
    login: str             # how to log in, shown when it is not
    available: bool = True  # False: listed as "coming soon"


TOOLS: tuple[Tool, ...] = (
    Tool("claude", "Claude Code", "npm i -g @anthropic-ai/claude-code", "claude  (then /login)"),
    Tool("agy", "Antigravity", "see antigravity.google", "agy login"),
    Tool("codex", "OpenAI Codex", "npm i -g @openai/codex", "codex login", available=False),
)


@dataclass
class ToolStatus:
    tool: Tool
    found: bool = False
    path: str = ""
    version: str = ""
    logged_in: bool | None = None
    billing: str = "subscription"     # the guess: "subscription" | "api"

    @property
    def id(self) -> str:
        return self.tool.id

    def summary(self) -> str:
        """One line for the onboarding list: found · version · login, or how to get it."""
        if not self.tool.available:
            return "coming soon"
        if not self.found:
            return f"not found — {self.tool.install}"
        parts = ["found"] + ([f"v{self.version}"] if self.version else [])
        if self.logged_in is False:
            parts.append(f"not logged in — {self.tool.login}")
        elif self.logged_in:
            parts.append("API key" if self.billing == "api" else "logged in")
        return " · ".join(parts)


def _bin(tool_id: str) -> str:
    return {"claude": claude_bin, "agy": agy_bin}.get(tool_id, lambda: tool_id)()


def _version(path: str, run: Callable) -> str:
    try:
        out = run([path, "--version"], capture_output=True, text=True, timeout=VERSION_TIMEOUT_S)
    except (OSError, subprocess.SubprocessError):
        return ""
    words = (out.stdout or "").split()
    return next((w.lstrip("v") for w in words if w[:1].isdigit() or (w[:1] == "v" and w[1:2].isdigit())), "")


def _claude_login(env: dict, home: Path) -> tuple[bool | None, str]:
    if env.get("ANTHROPIC_API_KEY"):
        return True, "api"
    if (home / ".claude" / ".credentials.json").is_file():
        return True, "subscription"
    try:
        data = json.loads((home / ".claude.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, "subscription"
    return (True if isinstance(data, dict) and data.get("oauthAccount") else None), "subscription"


def _agy_login(env: dict, home: Path) -> tuple[bool | None, str]:
    if env.get("GEMINI_API_KEY") or env.get("GOOGLE_API_KEY"):
        return True, "api"
    return None, "subscription"


def detect(which: Callable[[str], str | None] = shutil.which, run: Callable = subprocess.run,
           env: dict | None = None, home: Path | None = None) -> list[ToolStatus]:
    env = dict(os.environ) if env is None else env
    home = Path.home() if home is None else home
    out: list[ToolStatus] = []
    for tool in TOOLS:
        status = ToolStatus(tool)
        if tool.available and (path := which(_bin(tool.id))):
            status.found, status.path = True, path
            status.version = _version(path, run)
            login = {"claude": _claude_login, "agy": _agy_login}.get(tool.id)
            if login is not None:
                status.logged_in, status.billing = login(env, home)
        out.append(status)
    return out
