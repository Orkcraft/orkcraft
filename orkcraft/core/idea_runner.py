"""The runner of a passed plan (docs/specs/29a-board-focus.md §5): each task its own Claude session in a worktree,
tested, rebased and fast-forwarded into `ideas.merge_into` (default `main`), pushed.

    runner = IdeaRunner(repo_root, state_dir, settings, bus)
    runner.start(slug)        # after `ideas.start` set the plan's `passed_at`
    runner.tick()             # every few seconds from the host: never blocks, the work runs on threads
    runner.stop(slug) / runner.stop_all()

The plan's tasks live in `<state_dir>/ideas/<slug>/plan.json` (the runner owns them once the plan is passed; it
re-reads the file before each write, so the keeper's to-dos stay as the keeper wrote them). A task waits for its
`after` tasks to be merged and for the to-dos `for` it to be done, starts when a slot is free (`ideas.max_parallel`)
and its tool's window is not nearly spent (else `held`, "after HH:MM"), works, passes the gate (once more on the
same session when red), and lands. Every task change publishes `ideas.changed`. All git: realm/idea_git.py.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from orkcraft.realm import halt, harnesses, jobs, status, tool_errors
from orkcraft.realm.idea_git import CRITICAL_TESTS, Conflict, IdeaGit, env_name, read_secret

CHANGED = "ideas.changed"          # slug: an idea's state or one of its tasks changed
HARNESS = "claude"
LIMITS_EVERY_S = 600               # how often the runner reads the quota itself, when nobody hands it one
DEFAULTS = {"max_parallel": 1, "merge_into": "main", "push": True}
STOPPED = "stopped"
LIVE = ("running", "testing")
PAGE_KEEP = 20000
CLAUDE_KEEP = 12000

FIX = """The gate after your work said no:

{problem}

Fix it in this same worktree and commit the fix (every change committed). Then stop."""


def now_iso() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def setting(settings: Any, key: str, default: Any = None) -> Any:
    """`ideas.<key>` of the settings, however they carry it: an `ideas` dict or object, `ideas_<key>`, a dict."""
    default = DEFAULTS.get(key) if default is None else default
    ideas = settings.get("ideas") if isinstance(settings, dict) else getattr(settings, "ideas", None)
    if isinstance(ideas, dict) and key in ideas:
        return ideas[key]
    if ideas is not None and not isinstance(ideas, dict) and hasattr(ideas, key):
        return getattr(ideas, key)
    for name in (f"ideas_{key}", f"ideas.{key}"):
        if isinstance(settings, dict) and name in settings:
            return settings[name]
        if not isinstance(settings, dict) and hasattr(settings, name.replace(".", "_")):
            return getattr(settings, name.replace(".", "_"))
    return default


def _until_of(note: str, now: float) -> float | None:
    """The time an "after HH:MM" note means: today's, else tomorrow's when it has passed by more than an hour."""
    try:
        hh, mm = note.split("after", 1)[1].strip().split()[0].split(":")[:2]
        t = dt.datetime.fromtimestamp(now).replace(hour=int(hh), minute=int(mm[:2]), second=0, microsecond=0)
    except (IndexError, ValueError):
        return None
    if t.timestamp() < now - 3600:
        t += dt.timedelta(days=1)
    return t.timestamp()


class Held(Exception):
    def __init__(self, until: float) -> None:
        super().__init__("held")
        self.until = until


@dataclass
class Run:
    thread: threading.Thread
    cancel: threading.Event
    why: str = ""                  # set when someone stopped it


class IdeaRunner:
    def __init__(self, repo_root: Path, state_dir: Path, settings: Any, bus: Any = None, *,
                 limits: Callable[[], list] | None = None) -> None:
        """`limits`: the quota readers' last read (the town's `limits`); without it the runner reads it itself."""
        self.repo_root, self.state_dir = Path(repo_root), Path(state_dir)
        self.settings, self.bus = settings, bus
        self.git = IdeaGit(self.repo_root)
        self._limits_fn = limits
        self._limits: list = []
        self._limits_at = 0.0
        self._lock = threading.RLock()
        self._runs: dict[tuple[str, str], Run] = {}
        self._active: list[str] = []
        self._until: dict[tuple[str, str], float] = {}
        self._resume_working()

    # -- files -----------------------------------------------------------------------------------

    def _dir(self, slug: str) -> Path:
        return self.state_dir / "ideas" / slug

    def _read(self, path: Path) -> dict | None:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return data if isinstance(data, dict) else None

    def _write(self, path: Path, data: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        os.replace(tmp, path)

    def plan(self, slug: str) -> dict | None:
        plan = self._read(self._dir(slug) / "plan.json")
        if plan is None or not isinstance(plan.get("tasks"), list):
            return None
        return plan

    def _save_tasks(self, slug: str, tasks: list[dict]) -> None:
        """Write the tasks into the plan as it is on disk now (the to-dos and the rest stay as they are there)."""
        plan = self.plan(slug) or {"idea": slug, "todos": []}
        plan["tasks"] = tasks
        self._write(self._dir(slug) / "plan.json", plan)

    def _set_task(self, slug: str, task_id: str, **fields: Any) -> None:
        with self._lock:
            plan = self.plan(slug)
            if plan is None:
                return
            for t in plan["tasks"]:
                if t.get("id") == task_id:
                    t.update(fields)
            self._save_tasks(slug, plan["tasks"])
        self._changed(slug)

    def _set_idea(self, slug: str, state: str, error: str = "") -> None:
        path = self._dir(slug) / "state.json"
        data = self._read(path) or {}
        data.update(state=state, error=error)
        self._write(path, data)

    def _changed(self, slug: str) -> None:
        if self.bus is not None:
            try:
                self.bus.publish(CHANGED, slug=slug)
            except Exception:              # a face's subscriber never stops the work
                pass

    def _resume_working(self) -> None:
        """After a restart: the ideas that were `working` go on; a task cut off mid-run is ready again."""
        for state_file in sorted((self.state_dir / "ideas").glob("*/state.json")):
            slug = state_file.parent.name
            if (self._read(state_file) or {}).get("state") != "working" or (plan := self.plan(slug)) is None:
                continue
            for t in plan["tasks"]:
                if t.get("state") in LIVE:
                    t.update(state="ready", note="")
            self._save_tasks(slug, plan["tasks"])
            self._active.append(slug)

    # -- the commands ----------------------------------------------------------------------------

    def start(self, slug: str) -> None:
        """The plan was passed (or Start again): every task not merged waits anew, the idea is `working`."""
        with self._lock:
            plan = self.plan(slug)
            if plan is None:
                raise RuntimeError(f"no plan for {slug!r}")
            for t in plan["tasks"]:
                if (slug, t.get("id")) in self._runs:
                    continue
                if t.get("state") != "merged":
                    t.update(state="waiting", error="", note="")
                self._until.pop((slug, t.get("id")), None)
            self._save_tasks(slug, plan["tasks"])
            self._set_idea(slug, "working")
            if slug not in self._active:
                self._active.append(slug)
        self._changed(slug)
        self.tick()

    def stop(self, slug: str, why: str = "stopped by you") -> None:
        """Its running tasks stop (their worktrees stay until the next start); the idea needs you."""
        with self._lock:
            runs = [(k, r) for k, r in self._runs.items() if k[0] == slug]
            for _key, run in runs:
                run.why = why
                run.cancel.set()
            plan = self.plan(slug)
            if plan is not None:
                for t in plan["tasks"]:
                    if t.get("state") in ("ready", "held", *LIVE):
                        t.update(state="failed", error=why, finished=now_iso())
                self._save_tasks(slug, plan["tasks"])
            if slug in self._active:
                self._active.remove(slug)
                self._set_idea(slug, "failed", why)
        self._changed(slug)

    def stop_all(self) -> None:
        """Stop all (`realm/halt`): every idea's tasks stop and nothing new starts."""
        with self._lock:
            slugs = list(dict.fromkeys([*self._active, *(k[0] for k in self._runs)]))
        for slug in slugs:
            self.stop(slug, "stopped by Stop all")

    def busy(self) -> bool:
        with self._lock:
            return bool(self._runs)

    # -- the tick --------------------------------------------------------------------------------

    def tick(self) -> None:
        """Move what can move: waiting → ready, a held task whose window came back, a free slot → a task starts,
        an idea whose tasks are all merged → done, one with a failed task (and none running) → failed."""
        now = time.time()
        with self._lock:
            limits = self._read_limits(now)
            slots = max(1, int(setting(self.settings, "max_parallel") or 1)) - len(self._runs)
            for slug in list(self._active):
                plan = self.plan(slug)
                if plan is None:
                    self._active.remove(slug)
                    continue
                tasks, changed = plan["tasks"], self._advance(slug, plan, now)
                running = [t for t in tasks if (slug, t.get("id")) in self._runs]
                failed = next((t for t in tasks if t.get("state") == "failed"), None)
                if failed is not None or all(t.get("state") == "merged" for t in tasks):
                    if changed:
                        self._save_tasks(slug, tasks)
                    if not running:
                        self._finish(slug, failed)
                    elif changed:
                        self._changed(slug)
                    continue
                for t in tasks:
                    if slots <= 0:
                        break
                    if t.get("state") != "ready":
                        continue
                    until = status.reset_of(limits, HARNESS, now, status.NEARLY)
                    if until is not None:
                        self._hold(slug, t, until)
                    else:
                        self._launch(slug, t)
                        slots -= 1
                    changed = True
                if changed:
                    self._save_tasks(slug, tasks)
                    self._changed(slug)

    def _advance(self, slug: str, plan: dict, now: float) -> bool:
        tasks = plan["tasks"]
        merged = {t.get("id") for t in tasks if t.get("state") == "merged"}
        todos = [d for d in plan.get("todos") or [] if isinstance(d, dict)]
        changed = False
        for t in tasks:
            tid, state = t.get("id"), t.get("state")
            if state == "held":
                until = self._until.get((slug, tid)) or _until_of(t.get("note", ""), now) or now
                if until > now:
                    continue
                self._until.pop((slug, tid), None)
                t.update(state="waiting", note="")
                state, changed = "waiting", True
            if state in LIVE and (slug, tid) not in self._runs:      # its thread is gone (should not happen)
                t.update(state="ready")
                changed = True
            if state not in ("waiting", "", None):
                continue
            after_ok = all(a in merged for a in t.get("after") or [])
            todos_ok = all(d.get("done") for d in todos if tid in (d.get("for") or []))
            if after_ok and todos_ok:
                t["state"], changed = "ready", True
            elif state != "waiting":
                t["state"], changed = "waiting", True
        return changed

    def _finish(self, slug: str, failed: dict | None) -> None:
        self._active.remove(slug)
        if failed is None:
            self._set_idea(slug, "done")
        else:
            why = failed.get("error") or "it failed"
            self._set_idea(slug, "failed", f"{failed.get('title') or failed.get('id')}: {why}")
        self._changed(slug)

    def _hold(self, slug: str, task: dict, until: float) -> None:
        self._until[(slug, task.get("id"))] = until
        task.update(state="held", note=f"after {dt.datetime.fromtimestamp(until):%H:%M}")

    def _read_limits(self, now: float) -> list:
        if self._limits_fn is not None:
            try:
                return list(self._limits_fn() or [])
            except Exception:
                return []
        if now - self._limits_at > LIMITS_EVERY_S:
            self._limits_at = now

            def read() -> None:
                from orkcraft.sources.limits import fetch_limits
                try:
                    self._limits = list(fetch_limits(self.repo_root))
                except Exception:          # a quota never stops the work
                    pass
            threading.Thread(target=read, daemon=True, name="ideas-limits").start()
        return self._limits

    # -- one task --------------------------------------------------------------------------------

    def _launch(self, slug: str, task: dict) -> None:
        tid = task.get("id")
        cancel = threading.Event()
        task.update(state="running", started=now_iso(), finished="", error="", note="",
                    branch=f"idea/{slug}/{tid}", commit="", session="", cost=None, tokens=None)
        thread = threading.Thread(target=self._work, args=(slug, tid, cancel), daemon=True,
                                  name=f"idea-{slug}-{tid}")
        self._runs[(slug, tid)] = Run(thread, cancel)
        thread.start()

    def _work(self, slug: str, tid: str, cancel: threading.Event) -> None:
        path: Path | None = None
        spent = {"cost": None, "tokens": None}
        try:
            plan = self.plan(slug) or {"tasks": []}
            task = next(t for t in plan["tasks"] if t.get("id") == tid)
            base = str(setting(self.settings, "merge_into") or "main")
            path, branch = self.git.prepare(slug, tid, base)
            start_sha = self.git.head(path)
            h = harnesses.need(HARNESS)
            model = h.pick(task.get("tier") or "warrior")
            env = self._env(slug, tid, plan)
            session = self._session(slug, tid, path, cancel, model, env, self._prompt(slug, plan, task), "", spent)
            for attempt in (1, 2):
                self._set_task(slug, tid, state="testing")
                problem = self._check(path, start_sha, cancel)
                if problem is None:
                    break
                if attempt == 2:
                    raise RuntimeError(f"the gate is still red after one fix: {problem[-600:]}")
                self._set_task(slug, tid, state="running")
                session = self._session(slug, tid, path, cancel, model, env, FIX.format(problem=problem), session,
                                        spent)
            commit, subjects, note = self.git.land(path, branch, base, bool(setting(self.settings, "push")))
            self._set_task(slug, tid, state="merged", commit=commit, subjects=subjects, note=note,
                           finished=now_iso(), error="")
            self.git.remove(path)
        except Held as e:
            with self._lock:
                self._until[(slug, tid)] = e.until
            self._set_task(slug, tid, state="held", note=f"after {dt.datetime.fromtimestamp(e.until):%H:%M}",
                           finished="")
        except (InterruptedError, halt.Halted) as e:
            run = self._runs.get((slug, tid))
            why = (run.why if run else "") or (str(e) if isinstance(e, halt.Halted) else STOPPED)
            self._set_task(slug, tid, state="failed", error=why, finished=now_iso())
        except Conflict as e:
            self._set_task(slug, tid, state="failed", error=str(e), finished=now_iso())
        except Exception as e:             # a task's failure is said on its card, never a crash of the host
            self._set_task(slug, tid, state="failed", error=" ".join(str(e).split())[:600] or type(e).__name__,
                           finished=now_iso())
        finally:
            with self._lock:
                self._runs.pop((slug, tid), None)
            self._changed(slug)
            try:
                self.tick()
            except Exception:
                pass

    def _session(self, slug: str, tid: str, path: Path, cancel: threading.Event, model: str, env: dict,
                 prompt: str, resume: str, spent: dict) -> str:
        """One turn of the task's Claude session (work mode); its cost and tokens add up on the task."""
        try:
            _text, cost, tokens, session = jobs.run_work(HARNESS, prompt, path, cancel, model=model, env=env,
                                                         resume=resume)
        except tool_errors.ToolError as e:
            if e.kind != tool_errors.LIMIT:
                raise
            now = time.time()
            raise Held(status.reset_of(self._read_limits(now), HARNESS, now, 1.0)
                       or now + status.UNKNOWN_RESET_S) from e
        for key, value in (("cost", cost), ("tokens", tokens)):
            if value is not None:
                spent[key] = (spent[key] or 0) + value
        session = session or resume
        self._set_task(slug, tid, session=session, cost=spent["cost"], tokens=spent["tokens"])
        return session

    def _check(self, path: Path, start_sha: str, cancel: threading.Event) -> str | None:
        """None when the task's work passes; else what is wrong, in words the session can act on."""
        if not self.git.commits(path, start_sha):
            return "You made no commit. Commit your work with git (clear messages); uncommitted work is lost."
        if self.git.dirty(path):
            return "You left uncommitted changes: `git status` shows them. Commit them (or remove what is not work)."
        ok, tail = self.git.gate(path, start_sha, cancel)
        return None if ok else f"The tests failed:\n{tail}"

    def _env(self, slug: str, tid: str, plan: dict) -> dict[str, str]:
        """The task's environment: who runs (for the town's counts) and the values of its `secret` to-dos."""
        env = {"ORKCRAFT_ORC": f"ideas/{slug}-{tid}"}
        for todo in plan.get("todos") or []:
            if not isinstance(todo, dict) or todo.get("kind") != "secret" or tid not in (todo.get("for") or []):
                continue
            name = env_name(str(todo.get("title") or ""))
            value = read_secret(self.state_dir, slug, str(todo.get("id") or "")) if name else None
            if name and value:
                env[name] = value
        return env

    # -- the prompt ------------------------------------------------------------------------------

    def _page(self, slug: str) -> str:
        """The idea's page (the Wiki joined to the board, else llm-wiki/general): the newest one found."""
        found = [p for pattern in (f"llm-wiki/*/pages/ideas/{slug}.md", f"*/pages/ideas/{slug}.md",
                                   f"pages/ideas/{slug}.md") for p in self.repo_root.glob(pattern) if p.is_file()]
        if not found:
            return ""
        newest = max(found, key=lambda p: p.stat().st_mtime)
        try:
            return newest.read_text(encoding="utf-8")[:PAGE_KEEP]
        except OSError:
            return ""

    def _prompt(self, slug: str, plan: dict, task: dict) -> str:
        tasks = plan.get("tasks") or []
        before = tasks[:tasks.index(task)] if task in tasks else []
        done = []
        for t in before:
            merged = "; ".join(t.get("subjects") or []) if t.get("state") == "merged" else ""
            done.append(f"- {t.get('id')} · {t.get('title', '')} ({t.get('state')})"
                        + (f" — merged: {merged}" if merged else "") + f"\n  {t.get('brief', '')}")
        try:
            rules = (self.repo_root / "CLAUDE.md").read_text(encoding="utf-8")[:CLAUDE_KEEP]
        except OSError:
            rules = ""
        secrets = [n for n in self._env(slug, task.get("id"), plan) if n != "ORKCRAFT_ORC"]
        parts = [
            f"You do one task of the idea `{slug}` in this repository: a git worktree on branch "
            f"`idea/{slug}/{task.get('id')}`, cut from `{setting(self.settings, 'merge_into') or 'main'}`. "
            "Work only here.",
            "# The idea\n\n" + (self._page(slug) or "(its page was not found)"),
            f"# Your task: {task.get('title', '')}\n\n{task.get('brief', '')}",
        ]
        if done:
            parts.append("# The tasks before yours\n\n" + "\n".join(done))
        if rules:
            parts.append("# The repository's rules (CLAUDE.md)\n\n" + rules)
        finish = ("# When you are done\n\nCommit your work with git, with clear messages: what is not committed is "
                  f"lost. The gate runs `python -m pytest -q {' '.join(CRITICAL_TESTS)}` and the test files of the "
                  "modules you touch; run them before you stop.")
        if secrets:
            finish += (" The environment holds " + ", ".join(secrets) + ": use them from the environment, never "
                       "print them, write them to a file or commit them.")
        parts.append(finish)
        return "\n\n".join(parts)
