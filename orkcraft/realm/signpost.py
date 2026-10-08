"""🚏 The Signpost: a crossroads post — rules send what arrives down one route.

A grot with a pointy stick stands at the crossroads and shouts "DIS WAY!": the post took over the
routing of the old Totem (whose name and look wait for a building of its own).

One rule per line, the first that matches wins:

    <route>: contains <text>          the title or value contains it (any case)
    <route>: matches <regex>          a regex over title and value
    <route>: kind <text|file|node>    the payload's kind
    <route>: source <building id>     where it came from
    <route>: event <event id>         which event brought it
    <route>: <field> == <value>       field: title, value, source, event, kind, or a key of a JSON value
    <route>: <field> != <value>
    <route>: else                     always (put it last)

The match goes out as `signpost.routed` with the route as its title; each road from the Signpost waits
for its own route (a road filter). Nothing matched → `signpost.unmatched`.

A rule may also name the kind of work its carts ask for (docs/design/barracks-flows.md §4), after the
route: `bugs, change: contains stack trace`. It is set on a cart that came with none; on a cart that
came with one it may only lower it (`pipes.least_want`), never give the path more rights.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from orkcraft.realm import pipes

ROUTE = re.compile(r"^[a-z0-9_-]{1,32}$")
FIELDS = ("title", "value", "source", "event", "kind")


@dataclass(frozen=True)
class Rule:
    route: str
    how: str              # contains | matches | kind | source | event | eq | ne | else
    field: str = ""
    value: str = ""
    want: str = ""        # the kind of work it names (pipes.WANTS), "" for none


def parse(line: str) -> Rule:
    head, _, cond = str(line).partition(":")
    route, _, want = head.partition(",")
    route, want, cond = route.strip().lower(), want.strip().lower(), cond.strip()
    if not ROUTE.match(route):
        raise ValueError(f"route {route!r}: lowercase letters, digits, - and _")
    if want and not pipes.want_of(want):
        raise ValueError(f"kind of work {want!r}: {', '.join(pipes.WANTS)}")
    if cond.lower() in ("else", "*", "always"):
        return Rule(route, "else", want=want)
    for word in ("contains", "matches", "kind", "source", "event"):
        if cond.lower().startswith(word + " "):
            value = cond[len(word) + 1:].strip()
            if word == "matches":
                re.compile(value)
            return Rule(route, word, value=value, want=want)
    m = re.match(r"^([a-z_][a-z0-9_.]*)\s*(==|!=)\s*(.+)$", cond)
    if m:
        return Rule(route, "eq" if m.group(2) == "==" else "ne", m.group(1), m.group(3).strip().strip("\"'"), want)
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


def pick(rules: list[Rule], payload) -> Rule | None:
    """The first rule that matches, else None."""
    return next((r for r in rules if match(r, payload)), None)


def route(rules: list[Rule], payload) -> str | None:
    r = pick(rules, payload)
    return r.route if r else None


def want(rule: Rule | None, payload) -> str:
    """The kind of work the cart goes on with: the rule's on a cart that came with none, else the one of the
    two whose path may do least (a rule never raises a cart's rights)."""
    came = pipes.want_of(getattr(payload, "want", ""))
    named = rule.want if rule else ""
    if not named:
        return came
    return pipes.least_want(came, named) if came else named
