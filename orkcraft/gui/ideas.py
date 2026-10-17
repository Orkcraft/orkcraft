"""The board's host commands (spec 29a §6): tracks and ideas from the Wiki, the keeper, the runner.

    ideas = Ideas(host)
    host.commands.update(ideas.commands())     # ideas.board, ideas.page, ideas.add, … (the phone may call them all)
    ideas.tick(now)                            # the host's clock: the keeper's batch, the runner's tick
    ideas.snapshot()                           # focus, ideas_rev, needs_you, the digest: in the page's snapshot
    ideas.stop_all()                           # Stop all

The pages live in the Wiki joined to the board (`realm/ideas.py`), what runs on them in `.orkcraft/ideas/`. The
keeper (`core/idea_keeper.py`) reads, talks and plans in the background; the runner (`core/idea_runner.py`, spec 29a
part B) carries a passed plan's tasks to `main`. Every change bumps `ideas_rev`, so the board and the phone know to
look again.
"""
from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Any, Callable

from orkcraft import settings
from orkcraft.core import idea_keeper
from orkcraft.realm import catalog, idea_merged, idea_secrets, ideas, wiki

RUNNER_TICK_S = 3.0               # how often the runner looks at its tasks
SNAPSHOT_S = 10.0                 # the most a cached Needs you count is kept without a change
NEEDS_KIND = {"asks": "asks", "plan": "plan", "failed": "failed"}


def focus_of(machine) -> str:
    """The focus the window and the phone show: `ORKCRAFT_FOCUS` when set ("" the whole town, "board"), else the
    machine's setting. Tests set it to "" (tests/conftest.py), so the town's own suites see the town."""
    env = os.environ.get("ORKCRAFT_FOCUS")
    return env if env in settings.FOCUSES else machine.focus


class IdeasError(Exception):
    """A board command the host refuses, in plain words."""


class _Hop:
    """The bus as the runner gets it: a publish from its thread is made on the host's (town.call)."""

    def __init__(self, town) -> None:
        self.town = town

    def publish(self, topic: str, **data: Any) -> None:
        self.town.call(lambda: self.town.publish(topic, **data))


class Ideas:
    def __init__(self, host) -> None:
        self.host = host
        self.town = host.town
        self.state_dir = Path(self.town.repo_root) / ".orkcraft"
        self.rev = 0
        self._cache: tuple[int, float, dict] | None = None
        self._runner: Any = None
        self._runner_error = ""
        self._runner_at = 0.0
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

    def _changed(self, _event) -> None:
        self.rev += 1

    def changed(self, slug: str) -> None:
        self.town.publish(idea_keeper.CHANGED, slug=slug)

    def runner(self, need: bool = False):
        """The runner (spec 29a part B), made once; None while this build has none (`need`: say so instead)."""
        if self._runner is None and not self._runner_error:
            try:
                from orkcraft.core.idea_runner import IdeaRunner
                self._runner = IdeaRunner(self.town.repo_root, self.state_dir, self.town.machine, _Hop(self.town))
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

    def stop_all(self) -> None:
        self.keeper.stop_all()
        if self._runner is not None:
            try:
                self._runner.stop_all()
            except Exception:
                pass

    def snapshot(self) -> dict[str, Any]:
        """What the page's snapshot carries of the board: the focus, the rev, how many ideas need the person, each
        idea's state (what a push says when it changes: gui/mobile.py `news`; `held` when a task of a working idea
        waits for its tool's window) and the digest of this hour, if one is due (spec 29c §4)."""
        now = time.monotonic()
        if self._cache is None or self._cache[0] != self.rev or now - self._cache[1] > SNAPSHOT_S:
            try:
                b = self.board(make=False)
                held = {n["idea"] for n in b["today"]["needs_you"] if n["kind"] == "held"}
                data = {"needs_you": len(b["today"]["needs_you"]),
                        "idea_states": [{"slug": i["slug"], "title": i["title"],
                                         "state": "held" if i["state"] == "working" and i["slug"] in held
                                         else i["state"]} for i in b["ideas"]]}
            except Exception:                   # a broken page never breaks the town's snapshot
                data = {"needs_you": 0, "idea_states": []}
            self._cache = (self.rev, now, data)
        try:
            digest = idea_merged.due(self.state_dir, self.town.machine.ideas.get("digest_hours") or [])
        except Exception:
            digest = None
        return {"focus": focus_of(self.town.machine), "ideas_rev": self.rev, **self._cache[2], "digest": digest}

    # -- reading -------------------------------------------------------------------------------------------

    def _state(self, slug: str) -> dict:
        st = ideas.state(self.state_dir, slug)
        if st["state"] in ("reading", "planning") and not self.keeper.busy(slug):
            st["state"] = "raw" if st["state"] == "reading" else "ready"     # a run the host lost (it closed)
        return st

    def board(self, make: bool = True) -> dict[str, Any]:
        """`make`: General (and the Wiki) written when missing; the snapshot only reads."""
        root = self.root()
        tracks = ideas.tracks(root, make=make)
        out, todos, needs = [], [], []
        for i in ideas.ideas(root):
            slug = i["slug"]
            st, plan, page = self._state(slug), ideas.plan(self.state_dir, slug), ideas.idea_page(root, slug)
            tasks = (plan or {}).get("tasks") or []
            asks = ideas.items(page.section("Open questions")) if page else []
            out.append({"slug": slug, "title": i["title"], "track": i["track"], "order": i["order"],
                        "state": st["state"], "size": i["size"], "thesis": i["thesis"], "asks": len(asks),
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
        merged, more = idea_merged.unseen(self.state_dir)
        busy = self._runner.reverting() if self._runner is not None else set()
        merged = [{**m, "reverting": (m["idea"], m["task"]) in busy} for m in merged]
        return {"tracks": tracks, "ideas": out,
                "today": {"todos": todos, "needs_you": needs, "merged": merged, "merged_more": more},
                "batch_next": self.keeper.batch_next(), "rev": self.rev, "demo": bool(self.town.demo)}

    def page(self, slug: str) -> dict[str, Any]:
        root = self.root()
        page = ideas.idea_page(root, slug)
        if page is None:
            raise IdeasError("That idea is gone")
        names = list(ideas.SECTIONS) + [n for n, _t in page.sections if n not in ideas.SECTIONS]
        st = self._state(slug)
        size = page.get("size") if page.get("size") in ideas.SIZES else ""
        return {"slug": slug, "title": page.title or slug, "track": page.get("track") or ideas.GENERAL,
                "state": st["state"], "size": size,
                "sections": [{"name": n, "thesis": ideas.thesis(page.section(n)), "text": page.section(n),
                              "shown": ideas.shown(size, n, page.section(n))} for n in names],
                "questions": ideas.questions(self.state_dir, slug),
                "talk": ideas.talk(self.state_dir, slug), "plan": ideas.plan(self.state_dir, slug),
                "busy": bool(self.keeper.busy(slug)) or st["state"] in ("reading", "planning"),
                "error": st.get("error", ""), "proposed_track": page.get("proposed_track")}

    # -- writing -------------------------------------------------------------------------------------------

    def add(self, args: dict) -> dict:
        text = _text(args, "text", ideas.SECTION_CHARS)
        slug = ideas.add_idea(self.root(), text, _opt(args, "track") or ideas.GENERAL, self.state_dir)
        ideas.add_turn(self.state_dir, slug, "you", text, "Gist")     # the person's own words, kept
        self.changed(slug)
        return {"slug": slug}

    def say(self, args: dict) -> dict:
        slug = _text(args, "slug", 100)
        self.keeper.say(slug, _text(args, "text", ideas.SECTION_CHARS), _opt(args, "section"))
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
        ideas.move(self.root(), slug, _opt(args, "track") or None, _opt(args, "before") or None)
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

    # -- after the merge, questions as choices (spec 29c) ------------------------------------------------------

    def seen(self, args: dict) -> dict:
        """Looked: one merged task (`idea` and `task`), an idea's, or all of them (no args)."""
        idea_merged.mark(self.state_dir, _opt(args, "idea"), _opt(args, "task"), seen=True)
        self.changed(_opt(args, "idea"))
        return {"ok": True}

    def revert(self, args: dict) -> dict:
        """Revert a merged task on the branch. The gate takes a while and the host has one thread, so it runs on its
        own: what it refuses at once is the answer's `error`; a revert that fails later (a conflict, a red gate) is
        said in a toast, the branch untouched; one that lands moves the idea to Needs you (*Reverted: …*)."""
        slug, task = _text(args, "idea", 100), _text(args, "task", 20)
        line = idea_merged.find(self.state_dir, slug, task)
        if line is None:
            raise IdeasError("Nothing of that task reached the branch")
        if line["reverted"]:
            raise IdeasError("That task is reverted already")
        runner = self.runner(need=True)
        if runner.working(slug):
            raise IdeasError("Its idea is still working: stop it first")

        def work() -> None:
            out = runner.revert(slug, task)
            if out.get("error"):
                self.town.call(lambda: self.town.toast(out["error"], title=f"Revert “{line['subject']}”",
                                                       severity="error"))
            self._publish(slug)

        threading.Thread(target=work, daemon=True, name=f"idea-revert-{slug}").start()
        self.changed(slug)
        return {"ok": True}

    def answer(self, args: dict) -> dict:
        """The person answers one of the keeper's questions; all answered, they go to the talk at once."""
        slug, qid = _text(args, "slug", 100), _text(args, "id", 20)
        choice, text = args.get("choice"), args.get("text")
        if choice is not None and (not isinstance(choice, int) or isinstance(choice, bool)):
            raise IdeasError("choice is not a number")
        if text is not None and not isinstance(text, str):
            raise IdeasError("text is not text")
        left = self.keeper.answer(slug, qid, choice, text)
        self.changed(slug)
        return {"ok": True, "left": left}

    def commands(self) -> dict[str, Callable[[dict], Any]]:
        def guarded(fn):
            def run(args: dict) -> Any:
                try:
                    return fn(args)
                except (ValueError, idea_keeper.KeeperError) as e:
                    raise IdeasError(str(e)) from None
            return run

        table = {"ideas.board": lambda a: self.board(), "ideas.page": lambda a: self.page(_text(a, "slug", 100)),
                 "ideas.add": self.add, "ideas.say": self.say, "ideas.plan": self.plan, "ideas.start": self.start,
                 "ideas.move": self.move, "ideas.edit": self.edit, "ideas.track_add": self.track_add,
                 "ideas.track_set": self.track_set, "ideas.todo": self.todo, "ideas.drop": self.drop,
                 "ideas.stop": self.stop, "ideas.seen": self.seen, "ideas.revert": self.revert,
                 "ideas.answer": self.answer}
        return {name: guarded(fn) for name, fn in table.items()}


def _str(args: dict, key: str, limit: int) -> str:
    value = args.get(key, "")
    if not isinstance(value, str):
        raise IdeasError(f"{key} is not text")
    return value[:limit]


def _text(args: dict, key: str, limit: int) -> str:
    value = _str(args, key, limit).strip()
    if not value:
        raise IdeasError(f"{key} is missing")
    return value


def _opt(args: dict, key: str) -> str:
    value = args.get(key)
    return value.strip()[:100] if isinstance(value, str) else ""
