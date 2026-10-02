"""claude / agy quota through the bundled `orkcraft.quota` (answers locally, spends no quota)."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path

from orkcraft.env import getenv


@dataclass(frozen=True)
class Limit:
    provider: str  # claude | agy
    group: str
    window: str
    remaining: float | None  # 0..1
    reset: dt.datetime | None
    error: str | None = None


def fetch_limits(repo_root: Path, timeout: int = 30) -> list[Limit]:
    """Blocking: runs `claude -p /usage` and `agy -p /usage`. Call from a worker thread.

    `ORKCRAFT_LIMITS=0` turns it off (tests, machines without the CLIs).
    """
    if getenv("LIMITS").lower() in ("0", "false", "no", "off"):
        return [Limit("limits", "—", "—", None, None, "disabled (ORKCRAFT_LIMITS=0)")]
    from orkcraft.quota.agy_quota import get_agy_quota
    from orkcraft.quota.claude_quota import get_claude_quota
    out: list[Limit] = []
    for provider, fn, kwargs in (
        ("claude", get_claude_quota, {"timeout": timeout}),
        ("agy", get_agy_quota, {"timeout": timeout}),
    ):
        try:
            statuses = fn(**kwargs)
        except Exception as e:
            out.append(Limit(provider, "—", "—", None, None, str(e)))
            continue
        for s in statuses:
            reset = s.reset_time.astimezone().replace(tzinfo=None) if s.reset_time and s.reset_time.tzinfo else s.reset_time
            out.append(Limit(s.provider, s.group, s.window, s.remaining_fraction, reset, s.error))
    return out
