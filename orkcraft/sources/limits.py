"""Every AI tool's quota through the bundled `orkcraft.quota` (spends no quota): claude, agy and codex
always; Hermes and Cursor when they are on PATH; pi keeps no windows (its spend shows in 🪙)."""
from __future__ import annotations

import datetime as dt
from shutil import which
from dataclasses import dataclass
from pathlib import Path

from orkcraft.env import getenv
from orkcraft.realm import harnesses

PROVIDERS = harnesses.ids()     # the rows of ⏳ Limits, in this order


@dataclass(frozen=True)
class Limit:
    provider: str  # one of PROVIDERS
    group: str
    window: str
    remaining: float | None  # 0..1
    reset: dt.datetime | None
    error: str | None = None
    note: str = ""           # plan, credits, `as of …` when the reading is not fresh


def _codex(timeout: int) -> list:
    """Codex's windows: a plain row when it is not installed, not logged in or on an API key."""
    from orkcraft import tools
    from orkcraft.quota import codex_quota
    from orkcraft.sources.sessions import codex_bin
    path = which(codex_bin())
    if not path:
        return codex_quota.plain_row(codex_quota.NOT_INSTALLED)
    logged_in, billing = tools.codex_login(path)
    if logged_in is False:
        return codex_quota.plain_row(codex_quota.NOT_LOGGED_IN)
    return codex_quota.get_codex_quota(path, timeout=timeout, billing=billing)


def _on_path(harness: str) -> str | None:
    h = harnesses.get(harness)
    return which(h.bin) if h else None


def _hermes(timeout: int) -> list:
    from orkcraft.quota import hermes_quota
    path = _on_path("hermes")
    return hermes_quota.get_hermes_quota(path, timeout=timeout) if path else []


def _cursor(timeout: int) -> list:
    from orkcraft.quota import cursor_quota
    return cursor_quota.get_cursor_quota(timeout=timeout) if _on_path("cursor") else []


def _pi(timeout: int) -> list:
    from orkcraft.quota.models import QuotaStatus
    return [QuotaStatus("pi", "", "", None, None, None, "no windows: pi pays per token, see 🪙")] if _on_path("pi") else []


def fetch_limits(repo_root: Path, timeout: int = 30) -> list[Limit]:
    """Blocking: runs `claude -p /usage`, `agy -p /usage`, `codex app-server` and `hermes usage`, and
    asks Cursor's API for its plan. Call from a worker thread.

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
        ("codex", _codex, {"timeout": timeout}),
        ("hermes", _hermes, {"timeout": timeout}),
        ("pi", _pi, {"timeout": timeout}),
        ("cursor", _cursor, {"timeout": timeout}),
    ):
        try:
            statuses = fn(**kwargs)
        except Exception as e:
            out.append(Limit(provider, "—", "—", None, None, str(e)))
            continue
        for s in statuses:
            reset = s.reset_time.astimezone().replace(tzinfo=None) if s.reset_time and s.reset_time.tzinfo else s.reset_time
            out.append(Limit(s.provider, s.group, s.window, s.remaining_fraction, reset, s.error, s.note))
    return out
