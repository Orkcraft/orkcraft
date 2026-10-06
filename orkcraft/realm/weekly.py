"""🗓 The Town retro (the weekly self-audit): a heavy model looks over the whole camp once a week.

    when     `weekly_at` (Sunday 05:00 by default, the operator's morning window) or F10 on demand
    model    `claude -p --model <weekly_model>` (opus by default, the operator's subscription)
    sees     the rules audit, the week's spend per building, 👍 / 👎 and incidents, the Council's
             reviews, every building's type, settings and model prompts, the roads
    answers  a report: a summary and items. An item is applied only through one of these changes,
             each checked like everything else in the camp:
                 shrink · chain · script   a model part, as in the local proposals (realm/optimize.py)
                 set_config                one setting of a building (the spec is checked again)
                 remove_road               a road nobody needs
                 remove_building           a building nobody needs (demolished; Z / P bring it back)
                 add_building              a camp building from the catalog (a preset: no model)
                 note                      advice only — nothing to apply
The report may also ask for a restart (`restart: true`) — offered after Apply.
The operator ticks the items, Apply makes the changes one by one — each a checkpoint
`weekly(<id>)` in the camp's git, so Z takes any building back — saves the Town Scroll and restarts
the daemons (webhooks, schedules) of the buildings it touched. Reports stay in `.orkcraft/weekly/`.
"""
from __future__ import annotations

import datetime as dt
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from orkcraft.realm import builders, catalog, feedback, metrics, optimize

DIR = Path(".orkcraft") / "weekly"
CHANGES = ("shrink", "chain", "script", "enrich", "set_config", "remove_road", "remove_building", "add_building", "note")
CONTEXT_LIMIT = 24_000
GOALS = {"thrift": "🪙 thrift", "balance": "⚖️ balance", "quality": "💎 quality"}

PROMPT = """You are the Council of orkcraft doing the WEEKLY self-audit of the operator's camp: a terminal
harness where buildings pass events along roads to scripts, chains and agents. Find what to make cheaper,
safer, simpler or more useful — at most 8 items, the most valuable first. Prefer scripts and chains over models.
Each building has a goal: 🪙 thrift (make it cheaper), ⚖️ balance, 💎 quality (make its results better; it may
spend more) — work towards it: never make a 💎 building cheaper at the cost of its liked results.

THE CAMP:
{camp}

Each item applies ONE change:
- {{"change": "shrink", "building": id, "target": "orc:<id>|steward|orders", "prompt": "<at most 70% as long>"}}
- {{"change": "chain", "building": id, "target": "orc:<id>", "chain": [chain ops]}}   (an agent that needs no judgement)
- {{"change": "script", "building": id, "target": "steward", "script": "<python: stdin cart JSON, exit 0/4, never 3>"}}
- {{"change": "enrich", "building": id, "target": "orc:<id>|steward|orders", "prompt": "<a better prompt: longer, at most twice as long>"}}
  (only for ⚖️ and 💎 buildings)
- {{"change": "set_config", "building": id, "key": "<a setting of its type>", "value": <value>}}
- {{"change": "remove_road", "building": id, "road": "<road id>"}}
- {{"change": "remove_building", "building": id}}   (nobody uses it: no runs, no roads, no 👍)
- {{"change": "add_building", "building": "<new snake_case id>", "type": "<a camp type>", "title": "<title>", "config": {{…}}}}
  camp types: {types}
- {{"change": "note", "building": id or ""}}   (advice only, nothing to apply)
Chain ops: filter (field, cmp eq|ne|in|contains|matches, value), pick (fields), extract (field, regex, as),
sort (by, desc), limit (n), count (as), group (by), template (md with {{field}}), join (sep).
Answer with ONE JSON object and nothing else:
{{"summary": "<two or three sentences>", "restart": false,
  "items": [{{"title": "<short>", "why": "<one sentence>", ...the change...}}]}}"""


@dataclass
class Item:
    n: int
    title: str
    why: str
    change: str
    building: str = ""
    data: dict = field(default_factory=dict)      # the change's own fields
    problems: list[str] = field(default_factory=list)
    after: str = ""                               # the checked new text (shrink, chain, script)
    before: str = ""

    @property
    def applicable(self) -> bool:
        return self.change != "note" and not self.problems


@dataclass
class Report:
    ts: str
    summary: str
    items: list[Item] = field(default_factory=list)
    model: str = ""
    cost_usd: float | None = None
    applied: list[int] = field(default_factory=list)
    declined: list[int] = field(default_factory=list)   # items the operator said no to: never applied by the orks
    restart: bool = False
    surveyed: bool = False                        # the Town retro's survey was shown (realm/retro.py)


@dataclass
class Result:
    report: Report | None = None
    error: str = ""


# -- what the model sees -----------------------------------------------------------------------------

def camp_text(repo_root: Path, scroll, specs: dict[str, dict], audit_report=None, now: dt.datetime | None = None) -> str:
    now = now or dt.datetime.now()
    week = metrics._read(repo_root / metrics.LEDGER, now - dt.timedelta(days=7))
    spent: dict[str, list[float]] = {}
    for row in week:
        s = spent.setdefault(str(row.get("building") or ""), [0, 0.0, 0])
        s[0] += int(row.get("tokens") or 0)
        s[1] += float(row.get("cost") or 0.0)
        s[2] += 1
    scores = feedback.scores(repo_root)
    lines = []
    for b in scroll.buildings:
        if b.demolished:
            continue
        spec = specs.get(b.id)
        kind = catalog.type_of(spec).id if spec else "preset"
        tok, cost, runs = spent.get(b.id, [0, 0.0, 0])
        sc = scores.get(b.id, {})
        goal = getattr(b, "aim", "balance")
        lines.append(f"## {b.id} — {b.title} ({kind}) · goal: {GOALS.get(goal, goal)} · week: {runs} runs, {tok} tokens, ${cost:.2f} · "
                     f"👍 {sc.get('likes', 0)} 👎 {sc.get('dislikes', 0)} penalty {sc.get('penalty', 0)}"
                     + (f" · by what the operator did: liked {sc.get('liked', 0):g}, disliked {sc.get('disliked', 0):g} "
                        f"({', '.join(f'{k} {v:+g}' for k, v in sorted(sc['by'].items()))})" if sc.get("by") else ""))
        if spec and spec.get("config"):
            lines.append("settings: " + json.dumps(spec["config"], ensure_ascii=False)[:800])
        for r in b.roads:
            lines.append(f"road {r.id}: from {r.source} on {r.event}" + (f" → handler {r.handler}" if r.handler else ""))
        for p in optimize.parts(scroll, spec, b.id, repo_root):
            lines.append(f"[{p.id}] prompt: {p.text[:1200]}")
            if p.script:
                lines.append(f"  script: {p.script[:1500]}")
        logs = optimize.run_logs(repo_root, b.id, 3)
        if logs:
            lines.append("recent runs:")
            lines += logs
    incs = feedback.incidents(repo_root, 10)
    if incs:
        lines.append("\n## incidents (👎)")
        lines += [f"- {i.building} · {i.kind}" + ("" if i.source == feedback.EXPLICIT else f" ({i.source}, ×{i.weight:g})")
                  + (f" → blamed: {', '.join(f'{b} {p:g}' for b, p in i.blamed.items())}" if i.blamed else "")
                  + f": {i.note or '(no note)'}" for i in incs]
    if audit_report is not None:
        lines.append("\n## the rules audit")
        lines += [f"- {f.agent}: {f.text}" for f in audit_report.findings[:20]]
    return "\n".join(lines)[:CONTEXT_LIMIT]


# -- checking an item --------------------------------------------------------------------------------

def check_item(item: Item, repo_root: Path, scroll, specs: dict[str, dict]) -> Item:
    from orkcraft.realm import masonry, workshop
    b = scroll.building(item.building) if item.building else None
    if item.change not in CHANGES:
        item.problems = [f"unknown change {item.change!r}"]
        return item
    if item.change == "note":
        return item
    if item.change == "add_building":
        tid = str(item.data.get("type") or "")
        t = catalog.TYPES.get(tid)
        if t is None or tid in catalog.SYSTEM_TYPES | catalog.SCRATCH_TYPES or tid == catalog.DEFAULT_TYPE:
            item.problems = [f"type: one of the camp's ({', '.join(camp_types())})"]
            return item
        spec = new_spec(item)
        taken = {x.id for x in scroll.buildings} | set(specs)
        item.problems = masonry.validate_spec(spec, repo_root, taken)[:3]
        item.after = json.dumps(spec, ensure_ascii=False)
        return item
    if b is None:
        item.problems = [f"no building {item.building!r}"]
        return item
    spec = specs.get(item.building)
    if item.change in optimize.ACTIONS:
        ps = optimize.parts(scroll, spec, item.building, repo_root)
        part = next((p for p in ps if p.id == item.data.get("target")), None)
        cfg = (spec or {}).get("config") or {}
        mocks = workshop.load_blueprint(repo_root, item.building).get("mocks") or []
        after, problems = optimize.check({"action": item.change, **item.data}, ps, item.building, repo_root,
                                         str(cfg.get("runtime") or "python"), mocks,
                                         optimize.GOAL_ACTIONS.get(getattr(b, "aim", "balance"), optimize.ACTIONS))
        item.after, item.problems, item.before = after, problems, part.text if part else ""
        return item
    if item.change == "remove_road":
        if b.road(str(item.data.get("road") or "")) is None:
            item.problems = [f"{item.building} has no road {item.data.get('road')!r}"]
        return item
    if item.change == "remove_building":
        if item.building == "town_hall" or b.demolished:
            item.problems = ["the Town Hall stays" if item.building == "town_hall" else "it is demolished already"]
        return item
    # set_config
    if spec is None:
        item.problems = ["only a camp building's settings can change"]
        return item
    key = str(item.data.get("key") or "")
    new = dict(spec, config={**(spec.get("config") or {}), key: item.data.get("value")})
    item.problems = masonry.validate_spec(new, repo_root, set(specs) - {item.building})[:3]
    item.before = json.dumps((spec.get("config") or {}).get(key), ensure_ascii=False)
    item.after = json.dumps(item.data.get("value"), ensure_ascii=False)
    return item


def camp_types() -> list[str]:
    return [t for t in catalog.TYPES if t not in catalog.SYSTEM_TYPES | catalog.SCRATCH_TYPES and t != catalog.DEFAULT_TYPE]


def new_spec(item: Item) -> dict:
    """An add_building item as a spec (a preset: the type's defaults, the item's title and settings)."""
    t = catalog.TYPES[str(item.data.get("type"))]
    spec = {"id": item.building, "type": t.id, "title": str(item.data.get("title") or t.title)[:40], "icon": t.icon,
            "summary": (item.why or t.summary)[:200], "orc": {"name": t.orc, "role": t.preview[:80]}}
    if isinstance(item.data.get("config"), dict) and item.data["config"]:
        spec["config"] = dict(item.data["config"])
    return spec


def parse(data: dict, repo_root: Path, scroll, specs: dict[str, dict]) -> list[Item]:
    items = []
    for n, raw in enumerate((data.get("items") or [])[:8], 1):
        if not isinstance(raw, dict):
            continue
        fields = {k: v for k, v in raw.items() if k not in ("title", "why", "change", "building")}
        item = Item(n, str(raw.get("title") or "")[:80], str(raw.get("why") or "")[:300], str(raw.get("change") or ""),
                    str(raw.get("building") or ""), fields)
        items.append(check_item(item, repo_root, scroll, specs))
    return items


def run(repo_root: Path, scroll, specs: dict[str, dict], runner: builders.Runner, model: str = "",
        audit_report=None) -> Result:
    """One heavy-model call; never raises."""
    prompt = PROMPT.format(camp=camp_text(repo_root, scroll, specs, audit_report), types=", ".join(camp_types()))
    try:
        text, cost = runner(prompt)
    except Exception as e:  # the CLI missing, a timeout
        return Result(error=str(e)[:300])
    data = builders.extract_json(text)
    if data is None:
        return Result(error="the audit did not answer with a JSON report")
    report = Report(dt.datetime.now().isoformat(timespec="seconds"), str(data.get("summary") or "")[:1000],
                    parse(data, repo_root, scroll, specs), model, cost, restart=bool(data.get("restart")))
    save(repo_root, report)
    return Result(report)


# -- the reports -------------------------------------------------------------------------------------

def save(repo_root: Path, report: Report) -> Path:
    path = repo_root / DIR / f"{report.ts[:10]}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(report), ensure_ascii=False, indent=1), encoding="utf-8")
    return path


def latest(repo_root: Path) -> Report | None:
    files = sorted((repo_root / DIR).glob("[0-9]*.json"))
    if not files:
        return None
    try:
        data = json.loads(files[-1].read_text(encoding="utf-8"))
        data["items"] = [Item(**i) for i in data.get("items", [])]
        return Report(**data)
    except (OSError, ValueError, TypeError):
        return None


def last_run(repo_root: Path) -> dt.datetime | None:
    try:
        return dt.datetime.fromisoformat(json.loads((repo_root / DIR / "last.json").read_text(encoding="utf-8"))["at"])
    except (OSError, ValueError, KeyError, TypeError):
        return None


def mark_run(repo_root: Path, now: dt.datetime | None = None) -> None:
    path = repo_root / DIR / "last.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"at": (now or dt.datetime.now()).isoformat(timespec="seconds")}), encoding="utf-8")
