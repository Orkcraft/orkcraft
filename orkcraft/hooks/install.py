"""`orkcraft hooks install`: write the session hook and Warder into a project's Claude Code settings.

Merges into `<project>/.claude/settings.json` — other hooks and settings stay untouched, an
orkcraft hook already there is replaced, not doubled. The command uses this interpreter's
absolute path, so the hooks run with the orkcraft that installed them (pipx or a venv).
"""
from __future__ import annotations

import json
import shlex
import sys
from pathlib import Path

WARDER_MATCHER = "Bash|Read|Edit|Write|MultiEdit|NotebookEdit|Grep|Glob"
MARKERS = ("orkcraft.hooks.", "session_hook.py", "warder_hook.py")   # ours, old or new


def _cmd(module: str, *args: str) -> str:
    return " ".join([shlex.quote(sys.executable), "-m", f"orkcraft.hooks.{module}", *args])


def wanted() -> dict[str, list[dict]]:
    session = {"hooks": [{"type": "command", "command": _cmd("session", "claude"), "timeout": 10}]}
    return {
        "SessionStart": [session],
        "UserPromptSubmit": [session],
        "PreToolUse": [{"matcher": WARDER_MATCHER,
                        "hooks": [{"type": "command", "command": _cmd("warder"), "timeout": 10}]}],
    }


def _ours(group: dict) -> bool:
    return any(any(m in str(h.get("command", "")) for m in MARKERS) for h in group.get("hooks", []))


def install(project: Path) -> Path:
    """Returns the settings file written. Raises ValueError if it is not valid JSON."""
    path = Path(project) / ".claude" / "settings.json"
    data: dict = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8") or "{}")
        except ValueError as e:
            raise ValueError(f"{path} is not valid JSON ({e}); fix it first") from e
        if not isinstance(data, dict):
            raise ValueError(f"{path} must hold a JSON object")
    hooks = data.setdefault("hooks", {})
    for event, groups in wanted().items():
        kept = [g for g in hooks.get(event, []) if isinstance(g, dict) and not _ours(g)]
        hooks[event] = kept + groups
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def uninstall(project: Path) -> Path | None:
    path = Path(project) / ".claude" / "settings.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8") or "{}")
    hooks = data.get("hooks", {})
    for event in list(hooks):
        hooks[event] = [g for g in hooks[event] if not (isinstance(g, dict) and _ours(g))]
        if not hooks[event]:
            del hooks[event]
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path
