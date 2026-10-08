"""Where each AI tool finds the Wiki's MCP server (docs/design/wiki-mcp.md): an entry of this Wiki's own,
`orkcraft-wiki-<building id>`, in the project's file each tool reads its MCP servers from.

    .mcp.json              Claude Code   {"mcpServers": {name: {command, args}}}
    .cursor/mcp.json       Cursor        the same shape
    .codex/config.toml     Codex         a [mcp_servers.<name>] table between two marker lines of ours

Only our entry is written or removed; a file left with nothing else is deleted. agy and Hermes read MCP
servers only from their global settings, and pi has none: the rules for AI tools tell them where the wiki
is. Pure module, no Textual.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

CLAUDE, CURSOR, CODEX = Path(".mcp.json"), Path(".cursor") / "mcp.json", Path(".codex") / "config.toml"


def name_of(building_id: str) -> str:
    return "orkcraft-wiki-" + (re.sub(r"[^\w-]+", "-", building_id).strip("-") or "wiki")


def files_for(tools: list[str]) -> list[Path]:
    on = set(tools) or {"claude"}
    return [f for t, f in (("claude", CLAUDE), ("codex", CODEX), ("cursor", CURSOR)) if t in on]


def _json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8") or "{}")
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _set_json(path: Path, name: str, entry: dict | None) -> bool:
    """Our entry in a JSON file's `mcpServers` set (or removed when None). Whether the file changed. A file
    that is not valid JSON is left alone."""
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8") or "{}")
        except ValueError:
            return False
        if not isinstance(data, dict):
            return False
    else:
        data = {}
    servers = data.get("mcpServers") if isinstance(data.get("mcpServers"), dict) else {}
    if (servers.get(name) == entry) if entry is not None else name not in servers:
        return False
    if entry is None:
        servers.pop(name, None)
    else:
        servers[name] = entry
    data["mcpServers"] = servers
    if not servers and set(data) == {"mcpServers"}:
        if path.exists():
            path.unlink()
        return True
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return True


def _marks(name: str) -> tuple[str, str]:
    return f"# >>> {name} (orkcraft's Wiki; removed with its rules)", f"# <<< {name}"


def toml_block(name: str, command: list[str]) -> str:
    begin, end = _marks(name)
    q = json.dumps                                     # a JSON string is a TOML basic string
    return "\n".join([begin, f"[mcp_servers.{name}]", f"command = {q(command[0])}",
                      f"args = [{', '.join(q(a) for a in command[1:])}]", end, ""])


def _without_block(text: str, name: str) -> str:
    begin, end = _marks(name)
    out, inside = [], False
    for line in text.splitlines(keepends=True):
        if line.strip() == begin:
            inside = True
        elif inside and line.strip() == end:
            inside = False
        elif not inside:
            out.append(line)
    return "".join(out)


def _set_toml(path: Path, name: str, command: list[str] | None) -> bool:
    old = path.read_text(encoding="utf-8") if path.exists() else ""
    rest = _without_block(old, name)
    if command is None:
        new = rest.rstrip("\n") + "\n" if rest.strip() else ""
    else:
        new = (rest.rstrip("\n") + "\n\n" if rest.strip() else "") + toml_block(name, command)
    if new == old:
        return False
    if new.strip():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(new, encoding="utf-8")
    elif path.exists():
        path.unlink()
    return True


def write(folder: Path, building_id: str, tools: list[str], command: list[str]) -> list[Path]:
    """This Wiki's server in the files of `folder` the tools on read; out of the ones they no longer read."""
    name, wanted, changed = name_of(building_id), files_for(tools), []
    for rel in (CLAUDE, CURSOR):
        if _set_json(folder / rel, name, {"command": command[0], "args": command[1:]} if rel in wanted else None):
            changed.append(folder / rel)
    if _set_toml(folder / CODEX, name, command if CODEX in wanted else None):
        changed.append(folder / CODEX)
    return changed


def remove(folder: Path, building_id: str) -> list[Path]:
    name, changed = name_of(building_id), []
    for rel in (CLAUDE, CURSOR):
        if (folder / rel).exists() and _set_json(folder / rel, name, None):
            changed.append(folder / rel)
    if (folder / CODEX).exists() and _set_toml(folder / CODEX, name, None):
        changed.append(folder / CODEX)
    return changed


def written(folder: Path, building_id: str) -> list[str]:
    """The files of `folder` that name this Wiki's server now (relative to it)."""
    name, out = name_of(building_id), []
    for rel in (CLAUDE, CURSOR):
        if name in (_json(folder / rel).get("mcpServers") or {}):
            out.append(rel.as_posix())
    if (folder / CODEX).exists() and _marks(name)[0] in (folder / CODEX).read_text(encoding="utf-8"):
        out.append(CODEX.as_posix())
    return out
