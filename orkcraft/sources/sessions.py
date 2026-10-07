"""Claude Code, agy and Codex sessions, and which tickets they worked on.

Sources, merged by (harness, session id):
- `<repo>/.orkcraft/sessions.jsonl` — written by `scripts/session_hook.py` from the
  Claude / agy / Codex hooks; the only source that knows tickets reliably, and the only
  one for Codex (its own session store has no project folder to filter by).
- Claude Code transcripts `~/.claude/projects/<repo path with / → ->/*.jsonl`
  (title = first human prompt; tickets = `[[T…]]` / `T1234` in human prompts).
- agy conversations `~/.gemini/antigravity-cli/brain/<conversation-id>/`.
- Cloud Claude Code sessions: `Claude-Session: <url>` commit trailers, ticket
  from the commit subject `<type>(<ID>): …`.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from orkcraft.env import getenv
from orkcraft.realm import harnesses

HARNESS_CLAUDE = "claude"
HARNESS_AGY = "agy"
HARNESS_CODEX = "codex"
HARNESS_CLAUDE_WEB = "claude-web"
_TICKET = re.compile(r"\b(T\d{4,})\b")
_SUBJECT_ID = re.compile(r"^\w+\(([CTP]\d+)\)")
_TRAILER = re.compile(r"^Claude-Session:\s*(\S+)", re.MULTILINE)
TRANSCRIPT_SCAN_BYTES = 4 * 1024 * 1024  # enough for the prompts of a long session
MAX_LOCAL = 60

CACHE_S = 10  # the preview asks on every highlight; git log + stats are not free

_transcript_cache: dict[tuple[str, float, int], tuple[str, set[str]]] = {}
_collect_cache: dict[str, tuple[float, list[Session]]] = {}


@dataclass
class Session:
    harness: str
    id: str
    title: str = ""
    tickets: set[str] = field(default_factory=set)
    started: dt.datetime | None = None
    last: dt.datetime | None = None
    url: str | None = None
    transcript: str | None = None
    orcs: set[str] = field(default_factory=set)   # "<building_id>/<orc_id>" of a deployed garrison orc

    @property
    def key(self) -> str:
        return f"{self.harness}:{self.id}"

    @property
    def resumable(self) -> bool:
        return self.harness in (HARNESS_CLAUDE, HARNESS_AGY, HARNESS_CODEX)

    @property
    def short_id(self) -> str:
        return self.id.rsplit("_", 1)[-1][:8]

    def touch(self, when: dt.datetime | None) -> None:
        if when is None:
            return
        if self.started is None or when < self.started:
            self.started = when
        if self.last is None or when > self.last:
            self.last = when


def log_file(repo_root: Path) -> Path:
    return repo_root / ".orkcraft" / "sessions.jsonl"


def claude_projects_dir(repo_root: Path) -> Path:
    base = Path(getenv("CLAUDE_HOME") or Path.home() / ".claude")
    # Claude Code names the folder after the project path with every non-alphanumeric → "-".
    return base / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(repo_root.resolve()))


def agy_brain_dir() -> Path:
    base = getenv("AGY_HOME") or str(Path.home() / ".gemini" / "antigravity-cli")
    return Path(base) / "brain"


def _parse_ts(value: object) -> dt.datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        t = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return t.astimezone().replace(tzinfo=None) if t.tzinfo else t


# -- sources ---------------------------------------------------------------------------

def _from_log(repo_root: Path, into: dict[str, Session]) -> None:
    try:
        lines = log_file(repo_root).read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for line in lines:
        try:
            e = json.loads(line)
        except ValueError:
            continue
        harness, sid = str(e.get("harness") or ""), str(e.get("session") or "")
        if not harness or not sid:
            continue
        s = into.setdefault(f"{harness}:{sid}", Session(harness, sid))
        s.tickets.update(t for t in e.get("tickets") or [] if isinstance(t, str))
        if isinstance(e.get("orc"), str) and e["orc"]:
            s.orcs.add(e["orc"])
        s.touch(_parse_ts(e.get("ts")))
        if not s.title and e.get("prompt"):
            s.title = str(e["prompt"])
        if e.get("transcript") and not s.transcript:
            s.transcript = str(e["transcript"])


def _scan_transcript(path: Path) -> tuple[str, set[str]]:
    """First human prompt and ticket ids mentioned by the human (cached by mtime/size)."""
    st = path.stat()
    key = (str(path), st.st_mtime, st.st_size)
    if key in _transcript_cache:
        return _transcript_cache[key]
    title, tickets = "", set()
    read = 0
    with path.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            read += len(line)
            if read > TRANSCRIPT_SCAN_BYTES:
                break
            if '"type":"user"' not in line:
                continue
            try:
                msg = json.loads(line).get("message", {})
            except ValueError:
                continue
            content = msg.get("content")
            if isinstance(content, list):  # tool results etc. are not the human's words
                continue
            text = str(content or "")
            if not title:
                title = text.strip().splitlines()[0][:120] if text.strip() else ""
            tickets.update(_TICKET.findall(text))
    _transcript_cache[key] = (title, tickets)
    return title, tickets


def _from_claude_transcripts(repo_root: Path, into: dict[str, Session]) -> None:
    folder = claude_projects_dir(repo_root)
    if not folder.is_dir():
        return
    files = sorted(folder.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)[:MAX_LOCAL]
    for path in files:
        s = into.setdefault(f"{HARNESS_CLAUDE}:{path.stem}", Session(HARNESS_CLAUDE, path.stem))
        try:
            title, tickets = _scan_transcript(path)
        except OSError:
            continue
        s.title = s.title or title
        s.tickets |= tickets
        s.transcript = s.transcript or str(path)
        s.touch(dt.datetime.fromtimestamp(path.stat().st_mtime))


def _from_agy_brain(into: dict[str, Session]) -> None:
    brain = agy_brain_dir()
    if not brain.is_dir():
        return
    dirs = sorted((d for d in brain.iterdir() if d.is_dir()), key=lambda d: d.stat().st_mtime, reverse=True)
    for d in dirs[:MAX_LOCAL]:
        s = into.setdefault(f"{HARNESS_AGY}:{d.name}", Session(HARNESS_AGY, d.name))
        s.touch(dt.datetime.fromtimestamp(d.stat().st_mtime))


def _from_git(repo_root: Path, into: dict[str, Session]) -> None:
    try:
        out = subprocess.run(
            ["git", "log", "--grep=Claude-Session:", "--format=%x1e%cI%x1f%s%x1f%B"],
            cwd=repo_root, capture_output=True, text=True, timeout=10,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return
    for record in out.split("\x1e"):
        parts = record.strip().split("\x1f")
        if len(parts) < 3:
            continue
        when, subject, body = parts[0], parts[1], parts[2]
        m = _TRAILER.search(body)
        if not m:
            continue
        url = m.group(1)
        sid = url.rstrip("/").rsplit("/", 1)[-1]
        s = into.setdefault(f"{HARNESS_CLAUDE_WEB}:{sid}", Session(HARNESS_CLAUDE_WEB, sid, url=url))
        ticket = _SUBJECT_ID.match(subject)
        if ticket and ticket.group(1).startswith("T"):
            s.tickets.add(ticket.group(1))
        s.title = s.title or subject
        s.touch(_parse_ts(when))


def collect_sessions(repo_root: Path, max_age: float = CACHE_S) -> list[Session]:
    """Every known session, newest activity first (cached for `max_age` seconds)."""
    key = str(repo_root)
    hit = _collect_cache.get(key)
    if hit and time.monotonic() - hit[0] < max_age:
        return hit[1]
    found: dict[str, Session] = {}
    _from_log(repo_root, found)
    _from_claude_transcripts(repo_root, found)
    _from_agy_brain(found)
    _from_git(repo_root, found)
    result = sorted(found.values(), key=lambda s: s.last or dt.datetime.min, reverse=True)
    _collect_cache[key] = (time.monotonic(), result)
    return result


def sessions_for(sessions: list[Session], node_id: str | None) -> list[Session]:
    if not node_id:
        return sessions
    return [s for s in sessions if node_id in s.tickets]


def sessions_for_orc(sessions: list[Session], orc_ref: str) -> list[Session]:
    """The runs of a garrison orc (`<building_id>/<orc_id>`), newest first."""
    return [s for s in sessions if orc_ref in s.orcs]


def resume_command(session: Session) -> list[str] | None:
    """Command that reopens a session interactively (None for cloud-only sessions)."""
    h = harnesses.get(session.harness)
    return h.interactive(resume=session.id) if h else None


def new_command(harness: str) -> list[str]:
    h = harnesses.get(harness) or harnesses.need(HARNESS_CLAUDE)
    return h.interactive() or [h.bin]


def deploy_harness(step: dict) -> str:
    """The tool a garrison ork's session runs on: its step's (`main`: the machine's main tool), else —
    when that tool cannot start on a first prompt (agy) — the main tool, else Claude Code."""
    from orkcraft.realm import tiers
    tool = tiers.tool_of(step)
    if (h := harnesses.get(tool)) is not None and h.deploys:
        return tool
    main = tiers.tool_of({})
    return main if (h := harnesses.get(main)) is not None and h.deploys else HARNESS_CLAUDE


def deploy_command(harness: str, prompt: str) -> list[str] | None:
    """An interactive session that starts on `prompt` (a garrison orc's orders), or None.

    A tool that takes the first prompt as an argument (`deploys`) gets it as one argv item (no shell)
    that never starts with "-", so it cannot be read as a flag. agy's interactive mode has no
    documented way to do that yet, so there is no agy deployment (None).
    """
    h = harnesses.get(harness)
    return h.interactive(prompt) if h else None


def claude_bin() -> str:
    return getenv("CLAUDE_BIN") or "claude"


def agy_bin() -> str:
    return getenv("AGY_BIN") or "agy"


def codex_bin() -> str:
    return getenv("CODEX_BIN") or "codex"
