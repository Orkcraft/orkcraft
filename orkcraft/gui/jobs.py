"""The console's jobs: a model call in a thread (the Recruiter, the Council, the steward's watch, a
redesign, the keeper). The snapshot carries every job (`jobs`), the page shows it, and when it is ready
the person takes it (`job.accept`) or lets it go (`job.drop`).

A part of `Console` (console.py): its methods run with the console as `self`.
"""
from __future__ import annotations

import threading
from typing import Any, Callable

from orkcraft.realm import fastpath, modes


def plain(text: str) -> str:
    """What Office shows of a label: its words, no emoji (modes.text, realm/lexicon.py)."""
    return modes.text(text, modes.OFFICE)


class ConsoleError(Exception):
    """A console act the host refuses; the host turns it into a CommandError."""


class JobsMixin:
    def public_jobs(self) -> list[dict[str, Any]]:
        return [{k: v for k, v in j.items() if not k.startswith("_")} for j in self.jobs.values()]

    def _job(self, kind: str, building_id: str, text: str, work: Callable[[], Any],
             done: Callable[[dict, Any], None]) -> str:
        """`work()` in a thread; `done(job, result)` back on the host's thread."""
        jid = f"{kind}-{next(self._ids)}"
        self.jobs[jid] = {"id": jid, "kind": kind, "building": building_id, "title": plain(self.town.title_of(building_id)),
                          "state": "running", "text": text, "error": "", "view": {}}
        self._run(self.jobs[jid], text, work, done)
        return jid

    def _run(self, job: dict, text: str, work: Callable[[], Any], done: Callable[[dict, Any], None]) -> None:
        jid = job["id"]
        job.update(state="running", text=text, _accept=None)

        def run() -> None:
            try:
                result, failed = work(), None
            except Exception as e:                   # a model call never takes the town down
                result, failed = None, f"{type(e).__name__}: {e}"
            self.town.call(self._finished, jid, result, failed, done)

        threading.Thread(target=run, daemon=True, name=f"gui-{jid}").start()
        self.host.on_change()

    def _finished(self, jid: str, result: Any, failed: str | None, done: Callable[[dict, Any], None]) -> None:
        job = self.jobs.get(jid)
        if job is None:                              # let go while it ran
            return
        if failed:
            job.update(state="failed", error=failed[:500])
        else:
            try:
                done(job, result)
            except Exception as e:
                job.update(state="failed", error=f"{type(e).__name__}: {e}"[:500])
        self.host.refresh_roster()

    def drop(self, args: dict) -> bool:
        """The person lets a job go: a running one finishes unseen, a ready one is not taken."""
        job = self.jobs.pop(self._word(args, "job"), None)
        if job is not None and job.get("_verdict") is not None and not job.get("_blocked"):
            fastpath.log(self.town.repo_root, job["_verdict"], "cancelled")
        self.host.on_change()
        return job is not None

    def accept(self, args: dict) -> Any:
        job = self.jobs.get(self._word(args, "job"))
        if job is None:
            raise ConsoleError("That is gone")
        accept = job.get("_accept")
        if job["state"] not in ("ready", "verdict") or accept is None:
            raise ConsoleError("Nothing to take yet")
        return accept(job, args)
