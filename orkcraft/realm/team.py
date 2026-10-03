"""⚔ Agent Team: agents with roles discuss until they agree on one artifact.

    round 1     the first member drafts the artifact
    each round  every other member reviews the draft: `AGREE`, or `OBJECT:` with what to change
    all agree   → consensus: the artifact is ready
    objections  → the moderator revises the draft, and the next round reviews it
    the limits  `max_rounds` (then the moderator decides and the artifact says what stayed open),
                `budget_usd` (then it stops with the draft as it is)

Precedence, stated in every prompt: the operator's answers outrank the topic, and the topic (what
was asked for this discussion: typed at ▶ or carried by a cart) outranks the building's `goal`.

Any member may answer `QUESTION: …` instead: the discussion pauses (🔥 on the hut) until the
operator answers, and that member's turn runs again with the answer.

`members` are `Role:harness[:model]` — `Architect:claude`, `Critic:agy:gemini-3.1-pro-high`. The
discussion runs off the UI thread; every turn is reported as it happens. A runner is
`(harness, prompt, model) → (text, cost)`; tests pass a fake one.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import threading
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable

from orkcraft.realm import tiers

DEFAULT_MEMBERS = ("Author:claude", "Critic:claude")
DEFAULT_ROUNDS = 4
DEFAULT_BUDGET = 2.0
_AGREE = re.compile(r"^\s*\**\s*AGREE\b", re.I)
_OBJECT = re.compile(r"^\s*\**\s*OBJECT\b\s*:?\s*", re.I)
_QUESTION = re.compile(r"^\s*\**\s*QUESTION\b\s*:?\s*(.+)", re.I | re.S)

Runner = Callable[[str, str, str], tuple[str, float | None]]


def now_iso() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


@dataclass
class Member:
    role: str
    harness: str = "claude"
    model: str = ""

    @property
    def label(self) -> str:
        return f"{self.harness}:{self.model}" if self.model else self.harness

    @property
    def tier_icon(self) -> str:
        """🔮 / ⚔ / ⛏ by its model (realm/tiers.py); "" when the model says nothing."""
        return tiers.model_icon(self.harness, self.model)


def parse_member(entry: str) -> Member | None:
    role, _, rest = str(entry).partition(":")
    harness, _, model = rest.partition(":")
    role, harness = role.strip(), (harness.strip() or "claude")
    if not role or harness not in ("claude", "agy"):
        return None
    return Member(role, harness, tiers.resolve(harness, model.strip()))   # `Critic:claude:elder` → opus


def members_of(config: dict) -> list[Member]:
    out = [m for m in (parse_member(e) for e in (config.get("members") or DEFAULT_MEMBERS)) if m]
    return out if len(out) >= 2 else [parse_member(e) for e in DEFAULT_MEMBERS]  # type: ignore[misc]


@dataclass
class Turn:
    round: int
    role: str
    kind: str                       # draft | review | revise | decide | question | answer
    text: str
    agree: bool | None = None
    cost: float | None = None
    at: str = ""


@dataclass
class Discussion:
    id: str
    topic: str
    goal: str = ""
    started: str = ""
    ended: str = ""
    outcome: str = "running"        # running | agreed | no_consensus | budget | asked | error | stopped
    round: int = 0
    draft: str = ""
    reviewed: list[str] = field(default_factory=list)       # who reviewed this round's draft
    objections: list[str] = field(default_factory=list)     # this round's objections
    asking: str = ""                                        # the role whose question waits
    question: str = ""
    spent: float = 0.0
    error: str = ""
    turns: list[Turn] = field(default_factory=list)

    @property
    def finished(self) -> bool:
        return self.outcome not in ("running", "asked")

    def answers(self) -> list[str]:
        return [t.text for t in self.turns if t.kind == "answer"]


# -- prompts ------------------------------------------------------------------------------------------

PRECEDENCE = ("If these conflict, the operator's answers win over the topic, and the topic wins over "
              "the goal.")


def _brief(d: Discussion) -> list[str]:
    """Goal, topic and the operator's answers, with the rule of which wins."""
    parts = [f"Goal (the standing brief): {d.goal}" if d.goal else "", f"Topic (this request): {d.topic}"]
    if d.answers():
        parts.append("The operator answered:\n" + "\n".join(f"- {a}" for a in d.answers()))
    if d.goal or d.answers():
        parts.append(PRECEDENCE)
    return [p for p in parts if p]


def _frame(d: Discussion, me: Member, team: list[Member]) -> str:
    others = ", ".join(m.role for m in team if m.role != me.role)
    parts = [f"You are {me.role} in a team of agents ({others}) that must agree on one artifact.", *_brief(d),
             "If you cannot go on without the operator's decision, answer with one line "
             "`QUESTION: …` and nothing else."]
    return "\n\n".join(parts)


def draft_prompt(d: Discussion, me: Member, team: list[Member]) -> str:
    return _frame(d, me, team) + "\n\nWrite the first draft of the artifact in Markdown. Answer with the artifact only."


def review_prompt(d: Discussion, me: Member, team: list[Member]) -> str:
    return (_frame(d, me, team) + f"\n\n## The draft (round {d.round})\n\n{d.draft}\n\n"
            "Review it from your role. If you accept it as it is, answer `AGREE` on the first line. "
            "Otherwise answer `OBJECT:` followed by the concrete changes you need — short, numbered.")


def revise_prompt(d: Discussion, objections: list[str], final: bool) -> str:
    ask = ("This is the last round: decide. Return the final artifact, and end it with a short "
           "`## Open points` section listing what the team did not agree on." if final else
           "Revise the draft so that it answers the objections. Return the full revised artifact only.")
    return ("You moderate a team of agents.\n\n" + "\n\n".join(_brief(d)) +
            f"\n\n## The draft\n\n{d.draft}\n\n## Objections\n\n" + "\n\n".join(objections) + f"\n\n{ask}")


# -- the discussion -----------------------------------------------------------------------------------

def run(d: Discussion, team: list[Member], moderator: str, max_rounds: int, budget: float, runner: Runner,
        on_turn: Callable[[Discussion, Turn], None] | None = None,
        cancel: threading.Event | None = None) -> Discussion:
    """Run (or resume) the discussion until it agrees, asks, runs out of rounds or money, or fails."""
    cancel = cancel or threading.Event()
    mod_harness, _, mod_model = (moderator or "claude").partition(":")

    def call(role: str, kind: str, harness: str, model: str, prompt: str) -> Turn | None:
        if cancel.is_set():
            d.outcome = "stopped"
            return None
        if budget and d.spent >= budget:
            d.outcome = "budget"
            return None
        try:
            text, cost = runner(harness, prompt, model)
        except Exception as e:  # one failing call ends the discussion, the app goes on
            d.outcome, d.error = "error", f"{role}: {e}"[:300]
            return None
        d.spent = round(d.spent + (cost or 0.0), 4)
        q = _QUESTION.match(text or "")
        if q and kind != "revise" and kind != "decide":
            d.outcome, d.asking, d.question = "asked", role, q.group(1).strip()
            turn = Turn(d.round, role, "question", d.question, cost=cost, at=now_iso())
        else:
            agree = bool(_AGREE.match(text or "")) if kind == "review" else None
            turn = Turn(d.round, role, kind, (text or "").strip(), agree, cost, now_iso())
        d.turns.append(turn)
        if on_turn is not None:
            on_turn(d, turn)
        return turn

    d.outcome, d.asking, d.question = "running", "", ""
    if d.round == 0:
        d.round = 1
    author = team[0]
    if not d.draft:
        t = call(author.role, "draft", author.harness, author.model, draft_prompt(d, author, team))
        if t is None or t.kind == "question":
            return _end(d)
        d.draft = t.text
    while True:
        for m in team[1:]:
            if m.role in d.reviewed:
                continue
            t = call(m.role, "review", m.harness, m.model, review_prompt(d, m, team))
            if t is None or t.kind == "question":
                return _end(d)
            d.reviewed.append(m.role)
            if not t.agree:
                d.objections.append(f"**{m.role}:** {_OBJECT.sub('', t.text, count=1)}")
        if not d.objections:
            d.outcome = "agreed"
            return _end(d)
        final = d.round >= max_rounds
        t = call("Moderator", "decide" if final else "revise", mod_harness or "claude", mod_model,
                 revise_prompt(d, d.objections, final))
        if t is None:
            return _end(d)
        d.draft = t.text
        if final:
            d.outcome = "no_consensus"
            return _end(d)
        d.round, d.reviewed, d.objections = d.round + 1, [], []


def answer(d: Discussion, text: str) -> None:
    """The operator answered the waiting question: the asking member's turn runs again."""
    d.turns.append(Turn(d.round, "Operator", "answer", text.strip(), at=now_iso()))
    d.asking, d.question, d.outcome = "", "", "running"


def _end(d: Discussion) -> Discussion:
    if d.finished:
        d.ended = now_iso()
    return d


def new(topic: str, goal: str = "") -> Discussion:
    return Discussion(uuid.uuid4().hex[:8], topic.strip(), goal.strip(), now_iso())


# -- keeping it ---------------------------------------------------------------------------------------

def save(state_dir: Path, d: Discussion) -> Path:
    path = state_dir / "discussions" / f"{d.started[:10]}-{d.id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(d), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_all(state_dir: Path, limit: int = 20) -> list[Discussion]:
    folder = state_dir / "discussions"
    out = []
    for f in sorted(folder.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit] \
            if folder.is_dir() else []:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            data["turns"] = [Turn(**t) for t in data.get("turns", [])]
            out.append(Discussion(**data))
        except (OSError, ValueError, TypeError):
            continue
    return out


def artifact_markdown(d: Discussion, team: list[Member]) -> str:
    verdict = {"agreed": "agreed", "no_consensus": "no consensus — the moderator decided"}.get(d.outcome, d.outcome)
    head = (f"_Team: {', '.join(f'{m.role} ({m.label})' for m in team)} · {d.round} round"
            f"{'s' if d.round != 1 else ''} · {verdict} · ${d.spent:.2f}_")
    return f"{head}\n\n{d.draft}"
