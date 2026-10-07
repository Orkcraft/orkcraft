"""Town Scroll validation: the JSON schema plus the cross-references a schema cannot check.

Part of orkcraft.scroll, which re-exports every name here: import it from there."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from orkcraft.scroll import DEFAULT_HARNESS, MAX_GARRISON, SCHEMA_PATH, SCHEMA_V2_PATH

# -- validation ----------------------------------------------------------------------------------

def _schema(path: Path = SCHEMA_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _schema_errors(data: Any, path: Path, sub: str | None = None) -> list[str]:
    from jsonschema import Draft202012Validator

    schema = _schema(path)
    if sub:  # validate against one $defs entry, resolving refs inside the full schema
        schema = {**schema, "$ref": f"#/$defs/{sub}"}
        for k in ("required", "properties", "additionalProperties", "type"):
            schema.pop(k, None)
    return [
        f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
        for e in sorted(Draft202012Validator(schema).iter_errors(data), key=lambda e: list(e.absolute_path))
    ]


def _regex_problem(pattern: str) -> str:
    try:
        re.compile(pattern)
    except re.error as e:
        return f"bad regex {pattern!r}: {e}"
    return ""


def orc_problems(orc: dict, where: str = "") -> list[str]:
    """Schema and kind rules of one orc (a dict as in the file) — also the recruiter's check."""
    prefix = f"{where}: " if where else ""
    errors = [prefix + e for e in _schema_errors(orc, SCHEMA_PATH, "orc")]
    if errors:
        return errors
    kind = orc.get("kind", "agent")
    harness = orc.get("harness", DEFAULT_HARNESS)
    name = orc.get("id", "?")
    if kind == "chain" and not orc.get("chain"):
        errors.append(f"{prefix}ork {name}: a chain needs at least one op")
    if kind in ("script", "hybrid") and not orc.get("script"):
        errors.append(f"{prefix}ork {name}: a {kind} needs a script")
    if kind == "agent" and not harness:
        errors.append(f"{prefix}ork {name}: an {kind} needs a harness")
    if kind == "steward" and harness:
        errors.append(f"{prefix}ork {name}: a road rule thinks on the steward's tools — no harness of its own")
    if kind == "steward" and not str(orc.get("orders") or "").strip():
        errors.append(f"{prefix}ork {name}: a road rule needs its words (orders)")
    if kind != "chain" and orc.get("chain"):
        errors.append(f"{prefix}ork {name}: only a chain has chain ops")
    for op in orc.get("chain", []):
        pattern = op.get("regex") or (op.get("value") if op.get("cmp") == "matches" else None)
        if isinstance(pattern, str) and (p := _regex_problem(pattern)):
            errors.append(f"{prefix}ork {name}: {p}")
    return errors


def filter_problems(flt: dict) -> list[str]:
    errors = _schema_errors(flt, SCHEMA_PATH, "filter")
    if not errors and flt.get("match") and (p := _regex_problem(flt["match"])):
        errors.append(p)
    return errors


def _cycle(edges: dict[str, set[str]]) -> str | None:
    """A node on a directed cycle of `edges`, or None."""
    state: dict[str, int] = {}

    def visit(n: str) -> str | None:
        state[n] = 1
        for m in edges.get(n, ()):
            if state.get(m) == 1:
                return m
            if m not in state and (hit := visit(m)):
                return hit
        state[n] = 2
        return None

    for n in list(edges):
        if n not in state and (hit := visit(n)):
            return hit
    return None


def validate(data: dict[str, Any]) -> list[str]:
    """v3 schema errors plus the cross-references a JSON Schema cannot express."""
    errors = _schema_errors(data, SCHEMA_PATH)
    if errors:
        return errors
    errors += _common_refs(data)
    b_ids = {b["id"] for b in data["buildings"]}
    edges: dict[str, set[str]] = {}
    for b in data["buildings"]:
        g = b.get("garrison") or {}
        steward = g.get("steward")
        handlers = g.get("handlers", [])
        orcs = ([steward] if steward else []) + handlers
        ids = [m["id"] for m in orcs]
        dupes = sorted({m for m in ids if ids.count(m) > 1})
        if dupes:
            errors.append(f"building {b['id']}: duplicate ork ids {', '.join(dupes)}")
        if len(orcs) > MAX_GARRISON:
            errors.append(f"building {b['id']}: more than {MAX_GARRISON} orks in the garrison")
        for m in orcs:
            errors += orc_problems(m, f"building {b['id']}")
        handler_ids = {m["id"] for m in handlers}
        road_ids = [r["id"] for r in b.get("roads", [])]
        dupes = sorted({r for r in road_ids if road_ids.count(r) > 1})
        if dupes:
            errors.append(f"building {b['id']}: duplicate road ids {', '.join(dupes)}")
        seen: set[tuple] = set()
        for r in b.get("roads", []):
            where = f"building {b['id']}, road {r['id']}"
            if r["from"] not in b_ids:
                errors.append(f"{where}: source {r['from']!r} does not exist")
            if r["from"] == b["id"]:
                errors.append(f"{where}: a road cannot come from its own building")
            if r.get("handler") is not None and r["handler"] not in handler_ids:
                errors.append(f"{where}: handler {r['handler']!r} is not a handler of {b['id']}")
            errors += [f"{where}: filter {e}" for e in filter_problems(r.get("filter") or {})]
            key = (r["from"], r["event"], r.get("handler"), json.dumps(r.get("filter") or {}, sort_keys=True))
            if key in seen:
                errors.append(f"{where}: the same road twice")
            seen.add(key)
            if not (r.get("filter") or {}).get("returns"):     # a return road brings results back: no loop
                edges.setdefault(r["from"], set()).add(b["id"])
    if (hit := _cycle(edges)) is not None:
        errors.append(f"roads form a loop through {hit!r}")
    return errors


def _common_refs(data: dict[str, Any]) -> list[str]:
    """Orkspace / building references shared by v2 and v3."""
    errors = []
    b_ids = [b["id"] for b in data["buildings"]]
    o_ids = [o["id"] for o in data["orkspaces"]]
    for kind, ids in (("building", b_ids), ("orkspace", o_ids)):
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        if dupes:
            errors.append(f"duplicate {kind} ids: {', '.join(dupes)}")
    hotkeys = [o["hotkey"] for o in data["orkspaces"] if o.get("hotkey")]
    if len(hotkeys) != len(set(hotkeys)):
        errors.append("two orkspaces share a hotkey")
    if data["active_orkspace_id"] not in o_ids:
        errors.append(f"active_orkspace_id {data['active_orkspace_id']!r} is not an orkspace")
    placed: dict[str, str] = {}
    for o in data["orkspaces"]:
        for bid in o["buildings"]:
            if bid not in b_ids:
                errors.append(f"orkspace {o['id']}: unknown building {bid!r}")
            elif bid in placed:
                errors.append(f"building {bid!r} is in two orkspaces ({placed[bid]}, {o['id']})")
            placed[bid] = o["id"]
    return errors


def validate_v2(data: dict[str, Any]) -> list[str]:
    """A v2 scroll (before migration): the v2 schema and its rally / garrison references."""
    errors = _schema_errors(data, SCHEMA_V2_PATH)
    if errors:
        return errors
    errors += _common_refs(data)
    b_ids = [b["id"] for b in data["buildings"]]
    for b in data["buildings"]:
        rp = b.get("rally_point")
        if rp and rp["target_building_id"] not in b_ids:
            errors.append(f"building {b['id']}: rally target {rp['target_building_id']!r} does not exist")
        if rp and rp["target_building_id"] == b["id"]:
            errors.append(f"building {b['id']}: a rally point cannot target itself")
        g = b.get("garrison") or {}
        members = [m["id"] for m in g.get("members", [])]
        dupes = sorted({m for m in members if members.count(m) > 1})
        if dupes:
            errors.append(f"building {b['id']}: duplicate ork ids {', '.join(dupes)}")
        if len(members) > MAX_GARRISON:
            errors.append(f"building {b['id']}: more than {MAX_GARRISON} orks in the garrison")
        if g.get("lead_orc_id") and g["lead_orc_id"] not in members:
            errors.append(f"building {b['id']}: lead ork {g['lead_orc_id']!r} is not in the garrison")
    edges = {b["id"]: {b["rally_point"]["target_building_id"]} for b in data["buildings"] if b.get("rally_point")}
    if (hit := _cycle(edges)) is not None:
        errors.append(f"rally points form a loop through {hit!r}")
    return errors
