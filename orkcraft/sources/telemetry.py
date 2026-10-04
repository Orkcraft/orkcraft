"""🪙 Gold and 🪵 Lumber for one orkcraft run, read from the Claude Code transcripts it started.

Every War Tent terminal gets `ORKCRAFT_RUN` (this run's id) and `ORKCRAFT_TERMINAL` (its key);
`scripts/session_hook.py` writes them next to the session's transcript path in
`.orkcraft/sessions.jsonl`. The meter reads those transcripts incrementally (only new bytes on
each refresh) and prices every assistant message with `pricing.usage_cost`, counting only
messages timestamped after the run started — a resumed session's old history is not this run's.

Costs are API-equivalent estimates (see `pricing`); agy sessions have no published prices and
are counted as unpriced, never as $0.

Model calls that leave no transcript of this run — the Council's Fast Path, the Elders, the Builder,
the Recruiter, the daily proposal and the weekly self-audit (`claude -p` in an empty folder), the
Barracks orcs and the Orc Council's members — are charged here as they answer (`charge`); the
snapshot adds them to the same 🪙, so every limit and gate sees the whole spend. A call that carries
`ORKCRAFT_RUN` (a road's agent) is not charged: its transcript already counts.

    telemetry.charge(0.004, "claude -p haiku")    # from any thread
"""
from __future__ import annotations

import datetime as dt
import json
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from orkcraft.sources import pricing
from orkcraft.sources.sessions import log_file

MAX_LINE = 4 * 1024 * 1024  # a single transcript line beyond this is skipped, not parsed


def new_run_id() -> str:
    return uuid.uuid4().hex


# -- the side ledger: model calls with no transcript of this run -----------------------------------

_LEDGER: list[tuple[dt.datetime, float | None, str]] = []      # (when, usd or None: unpriced, source)
_LEDGER_LOCK = threading.Lock()
LEDGER_KEEP = 10_000


def charge(usd: float | None, source: str) -> None:
    """One model call's cost; None when it could not be priced (agy, or no cost in the answer)."""
    if usd is not None and (not isinstance(usd, (int, float)) or usd < 0):
        return
    with _LEDGER_LOCK:
        _LEDGER.append((dt.datetime.now().astimezone(), None if usd is None else float(usd), source))
        del _LEDGER[:-LEDGER_KEEP]


def charged(env: dict | None) -> bool:
    """Whether a call run with `env` leaves a transcript this run already counts (it carries `ORKCRAFT_RUN`)."""
    return bool((env or {}).get("ORKCRAFT_RUN"))


def charges(since: dt.datetime) -> list[tuple[dt.datetime, float | None, str]]:
    with _LEDGER_LOCK:
        return [c for c in _LEDGER if c[0] >= since]


def reset_charges() -> None:
    with _LEDGER_LOCK:
        _LEDGER.clear()


def _ts(value: object) -> dt.datetime | None:
    if not isinstance(value, str):
        return None
    try:
        t = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.astimezone()


@dataclass
class _Meter:
    """Running totals of one transcript file."""
    offset: int = 0
    seen: set[str] = field(default_factory=set)
    cost: float = 0.0
    unpriced: set[str] = field(default_factory=set)
    context: int = 0
    model: str = ""

    def feed(self, path: Path, since: dt.datetime) -> None:
        try:
            size = path.stat().st_size
        except OSError:
            return
        if size < self.offset:            # truncated / rewritten: start over
            self.__init__()
        if size == self.offset:
            return
        with path.open("rb") as f:
            f.seek(self.offset)
            data = f.read(size - self.offset)
        end = data.rfind(b"\n")
        if end < 0:
            return                        # no complete line yet
        self.offset += end + 1
        for raw in data[: end + 1].splitlines():
            if len(raw) > MAX_LINE or b'"assistant"' not in raw:
                continue
            try:
                e = json.loads(raw)
            except ValueError:
                continue
            if not isinstance(e, dict) or e.get("type") != "assistant":
                continue
            msg = e.get("message") if isinstance(e.get("message"), dict) else {}
            usage = msg.get("usage") if isinstance(msg.get("usage"), dict) else None
            mid = str(msg.get("id") or "")
            if usage is None or (mid and mid in self.seen):
                continue
            if mid:
                self.seen.add(mid)
            when = _ts(e.get("timestamp"))
            self.context = pricing.context_of(usage)
            model = str(msg.get("model") or "")
            if model:
                self.model = model
            if when is not None and when < since:
                continue                  # before this run: context yes, spend no
            if not model or model.startswith("<"):
                continue
            cost = pricing.usage_cost(model, usage)
            if cost is None:
                self.unpriced.add(model)
            else:
                self.cost += cost


@dataclass
class Snapshot:
    spent_usd: float = 0.0
    sessions: int = 0                                  # sessions of this run with a transcript
    unpriced: set[str] = field(default_factory=set)    # models or harnesses with no price
    context_by_terminal: dict[str, int] = field(default_factory=dict)
    model_by_terminal: dict[str, str] = field(default_factory=dict)
    cost_by_terminal: dict[str, float] = field(default_factory=dict)   # this run's spend per session
    side_usd: float = 0.0                              # model calls with no transcript (already in spent_usd)
    side_by_source: dict[str, float] = field(default_factory=dict)


class Telemetry:
    def __init__(self, repo_root: Path, run_id: str, started: dt.datetime | None = None) -> None:
        self.repo_root = repo_root
        self.run_id = run_id
        self.started = started or dt.datetime.now().astimezone()
        self._meters: dict[str, _Meter] = {}

    def _this_run(self) -> tuple[dict[str, str], set[str]]:
        """terminal key → transcript path for this run's Claude sessions; unpriced harnesses."""
        transcripts: dict[str, str] = {}
        unpriced: set[str] = set()
        try:
            lines = log_file(self.repo_root).read_text(encoding="utf-8").splitlines()
        except OSError:
            return transcripts, unpriced
        for line in lines:
            if self.run_id not in line:
                continue
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get("run") != self.run_id:
                continue
            terminal = str(e.get("terminal") or e.get("session") or "")
            if e.get("harness") != "claude":
                unpriced.add(str(e.get("harness") or "unknown"))
                continue
            if e.get("transcript"):
                transcripts[terminal] = str(e["transcript"])
        return transcripts, unpriced

    def refresh(self) -> Snapshot:
        snap = Snapshot()
        transcripts, snap.unpriced = self._this_run()
        for terminal, path in transcripts.items():
            meter = self._meters.setdefault(path, _Meter())
            meter.feed(Path(path), self.started)
            snap.spent_usd += meter.cost
            snap.unpriced |= meter.unpriced
            snap.context_by_terminal[terminal] = meter.context
            snap.model_by_terminal[terminal] = meter.model
            snap.cost_by_terminal[terminal] = meter.cost
        snap.sessions = len(transcripts)
        for _, usd, source in charges(self.started):
            if usd is None:
                snap.unpriced.add(source)
                continue
            snap.side_usd += usd
            snap.side_by_source[source] = snap.side_by_source.get(source, 0.0) + usd
        snap.spent_usd += snap.side_usd
        return snap


def level(value: float, limit: float) -> str:
    """ok below 80 % of the limit, warn from 80 %, over from 100 %."""
    if limit <= 0:
        return "ok"
    ratio = value / limit
    return "over" if ratio >= 1 else "warn" if ratio >= 0.8 else "ok"


def fmt_tokens(n: int) -> str:
    """One unit for 🪵 context and its limit (the budget's 131072 reads "128k"): k = 1024 tokens."""
    return f"{n / 1024 / 1024:.1f}M" if n >= 1024 * 1024 else f"{n // 1024}k" if n >= 1024 else str(n)
