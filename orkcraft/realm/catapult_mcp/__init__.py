"""🎯 The Catapult through MCP: a shot carried by the AI tool that has the server, then a path of its own.

    templates.py   what a shot sends, as a template over the cart; learned from a recorded call
    carrier.py     the tool that carries (chosen by the server), held to one MCP tool, checked by its events
    local.py       the Catapult's own MCP client for a local (stdio) server you allowed: no model
    routes.py      a direct path — the service's API or SMTP with a token of your own — from recipes/*.json

A shot takes the most deterministic track there is: **direct** (a learned route that is on and has its
token), else **local** (allowed and the server is local), else **carrier** (one call of the light
model). After a carried shot the Loader learns: the arguments become a template, the template a
direct route where a recipe knows the service. Its route lives in `.orkcraft/scripts/<id>/route.json`
(the camp's git: every lesson is a commit you can revert). docs/design/catapult-mcp.md
"""
from __future__ import annotations

import json
from pathlib import Path

from orkcraft.realm.catapult_mcp import carrier, local, routes, templates  # noqa: F401

TRACKS = ("direct", "local", "carrier")


def route_file(repo_root: Path, building_id: str) -> Path:
    return repo_root / ".orkcraft" / "scripts" / building_id / "route.json"


def load(repo_root: Path, building_id: str) -> dict:
    """The building's route: {server, tool, args, carrier, learned, options: [route…], pick, on, proven};
    {} before its first carried shot."""
    try:
        data = json.loads(route_file(repo_root, building_id).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save(repo_root: Path, building_id: str, route: dict) -> None:
    f = route_file(repo_root, building_id)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(route, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def direct(route: dict) -> dict | None:
    """The direct route picked among the learned options, or None."""
    options = route.get("options") or []
    i = route.get("pick", 0)
    return options[i] if isinstance(i, int) and 0 <= i < len(options) else None
