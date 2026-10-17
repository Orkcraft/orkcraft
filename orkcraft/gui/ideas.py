"""The board's host commands (spec 29a §6): tracks and ideas from the Wiki, the keeper, the runner.

    ideas = Ideas(host)
    host.commands.update(ideas.commands())     # ideas.board, ideas.page, ideas.add, … (the phone may call them all)
    ideas.tick(now)                            # the host's clock: the keeper's batch, the runner's tick
    ideas.snapshot()                           # focus, ideas_rev, needs_you, review_count, limits: in the snapshot
    ideas.stop_all()                           # Stop all

The pages live in the Wiki joined to the board (`realm/ideas.py`), what runs on them in `.orkcraft/ideas/`. The
keeper (`core/idea_keeper.py`) reads, talks and plans in the background; the runner (`core/idea_runner.py`, spec 29a
part B) carries a passed plan's tasks to `main`. Every change bumps `ideas_rev`, so the board and the phone know to
look again.

Spec 33 adds Review: the results waiting for the person (`ideas.review_list`, `ideas.diff`), their three answers
(`ideas.merge`, `ideas.back`, `ideas.drop_task`), `ideas.stop_task`, the Agents window (`ideas.agents`), one task
with its log (`ideas.task`) and the branch results merge into (`ideas.into`).
"""
from __future__ import annotations

import base64
import datetime as dt
import os
import time
from pathlib import Path
from typing import Any, Callable

from orkcraft import settings
from orkcraft.core import idea_keeper
from orkcraft.realm import catalog, event_log, idea_secrets, ideas, wiki
from orkcraft.gui.ideas_args import IdeasError, _device, _opt, _str, _text
from orkcraft.gui.ideas_goals import GoalsMixin
from orkcraft.gui.ideas_limits import LimitsMixin
from orkcraft.gui.ideas_roles import RolesMixin
from orkcraft.realm.idea_git import IdeaGit

RUNNER_TICK_S = 3.0               # how often the runner looks at its tasks
SNAPSHOT_S = 10.0                 # the most a cached Needs you count is kept without a change
PHONE_ZIP_MAX = 8 * 1024 * 1024   # a zip the phone is handed in a message: larger waits for the computer
OPENED = ("idea", "plan", "todo", "task", "result", "tab")
NEEDS_KIND = {"asks": "asks", "plan": "plan", "failed": "failed"}


def focus_of(machine) -> str:
    """The focus the window and the phone show: `ORKCRAFT_FOCUS` when set ("" the whole town, "board"), else the
    machine's setting. Tests set it to "" (tests/conftest.py), so the town's own suites see the town."""
    env = os.environ.get("ORKCRAFT_FOCUS")
    return env if env in settings.FOCUSES else machine.focus


class _Hop:
    """The bus as the runner gets it: a publish from its thread is made on the host's (town.call)."""

    def __init__(self, town) -> None:
        self.town = town

    def publish(self, topic: str, **data: Any) -> None:
        self.town.call(lambda: self.town.publish(topic, **data))


class Ideas(LimitsMixin, GoalsMixin, RolesMixin):
    def __init__(self, host) -> None:
        self.host = host
        self.town = host.town
        self.state_dir = Path(self.town.repo_root) / ".orkcraft"
        self.rev = 0
        self._cache: tuple[int, float, dict] | None = None
        self._runner: Any = None
        self._runner_error = ""
        self._runner_at = 0.0
        self._limits: list[dict] = []
        self._limits_at = float("-inf")
        self._limits_busy = False
        self._seen: dict[str, tuple[str, float]] = {}     # slug → (state, when it began): keeper_state
        self._limits_logged = float("-inf")
        self.keeper = idea_keeper.IdeaKeeper(
            self.town.repo_root, self.state_dir, self.root, lambda: self.town.machine.ideas, self._publish,
            demo=bool(self.town.demo), budget_ok=lambda: self.town.budget_ok())
        self.town.bus.subscribe(idea_keeper.CHANGED, self._changed)

    # -- where the pages are --------------------------------------------------------------------------------

    def root(self) -> Path:
        """The Wiki joined to the board: the board's `wiki` (a Wiki's id), else the camp's first Wiki (team or
        general first), else `llm-wiki/general/` in the town's folder."""
        repo = Path(self.town.repo_root)
        found, named = [], ""
        for bid, spec in self.town.custom_specs.items():
            spec = catalog.migrate(spec)
            if spec.get("type") == "fields" and not named:
                named = str((spec.get("config") or {}).get("wiki") or "")
            elif spec.get("type") == "scrolls":
                bs = self.town.scroll.building(bid)
                if bs is not None and not bs.demolished:
                    topic = str((spec.get("config") or {}).get("topic") or "general")
                    found.append((topic not in ("team", "general"), bid))
        for _rank, bid in sorted(found, key=lambda f: (f[1] != named, *f)):
            w = self.town.worker(bid)
            root = getattr(w, "wiki_root", None)
            if root is not None:
                return Path(root)
        return wiki.root_of(repo, None, "general")

    # -- the bus, the clock, the snapshot ------------------------------------------------------------------

    def _publish(self, slug: str) -> None:
        """From the keeper's thread: `ideas.changed` on the host's."""
        self.town.call(lambda: self.town.publish(idea_keeper.CHANGED, slug=slug))

    def _changed(self, event) -> None:
        self.rev += 1
        slug = str((getattr(event, "data", None) or {}).get("slug") or "")
        if slug:
            try:
                if slug.startswith("goal:"):
                    self.goal_event(slug[5:])
                else:
                    self._state_event(slug)
            except Exception:                   # a log never stops the board
                pass

    # -- the event log (spec 33 §9): every action of the shell, for the day's analysis ------------------------

    def _ev(self, event: str, args: dict | None = None, **fields: Any) -> None:
        """One line of `.orkcraft/usage/events.jsonl`; none in the demo. `device`: "phone" (put there by the listener) or "desktop"."""
        if not self.town.demo:
            if args is not None:
                fields["device"] = _device(args)
            event_log.record(Path(self.town.repo_root), event, **fields)

    def _state_event(self, slug: str) -> None:
        """`keeper_state` when an idea's state changed, and `plan_made` when it reaches `plan`."""
        state = str(ideas.state(self.state_dir, slug).get("state") or "")
        now = time.monotonic()
        was, since = self._seen.get(slug, ("", None))
        if state == was:
            return
        self._seen[slug] = (state, now)
        self._ev(event_log.KEEPER_STATE, idea=slug, state=state, was=was, seconds=round(now - since, 1) if since else None)
        if state == "plan":
            plan = ideas.plan(self.state_dir, slug) or {}
            est = plan.get("estimate") or {}
            self._ev(event_log.PLAN_MADE, idea=slug, tasks=len(plan.get("tasks") or []), todos=len(plan.get("todos") or []),
                     usd_low=est.get("usd_low"), usd_high=est.get("usd_high"))

    def _since(self, iso: object) -> float | None:
        try:
            return round(max(0.0, time.time() - dt.datetime.fromisoformat(str(iso)).timestamp()), 1)
        except ValueError:
            return None

    def changed(self, slug: str) -> None:
        self.town.publish(idea_keeper.CHANGED, slug=slug)

    def runner(self, need: bool = False):
        """The runner (spec 29a part B), made once; None while this build has none (`need`: say so instead)."""
        if self._runner is None and not self._runner_error:
            try:
                from orkcraft.core.idea_runner import IdeaRunner
                self._runner = IdeaRunner(self.town.repo_root, self.state_dir, self.town.machine, _Hop(self.town),
                                          events=not self.town.demo, on_held=lambda: self.log_limits(force=True))
            except ImportError:
                self._runner_error = "The runner is not in this build yet: plans cannot start"
            except Exception as e:              # a runner that cannot start never stops the board
                self._runner_error = f"The runner could not start: {e}"
        if self._runner is None and need:
            raise IdeasError(self._runner_error)
        return self._runner

    def tick(self, now: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        try:
            self.keeper.tick()
        except Exception as e:                  # the keeper's batch never stops the clock
            self.town.toast(f"{type(e).__name__}: {e}", title="The keeper", severity="error")
        if now - self._runner_at >= RUNNER_TICK_S:
            self._runner_at = now
            runner = self.runner() if self._ever_passed() else self._runner
            if runner is not None:
                try:
                    runner.tick()
                except Exception as e:
                    self.town.toast(f"{type(e).__name__}: {e}", title="The runner", severity="error")

    def _ever_passed(self) -> bool:
        folder = self.state_dir / "ideas"
        return folder.is_dir() and any((p / "plan.json").exists() for p in folder.iterdir() if p.is_dir())

    def stop_all(self, device: str = "desktop") -> None:
        self._ev(event_log.STOP_ALL, count=len(getattr(self._runner, "_runs", {}) or {}), device=device or "desktop")
        self.keeper.stop_all()
        if self._runner is not None:
            try:
                self._runner.stop_all()
            except Exception:
                pass

    def snapshot(self) -> dict[str, Any]:
        """What the page's snapshot carries of the board: the focus, the rev, how many ideas need the person, and
        each idea's state (what a push says when it changes: gui/mobile.py `news`)."""
        now = time.monotonic()
        if self._cache is None or self._cache[0] != self.rev or now - self._cache[1] > SNAPSHOT_S:
            try:
                b = self.board(make=False)
                waiting = self.results()
                data = {"needs_you": len(b["today"]["needs_you"]),
                        "idea_states": [{"slug": i["slug"], "title": i["title"], "state": i["state"]} for i in b["ideas"]],
                        "review_count": len(waiting),
                        "review_results": [{k: r[k] for k in ("idea", "task", "title")} for r in waiting]}
            except Exception:                   # a broken page never breaks the town's snapshot
                data = {"needs_you": 0, "idea_states": [], "review_count": 0, "review_results": []}
            self._cache = (self.rev, now, data)
        return {"focus": focus_of(self.town.machine), "ideas_rev": self.rev, **self._cache[2],
                "limits": self.limits()}

    # -- reading -------------------------------------------------------------------------------------------

    def _state(self, slug: str) -> dict:
        st = ideas.state(self.state_dir, slug)
        if st["state"] in ("reading", "planning") and not self.keeper.busy(slug):
            st["state"] = "raw" if st["state"] == "reading" else "ready"     # a run the host lost (it closed)
        return st

    def board(self, make: bool = True) -> dict[str, Any]:
        """`make`: General (and the Wiki) written when missing; the snapshot only reads."""
        root = self.root()
        tracks = [self._goal_row(g) for g in ideas.tracks(root, make=make)]
        out, todos, needs = [], [], self.goal_needs(tracks)
        for i in ideas.ideas(root):
            slug = i["slug"]
            st, plan, page = self._state(slug), ideas.plan(self.state_dir, slug), ideas.idea_page(root, slug)
            tasks = (plan or {}).get("tasks") or []
            asks = ideas.items(page.section("Open questions")) if page else []
            out.append({"slug": slug, "title": i["title"], "track": i["track"], "order": i["order"],
                        "state": st["state"], "size": i["size"], "thesis": i["thesis"], "asks": len(asks), "priority": i["priority"],
                        "progress": {"done": sum(1 for t in tasks if t.get("state") == "merged"), "total": len(tasks)},
                        "updated": ideas.touched_at(root, self.state_dir, slug)})
            kind = NEEDS_KIND.get(st["state"])
            if kind:
                text = {"asks": asks[0] if asks else "The keeper asks you",
                        "plan": "Plan ready" + (f" · {len(tasks)} tasks" if tasks else ""),
                        "failed": st.get("error") or "Something failed"}[kind]
                needs.append({"idea": slug, "kind": kind, "title": i["title"], "text": text})
            for t in tasks:
                if t.get("state") == "held":
                    needs.append({"idea": slug, "kind": "held", "title": i["title"],
                                  "text": f"{t.get('title', '')}: {t.get('note') or 'held'}"})
            if plan and st["state"] in ("plan", "working", "failed"):
                todos += [{"idea": slug, **{k: td.get(k) for k in ("id", "title", "kind", "why", "choices", "steps",
                                                                    "done")}}
                          for td in plan.get("todos") or [] if not td.get("done")]
        return {"tracks": tracks, "ideas": out, "today": {"todos": todos, "needs_you": needs},
                "batch_next": self.keeper.batch_next(), "rev": self.rev, "demo": bool(self.town.demo)}

    def page(self, slug: str) -> dict[str, Any]:
        root = self.root()
        page = ideas.idea_page(root, slug)
        if page is None:
            raise IdeasError("That idea is gone")
        names = list(ideas.SECTIONS) + [n for n, _t in page.sections if n not in ideas.SECTIONS]
        st = self._state(slug)
        return {"slug": slug, "title": page.title or slug, "track": page.get("track") or ideas.GENERAL,
                "state": st["state"], "size": page.get("size") if page.get("size") in ideas.SIZES else "",
                "sections": [{"name": n, "thesis": ideas.thesis(page.section(n)), "text": page.section(n)}
                             for n in names],
                "talk": ideas.talk(self.state_dir, slug), "plan": ideas.plan(self.state_dir, slug),
                "busy": bool(self.keeper.busy(slug)) or st["state"] in ("reading", "planning"),
                "error": st.get("error", ""), "proposed_track": page.get("proposed_track")}

    # -- writing -------------------------------------------------------------------------------------------

    def add(self, args: dict) -> dict:
        text = _text(args, "text", ideas.SECTION_CHARS)
        slug = ideas.add_idea(self.root(), text, _opt(args, "track") or ideas.GENERAL, self.state_dir)
        ideas.add_turn(self.state_dir, slug, "you", text, "Gist")     # the person's own words, kept
        now = args.get("now") is True
        self._ev(event_log.IDEA_ADDED, args, idea=slug, track=_opt(args, "track") or ideas.GENERAL, chars=len(text), now=now)
        out = {"slug": slug}
        if now:                                 # Process now: the keeper reads it at once (else the batch does)
            try:
                self.keeper.read_now(slug)
            except idea_keeper.KeeperError as e:
                ideas.save_state(self.state_dir, slug, error=str(e))
                out["error"] = str(e)
        self.changed(slug)
        return out

    def say(self, args: dict) -> dict:
        slug = _text(args, "slug", 100)
        text = _text(args, "text", ideas.SECTION_CHARS)
        if args.get("goal") is True or (ideas.idea_page(self.root(), slug) is None and ideas.track_page(self.root(), slug)):
            self._read_goal(slug, text)         # the answer to a goal's questions: the same talk, on the goal
            self._ev(event_log.IDEA_SAID, args, idea=f"goal:{slug}", section="", chars=len(text), text=text)
            self.changed(f"goal:{slug}")
            return {"ok": True}
        self.keeper.say(slug, text, _opt(args, "section"))
        self._ev(event_log.IDEA_SAID, args, idea=slug, section=_opt(args, "section"), chars=len(text), text=text)
        self.changed(slug)
        return {"ok": True}

    def plan(self, args: dict) -> dict:
        slug = _text(args, "slug", 100)
        self.keeper.plan(slug)
        self.changed(slug)
        return {"ok": True}

    def start(self, args: dict) -> dict:
        """The person passes the plan: it is the runner's from now on, and it starts."""
        slug = _text(args, "slug", 100)
        plan = ideas.plan(self.state_dir, slug)
        if plan is None:
            raise IdeasError("This idea has no plan yet: Take it to work first")
        st = self._state(slug)["state"]
        if st not in ("plan", "failed", "working"):
            raise IdeasError("Its plan is not ready")
        runner = self.runner(need=True)
        if not plan.get("passed_at"):
            ideas.edit_plan(self.state_dir, slug, lambda p: p.update(
                passed_at=time.strftime("%Y-%m-%dT%H:%M:%S")))
            self._ev(event_log.PLAN_PASSED, args, idea=slug, tasks=len(plan.get("tasks") or []), seconds=self._since(plan.get("made_at")))
        ideas.save_state(self.state_dir, slug, state="working", error="")
        runner.start(slug)
        self.changed(slug)
        return {"ok": True}

    def stop(self, args: dict) -> dict:
        slug = _text(args, "slug", 100)
        self.runner(need=True).stop(slug)
        self.changed(slug)
        return {"ok": True}

    def move(self, args: dict) -> dict:
        slug = _text(args, "slug", 100)
        ideas.move(self.root(), slug, _opt(args, "track") or None, _opt(args, "before") or None, by="person")
        self.changed(slug)
        return {"ok": True}

    def edit(self, args: dict) -> dict:
        slug = _text(args, "slug", 100)
        if self.keeper.busy(slug):
            raise IdeasError("The keeper is writing this idea: a moment")
        ideas.set_section(self.root(), slug, _text(args, "section", 60), _str(args, "text", ideas.SECTION_CHARS))
        self.changed(slug)
        return {"ok": True}

    def track_add(self, args: dict) -> dict:
        slug = ideas.add_track(self.root(), _text(args, "title", ideas.TITLE_CHARS))
        self.changed("")
        return {"slug": slug}

    def track_set(self, args: dict) -> dict:
        criteria = args.get("criteria")
        if criteria is not None and not isinstance(criteria, list):
            raise IdeasError("Success criteria are a list")
        about, deadline = args.get("about"), args.get("deadline")
        ideas.set_track(self.root(), _text(args, "slug", 100),
                        about=str(about)[:ideas.SECTION_CHARS] if isinstance(about, str) else None,
                        criteria=criteria, deadline=str(deadline) if isinstance(deadline, str) else None)
        self.changed("")
        return {"ok": True}

    def todo(self, args: dict) -> dict:
        """A to-do of a plan ticked (or unticked). A secret's value goes to the machine's secret store; the plan
        says only "stored". This is the one write to a passed plan: the runner reads the to-do as done."""
        slug, tid = _text(args, "idea", 100), _text(args, "id", 20)
        plan = ideas.plan(self.state_dir, slug)
        todo = next((t for t in (plan or {}).get("todos") or [] if t.get("id") == tid), None)
        if todo is None:
            raise IdeasError("That to-do is gone")
        done, value = bool(args.get("done")), args.get("value")
        kept: Any = todo.get("value")
        if done and todo.get("kind") == "secret":
            if not isinstance(value, str) or not value.strip():
                if todo.get("value") != "stored":
                    raise IdeasError("A secret needs its value")
            else:
                idea_secrets.put(self.state_dir, slug, tid, value.strip())
                kept = "stored"
        elif done and todo.get("kind") == "choice":
            if value not in (todo.get("choices") or []):
                raise IdeasError("Pick one of its choices")
            kept = value
        elif isinstance(value, str) and value.strip():
            kept = value.strip()[:500]

        def tick(p: dict) -> None:
            for t in p.get("todos") or []:
                if t.get("id") == tid:
                    t["done"], t["value"] = done, kept
            if not p.get("passed_at"):
                idea_keeper.readiness(p)

        ideas.edit_plan(self.state_dir, slug, tick)
        if done:                                # a secret's value is never logged: only that it was done
            self._ev(event_log.TODO_DONE, args, idea=slug, todo=tid, kind=todo.get("kind"), seconds=self._since(plan.get("made_at")))
        self.changed(slug)
        return {"ok": True}

    def drop(self, args: dict) -> dict:
        slug = _text(args, "slug", 100)
        if self.keeper.busy(slug):
            raise IdeasError("The keeper is busy with this idea: a moment")
        plan = ideas.plan(self.state_dir, slug) or {}
        if self._runner is not None and plan.get("passed_at"):
            self._runner.stop(slug)
        secrets = [t["id"] for t in plan.get("todos") or [] if t.get("kind") == "secret" and t.get("id")]
        ideas.drop(self.root(), slug, self.state_dir)
        idea_secrets.forget(self.state_dir, slug, secrets)
        self.changed(slug)
        return {"ok": True}

    # -- Review, Agents, one task (spec 33 §5) -------------------------------------------------------------

    def _into(self) -> str:
        return str((self.town.machine.ideas or {}).get("merge_into") or settings.IDEAS["merge_into"])

    def _plans(self) -> list[tuple[str, str, dict]]:
        """(slug, title, plan) of every idea that has a plan, in the board's order."""
        out = []
        for i in ideas.ideas(self.root()):
            plan = ideas.plan(self.state_dir, i["slug"])
            if plan:
                out.append((i["slug"], i["title"], plan))
        return out

    def results(self) -> list[dict]:
        """The results waiting at Review, oldest first."""
        out = []
        for slug, title, plan in self._plans():
            for t in plan.get("tasks") or []:
                if t.get("state") == "review":
                    out.append({"idea": slug, "idea_title": title, "task": t.get("id"), "title": t.get("title", ""),
                                "round": int(t.get("round") or 1), "tests": t.get("tests") or _NO_TESTS,
                                "diff": t.get("diff") or {"files": 0, "added": 0, "removed": 0},
                                "cost": t.get("cost"), "conflict": t.get("conflict") or "",
                                "finished": t.get("finished") or ""})
        return sorted(out, key=lambda r: r["finished"])

    def review_list(self, args: dict) -> dict:
        m = self.town.machine.ideas or {}
        try:
            branches = IdeaGit(Path(self.town.repo_root)).branches()
        except Exception:                       # not a git folder yet: the picker offers only the current branch
            branches = []
        into = self._into()
        return {"into": into, "push": bool(m.get("push", settings.IDEAS["push"])),
                "branches": branches if into in branches else [into, *branches], "results": self.results()}

    def _task(self, args: dict) -> tuple[str, str, dict, dict]:
        slug, tid = _text(args, "slug", 100), _text(args, "task", 40)
        plan = ideas.plan(self.state_dir, slug)
        task = next((t for t in (plan or {}).get("tasks") or [] if t.get("id") == tid), None)
        if task is None:
            raise IdeasError("That task is gone")
        return slug, tid, task, plan

    def diff(self, args: dict) -> dict:
        _slug, _tid, task, _plan = self._task(args)
        branch = str(task.get("branch") or "")
        if not branch:
            raise IdeasError("That task has no code yet")
        git = IdeaGit(Path(self.town.repo_root))
        try:
            got = git.diff(branch, str(task.get("base") or self._into()))
        except Exception as e:
            raise IdeasError("Its code cannot be read: " + " ".join(str(e).split())[:200]) from None
        return {**got, "base": self._into()}

    def merge(self, args: dict) -> dict:
        slug, tid, _task, _plan = self._task(args)
        commit = self.runner(need=True).merge(slug, tid, device=_device(args))
        self.changed(slug)
        return {"ok": True, "commit": commit}

    def back(self, args: dict) -> dict:
        slug, tid, _task, _plan = self._task(args)
        self.runner(need=True).back(slug, tid, _text(args, "why", 1000), device=_device(args))
        self.changed(slug)
        return {"ok": True}

    def drop_task(self, args: dict) -> dict:
        slug, tid, _task, _plan = self._task(args)
        self.runner(need=True).drop_task(slug, tid, device=_device(args))
        self.changed(slug)
        return {"ok": True}

    def stop_task(self, args: dict) -> dict:
        slug, tid, _task, _plan = self._task(args)
        self.runner(need=True).stop_task(slug, tid, device=_device(args))
        self.changed(slug)
        return {"ok": True}

    def task(self, args: dict) -> dict:
        slug, tid, task, plan = self._task(args)
        page = ideas.idea_page(self.root(), slug)
        runner = self._runner
        return {**task, "idea": slug, "idea_title": (page.title if page else "") or slug,
                "log": runner.log(slug, tid) if runner is not None else "",
                "after": task.get("after") or [], "round": int(task.get("round") or 1)}

    def into(self, args: dict) -> dict:
        """The branch results merge into (made from the default branch when missing) and whether it is pushed."""
        branch, push = args.get("branch"), args.get("push")
        if branch is None and not isinstance(push, bool):
            raise IdeasError("branch is missing")
        mine = dict(self.town.machine.ideas or settings.IDEAS)
        if branch is not None:
            name = _text(args, "branch", 100)
            if settings.clean_ideas({"merge_into": name})["merge_into"] != name:
                raise IdeasError(f"{name!r} is not a branch name")
            try:
                IdeaGit(Path(self.town.repo_root)).ensure_branch(name)
            except RuntimeError as e:
                raise IdeasError(str(e)) from None
            mine["merge_into"] = name
        if isinstance(push, bool):
            mine["push"] = push
        self.town.machine.ideas = settings.clean_ideas(mine)
        settings.save(self.town.machine)
        self._ev(event_log.INTO_CHANGED, args, branch=self.town.machine.ideas["merge_into"], push=self.town.machine.ideas["push"])
        self.changed("")
        return {"ok": True}

    def log(self, args: dict) -> dict:
        """`ideas.log`: the shell's one event, `opened` — a preview or a tab the person opened. Any other event is refused."""
        if args.get("event") != event_log.OPENED:
            raise IdeasError("Only `opened` can be logged from here")
        what, ref = _opt(args, "what"), _opt(args, "ref")
        if what not in OPENED:
            raise IdeasError(f"`what` is one of {', '.join(OPENED)}")
        self._ev(event_log.OPENED, args, what=what, ref=ref)
        return {"ok": True}

    def logs(self, args: dict) -> dict:
        """The day's logs (or the last `days`) as the analytics zip, for a phone: {"name", "data": base64}. The computer's
        gear downloads the same zip from `/api/analytics`."""
        days = args.get("days")
        got = self.host.day_logs.pack_period(days if isinstance(days, int) and not isinstance(days, bool) and days > 0 else 1)
        if got is None:
            raise IdeasError("No logs yet")
        name, data = got
        if len(data) > PHONE_ZIP_MAX:
            raise IdeasError("The logs are too large for the phone: download them on the computer")
        return {"name": name, "data": base64.b64encode(data).decode("ascii")}

    def commands(self) -> dict[str, Callable[[dict], Any]]:
        def guarded(fn):
            def run(args: dict) -> Any:
                try:
                    return fn(args)
                except (ValueError, idea_keeper.KeeperError) as e:
                    raise IdeasError(str(e)) from None
                except Exception as e:
                    if type(e).__name__ != "RunnerError":      # the runner is loaded on demand: no import here
                        raise
                    raise IdeasError(str(e)) from None
            return run

        table = {"ideas.board": lambda a: self.board(), "ideas.page": lambda a: self.page(_text(a, "slug", 100)),
                 "ideas.add": self.add, "ideas.say": self.say, "ideas.plan": self.plan, "ideas.start": self.start,
                 "ideas.move": self.move, "ideas.edit": self.edit, "ideas.track_add": self.track_add,
                 "ideas.track_set": self.track_set, "ideas.todo": self.todo, "ideas.drop": self.drop,
                 "ideas.stop": self.stop, "ideas.review_list": self.review_list, "ideas.diff": self.diff,
                 "ideas.merge": self.merge, "ideas.back": self.back, "ideas.drop_task": self.drop_task,
                 "ideas.stop_task": self.stop_task, "ideas.agents": self.agents, "ideas.task": self.task,
                 "ideas.into": self.into, "ideas.log": self.log, "ideas.logs": self.logs, "ideas.goal_save": self.goal_save,
                 "ideas.goal": self.goal, "ideas.read_now": self.read_now, "ideas.doc": self.doc, "ideas.roles": self.roles,
                 "ideas.role_save": self.role_save, "ideas.role_drop": self.role_drop, "ideas.kind_set": self.kind_set}
        return {name: guarded(fn) for name, fn in table.items()}


_NO_TESTS = {"passed": 0, "failed": 0, "failing": [], "tail": ""}
