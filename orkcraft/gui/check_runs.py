"""✅ `orkcraft check` from the Test bench's window (docs/design/check.md §6): the check runs in a process of its own
(one town at a time), its lines come in as it goes, and its last verdict and its folder — every run and every model
call, for an agent to read — are a zip to download (`/api/check/latest`, gui/server.py).

    host.bench.check.start()      the check, on the budget's AI tool (the cheap one, agy)
    host.bench.check.state()      {"job": …, "last": {"stamp", "green", "report"}}
    host.bench.check.pack()       (file name, check.zip) of the last check
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import threading
from pathlib import Path

from orkcraft.realm import check, halt

KEY = "check"                        # its job among the bench's (gui/bench.py `jobs`)
LINES = 400


class CheckError(Exception):
    """A step the check refuses; its text is shown to the person."""


class CheckRuns:
    def __init__(self, engine) -> None:
        self.engine = engine                 # gui/bench.py Bench: its jobs
        self.host = engine.host

    @property
    def root(self) -> Path:
        return self.engine.root

    def job(self):
        return self.engine.jobs.get(KEY)

    def start(self, scenarios: list[str] | None = None, replay: bool = False) -> None:
        """The check (`replay`: the last one played back on its recorded answers: free, no AI tool called)."""
        if (job := self.job()) and not job.done:
            raise CheckError("A check is on: stop it first")
        from orkcraft.gui.bench import Job
        argv = [sys.executable, "-m", "orkcraft", "--repo", str(self.root), "check"]
        for s in scenarios or []:
            argv += ["--scenario", s]
        if replay:
            argv += ["--replay", "latest"]
        job = Job(KEY, KEY, "the check played back" if replay else "the check")
        try:
            job.proc = subprocess.Popen(argv, cwd=self.root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        text=True, start_new_session=True, env={**os.environ, "PYTHONUNBUFFERED": "1"})
        except OSError as e:
            raise CheckError(f"The check did not start: {e}") from None
        halt.started(job.proc, "lab/check", agent=True)
        self.engine.jobs[KEY] = job
        threading.Thread(target=self._follow, args=(job,), daemon=True, name="check").start()

    def _follow(self, job) -> None:
        for line in job.proc.stdout:
            if line.strip():
                job.lines = (job.lines + [line.rstrip()])[-LINES:]
        code = job.proc.wait()
        halt.ended(job.proc)
        if code not in (0, 1):                     # 1 is a red check, not a failure of it
            job.error = "stopped" if job.cancel.is_set() else f"the check ended with exit {code}"
        job.done = True
        self.host.town.call(self.host.on_change)

    def stop(self) -> None:
        job = self.job()
        if job is not None and not job.done and job.proc is not None:
            job.cancel.set()
            try:
                os.killpg(job.proc.pid, signal.SIGTERM)       # the check and the AI tools it started
            except (ProcessLookupError, PermissionError):
                pass

    def last(self) -> dict:
        from orkcraft import check_cli
        folder = check_cli.latest(self.root)
        if folder is None:
            return {}
        try:
            data = json.loads((folder / "results.json").read_text(encoding="utf-8"))
            report = (folder / "report.md").read_text(encoding="utf-8")
        except (OSError, ValueError):
            return {}
        return {"stamp": folder.name, "green": bool(data.get("green")), "report": report,
                "zip": (folder / "check.zip").is_file(),
                "told": check.told(self.root, folder.name, data.get("scenarios") or []),
                "idle": data.get("idle"), "since": data.get("since") or []}

    def state(self) -> dict:
        job = self.job()
        night = getattr(getattr(self.host, "nightly", None), "check", None)
        titles = {s.id: s.title for s in check.SCENARIOS}
        return {"job": job.public() if job else None, "last": self.last(),
                "scenarios": [{"id": s.id, "title": s.title, "checked": bool(s.type)} for s in check.SCENARIOS],
                "night": {**night.settings(), "tonight": [titles[i] for i in night.tonight()]} if night else None}

    def pack(self) -> tuple[str, bytes] | None:
        from orkcraft import check_cli
        folder = check_cli.latest(self.root)
        if folder is None or not (folder / "check.zip").is_file():
            return None
        return f"orkcraft-check-{folder.name}.zip", (folder / "check.zip").read_bytes()
