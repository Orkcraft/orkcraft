"""`orkcraft hooks install`: write the session hook and Warder into the settings of every AI tool orkcraft leads.

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

Cursor: `<project>/.cursor/hooks.json` (`preToolUse`, `sessionStart`, `beforeSubmitPrompt`) when
cursor-agent is on PATH or the project has `.cursor/`. pi has no hook config: its extension goes to
`<project>/.pi/extensions/orkcraft.ts` (pi loads it once the folder is trusted; the runs orkcraft
starts pass it with `-e`). Hermes reads hooks only from its own `~/.hermes/config.yaml`: a block of
ours, between two marker comments, is added there after the operator said yes — never into a file
that already has a `hooks:` key of its own (`HERMES_MERGE` says what to add by hand then).
"""
from __future__ import annotations

import json
import os
import shlex
import shutil
import sys
from pathlib import Path

from orkcraft import tools
from orkcraft.hooks import pi_extension
from orkcraft.realm import harnesses
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


CURSOR_FILE = Path(".cursor") / "hooks.json"
CURSOR_WARDER_MATCHER = "Shell|Read|Write|Grep|Delete"
PI_FILE = Path(".pi") / "extensions" / "orkcraft.ts"
HERMES_WARDER_MATCHER = "terminal|read_file|search_files|write_file|patch"
HERMES_BEGIN, HERMES_END = "# >>> orkcraft hooks (orkcraft hooks uninstall removes them)", "# <<< orkcraft hooks"
HERMES_GLOBAL_ASK = ("Hermes reads hooks only from ~/.hermes/config.yaml. Guard it there too (adds orkcraft's "
                     "block between two marked lines, keeps the rest)?")
HERMES_MERGE = "Hermes' config.yaml already has its own hooks: add orkcraft's by hand —"


def _on_path(harness: str) -> bool:
    h = harnesses.get(harness)
    return h is not None and shutil.which(h.bin) is not None


def wanted_cursor() -> dict:
    """Cursor's hooks file: the Warder before a tool, the session log at a start and per prompt."""
    session = {"command": _cmd("session", "cursor"), "timeout": 10}
    return {"preToolUse": [{"command": _cmd("warder", "cursor"), "matcher": CURSOR_WARDER_MATCHER, "timeout": 10}],
            "sessionStart": [session], "beforeSubmitPrompt": [session]}


def install_cursor(project: Path) -> Path:
    """Merge ours into `.cursor/hooks.json`: an orkcraft hook already there is replaced, others stay."""
    path = Path(project) / CURSOR_FILE
    data = _read(path)
    data.setdefault("version", 1)
    hooks = data.setdefault("hooks", {})
    for event, entries in wanted_cursor().items():
        kept = [e for e in hooks.get(event, []) if isinstance(e, dict) and not _ours({"hooks": [e]})]
        hooks[event] = kept + entries
    return _write(path, data)


def uninstall_cursor(project: Path) -> Path | None:
    path = Path(project) / CURSOR_FILE
    if not path.exists():
        return None
    data = _read(path)
    hooks = data.get("hooks") if isinstance(data.get("hooks"), dict) else {}
    found = False
    for event in list(hooks):
        kept = [e for e in hooks[event] if not (isinstance(e, dict) and _ours({"hooks": [e]}))]
        found |= len(kept) != len(hooks[event])
        hooks[event] = kept
        if not kept:
            del hooks[event]
    return _write(path, data) if found else None


def install_pi(project: Path) -> Path | None:
    """The project's copy of pi's extension (`.pi/extensions/orkcraft.ts`)."""
    return pi_extension.write(Path(project) / PI_FILE)


def uninstall_pi(project: Path) -> Path | None:
    path = Path(project) / PI_FILE
    if not path.exists():
        return None
    path.unlink()
    return path


def hermes_global_file() -> Path:
    return Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes") / "config.yaml"


def hermes_block() -> str:
    """Our hooks for Hermes' config.yaml, plain YAML (no library: it is written, never parsed)."""
    warder, session = _cmd("warder", "hermes"), _cmd("session", "hermes")
    q = json.dumps                                         # a JSON string is a YAML string
    return "\n".join([
        HERMES_BEGIN, "hooks:",
        "  pre_tool_call:", f"    - matcher: {q(HERMES_WARDER_MATCHER)}", f"      command: {q(warder)}",
        "      timeout: 10",
        "  on_session_start:", f"    - command: {q(session)}", "      timeout: 10",
        "  pre_llm_call:", f"    - command: {q(session)}", "      timeout: 10",
        HERMES_END, ""])


def _without_ours(text: str) -> tuple[str, bool]:
    lines, out, inside, found = text.splitlines(keepends=True), [], False, False
    for line in lines:
        if line.strip() == HERMES_BEGIN:
            inside = found = True
        elif inside and line.strip() == HERMES_END:
            inside = False
        elif not inside:
            out.append(line)
    return "".join(out), found


def install_hermes_global(path: Path | None = None) -> Path:
    """Our block in Hermes' config.yaml (replaced when there). Raises ValueError when the file has a
    `hooks:` key of its own: two would clash, so the operator merges by hand (`HERMES_MERGE`)."""
    path = path or hermes_global_file()
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    rest, _ = _without_ours(text)
    if any(line.startswith("hooks:") for line in rest.splitlines()):
        raise ValueError(f"{HERMES_MERGE}\n{hermes_block()}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rest + ("" if not rest or rest.endswith("\n") else "\n") + hermes_block(), encoding="utf-8")
    return path


def uninstall_hermes_global(path: Path | None = None) -> Path | None:
    path = path or hermes_global_file()
    if not path.exists():
        return None
    rest, found = _without_ours(path.read_text(encoding="utf-8"))
    if not found:
        return None
    path.write_text(rest, encoding="utf-8")
    return path


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


AGY_UNGUARDED = ("The 🛡 Security reviewer does not guard agy yet: agy sessions run with only agy's own sandbox "
                 "and permission prompts, so start agy with --sandbox and keep secrets out of the project folder.")
AGY_GUARDED = ("The 🛡 Security reviewer guards agy too, through .agents/hooks.json once agy trusts this folder. "
               "`orkcraft hooks install` asks before guarding agy's headless steps as well.")
AGY_TOO_OLD = ("The 🛡 Security reviewer cannot guard {agy}: it needs agy {least} or later. agy sessions run with "
               "only agy's own sandbox and permission prompts, so start agy with --sandbox and keep secrets out "
               "of the project folder.")


def agy_warder_line(checked: bool, statuses: list[tools.ToolStatus] | None) -> str:
    """What the onboarding's guard step says about agy. Until its hook was checked on a live agy
    (`MachineSettings.agy_warder_checked`, docs/design/agy-guard.md §8), that it does not guard agy
    yet; then whether this agy is recent enough for it."""
    if not checked or statuses is None:
        return AGY_UNGUARDED
    agy = next((st for st in statuses if st.id == "agy"), None)
    if agy is not None and agy.found and tools.agy_guardable(agy.version):
        return AGY_GUARDED
    least = ".".join(map(str, tools.AGY_WARDER_MIN))
    what = "agy, which is not installed here" if agy is None or not agy.found else \
        f"agy {agy.version}" if agy.version else "this agy, which does not say its version"
    return AGY_TOO_OLD.format(agy=what, least=least)


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
    if (Path(project) / ".cursor").is_dir() or _on_path("cursor"):
        paths.append(install_cursor(project))
    if ((Path(project) / ".pi").is_dir() or _on_path("pi")) and (pi := install_pi(project)) is not None:
        paths.append(pi)
    return paths


def wants_hermes() -> bool:
    """Whether to offer Hermes' global hooks: Hermes is on PATH."""
    return _on_path("hermes")


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
    paths = [uninstall(project, h) for h in FILES] + [uninstall_agy(Path(project) / AGY_FILE),
                                                      uninstall_cursor(project), uninstall_pi(project)]
    if agy_global:
        paths.append(uninstall_agy(agy_global_file()))
        paths.append(uninstall_hermes_global())
    return [p for p in paths if p is not None]
