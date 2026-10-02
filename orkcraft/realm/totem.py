"""🗿 The Totem: a crossroads — rules send what arrives down one route.

One rule per line, the first that matches wins:

    <route>: contains <text>          the title or value contains it (any case)
    <route>: matches <regex>          a regex over title and value
    <route>: kind <text|file|node>    the payload's kind
    <route>: source <building id>     where it came from
    <route>: event <event id>         which event brought it
    <route>: <field> == <value>       field: title, value, source, event, kind, or a key of a JSON value
    <route>: <field> != <value>
    <route>: else                     always (put it last)

The match goes out as `totem.routed` with the route as its title; each road from the Totem waits
for its own route (a road filter). Nothing matched → `totem.unmatched`.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

ROUTE = re.compile(r"^[a-z0-9_-]{1,32}$")
FIELDS = ("title", "value", "source", "event", "kind")


@dataclass(frozen=True)
class Rule:
    route: str
    how: str              # contains | matches | kind | source | event | eq | ne | else
    field: str = ""
    value: str = ""


def parse(line: str) -> Rule:
    route, _, cond = str(line).partition(":")
    route, cond = route.strip().lower(), cond.strip()
    if not ROUTE.match(route):
        raise ValueError(f"route {route!r}: lowercase letters, digits, - and _")
    if cond.lower() in ("else", "*", "always"):
        return Rule(route, "else")
    for word in ("contains", "matches", "kind", "source", "event"):
        if cond.lower().startswith(word + " "):
            value = cond[len(word) + 1:].strip()
            if word == "matches":
                re.compile(value)
            return Rule(route, word, value=value)
    m = re.match(r"^([a-z_][a-z0-9_.]*)\s*(==|!=)\s*(.+)$", cond)
    if m:
        return Rule(route, "eq" if m.group(2) == "==" else "ne", m.group(1), m.group(3).strip().strip("\"'"))
    raise ValueError(f"cannot read {cond!r}: contains, matches, kind, source, event, field == value, else")


def rules_of(lines: list[str]) -> tuple[list[Rule], list[str]]:
    rules, problems = [], []
    for i, line in enumerate(lines, 1):
        try:
            rules.append(parse(line))
        except (ValueError, re.error) as e:
            problems.append(f"rule {i}: {e}")
    return rules, problems


def routes(lines: list[str]) -> list[str]:
    return list(dict.fromkeys(r.route for r in rules_of(lines)[0]))


def _field(payload, name: str) -> str:
    if name in FIELDS:
        return str(getattr(payload, "mode" if name == "event" else name, "") or "")
    try:
        data = json.loads(payload.value)
    except (ValueError, TypeError):
        return ""
    for part in name.split("."):
        data = data.get(part) if isinstance(data, dict) else None
    return "" if data is None else str(data)


def match(rule: Rule, payload) -> bool:
    hay = f"{payload.title}\n{payload.value}"
    if rule.how == "else":
        return True
    if rule.how == "contains":
        return rule.value.lower() in hay.lower()
    if rule.how == "matches":
        return re.search(rule.value, hay[:10_000]) is not None
    if rule.how == "kind":
        return payload.kind == rule.value
    if rule.how == "source":
        return payload.source == rule.value
    if rule.how == "event":
        return payload.mode == rule.value
    have = _field(payload, rule.field)
    return (have == rule.value) if rule.how == "eq" else (have != rule.value)


def route(rules: list[Rule], payload) -> str | None:
    return next((r.route for r in rules if match(r, payload)), None)
