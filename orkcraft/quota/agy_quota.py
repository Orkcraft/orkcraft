"""
agy_quota.py — fetch and parse official quota data from the Google Antigravity (agy) CLI.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from typing import Callable, Optional

from orkcraft.quota.models import QuotaStatus


def _parse_iso_datetime(dt_str: Optional[str]) -> Optional[datetime]:
    if not dt_str:
        return None
    try:
        ts = dt_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _run_command(cmd: list[str], timeout: int, runner: Optional[Callable] = None) -> str:
    if runner is not None:
        try:
            return runner(cmd, timeout=timeout)
        except TypeError:
            return runner(cmd)
    res = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=True,
    )
    return res.stdout


def get_agy_quota(
    agy_bin: str = "agy",
    timeout: int = 30,
    runner: Optional[Callable] = None,
) -> list[QuotaStatus]:
    """
    Query the agy CLI for quota usage and return a list of QuotaStatus records.

    Calls ``agy -p "/usage" --output-format json``.
    """
    cmd = [agy_bin, "-p", "/usage", "--output-format", "json"]
    try:
        raw_output = _run_command(cmd, timeout=timeout, runner=runner)
    except FileNotFoundError:
        return [
            QuotaStatus(
                provider="agy",
                group="",
                window="",
                remaining_fraction=None,
                reset_time=None,
                error=f"CLI not found: {agy_bin}",
            )
        ]
    except subprocess.TimeoutExpired:
        return [
            QuotaStatus(
                provider="agy",
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
                provider="agy",
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
                provider="agy",
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
                provider="agy",
                group="",
                window="",
                remaining_fraction=None,
                reset_time=None,
                error=f"Failed to parse JSON: {e}",
            )
        ]

    try:
        command_data = data["command"]["data"]
        groups = command_data["groups"]
        if not isinstance(groups, list):
            raise ValueError("Expected 'groups' to be a list")

        statuses: list[QuotaStatus] = []
        for g in groups:
            group_name = str(g.get("name", ""))
            buckets = g.get("buckets", [])
            for b in buckets:
                rem_frac = b.get("remaining_fraction")
                if rem_frac is not None:
                    rem_frac = float(rem_frac)
                reset_dt = _parse_iso_datetime(b.get("reset_time"))
                window_name = str(b.get("window", ""))
                statuses.append(
                    QuotaStatus(
                        provider="agy",
                        group=group_name,
                        window=window_name,
                        remaining_fraction=rem_frac,
                        reset_time=reset_dt,
                        error=None,
                    )
                )
        if not statuses:
            return [
                QuotaStatus(
                    provider="agy",
                    group="",
                    window="",
                    remaining_fraction=None,
                    reset_time=None,
                    error="No quota buckets found in agy output",
                )
            ]
        return statuses
    except Exception as e:
        return [
            QuotaStatus(
                provider="agy",
                group="",
                window="",
                remaining_fraction=None,
                reset_time=None,
                error=f"Unexpected output structure: {e}",
            )
        ]
