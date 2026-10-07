"""The plan: which form field gets which key of the cart — settings, the model's mapping, names."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


@dataclass
class Step:
    field: dict
    path: str = ""             # a body path ("store.title", "images.0"), or
    literal: str | None = None  # a fixed value from the settings ('Category = "Major update"')
    by: str = "name"           # settings | model | name

    @property
    def label(self) -> str:
        return field_name(self.field)


@dataclass
class Plan:
    steps: list[Step] = field(default_factory=list)
    unused: list[str] = field(default_factory=list)       # body keys no field took
    unfilled: list[str] = field(default_factory=list)     # required fields nothing fills
    problems: list[str] = field(default_factory=list)     # settings lines that matched nothing


def field_name(f: dict) -> str:
    return str(f.get("label") or f.get("name") or f.get("id") or f.get("selector") or "?")


def _norm(s: str) -> str:
    return re.sub(r"[^0-9a-zа-яё]+", "", str(s).lower())


def _words(s: str) -> set[str]:
    s = re.sub(r"([a-z])([A-Z])", r"\1 \2", str(s))
    return {w for w in re.split(r"[^0-9a-zа-яё]+", s.lower()) if len(w) > 1}


def leaves(body, prefix: str = "") -> dict[str, object]:
    """Every scalar of the body under its dotted path; a list of scalars stays one value."""
    if isinstance(body, dict):
        out: dict[str, object] = {}
        for k, v in body.items():
            out.update(leaves(v, f"{prefix}.{k}" if prefix else str(k)))
        return out
    if isinstance(body, list) and body and all(isinstance(x, dict) for x in body):
        out = {}
        for i, v in enumerate(body):
            out.update(leaves(v, f"{prefix}.{i}" if prefix else str(i)))
        return out
    return {prefix or "value": body}


def schema_paths(schema: dict, prefix: str = "") -> list[str]:
    props = schema.get("properties") if isinstance(schema, dict) else None
    if not isinstance(props, dict):
        return [prefix] if prefix else []
    out: list[str] = []
    for k, sub in props.items():
        out += schema_paths(sub, f"{prefix}.{k}" if prefix else str(k))
    return out


def pick(body, path: str):
    if path in ("", "value") and not isinstance(body, (dict, list)):
        return body
    cur = body
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        elif isinstance(cur, list) and part.isdigit() and int(part) < len(cur):
            cur = cur[int(part)]
        else:
            return None
    return cur


def _find_field(fields: list[dict], name: str) -> int | None:
    name = name.strip()
    if name.startswith(("#", "[", "css:")):
        sel = name[4:].strip() if name.startswith("css:") else name
        return next((i for i, f in enumerate(fields) if f.get("selector") == sel), None)
    n = _norm(name)
    for key in ("label", "name", "id"):
        hit = next((i for i, f in enumerate(fields) if _norm(f.get(key, "")) == n and n), None)
        if hit is not None:
            return hit
    hit = next((i for i, f in enumerate(fields) if n and n in {_norm(x) for x in f.get("aka") or []}), None)
    if hit is not None:                              # renamed on the site, repaired by the overseer
        return hit
    return next((i for i, f in enumerate(fields) if n and n in _norm(f.get("label", ""))), None)


def parse_rules(lines: list[str]) -> tuple[list[tuple[str, str | None, str | None]], list[str]]:
    """`Field = body.path` or `Field = "fixed text"` → (field, path, literal)."""
    rules, errors = [], []
    for line in lines or []:
        left, eq, right = str(line).partition("=")
        left, right = left.strip(), right.strip()
        if not eq or not left or not right:
            errors.append(f"{line!r}: say `Field label = body.path` or `Field label = \"text\"`")
            continue
        if len(right) >= 2 and right[0] == right[-1] and right[0] in "\"'":
            rules.append((left, None, right[1:-1]))
        else:
            rules.append((left, right, None))
    return rules, errors


def plan(page_map: dict, keys: list[str], rules: list[str] | None = None,
         model_mapping: dict | None = None) -> Plan:
    """Which field gets which body key. Settings first, then the model's mapping, then names."""
    fields = list(page_map.get("fields") or [])
    out, taken, used = Plan(), set(), set()
    parsed, out.problems = parse_rules(rules or [])
    for name, path, literal in parsed:
        i = _find_field(fields, name)
        if i is None:
            out.problems.append(f"{name!r}: no such field on the page")
            continue
        if i not in taken:
            out.steps.append(Step(fields[i], path or "", literal, "settings"))
            taken.add(i)
            used.add(path)
    for idx, path in (model_mapping or {}).items():
        i = int(idx) if str(idx).isdigit() else None
        if i is None or i >= len(fields) or i in taken or path not in keys or path in used:
            continue
        out.steps.append(Step(fields[i], path, None, "model"))
        taken.add(i)
        used.add(path)
    for path in keys:
        if path in used:
            continue
        last = path.split(".")[-1]
        best, score = None, 0
        for i, f in enumerate(fields):
            if i in taken:
                continue
            names = [f.get("label", ""), f.get("name", ""), f.get("id", ""), *(f.get("aka") or [])]
            if any(_norm(x) and _norm(x) in (_norm(path), _norm(last)) for x in names):
                s = 3
            else:
                kw = _words(last) or _words(path)
                s = max((len(kw & _words(x)) for x in names), default=0)
                s = 2 if kw and s == len(kw) else 0
            if s > score:
                best, score = i, s
        if best is not None:
            out.steps.append(Step(fields[best], path, None, "name"))
            taken.add(best)
            used.add(path)
    out.unused = [k for k in keys if k not in used]
    out.unfilled = [field_name(f) for i, f in enumerate(fields) if f.get("required") and i not in taken]
    return out


def describe(p: Plan, body=None) -> str:
    """The plan as text, with the values when a body is given (the dry run)."""
    lines = []
    for s in p.steps:
        src = f'"{s.literal}"' if s.literal is not None else s.path
        val = "" if body is None or s.literal is not None else f"  ⇐ {str(pick(body, s.path))[:60]!r}"
        lines.append(f"  {s.label[:40]:<40} ← {src} ({s.by}){val}")
    out = ["fills:", *(lines or ["  nothing — load a cart, set a schema or map the fields"])]
    if p.unfilled:
        out.append("required, left empty: " + ", ".join(p.unfilled))
    if p.unused:
        out.append("not used: " + ", ".join(p.unused))
    if p.problems:
        out.append("settings: " + "; ".join(p.problems))
    return "\n".join(out)


# -- the model's mapping --------------------------------------------------------------------------

MAPPER = """You map data keys to the fields of a web form. The form's labels may be in any language.

FIELDS (index: kind, label, name, options):
{fields}

DATA KEYS (path: sample value):
{keys}

Answer with ONE JSON object and nothing else: {{"<field index>": "<data key path>", ...}}.
Map a key only when you are confident it belongs in that field; leave the rest out."""


def map_with_model(page_map: dict, body_sample: dict[str, object],
                   runner: Callable[[str], tuple[str, float | None]] | None = None) -> tuple[dict, float | None]:
    """One model call (the operator's Claude Code, in an empty folder): field index → key path."""
    from orkcraft.realm import builders
    runner = runner or builders.main_runner
    fields = "\n".join(f"{i}: {f.get('kind')}, {f.get('label', '')!r}, {f.get('name', '')!r}"
                       + (f", {f['options'][:12]}" if f.get("options") else "")
                       for i, f in enumerate(page_map.get("fields") or []))
    keys = "\n".join(f"{k}: {str(v)[:60]!r}" for k, v in body_sample.items())
    text, cost = runner(MAPPER.format(fields=fields, keys=keys))
    got = builders.extract_json(text) or {}
    n = len(page_map.get("fields") or [])
    return {str(k): v for k, v in got.items()
            if str(k).isdigit() and int(k) < n and isinstance(v, str) and v in body_sample}, cost


def load_mapping(state_dir: Path) -> dict:
    try:
        m = json.loads((state_dir / "mapping.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return m if isinstance(m, dict) else {}


def save_mapping(state_dir: Path, mapping: dict) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "mapping.json").write_text(json.dumps(mapping, ensure_ascii=False, indent=1), encoding="utf-8")
