"""The MCP servers already connected to the operator's AI tools: their names, never their secrets.

The onboarding lists them (docs/design/gui-onboarding.md §4): the ones turned on go to the Town planner,
which gives each to the orks that need it and shows its glyph on their buildings. Read from where each
agent keeps them; a server named in several places is one row with every tool that has it.

    found(home, repo)        → [Server("github", "GitHub", ("claude", "codex"), "github"), …]

Only the server's name leaves its file: no command, no argument, no environment, no header, no URL —
those may hold a token (`--api-key …`, `Authorization: …`). Nothing is run and nothing is written.
"""
from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

# The services that have a glyph (gui/static/icons/services/): a server whose name holds one is drawn with it.
GLYPHS: tuple[str, ...] = ("github", "gitlab", "gmail", "jira", "confluence", "figma", "discord", "slack")
# What a server's name says, in plain words, when the name alone is a known service.
TITLES: dict[str, str] = {
    "github": "GitHub", "gitlab": "GitLab", "gmail": "Gmail", "jira": "Jira", "confluence": "Confluence",
    "atlassian": "Jira & Confluence", "figma": "Figma", "discord": "Discord", "slack": "Slack",
    "notion": "Notion", "linear": "Linear", "sentry": "Sentry", "amplitude": "Amplitude", "asana": "Asana",
    "gdrive": "Google Drive", "google_drive": "Google Drive", "postgres": "Postgres", "playwright": "Playwright",
}
NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


@dataclass(frozen=True)
class Server:
    id: str                      # the name as the agents know it, lower case
    title: str
    tools: tuple[str, ...]       # the AI tools it is connected in (realm/harnesses.py ids)
    glyph: str = ""              # a service with a glyph, or ""

    def to_dict(self) -> dict:
        return {"id": self.id, "title": self.title, "tools": list(self.tools), "glyph": self.glyph}


def _json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _toml(path: Path) -> dict:
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _names(block) -> list[str]:
    """The server names of an `mcpServers` / `mcp_servers` table, and nothing of what is in them."""
    if not isinstance(block, dict):
        return []
    return [n for n in block if isinstance(n, str) and NAME.match(n)]


def _claude(home: Path, repo: Path | None) -> list[str]:
    data = _json(home / ".claude.json")
    names = _names(data.get("mcpServers"))
    projects = data.get("projects")
    if repo is not None and isinstance(projects, dict):
        mine = projects.get(str(repo)) or projects.get(str(repo.resolve()))
        if isinstance(mine, dict):
            names += _names(mine.get("mcpServers"))
    if repo is not None:
        names += _names(_json(repo / ".mcp.json").get("mcpServers"))
    return names


def _codex(home: Path) -> list[str]:
    return _names(_toml(home / ".codex" / "config.toml").get("mcp_servers"))


def _agy(home: Path) -> list[str]:
    return _names(_json(home / ".gemini" / "settings.json").get("mcpServers"))


def _cursor(home: Path, repo: Path | None) -> list[str]:
    names = _names(_json(home / ".cursor" / "mcp.json").get("mcpServers"))
    return names + (_names(_json(repo / ".cursor" / "mcp.json").get("mcpServers")) if repo is not None else [])


def _pi(home: Path, repo: Path | None) -> list[str]:
    out = []
    for path in [home / ".pi" / "agent" / "mcp.json"] + ([repo / ".pi" / "mcp.json"] if repo is not None else []):
        data = _json(path)
        out += _names(data.get("mcpServers") or data.get("mcp_servers") or data.get("servers"))
    return out


def _hermes(home: Path) -> list[str]:
    """The keys right under `mcp_servers:` in Hermes' config.yaml, read as lines (no YAML library)."""
    try:
        lines = (home / ".hermes" / "config.yaml").read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    names, inside, step = [], False, None
    for line in lines:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line[0].isspace():
            inside = line.split("#")[0].strip() == "mcp_servers:"
            step = None
            continue
        if inside:
            indent = len(line) - len(line.lstrip())
            step = step or indent
            key = line.strip().split(":", 1)[0].strip("'\"")
            if indent == step and line.strip().endswith(":") and NAME.match(key):
                names.append(key)
    return names


def title_of(name: str) -> str:
    key = name.lower().replace("-", "_")
    if key in TITLES:
        return TITLES[key]
    for k, t in TITLES.items():
        if k in key:
            return t
    return name


def glyph_of(name: str) -> str:
    key = name.lower()
    return next((g for g in GLYPHS if g in key), "")


def found(home: Path | None = None, repo: Path | None = None) -> list[Server]:
    """Every MCP server the AI tools here know, once each, with the tools that have it."""
    home = Path.home() if home is None else home
    where: dict[str, list[str]] = {}
    for tool, names in (("claude", _claude(home, repo)), ("codex", _codex(home)), ("agy", _agy(home)),
                        ("hermes", _hermes(home)), ("pi", _pi(home, repo)), ("cursor", _cursor(home, repo))):
        for n in names:
            tools = where.setdefault(n.lower(), [])
            if tool not in tools:
                tools.append(tool)
    return [Server(n, title_of(n), tuple(t), glyph_of(n)) for n, t in sorted(where.items())]
