"""The Builder: the operator's interview becomes a script-first blueprint.

    interview  {"purpose", "layout": log|table|card, "inputs": ["source:event", …], "events": [...]}
    blueprint  {"id", "title", "icon", "summary", "runtime": python|bash, "script",
                "steward_prompt", "steward_why", "mocks": [cart, …], "layout", "inputs", "events"}

One `claude -p` call per attempt, in an empty folder, like Mason: the Builder sees the interview
and the contract below, never the graph. Its answer is untrusted: only a blueprint that passes
`problems` goes on — to the Council, then the sandbox (realm/workshop.py), then the operator.
A steward prompt is written only when a script cannot do the job, and says why.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from orkcraft.realm import builders, workshop

MAX_ATTEMPTS = 3
SCRIPT_LIMIT = 20_000
ID = re.compile(r"^[a-z][a-z0-9_]{1,31}$")

BUILDER = """You are the Builder of orkcraft, a terminal harness where windows ("buildings") pass events
("carts") along roads. The operator wants a NEW building. Write its logic as a small SCRIPT first.

WHAT THE OPERATOR WANTS:
{purpose}

It shows its results as: {layout} ({layout_help})
Carts will arrive from: {inputs}
It may send: {events}

THE SCRIPT CONTRACT
- stdin: one cart as JSON {{"event": "...", "source": "<building id>", "title": "...", "value": "<text>"}}
- stdout: the result — plain text, a JSON object (shown as a card) or a JSON list of objects (a table)
- exit 0 = done · exit 4 = alert (done, but the operator should look) · exit 3 = the script cannot
  decide and hands the cart to the steward prompt · anything else = failed
- python3 (standard library only) or bash with coreutils / jq; no network, no sudo, no writes outside
  the current folder, no eval; short and readable (under 120 lines)

THE STEWARD PROMPT: only when part of the job needs judgement a script cannot have (summarising free
text, classifying intent…). Then the script exits 3 for those carts and "steward_prompt" says what the
model should do; "steward_why" says why a script is not enough. Otherwise leave both empty.

Its own timer: when it should also run without a cart, give "schedule" (`every 15m`, `hourly`, `daily 05:00`,
`weekly mon 09:00` or a 5-field cron) — then a cart {{"event": "workshop.tick", "source": "<its id>", "value":
"<ISO time>"}} arrives on schedule; otherwise leave it empty. Wanted: {schedule}.

Also write 2-4 realistic mock carts that exercise the script (one of them an edge case).
{feedback}
Answer with ONE JSON object and nothing else:
{{"id": "<snake_case, 2-32 chars>", "title": "<plain functional title, max 32 chars>", "icon": "<one emoji>",
  "summary": "<one sentence>", "runtime": "python|bash", "script": "<the whole script>",
  "steward_prompt": "", "steward_why": "", "schedule": "", "mocks": [{{"event": "...", "source": "...", "title": "", "value": "..."}}]}}"""

LAYOUT_HELP = {"log": "a list of runs, newest first, each with its output",
               "table": "a table built from a JSON list of objects",
               "card": "one card with the latest result's fields"}


@dataclass
class Attempt:
    answer: str = ""
    errors: list[str] = field(default_factory=list)


@dataclass
class Result:
    blueprint: dict | None = None
    attempts: list[Attempt] = field(default_factory=list)
    cost_usd: float | None = None
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.blueprint is not None


def problems(bp: dict, taken: set[str] | frozenset[str] = frozenset()) -> list[str]:
    errors = []
    bid = str(bp.get("id") or "")
    if not ID.match(bid):
        errors.append("id: snake_case, 2-32 chars, starting with a letter")
    elif bid in taken:
        errors.append(f"id: {bid} is taken — pick another")
    if not str(bp.get("title") or "").strip() or len(str(bp.get("title"))) > 40:
        errors.append("title: 1-40 chars")
    runtime = bp.get("runtime")
    if runtime not in workshop.RUNTIMES:
        errors.append("runtime: python or bash")
    script = str(bp.get("script") or "")
    if len(script) > SCRIPT_LIMIT:
        errors.append(f"script: longer than {SCRIPT_LIMIT} chars")
    elif runtime in workshop.RUNTIMES and (why := workshop.check_syntax(script, runtime)):
        errors.append(f"script: {why}")
    mocks = bp.get("mocks")
    if not isinstance(mocks, list) or not 1 <= len(mocks) <= 6 or not all(isinstance(m, dict) for m in mocks):
        errors.append("mocks: 1-6 cart objects")
    if bp.get("steward_prompt") and not str(bp.get("steward_why") or "").strip():
        errors.append("steward_why: say why a script is not enough, or drop the steward prompt")
    if len(str(bp.get("steward_prompt") or "")) > 2000:
        errors.append("steward_prompt: at most 2000 chars")
    if bp.get("schedule"):
        from orkcraft.realm import watch
        if not watch.schedule_ok(str(bp["schedule"])):
            errors.append("schedule: `every 15m`, `hourly`, `daily 05:00`, `weekly mon 09:00`, a 5-field cron, or empty")
    return errors


def normalise(bp: dict, interview: dict) -> dict:
    out = {k: bp.get(k) for k in ("id", "title", "icon", "summary", "runtime", "script", "steward_prompt",
                                   "steward_why", "mocks", "schedule")}
    out["icon"] = str(out.get("icon") or "🛠️")[:4]
    out["summary"] = str(out.get("summary") or interview.get("purpose", ""))[:200]
    out["steward_prompt"] = str(out.get("steward_prompt") or "").strip()
    out["steward_why"] = str(out.get("steward_why") or "").strip()
    out["mocks"] = [workshop.cart(str(m.get("event", "")), str(m.get("source", "")), str(m.get("value", "")),
                                  str(m.get("title", ""))) for m in (out.get("mocks") or []) if isinstance(m, dict)]
    out["layout"] = interview.get("layout") if interview.get("layout") in workshop.LAYOUTS else "log"
    out["inputs"] = list(interview.get("inputs") or [])
    out["events"] = list(interview.get("events") or ["workshop.done", "workshop.failed"])
    out["purpose"] = str(interview.get("purpose") or "")
    out["schedule"] = str(interview.get("schedule") or bp.get("schedule") or "").strip()
    return out


def to_spec(bp: dict) -> dict:
    """The building's spec: a Workshop that runs the blueprint's script."""
    config = {"runtime": bp["runtime"], "layout": bp.get("layout") or "log"}
    if bp.get("steward_prompt"):
        config["steward_prompt"] = bp["steward_prompt"]
    if bp.get("inputs"):
        config["inputs"] = list(bp["inputs"])
    if bp.get("schedule"):
        config["schedule"] = bp["schedule"]
    return {"id": bp["id"], "type": "workshop", "title": bp["title"], "icon": bp.get("icon") or "🛠️",
            "summary": bp.get("summary") or "", "orc": {"name": "Tinker", "role": (bp.get("summary") or "")[:80]},
            "events": list(bp.get("events") or ["workshop.done", "workshop.failed"]),
            "quick_actions": ["workshop.run", "workshop.test"], "config": config}


def _feedback(attempts: list[Attempt], operator: str) -> str:
    parts = []
    if operator.strip():
        parts.append(f"THE OPERATOR REJECTED THE LAST BLUEPRINT AND SAYS:\n{operator.strip()[:1500]}")
    if attempts and attempts[-1].errors:
        parts.append("YOUR LAST ANSWER HAD THESE PROBLEMS — fix them:\n" + "\n".join(f"- {e}" for e in attempts[-1].errors))
    return ("\n" + "\n\n".join(parts) + "\n") if parts else ""


def build(interview: dict, taken: set[str] | frozenset[str] = frozenset(), runner: builders.Runner = builders.claude_runner,
          feedback: str = "", previous: dict | None = None, max_attempts: int = MAX_ATTEMPTS) -> Result:
    """The Builder's blueprint for `interview`. Never raises; blocking (one model call per attempt)."""
    result = Result()
    inputs = ", ".join(interview.get("inputs") or []) or "roads the operator will add later"
    events = ", ".join(interview.get("events") or ["workshop.done", "workshop.failed"])
    layout = interview.get("layout") if interview.get("layout") in workshop.LAYOUTS else "log"
    purpose = str(interview.get("purpose") or "")[:builders.PROMPT_LIMIT]
    extra = feedback
    if previous and feedback:
        extra = feedback + "\n\nTHE REJECTED SCRIPT:\n" + str(previous.get("script") or "")[:6000]
    for _ in range(max_attempts):
        prompt = BUILDER.format(purpose=purpose, layout=layout, layout_help=LAYOUT_HELP[layout], inputs=inputs,
                                events=events, feedback=_feedback(result.attempts, extra),
                                schedule=interview.get("schedule") or "none said")
        try:
            text, cost = runner(prompt)
        except Exception as e:  # the CLI missing, a timeout
            result.error = str(e)[:300]
            return result
        if cost is not None:
            result.cost_usd = (result.cost_usd or 0.0) + cost
        attempt = Attempt(text[:8000])
        result.attempts.append(attempt)
        data = builders.extract_json(text)
        if data is None:
            attempt.errors = ["answer with ONE JSON object"]
            continue
        attempt.errors = problems(data, taken)
        if not attempt.errors:
            result.blueprint = normalise(data, interview)
            return result
    return result


# -- the conversation: the Builder asks until it knows enough ---------------------

TALK = """You are the Builder of orkcraft, a terminal harness where windows ("buildings") pass events
("carts") along roads. The operator wants a NEW building; its logic will be a script. Talk with the
operator until you know at least: (1) what it does, (2) how it should look — offer THREE different
views, (3) which carts it takes, (4) which events it sends. Ask only what you cannot infer, at most 3
short questions per turn, in the operator's language.

BUILDINGS THAT CAN FEED IT ("source:event"):
{sources}

EVENTS IT MAY SEND: workshop.done (its output), workshop.failed (an error), workshop.alert (a flagged output)
VIEWS: log (a list of runs), table (rows from a JSON list), card (the fields of the latest result)

THE CONVERSATION SO FAR:
{history}

Answer with ONE JSON object and nothing else — either more questions:
{{"questions": ["...", "..."]}}
or, when you know enough:
{{"ready": true, "purpose": "<one paragraph: what comes in, what it finds or makes, when it alerts>",
  "views": [{{"name": "<short>", "layout": "log|table|card", "preview": "<up to 6 lines: how it looks>"}}, … three …],
  "inputs": ["source:event", …], "events": ["workshop.done", …],
  "schedule": "<empty, or when it should also run on its own: every 15m | hourly | daily 05:00 | weekly mon 09:00>"}}"""

MAX_TURN_ATTEMPTS = 2


@dataclass
class Turn:
    questions: list[str] = field(default_factory=list)
    ready: bool = False
    purpose: str = ""
    views: list[dict] = field(default_factory=list)
    inputs: list[str] = field(default_factory=list)
    events: list[str] = field(default_factory=list)
    schedule: str = ""
    error: str = ""
    cost_usd: float | None = None


EVENT_IDS = ("workshop.done", "workshop.failed", "workshop.alert")


def _turn_problems(data: dict, sources: set[str]) -> list[str]:
    if data.get("questions") and not data.get("ready"):
        qs = data["questions"]
        return [] if isinstance(qs, list) and all(isinstance(q, str) and q.strip() for q in qs) else \
            ["questions: a list of short questions"]
    problems = []
    views = data.get("views")
    if not isinstance(views, list) or len(views) != 3 or not all(
            isinstance(v, dict) and v.get("layout") in workshop.LAYOUTS and str(v.get("name") or "").strip() for v in views):
        problems.append("views: exactly three {name, layout: log|table|card, preview}")
    if not str(data.get("purpose") or "").strip():
        problems.append("purpose: one paragraph")
    bad_in = [i for i in data.get("inputs") or [] if i not in sources]
    if bad_in:
        problems.append(f"inputs: only these — {', '.join(sorted(sources)) or 'none (leave it empty)'}; not {', '.join(bad_in)}")
    events = data.get("events") or []
    if not events or any(e not in EVENT_IDS for e in events):
        problems.append(f"events: some of {', '.join(EVENT_IDS)}")
    if data.get("schedule"):
        from orkcraft.realm import watch
        if not watch.schedule_ok(str(data["schedule"])):
            problems.append("schedule: every 15m | hourly | daily 05:00 | weekly mon 09:00 | a 5-field cron | empty")
    return problems


def talk(history: list[tuple[str, str]], sources: list[tuple[str, str]], runner: builders.Runner) -> Turn:
    """The Builder's next turn: questions, or the facts of the building with three views. Never raises."""
    offered = {value for value, _ in sources}
    lines = "\n".join(f"{who}: {text}" for who, text in history[-30:])[:8000]
    base = TALK.format(sources="\n".join(f"- {v} ({label})" for v, label in sources) or "- none yet",
                       history=lines or "(nothing yet)")
    problems: list[str] = []
    total = None
    for _ in range(MAX_TURN_ATTEMPTS):
        prompt = base + ("\n\nYOUR LAST ANSWER WAS REJECTED:\n" + "\n".join(f"- {p}" for p in problems) if problems else "")
        try:
            text, cost = runner(prompt)
        except Exception as e:  # the CLI missing, a timeout
            return Turn(error=str(e)[:300], cost_usd=total)
        if cost is not None:
            total = (total or 0.0) + cost
        data = builders.extract_json(text)
        if data is None:
            problems = ["answer with ONE JSON object"]
            continue
        problems = _turn_problems(data, offered)
        if problems:
            continue
        if not data.get("ready"):
            return Turn(questions=[str(q).strip()[:300] for q in data["questions"][:3]], cost_usd=total)
        views = [{"name": str(v["name"])[:40], "layout": v["layout"], "preview": str(v.get("preview") or "")[:400]}
                 for v in data["views"]]
        return Turn(ready=True, purpose=str(data["purpose"])[:2000], views=views, inputs=list(data.get("inputs") or []),
                    events=list(data["events"]), schedule=str(data.get("schedule") or "").strip(), cost_usd=total)
    return Turn(error="the Builder did not answer in the contract: " + "; ".join(problems), cost_usd=total)


def interview_from(turn: Turn, view: int, inputs: list[str], events: list[str], history: list[tuple[str, str]],
                   schedule: str | None = None) -> dict:
    """What `build` needs, from the conversation's last turn and the operator's picks."""
    v = turn.views[view]
    talk_text = "\n".join(f"{who}: {text}" for who, text in history[-12:])
    purpose = (f"{turn.purpose}\n\nTHE VIEW THE OPERATOR CHOSE: {v['name']} ({v['layout']})\n{v['preview']}"
               f"\n\nTHE CONVERSATION:\n{talk_text}")[:builders.PROMPT_LIMIT]
    return {"purpose": purpose, "layout": v["layout"], "inputs": inputs, "events": events or ["workshop.done"],
            "history": history, "schedule": turn.schedule if schedule is None else schedule.strip()}


def blueprint_dir(repo_root: Path, building_id: str) -> Path:
    return repo_root / workshop.BLUEPRINTS / building_id
