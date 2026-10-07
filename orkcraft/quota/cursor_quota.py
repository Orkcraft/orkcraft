"""Cursor's plan: its month's use, as Cursor's own clients read it — `DashboardService/
GetCurrentPeriodUsage` on api2.cursor.sh with the CLI's stored login (`accessToken` in its auth.json;
macOS keeps it in the Keychain, which is not read). Not a documented API: an answer it does not
expect is a plain row, never an error that stops ⏳ Limits. A key in CURSOR_API_KEY may name another
account than the login, so then nothing is read. docs/design/harnesses.md"""
from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from orkcraft.quota.models import QuotaStatus

PROVIDER = "cursor"
ENDPOINT = "https://api2.cursor.sh/aiserver.v1.DashboardService/GetCurrentPeriodUsage"
WINDOWS = (("totalPercentUsed", "month"), ("autoPercentUsed", "month · Auto"), ("apiPercentUsed", "month · API"))


def row(error: str = "", note: str = "") -> list[QuotaStatus]:
    return [QuotaStatus(provider=PROVIDER, group="", window="", remaining_fraction=None, reset_time=None,
                        error=error or None, note=note)]


def token(env: dict | None = None, home: Path | None = None) -> str:
    env = dict(os.environ) if env is None else env
    home = Path.home() if home is None else home
    config = Path(env["XDG_CONFIG_HOME"]) if env.get("XDG_CONFIG_HOME") else home / ".config"
    for auth in (config / "cursor" / "auth.json", home / ".cursor" / "auth.json",
                 Path(env.get("APPDATA") or home / "AppData" / "Roaming") / "Cursor" / "auth.json"):
        try:
            data = json.loads(auth.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and isinstance(data.get("accessToken"), str) and data["accessToken"].strip():
            return data["accessToken"].strip()
    return ""


def parse(data: dict) -> list[QuotaStatus]:
    end = data.get("billingCycleEnd")
    try:
        reset = datetime.fromtimestamp(float(end) / 1000, tz=timezone.utc) if end and float(end) > 0 else None
    except (TypeError, ValueError):
        reset = None
    usage = data.get("planUsage") if isinstance(data.get("planUsage"), dict) else {}
    out = [QuotaStatus(provider=PROVIDER, group="plan", window=label,
                       remaining_fraction=max(0.0, min(1.0, 1 - float(usage[key]) / 100)), reset_time=reset)
           for key, label in WINDOWS if isinstance(usage.get(key), (int, float))]
    return out or row("no plan use in the answer")


def get_cursor_quota(timeout: int = 30, env: dict | None = None, home: Path | None = None,
                     opener=urllib.request.urlopen) -> list[QuotaStatus]:
    env = dict(os.environ) if env is None else env
    if env.get("CURSOR_API_KEY"):
        return row(note="on CURSOR_API_KEY: the plan is read only with a login")
    access = token(env, home)
    if not access:
        return row(note="no stored login to read the plan with (macOS keeps it in the Keychain)")
    req = urllib.request.Request(ENDPOINT, data=b"{}", method="POST", headers={
        "Authorization": f"Bearer {access}", "Content-Type": "application/json",
        "connect-protocol-version": "1", "x-cursor-client-type": "cli"})
    try:
        with opener(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:                    # offline, a changed API: a row that says so
        return row(f"plan not read ({type(e).__name__})")
    return parse(data) if isinstance(data, dict) else row("plan not read")
