"""`orkcraft hooks install`: write the session hook and Warder into a project's Claude Code, Codex and agy settings.

Merges into `<project>/.claude/settings.json`; when Codex is here (on PATH, or the project
already has a `.codex/` folder), `<project>/.codex/hooks.json`; and when agy 1.1.12 or later is on
PATH, `<project>/.agents/hooks.json` — other hooks and settings stay untouched, an orkcraft hook
already there is replaced, not doubled. The command uses this interpreter's absolute path, so the
hooks run with the orkcraft that installed them (pipx or a venv).
Codex runs a project's hooks only once they are trusted: `/hooks` in Codex reviews them. agy too
reads a project's `.agents/hooks.json` only once the folder is trusted.

agy's `hooks.json` names each hook by a top-level key; ours is `orkcraft`, and only that key is
written or removed. agy's headless steps run in an empty temp folder outside the project, so they
see only the global `~/.gemini/config/hooks.json`: `install_agy_global` writes there, and only
after the operator said yes (docs/design/agy-guard.md).
"""
from __future__ import annotations

import json
import shlex
import shutil
import sys
from pathlib import Path

from orkcraft import tools
from orkcraft.sources.sessions import codex_bin

WARDER_MATCHER = "Bash|Read|Edit|Write|MultiEdit|NotebookEdit|Grep|Glob"
CODEX_WARDER_MATCHER = "Bash|apply_patch|Edit|Write"     # Codex edits files through apply_patch
MARKERS = ("orkcraft.hooks.", "session_hook.py", "warder_hook.py")   # ours, old or new
# agy's tools the Warder judges: shell commands and the file tools (hooks/warder.py AGY_TOOLS)
AGY_WARDER_MATCHER = ("run_command|view_file|list_dir|grep_search|write_to_file|edit_file|replace_file_content"
                      "|multi_replace_file_content")
AGY_KEY = "orkcraft"                                     # our top-level entry in agy's hooks.json
FILES = {"claude": Path(".claude") / "settings.json", "codex": Path(".codex") / "hooks.json"}
AGY_FILE = Path(".agents") / "hooks.json"
CODEX_TRUST = "Codex runs them once trusted: open `codex` here and review them with /hooks"
AGY_TRUST = "agy runs them once this folder is trusted"
AGY_GLOBAL_ASK = ("agy's headless steps run in a temp folder outside the project and read only "
                  "~/.gemini/config/hooks.json. Guard them there too (adds orkcraft's entry, keeps the rest)?")


def agy_global_file() -> Path:
    return Path.home() / ".gemini" / "config" / "hooks.json"


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


def wants_agy(version: str | None = None) -> bool:
    """Whether agy's hooks belong here: an agy the Warder can guard (1.1.12 or later) is on PATH.
    `version`: agy's, when the caller knows it already (None: ask agy, blocking)."""
    if version is None:
        version = tools.agy_version()
    return version is not None and tools.agy_guardable(version)


def wanted_agy() -> dict[str, list[dict]]:
    """agy's events for our entry: the Warder before each tool, the session log per turn. Only tool
    events group their handlers under a `matcher`; the others list them directly."""
    session = {"type": "command", "command": _cmd("session", "agy"), "timeout": 10}
    return {
        "PreToolUse": [{"matcher": AGY_WARDER_MATCHER,
                        "hooks": [{"type": "command", "command": _cmd("warder", "agy"), "timeout": 10}]}],
        "PreInvocation": [session],
        "Stop": [session],
    }


def _read(path: Path) -> dict:
    """A hooks file's JSON object ({} when it is not there). Raises ValueError if it is not one."""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8") or "{}")
    except ValueError as e:
        raise ValueError(f"{path} is not valid JSON ({e}); fix it first") from e
    if not isinstance(data, dict):
        raise ValueError(f"{path} must hold a JSON object")
    return data


def _write(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def install_agy(path: Path) -> Path:
    """Merge our entry into an agy `hooks.json` (the project's or the global one); every other entry
    stays as it is. Raises ValueError if the file is not a JSON object."""
    data = _read(path)
    data[AGY_KEY] = wanted_agy()
    return _write(path, data)


def uninstall_agy(path: Path) -> Path | None:
    """Remove only our entry from an agy `hooks.json`; None when there was none."""
    if not path.exists():
        return None
    data = _read(path)
    if AGY_KEY not in data:
        return None
    del data[AGY_KEY]
    return _write(path, data)


def install_agy_global() -> Path:
    """The global `~/.gemini/config/hooks.json`, for agy's headless steps. Call only after asking."""
    return install_agy(agy_global_file())


def _ours(group: dict) -> bool:
    return any(any(m in str(h.get("command", "")) for m in MARKERS) for h in group.get("hooks", []))


def install(project: Path, harness: str = "claude") -> Path:
    """Returns the settings file written. Raises ValueError if it is not valid JSON."""
    path = Path(project) / FILES[harness]
    data = _read(path)
    hooks = data.setdefault("hooks", {})
    for event, groups in wanted(harness).items():
        kept = [g for g in hooks.get(event, []) if isinstance(g, dict) and not _ours(g)]
        hooks[event] = kept + groups
    return _write(path, data)


def install_all(project: Path, agy: bool | None = None) -> list[Path]:
    """Claude Code's hooks always, Codex's when Codex is here, agy's project file when `agy`
    (None: when an agy the Warder can guard is on PATH). Never the global agy file: see
    `install_agy_global`."""
    paths = [install(project, h) for h in FILES if h == "claude" or wants_codex(project)]
    if wants_agy() if agy is None else agy:
        paths.append(install_agy(Path(project) / AGY_FILE))
    return paths


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


def uninstall_all(project: Path, agy_global: bool = True) -> list[Path]:
    """Every orkcraft hook of the project, and our entry in the global agy file (only ours)."""
    paths = [uninstall(project, h) for h in FILES] + [uninstall_agy(Path(project) / AGY_FILE)]
    if agy_global:
        paths.append(uninstall_agy(agy_global_file()))
    return [p for p in paths if p is not None]
