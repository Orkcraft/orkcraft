"""An AI tool that failed, as the page shows it: "<Tool> hit an error", one line of what happened, and
Switch to another tool, Retry, Details (realm/tool_errors.py says what each failure means).

    host.failures.report(err, "Recruiter", retry=lambda: ...)   # a face's own model call failed
    ← {"t": "toast", "severity": "error", "tool": {title, line, action, detail, switch, hint, retry}}

A service publishes `TOOL_ERROR` on the bus (Town.tool_failed); this turns it into the toast and keeps
what Retry runs again. Switch changes the machine's main tool (Settings → AI tools), the one decisions
and steps on `main` run on, then retries when it can: the same failure would come back on the tool that
failed, so a tool picked for one building is changed in that building's settings, not here.
"""
from __future__ import annotations

import itertools
import time
from typing import Any, Callable

from orkcraft import settings
from orkcraft.realm import harnesses, tool_errors

AGAIN_S = 60.0          # the same tool failing the same way within this shows one toast, not a stream
TOAST_S = 60            # a failure stays until it is read (or a minute)
KEEP_RETRIES = 20       # the newest Retry each toast can run


class Failures:
    def __init__(self, host) -> None:
        self.host = host
        self.retries: dict[str, Callable[[], Any]] = {}
        self.broken: dict[str, str] = {}             # tool id → the kind it failed with (missing, login)
        self._shown: dict[tuple[str, str], float] = {}
        self._ids = itertools.count(1)

    def commands(self) -> dict[str, Callable[[dict], Any]]:
        return {"tool_error.switch": self.switch, "tool_error.retry": self.retry}

    # -- what failed ---------------------------------------------------------------------------

    def report(self, error: tool_errors.ToolError, where: str = "",
               retry: Callable[[], Any] | None = None) -> dict[str, Any]:
        """A model call of the face failed on an AI tool: on the bus, with what Retry runs again."""
        rid = ""
        if retry is not None:
            rid = f"retry-{next(self._ids)}"
            self.retries[rid] = retry
            for old in list(self.retries)[:-KEEP_RETRIES]:
                self.retries.pop(old, None)
        return self.host.town.tool_failed(error, where, rid, broken=tuple(self.broken))

    def show(self, data: dict[str, Any], now: float | None = None) -> bool:
        """A `TOOL_ERROR` as a toast (False when the same failure was just shown and nothing can be retried)."""
        now = time.monotonic() if now is None else now
        harness, kind = str(data.get("harness") or ""), str(data.get("kind") or "")
        if kind in (tool_errors.MISSING, tool_errors.LOGIN):
            self.broken[harness] = kind
        key = (harness, kind)
        if not data.get("retry") and now - self._shown.get(key, -AGAIN_S) < AGAIN_S:
            return False
        self._shown[key] = now
        tool = {k: data.get(k) for k in ("harness", "tool", "kind", "where", "line", "action", "detail",
                                         "switch", "hint", "retry")}
        message = data.get("line") or ""
        if data.get("where"):
            message = f"{data['where']}: {message}"
        self.host.on_toast({"message": message, "title": data.get("title") or "", "severity": "error",
                            "timeout": TOAST_S, "message_plain": message, "title_plain": data.get("title") or "",
                            "tool": tool})
        return True

    # -- what the person does --------------------------------------------------------------------

    def switch(self, args: dict) -> dict[str, Any]:
        """Make `to` the main tool (turned on if it was off), then run `retry` again if it is given."""
        from orkcraft.gui.host import CommandError
        to = str(args.get("to") or "")
        if harnesses.get(to) is None:
            raise CommandError(f"No AI tool {to!r}")
        if not tool_errors.installed(to):
            raise CommandError(f"{harnesses.title(to)} is not installed on this computer")
        town = self.host.town
        m = town.machine
        if to in m.tools and not m.tools[to].enabled:
            m.tools[to] = settings.ToolChoice(enabled=True, billing=m.tools[to].billing)
        m.main_tool = to
        settings.save(m)
        self.broken.pop(to, None)
        town.toast(f"Decisions and steps on main run on {harnesses.title(to)}", title="Main tool")
        self.host.on_change()
        retried = self._again(str(args.get("retry") or ""))
        return {"main": to, "retried": retried}

    def retry(self, args: dict) -> bool:
        from orkcraft.gui.host import CommandError
        if not self._again(str(args.get("retry") or "")):
            raise CommandError("That cannot be tried again any more")
        return True

    def _again(self, rid: str) -> bool:
        again = self.retries.pop(rid, None) if rid else None
        if again is None:
            return False
        again()
        return True


def notice(data: dict[str, Any]) -> str:
    """One line for a phone or a log: who failed, nothing of its output."""
    return f"{data.get('title') or 'An AI tool hit an error'}: {data.get('line') or ''}".rstrip(": ")

