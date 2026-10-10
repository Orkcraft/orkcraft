"""🏕 Barracks: a foreman orc runs incoming tasks in parallel.

A task arrives (a cart from Tasks, a ticket, any text). The steward judges it first (realm/plans.py,
docs/design/barracks-planning.md): a simple one goes whole to one ork of the light tier the building's
goal names; a hard one becomes a plan — subtasks with a tier, a persona, the files they touch and what
they wait for — each a task of its own here, merged into the task's branch, the whole reviewed at the
end. Nobody hires by hand. Then the foreman decides, by rules:

    follow-up   it names a ticket an orc already worked on, or reads like a follow-up of the
                only orc with history → that orc gets it (now if idle, else when it is free)
    reuse       an idle orc of the tier and persona the task wants, with nothing waiting for it
    hire        fewer orcs than `max_orcs` and budget left → a new orc of that tier and persona; the
                foreman picks its provider from `providers` (a provider that names its model keeps it)
    retier      the pool is full: an idle orc of another tier takes it, on the task's model
    queue       otherwise it waits

Context is reused, not re-sent. An orc whose earlier work is close to the new task (same ticket,
or overlapping words with what it recently did) is preferred, and it resumes its own session: the
prompt is then only the task — the orders and the briefing are already in the session. A session
is rolled over after `session_tasks` tasks (it only grows); the next run starts fresh with a short
handoff of the orc's recent work. A cold start on an unrelated task gets no history at all.

Rules first, a model only when in doubt (not wired yet: a doubtful follow-up goes to the most
recent orc and the decision says so). The foreman learns: every finished task updates the stats
of its provider/model, and the next hire weighs success rate against cost — the self-reflection
the orcs of the town already do.

The unit of work is the task, not the orc: every task has its own branch `pool/<building>/<task>`,
cut from a fresh base in the orc's worktree (a follow-up of the same ticket goes on the same
branch). Orcs are only a pool of agents to reuse.

The steward (the building's own orc) keeps the rules — the `orders`, like a CLAUDE.md — and
judges. An orc that cannot go on answers `QUESTION: …`; the steward answers from its rules, or
hands the question to the operator (🔥 on the steward, never on the orc). A finished task is
reviewed: the tests (`test_cmd`) first, then the steward reads the diff against the task and the
rules → `ACCEPT` (the branch is pushed and a pull request opened) or `REWORK: …` (back to the same
orc, at most `max_reworks` times; then 🔥 for the operator).

State lives in `.orkcraft/pool/<id>/`: `barracks.json` (orcs, queue, recent tasks),
`decisions.jsonl` (every decision with its reason) and `stats.json` (per provider/model).
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from orkcraft import scroll as ts
from orkcraft.realm import harnesses, plans, tiers
from orkcraft.realm.jobs import now_iso

DEFAULT_PROVIDERS = (harnesses.MAIN,)        # the machine's main tool
DEFAULT_MAX_ORCS = 3
AGY_CODE, AGY_DOCS = harnesses.need("agy").task_models["code"], harnesses.need("agy").task_models["docs"]
TICKET = re.compile(r"\b([A-Z]{1,5}-?\d{2,6})\b")
FOLLOW_UP = re.compile(r"^\s*(follow[- ]?up|re:|also|and also|fix (the )?review|уточн|ещё|еще|также|доработ|поправ)",
                       re.I)
DOCS_WORDS = re.compile(r"\b(doc|docs|readme|write[- ]?up|research|summar|explain|report|документ|исследу|опиши)",
                        re.I)
RESUMABLE = frozenset(h.id for h in harnesses.REGISTRY.values() if h.resumable)   # a session it can resume
DEFAULT_SESSION_TASKS = 5                  # tasks one session carries before it is rolled over
RELATED = 0.2                              # word overlap from which a task counts as the orc's kind of work
LOOKAHEAD = 5                              # a freed orc looks this far into the queue for related work
KEEP_RECENT = 3
DEFAULT_MAX_REWORKS = 3
MAX_STEWARD_ANSWERS = 3                    # questions the steward answers in one run before the operator is asked
DIFF_LIMIT = 20_000                        # characters of the diff the steward reads
QUESTION = re.compile(r"^\s*\**\s*QUESTION\b\s*:?\s*(.+)", re.I | re.S | re.M)
ACCEPT = re.compile(r"^\s*\**\s*ACCEPT\b", re.I)
REWORK = re.compile(r"^\s*\**\s*REWORK\b\s*:?\s*", re.I)
ANSWER = re.compile(r"^\s*\**\s*ANSWER\b\s*:?\s*(.+)", re.I | re.S)
PUBLISH = re.compile(r"^\s*\**\s*PUBLISH\b\**\s*:\s*(.*)$", re.I | re.M)
SCOPE = re.compile(r"^\s*\**\s*SCOPE\b\s*:?\s*\**\s*(local|external)\b", re.I | re.M)
DOC_SUFFIXES = (".md", ".markdown", ".txt", ".rst", ".adoc", ".org")
LOCAL, EXTERNAL = "local", "external"      # a task's scope: no pull request / reviewed and sent as a PR
_DIFF_FILE = re.compile(r"^diff --git a/(.+?) b/(.+)$", re.M)
WORD = re.compile(r"[^\W\d_][\w-]{3,}")
STOP = frozenset("this that with from have will what when where which into your there their about please "
                 "should could would also make sure some them then than only just like need want task".split())
NAMES = ("Grub", "Mogka", "Thrak", "Ugluk", "Snaga", "Lurtz", "Gorbag", "Shagrat", "Muzgash", "Radbug")
KEEP_TASKS = 50


@dataclass
class PoolOrc:
    name: str
    harness: str
    model: str = ""
    status: str = "idle"            # idle | working
    task: str = ""                  # the task id it works on
    keys: list[str] = field(default_factory=list)   # tickets / nodes it worked on
    worktree: str = ""
    branch: str = ""
    session: str = ""               # the harness session to resume for a follow-up
    hired: str = ""
    done: int = 0
    failed: int = 0
    cost_usd: float = 0.0
    last: str = ""                  # when it last finished
    recent: list[str] = field(default_factory=list)  # its last tasks, a line each: what it knows
    session_tasks: int = 0          # tasks the current session carries
    tokens: int = 0
    persona: str = ""               # who it was hired as (realm/personas.py); "" — any work

    @property
    def tier(self) -> str | None:
        return tiers.step_tier({"harness": self.harness, "model": self.model})

    @property
    def label(self) -> str:
        return f"{self.harness}:{self.model}" if self.model else self.harness

    @property
    def tier_icon(self) -> str:
        """🔮 / ⚔ / ⛏ by its model (realm/tiers.py); "" when the model says nothing."""
        return tiers.model_icon(self.harness, self.model)


@dataclass
class PoolTask:
    id: str
    title: str
    text: str
    key: str = ""
    arrived: str = ""
    status: str = "queued"          # queued | working | reviewing | asked | done | failed (asked: a question,
    #                                 or a draft waiting for the operator's approval)
    orc: str = ""
    wait_for: str = ""              # a follow-up waiting for this orc
    result: str = ""
    error: str = ""
    cost_usd: float | None = None
    decided: str = ""               # the last decision about it
    warm: bool = False              # ran in the orc's resumed session
    tokens: int | None = None
    branch: str = ""                # its own branch; follow-ups and reworks stay on it
    base: str = ""                  # what the branch is cut from and the PR targets
    attempts: int = 0               # runs of the orc; 1 + the reworks
    feedback: str = ""              # the steward's last REWORK notes
    qa: list[list[str]] = field(default_factory=list)   # [question, answer, who answered]
    question: str = ""              # the question waiting for the operator (status asked)
    pr: str = ""                    # the pull request's URL
    pr_state: str = ""              # MERGED | CLOSED once it was settled (what the operator thought of it)
    scope: str = ""                 # local (no pull request) | external (reviewed, sent as a PR); "" not yet
    ref: str = ""                   # the thing worked on (a cart's ref), kept through rework rounds
    trail: list = field(default_factory=list)   # the hops before it arrived (pipes.Hop dicts)
    files: list[str] = field(default_factory=list)  # what its branch changed
    target: str = ""                # where its draft goes out (Jira, Confluence…): the `PUBLISH:` line
    draft: str = ""                 # what goes out, waiting for the operator's approval
    publish: str = ""               # the approved version: the orc posts it on its next run
    tier: str = ""                  # the tier it wants (realm/tiers.py); "" — whatever the ork has
    kind: str = ""                  # the triage (realm/plans.py): trivial | single | plan; "" not sorted
    persona: str = ""               # the persona it wants (realm/personas.py)
    want: str = ""                  # the kind of work its cart asked for (pipes.WANTS); "" none named
    want_by: str = ""               # who named it: a building, or "@table" / "@sort" (docs/design/barracks-flows.md §9)
    source: str = ""                # the building its cart came from
    code_card: str = ""             # a reply that reads like code: the card it left for the person on a Task board
    # A planned task (realm/plans.py): the parent keeps the plan, its subtasks point back at it.
    plan: list[dict] = field(default_factory=list)   # the parent's subtasks as planned (plans.Sub dicts)
    parent: str = ""                # a subtask: its parent task's id
    sub: str = ""                   # a subtask: its id in the plan
    after: list[str] = field(default_factory=list)   # a subtask: the ids it waits for
    touches: list[str] = field(default_factory=list)  # a subtask: the files it changes
    cheaper_ok: bool = False
    persona_waits: str = ""         # a new persona that waits for approval before this subtask runs
    waits_since: float = 0.0        # asked the operator since then (epoch seconds): the autonomy says how long
    ask_kind: str = ""              # what it asks: question | rejected | persona | draft (never decided by the orks)
    retried: bool = False           # a crashed run was tried once more already
    # Areas in work and design briefs (realm/claims.py, realm/briefs.py; docs/design/barracks-designs.md).
    claimed: list[str] = field(default_factory=list)  # the paths it claims (a guess until its work shows them)
    overlaps: list[dict] = field(default_factory=list)  # other tasks on its area: key, title, paths, branch, pr, …
    held_since: float = 0.0         # waits for an older task on its area since then (epoch seconds)
    design: str = ""                # its design brief's path, committed on its branch
    against: list[dict] = field(default_factory=list)   # the briefs its plan goes against: {with, why}
    pending: dict = field(default_factory=dict)         # a plan that waits for the operator on such a conflict
    designs: list[dict] = field(default_factory=list)   # the briefs its change met: {path, state}


@dataclass
class Decision:
    at: str
    task: str
    action: str                     # follow-up | wait | reuse | hire | retier | queue | budget | paused | plan | …
    orc: str = ""
    why: str = ""


def task_key(kind: str, value: str, title: str = "") -> str:
    """What a task is about: a node id, else the first ticket id it names."""
    if kind == "node" and value:
        return value.strip()
    m = TICKET.search(f"{title} {value}")
    return m.group(1) if m else ""


QUOTE = "\n\n---\n\n"           # a rework (gate / team `rework_markdown`) quotes the work it sends back after it


def body_of(task: PoolTask) -> str:
    """The task's text as a prompt gives it under `## Task: <title>`: without a first line that only
    says the title again (a card, a note and a meeting line often start with it)."""
    text = task.text.strip()
    first, _, rest = text.partition("\n")
    if rest.strip() and " ".join(first.strip(" #*-").split()).lower() == " ".join(task.title.split()).lower():
        return rest.strip()
    return text


def without_own_work(text: str, earlier: str) -> str:
    """A rework into the session that wrote `earlier`: the notes, not the quote of that work after them
    (the session holds it). The text as it is when it does not quote it."""
    earlier = earlier.strip()
    if not earlier or QUOTE not in text:
        return text
    i = text.find(QUOTE)
    while i >= 0:
        if earlier in text[i + len(QUOTE):]:
            return text[:i].rstrip() + "\n\n_(Your earlier report, quoted here, is in this session already.)_"
        i = text.find(QUOTE, i + 1)
    return text


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40]


def task_branch(building_id: str, task: PoolTask) -> str:
    """`pool/<building>/<ticket or id>`: a follow-up of the same ticket lands on the same branch."""
    return f"pool/{slug(building_id) or 'barracks'}/{slug(task.key) or task.id}"


def question_of(text: str) -> str:
    """The orc's `QUESTION: …` when it stopped to ask, else ""."""
    m = QUESTION.search(text or "")
    return m.group(1).strip() if m else ""


# What an orc may publish, named first on its `PUBLISH:` line (`PUBLISH: ticket, Jira, project APP`), so a
# Loot shows it before anyone opens the draft (realm/content.py has these among its types).
PUBLISH_KINDS: tuple[tuple[str, str], ...] = (
    ("message", "Slack, mail, a chat"), ("doc", "Confluence, Notion, a wiki page"),
    ("ticket", "Jira, Linear, an issue"), ("code", "a pull request"), ("image", "a picture"),
    ("data", "a JSON or CSV payload to an API"))
_KIND = re.compile(rf"^\s*({'|'.join(k for k, _ in PUBLISH_KINDS)})\b\s*(?:[,:;|·—–-]\s*|$)", re.I)


def publish_kind(target: str) -> tuple[str, str]:
    """(kind, where) of a `PUBLISH:` target: the kind it names first, "" when it names none (an older
    draft: `PUBLISH: Jira, APP`)."""
    m = _KIND.match(target or "")
    if m is None:
        return "", (target or "").strip()
    return m.group(1).lower(), target[m.end():].strip()


def publish_of(text: str) -> tuple[str, str, str]:
    """(report, target, draft) when the orc prepared something to go out — a `PUBLISH: <where>` line and,
    below it, exactly what to post; else (text, "", "")."""
    m = PUBLISH.search(text or "")
    if m is None:
        return text, "", ""
    return text[:m.start()].rstrip(), m.group(1).strip(" *"), text[m.end():].strip()


APPROVE = frozenset({"yes", "y", "ok", "approve", "approved", "publish", "go", "да", "ок", "ага", "постить"})
OUTSIDE_RULE = ("Never act outside this repository yourself: do not post, send or change anything in Jira, Confluence, "
                "Slack, mail or any other service. When the task asks for that, prepare it instead: end your answer "
                "with one line `PUBLISH: <kind>, <where>` — the kind is what goes out, one of "
                + "; ".join(f"{k} ({what})" for k, what in PUBLISH_KINDS)
                + " — (e.g. `PUBLISH: ticket, Jira, project APP, a new Bug` or `PUBLISH: message, Slack #release`) and "
                "below it exactly what goes out — the title, the fields, the text. The operator approves it first; "
                "then you post it.")

ANSWER_RULE = ("When the task only asks a question or for information (find, explain, compare), your report is the "
               "answer: write it there in full; it needs no commit.")


def publish_prompt(task: PoolTask) -> str:
    return "\n\n".join(p for p in [
        f"## Approved: {task.title}",
        f"The operator approved what you prepared. Post it now to {publish_kind(task.target)[1] or 'where the task says'}, exactly as "
        "below (it may have been edited) — nothing more, nothing else. Then answer with a short report: where it "
        "went, with a link or an id.",
        f"PUBLISH: {task.target}" if task.target else "", task.publish] if p)


def changed_files(diff: str) -> list[str]:
    """The files a `git diff` touches (both names of a rename)."""
    out: list[str] = []
    for a, b in _DIFF_FILE.findall(diff or ""):
        out += [a] if a == b else [a, b]
    return list(dict.fromkeys(out))


def docs_only(files: list[str]) -> bool:
    """Only documents changed (Markdown, text…) — no code, no config."""
    return all(f.lower().endswith(DOC_SUFFIXES) for f in files)


def scope_rule(files: list[str], meeting: bool) -> str:
    """What the rules decide before the steward: code (or any non-document) → `external`, always
    reviewed and sent as a pull request; a meeting's document → `local`; "" — the steward decides."""
    if files and not docs_only(files):
        return EXTERNAL
    return LOCAL if meeting else ""


def scope_of(text: str) -> str:
    """The steward's `SCOPE: local | external` line; `external` when it said nothing (the safe side)."""
    m = SCOPE.search(text or "")
    return m.group(1).lower() if m else EXTERNAL


def verdict_of(text: str) -> tuple[bool, str]:
    """(accepted, notes) from the steward's review: `ACCEPT` or `REWORK: …` (anything else is a rework)."""
    text = (text or "").strip()
    if ACCEPT.match(text):
        return True, ACCEPT.sub("", text, count=1).strip(" :-\n")
    return False, REWORK.sub("", text, count=1).strip() or "the steward did not accept it"


def steward_answer_of(text: str) -> str:
    """The steward's `ANSWER: …`, or "" when it hands the question to the operator."""
    m = ANSWER.match(text or "")
    return m.group(1).strip() if m else ""


FROM_ABOVE = plans.FROM_ABOVE         # the steward judges from its prompt (realm/plans.py)


def _rules(orders: str) -> str:
    return f"## Your rules\n\n{orders.strip()}" if orders.strip() else "## Your rules\n\n(none written yet)"


def steward_question_prompt(keeper: str, orders: str, task: PoolTask, question: str) -> str:
    return "\n\n".join([
        f"You are {keeper}, the steward of a barracks of coding agents: you keep its rules and judge.",
        _rules(orders), f"## The task: {task.title}", body_of(task),
        f"## The orc working on it asks\n\n{question}",
        "If your rules, the task or plain good practice settle it, answer `ANSWER: …` with the decision. "
        "If only the operator can decide (taste, scope, money, anything your rules do not cover), answer "
        "`ASK` and nothing else.", FROM_ABOVE])


def review_prompt(keeper: str, orders: str, task: PoolTask, report: str, diff: str, tests: str,
                  scope: str = EXTERNAL, extra: str = "") -> str:
    """`scope`: what the rules decided already; "" asks the steward for a `SCOPE:` line. `extra`: the work on the
    same files and the design briefs the change meets (core/workers/barracks_claims.py)."""
    cut = diff if len(diff) <= DIFF_LIMIT else diff[:DIFF_LIMIT] + "\n… (cut)"
    return "\n\n".join(p for p in [
        f"You are {keeper}, the steward of a barracks of coding agents: you keep its rules and judge their work.",
        _rules(orders), f"## The task: {task.title}", body_of(task),
        "## Earlier notes\n\n" + "\n".join(f"- {q} → {a}" for q, a, *_ in task.qa) if task.qa else "",
        f"## The orc's report\n\n{report.strip() or '(none)'}",
        f"## Tests\n\n{tests}" if tests else "",
        f"## The diff of its branch against {task.base or 'the base'}\n\n```diff\n{cut}\n```" if diff.strip()
        else "## The diff\n\n(nothing committed: the report is the work. That is enough when the task asks a "
             "question or for information; when it asks for changes, they had to be committed.)",
        extra,
        "The report ends with a draft to post (`PUBLISH:`): judge it as the work. Nothing is posted until the "
        "operator approves it." if publish_of(report)[2] else "",
        "Judge whether the task is done and your rules are kept. Answer `ACCEPT` on the first line, or "
        "`REWORK: …` with what exactly to fix. " + FROM_ABOVE,
        "" if scope else
        "Only documents changed. After ACCEPT add one line `SCOPE: local` when they are only for the operator's "
        "own use and stay in the camp (notes, a meeting's prep), or `SCOPE: external` when they go out — to the "
        "repository's readers, a wiki, other people or a tool — and need a pull request. In doubt: external."] if p)


def words(text: str) -> set[str]:
    return {w for w in WORD.findall(text.lower()) if w not in STOP}


def parse_provider(entry: str) -> tuple[str, str]:
    """`claude`, `agy:gemini-pro-high` (a family: its newest model), or a tier in place of the model: `claude:laborer`; `main`
    is the machine's main tool, as it is when the foreman reads it."""
    harness, _, model = str(entry).partition(":")
    harness = tiers.tool_of({"harness": harness.strip()})
    return harness, tiers.resolve(harness, model.strip())


class Foreman:
    def __init__(self, config: dict, stats: dict | None = None) -> None:
        self.max_orcs = int(config.get("max_orcs") or DEFAULT_MAX_ORCS)
        self.budget = float(config.get("budget_usd") or 0.0)          # 0: no budget of its own
        self.providers = [parse_provider(p) for p in (config.get("providers") or DEFAULT_PROVIDERS)]
        self.providers = [(h, m) for h, m in self.providers if h in ts.HARNESSES] or \
            [parse_provider(p) for p in DEFAULT_PROVIDERS]
        self.session_tasks = int(config.get("session_tasks") or DEFAULT_SESSION_TASKS)
        self.max_reworks = int(config["max_reworks"]) if config.get("max_reworks") is not None else DEFAULT_MAX_REWORKS
        self.stats = stats or {}

    # -- the model ------------------------------------------------------------------------------------

    def choose_model(self, task: PoolTask) -> tuple[str, str, str]:
        """(harness, model, why): the best provider by its record, nudged by what the task is; the model is
        the task's tier's on that harness, unless the provider names its own."""
        docs = bool(DOCS_WORDS.search(f"{task.title} {task.text}"))
        best, best_score, best_why = None, -1e9, ""
        for harness, model in self.providers:
            if not model and task.tier:
                model = tiers.MODELS.get(harness, {}).get(task.tier, "")
            h = harnesses.get(harness)
            if h is not None and h.task_models and not model:
                model = h.task_models.get("docs" if docs else "code", "")
            key = f"{harness}:{model}" if model else harness
            st = self.stats.get(key, {})
            runs, ok, cost = int(st.get("runs", 0)), int(st.get("ok", 0)), float(st.get("cost", 0.0))
            rate = (ok + 1) / (runs + 2)                         # Laplace: unknown providers start at ½
            avg_cost = cost / runs if runs else 0.0
            fit = 0.1 if h is not None and ("docs" if docs else "code") in h.fits else 0.0
            score = rate - 0.2 * min(avg_cost, 2.0) + fit
            if score > best_score:
                why = f"{key}: {ok}/{runs} ok" + (f", ${avg_cost:.2f}/task" if runs else ", no record yet")
                why += "; fits a docs task" if fit and docs else "; fits a code task" if fit else ""
                best, best_score, best_why = (harness, model), score, why
        assert best is not None
        return best[0], best[1], best_why

    def learn(self, orc: PoolOrc, ok: bool, cost: float | None, tokens: int | None = None) -> None:
        st = self.stats.setdefault(orc.label, {"runs": 0, "ok": 0, "cost": 0.0})
        st["runs"] += 1
        st["ok"] += int(ok)
        st["cost"] = round(st["cost"] + (cost or 0.0), 4)
        if tokens:
            st["tokens"] = st.get("tokens", 0) + tokens

    # -- the context ----------------------------------------------------------------------------------

    def affinity(self, task: PoolTask, orc: PoolOrc) -> float:
        """0…1: how much of the task the orc has already seen — its ticket, else shared words."""
        if task.key and task.key in orc.keys:
            return 1.0
        a, b = words(f"{task.title} {task.text[:1000]}"), words(" ".join(orc.recent))
        return len(a & b) / len(a | b) if a and b else 0.0

    def over_budget(self, spent: float) -> bool:
        return bool(self.budget) and spent >= self.budget

    def related(self, task: PoolTask, orc: PoolOrc) -> bool:
        return self.affinity(task, orc) >= RELATED

    def model_for(self, harness: str, tier: str) -> str | None:
        """The model of `tier` on `harness`; None when the providers name that harness's model outright
        (the operator chose it) or the harness has no tiers."""
        if not any(h == harness and not m for h, m in self.providers):
            return None
        return tiers.MODELS.get(harness, {}).get(tier)

    @staticmethod
    def fits(task: PoolTask, orc: PoolOrc) -> bool:
        """The orc is of the tier and the persona the task wants (a task that wants none fits any)."""
        return (not task.tier or orc.tier == task.tier) and (not task.persona or orc.persona == task.persona)

    def can_resume(self, orc: PoolOrc) -> bool:
        return orc.harness in RESUMABLE and bool(orc.session) and orc.session_tasks < self.session_tasks

    # -- the decision -----------------------------------------------------------------------------------

    def follow_up_of(self, task: PoolTask, orcs: list[PoolOrc]) -> tuple[PoolOrc | None, str]:
        if task.key:
            for o in orcs:
                if task.key in o.keys:
                    return o, f"{task.key} was {o.name}'s"
        if FOLLOW_UP.search(task.text) or FOLLOW_UP.search(task.title):
            seasoned = sorted((o for o in orcs if o.keys or o.done or o.failed), key=lambda o: o.last, reverse=True)
            if len(seasoned) == 1:
                return seasoned[0], f"reads like a follow-up; {seasoned[0].name} is the only one with history"
            if seasoned:
                return seasoned[0], f"reads like a follow-up; in doubt — {seasoned[0].name} finished last"
        return None, ""

    def decide(self, task: PoolTask, orcs: list[PoolOrc], queue: list[PoolTask], spent: float,
               paused: bool = False) -> Decision:
        at = now_iso()
        if paused:
            return Decision(at, task.id, "paused", why="the barracks is paused")
        if self.over_budget(spent):
            return Decision(at, task.id, "budget", why=f"spent ${spent:.2f} of ${self.budget:.2f}")
        orc, why = self.follow_up_of(task, orcs)
        if orc is not None:
            if orc.status == "idle":
                return Decision(at, task.id, "follow-up", orc.name, why)
            return Decision(at, task.id, "wait", orc.name, why + f"; waits until {orc.name} is free")
        waiting_for = {t.wait_for for t in queue if t.wait_for}
        idle = [o for o in orcs if o.status == "idle" and o.name not in waiting_for]
        fit = [o for o in idle if self.fits(task, o)]
        if fit:
            best = max(fit, key=lambda o: self.affinity(task, o))          # max keeps the first of equals
            score = self.affinity(task, best)
            why = f"{best.name} is idle" + (f" and knows this work ({score:.0%} overlap)" if score >= RELATED else "")
            return Decision(at, task.id, "reuse", best.name, why)
        wants = " ".join(w for w in (task.tier, task.persona and f"as {task.persona}") if w)
        if len(orcs) < self.max_orcs:
            harness, model, mwhy = self.choose_model(task)
            name = next((n for n in NAMES if n not in {o.name for o in orcs}), f"Ork{len(orcs) + 1}")
            busy = f"{len(orcs)}/{self.max_orcs} orks" + (f", none idle is {wants}" if idle else " busy")
            return Decision(at, task.id, "hire", name, f"{busy} → hire; {mwhy}")
        if idle:
            best = max(idle, key=lambda o: self.affinity(task, o))
            return Decision(at, task.id, "retier", best.name, f"the pool is full; {best.name} is idle and becomes {wants}")
        return Decision(at, task.id, "queue", why=f"all {len(orcs)} orks busy — waits in the queue")

    def next_for(self, orc: PoolOrc, queue: list[PoolTask], room: bool = False) -> PoolTask | None:
        """What a freed orc takes: its own follow-ups first, then — among the first few tasks nobody waits
        on — the one closest to its work, else the oldest. While the pool has `room` for a new orc, only a
        task of its tier and persona: the others wait for an orc hired for them."""
        mine = next((t for t in queue if t.wait_for == orc.name), None)
        if mine is not None:
            return mine
        free = [t for t in queue if not t.wait_for and (not room or self.fits(t, orc))]
        if not free:
            return None
        best = max(free[:LOOKAHEAD], key=lambda t: self.affinity(t, orc))
        return best if self.related(best, orc) else free[0]


class Barracks:
    """The state on disk of one Barracks building."""

    def __init__(self, state_dir: Path) -> None:
        self.dir = state_dir
        self.orcs: list[PoolOrc] = []
        self.queue: list[PoolTask] = []
        self.tasks: list[PoolTask] = []       # working and finished, newest last
        self.paused = False
        self.steward_cost = 0.0
        self.stats: dict = {}
        self.load()

    @property
    def spent(self) -> float:
        return round(sum(o.cost_usd for o in self.orcs) + self.steward_cost, 4)

    @property
    def asked(self) -> list[PoolTask]:
        """Tasks waiting for the operator at the steward (🔥)."""
        return [t for t in self.tasks if t.status == "asked"]

    def orc(self, name: str) -> PoolOrc | None:
        return next((o for o in self.orcs if o.name == name), None)

    def task(self, task_id: str) -> PoolTask | None:
        return next((t for t in self.queue + self.tasks if t.id == task_id), None)

    def load(self) -> None:
        try:
            data = json.loads((self.dir / "barracks.json").read_text(encoding="utf-8"))
            self.orcs = [PoolOrc(**o) for o in data.get("orcs", [])]
            self.queue = [PoolTask(**t) for t in data.get("queue", [])]
            self.tasks = [PoolTask(**t) for t in data.get("tasks", [])]
            self.paused = bool(data.get("paused", False))
            self.steward_cost = float(data.get("steward_cost", 0.0))
        except (OSError, ValueError, TypeError):
            pass
        for t in [t for t in self.tasks if t.status == "planning"]:     # the plan is made again
            self.tasks.remove(t)
            t.status = "queued"
            self.queue.insert(0, t)
        for t in self.tasks:                  # the last look at a planned whole is taken again
            if t.plan and t.status == "reviewing":
                t.status = "planned"
        for o in self.orcs:                   # a restart interrupts the work: those tasks go back
            if o.status == "working":
                t = next((x for x in self.tasks if x.id == o.task and x.status in ("working", "reviewing")), None)
                if t is not None:
                    self.tasks.remove(t)
                    t.status, t.wait_for = "queued", o.name
                    self.queue.insert(0, t)
                o.status, o.task = "idle", ""
        try:
            self.stats = json.loads((self.dir / "stats.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.stats = {}

    def save(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        data = {"orcs": [asdict(o) for o in self.orcs], "queue": [asdict(t) for t in self.queue],
                "tasks": [asdict(t) for t in self._kept()], "paused": self.paused,
                "steward_cost": self.steward_cost}
        (self.dir / "barracks.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        (self.dir / "stats.json").write_text(json.dumps(self.stats, indent=2), encoding="utf-8")

    def _kept(self) -> list[PoolTask]:
        """The last KEEP_TASKS tasks, and every one still open whatever its age."""
        old = self.tasks[:-KEEP_TASKS]
        return [t for t in old if t.status not in ("done", "failed")] + self.tasks[-KEEP_TASKS:]

    def log(self, d: Decision) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        with (self.dir / "decisions.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(d), ensure_ascii=False) + "\n")

    def decisions(self, limit: int = 30) -> list[Decision]:
        try:
            lines = (self.dir / "decisions.jsonl").read_text(encoding="utf-8").splitlines()[-limit:]
        except OSError:
            return []
        out = []
        for line in reversed(lines):
            try:
                out.append(Decision(**json.loads(line)))
            except (ValueError, TypeError):
                continue
        return out
