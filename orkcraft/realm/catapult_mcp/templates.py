"""What a shot sends, as a template over the cart: constants, and `{"$": "path"}` where a value comes
from the cart (a body path, "" the whole body).

    learn({"channel": "C01", "text": "v0.2: …"}, {"notes": "v0.2: …"})  → {"channel": "C01", "text": {"$": "notes"}}
    render(template, body)                                              → the arguments of this cart
    from_lines(['channel = "C01"', "text = notes"])                     → the `args` setting as a template

A template is plain JSON (route.json keeps it), so it is read and reviewed like any file.
"""
from __future__ import annotations

import json

from orkcraft.realm.catapult_web import leaves

REF = "$"


class Missing(ValueError):
    """The cart has no value at a path the template takes."""


def ref(path: str) -> dict:
    return {REF: path}


def is_ref(node) -> bool:
    return isinstance(node, dict) and set(node) == {REF} and isinstance(node[REF], str)


def pick(body, path: str):
    """The value at a dotted path ("" the body itself); raises Missing."""
    if path == "":
        return body
    cur = body
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        elif isinstance(cur, list) and part.isdigit() and int(part) < len(cur):
            cur = cur[int(part)]
        else:
            raise Missing(f"the cart has no {path}")
    return cur


def render(template, body):
    """The template with every reference replaced by the cart's value."""
    if is_ref(template):
        return pick(body, template[REF])
    if isinstance(template, dict):
        return {k: render(v, body) for k, v in template.items()}
    if isinstance(template, list):
        return [render(v, body) for v in template]
    return template


def paths(template) -> list[str]:
    """The cart paths a template takes, in order."""
    if is_ref(template):
        return [template[REF]]
    if isinstance(template, dict):
        return [p for v in template.values() for p in paths(v)]
    if isinstance(template, list):
        return [p for v in template for p in paths(v)]
    return []


def _same(a, b) -> bool:
    if isinstance(a, str) and isinstance(b, str):
        return a.strip() == b.strip() and a.strip() != ""
    if isinstance(a, bool) or isinstance(b, bool):
        return False                                   # true/false are too common to be the cart's
    return isinstance(a, (int, float)) and isinstance(b, (int, float)) and a == b


def learn(args, body):
    """A recorded call's arguments as a template: a value that is one of the cart's (the whole body,
    or a leaf) becomes a reference to it; the rest stays as it was sent."""
    flat = leaves(body) if isinstance(body, (dict, list)) else {}
    whole = json.dumps(body, ensure_ascii=False, sort_keys=True) if body is not None else None

    def walk(node):
        if isinstance(node, dict):
            return {k: walk(v) for k, v in node.items()}
        if isinstance(node, list):
            return [walk(v) for v in node]
        if _same(node, body):
            return ref("")
        if isinstance(node, str) and whole is not None and isinstance(body, (dict, list)):
            try:
                if json.dumps(json.loads(node), ensure_ascii=False, sort_keys=True) == whole:
                    return ref("")
            except ValueError:
                pass
        for path, value in flat.items():
            if _same(node, value):
                return ref(path)
        return node

    return walk(args)


def from_lines(lines: list[str]) -> dict:
    """The `args` setting: `name = "a constant"`, `name = 5` (JSON), or `name = a.cart.path`."""
    out: dict = {}
    for line in lines:
        name, sep, value = str(line).partition("=")
        name, value = name.strip(), value.strip()
        if not sep or not name:
            continue
        if value.startswith('"') or value[:1] in "[{" or value in ("true", "false", "null") \
                or value.lstrip("-").replace(".", "", 1).isdigit():
            try:
                out[name] = json.loads(value)
                continue
            except ValueError:
                pass
        out[name] = ref("" if value in ("", ".") else value)
    return out


def describe(template) -> str:
    """One line per argument: `text ← notes`, `channel = "C01"`."""
    if not isinstance(template, dict):
        return json.dumps(template, ensure_ascii=False)[:200]
    lines = []
    for k, v in template.items():
        if is_ref(v):
            lines.append(f"{k} ← {v[REF] or 'the whole cart'}")
        else:
            lines.append(f"{k} = {json.dumps(v, ensure_ascii=False)[:120]}")
    return "\n".join(lines)
