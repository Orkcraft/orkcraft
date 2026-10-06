"""The AI tools onboarding finds: the CLIs orkcraft can lead, and the others it only asks about
(design: docs/design/onboarding.md).

    for t in tools.detect():                # blocking (a `--version` each): call from a worker thread
        t.id, t.found, t.version, t.logged_in, t.billing
    tools.detect_others()                   # [Other(...)] installed: Cursor, Copilot, ChatGPT… (no process run)

Nothing here spends quota or keeps a key: a CLI is looked up on PATH, asked for its version, and
its login is guessed from what it leaves on disk or in the environment (Codex's `auth.json` is read
for which kind of login it holds, never for the key; failing that, `codex login status` tells).
`logged_in` is None when it cannot be told without a model call. `billing` is a guess the operator may override.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from orkcraft.sources.sessions import agy_bin, claude_bin, codex_bin

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
    Tool("codex", "OpenAI Codex", "npm i -g @openai/codex", "codex login"),
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
    return {"claude": claude_bin, "agy": agy_bin, "codex": codex_bin}.get(tool_id, lambda: tool_id)()


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


# Codex's auth modes (`AuthMode` in openai/codex codex-rs/protocol/src/auth.rs) by who pays.
_CODEX_API_MODES = frozenset({"apikey", "bedrockApiKey", "bedrockAccessKeys"})
_CODEX_PLAN_MODES = frozenset({"chatgpt", "chatgptAuthTokens", "agentIdentity", "personalAccessToken"})


def _codex_auth_billing(auth: Path) -> str:
    """"api" | "subscription" from `auth.json` (`AuthDotJson`), "" when it cannot be told. An API-key
    login (`codex login --with-api-key`) writes the same file as a ChatGPT one: its `auth_mode`, or
    for an older file what it holds (as Codex's `resolved_mode`), says which. Only the field names are
    looked at."""
    try:
        data = json.loads(auth.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    if not isinstance(data, dict):
        return ""
    mode = data.get("auth_mode")
    if isinstance(mode, str):
        return "api" if mode in _CODEX_API_MODES else "subscription" if mode in _CODEX_PLAN_MODES else ""
    if data.get("personal_access_token"):
        return "subscription"
    if data.get("bedrock_api_key") or data.get("bedrock_access_keys") or data.get("OPENAI_API_KEY"):
        return "api"
    return "subscription" if data.get("tokens") else ""


def _codex_login_status(path: str, run: Callable, env: dict) -> tuple[bool | None, str]:
    """`codex login status`: one line on stderr from the auth store, no network call, no model turn."""
    try:
        out = run([path, "login", "status"], capture_output=True, text=True, timeout=VERSION_TIMEOUT_S, env=env)
    except (OSError, subprocess.SubprocessError):
        return None, "subscription"
    said = f"{out.stderr or ''}\n{out.stdout or ''}"
    if "Not logged in" in said:
        return False, "subscription"
    if "Logged in using ChatGPT" in said or "access token" in said:     # also a personal one
        return True, "subscription"
    if "API key" in said or "AWS access keys" in said:
        return True, "api"
    return None, "subscription"


def _codex_login(env: dict, home: Path, path: str = "", run: Callable | None = None) -> tuple[bool | None, str]:
    if env.get("CODEX_API_KEY"):                       # `codex exec` honours it; OPENAI_API_KEY it does not
        return True, "api"
    codex_home = Path(env["CODEX_HOME"]) if env.get("CODEX_HOME") else home / ".codex"
    if billing := _codex_auth_billing(codex_home / "auth.json"):
        return True, billing
    if path and run is not None:                      # no file (a keyring login) or one it cannot read
        return _codex_login_status(path, run, env)
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
            login = {"claude": _claude_login, "agy": _agy_login,
                     "codex": lambda e, h: _codex_login(e, h, path, run)}.get(tool.id)
            if login is not None:
                status.logged_in, status.billing = login(env, home)
        out.append(status)
    return out


# -- the AI tools orkcraft does not lead, only asks the operator about ---------------------------------

@dataclass(frozen=True)
class Other:
    id: str
    title: str
    bins: tuple[str, ...] = ()            # on PATH
    paths: tuple[str, ...] = ()           # under the home folder (~) or /Applications; a glob is allowed


OTHERS: tuple[Other, ...] = (
    Other("cursor", "Cursor", ("cursor",), ("/Applications/Cursor.app", "~/.cursor", "~/AppData/Local/Programs/cursor")),
    Other("copilot", "GitHub Copilot", (), ("~/.vscode/extensions/github.copilot-*",
                                            "~/.config/github-copilot")),
    Other("chatgpt", "ChatGPT app", ("chatgpt",), ("/Applications/ChatGPT.app", "~/AppData/Local/Programs/ChatGPT")),
    Other("gemini", "Gemini CLI", ("gemini",), ("~/.gemini",)),
    Other("aider", "Aider", ("aider",), ()),
    Other("windsurf", "Windsurf", ("windsurf",), ("/Applications/Windsurf.app", "~/.codeium/windsurf")),
)


APPS = Path("/Applications")


def detect_others(which: Callable[[str], str | None] = shutil.which, home: Path | None = None,
                  apps: Path | None = None) -> list[Other]:
    """The other AI tools installed here: a binary on PATH or their folder on disk. Runs nothing.

    `home` stands for `~` and `apps` for `/Applications`, so a test never sees this machine's apps."""
    home = Path.home() if home is None else home
    apps = APPS if apps is None else apps
    found = []
    for o in OTHERS:
        hit = any(which(b) for b in o.bins)
        for raw in o.paths if not hit else ():
            p = Path(raw)
            if raw.startswith("~"):
                p = Path(raw.replace("~", str(home), 1))
            elif p.is_relative_to(APPS):
                p = apps / p.relative_to(APPS)
            if "*" in p.name:
                hit = p.parent.is_dir() and any(p.parent.glob(p.name))
            else:
                hit = p.exists()
            if hit:
                break
        if hit:
            found.append(o)
    return found
