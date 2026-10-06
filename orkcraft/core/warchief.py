"""The Warchief's orders (docs/design/calm-town.md §5–§7): it does not build. It understands what the
person wants, gives the work to the specialist who does it, and brings back what they made as a card in
its chat. Its answer ends with at most one line that says which:

    DO: {"plan": "<order>"}                                  the Town Builder plans buildings and roads
    DO: {"build": "<type id>"}                               one building of the catalog, no model
    DO: {"road": "<into id>", "from": "<from id>", "order": "<what it carries>"}   the road planner
    DO: {"recruit": "<building id>", "order": "<what the ork does>"}             the Recruiter
    DO: {"keeper": "<building id>", "order": "<the change>"}                     the building's keeper

The first two are the town's own (here, faceless): a plan is made in a thread and reviewed by the
Council's rules, then it waits on its card — Build, Change (talk on), Cancel — or, when the town is
unchained, it is raised at once and the card offers Undo. The other three are a face's jobs (the GUI's
console: their offer opens when ready and the person takes it there): the order goes out on the bus
(`bus.ORDER`) and the card says who has it.

A card: {id, kind, state, steps, …}; its state is working → ready → done (→ undone), or dropped, failed,
sent (a face's job). An old answer's `BUILD: <type>` line still reads as a build.
"""
from __future__ import annotations

import itertools
import json
import re
import time
from typing import Any

from orkcraft.realm import catalog, fastpath

DO_LINE = re.compile(r"^\s*DO:\s*(\{.*\})\s*$", re.M)
BUILD_LINE = re.compile(r"^\s*BUILD:\s*([a-z_]+)\s*$", re.M)
KINDS = ("plan", "build", "road", "recruit", "keeper")
FACE_KINDS = ("road", "recruit", "keeper")       # a face runs these as its jobs
ORDER_LIMIT = 2000

# Who does each order: the step a card shows while it works.
WHO = {"plan": "Town Builder", "build": "Foreman", "road": "Road planner", "recruit": "Recruiter", "keeper": "keeper"}

PROMPT = """
When the person wants something done, you do not do it yourself: you give it to the specialist who does,
with one last line `DO: <one JSON object>`, and you say in a sentence what you gave to whom. One of:
- `{{"plan": "<the order, in the person's words and what you know of the town>"}}` — the Town Builder plans
  several buildings and the roads between them (a new flow, a whole job);
- `{{"build": "<type id>"}}` — one building of the catalog, as it comes;
- `{{"road": "<id of the building it goes into>", "from": "<id it comes from, or empty>", "order": "<what it
  should carry and what happens to it>"}}` — the road planner lays a road;
- `{{"recruit": "<building id>", "order": "<what the ork should do>"}}` — the Recruiter hires an ork there;
- `{{"keeper": "<building id>", "order": "<the change to its rules or settings>"}}` — its keeper changes it.
Only ids of the town above and types of the catalog. A question is answered, not delegated: then no DO line.
{about}"""

_ids = itertools.count(1)


def about_text(town, ids: list[str]) -> str:
    """The buildings the person pointed at (chips in the line), for the Warchief's prompt."""
    named = [(i, town.scroll.building(i)) for i in ids]
    lines = [f"- {i} · {bs.title}" for i, bs in named if bs is not None and not bs.demolished]
    return ("The person points at:\n" + "\n".join(lines) + "\n") if lines else ""


def parse(answer: str, types: set[str], buildings: set[str]) -> tuple[str, dict | None]:
    """The answer without its DO line, and the order it gives (None: a plain answer, or one that names
    what does not exist — an order is never made up)."""
    found = DO_LINE.findall(answer)
    text = BUILD_LINE.sub("", DO_LINE.sub("", answer)).strip()
    if not found:
        old = BUILD_LINE.findall(answer)
        return text, ({"kind": "build", "type": old[-1]} if old and old[-1] in types else None)
    try:
        data = json.loads(found[-1])
    except ValueError:
        return text, None
    if not isinstance(data, dict):
        return text, None
    kind = next((k for k in KINDS if k in data), None)
    if kind is None:
        return text, None
    what = str(data.get(kind) or "").strip()
    words = str(data.get("order") or "").strip()[:ORDER_LIMIT]
    if kind == "plan":
        return text, ({"kind": "plan", "order": what[:ORDER_LIMIT]} if what else None)
    if kind == "build":
        what = catalog.ALIASES.get(what, what)
        return text, ({"kind": "build", "type": what} if what in types else None)
    if what not in buildings or not words:
        return text, None
    order = {"kind": kind, "building": what, "order": words}
    source = str(data.get("from") or "").strip()
    if kind == "road" and source in buildings and source != what:
        order["source"] = source
    return text, order


def card(order: dict) -> dict:
    """A new card for an order: the step its specialist takes, working."""
    c = {"id": f"c{int(time.time())}-{next(_ids)}", **order,
         "state": "sent" if order["kind"] in FACE_KINDS else "working",
         "steps": [{"who": WHO[order["kind"]], "state": "working"}]}
    if order["kind"] == "build":
        c["state"], c["steps"] = "ready", []          # the catalog's own defaults: nothing to make
    return c


def review(town, specs: list[dict], runner=None) -> tuple[list[str], list[str]]:
    """The Council's Fast Path over what a plan raises: (what blocks it, what it warns of)."""
    blocks, warns = [], []
    existing = town.taken_ids()
    for spec in specs:
        v = fastpath.review(fastpath.Subject("building", spec["id"], spec), town.repo_root, existing, runner=runner)
        title = spec.get("title", spec["id"])
        blocks += [f"{title}: {n.text}" for n in v.notes if n.severity == "block"]
        warns += [f"{title}: {n.text}" for n in v.notes if n.severity in ("warn", "object")]
    return blocks, warns


def public(c: dict, titles: dict[str, str]) -> dict[str, Any]:
    """What a face draws of a card: no specs, only what the person reads."""
    out = {k: c[k] for k in ("id", "kind", "state", "steps") if k in c}
    for k in ("order", "type", "error", "cost", "notes"):
        if c.get(k):
            out[k] = c[k]
    if c.get("building"):
        out["building"], out["building_title"] = c["building"], titles.get(c["building"], c["building"])
    if c.get("source"):
        out["source_title"] = titles.get(c["source"], c["source"])
    if c["kind"] == "build":
        t = catalog.TYPES.get(c.get("type", ""))
        out["type_title"] = t.title if t else c.get("type", "")
    if c.get("plan"):
        out["plan"] = c["plan"]
    if c.get("made"):
        out["made"] = [titles.get(i, i) for i in c["made"].get("buildings", [])]
    return out
