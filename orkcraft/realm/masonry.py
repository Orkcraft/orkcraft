"""Custom buildings (Mason & Artisan): the declarative spec, its checks and its data fetchers.

A custom building is data, never code: panes of whitelisted widgets bound to whitelisted data
sources with bounded parameters, and whitelisted Command Card actions. `validate_spec` checks
the JSON Schema (`schemas/building-spec.v1.json`) plus what a schema cannot: data names used by
panes exist, widget ↔ source kinds fit, paths stay inside the repository, keys don't clash with
orkcraft's own. `fetch` is the only code that reads data for a custom building — the UI renders
what it returns and nothing else.

Specs live in `.orkcraft/buildings/<id>.json` (local, like the Town Scroll) and the scroll refers
to them as `preset_ref: "custom:<id>"`.
"""
from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "building-spec.v1.json"
SPECS_DIR = Path(".orkcraft") / "buildings"

LIST, TEXT, TREE = "list", "text", "tree"

# source → (kind, {param: (type, allowed values | (min, max) | None)}, one-line description)
SOURCES: dict[str, tuple[str, dict[str, tuple[type, Any]], str]] = {
    "graph_nodes": (LIST, {
        "type": (str, ("task", "context", "process")),
        "status": (str, ("todo", "in-progress", "done", "ongoing", "active", "outdated", "paused")),
        "subtype": (str, ("goal", "personal", "decision", "knowledge")),
        "priority": (str, ("high", "medium", "low")),
        "assignee": (str, None),
        "tag": (str, None),
        "limit": (int, (1, 200)),
    }, "Markdown items with frontmatter (showcase sandbox) filtered by type / status / priority / assignee / tag"),
    "file": (TEXT, {"path": (str, None)}, "one Markdown or text file inside the repository"),
    "file_tail": (TEXT, {"path": (str, None), "lines": (int, (1, 500))}, "the last lines of a file inside the repository"),
    "directory": (TREE, {"path": (str, None)}, "a folder inside the repository"),
    "sessions": (LIST, {
        "ticket": (str, None), "harness": (str, ("claude", "agy", "claude-web")), "limit": (int, (1, 100)),
    }, "Claude / agy sessions, optionally of one ticket"),
    "agents": (LIST, {"system": (str, None)}, "agents of the multi-agent systems"),
    "git_log": (LIST, {"path": (str, None), "limit": (int, (1, 200))}, "recent commits, optionally touching a path"),
}
WIDGETS: dict[str, tuple[str, str]] = {
    "list": (LIST, "selectable rows; a row with a node id feeds the War Tent and rally pipes"),
    "table": (LIST, "rows with columns"),
    "counter": (LIST, "a big number: how many rows the data has"),
    "markdown": (TEXT, "rendered Markdown"),
    "log": (TEXT, "monospace text, newest at the bottom"),
    "tree": (TREE, "a folder tree"),
}
ACTIONS: dict[str, str] = {
    "node:open": "open the card of the selected node",
    "node:chat": "open the War Tent on the selected node",
    "node:preview": "show the selected node in the Scrying Spire",
    "building:refresh": "reload this building's data",
}
# Keys orkcraft already uses: digits pick buildings; these capitals are the Command Card's.
RESERVED_KEYS = frozenset("0123456789BCDFHKLMNPRSTUXYZ")
ID_RESERVED = frozenset({"farm", "forge", "loot", "watchtower", "great_hall", "scrying", "chat",
                         "processes", "agents", "systems", "limits", "town_hall"})
MAX_ROWS = 200
TEXT_LIMIT = 256 * 1024
_TICKET = re.compile(r"^[TCP]\d{4,}$")


# -- paths ------------------------------------------------------------------------------------------

def safe_path(repo_root: Path, rel: str) -> Path | None:
    """The resolved path if it stays inside the repository (symlinks resolved first), else None."""
    if not isinstance(rel, str) or not rel.strip() or "\0" in rel or Path(rel).is_absolute():
        return None
    root = repo_root.resolve()
    try:
        target = (root / rel).resolve()
        target.relative_to(root)
    except (OSError, ValueError):
        return None
    if ".git" in target.relative_to(root).parts:
        return None
    return target


# -- validation -------------------------------------------------------------------------------------

def _schema_errors(data: Any) -> list[str]:
    from jsonschema import Draft202012Validator

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return [
        f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
        for e in sorted(Draft202012Validator(schema).iter_errors(data), key=lambda e: list(e.absolute_path))
    ]


def validate_spec(data: Any, repo_root: Path, existing_ids: set[str] | frozenset[str] = frozenset()) -> list[str]:
    """Every problem, operator- and model-readable; [] means the spec can be raised."""
    if isinstance(data, dict):
        from orkcraft.realm import catalog
        data = catalog.migrate(data)                  # an old type id is checked as its camp building
    errors = _schema_errors(data)
    if errors:
        return errors
    if data["id"] in ID_RESERVED or data["id"] in existing_ids:
        errors.append(f"id {data['id']!r} is taken — choose another")
    from orkcraft.realm import catalog
    errors.extend(catalog.validate(data))
    kinds: dict[str, str] = {}
    for i, d in enumerate(data.get("data", [])):
        if d["name"] in kinds:
            errors.append(f"data/{i}: duplicate name {d['name']!r}")
        kind, allowed, _ = SOURCES[d["source"]]
        kinds[d["name"]] = kind
        params = d.get("params") or {}
        for key, value in params.items():
            if key not in allowed:
                errors.append(f"data/{i} ({d['source']}): unknown param {key!r}; allowed: {', '.join(allowed) or 'none'}")
                continue
            typ, rule = allowed[key]
            if typ is int and (not isinstance(value, int) or isinstance(value, bool)):
                errors.append(f"data/{i}: {key} must be an integer")
            elif typ is str and not isinstance(value, str):
                errors.append(f"data/{i}: {key} must be a string")
            elif isinstance(rule, tuple) and typ is int and isinstance(value, int) and not rule[0] <= value <= rule[1]:
                errors.append(f"data/{i}: {key} must be between {rule[0]} and {rule[1]}")
            elif isinstance(rule, tuple) and typ is str and value not in rule:
                errors.append(f"data/{i}: {key} must be one of {', '.join(rule)}")
            elif typ is str and isinstance(value, str) and len(value) > 200:
                errors.append(f"data/{i}: {key} is too long")
        if d["source"] in ("file", "file_tail", "directory") and "path" not in params:
            errors.append(f"data/{i} ({d['source']}): needs a path")
        if "path" in params and isinstance(params["path"], str):
            p = safe_path(repo_root, params["path"])
            if p is None:
                errors.append(f"data/{i}: path {params['path']!r} is outside the repository or not allowed")
            elif d["source"] == "directory" and p.exists() and not p.is_dir():
                errors.append(f"data/{i}: {params['path']!r} is not a folder")
        if d["source"] == "sessions" and "ticket" in params and not _TICKET.match(str(params["ticket"])):
            errors.append(f"data/{i}: ticket must look like T1234")
    for i, pane in enumerate((data.get("layout") or {}).get("panes", [])):
        want = WIDGETS[pane["widget"]][0]
        have = kinds.get(pane["data"])
        if have is None:
            errors.append(f"layout/panes/{i}: no data named {pane['data']!r}")
        elif have != want:
            errors.append(f"layout/panes/{i}: widget {pane['widget']!r} shows {want} data, but {pane['data']!r} is {have}")
        if pane.get("columns") and pane["widget"] != "table":
            errors.append(f"layout/panes/{i}: columns only apply to a table")
    from orkcraft.realm.huts import validate_mini
    errors.extend(validate_mini(data, kinds))
    keys = [a["key"] for a in data.get("actions", [])]
    for k in sorted(set(keys)):
        if k in RESERVED_KEYS:
            errors.append(f"actions: key {k!r} is taken by orkcraft; free keys: {''.join(free_keys())}")
        if keys.count(k) > 1:
            errors.append(f"actions: key {k!r} used twice")
    return errors


def free_keys() -> list[str]:
    return [c for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if c not in RESERVED_KEYS]


def catalog() -> str:
    """What Mason and Artisan may use, generated from the tables above (never hand-written)."""
    lines = ["DATA SOURCES (source: kind — params):"]
    for name, (kind, params, desc) in SOURCES.items():
        ps = ", ".join(
            f"{k}={('|'.join(r) if isinstance(r, tuple) and t is str else f'{r[0]}..{r[1]}' if isinstance(r, tuple) else t.__name__)}"
            for k, (t, r) in params.items()
        ) or "none"
        lines.append(f"- {name}: {kind} — {desc}; params: {ps}")
    lines.append("WIDGETS (widget: shows kind):")
    lines += [f"- {w}: {k} — {d}" for w, (k, d) in WIDGETS.items()]
    lines.append("ACTIONS (Command Card of the building):")
    lines += [f"- {a}: {d}" for a, d in ACTIONS.items()]
    lines.append(f"Free action keys: {' '.join(free_keys())}. Paths are relative to the repository root.")
    return "\n".join(lines)


# -- storage ----------------------------------------------------------------------------------------

def spec_file(repo_root: Path, building_id: str) -> Path:
    return repo_root / SPECS_DIR / f"{building_id}.json"


def save_spec(repo_root: Path, spec: dict, existing_ids: set[str] | frozenset[str] = frozenset()) -> list[str]:
    """Write a valid spec; returns the problems (and writes nothing) otherwise."""
    from orkcraft.realm import catalog
    spec = catalog.migrate(spec)
    problems = validate_spec(spec, repo_root, existing_ids)
    if problems:
        return problems
    path = spec_file(repo_root, spec["id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"version": 1, **spec}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)
    return []


def load_specs(repo_root: Path) -> tuple[list[dict], list[str]]:
    """Valid specs and the problems of the invalid ones (which are skipped, never raised)."""
    folder = repo_root / SPECS_DIR
    specs, problems, ids = [], [], set()
    for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            problems.append(f"{path.name}: {e}")
            continue
        if isinstance(data, dict):
            from orkcraft.realm import catalog
            data = catalog.migrate(data)              # old type ids load as camp buildings
        errs = validate_spec(data, repo_root, ids)
        if errs:
            problems.append(f"{path.name}: " + "; ".join(errs[:3]))
            continue
        ids.add(data["id"])
        specs.append(data)
    return specs, problems


# -- data -------------------------------------------------------------------------------------------

@dataclass
class Row:
    title: str
    id: str = ""            # a node id when the row is a node (selection feeds War Tent / pipes)
    status: str = ""
    priority: str = ""
    assignee: str = ""
    type: str = ""
    deadline: str = ""
    when: str = ""
    meta: str = ""

    def get(self, column: str) -> str:
        return str(getattr(self, column, "") or "")


@dataclass
class Data:
    kind: str
    rows: list[Row] = field(default_factory=list)
    text: str = ""
    path: Path | None = None       # for a tree
    error: str = ""


def fetch(source: str, params: dict | None, repo_root: Path, graph: Any = None) -> Data:
    """Read one data entry of a validated spec. Never raises; errors land in `Data.error`."""
    params = params or {}
    kind = SOURCES.get(source, (TEXT, {}, ""))[0]
    try:
        if source == "graph_nodes":
            return Data(LIST, rows=_graph_rows(graph, params))
        if source in ("file", "file_tail"):
            return _file(repo_root, params, tail=source == "file_tail")
        if source == "directory":
            p = safe_path(repo_root, params.get("path", ""))
            if p is None or not p.is_dir():
                return Data(TREE, error=f"no folder {params.get('path')!r} in the repository")
            return Data(TREE, path=p)
        if source == "sessions":
            return Data(LIST, rows=_session_rows(repo_root, params))
        if source == "agents":
            return Data(LIST, rows=_agent_rows(repo_root, params))
        if source == "git_log":
            return _git_log(repo_root, params)
    except Exception as e:  # a data source must never take the building down
        return Data(kind, error=f"{source}: {e}")
    return Data(kind, error=f"unknown source {source!r}")


def _graph_rows(graph: Any, params: dict) -> list[Row]:
    if graph is None:
        return []
    out = []
    for e in sorted(graph.entities.values(), key=lambda e: e.id):
        if params.get("type") and e.type != params["type"]:
            continue
        if params.get("status") and e.status != params["status"]:
            continue
        if params.get("subtype") and (e.subtype or "") != params["subtype"]:
            continue
        if params.get("priority") and e.priority != params["priority"]:
            continue
        if params.get("assignee") and e.assignee != params["assignee"]:
            continue
        if params.get("tag") and params["tag"] not in e.tags:
            continue
        out.append(Row(e.title, id=e.id, status=e.status, priority=e.priority if e.priority != "-" else "",
                       assignee=e.assignee, type=e.type + (f"/{e.subtype}" if e.subtype else ""),
                       deadline=e.deadline or "", meta=("🔒 " if getattr(e, "is_personal", False) else "") + (e.summary or "")))
        if len(out) >= min(int(params.get("limit", MAX_ROWS)), MAX_ROWS):
            break
    return out


def _file(repo_root: Path, params: dict, tail: bool) -> Data:
    p = safe_path(repo_root, params.get("path", ""))
    if p is None or not p.is_file():
        return Data(TEXT, error=f"no file {params.get('path')!r} in the repository")
    size = p.stat().st_size
    with p.open("rb") as f:
        if size > TEXT_LIMIT:
            f.seek(size - TEXT_LIMIT if tail else 0)
        raw = f.read(TEXT_LIMIT)
    if b"\0" in raw[:4096]:
        return Data(TEXT, error="binary file")
    text = raw.decode("utf-8", errors="replace")
    if tail:
        text = "\n".join(text.splitlines()[-int(params.get("lines", 50)):])
    elif size > TEXT_LIMIT:
        text += f"\n\n… cut at {TEXT_LIMIT // 1024} KB"
    return Data(TEXT, text=text)


def _session_rows(repo_root: Path, params: dict) -> list[Row]:
    from orkcraft.sources.sessions import collect_sessions, sessions_for

    sessions = sessions_for(collect_sessions(repo_root), params.get("ticket"))
    if params.get("harness"):
        sessions = [s for s in sessions if s.harness == params["harness"]]
    limit = min(int(params.get("limit", 50)), MAX_ROWS)
    return [Row(s.title or s.id, status=s.harness, when=s.last.strftime("%d %b %H:%M") if s.last else "",
                meta=", ".join(sorted(s.tickets))) for s in sessions[:limit]]


def _agent_rows(repo_root: Path, params: dict) -> list[Row]:
    from orkcraft.sources.agents import collect_agents

    agents = collect_agents(repo_root)
    if params.get("system"):
        agents = [a for a in agents if a.system == params["system"]]
    return [Row(a.name, status=a.status, type=a.system, meta=(a.description or "").split(".")[0]) for a in agents][:MAX_ROWS]


def _git_log(repo_root: Path, params: dict) -> Data:
    limit = min(int(params.get("limit", 30)), MAX_ROWS)
    cmd = ["git", "log", f"-n{limit}", "--format=%h%x1f%cI%x1f%s", "--"]
    if params.get("path"):
        p = safe_path(repo_root, params["path"])
        if p is None:
            return Data(LIST, error="path outside the repository")
        cmd.append(str(p.relative_to(repo_root.resolve())))
    out = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True, timeout=10).stdout
    rows = []
    for line in out.splitlines():
        parts = line.split("\x1f")
        if len(parts) == 3:
            rows.append(Row(parts[2], meta=parts[0], when=parts[1][:16].replace("T", " ")))
    return Data(LIST, rows=rows)
