"""A building's UI document (`schemas/building-ui.v1.json`, docs/design-system.md): how its window
is laid out, as data a steward can rewrite and a validator can check.

    c = ui.contract("lake")          # the panes a Lake has and the components each may wear
    doc = ui.current(building, "lake")   # what the scroll keeps for it, else the type's default
    ui.validate(doc, c)              # [] or the problems, in words a model can fix
    ui.leaves(doc)                   # the panes in order, each with its parent's split

Every type has a contract: its file in `design/buildings/`, else one pane, `main`, that is the
type's own view. A document names roles only — components, font roles, colour roles — never a
colour, a font name or code; each face draws the roles its own way.
"""
from __future__ import annotations

import copy
import functools
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from orkcraft.design import tokens

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "building-ui.v1.json"
CONTRACTS_DIR = Path(__file__).with_name("buildings")
MAX_DEPTH = 3                   # a document, a group, a group in it

# The closed list of components. A face draws each its own way; a contract says which a pane may wear.
COMPONENTS: dict[str, str] = {
    "status": "one to three short live lines: what runs, what waits, what was shown",
    "text": "plain text, wrapped",
    "markdown": "Markdown, rendered",
    "diff": "a diff, side by side or unified",
    "editor": "a text editor for one file",
    "list": "selectable rows",
    "table": "rows with columns",
    "tree": "folders and files, foldable",
    "board": "lanes side by side, a card per item",
    "counter": "one big number and its label",
    "chart": "bars or a line over time",
    "log": "lines as they come, newest last",
    "form": "fields and a button",
    "terminal": "an agent's live terminal",
    "view": "the building's own view, as its type draws it",
}


# What a model (a steward rebuilding a building's window) must keep to. docs/design-system.md explains
# them to people; this is the text the model reads.
RULES = """\
- Change only what the operator asked for; every other pane stays as it is.
- Use only the panes of the contract and, for each, only the components it lists. A required pane stays
  and is never hidden; a dynamic pane shows and hides by itself (leave out `hidden`).
- Name roles, never values: `font` is a font role, `tone` a colour role. No colours, font names, pixel
  sizes or code anywhere in the document.
- Fonts: title for a name, heading for a pane's heading, body for running text, mono for code, paths and
  diffs, status for the short live lines, label for a field's name, number for counters and money.
- Tones mean something: ok, wait, error as they say, fire only for what waits for the person. Most panes
  have no tone.
- Sizes: auto for a pane as tall as its content (status lines), 1-12 for a share of the room left; the
  pane people read most gets the largest share.
- Split: column puts panes one under another, row side by side. Side by side only where both halves stay
  readable (a list beside its detail). Groups nest at most two deep.
- The town stays simple: a layout never adds roads, ports or settings to the map; a building's settings
  live in its window.
- Give a pane a title only when its content does not say what it is.
- Write `note`: one sentence on what changed and why."""


@dataclass(frozen=True)
class Contract:
    type: str
    about: str
    panes: dict[str, dict]       # id → {"about", "components", "required", "dynamic"}
    default: dict

    def required(self) -> set[str]:
        return {p for p, d in self.panes.items() if d.get("required")}

    def describe(self) -> str:
        """The contract in a few lines, for a prompt."""
        lines = [f"type {self.type}: {self.about}"]
        for pid, d in self.panes.items():
            flags = [f for f in ("required", "dynamic") if d.get(f)]
            lines.append(f"- pane {pid}{' (' + ', '.join(flags) + ')' if flags else ''}: {d.get('about', '')}; "
                         f"components {', '.join(d['components'])}")
        return "\n".join(lines)


def _generic(type_id: str) -> Contract:
    default = {"version": 1, "type": type_id, "split": "column",
               "panes": [{"id": "main", "component": "view", "size": 1, "font": "body"}]}
    return Contract(type_id, "the building's own view, as one pane",
                    {"main": {"about": "the whole view", "components": ["view"], "required": True}}, default)


@functools.lru_cache(maxsize=None)
def _contract_files() -> dict[str, dict]:
    out = {}
    for path in sorted(CONTRACTS_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        out[data["type"]] = data
    return out


def contract(type_id: str) -> Contract:
    data = _contract_files().get(type_id)
    if data is None:
        return _generic(type_id)
    return Contract(data["type"], data.get("about", ""), data["panes"], data["default"])


def default(type_id: str) -> dict:
    return copy.deepcopy(contract(type_id).default)


def current(building: Any, type_id: str) -> dict:
    """The building's UI document: what its scroll entry keeps (`BuildingSpec.ui`), when it is still
    one for this type and still fits its contract (a type that got its panes after the document was
    kept: the old `main` no longer does), else the type's default."""
    doc = getattr(building, "ui", None)
    if isinstance(doc, dict) and doc.get("type") == type_id and _fits(json.dumps(doc, sort_keys=True), type_id):
        return copy.deepcopy(doc)
    return default(type_id)


@functools.lru_cache(maxsize=256)
def _fits(doc_json: str, type_id: str) -> bool:
    return not validate(json.loads(doc_json), contract(type_id))


# -- reading a document -------------------------------------------------------------------------

@dataclass(frozen=True)
class Leaf:
    pane: dict          # the pane as in the document
    split: str          # its parent's split: "column" (sizes are heights) or "row" (widths)
    depth: int


def leaves(doc: dict) -> Iterator[Leaf]:
    """Every pane in document order, with the split of the group it sits in."""
    def walk(items: list, split: str, depth: int) -> Iterator[Leaf]:
        for item in items:
            if "split" in item:
                yield from walk(item.get("panes") or [], item["split"], depth + 1)
            else:
                yield Leaf(item, split, depth)
    yield from walk(doc.get("panes") or [], doc.get("split", "column"), 1)


def outline(doc: dict) -> str:
    """The layout in one line, for people: `head (status, auto) / [tree (tree, 2) | page (markdown, 3)]`."""
    def item(x: dict) -> str:
        if "split" in x:
            return "[" + (" | " if x["split"] == "row" else " / ").join(item(y) for y in x.get("panes") or []) + "]"
        bits = [x.get("component", "?"), str(x.get("size", 1))]
        bits += [f"{k} {x[k]}" for k in ("font", "tone") if x.get(k)]
        return f"{x.get('id')}{' (hidden)' if x.get('hidden') else ''} ({', '.join(bits)})"
    return (" | " if doc.get("split") == "row" else " / ").join(item(x) for x in doc.get("panes") or [])


def _depth(items: list, depth: int = 1) -> int:
    deepest = depth
    for item in items:
        if isinstance(item, dict) and "split" in item:
            deepest = max(deepest, _depth(item.get("panes") or [], depth + 1))
    return deepest


# -- checking a document ------------------------------------------------------------------------

@functools.lru_cache(maxsize=1)
def _schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def validate(doc: Any, c: Contract) -> list[str]:
    """The problems of a UI document against its type's contract, in words a model can fix; []: fine."""
    from jsonschema import Draft202012Validator

    errors = [f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
              for e in sorted(Draft202012Validator(_schema()).iter_errors(doc), key=lambda e: list(e.absolute_path))]
    if errors:
        return errors[:12]
    if doc["type"] != c.type:
        return [f"type: {doc['type']!r} is not this building's type {c.type!r}"]
    if _depth(doc["panes"]) > MAX_DEPTH:
        errors.append(f"panes: groups nest at most {MAX_DEPTH - 1} deep")
    seen: set[str] = set()
    for leaf in leaves(doc):
        p, pid = leaf.pane, leaf.pane["id"]
        where = f"pane {pid}"
        if pid in seen:
            errors.append(f"{where}: appears twice")
        seen.add(pid)
        spec = c.panes.get(pid)
        if spec is None:
            errors.append(f"{where}: not a pane of {c.type} (it has {', '.join(c.panes)})")
            continue
        if p["component"] not in COMPONENTS:
            errors.append(f"{where}: component {p['component']!r} is not one of {', '.join(COMPONENTS)}")
        elif p["component"] not in spec["components"]:
            errors.append(f"{where}: may be {', '.join(spec['components'])}, not {p['component']!r}")
        if "font" in p and p["font"] not in tokens.FONTS:
            errors.append(f"{where}: font {p['font']!r} is not a font role ({', '.join(tokens.FONTS)})")
        if "tone" in p and p["tone"] not in tokens.TONES:
            errors.append(f"{where}: tone {p['tone']!r} is not a colour role ({', '.join(tokens.TONES)})")
        if p.get("hidden") and spec.get("required"):
            errors.append(f"{where}: is required, it cannot be hidden")
        if "hidden" in p and spec.get("dynamic"):
            errors.append(f"{where}: shows and hides by itself, leave out hidden")
    missing = c.required() - seen
    if missing:
        errors.append(f"panes: missing {', '.join(sorted(missing))} (required)")
    return errors
