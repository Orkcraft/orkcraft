"""The night gate (docs/specs/32-night-gate.md; decisions §39, §42, §45.6): `dev` tested every night, `main` by one press.

    gate = NightGate(repo_root, state_dir, lambda: machine.gate, bus)
    gate.tick()                  # the host's clock: at `gate.night_hour`, when `dev`'s head moved since the last run
    gate.run_now()               # Run now (`gate.run_night`): the same run, whatever the hour
    gate.latest()                # the newest report; gate.card() what the board and the Review gate show of it
    gate.pass_night(date)        # main ← the report's `dev` sha (a fast-forward), pushed: the one press
    gate.stop_all()              # Stop all

A run is a worktree on `night/<date>` off `dev`'s head and three steps, each recorded as it ends: the full suite, the
browser tests (the `*_browser.py` files), and the daily check — one Claude session (`gate.check_tier`) that reads what
merged into `dev` since `main` against the ideas it came from, and the failures, and fixes what fails on its branch,
within `gate.night_budget_usd` (said in the report; no new turn starts once it is spent). Its fix lands on `dev` only
through the gate a task passes (the critical tests, then the suite and the browser tests again). The report is
`.orkcraft/gate/night/<date>.json`. The run never moves `main`; only `pass_night` does, and only to the exact sha the
report was made on. Every ref changes under the repository lock the board's runner holds (realm/idea_git.py). No face.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import threading
from pathlib import Path
from typing import Any, Callable

from orkcraft.realm import halt, harnesses, idea_merged, jobs, lexicon, nightround, tool_errors
from orkcraft.realm.idea_git import CRITICAL_TESTS, Conflict, IdeaGit, _git

CHANGED = "ideas.changed"          # the board looks again (its rev): the night's card changed
HARNESS = "claude"
DEV, MAIN = "dev", "main"
DEFAULTS = {"night_hour": 3, "check_tier": "warrior", "night_budget_usd": 2.0}
SUITE, BROWSER, CHECK = "Full suite", "Browser tests", "Daily check"
SUITE_TIMEOUT_S = 3600
CHECK_TIMEOUT_S = 1800
CHECK_TURNS = 3                    # the check's turns at most: the first, and a fix when its gate is red
FAILED_KEEP = 40                   # failing test names a step keeps
TAIL = 4000                        # of a red step's output, what the check reads
COMMITS_KEEP = 200
PAGE_KEEP = 6000
STOPPED = "stopped by Stop all"
FAILED_LINE = re.compile(r"^(?:FAILED|ERROR) (\S+)", re.M)
COUNT_LINE = re.compile(r"\b\d+ (?:passed|failed|errors?|skipped|deselected)\b.*")

CHECK_PROMPT = """You are the {who}, at Orkline's Review gate: tonight's daily check of the `dev` branch before it may go to
`main`. You work in a git worktree on branch `{branch}`, cut from `dev`'s head. Work only here, and never touch `main`.

Your budget tonight is ${budget:.2f}; it is said in the report and nothing more is spent after it.

# What merged into `dev` since `main`

{commits}

# The ideas they came from (their pages: what each change was for)

{pages}

# Tonight's tests

{steps}

# Your job

1. Read each change against the idea it came from and its tests. Where the code does not do what its idea asks, or a
   test fails, fix it here, small and to the point. Do not widen anything, do not refactor what works.
2. Commit each fix with a clear message (what you leave uncommitted is committed for you).
3. A fix lands on `dev` only if the critical tests ({critical}), the full suite and the browser tests are green after it.
4. If everything is right, change nothing.

End your answer with one line of JSON, nothing after it:
{{"summary": "one sentence", "fixed": ["what you fixed"], "not_fixed": ["what fails and you could not fix, and why"]}}
"""

FIX_PROMPT = """The gate after your fix said no:

{problem}

Fix it in this same worktree, then end with the same one line of JSON."""


def now_iso() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def outcome(code: int, out: str) -> dict:
    """A pytest run as a step's `ok`, `summary` (pytest's count line) and `failed` (the names it ends with)."""
    failed = list(dict.fromkeys(FAILED_LINE.findall(out or "")))[:FAILED_KEEP]
    counts = [m.group(0).strip(" =") for m in COUNT_LINE.finditer(out or "")]
    if code == 5:                                  # nothing collected: nothing to fail
        return {"ok": True, "summary": "no tests", "failed": []}
    summary = counts[-1] if counts else ("passed" if code == 0 else f"exit {code}")
    return {"ok": code == 0, "summary": summary, "failed": failed}


def verdict(text: str) -> dict:
    """The check's last line of JSON: summary, fixed, not_fixed (strings); missing or broken → empty."""
    for line in reversed((text or "").strip().splitlines()):
        line = line.strip().strip("`")
        if line.startswith("{") and line.endswith("}"):
            try:
                got = json.loads(line)
            except ValueError:
                continue
            if isinstance(got, dict):
                lists = {k: [str(x)[:300] for x in got.get(k) or [] if isinstance(x, (str, int, float))][:20]
                         for k in ("fixed", "not_fixed") if isinstance(got.get(k) or [], list)}
                return {"summary": str(got.get("summary") or "")[:300], "fixed": lists.get("fixed", []),
                        "not_fixed": lists.get("not_fixed", [])}
    return {"summary": "", "fixed": [], "not_fixed": []}


class NightGate:
    def __init__(self, repo_root: Path, state_dir: Path, settings: Callable[[], dict] | None = None, bus: Any = None,
                 *, demo: bool = False, budget_ok: Callable[[], bool] | None = None) -> None:
        self.root, self.state_dir = Path(repo_root), Path(state_dir)
        self.settings = settings or (lambda: {})
        self.bus, self.demo = bus, demo
        self.budget_ok = budget_ok or (lambda: True)
        self.git = IdeaGit(self.root)
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._cancel = threading.Event()
        self._why = ""
        self._tried = ""                           # the date the clock last looked at (once a night)

    # -- settings and files ----------------------------------------------------------------------------------

    def setting(self, key: str) -> Any:
        try:
            got = (self.settings() or {}).get(key)
        except Exception:
            got = None
        return DEFAULTS[key] if got is None else got

    def folder(self) -> Path:
        return self.state_dir / "gate" / "night"

    def _path(self, date: str) -> Path:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date or ""):
            raise ValueError("That is not a night's date")
        return self.folder() / f"{date}.json"

    def report(self, date: str) -> dict | None:
        try:
            data = json.loads(self._path(date).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return data if isinstance(data, dict) else None

    def latest(self) -> dict | None:
        dates = sorted(p.stem for p in self.folder().glob("*.json") if re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.stem))
        return self.report(dates[-1]) if dates else None

    def _save(self, rep: dict) -> None:
        path = self._path(rep["date"])
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
        tmp.write_text(json.dumps(rep, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        os.replace(tmp, path)
        self._changed()

    def _changed(self) -> None:
        if self.bus is not None:
            try:
                self.bus.publish(CHANGED, slug="")
            except Exception:                      # a face's subscriber never stops the night
                pass

    # -- when ------------------------------------------------------------------------------------------------

    def running(self) -> bool:
        with self._lock:
            return self._thread is not None and self._thread.is_alive()

    def due(self, now: dt.datetime | None = None) -> bool:
        """At the night's hour, once a date, when `dev` exists and its head moved since the last run."""
        now = now or dt.datetime.now()
        if self.demo or nightround.off_by_env() or now.hour != int(self.setting("night_hour")):
            return False
        date = now.date().isoformat()
        if self._tried == date or self.running():
            return False
        self._tried = date
        if self.report(date) is not None:
            return False
        head = self.git.rev(f"refs/heads/{DEV}")
        last = self.latest() or {}
        return bool(head) and head not in (last.get("dev"), last.get("dev_start"))

    def tick(self, now: dt.datetime | None = None) -> bool:
        """The host's clock (every second is fine: it only looks once a night). True when a run started."""
        if not self.due(now):
            return False
        return self.start((now or dt.datetime.now()).date().isoformat())

    def run_now(self) -> bool:
        """Run now, whatever the hour and whether `dev` moved; False when one runs already."""
        if self.demo:
            raise RuntimeError("The demo town runs no night")
        if not self.git.rev(f"refs/heads/{DEV}"):
            raise RuntimeError(f"There is no `{DEV}` branch to test yet")
        return self.start(dt.date.today().isoformat())

    def start(self, date: str, wait: bool = False) -> bool:
        with self._lock:
            if self.running():
                return False
            self._cancel, self._why = threading.Event(), ""
            self._thread = threading.Thread(target=self._run, args=(date, self._cancel), daemon=True,
                                            name=f"night-gate-{date}")
            self._thread.start()
            thread = self._thread
        if wait:
            thread.join()
        return True

    def join(self, timeout: float | None = None) -> None:
        thread = self._thread
        if thread is not None:
            thread.join(timeout)

    def stop_all(self) -> None:
        """Stop all: the night's tests and its check end now; the report says so, nothing lands."""
        with self._lock:
            if self.running():
                self._why = STOPPED
                self._cancel.set()

    # -- the run ---------------------------------------------------------------------------------------------

    def _run(self, date: str, cancel: threading.Event) -> None:
        budget = float(self.setting("night_budget_usd"))
        rep: dict[str, Any] = {"date": date, "dev": "", "dev_start": "", "main": "", "commits": [], "steps": [],
                               "fixed": [], "not_fixed": [], "cost": 0.0, "budget": budget, "green": False,
                               "started": now_iso(), "finished": "", "running": True, "branch": f"night/{date}",
                               "error": ""}
        path: Path | None = None
        try:
            with self.git.lock:
                head = self.git.rev(f"refs/heads/{DEV}")
                if not head:
                    raise RuntimeError(f"There is no `{DEV}` branch to test")
                path = self.git.worktree(f"night/{date}", DEV, f"night-{date}")
            tested = self.git.head(path)
            rep.update(dev=tested, dev_start=tested, main=self.git.rev(f"refs/heads/{MAIN}"),
                       commits=self._commits(tested))
            self._save(rep)
            suite, browser, tails = self._suite(path, cancel)
            rep["steps"] = [suite, browser]
            self._save(rep)
            if rep["commits"]:
                self._check(path, tested, tails, cancel, rep)
            else:
                rep["steps"].append({"name": CHECK, "ok": True, "summary": "nothing merged since main", "failed": []})
            rep["green"] = all(s["ok"] for s in rep["steps"]) and not rep["not_fixed"]
        except (InterruptedError, halt.Halted) as e:
            rep["error"] = self._why or (str(e) if isinstance(e, halt.Halted) else STOPPED)
            rep["green"] = False
        except Exception as e:                     # a night that breaks says so in its report, never in the host
            rep["error"] = " ".join(str(e).split())[:600] or type(e).__name__
            rep["green"] = False
        finally:
            if path is not None:
                self.git.remove(path)
            rep.update(running=False, finished=now_iso(), cost=round(float(rep["cost"] or 0), 4))
            try:
                self._save(rep)
            except Exception:
                pass

    def _commits(self, tested: str) -> list[dict]:
        """What merged into `dev` since `main`, oldest first, each with the idea it came from (merged.jsonl)."""
        span = f"{MAIN}..{tested}" if self.git.rev(f"refs/heads/{MAIN}") else tested
        out = _git(self.root, "log", "--reverse", "--no-merges", f"-n{COMMITS_KEEP}", "--format=%H%x1f%s", span).stdout
        ideas: dict[str, str] = {}
        for row in idea_merged.rows(self.state_dir):
            if not row["commit"]:
                continue
            span_of = f"{row['base']}..{row['commit']}" if row.get("base") else f"{row['commit']}~1..{row['commit']}"
            for sha in _git(self.root, "rev-list", span_of).stdout.split():
                ideas.setdefault(sha, row["idea"])
        commits = []
        for line in out.splitlines():
            sha, _, subject = line.partition("\x1f")
            if sha:
                commits.append({"sha": sha, "subject": subject, "idea": ideas.get(sha, "")})
        return commits

    def _pytest(self, path: Path, args: list[str], cancel: threading.Event) -> tuple[dict, str]:
        code, out = self.git.pytest(path, args, cancel, SUITE_TIMEOUT_S, "gate/night")
        return outcome(code, out), out

    def browser_files(self, path: Path) -> list[str]:
        return sorted(p.relative_to(path).as_posix() for p in (path / "tests").rglob("*_browser.py")) \
            if (path / "tests").is_dir() else []

    def _suite(self, path: Path, cancel: threading.Event) -> tuple[dict, dict, str]:
        """Steps 1–2 in `path`: (the suite's step, the browser tests' step, both outputs' red tails)."""
        browser = self.browser_files(path)
        step1, out1 = self._pytest(path, [f"--ignore={f}" for f in browser], cancel)
        if browser:
            step2, out2 = self._pytest(path, browser, cancel)
        else:
            step2, out2 = {"ok": True, "summary": "no browser tests", "failed": []}, ""
        tails = "\n\n".join(f"$ {name}\n{out[-TAIL:]}" for name, step, out in
                            ((SUITE, step1, out1), (BROWSER, step2, out2)) if not step["ok"])
        return {"name": SUITE, **step1}, {"name": BROWSER, **step2}, tails

    # -- the daily check (§39) -------------------------------------------------------------------------------

    def _pages(self, slugs: list[str], path: Path) -> str:
        """The ideas' pages: the town's working tree (where the board writes them), else the night's worktree."""
        out = []
        for slug in slugs:
            found = [p for where in (self.root, path)
                     for pattern in (f"llm-wiki/*/pages/ideas/{slug}.md", f"*/pages/ideas/{slug}.md")
                     for p in where.glob(pattern) if p.is_file()]
            if found:
                try:
                    text = max(found, key=lambda p: p.stat().st_mtime).read_text(encoding="utf-8")[:PAGE_KEEP]
                except OSError:
                    continue
                out.append(f"## {slug}\n\n{text}")
        return "\n\n".join(out) or "(no idea pages: these changes came from elsewhere)"

    def _prompt(self, rep: dict, tails: str, path: Path) -> str:
        commits = "\n".join(f"- {c['sha'][:10]} {c['subject']}" + (f"  (idea: {c['idea']})" if c["idea"] else "")
                            for c in rep["commits"])
        steps = "\n".join(f"- {s['name']}: {'green' if s['ok'] else 'RED'} · {s['summary']}" for s in rep["steps"])
        if tails:
            steps += "\n\nThe failures:\n\n" + tails
        slugs = list(dict.fromkeys(c["idea"] for c in rep["commits"] if c["idea"]))
        return CHECK_PROMPT.format(who=lexicon.term("orc.loot"), branch=rep["branch"], budget=rep["budget"],
                                   commits=commits, pages=self._pages(slugs, path), steps=steps,
                                   critical=", ".join(CRITICAL_TESTS))

    def _check(self, path: Path, tested: str, tails: str, cancel: threading.Event, rep: dict) -> None:
        """One Claude session, its fix through the gate and onto `dev`; the check's step, fixed and not fixed."""
        budget, (suite, browser) = float(rep["budget"]), rep["steps"][:2]
        step = {"name": CHECK, "ok": False, "summary": "", "failed": []}
        red = [n for s in (suite, browser) for n in s["failed"]] or \
              [s["name"] for s in (suite, browser) if not s["ok"]]
        if budget <= 0:
            step.update(ok=suite["ok"] and browser["ok"], summary="off: its budget is $0")
            rep["steps"].append(step)
            rep["not_fixed"] = red
            return
        if not self.budget_ok():
            step.update(summary="not run: the town's spend is over its limit")
            rep["steps"].append(step)
            rep["not_fixed"] = red
            return
        try:
            model = harnesses.need(HARNESS).pick(str(self.setting("check_tier") or "warrior"))
        except Exception as e:                     # no Claude here: the check says so, the night is red
            step.update(summary=f"not run: {' '.join(str(e).split())[:200] or 'Claude is not set up'}")
            rep["steps"].append(step)
            rep["not_fixed"] = red
            return
        env = {"ORKCRAFT_ORC": "gate/night"}
        prompt, session, said = self._prompt(rep, tails, path), "", verdict("")
        landed, at_budget, problem, tested_steps = False, False, "", list(rep["steps"])
        for _turn in range(CHECK_TURNS):
            if float(rep["cost"]) >= budget:
                at_budget = True
                break
            try:
                text, cost, _tokens, session = jobs.run_work(HARNESS, prompt, path, cancel, model=model, env=env,
                                                             resume=session, timeout_s=CHECK_TIMEOUT_S)
            except tool_errors.ToolError as e:
                step["summary"] = f"Claude could not run: {e}"[:300]
                break
            rep["cost"] = round(float(rep["cost"]) + float(cost or 0), 4)
            got = verdict(text)
            said = got if got["summary"] or got["fixed"] or got["not_fixed"] else said
            self.git.commit_left(path, "Night check: fixes")
            if not self.git.commits(path, tested):
                break                                      # nothing to land: what it said stands
            problem = self._gate(path, tested, cancel, rep)
            if problem is None:
                head = self.git.head(path)
                try:
                    _commit, _subjects, note = self.git.land(path, rep["branch"], DEV, True)
                except (Conflict, RuntimeError) as e:     # dev is as it was: the night stands as it was tested
                    rep["steps"] = tested_steps
                    said["not_fixed"] = [*said["not_fixed"], f"its fix did not land on dev: {' '.join(str(e).split())[:200]}"]
                    break
                # The sha tested. Had `dev` moved meanwhile, the landed head differs and Pass says to run again.
                rep["dev"], rep["push"] = head, note
                landed = True
                break
            self._save(rep)
            prompt = FIX_PROMPT.format(problem=problem)
        if not landed and problem and float(rep["cost"]) >= budget:
            at_budget = True
        still = [n for s in rep["steps"][:2] for n in s["failed"]] or \
                [s["name"] for s in rep["steps"][:2] if not s["ok"]]
        rep["fixed"] = ([n for n in red if n not in still] if landed else []) + (said["fixed"] if landed else [])
        rep["not_fixed"] = list(dict.fromkeys(still + said["not_fixed"]))
        if at_budget and not landed:
            step["summary"] = f"stopped at its budget, ${budget:.2f}"
        elif not step["summary"]:
            step["summary"] = said["summary"] or ("fixed and landed on dev" if landed else
                                                  "nothing to fix" if not red else "could not fix it")
        if landed and not step["summary"].endswith("dev"):
            step["summary"] += " · landed on dev"
        step["ok"] = not rep["not_fixed"] and all(s["ok"] for s in rep["steps"][:2]) and not (at_budget and not landed)
        rep["steps"].append(step)

    def _gate(self, path: Path, tested: str, cancel: threading.Event, rep: dict) -> str | None:
        """The fix's gate, as a task's: the critical tests (and the touched modules'), then steps 1–2 again. None when
        green (the report's steps become the new runs), else what is wrong, in words the session can act on."""
        if self.git.dirty(path):
            return "You left uncommitted changes. Commit them (or remove what is not work)."
        ok, tail = self.git.gate(path, tested, cancel)
        if not ok:
            return f"The critical tests failed:\n{tail}"
        suite, browser, tails = self._suite(path, cancel)
        if not (suite["ok"] and browser["ok"]):
            return f"The tests failed:\n{tails}"
        rep["steps"] = [{**suite, "summary": f"{suite['summary']} after the night's fix"},
                        {**browser, "summary": f"{browser['summary']} after the night's fix"}]
        return None

    # -- the one press ---------------------------------------------------------------------------------------

    def pass_night(self, date: str) -> dict:
        """Pass to main: only a green report whose `dev` sha is still `dev`'s head. `main` is fast-forwarded to it
        (a merge commit only when `main` has commits of its own: a critical release), pushed, the report marked."""
        rep = self.report(date)
        if rep is None:
            return {"error": "There is no night report of that date"}
        if rep.get("running") and self.running():
            return {"error": "The night run is still on"}
        if rep.get("passed_at"):
            return {"error": "That night went to main already"}
        if not rep.get("green"):
            return {"error": "A red night does not go to main"}
        sha = str(rep.get("dev") or "")
        with self.git.lock:
            if not sha or self.git.rev(f"refs/heads/{DEV}") != sha:
                return {"error": f"{DEV} moved since the night; run again"}
            old = self.git.rev(f"refs/heads/{MAIN}")
            if not old:
                return {"error": f"There is no `{MAIN}` branch"}
            try:
                new = sha if self.git.is_ancestor(old, sha) else self._merge(date, sha)
                if new != old:
                    self.git.fast_forward(MAIN, old, new)
            except (Conflict, RuntimeError) as e:
                return {"error": f"{MAIN} is as it was: " + (" ".join(str(e).split())[:400] or type(e).__name__)}
            note = self.git.push(MAIN)
        rep.update(passed_by="you", passed_at=now_iso(), main_after=new, push=note)
        self._save(rep)
        return {"ok": True, "main": new, "note": note}

    def _merge(self, date: str, sha: str) -> str:
        """`main` has commits `dev` lacks (a critical release): a merge commit of `sha` on a worktree off `main`."""
        path = self.git.worktree(f"night/{date}-main", MAIN, f"night-{date}-main")
        try:
            done = _git(path, "-c", "user.name=Orkline", "-c", "user.email=orkline@localhost", "merge", "--no-ff",
                        "-m", f"Night gate {date}: {DEV} into {MAIN}", sha)
            if done.returncode != 0:
                _git(path, "merge", "--abort")
                raise Conflict(f"{DEV} does not merge cleanly into {MAIN}")
            return self.git.head(path)
        finally:
            self.git.remove(path)

    # -- what the faces show ---------------------------------------------------------------------------------

    def card(self) -> dict | None:
        """The night report as the board's Today and the Review gate show it; None before the first night."""
        rep = self.latest()
        if rep is None:
            return None
        head, running = self.git.rev(f"refs/heads/{DEV}"), bool(rep.get("running")) and self.running()
        cut = bool(rep.get("running")) and not running            # the town closed during the run
        return {"date": rep.get("date", ""), "green": bool(rep.get("green")) and not cut, "running": running,
                "count": len(rep.get("commits") or []), "commits": (rep.get("commits") or [])[:50],
                "steps": rep.get("steps") or [], "fixed": rep.get("fixed") or [],
                "not_fixed": rep.get("not_fixed") or [], "cost": rep.get("cost") or 0.0,
                "budget": rep.get("budget") or 0.0, "dev": rep.get("dev", ""), "main": rep.get("main", ""),
                "error": rep.get("error", "") or ("the run was cut off: the town closed" if cut else ""),
                "passed_at": rep.get("passed_at", ""),
                "stale": bool(rep.get("dev")) and head != rep.get("dev"), "started": rep.get("started", ""),
                "finished": rep.get("finished", ""), "hour": int(self.setting("night_hour"))}
