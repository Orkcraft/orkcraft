"""The console's jobs: a model call in a thread (the Recruiter, the Council, the steward's watch, a
redesign, the keeper). The snapshot carries every job (`jobs`), the page shows it, and when it is ready
the person takes it (`job.accept`) or lets it go (`job.drop`).

A part of `Console` (console.py): its methods run with the console as `self`.
"""
from __future__ import annotations

import threading
from typing import Any, Callable

from orkcraft.realm import fastpath, modes, tool_errors


def plain(text: str) -> str:
    """A label in today's words, no emoji (modes.plain, realm/lexicon.py)."""
    return modes.plain(text)


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
            tool_errors.taken()                      # this thread's AI tool failures from here on
            try:
                result, failed = work(), None
            except Exception as e:                   # a model call never takes the town down
                result, failed = None, f"{type(e).__name__}: {e}"
            # The AI tool that failed, even when the call turned it into its result's error.
            again = lambda: self._run(job, text, work, done)    # noqa: E731
            self.town.call(self._finished, jid, result, failed, done, tool_errors.taken(), again)

        threading.Thread(target=run, daemon=True, name=f"gui-{jid}").start()
        self.host.on_change()

    def _finished(self, jid: str, result: Any, failed: str | None, done: Callable[[dict, Any], None],
                  tool: tool_errors.ToolError | None = None, again: Callable[[], None] | None = None) -> None:
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
        if job["state"] == "failed" and tool is not None:   # an AI tool failed it: Switch, Retry, Details
            self._tool_failed(job, tool, again)

    def _tool_failed(self, job: dict, error: tool_errors.ToolError, again: Callable[[], None] | None) -> None:
        failures = getattr(self.host, "failures", None)
        if failures is None:
            return

        def retry() -> None:
            if self.jobs.get(job["id"]) is job:      # the same call, on the main tool as it is now
                again()
        failures.report(error, job["title"] or job["kind"], retry=retry if again else None)

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
