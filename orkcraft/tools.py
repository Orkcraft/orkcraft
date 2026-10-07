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
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from orkcraft.realm import harnesses

VERSION_TIMEOUT_S = 5
# The oldest agy the 🛡 Warder guards: `--mode` is honoured in `-p` runs and a project's
# `.agents/hooks.json` loads once the folder is trusted (docs/design/agy-guard.md).
AGY_WARDER_MIN = (1, 1, 12)


@dataclass(frozen=True)
class Tool:
    id: str
    title: str
    install: str           # how to get it, shown when it is missing
    login: str             # how to log in, shown when it is not
    available: bool = True  # False: listed as "coming soon"


TOOLS: tuple[Tool, ...] = tuple(Tool(h.id, h.title, h.install, h.login) for h in harnesses.REGISTRY.values())


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
    h = harnesses.get(tool_id)
    return h.bin if h else tool_id


def _version(path: str, run: Callable) -> str:
    try:
        out = run([path, "--version"], capture_output=True, text=True, timeout=VERSION_TIMEOUT_S)
    except (OSError, subprocess.SubprocessError):
        return ""
    words = (out.stdout or "").split()
    return next((w.lstrip("v") for w in words if w[:1].isdigit() or (w[:1] == "v" and w[1:2].isdigit())), "")


def version_tuple(version: str) -> tuple[int, ...] | None:
    """"1.2.17" (or "v1.2.17-beta") as (1, 2, 17); None when it holds no number."""
    m = re.match(r"v?(\d+(?:\.\d+)*)", (version or "").strip())
    return tuple(int(x) for x in m.group(1).split(".")) if m else None


def agy_guardable(version: str) -> bool:
    """Whether the 🛡 Warder can guard this agy: 1.1.12 or later. An unknown version cannot be."""
    v = version_tuple(version)
    return v is not None and v >= AGY_WARDER_MIN


def agy_version(which: Callable[[str], str | None] | None = None, run: Callable | None = None) -> str | None:
    """Blocking: the agy on PATH's version ("" when it does not say), or None when agy is not installed."""
    path = (which or shutil.which)(_bin("agy"))
    return None if not path else _version(path, run or subprocess.run)


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


def codex_login(path: str = "", run: Callable = subprocess.run, env: dict | None = None,
                home: Path | None = None) -> tuple[bool | None, str]:
    """(logged in, billing) of Codex as onboarding tells it: what ⏳ Limits asks before reading its windows."""
    return _codex_login(dict(os.environ) if env is None else env, Path.home() if home is None else home, path, run)


# Keys a provider bills by the token, as Hermes and pi read them from the environment.
_PROVIDER_KEYS = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY",
                  "XAI_API_KEY", "NOUS_API_KEY", "DEEPSEEK_API_KEY", "MISTRAL_API_KEY", "GROQ_API_KEY")


def _json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _hermes_login(env: dict, home: Path) -> tuple[bool | None, str]:
    """Hermes: an OAuth login (a subscription: Nous, ChatGPT, Claude, Copilot…) in `auth.json`, else a
    provider key in its `.env` or the environment. Only names are looked at, never values."""
    root = Path(env["HERMES_HOME"]) if env.get("HERMES_HOME") else home / ".hermes"
    if _json(root / "auth.json"):
        return True, "subscription"
    if any(env.get(k) for k in _PROVIDER_KEYS):
        return True, "api"
    try:
        names = {line.split("=", 1)[0].strip() for line in (root / ".env").read_text(encoding="utf-8").splitlines()
                 if "=" in line and line.split("=", 1)[1].strip()}
    except OSError:
        names = set()
    return (True, "api") if names & set(_PROVIDER_KEYS) else (None, "subscription")


def _pi_login(env: dict, home: Path) -> tuple[bool | None, str]:
    """pi: `auth.json` holds `{provider: {"type": "oauth" | "api_key"}}`; the environment's keys too."""
    root = Path(env["PI_CODING_AGENT_DIR"]) if env.get("PI_CODING_AGENT_DIR") else home / ".pi" / "agent"
    kinds = {str(v.get("type")) for v in _json(root / "auth.json").values() if isinstance(v, dict)}
    if "oauth" in kinds:
        return True, "subscription"
    if "api_key" in kinds or any(env.get(k) for k in _PROVIDER_KEYS):
        return True, "api"
    return None, "subscription"


def _cursor_login(env: dict, home: Path) -> tuple[bool | None, str]:
    """Cursor: the plan pays either way; a key in CURSOR_API_KEY, else the login file it keeps (Linux and
    Windows; macOS keeps it in the Keychain, so there it cannot be told)."""
    if env.get("CURSOR_API_KEY"):
        return True, "subscription"
    config = Path(env["XDG_CONFIG_HOME"]) if env.get("XDG_CONFIG_HOME") else home / ".config"
    for auth in (config / "cursor" / "auth.json", home / ".cursor" / "auth.json",
                 Path(env.get("APPDATA") or home / "AppData" / "Roaming") / "Cursor" / "auth.json"):
        if _json(auth).get("accessToken"):
            return True, "subscription"
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
            login = {"claude": _claude_login, "agy": _agy_login, "hermes": _hermes_login, "pi": _pi_login,
                     "cursor": _cursor_login, "codex": lambda e, h: _codex_login(e, h, path, run)}.get(tool.id)
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
