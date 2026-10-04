"""`orkcraft hooks install`: write the session hook and Warder into a project's Claude Code and Codex settings.

Merges into `<project>/.claude/settings.json` and, when Codex is here (on PATH, or the project
already has a `.codex/` folder), `<project>/.codex/hooks.json` — other hooks and settings stay
untouched, an orkcraft hook already there is replaced, not doubled. The command uses this
interpreter's absolute path, so the hooks run with the orkcraft that installed them (pipx or a venv).
Codex runs a project's hooks only once they are trusted: `/hooks` in Codex reviews them.
"""
from __future__ import annotations

import json
import shlex
import shutil
import sys
from pathlib import Path

from orkcraft.sources.sessions import codex_bin

WARDER_MATCHER = "Bash|Read|Edit|Write|MultiEdit|NotebookEdit|Grep|Glob"
CODEX_WARDER_MATCHER = "Bash|apply_patch|Edit|Write"     # Codex edits files through apply_patch
MARKERS = ("orkcraft.hooks.", "session_hook.py", "warder_hook.py")   # ours, old or new
FILES = {"claude": Path(".claude") / "settings.json", "codex": Path(".codex") / "hooks.json"}
CODEX_TRUST = "Codex runs them once trusted: open `codex` here and review them with /hooks"


def _cmd(module: str, *args: str) -> str:
    return " ".join([shlex.quote(sys.executable), "-m", f"orkcraft.hooks.{module}", *args])


def wanted(harness: str = "claude") -> dict[str, list[dict]]:
    session = {"hooks": [{"type": "command", "command": _cmd("session", harness), "timeout": 10}]}
    matcher, args = (WARDER_MATCHER, ()) if harness == "claude" else (CODEX_WARDER_MATCHER, (harness,))
    return {
        "SessionStart": [session],
        "UserPromptSubmit": [session],
        "PreToolUse": [{"matcher": matcher,
                        "hooks": [{"type": "command", "command": _cmd("warder", *args), "timeout": 10}]}],
    }


def wants_codex(project: Path) -> bool:
    """Whether Codex hooks belong here: Codex is installed, or the project already configures it."""
    return (Path(project) / ".codex").is_dir() or shutil.which(codex_bin()) is not None


def _ours(group: dict) -> bool:
    return any(any(m in str(h.get("command", "")) for m in MARKERS) for h in group.get("hooks", []))


def install(project: Path, harness: str = "claude") -> Path:
    """Returns the settings file written. Raises ValueError if it is not valid JSON."""
    path = Path(project) / FILES[harness]
    data: dict = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8") or "{}")
        except ValueError as e:
            raise ValueError(f"{path} is not valid JSON ({e}); fix it first") from e
        if not isinstance(data, dict):
            raise ValueError(f"{path} must hold a JSON object")
    hooks = data.setdefault("hooks", {})
    for event, groups in wanted(harness).items():
        kept = [g for g in hooks.get(event, []) if isinstance(g, dict) and not _ours(g)]
        hooks[event] = kept + groups
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def install_all(project: Path) -> list[Path]:
    """Claude Code's hooks always, Codex's when Codex is here."""
    return [install(project, h) for h in FILES if h == "claude" or wants_codex(project)]


def uninstall(project: Path, harness: str = "claude") -> Path | None:
    path = Path(project) / FILES[harness]
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


def uninstall_all(project: Path) -> list[Path]:
    return [p for p in (uninstall(project, h) for h in FILES) if p is not None]
