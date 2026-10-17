"""The board's keeper (spec 29a §4, decisions §43.3–6): it reads the new ideas in a batch, talks a spec through with
the person, and turns a spec into a plan.

    keeper = IdeaKeeper(repo_root, state_dir, wiki_root=lambda: root, settings=lambda: machine.ideas,
                        publish=lambda slug: ...)
    keeper.tick()                     # the host's clock: the batch when it is due
    keeper.say(slug, "Why not a toggle?", "Risks")    # the keeper answers in the background
    keeper.plan(slug)                 # once: the page → plan.json, with its estimate

- **Batch** (laborer): each `raw` idea, read-only in the repository, given the Wiki's `index.md` and the tracks: it
  fills Gist and Why, the size, proposes a track (only for an idea in General) and writes 1–3 Open questions.
- **Talk** (elder): one Claude session per idea (`--resume` its session). A new session when the last turn is older
  than `idle_hours` or its context passed 60 % of the window; the new one starts from the page only (its Decisions
  and Open questions with it). The talk is archived in `talk.jsonl` and never read back into a model.
- **Plan** (elder): the page → `plan.json` (at most 8 tasks), the estimate from `realm/plans.py` `DEFAULT_COST`.

Every model call goes through `realm/jobs.py` on the `claude` harness; its answer is untrusted: it is parsed
strictly and only known sections are written. Each change is published (`publish(slug)`: the face puts
`ideas.changed` on the bus). The keeper never commits: the pages stay in the working tree. No face.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import threading
import time
from pathlib import Path
from typing import Any, Callable

from orkcraft.realm import ideas, plans

CHANGED = "ideas.changed"          # the bus's topic: slug
HARNESS = "claude"
WINDOW = 200_000                   # Claude's context window, tokens
COMPACT_SHARE = 0.6                # a talk's session past this share of the window is compacted
MAX_TASKS, MAX_TODOS, MAX_QUESTIONS = 8, 5, 3
INDEX_CHARS, PAGE_CHARS, REPLY_CHARS = 6000, 30_000, 4000
TIERS = ("elder", "warrior", "laborer")
KINDS = ("secret", "choice", "confirm", "instructions")
ENV_NAME = re.compile(r"^[A-Z][A-Z0-9_]{1,63}$")

Call = Callable[[str, str, str], tuple[str, Any, Any, str]]   # (tier, prompt, resume) → (text, cost, tokens, session)


class KeeperError(Exception):
    """What the keeper refuses, in plain words."""


def first_json(text: str) -> dict | None:
    """The first JSON object in a model's answer (it may wrap it in prose or a code fence); None when there is none."""
    decoder = json.JSONDecoder()
    for m in re.finditer(r"\{", text or ""):
        try:
            value, _end = decoder.raw_decode(text, m.start())
        except ValueError:
            continue
        if isinstance(value, dict):
            return value
    return None


def _words(value: object, limit: int) -> str:
    return str(value).strip()[:limit] if isinstance(value, (str, int, float)) and not isinstance(value, bool) else ""


def _strings(value: object, limit: int, each: int = 500) -> list[str]:
    if not isinstance(value, list):
        return []
    return [s for s in (_words(v, each) for v in value) if s][:limit]


def _bullets(lines: list[str]) -> str:
    return "\n".join(f"- {' '.join(q.split())}" for q in lines)


class IdeaKeeper:
    def __init__(self, repo_root: Path, state_dir: Path, wiki_root: Callable[[], Path],
                 settings: Callable[[], dict], publish: Callable[[str], None] = lambda slug: None,
                 demo: bool = False, budget_ok: Callable[[], bool] = lambda: True) -> None:
        self.repo_root, self.state_dir = Path(repo_root), Path(state_dir)
        self.wiki_root, self.settings, self.publish = wiki_root, settings, publish
        self.demo, self.budget_ok = demo, budget_ok
        self.call: Call = self._claude                # tests swap the model call here
        self.cancel = threading.Event()
        self._lock = threading.Lock()
        self._busy: dict[str, str] = {}             # slug → reading | talking | planning
        self._batching = False
        self._batch_next = time.time() + self._minutes() * 60

    # -- the model call -------------------------------------------------------------------------------------

    def _claude(self, tier: str, prompt: str, resume: str = "") -> tuple[str, Any, Any, str]:
        from orkcraft.realm import harnesses, jobs
        from orkcraft.sources import telemetry
        h = harnesses.get(HARNESS)
        purpose = {"laborer": "sort", "elder": "plan"}.get(tier, "plan")
        with telemetry.tagged(purpose, "board"):
            return jobs.run_read(HARNESS, prompt, self.repo_root, self.cancel, h.pick(tier) if h else tier,
                                 env={"ORKCRAFT_ORC": "board/keeper"}, resume=resume)

    def _context(self, session: str, tokens) -> int:
        from orkcraft.realm import jobs
        try:
            read = jobs.context_of(HARNESS, session, self.repo_root)
        except Exception:                            # a transcript we cannot read: the run's own count
            read = 0
        return int(read or tokens or 0)

    # -- what the host asks ------------------------------------------------------------------------------

    def _minutes(self) -> int:
        return int((self.settings() or {}).get("batch_minutes") or 30)

    def batch_next(self) -> str:
        return dt.datetime.fromtimestamp(self._batch_next).isoformat(timespec="seconds")

    def busy(self, slug: str) -> str:
        """What the keeper does on this idea now ("" nothing)."""
        return self._busy.get(slug, "")

    def stop_all(self) -> None:
        """Stop all: what runs is stopped (its call raises), the next calls run again."""
        stopping, self.cancel = self.cancel, threading.Event()
        stopping.set()

    def _may_run(self) -> str:
        if self.demo:
            return "The demo runs no model: the keeper only reads ideas in a real town"
        if not self.budget_ok():
            return "Today's spend limit is reached: the keeper waits"
        return ""

    def tick(self, now: float | None = None) -> bool:
        """The host's clock: the batch when it is due; True when one started."""
        now = time.time() if now is None else now
        if now < self._batch_next or self._batching:
            return False
        self._batch_next = now + self._minutes() * 60
        if self._may_run():
            return False
        raw = [i["slug"] for i in ideas.ideas(self.wiki_root())
               if ideas.state(self.state_dir, i["slug"])["state"] == "raw" and not self.busy(i["slug"])]
        if not raw:
            return False
        self._batching = True
        threading.Thread(target=self._batch, args=(raw,), daemon=True, name="idea-batch").start()
        return True

    def _start(self, slug: str, what: str, fn: Callable[[], None]) -> None:
        with self._lock:
            if self._busy.get(slug):
                raise KeeperError("The keeper is busy with this idea: a moment")
            self._busy[slug] = what

        def run() -> None:
            try:
                fn()
            finally:
                with self._lock:
                    self._busy.pop(slug, None)
                self.publish(slug)

        threading.Thread(target=run, daemon=True, name=f"idea-{what}").start()

    # -- the batch: a light model reads the new ideas ----------------------------------------------------

    def _batch(self, slugs: list[str]) -> None:
        try:
            for slug in slugs:
                if self._may_run() or self.cancel.is_set():
                    return
                with self._lock:
                    if self._busy.get(slug):
                        continue
                    self._busy[slug] = "reading"
                try:
                    self.read_one(slug)
                finally:
                    with self._lock:
                        self._busy.pop(slug, None)
                    self.publish(slug)
        finally:
            self._batching = False

    def batch_prompt(self, root: Path, slug: str) -> str:
        page = ideas.idea_page(root, slug)
        tracks = ideas.tracks(root)
        try:
            index = (root / "index.md").read_text(encoding="utf-8")[:INDEX_CHARS]
        except OSError:
            index = "(no index yet)"
        lines = "\n".join(f"- {t['slug']}: {t['title']}" + (f" — {ideas.thesis(t['about'])}" if t["about"] else "")
                          + (f" (success: {'; '.join(t['criteria'])})" if t["criteria"] else "") for t in tracks)
        track = page.get("track") or ideas.GENERAL
        return f"""You are the keeper of this project's Task board. A person dropped a new idea; read it and get it
ready to be talked through as a spec. You may read the repository (read only) to understand what it touches.

The project's Wiki, its map (index.md):
{index}

The tracks:
{lines}

The idea (track: {track}):
{page.section("Gist")[:PAGE_CHARS]}

Answer with one JSON object and nothing else:
{{"gist": "the idea rewritten clearly: its first line one sentence, the thesis; then a few lines if needed",
 "why": "which success criterion of its track it moves, and why it matters",
 "size": "S, M or L",
 "track": "the slug of the listed track it belongs to{'' if track == ideas.GENERAL else ' (leave empty)'}",
 "questions": ["one to three questions the person must answer before it can be planned"]}}
"""

    def read_one(self, slug: str) -> None:
        """One raw idea read by the laborer: Gist, Why, size, a proposed track, its questions; then asks or ready."""
        root = self.wiki_root()
        page = ideas.idea_page(root, slug)
        if page is None:
            return
        ideas.save_state(self.state_dir, slug, state="reading", error="")
        self.publish(slug)
        try:
            text, _cost, _tokens, _session = self.call("laborer", self.batch_prompt(root, slug), "")
            answer = first_json(text)
            if answer is None:
                raise KeeperError("the keeper's answer was not the JSON it was asked for")
        except Exception as e:                      # the idea stays new: the next batch tries again
            ideas.save_state(self.state_dir, slug, state="raw", error=_why(e))
            return
        sections = {}
        if gist := _words(answer.get("gist"), ideas.SECTION_CHARS):
            sections["Gist"] = gist
        if why := _words(answer.get("why"), ideas.SECTION_CHARS):
            sections["Why"] = why
        questions = _strings(answer.get("questions"), MAX_QUESTIONS)
        if questions:
            sections["Open questions"] = _bullets(questions)
        ideas.update(root, slug, sections)
        meta: dict[str, str] = {}
        size = _words(answer.get("size"), 2).upper()
        if size in ideas.SIZES:
            meta["size"] = size
        track = _words(answer.get("track"), 60)
        if (page.get("track") or ideas.GENERAL) == ideas.GENERAL and track and track != ideas.GENERAL \
                and track in {t["slug"] for t in ideas.tracks(root)}:
            meta["proposed_track"] = track
        if meta:
            ideas.set_meta(root, slug, **meta)
        ideas.save_state(self.state_dir, slug, state="asks" if questions else "ready", error="",
                         batch_at=dt.datetime.now().isoformat(timespec="seconds"))

    # -- the talk: one session per idea, on the elder tier -----------------------------------------------

    def say(self, slug: str, text: str, section: str = "") -> None:
        root = self.wiki_root()
        text = str(text or "").strip()[:ideas.SECTION_CHARS]
        if ideas.idea_page(root, slug) is None:
            raise KeeperError("That idea is gone")
        if not text:
            raise KeeperError("Say something to the keeper")
        if section and section not in ideas.SECTIONS:
            raise KeeperError(f"An idea has no section {section!r}")
        if why := self._may_run():
            raise KeeperError(why)
        if self.busy(slug):
            raise KeeperError("The keeper is busy with this idea: a moment")
        ideas.add_turn(self.state_dir, slug, "you", text, section)
        self._start(slug, "talking", lambda: self.talk_one(slug, text, section))

    def fresh(self, st: dict, now: dt.datetime | None = None) -> bool:
        """Whether the talk's next turn needs a new session (compaction): none yet, its last turn older than
        `idle_hours`, or its context past 60 % of the window."""
        if not st.get("session"):
            return True
        now = now or dt.datetime.now()
        hours = int((self.settings() or {}).get("idle_hours") or 24)
        try:
            at = dt.datetime.fromisoformat(str(st.get("session_at") or ""))
        except ValueError:
            return True
        return now - at > dt.timedelta(hours=hours) or int(st.get("context") or 0) > COMPACT_SHARE * WINDOW

    def talk_prompt(self, root: Path, slug: str, text: str, section: str, fresh: bool) -> str:
        page = ideas.idea_page(root, slug)
        about = f" (about {section})" if section else ""
        ask = f"""The person says{about}:
{text}

Answer with one JSON object and nothing else:
{{"reply": "your answer to the person, short and plain",
 "sections": {{"<a section's name>": "its whole new text"}},
 "decisions": ["one line for each thing decided in this turn, and why"],
 "questions": ["the open questions that remain (all of them; [] when none)"]}}
Put in `sections` only the sections this turn is about; leave the others out. Section names: {", ".join(n for n in ideas.SECTIONS if n != "Decisions")}."""
        if not fresh:
            now = page.section(section) if section else ""
            return ask + (f"\n\nThe section {section} reads now:\n{now[:PAGE_CHARS]}" if section else "")
        return f"""You are the keeper of one idea on this project's Task board: you talk its spec through with the
person, and keep its page. You may read the repository (read only). Edit only the sections a turn is about, never
rewrite the page; each decision goes to Decisions (you name it, the board writes the line).

The idea's page now:
{page.text()[:PAGE_CHARS]}

{ask}"""

    def talk_one(self, slug: str, text: str, section: str = "") -> None:
        root = self.wiki_root()
        st = ideas.state(self.state_dir, slug)
        fresh = self.fresh(st)
        try:
            out, _cost, tokens, session = self.call("elder", self.talk_prompt(root, slug, text, section, fresh),
                                                    "" if fresh else st["session"])
        except Exception as e:
            ideas.add_turn(self.state_dir, slug, "keeper", f"I could not answer: {_why(e)}", section)
            ideas.save_state(self.state_dir, slug, error=_why(e))
            return
        answer = first_json(out)
        if answer is None:                           # plain words: kept as the reply, nothing written
            answer = {"reply": out}
        sections = answer.get("sections") if isinstance(answer.get("sections"), dict) else {}
        written = {n: _words(v, ideas.SECTION_CHARS) for n, v in sections.items()
                   if n in ideas.SECTIONS and n != "Decisions" and isinstance(v, str)}
        if isinstance(answer.get("questions"), list):
            written["Open questions"] = _bullets(_strings(answer["questions"], 10))
        decisions = _strings(answer.get("decisions"), 10)
        if written or decisions:
            ideas.update(root, slug, written, decisions)
        reply = _words(answer.get("reply"), REPLY_CHARS) or "(the keeper wrote the page and said nothing)"
        ideas.add_turn(self.state_dir, slug, "keeper", reply, section)
        changes: dict[str, Any] = {"session": session or ("" if fresh else st["session"]),
                                   "session_at": dt.datetime.now().isoformat(timespec="seconds"),
                                   "context": self._context(session or st["session"], tokens), "error": ""}
        state = ideas.state(self.state_dir, slug)["state"]
        if state in ("raw", "asks", "ready"):
            page = ideas.idea_page(root, slug)
            changes["state"] = "asks" if page and ideas.items(page.section("Open questions")) else "ready"
        ideas.save_state(self.state_dir, slug, **changes)

    # -- the plan: the spec → plan.json -------------------------------------------------------------------

    def plan(self, slug: str) -> None:
        root = self.wiki_root()
        if ideas.idea_page(root, slug) is None:
            raise KeeperError("That idea is gone")
        old = ideas.plan(self.state_dir, slug)
        if old and old.get("passed_at"):
            raise KeeperError("Its plan is passed already: the tasks are in work")
        if why := self._may_run():
            raise KeeperError(why)
        if self.busy(slug):
            raise KeeperError("The keeper is busy with this idea: a moment")
        was = ideas.state(self.state_dir, slug)["state"]
        ideas.save_state(self.state_dir, slug, state="planning", error="")
        try:
            self._start(slug, "planning", lambda: self.plan_one(slug, was))
        except KeeperError:
            ideas.save_state(self.state_dir, slug, state=was)
            raise

    def plan_prompt(self, root: Path, slug: str) -> str:
        page = ideas.idea_page(root, slug)
        return f"""You are the keeper of this project's Task board. The person passes this spec to work: turn it into
a plan. You may read the repository (read only) to see what the work touches.

The spec:
{page.text()[:PAGE_CHARS]}

Rules:
- At most {MAX_TASKS} tasks. Each is a brief another Claude session can do alone, in a worktree of the repository:
  what to change, where, and how it is tested. `after` only where a task needs another's result.
- Each task's tier: "elder" (hard design or a wide change), "warrior" (ordinary code), "laborer" (small, mechanical).
- To-dos only for what a task cannot start without: a key ("secret": its title is the environment variable's name,
  e.g. API_KEY), a decision ("choice", with its choices), a yes ("confirm"), steps a person does ("instructions").
  Most plans need none. `for`: the tasks that wait for it.

Answer with one JSON object and nothing else:
{{"tasks": [{{"id": "k1", "title": "…", "brief": "…", "tier": "warrior", "after": []}}],
 "todos": [{{"id": "t1", "title": "…", "kind": "confirm", "why": "…", "choices": [], "steps": [], "for": ["k1"]}}]}}
"""

    def plan_one(self, slug: str, was: str = "ready") -> None:
        root = self.wiki_root()
        back = was if was in ("raw", "asks", "ready", "plan", "failed") else "ready"
        try:
            text, _cost, _tokens, _session = self.call("elder", self.plan_prompt(root, slug), "")
            data = make_plan(slug, first_json(text))
            ideas.save_plan(self.state_dir, slug, data)
        except Exception as e:
            ideas.save_state(self.state_dir, slug, state=back, error=f"No plan: {_why(e)}")
            return
        ideas.save_state(self.state_dir, slug, state="plan", error="")


def make_plan(slug: str, answer: dict | None, made_at: str = "") -> dict:
    """plan.json from the model's answer, strictly: at most 8 tasks with their ids renamed k1…, `after` only to an
    earlier task, known tiers and kinds; the estimate from the tiers' default cost, ±50 %."""
    if not isinstance(answer, dict) or not isinstance(answer.get("tasks"), list):
        raise KeeperError("the keeper's answer was not a plan")
    names: dict[str, str] = {}
    tasks: list[dict] = []
    for raw in answer["tasks"]:
        if not isinstance(raw, dict) or len(tasks) >= MAX_TASKS:
            continue
        title, brief = _words(raw.get("title"), 200), _words(raw.get("brief"), 6000)
        if not title or not brief:
            continue
        tid = f"k{len(tasks) + 1}"
        after = [names[a] for a in _strings(raw.get("after"), MAX_TASKS, 20) if a in names]
        names[_words(raw.get("id"), 20) or tid] = tid
        tier = raw.get("tier") if raw.get("tier") in TIERS else "warrior"
        tasks.append({"id": tid, "title": title, "brief": brief, "tier": tier, "after": list(dict.fromkeys(after)),
                      "state": "waiting", "branch": "", "commit": "", "session": "", "cost": None, "tokens": None,
                      "started": "", "finished": "", "error": "", "note": ""})
    if not tasks:
        raise KeeperError("the plan had no task")
    todos: list[dict] = []
    for raw in answer.get("todos") if isinstance(answer.get("todos"), list) else []:
        if not isinstance(raw, dict) or len(todos) >= MAX_TODOS or raw.get("kind") not in KINDS:
            continue
        title = _words(raw.get("title"), 200)
        if raw["kind"] == "secret":
            title = re.sub(r"[^A-Z0-9_]+", "_", title.upper()).strip("_")
            if not ENV_NAME.match(title):
                continue
        if not title:
            continue
        for_ = [names[f] for f in _strings(raw.get("for"), MAX_TASKS, 20) if f in names]
        todos.append({"id": f"t{len(todos) + 1}", "title": title, "kind": raw["kind"],
                      "why": _words(raw.get("why"), 500),
                      "choices": _strings(raw.get("choices"), 8, 200) if raw["kind"] == "choice" else [],
                      "steps": _strings(raw.get("steps"), 12, 500) if raw["kind"] == "instructions" else [],
                      "for": list(dict.fromkeys(for_)), "done": False, "value": None})
    data = {"idea": slug, "made_at": made_at or dt.datetime.now().isoformat(timespec="seconds"), "passed_at": None,
            "estimate": estimate(tasks), "todos": todos, "tasks": tasks}
    readiness(data)
    return data


def estimate(tasks: list[dict]) -> dict:
    base = sum(plans.DEFAULT_COST.get(t.get("tier", "warrior"), plans.DEFAULT_COST["warrior"]) for t in tasks)
    return {"tasks": len(tasks), "usd_low": round(base * 0.5, 2), "usd_high": round(base * 1.5, 2)}


def readiness(data: dict) -> None:
    """A task not started yet is `ready` when what it waits for is done (its `after`, its to-dos), else `waiting`."""
    merged = {t["id"] for t in data.get("tasks") or [] if t.get("state") == "merged"}
    blocked = {f for td in data.get("todos") or [] if not td.get("done") for f in td.get("for") or []}
    for t in data.get("tasks") or []:
        if t.get("state") in ("waiting", "ready"):
            t["state"] = "ready" if set(t.get("after") or []) <= merged and t["id"] not in blocked else "waiting"


def _why(e: Exception) -> str:
    if isinstance(e, InterruptedError):
        return "stopped"
    return (str(e) or type(e).__name__).strip()[:300]
