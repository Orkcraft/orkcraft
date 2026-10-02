"""
claude_quota.py — fetch and parse official quota data from the Claude Code CLI.
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional
from zoneinfo import ZoneInfo

from orkcraft.quota.models import QuotaStatus

_MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

_CLAUDE_LINE_RE = re.compile(
    r"^Current\s+(?P<label>.+?):\s+(?P<pct>\d+)%\s+used\s+·\s+resets\s+(?P<mon>[A-Za-z]+)\s+(?P<day>\d{1,2})\s+at\s+(?P<hour>\d{1,2})(?::(?P<min>\d{2}))?(?P<ampm>[aApP][mM])\s+\((?P<tz>[^)]+)\)$"
)


def _infer_window(label: str) -> str:
    lower = label.lower()
    if "session" in lower:
        return "session"
    if "week" in lower:
        return "weekly"
    return label


def _parse_claude_reset(
    mon_str: str,
    day_str: str,
    hour_str: str,
    min_str: Optional[str],
    ampm_str: str,
    tz_str: str,
    now: Optional[datetime] = None,
) -> datetime:
    if now is None:
        now = datetime.now(timezone.utc)

    month = _MONTHS.get(mon_str.lower()[:3])
    if month is None:
        raise ValueError(f"Unknown month: {mon_str}")

    day = int(day_str)
    hour = int(hour_str)
    minute = int(min_str) if min_str else 0
    ampm = ampm_str.lower()
    if ampm == "pm" and hour != 12:
        hour += 12
    elif ampm == "am" and hour == 12:
        hour = 0

    tz = ZoneInfo(tz_str.strip())

    # Cutoff: not more than one day in the past
    cutoff = now - timedelta(days=1)

    candidate_years = [now.year - 1, now.year, now.year + 1]
    valid_dts: list[datetime] = []
    for y in candidate_years:
        try:
            dt_local = datetime(y, month, day, hour, minute, tzinfo=tz)
        except ValueError:
            continue
        dt_utc = dt_local.astimezone(timezone.utc)
        if dt_utc >= cutoff:
            valid_dts.append(dt_utc)

    if not valid_dts:
        dt_local = datetime(now.year, month, day, hour, minute, tzinfo=tz)
        return dt_local.astimezone(timezone.utc)

    valid_dts.sort()
    return valid_dts[0]


def _run_command(
    cmd: list[str],
    timeout: int,
    cwd: str,
    runner: Optional[Callable] = None,
) -> str:
    if runner is not None:
        try:
            return runner(cmd, timeout=timeout, cwd=cwd)
        except TypeError:
            try:
                return runner(cmd, timeout=timeout)
            except TypeError:
                return runner(cmd)
    res = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=cwd,
        check=True,
    )
    return res.stdout


def get_claude_quota(
    claude_bin: str = "claude",
    timeout: int = 30,
    runner: Optional[Callable] = None,
    now: Optional[datetime] = None,
) -> list[QuotaStatus]:
    """
    Query the Claude Code CLI for quota usage and return a list of QuotaStatus records.

    Calls ``claude -p "/usage" --output-format json --no-session-persistence``
    with cwd set to a temp directory.
    """
    cmd = [
        claude_bin,
        "-p",
        "/usage",
        "--output-format",
        "json",
        "--no-session-persistence",
    ]
    cwd = tempfile.gettempdir()

    try:
        raw_output = _run_command(cmd, timeout=timeout, cwd=cwd, runner=runner)
    except FileNotFoundError:
        return [
            QuotaStatus(
                provider="claude",
                group="",
                window="",
                remaining_fraction=None,
                reset_time=None,
                error=f"CLI not found: {claude_bin}",
            )
        ]
    except subprocess.TimeoutExpired:
        return [
            QuotaStatus(
                provider="claude",
                group="",
                window="",
                remaining_fraction=None,
                reset_time=None,
                error=f"Command timed out after {timeout}s",
            )
        ]
    except subprocess.CalledProcessError as e:
        err = (e.stderr or e.stdout or f"Process exited with code {e.returncode}").strip()
        return [
            QuotaStatus(
                provider="claude",
                group="",
                window="",
                remaining_fraction=None,
                reset_time=None,
                error=f"Command failed (exit {e.returncode}): {err}",
            )
        ]
    except Exception as e:
        return [
            QuotaStatus(
                provider="claude",
                group="",
                window="",
                remaining_fraction=None,
                reset_time=None,
                error=str(e),
            )
        ]

    try:
        data = json.loads(raw_output)
    except Exception as e:
        return [
            QuotaStatus(
                provider="claude",
                group="",
                window="",
                remaining_fraction=None,
                reset_time=None,
                error=f"Failed to parse JSON: {e}",
            )
        ]

    result_text = data.get("result")
    if not isinstance(result_text, str):
        return [
            QuotaStatus(
                provider="claude",
                group="",
                window="",
                remaining_fraction=None,
                reset_time=None,
                error="Missing or invalid 'result' field in Claude output",
            )
        ]

    statuses: list[QuotaStatus] = []
    for line in result_text.splitlines():
        line = line.strip()
        m = _CLAUDE_LINE_RE.match(line)
        if not m:
            continue
        label = m.group("label").strip()
        pct = int(m.group("pct"))
        rem_frac = max(0.0, min(1.0, (100 - pct) / 100.0))
        try:
            reset_dt = _parse_claude_reset(
                mon_str=m.group("mon"),
                day_str=m.group("day"),
                hour_str=m.group("hour"),
                min_str=m.group("min"),
                ampm_str=m.group("ampm"),
                tz_str=m.group("tz"),
                now=now,
            )
        except Exception as e:
            return [
                QuotaStatus(
                    provider="claude",
                    group="",
                    window="",
                    remaining_fraction=None,
                    reset_time=None,
                    error=f"Failed to parse reset date: {e}",
                )
            ]
        window = _infer_window(label)
        statuses.append(
            QuotaStatus(
                provider="claude",
                group=label,
                window=window,
                remaining_fraction=rem_frac,
                reset_time=reset_dt,
                error=None,
            )
        )

    if not statuses:
        return [
            QuotaStatus(
                provider="claude",
                group="",
                window="",
                remaining_fraction=None,
                reset_time=None,
                error="No quota lines found in Claude output",
            )
        ]

    return statuses
