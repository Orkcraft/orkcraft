"""Hermes Agent's windows: `hermes usage --json` (its provider's own rate limits, read by Hermes;
no model turn). Its answer: `{"provider", "title", "plan", "windows": [{"label", "used_percent",
"resets_at", "detail"}], "unavailable_reason"}`; when it cannot tell it exits 1 with one line."""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from typing import Callable

from orkcraft.quota.models import QuotaStatus

PROVIDER = "hermes"


def row(error: str = "", note: str = "") -> list[QuotaStatus]:
    return [QuotaStatus(provider=PROVIDER, group="", window="", remaining_fraction=None, reset_time=None,
                        error=error or None, note=note)]


def _when(value) -> datetime | None:
    if isinstance(value, (int, float)) and value > 0:
        return datetime.fromtimestamp(value / 1000 if value > 1e11 else value, tz=timezone.utc)
    if isinstance(value, str) and value:
        try:
            when = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return when if when.tzinfo else when.replace(tzinfo=timezone.utc)
    return None


def parse(data: dict) -> list[QuotaStatus]:
    windows = data.get("windows") if isinstance(data.get("windows"), list) else []
    group, note = str(data.get("title") or data.get("provider") or ""), str(data.get("plan") or "")
    out = []
    for w in windows:
        if not isinstance(w, dict):
            continue
        used = w.get("used_percent")
        remaining = max(0.0, min(1.0, 1 - float(used) / 100)) if isinstance(used, (int, float)) else None
        out.append(QuotaStatus(provider=PROVIDER, group=group, window=str(w.get("label") or ""),
                               remaining_fraction=remaining, reset_time=_when(w.get("resets_at")), note=note))
    return out or row(str(data.get("unavailable_reason") or "no windows"))


def get_hermes_quota(hermes_bin: str = "hermes", timeout: int = 30, runner: Callable | None = None) -> list[QuotaStatus]:
    cmd = [hermes_bin, "usage", "--json"]
    try:
        if runner is not None:
            out, code, err = runner(cmd, timeout=timeout), 0, ""
        else:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            out, code, err = proc.stdout, proc.returncode, proc.stderr
    except FileNotFoundError:
        return row("not installed")
    except subprocess.TimeoutExpired:
        return row(f"`hermes usage` timed out after {timeout}s")
    if code != 0:
        return row((err or out).strip().splitlines()[0][:200] if (err or out).strip() else f"exit {code}")
    try:
        data = json.loads(out)
    except ValueError as e:
        return row(f"Failed to parse JSON: {e}")
    return parse(data) if isinstance(data, dict) else row("Failed to parse JSON")
