"""🪙 Gold and 🪵 Lumber for one orkcraft run, read from the transcripts of the sessions it started.

Every War Tent terminal gets `ORKCRAFT_RUN` (this run's id) and `ORKCRAFT_TERMINAL` (its key);
`scripts/session_hook.py` writes them next to the session's transcript path in
`.orkcraft/sessions.jsonl`. The meter reads those transcripts incrementally (only new bytes on
each refresh) and prices every assistant message with `pricing.usage_cost`, counting only
messages timestamped after the run started — a resumed session's old history is not this run's.

Costs are API-equivalent estimates (see `pricing`). pi prices each message itself (its session
JSONL, `usage.cost.total`) and Hermes each session (`estimated_cost_usd` in its `state.db`): their
own figures count. Codex prints tokens and no price: its rollout (the SessionStart hook's
`transcript_path`) is priced from its model with `pricing.codex_usage_cost`, unpriced while OpenAI's
table has no price for it. agy and Cursor print no price: unpriced, never $0.

Model calls that leave no transcript of this run — the Council's Fast Path, the Elders, the Builder,
the Recruiter, the daily proposal and the weekly self-audit (`claude -p` in an empty folder), the
Barracks orcs and the Clan Fire's members — are charged here as they answer (`charge`); the
snapshot adds them to the same 🪙, so every limit and gate sees the whole spend. A call that carries
`ORKCRAFT_RUN` (a road's agent) is not charged: its transcript already counts.

    telemetry.charge(0.004, "claude -p haiku", purpose="build")    # from any thread

Each call is also a line of `.orkcraft/spend/calls.jsonl` (`keep_ledger`): when, building, purpose, model,
tokens, $ — the numbers the Spend window's *By purpose* reads (docs/design/simplify.md §2).
"""
from __future__ import annotations

import contextlib
import contextvars
import datetime as dt
import json
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple

from orkcraft.sources import pricing
from orkcraft.sources.sessions import log_file

MAX_LINE = 4 * 1024 * 1024  # a single transcript line beyond this is skipped, not parsed


def new_run_id() -> str:
    return uuid.uuid4().hex


# -- the side ledger: model calls with no transcript of this run -----------------------------------
#
# Every model call says what it was for (docs/design/simplify.md §2): one `purpose` of a closed list, next
# to its building. A call with no purpose of its own takes the one its caller set (`tagged`), else `work`.

PURPOSES = ("work", "sort", "plan", "review", "check", "ingest", "answer", "look", "retro", "build", "chat")
CALLS = Path(".orkcraft") / "spend" / "calls.jsonl"       # one line per call, under the repository


class Charge(NamedTuple):
    when: dt.datetime
    usd: float | None          # None: unpriced
    source: str
    purpose: str = "work"
    building: str = ""
    model: str = ""
    tokens: int | None = None


_LEDGER: list[Charge] = []
_LEDGER_LOCK = threading.Lock()
LEDGER_KEEP = 10_000
_TAG: contextvars.ContextVar[tuple[str, str]] = contextvars.ContextVar("orkcraft_charge_tag", default=("", ""))
_KEPT: dict[str, Path | None] = {"root": None}


def keep_ledger(repo_root: Path | None) -> None:
    """Write every call to `repo_root/.orkcraft/spend/calls.jsonl` from now on (None: memory only)."""
    _KEPT["root"] = repo_root


@contextlib.contextmanager
def tagged(purpose: str = "", building: str = ""):
    """The model calls in this block (on this thread) are for `purpose`, of `building`; what is not given
    is kept from an outer block."""
    outer = _TAG.get()
    token = _TAG.set((purpose if purpose in PURPOSES else outer[0], building or outer[1]))
    try:
        yield
    finally:
        _TAG.reset(token)


def purpose_now() -> str:
    """The purpose set by the caller (`tagged`), else `work`."""
    return _TAG.get()[0] or "work"


def building_of(env: dict | None) -> str:
    """The building of a call started with `ORKCRAFT_ORC` (`<building>/<ork>`), else ""."""
    orc = str((env or {}).get("ORKCRAFT_ORC") or "")
    return orc.split("/", 1)[0] if "/" in orc else ""


def _entry(usd: float | None, source: str, purpose: str, building: str, model: str,
           tokens: int | None) -> Charge:
    tag_purpose, tag_building = _TAG.get()
    purpose = purpose if purpose in PURPOSES else tag_purpose or "work"
    tokens = int(tokens) if isinstance(tokens, (int, float)) and not isinstance(tokens, bool) and tokens >= 0 else None
    return Charge(dt.datetime.now().astimezone(), None if usd is None else float(usd), source, purpose,
                  building or tag_building, model, tokens)


def _write(c: Charge, counted: bool = False) -> None:
    root = _KEPT["root"]
    if root is None:
        return
    line = {"at": c.when.isoformat(timespec="seconds"), "building": c.building, "purpose": c.purpose,
            "model": c.model, "tokens": c.tokens, "usd": c.usd, "source": c.source}
    if counted:
        line["transcript"] = True                 # its transcript counts it in 🪙; the line is for the purposes
    path = root / CALLS
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
    except OSError:
        pass                                      # the ledger must never stop a call


def charge(usd: float | None, source: str, purpose: str = "", tokens: int | None = None,
           building: str = "", model: str = "") -> None:
    """One model call's cost; None when it could not be priced (agy, or no cost in the answer).
    `purpose`: one of PURPOSES ("" or unknown: the caller's `tagged`, else `work`)."""
    if usd is not None and (not isinstance(usd, (int, float)) or usd < 0):
        return
    c = _entry(usd, source, purpose, building, model, tokens)
    with _LEDGER_LOCK:
        _LEDGER.append(c)
        del _LEDGER[:-LEDGER_KEEP]
        _write(c)


def noted(usd: float | None, source: str, purpose: str = "", tokens: int | None = None,
          building: str = "", model: str = "") -> None:
    """A call its transcript already counts (`charged`): only its line in the ledger, so the spend by
    purpose sees it too; never added to 🪙 twice."""
    if usd is not None and (not isinstance(usd, (int, float)) or usd < 0):
        return
    with _LEDGER_LOCK:
        _write(_entry(usd, source, purpose, building, model, tokens), counted=True)


def charged(env: dict | None) -> bool:
    """Whether a call run with `env` leaves a transcript this run already counts (it carries `ORKCRAFT_RUN`)."""
    return bool((env or {}).get("ORKCRAFT_RUN"))


def purpose_env(purpose: str = "") -> dict[str, str]:
    """The env a transcript run carries so the session hook records what it was for."""
    return {"ORKCRAFT_PURPOSE": purpose if purpose in PURPOSES else purpose_now()}


def charges(since: dt.datetime) -> list[Charge]:
    with _LEDGER_LOCK:
        return [c for c in _LEDGER if c.when >= since]


def reset_charges() -> None:
    with _LEDGER_LOCK:
        _LEDGER.clear()


def calls(repo_root: Path, since: dt.datetime | None = None) -> list[dict]:
    """The ledger's lines on disk (oldest first), from `since` on (a time with no zone is local); malformed lines
    are skipped."""
    if since is not None and since.tzinfo is None:
        since = since.astimezone()
    try:
        lines = (repo_root / CALLS).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for raw in lines:
        try:
            e = json.loads(raw)
        except ValueError:
            continue
        if not isinstance(e, dict) or (when := _ts(e.get("at"))) is None:
            continue
        if since is None or when >= since:
            out.append(e)
    return out


_WEEK: dict[str, object] = {}


def by_purpose(repo_root: Path, days: int = 7, now: dt.datetime | None = None) -> list[dict]:
    """The ledger of the last `days`, by purpose and, inside each, by building — most $ first:
    [{"purpose", "usd", "tokens", "calls", "unpriced", "buildings": [{"building", "usd", "tokens", "calls"}]}].
    `usd` counts the priced calls; `unpriced` how many had no price. Read again only when the file changed."""
    now = now or dt.datetime.now().astimezone()
    path = repo_root / CALLS
    try:
        st = path.stat()
        key = (str(path), st.st_mtime_ns, st.st_size, days, now.strftime("%Y-%m-%d %H"))
    except OSError:
        return []
    if _WEEK.get("key") == key:
        return _WEEK["value"]                     # type: ignore[return-value]
    groups: dict[str, dict] = {}
    for c in calls(repo_root, now - dt.timedelta(days=days)):
        purpose = c.get("purpose") if c.get("purpose") in PURPOSES else "work"
        g = groups.setdefault(purpose, {"purpose": purpose, "usd": 0.0, "tokens": 0, "calls": 0, "unpriced": 0,
                                        "buildings": {}})
        b = g["buildings"].setdefault(str(c.get("building") or ""), {"building": str(c.get("building") or ""),
                                                                     "usd": 0.0, "tokens": 0, "calls": 0})
        usd, tokens = c.get("usd"), c.get("tokens")
        for row in (g, b):
            row["calls"] += 1
            if isinstance(usd, (int, float)) and usd >= 0:
                row["usd"] += float(usd)
            if isinstance(tokens, int) and tokens >= 0:
                row["tokens"] += tokens
        if not isinstance(usd, (int, float)):
            g["unpriced"] += 1
    rank = lambda r: (-r["usd"], -r["calls"])          # noqa: E731
    value = sorted(({**g, "buildings": sorted(g["buildings"].values(), key=rank)} for g in groups.values()), key=rank)
    _WEEK.update(key=key, value=value)
    return value


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
class _PiMeter:
    """A pi session file (`~/.pi/agent/sessions/…/<ts>_<id>.jsonl`): each assistant message's own price."""
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
        if size < self.offset:
            self.__init__()
        if size == self.offset:
            return
        with path.open("rb") as f:
            f.seek(self.offset)
            data = f.read(size - self.offset)
        end = data.rfind(b"\n")
        if end < 0:
            return
        self.offset += end + 1
        for raw in data[: end + 1].splitlines():
            if len(raw) > MAX_LINE or b'"assistant"' not in raw:
                continue
            try:
                e = json.loads(raw)
            except ValueError:
                continue
            msg = e.get("message") if isinstance(e, dict) and isinstance(e.get("message"), dict) else {}
            usage = msg.get("usage") if isinstance(msg.get("usage"), dict) else None
            if e.get("type") != "message" or msg.get("role") != "assistant" or usage is None:
                continue
            mid = str(e.get("id") or "")
            if mid and mid in self.seen:
                continue
            self.seen.add(mid)
            self.context = sum(int(usage.get(k) or 0) for k in ("input", "cacheRead", "cacheWrite"))
            self.model = str(msg.get("model") or self.model)
            when = _ts(e.get("timestamp"))
            if when is not None and when < since:
                continue
            total = (usage.get("cost") or {}).get("total") if isinstance(usage.get("cost"), dict) else None
            if isinstance(total, (int, float)):
                self.cost += float(total)
            else:
                self.unpriced.add(self.model or "pi")


@dataclass
class _HermesMeter:
    """A Hermes session: its running `estimated_cost_usd` in `$HERMES_HOME/state.db`, less what it had
    cost before this run when it started earlier (a resumed session)."""
    session: str = ""
    base: float | None = None
    cost: float = 0.0
    unpriced: set[str] = field(default_factory=set)
    context: int = 0
    model: str = ""

    def feed(self, db: Path, since: dt.datetime) -> None:
        import sqlite3
        try:
            con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=1)
            try:
                row = con.execute("SELECT estimated_cost_usd, started_at, model, input_tokens, cache_read_tokens "
                                  "FROM sessions WHERE id = ?", (self.session,)).fetchone()
            finally:
                con.close()
        except sqlite3.Error:
            return
        if row is None:
            return
        usd, started, model, fresh, cached = row
        self.model, self.context = str(model or ""), int(fresh or 0) + int(cached or 0)
        if not isinstance(usd, (int, float)):
            self.unpriced.add(self.model or "hermes")
            return
        if self.base is None:
            begun = isinstance(started, (int, float)) and started >= since.timestamp()
            self.base = 0.0 if begun else float(usd)
        self.cost = max(float(usd) - self.base, 0.0)


@dataclass
class _CodexMeter:
    """A Codex rollout (`~/.codex/sessions/YYYY/MM/DD/rollout-<ts>-<thread>.jsonl`), read incrementally:
    the model from the latest `turn_context`, each request's `token_count` `last_token_usage` priced
    once (a repeated count, same running total, is not a new request)."""
    offset: int = 0
    total: int = -1
    cost: float = 0.0
    unpriced: set[str] = field(default_factory=set)
    context: int = 0
    model: str = ""

    def feed(self, path: Path, since: dt.datetime) -> None:
        try:
            size = path.stat().st_size
        except OSError:
            return
        if size < self.offset:
            self.__init__()
        if size == self.offset:
            return
        with path.open("rb") as f:
            f.seek(self.offset)
            data = f.read(size - self.offset)
        end = data.rfind(b"\n")
        if end < 0:
            return
        self.offset += end + 1
        for raw in data[: end + 1].splitlines():
            if len(raw) > MAX_LINE or (b'"turn_context"' not in raw and b'"token_count"' not in raw):
                continue
            try:
                e = json.loads(raw)
            except ValueError:
                continue
            payload = e.get("payload") if isinstance(e, dict) else None
            if not isinstance(payload, dict):
                continue
            if e.get("type") == "turn_context":
                self.model = str(payload.get("model") or self.model)
                continue
            info = payload.get("info") if payload.get("type") == "token_count" else None
            if not isinstance(info, dict) or not isinstance(info.get("last_token_usage"), dict):
                continue
            last, total = info["last_token_usage"], info.get("total_token_usage")
            running = int(total.get("total_tokens") or 0) if isinstance(total, dict) else -1
            if running >= 0 and running == self.total:
                continue                  # the same count again
            self.total = running
            self.context = int(last.get("input_tokens") or 0)
            when = _ts(e.get("timestamp"))
            if when is not None and when < since:
                continue
            cost = pricing.codex_usage_cost(self.model, last, one_request=True)
            if cost is None:
                self.unpriced.add(self.model or "codex")
            else:
                self.cost += cost


def hermes_db(env: dict | None = None) -> Path:
    import os
    env = os.environ if env is None else env
    return Path(env.get("HERMES_HOME") or Path.home() / ".hermes") / "state.db"


# harness → the meter of its transcript file
METERED = {"claude": _Meter, "pi": _PiMeter, "codex": _CodexMeter}


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
    side_by_purpose: dict[str, float] = field(default_factory=dict)
    by_purpose: dict[str, float] = field(default_factory=dict)         # all of spent_usd, by what it was for


class Telemetry:
    def __init__(self, repo_root: Path, run_id: str, started: dt.datetime | None = None) -> None:
        self.repo_root = repo_root
        self.run_id = run_id
        self.started = started or dt.datetime.now().astimezone()
        self._meters: dict[str, _Meter | _PiMeter | _HermesMeter | _CodexMeter] = {}
        self._purpose: dict[str, str] = {}               # terminal key → what its session was for (the hook's)

    def _this_run(self) -> tuple[dict[str, tuple[str, str]], set[str]]:
        """terminal key → (harness, transcript path or Hermes session id) for this run's sessions that
        say what they cost (Claude Code, pi, Hermes, Codex); the harnesses that do not."""
        transcripts: dict[str, tuple[str, str]] = {}
        unpriced: set[str] = set()
        bare: set[tuple[str, str]] = set()
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
            harness = str(e.get("harness") or "unknown")
            if e.get("purpose") in PURPOSES:
                self._purpose[terminal] = e["purpose"]
            if harness == "hermes" and e.get("session"):
                transcripts[terminal] = (harness, str(e["session"]))
            elif harness in METERED and e.get("transcript"):
                transcripts[terminal] = (harness, str(e["transcript"]))
            elif harness not in (*METERED, "hermes"):
                unpriced.add(harness)
            else:
                bare.add((terminal, harness))
        unpriced |= {harness for terminal, harness in bare if terminal not in transcripts}   # no transcript: no price
        return transcripts, unpriced

    def refresh(self) -> Snapshot:
        snap = Snapshot()
        transcripts, snap.unpriced = self._this_run()
        for terminal, (harness, path) in transcripts.items():
            if harness == "hermes":
                meter = self._meters.setdefault(f"hermes:{path}", _HermesMeter(session=path))
                meter.feed(hermes_db(), self.started)
            else:
                meter = self._meters.setdefault(path, METERED[harness]())
                meter.feed(Path(path), self.started)
            snap.spent_usd += meter.cost
            snap.unpriced |= meter.unpriced
            snap.context_by_terminal[terminal] = meter.context
            snap.model_by_terminal[terminal] = meter.model
            snap.cost_by_terminal[terminal] = meter.cost
            purpose = self._purpose.get(terminal, "work")
            snap.by_purpose[purpose] = snap.by_purpose.get(purpose, 0.0) + meter.cost
        snap.sessions = len(transcripts)
        for c in charges(self.started):
            if c.usd is None:
                snap.unpriced.add(c.source)
                continue
            snap.side_usd += c.usd
            snap.side_by_source[c.source] = snap.side_by_source.get(c.source, 0.0) + c.usd
            snap.side_by_purpose[c.purpose] = snap.side_by_purpose.get(c.purpose, 0.0) + c.usd
        snap.spent_usd += snap.side_usd
        for purpose, usd in snap.side_by_purpose.items():
            snap.by_purpose[purpose] = snap.by_purpose.get(purpose, 0.0) + usd
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
