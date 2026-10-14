"""A building type's defaults that Orkline ships (docs/design/improve-buildings.md §5.4): the settings a building
raised from Build starts with, beyond what its type's code assumes. One file per type,
`orkcraft/design/defaults/<type>.json`, `{"config": {...}}`. A Test bench sends the settings and prompts it tried on
its virtual building there, as a pull request (gui/lab_runs.py), so every new building of the type starts with them.

    type_defaults.config("barracks")             -> {} or the shipped config
    type_defaults.changed(before, after)         -> the keys a change set, with their new values
    type_defaults.text("barracks", keys)         -> (its file as installed, as changed with `keys`)

Pure: no face.
"""
from __future__ import annotations

import json
from pathlib import Path

DIR = Path(__file__).resolve().parent.parent / "design" / "defaults"


def path(type_id: str) -> Path:
    return DIR / f"{type_id}.json"


def config(type_id: str) -> dict:
    try:
        got = json.loads(path(type_id).read_text(encoding="utf-8")).get("config")
    except (OSError, ValueError, AttributeError):
        return {}
    return dict(got) if isinstance(got, dict) else {}


def changed(before: dict, after: dict) -> dict:
    """What a change set: each top-level key whose value it changed or added (a key it took away is not a default)."""
    return {k: v for k, v in (after or {}).items() if (before or {}).get(k) != v}


def text(type_id: str, keys: dict) -> tuple[str, str]:
    p = path(type_id)
    base = p.read_text(encoding="utf-8") if p.is_file() else ""
    return base, json.dumps({"config": dict(sorted({**config(type_id), **keys}.items()))}, indent=1,
                            ensure_ascii=False) + "\n"
