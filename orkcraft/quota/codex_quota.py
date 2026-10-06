"""
codex_quota.py — the Codex plan's windows, read without a model turn (docs/design/codex-limits.md).

Primary: ``codex app-server`` over stdio JSON-RPC (``initialize``, ``initialized``, then
``account/rateLimits/read``), Codex 0.53.0 and later; it asks the ChatGPT backend for the plan's
usage and refuses an API-key login. Fallback: the newest ``token_count`` line with ``rate_limits``
in ``$CODEX_HOME/sessions/YYYY/MM/DD/rollout-*.jsonl`` (``.jsonl.zst`` when ``zstandard`` is
there), only as fresh as the last Codex turn.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional

from orkcraft.quota.models import QuotaStatus

PROVIDER = "codex"
API_KEY = "API key — no plan windows"
NOT_INSTALLED = "not installed"
NOT_LOGGED_IN = "not logged in"
CLIENT_INFO = {"name": "orkcraft", "title": "Orkcraft", "version": "0"}
ROLLOUTS_SCANNED = 20           # newest rollout files looked at for a snapshot


def plain_row(error: str) -> list[QuotaStatus]:
    return [QuotaStatus(provider=PROVIDER, group="", window="", remaining_fraction=None,
                        reset_time=None, error=error)]


def _window_name(minutes) -> str:
    if not isinstance(minutes, (int, float)) or minutes <= 0:
        return ""
    minutes = int(minutes)
    if minutes == 300:
        return "5h"
    if minutes == 10080:
        return "weekly"
    if minutes == 1440:
        return "daily"
    if minutes % 60 == 0 and minutes < 1440:
        return f"{minutes // 60}h"
    return f"{minutes}m"


def _when(value) -> Optional[datetime]:
    """A time as unix seconds or an RFC 3339 string."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value, timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str) and value:
        try:
            when = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return when if when.tzinfo else when.replace(tzinfo=timezone.utc)
    return None


def _status(bucket: str, note: str, used, minutes, reset: Optional[datetime], now: datetime) -> Optional[QuotaStatus]:
    """One window. The plain `codex` bucket's rows are `5h` / `weekly`; another bucket names itself
    with its window (`gpt-6-astra 5h`), so each row keeps its own name on the Tally Crag."""
    if isinstance(used, bool) or not isinstance(used, (int, float)):
        return None
    left = max(0.0, min(1.0, 1 - float(used) / 100.0))
    if reset is not None and reset <= now:   # the window has turned over since this was read
        left, reset = 1.0, None
    window = _window_name(minutes)
    group, window = (" ".join(p for p in (bucket, window) if p), "") if bucket else ("", window)
    return QuotaStatus(provider=PROVIDER, group=group, window=window, remaining_fraction=left,
                       reset_time=reset, error=None, note=note)


def _bucket(limit_id, limit_name) -> str:
    return str(limit_name or (limit_id if limit_id and limit_id != "codex" else ""))


def _note(plan, credits) -> str:
    parts = [str(plan)] if plan and plan != "unknown" else []
    if isinstance(credits, dict) and not credits.get("unlimited") and credits.get("balance") not in (None, ""):
        parts.append(f"credits {credits['balance']}")
    return " · ".join(parts)


# --- app-server -------------------------------------------------------------------------------

def parse_app_server(stdout: str, request_id: int = 2, now: Optional[datetime] = None) -> list[QuotaStatus]:
    """The rows of the ``account/rateLimits/read`` answer among app-server's JSONL output.

    Notifications (``account/updated``, ``account/rateLimits/updated``) may come first; the answer is
    matched by its id. Raises ValueError when there is no usable answer (so the caller falls back).
    """
    now = now or datetime.now(timezone.utc)
    answer = None
    for line in stdout.splitlines():
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        if isinstance(msg, dict) and msg.get("id") == request_id and ("result" in msg or "error" in msg):
            answer = msg
    if answer is None:
        raise ValueError("no answer from codex app-server")
    if "error" in answer:
        err = answer["error"]
        text = str(err.get("message") if isinstance(err, dict) else err)
        if "chatgpt authentication required" in text.lower():
            return plain_row(API_KEY)
        raise ValueError(text)
    result = answer.get("result")
    if not isinstance(result, dict):
        raise ValueError("app-server answered without a result")
    by_id = result.get("rateLimitsByLimitId")
    snapshots = list(by_id.values()) if isinstance(by_id, dict) and by_id else [result.get("rateLimits")]
    statuses: list[QuotaStatus] = []
    for snap in snapshots:
        if not isinstance(snap, dict):
            continue
        bucket, note = _bucket(snap.get("limitId"), snap.get("limitName")), _note(snap.get("planType"), snap.get("credits"))
        for key in ("primary", "secondary"):
            win = snap.get(key)
            if isinstance(win, dict) and (s := _status(bucket, note, win.get("usedPercent"), win.get("windowDurationMins"),
                                                       _when(win.get("resetsAt")), now)):
                statuses.append(s)
    if not statuses:
        return plain_row("no plan windows reported")
    return statuses


def _converse(cmd: list[str], messages: list[dict], timeout: int, cwd: str) -> str:
    """Write each message as a JSON line; after a request wait for its answer before the next one.
    Returns what app-server printed; kills it at the end or when `timeout` runs out."""
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            text=True, cwd=cwd, bufsize=1)
    lines: list[str] = []
    answered: dict[int, threading.Event] = {m["id"]: threading.Event() for m in messages if "id" in m}
    ended = threading.Event()

    def read() -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            lines.append(line)
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            if isinstance(msg, dict) and msg.get("id") in answered and "method" not in msg:
                answered[msg["id"]].set()
        ended.set()

    threading.Thread(target=read, daemon=True, name="codex-app-server").start()
    deadline = datetime.now() + timedelta(seconds=timeout)
    try:
        assert proc.stdin is not None
        for msg in messages:
            proc.stdin.write(json.dumps(msg) + "\n")
            proc.stdin.flush()
            if "id" in msg:
                while not answered[msg["id"]].is_set():
                    left = (deadline - datetime.now()).total_seconds()
                    if left <= 0:
                        raise subprocess.TimeoutExpired(cmd, timeout)
                    if ended.is_set():
                        raise RuntimeError(f"codex app-server exited (code {proc.poll()})")
                    answered[msg["id"]].wait(min(left, 0.1))
    finally:
        proc.kill()
        proc.wait()
    return "".join(lines)


def _messages() -> list[dict]:
    # The JSON-RPC 2.0 header is left out, as app-server does.
    return [
        {"id": 1, "method": "initialize", "params": {"clientInfo": CLIENT_INFO}},
        {"method": "initialized"},
        {"id": 2, "method": "account/rateLimits/read", "params": {"excludeResetCreditDetails": True}},
    ]


# --- rollout fallback --------------------------------------------------------------------------

def _rollout_lines(path: Path) -> list[str]:
    if path.suffix == ".zst":
        try:
            import zstandard  # type: ignore[import-not-found]
        except ImportError:
            return []
        with path.open("rb") as fh:
            data = zstandard.ZstdDecompressor().stream_reader(fh).read()
        return data.decode("utf-8", errors="replace").splitlines()
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def parse_rate_limits(rl: dict, line_time: Optional[datetime], now: datetime) -> list[QuotaStatus]:
    """One rollout ``rate_limits`` snapshot, whatever the Codex version wrote:

    - ~0.40 flat: ``primary_used_percent``, ``primary_window_minutes``, ``primary_resets_in_seconds``
    - objects: ``primary`` / ``secondary`` with ``used_percent``, ``window_minutes`` and
      ``resets_in_seconds`` (from the line's time), ``resets_at`` as RFC 3339, or as unix seconds
      next to ``limit_id``, ``plan_type``, ``credits``.
    """
    bucket, note = _bucket(rl.get("limit_id"), rl.get("limit_name")), _note(rl.get("plan_type"), rl.get("credits"))
    out: list[QuotaStatus] = []
    for key in ("primary", "secondary"):
        win = rl.get(key)
        if isinstance(win, dict):
            used, minutes = win.get("used_percent"), win.get("window_minutes")
            reset = _when(win.get("resets_at"))
            secs = win.get("resets_in_seconds")
        else:
            used, minutes = rl.get(f"{key}_used_percent"), rl.get(f"{key}_window_minutes")
            reset = _when(rl.get(f"{key}_resets_at"))
            secs = rl.get(f"{key}_resets_in_seconds")
        if reset is None and isinstance(secs, (int, float)) and not isinstance(secs, bool) and line_time:
            reset = line_time + timedelta(seconds=secs)
        if s := _status(bucket, note, used, minutes, reset, now):
            out.append(s)
    return out


def _latest_in(lines: list[str], fallback_time: Optional[datetime], now: datetime) -> list[QuotaStatus]:
    for line in reversed(lines):
        if '"rate_limits"' not in line:
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if not isinstance(obj, dict):
            continue
        payload = obj.get("payload") if isinstance(obj.get("payload"), dict) else obj
        if payload.get("type") != "token_count" or not isinstance(payload.get("rate_limits"), dict):
            continue
        statuses = parse_rate_limits(payload["rate_limits"], _when(obj.get("timestamp")) or fallback_time, now)
        if statuses:
            return statuses
    return []


def from_rollouts(codex_home: Path, now: Optional[datetime] = None) -> list[QuotaStatus]:
    """The newest snapshot in the session rollouts, each row marked `as of` its file's time."""
    now = now or datetime.now(timezone.utc)
    files = sorted((codex_home / "sessions").glob("*/*/*/rollout-*.jsonl*"), key=lambda p: p.name, reverse=True)
    for path in files[:ROLLOUTS_SCANNED]:
        if not (path.name.endswith(".jsonl") or path.name.endswith(".jsonl.zst")):
            continue
        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
            statuses = _latest_in(_rollout_lines(path), mtime, now)
        except (OSError, ValueError, EOFError):
            continue
        if statuses:
            stamp = f"as of {mtime.astimezone():%a %H:%M}"
            for s in statuses:
                s.note = f"{s.note} · {stamp}" if s.note else stamp
            return statuses
    return []


# --- entry point -------------------------------------------------------------------------------

def codex_home(env: Optional[dict] = None) -> Path:
    env = os.environ if env is None else env
    return Path(env["CODEX_HOME"]) if env.get("CODEX_HOME") else Path.home() / ".codex"


def get_codex_quota(
    codex_bin: str = "codex",
    timeout: int = 30,
    runner: Optional[Callable] = None,
    home: Optional[Path] = None,
    billing: Optional[str] = None,
    now: Optional[datetime] = None,
) -> list[QuotaStatus]:
    """
    The Codex plan's windows as QuotaStatus records; never spends quota.

    ``billing="api"`` (an API-key login, told by ``tools``) answers one plain row without running
    anything. ``runner(cmd, messages, timeout=, cwd=)`` stands in for app-server in tests and
    returns what it would print.
    """
    if billing == "api":
        return plain_row(API_KEY)
    home = home or codex_home()
    cmd = [codex_bin, "app-server"]
    failure = ""
    try:
        if runner is not None:
            raw = runner(cmd, _messages(), timeout=timeout, cwd=tempfile.gettempdir())
        else:
            raw = _converse(cmd, _messages(), timeout, tempfile.gettempdir())
        return parse_app_server(raw, now=now)
    except FileNotFoundError:
        return plain_row(NOT_INSTALLED)
    except subprocess.TimeoutExpired:
        failure = f"app-server timed out after {timeout}s"
    except Exception as e:      # an older Codex, a backend error: the rollouts may still tell
        failure = str(e) or type(e).__name__
    statuses = from_rollouts(home, now=now)
    return statuses or plain_row(f"no windows read ({failure})")
