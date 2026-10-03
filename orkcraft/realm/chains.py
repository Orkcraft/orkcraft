"""Chain handlers 🪧: a declarative pipeline of whitelisted ops over a handler's road snapshot.

A chain is data, not code (validated by `scroll.orc_problems`): nothing here evaluates,
imports or formats with Python attribute access. Input is a list of records — one per road
that has fired, its latest payload flattened (`record_of`) — and every op maps a list of
records to a new list:

    filter   {field, cmp: eq|ne|in|contains|matches, value}   keep matching records
    pick     {fields}                                          keep only these fields
    extract  {field, regex, as}                                first group (or match) → a new field
    sort     {by, desc?}        limit {n}                      order / cut
    count    {as?}                                             → one record {as|count: n}
    group    {by}                                              → {by: key, count: n} per key
    template {md}                                              `{field}` per record → text lines
    join     {sep?}                                            text lines → one text

    run_chain(ops, records) -> ChainResult(markdown, records, error)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

MAX_RECORDS = 1000
FIELD_CHARS = 10_000          # regex ops see at most this much of a field
OUTPUT_CHARS = 64 * 1024
_PLACEHOLDER = re.compile(r"\{\{|\}\}|\{([a-z_]{1,32})\}")


@dataclass
class ChainResult:
    markdown: str = ""
    records: list[Any] = field(default_factory=list)
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error


def record_of(road_id: str, payload: Any, meta: dict | None = None) -> dict[str, Any]:
    """One road's latest payload (a `pipes.Payload`) as a flat record."""
    rec: dict[str, Any] = {
        "road": road_id, "source": payload.source, "event": payload.mode, "kind": payload.kind,
        "value": payload.value, "title": payload.title,
    }
    if payload.kind == "node":
        rec["id"] = payload.value
    elif payload.kind == "file":
        rec["path"] = payload.value
    else:
        rec["text"] = payload.value
    for k, v in (meta or {}).items():
        if k in ("type", "status", "subtype", "outcome", "title") and v is not None and not (k == "title" and rec["title"]):
            rec[k] = v
    return rec


def _text(v: Any) -> str:
    return "" if v is None else str(v)


def _cmp(rec: Any, op: dict) -> bool:
    if not isinstance(rec, dict):
        return False
    have, want, how = rec.get(op["field"]), op["value"], op["cmp"]
    if how == "eq":
        return have == want or _text(have) == _text(want)
    if how == "ne":
        return not (have == want or _text(have) == _text(want))
    if how == "in":
        return isinstance(want, list) and (have in want or _text(have) in [_text(w) for w in want])
    if how == "contains":
        return _text(want).lower() in _text(have).lower()
    if how == "matches":
        return re.search(_text(want), _text(have)[:FIELD_CHARS]) is not None
    return False


def _fill(md: str, rec: Any) -> str:
    def sub(m: re.Match) -> str:
        if m.group(0) == "{{":
            return "{"
        if m.group(0) == "}}":
            return "}"
        return _text(rec.get(m.group(1))) if isinstance(rec, dict) else ""
    return _PLACEHOLDER.sub(sub, md)


def _apply(op: dict, recs: list[Any]) -> list[Any]:
    name = op["op"]
    if name == "filter":
        return [r for r in recs if _cmp(r, op)]
    if name == "pick":
        return [{f: r.get(f) for f in op["fields"] if f in r} if isinstance(r, dict) else r for r in recs]
    if name == "extract":
        pattern = re.compile(op["regex"])
        out = []
        for r in recs:
            if isinstance(r, dict):
                m = pattern.search(_text(r.get(op["field"]))[:FIELD_CHARS])
                r = {**r, op["as"]: (m.group(1) if m and m.groups() else m.group(0) if m else None)}
            out.append(r)
        return out
    if name == "sort":
        return sorted(recs, key=lambda r: _text(r.get(op["by"])) if isinstance(r, dict) else _text(r),
                      reverse=bool(op.get("desc")))
    if name == "limit":
        return recs[: op["n"]]
    if name == "count":
        return [{op.get("as") or "count": len(recs)}]
    if name == "group":
        counts: dict[str, int] = {}
        for r in recs:
            key = _text(r.get(op["by"])) if isinstance(r, dict) else _text(r)
            counts[key] = counts.get(key, 0) + 1
        return [{op["by"]: k, "count": n} for k, n in sorted(counts.items())]
    if name == "template":
        return [_fill(op["md"], r) for r in recs]
    if name == "join":
        return [(op.get("sep", "\n")).join(_text(r) if not isinstance(r, dict) else _render([r]) for r in recs)]
    raise ValueError(f"unknown chain op {name!r}")


def _render(recs: list[Any]) -> str:
    lines = []
    for r in recs:
        if isinstance(r, dict):
            lines.append("- " + ", ".join(f"{k}: {_text(v)}" for k, v in r.items()))
        else:
            lines.append(_text(r))
    return "\n".join(lines)


def run_chain(ops: list[dict], records: list[dict]) -> ChainResult:
    """Never raises: a failing op returns its error (the handler's cart turns red)."""
    recs: list[Any] = list(records[:MAX_RECORDS])
    for i, op in enumerate(ops):
        try:
            recs = _apply(op, recs)[:MAX_RECORDS]
        except (re.error, KeyError, TypeError, ValueError) as e:
            return ChainResult(records=recs, error=f"op {i + 1} ({op.get('op', '?')}): {e}")
    md = _render(recs)
    if len(md) > OUTPUT_CHARS:
        md = md[: OUTPUT_CHARS - 1] + "…"
    return ChainResult(md, recs)
