"""The road planner: the operator says in words what a building should listen to, its steward lays the road.

    options = road_planner.plan(order, target, sources, scroll, runner)     # never raises
    options.ok → options.options: up to `MAX_OPTIONS` roads, each checked, the best first

Listen (+ on the receiver) knows only the target: the planner picks the source among `sources`, then the
event. A road drawn from one building to another knows both: `sources` holds just that one. What a
building sends and what it takes are its contract (`Source`, `Target`), data the core reads from the
catalog — the planner sees those, never the town's content.

An option is a plain road (an event, and a `match` filter at the source when only some carts should
go: "unread", "from my boss") or a road with a rule — `rule` says what the receiver's handler should
do with each cart, and the Recruiter makes that handler (realm/recruiter.py). New events are never
made up: a source sends only what its type declares (realm/catalog.py), a filter or a rule narrows it.

One `claude -p` call per attempt, in an empty folder, like the Town Builder. The answer is untrusted:
every option is checked here (the source, its events, the filter's regex) and on a copy of the scroll
(`scroll.subscribe`: a duplicate, a loop, too many roads). Options that fail are dropped; when none is
left the planner gets its problems back, up to `MAX_ATTEMPTS` times. Nothing is laid here.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field

from orkcraft import scroll as ts
from orkcraft.realm import builders

MAX_ATTEMPTS = 2
MAX_OPTIONS = 3
ORDER_LIMIT = 1500


@dataclass(frozen=True)
class Event:
    id: str                  # "mail.received", or "signpost.routed#urgent" (a road that waits for one route)
    label: str
    help: str = ""


@dataclass(frozen=True)
class Source:
    """A building that could send: what a plain road from it can carry, what a rule's handler can take."""
    id: str
    title: str
    summary: str = ""
    plain: tuple[Event, ...] = ()
    ruled: tuple[Event, ...] = ()


@dataclass(frozen=True)
class Target:
    id: str
    title: str
    takes: str = ""          # what a cart on a plain road makes it do (catalog.takes)


@dataclass
class Option:
    source: str
    event: str
    match: str = ""          # a regex at the source: only what matches leaves
    rule: str = ""           # what the receiver's handler does with each cart; "" — a plain road
    say: str = ""            # one sentence for the operator: "When …, …"

    @property
    def filter(self) -> dict:
        base, _, route = self.event.partition("#")
        flt: dict = {"route": [route]} if route else {}
        if self.match:
            flt["match"] = self.match
        return flt


@dataclass
class RoadPlan:
    options: list[Option] = field(default_factory=list)
    missing: str = ""        # nothing fits: what the town lacks, in the planner's words
    attempts: list[builders.Attempt] = field(default_factory=list)
    cost_usd: float | None = None
    error: str = ""

    @property
    def ok(self) -> bool:
        return bool(self.options)


PLANNER = """You are the steward of the building "{target}" in orkcraft, a harness where windows are
"buildings" on a town map and roads carry events ("carts") from one building to another. The operator
wants "{target}" to listen to something. Say how, from the buildings below.

WHAT THE OPERATOR WANTS:
{order}

"{target}" TAKES: {takes}

{sources_title}
{sources}

Give 1-{max_options} options, the best first. Each is one road from one source, on one of its events:
- a PLAIN road: "event" is one of the source's "plain" events; the cart arrives as is. When only some
  carts should go, add "match": a Python regex searched in the cart's title and text (e.g. "(?i)urgent").
- a road with a RULE: when the carts must be read, judged, rewritten or sorted on the way, "event" is one
  of the source's "rule" events and "rule" says, in one or two sentences, what the handler of "{target}"
  does with each cart. Leave "match" out then.
Never invent an event: only the ones listed. "say" tells the operator in one plain sentence what will
happen: "When <the source> <does what>, <the target> <does what>." Write "say" and "rule" in the
operator's language.
If nothing listed can do it, give no options and say in "missing" what building or setting is lacking.
{feedback}
Answer with ONE JSON object and nothing else:
{{"options": [{{"from": "<source id>", "event": "...", "match": "<regex, or leave out>",
               "rule": "<what the handler does, or leave out>", "say": "..."}}],
  "missing": "<only when there are no options>"}}"""


def _events_text(events: tuple[Event, ...]) -> str:
    return "; ".join(f"{e.id} ({e.label}{': ' + e.help if e.help else ''})" for e in events) or "none"


def sources_text(sources: list[Source]) -> str:
    return "\n".join(f'- id "{s.id}": {s.title}' + (f" — {s.summary}" if s.summary else "")
                     + f"\n  plain: {_events_text(s.plain)}\n  rule: {_events_text(s.ruled)}" for s in sources)


def check(answer: dict, target: Target, sources: list[Source],
          scroll: ts.TownScroll | None) -> tuple[list[Option], str, list[str]]:
    """(the options that hold, missing, the problems of the rest)."""
    by_id = {s.id: s for s in sources}
    raw = answer.get("options")
    raw = raw if isinstance(raw, list) else []
    options: list[Option] = []
    errors: list[str] = []
    for n, o in enumerate(raw[:MAX_OPTIONS * 2], 1):
        if not isinstance(o, dict):
            errors.append(f"option {n}: not an object")
            continue
        src = by_id.get(str(o.get("from") or ""))
        event, match = str(o.get("event") or "").strip(), str(o.get("match") or "").strip()
        rule, say = str(o.get("rule") or "").strip()[:600], str(o.get("say") or "").strip()[:300]
        if src is None:
            errors.append(f"option {n}: {o.get('from')!r} is not one of the sources")
            continue
        events = src.ruled if rule else src.plain
        if event not in {e.id for e in events}:
            kind = "rule" if rule else "plain"
            errors.append(f"option {n}: {src.title} sends no {kind} event {event!r} (its {kind} events: "
                          f"{', '.join(e.id for e in events) or 'none'})")
            continue
        if rule:
            match = ""                                # the rule decides what it takes
        opt = Option(src.id, event, match, rule, say or f"{src.title} → {target.title}")
        if problems := ts.filter_problems(opt.filter):
            errors.append(f"option {n}: match: {'; '.join(problems)}")
            continue
        if not rule and scroll is not None:           # a plain road must hold in the town as it is
            try:
                ts.subscribe(copy.deepcopy(scroll), target.id, src.id, event.partition("#")[0], opt.filter,
                             label=event.partition("#")[2])
            except ValueError as e:
                errors.append(f"option {n}: {e}")
                continue
        if any((x.source, x.event, x.match, x.rule) == (opt.source, opt.event, opt.match, opt.rule) for x in options):
            continue
        options.append(opt)
    missing = "" if options else str(answer.get("missing") or "").strip()[:400]
    return options[:MAX_OPTIONS], missing, errors


def plan(order: str, target: Target, sources: list[Source], scroll: ts.TownScroll | None = None,
         runner: builders.Runner = builders.main_runner, max_attempts: int = MAX_ATTEMPTS) -> RoadPlan:
    """Ask until at least one option holds or the attempts run out. Never raises."""
    order = order.strip()[:ORDER_LIMIT]
    if not order:
        return RoadPlan(error="say what it should listen to")
    sources = [s for s in sources if s.id != target.id and (s.plain or s.ruled)]
    if not sources:
        return RoadPlan(error=f"no building can send anything to {target.title}")
    title = "THE SOURCE (the operator drew the road from it):" if len(sources) == 1 else \
        "THE BUILDINGS THAT COULD SEND (pick the source among them):"
    attempts: list[builders.Attempt] = []
    total: float | None = None
    for _ in range(max_attempts):
        attempt = builders.Attempt()
        try:
            text, cost = runner(PLANNER.format(target=target.title, order=order, takes=target.takes or "anything",
                                               sources_title=title, sources=sources_text(sources),
                                               max_options=MAX_OPTIONS, feedback=builders._feedback(attempts)))
        except RuntimeError as e:
            attempts.append(attempt)
            return RoadPlan(attempts=attempts, cost_usd=total, error=str(e))
        if cost is not None:
            total = (total or 0.0) + cost
        attempt.mason = text
        answer = builders.extract_json(text)
        if answer is None:
            attempt.errors = ["the answer had no JSON object"]
            attempts.append(attempt)
            continue
        options, missing, attempt.errors = check(answer, target, sources, scroll)
        attempts.append(attempt)
        if options or (missing and not attempt.errors):
            return RoadPlan(options, missing, attempts, total)
    return RoadPlan(attempts=attempts, cost_usd=total,
                    error="no road passed the checks: " + "; ".join((attempts[-1].errors if attempts else [])[:3]))
