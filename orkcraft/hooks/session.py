#!/usr/bin/env python3
"""Record which Claude Code / agy / Codex session worked on which ticket — hook target.

    python3 -m orkcraft.hooks.session claude   # .claude/settings.json hooks (`orkcraft hooks install`)
    python3 -m orkcraft.hooks.session codex    # .codex/hooks.json hooks (`orkcraft hooks install`)
    python3 -m orkcraft.hooks.session agy      # .agents/hooks.json hooks

Reads the hook payload (JSON) on stdin and appends one line to
`<repo>/.orkcraft/sessions.jsonl` of the project the session works in, found from its `cwd`
(gitignored: sessions live on this machine):

    {"ts", "harness", "event", "session", "tickets", "cwd", "transcript", "prompt", "orc"?, "run"?, "terminal"?}

Session id: Claude and Codex send `session_id`; agy sends `conversationId`. Tickets come
from `$ORKCRAFT_TICKET` (set by orkcraft when it opens a session for a node;
the older `$ORCRAFT_TICKET` / `$MGTUI_TICKET` still work) and from
`[[T1234]]` / `T1234` in the prompt; `orc` from `$ORKCRAFT_ORC` (a deployed garrison orc). Never fails the host tool: any error is
swallowed and the hook exits 0. For agy it prints `{}` (agy reads hook stdout
as a response); for Claude and Codex it prints nothing (both add SessionStart /
UserPromptSubmit stdout to the conversation). Standard library only.
"""
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def main_repo(root: Path) -> Path:
    """The main checkout even when this copy runs in a git worktree (orkcraft orkspaces):
    a worktree's `.git` is a file `gitdir: <main>/.git/worktrees/<name>`."""
    dot_git = root / ".git"
    try:
        if dot_git.is_file():
            target = dot_git.read_text(encoding="utf-8").strip().removeprefix("gitdir:").strip()
            gitdir = (root / target).resolve() if not Path(target).is_absolute() else Path(target)
            if gitdir.parent.name == "worktrees" and gitdir.parents[1].name == ".git":
                return gitdir.parents[2]
    except OSError:
        pass
    return root


def project_of(cwd: str) -> Path | None:
    """The git checkout a session works in (the main repository for a worktree), or None outside one."""
    try:
        here = Path(cwd).resolve()
    except (OSError, RuntimeError):
        return None
    for folder in (here, *here.parents):
        if (folder / ".git").exists():
            return main_repo(folder)
    return None


LOG = main_repo(REPO) / ".orkcraft" / "sessions.jsonl"      # a session outside any git project
_TICKET = re.compile(r"\b(T\d{4,})\b")
_ORC = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}/[a-z0-9][a-z0-9_-]{0,63}$")
_RUN = re.compile(r"^[0-9a-f]{32}$")
_TERMINAL = re.compile(r"^[A-Za-z0-9:_./-]{1,200}$")
PROMPT_KEEP = 200


def _first(payload: dict, *keys: str) -> str:
    for k in keys:
        v = payload.get(k)
        if isinstance(v, str) and v:
            return v
    return ""


def record(harness: str, payload: dict, env: dict | None = None) -> dict | None:
    env = os.environ if env is None else env
    session = _first(payload, "session_id", "sessionId", "conversationId", "conversation_id")
    if not session:
        return None
    prompt = _first(payload, "prompt", "userPrompt", "user_prompt", "message")
    tickets = []
    ticket_env = env.get("ORKCRAFT_TICKET") or env.get("ORCRAFT_TICKET") or env.get("MGTUI_TICKET") or ""
    for t in [ticket_env] + _TICKET.findall(prompt):
        t = t.strip().upper()
        if t and t not in tickets:
            tickets.append(t)
    workspace = payload.get("workspacePaths")
    cwd = _first(payload, "cwd") or (workspace[0] if isinstance(workspace, list) and workspace else "")
    entry = {
        "ts": dt.datetime.now().isoformat(timespec="seconds"),
        "harness": harness,
        "event": _first(payload, "hook_event_name", "hookEventName", "event") or env.get("ORKCRAFT_HOOK_EVENT", ""),
        "session": session,
        "tickets": tickets,
        "cwd": cwd,
        "transcript": _first(payload, "transcript_path", "transcriptPath"),
        "prompt": prompt[:PROMPT_KEEP],
    }
    # A garrison orc deployed by orkcraft (`<building_id>/<orc_id>`): its Unit Chronicles.
    orc = (env.get("ORKCRAFT_ORC") or "").strip()
    if _ORC.match(orc):
        entry["orc"] = orc
    # Which orkcraft run and War Tent terminal started it: the 🪙 / 🪵 telemetry of that run.
    run = (env.get("ORKCRAFT_RUN") or "").strip()
    terminal = (env.get("ORKCRAFT_TERMINAL") or "").strip()
    if _RUN.match(run):
        entry["run"] = run
        if _TERMINAL.match(terminal):
            entry["terminal"] = terminal
    project = project_of(cwd) if cwd else None
    log = project / ".orkcraft" / "sessions.jsonl" if project else LOG
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def main() -> int:
    harness = sys.argv[1] if len(sys.argv) > 1 else "claude"
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
        if isinstance(payload, dict):
            record(harness, payload)
    except Exception:
        pass  # a hook must never break the session it observes
    if harness == "agy":
        print("{}")  # agy parses hook stdout; Claude would add it to the context
    return 0


if __name__ == "__main__":
    sys.exit(main())
