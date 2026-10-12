"""Improve Orkcraft in the GUI (docs/design/improve-buildings.md §14): comments on any part of the window for the
Alchemist, the Mechanic's code findings from the logs, each written as a fix in a copy of Orkcraft's source by this
machine's main tool, shown, tried in the window (Preview) and sent to Orkcraft as a pull request.

    host.fixes = Fixes(host); host.commands.update(host.fixes.commands())
    host.fixes.preview_dir()      the copy whose page (orkcraft/gui/static) the server shows first, or None

The copies and the list live in `<state>/improve/` (`ORKCRAFT_STATE_DIR`, else ~/.orkcraft): they are about Orkcraft,
not a town. The pull request goes through the Orkcraft Improve app (realm/github_app.py), as the benches' do.
"""
from __future__ import annotations

import datetime as dt
import sys
import threading
from pathlib import Path

from orkcraft.core import running
from orkcraft.env import getenv
from orkcraft.realm import builders, day_review, fixes, github_app, jobs, work_copy
from orkcraft.sources import telemetry

STATIC = Path("orkcraft") / "gui" / "static"
DIFF_SHOWN = 60_000


class FixError(Exception):
    """A step that cannot be taken; its text is shown to the person."""


def folder() -> Path:
    return Path(getenv("STATE_DIR") or Path.home() / ".orkcraft") / "improve"


class Fixes:
    def __init__(self, host) -> None:
        self.host = host
        self.store = fixes.Store(folder())
        self.preview = ""                         # the fix whose page the window shows now
        self.sending: set[str] = set()
        self._stops: dict[str, threading.Event] = {}

    # -- what the window shows -----------------------------------------------------------------------------------

    def summary(self) -> dict:
        """For the snapshot: how many comments wait, how many fixes are written, ready or sent."""
        count = lambda state: sum(f.state == state for f in self.store.fixes)  # noqa: E731
        return {"comments": len(self.store.waiting()), "writing": count("writing"), "ready": count("ready"),
                "preview": self.preview}

    def state(self, args: dict | None = None) -> dict:
        acct = github_app.account()
        rows = []
        for f in self.store.fixes:
            top = Path(f.top) if f.top else None
            shown = work_copy.diff(top, f.base)[:DIFF_SHOWN] if top and top.is_dir() and f.state == "ready" else ""
            rows.append({"id": f.id, "who": fixes.WHO[f.who], "at": f.at, "asks": f.asks, "state": f.state,
                         "said": f.said, "files": f.files, "pr": f.pr, "error": f.error, "diff": shown,
                         "page": any(p.startswith(STATIC.as_posix()) for p in f.files),
                         "title": fixes.title(f), "sending": f.id in self.sending,
                         "comments": [c.text for c in self.store.comments if c.fix == f.id]})
        return {"comments": [{"id": c.id, "at": c.at, "text": c.text, "where": c.where} for c in self.store.waiting()],
                "fixes": rows, "preview": self.preview, "login": acct["login"] if acct else "",
                "kind": "worktree" if running.checkout() is not None else "package"}

    def preview_dir(self) -> Path | None:
        if not self.preview:
            return None
        try:
            f = self.store.get(self.preview)
        except KeyError:
            return None
        page = Path(f.top) / STATIC
        return page if page.is_dir() else None

    # -- comments ------------------------------------------------------------------------------------------------

    def comment(self, args: dict) -> dict:
        try:
            c = self.store.comment(str(args.get("text") or ""), args.get("where") if isinstance(args.get("where"),
                                                                                                dict) else {})
        except ValueError as e:
            raise FixError(str(e)) from None
        self._changed()
        n = len(self.store.waiting())
        return {"said": f"The Alchemist has it ({n} comment{'' if n == 1 else 's'} waiting): Improve Orkcraft writes "
                        "the fix", "id": c.id}

    def drop_comment(self, args: dict) -> dict:
        self.store.drop_comment(str(args.get("id") or ""))
        self._changed()
        return self.state()

    def ask(self, args: dict) -> dict:
        """The waiting comments (or those named) as one fix, written by the Alchemist."""
        ids = set(args.get("ids") or [])
        picked = [c for c in self.store.waiting() if not ids or c.id in ids]
        if not picked:
            raise FixError("No comment waits: turn on Comment mode and press the part of the window to change")
        f = self.store.fix("alchemist", [c.text for c in picked], "## The comments\n" + fixes.comments_about(picked))
        for c in picked:
            c.fix = f.id
        self.store.save()
        self._write(f)
        return self.state()

    # -- the Mechanic's findings ---------------------------------------------------------------------------------

    def finding(self, args: dict) -> dict:
        """A finding of read logs (gui/day_review.py) as a code fix the Mechanic writes."""
        key, n = str(args.get("day") or ""), int(args.get("n") or 0)
        review = day_review.load(self.host.town.repo_root, key)
        if review is None or not 0 <= n < len(review.findings):
            raise FixError("That finding is gone: read the logs again")
        g = review.findings[n]
        spots = {h["id"]: h for h in review.hotspots}
        cited = "\n".join(f"- {h}: {spots[h]['said']}" for h in g.hotspots if h in spots)
        where = self.host.town.title_of(g.building) if g.building else "the town"
        about = (f"## The finding (from the logs of {day_review.label(key)})\nWhere: {where} (`{g.building}`)\n"
                 f"What is wrong: {g.what}\nWhy it matters: {g.why}\nThe change ({g.kind}): {g.change}\n"
                 f"It rests on:\n{cited}")
        f = self.store.fix("mechanic", [g.what], about)
        self._write(f)
        return {"said": "The Mechanic is writing the fix: Improve Orkcraft shows it when done", "id": f.id}

    # -- writing a fix -------------------------------------------------------------------------------------------

    def _write(self, f: fixes.Fix, more: str = "") -> None:
        checkout = running.checkout()
        if not f.top or not Path(f.top).is_dir():
            try:
                copy = work_copy.make(folder() / "copies" / f.id, checkout)
            except (OSError, RuntimeError) as e:
                f.state, f.error = "failed", f"The copy of Orkcraft's source could not be made: {e}"[:400]
                self.store.save()
                self._changed()
                return
            f.top, f.base, f.kind = copy["top"], copy["base"], copy["kind"]
            work_copy.allow_tests(Path(f.top), sys.executable)
        f.state, f.error, f.rounds = "writing", "", f.rounds + 1
        self.store.save()
        text = fixes.prompt(f, f.kind, sys.executable, more)
        stop = self._stops[f.id] = threading.Event()
        tool = builders.main_tool(self.host.town.machine)

        def work() -> None:
            said, error = "", ""
            try:
                with telemetry.tagged("retro"):
                    said = jobs.run_work(tool, text, Path(f.top), stop)[0]
            except (RuntimeError, OSError) as e:
                error = str(e)[:400] or type(e).__name__
            self.host.town.call(done, said, error)

        def done(said: str, error: str) -> None:
            self._stops.pop(f.id, None)
            if f not in self.store.fixes:          # dropped while it was written
                return
            top = Path(f.top)
            f.files = work_copy.changed(top, f.base) if top.is_dir() else []
            if error:
                f.state, f.error = "failed", error
            elif not f.files:
                f.state, f.said = "empty", said.strip()[:3000]
            else:
                f.state, f.said = "ready", said.strip()[:3000]
            self.store.save()
            word = {"ready": "wrote a fix", "empty": "changed nothing", "failed": "could not write the fix"}[f.state]
            who = fixes.WHO[f.who]
            self.host.town.toast(f"{who[0].upper()}{who[1:]} {word}: {fixes.title(f)}"[:240],
                                 title="Improve Orkcraft", severity="error" if error else "information")
            self._changed()

        threading.Thread(target=work, daemon=True, name=f"fix-{f.id}").start()
        self._changed()

    def again(self, args: dict) -> dict:
        f = self._fix(args)
        if f.state == "writing":
            raise FixError("It is being written")
        self._write(f, str(args.get("text") or ""))
        return self.state()

    def drop(self, args: dict) -> dict:
        f = self._fix(args)
        stop = self._stops.pop(f.id, None)
        if stop is not None:
            stop.set()
        if self.preview == f.id:
            self.preview = ""
        if f.top:
            work_copy.drop(Path(f.top), running.checkout() if f.kind == "worktree" else None)
        self.store.drop(f.id)
        self._changed()
        return self.state()

    def show(self, args: dict) -> dict:
        """Preview: the window's page from the fix's copy (its js and css; its Python runs once Orkcraft takes it)."""
        fid = str(args.get("id") or "")
        if fid:
            f = self._fix(args)
            if not (Path(f.top) / STATIC).is_dir():
                raise FixError("Its copy is gone")
        self.preview = fid
        self._changed()
        return {**self.state(), "reload": True}

    # -- the pull request ----------------------------------------------------------------------------------------

    def preview_pr(self, args: dict) -> dict:
        f = self._fix(args)
        if f.state not in ("ready", "sent"):
            raise FixError("Nothing to send yet")
        top = Path(f.top)
        paths = work_copy.changed(top, f.base)
        comments = [c for c in self.store.comments if c.fix == f.id]
        return {"title": fixes.title(f), "body": fixes.body(f, paths, comments, work_copy.deleted(top, f.base)),
                "diff": work_copy.diff(top, f.base)[:DIFF_SHOWN], "files": paths}

    def send(self, args: dict) -> dict:
        f = self._fix(args)
        if f.state != "ready":
            raise FixError("Only a written fix goes" if f.state != "sent" else f"Sent already: {f.pr}")
        if github_app.account() is None:
            raise FixError("Connect GitHub first: the mascot's menu → GitHub")
        if f.id in self.sending:
            raise FixError("It is being sent")
        got = self.preview_pr(args)
        changes = work_copy.files(Path(f.top), f.base)
        branch = f"improve/{f.who}-{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}"
        self.sending.add(f.id)

        def work() -> None:
            url, error = "", ""
            try:
                url = github_app.send(changes, got["title"], got["body"], branch)
            except github_app.GithubError as e:
                error = str(e)
            except Exception as e:  # the network, GitHub's answer: said, the fix stays ready
                error = f"GitHub: {e}"[:300]
            self.host.town.call(sent, url, error)

        def sent(url: str, error: str) -> None:
            self.sending.discard(f.id)
            if error:
                f.error = error
                self.host.town.toast(error, title="Improve Orkcraft", severity="error")
            else:
                f.state, f.pr, f.error = "sent", url, ""
                self.host.town.toast(f"Pull request opened: {url}", title="Improve Orkcraft")
            self.store.save()
            self._changed()

        threading.Thread(target=work, daemon=True, name="fix-pr").start()
        self._changed()
        return self.state()

    # -- plumbing ------------------------------------------------------------------------------------------------

    def _fix(self, args: dict) -> fixes.Fix:
        try:
            return self.store.get(str(args.get("id") or ""))
        except KeyError:
            raise FixError("That fix is gone") from None

    def _changed(self) -> None:
        cb = getattr(self.host, "on_change", None)
        if callable(cb):
            cb()

    def close(self) -> None:
        for stop in self._stops.values():
            stop.set()

    def commands(self) -> dict:
        return {"fixes.state": self.state, "fixes.comment": self.comment, "fixes.drop_comment": self.drop_comment,
                "fixes.ask": self.ask, "fixes.finding": self.finding, "fixes.again": self.again,
                "fixes.drop": self.drop, "fixes.preview": self.show, "fixes.pr": self.preview_pr,
                "fixes.send": self.send}
