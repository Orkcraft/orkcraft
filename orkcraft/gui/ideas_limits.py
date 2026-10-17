"""The top bar's limits (docs/specs/33-v1-shell.md §5) and their `limits_read` events (§9), as `gui/ideas.py`'s `Ideas` has them.

What is left of each installed AI tool: `[{"provider","name","left","rows":[{"window","left","reset"}]}]`, `left` the smallest
`remaining` of the tool's rows (decisions §45.3). The Town Hall's last read when it has one, else read in a thread every
LIMITS_S. Split from ideas.py to keep it under ~600 lines.
"""
from __future__ import annotations

import datetime as dt
import threading
import time
from pathlib import Path

from orkcraft.realm import event_log, harnesses

LIMITS_S = 300.0                  # how often the AI tools' limits are read for the top bar
LIMITS_LOG_S = 3600.0             # limits_read at most once an hour (and whenever a task is held)
WINDOWS = {"session": "5h", "weekly": "week"}      # the quota readers' window names → the top bar's


class LimitsMixin:
    def limits(self) -> list[dict]:
        """What is left of each installed AI tool, for the top bar: `[{"provider","name","left","rows":[{"window",
        "left","reset"}]}]`, `left` the smallest `remaining` of the tool's rows (decisions §45.3). The Town Hall's
        last read when it has one, else read here in a thread every LIMITS_S."""
        rows = list(self.host.limits() or [])
        if rows:
            self.log_limits()
        if not rows:
            now = time.monotonic()
            if now - self._limits_at >= LIMITS_S and not self._limits_busy:
                self._limits_busy, self._limits_at = True, now
                threading.Thread(target=self._read_limits, daemon=True, name="ideas-limits").start()
            return self._limits
        return self._limits_of(rows)

    def log_limits(self, force: bool = False) -> None:
        """`limits_read` for each tool: once an hour at most, and whenever a task is held (`force`)."""
        now = time.monotonic()
        if not force and now - self._limits_logged < LIMITS_LOG_S:
            return
        rows = list(self.host.limits() or [])
        found = self._limits_of(rows) if rows else self._limits
        if not found:
            return
        self._limits_logged = now
        for l in found:
            low = min(l["rows"], key=lambda r: r["left"]) if l.get("rows") else {}
            self._ev(event_log.LIMITS_READ, provider=l["provider"], left=l["left"], window=low.get("window", ""))

    def _read_limits(self) -> None:
        try:
            from orkcraft.sources.limits import fetch_limits
            self._limits = self._limits_of(fetch_limits(Path(self.town.repo_root)))
            self.log_limits()
        except Exception:                       # a quota never breaks the top bar
            pass
        finally:
            self._limits_busy = False

    def _limits_of(self, rows: list) -> list[dict]:
        by: dict[str, list] = {}
        for lim in rows:
            if getattr(lim, "remaining", None) is not None and harnesses.get(getattr(lim, "provider", "")):
                by.setdefault(lim.provider, []).append(lim)
        out = []
        for provider, mine in by.items():
            out.append({"provider": provider, "name": harnesses.title(provider).split()[0],
                        "left": round(min(x.remaining for x in mine), 4),
                        "rows": [{"window": WINDOWS.get(x.window, x.window) or x.group or "limit",
                                  "left": round(x.remaining, 4),
                                  "reset": x.reset.isoformat(timespec="minutes") if isinstance(x.reset, dt.datetime)
                                  else ""} for x in mine]})
        return out
