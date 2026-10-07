#!/usr/bin/env python3
"""🛡️ Warder — the Council's security orc, as a PreToolUse hook of every AI tool orkcraft leads.

    .claude/settings.json → hooks.PreToolUse → python3 -m orkcraft.hooks.warder        (`orkcraft hooks install`)
    .codex/hooks.json     → hooks.PreToolUse → python3 -m orkcraft.hooks.warder codex
    .agents/hooks.json    → orkcraft.PreToolUse → python3 -m orkcraft.hooks.warder agy
    .cursor/hooks.json    → hooks.preToolUse → python3 -m orkcraft.hooks.warder cursor
    ~/.hermes/config.yaml → hooks.pre_tool_call → python3 -m orkcraft.hooks.warder hermes   (asked first)
    pi: the extension `-e …/orkcraft.ts` (hooks/pi_extension.py) → python3 -m orkcraft.hooks.warder pi

Hermes, Cursor and pi name their tools their way (`terminal`, `Shell`, `bash`…): `from_named` judges
each as the Claude Code tool it is, and `answer` says the verdict as each reads it (Hermes hands an
ask to its own approval gate; pi's extension asks in its UI, or refuses when no one is there).

Reads the hook payload (`tool_name`, `tool_input`, `cwd`) on stdin and decides:

- deny — catastrophic or secret-leaking: `rm -rf` of /, ~, the repo or .git; `curl … | sh`;
  mkfs / dd to a device / fork bombs; `git push --force`; reading, writing or staging secret
  files (.env, private keys, .ssh, .aws credentials, .netrc, …);
- ask  — destructive but legitimate: `git reset --hard`, `git clean -f`, discarding all changes,
  `git branch -D`, dropping stashes, `sudo`, dumping the environment, and edits to Warder itself
  (`orkcraft/hooks/warder.py`, `scripts/warder_hook.py`, `.claude/settings*.json`, `.codex/hooks.json`,
  `.codex/config.toml`). Codex cannot ask yet, so for Codex an ask is a deny that says why;
- nothing — everything else goes through the agent's normal permission flow.

Codex edits files with `apply_patch`: the files it touches are read from the patch itself.

agy sends `toolCall.name` / `toolCall.args` (camelCase, no `cwd`): `run_command`'s `CommandLine` is
judged as a Bash command, the file tools by the paths in their arguments, in `args.Cwd` or else
`workspacePaths[0]`. The answer is `{"decision": "deny" | "ask", "reason": …}`, or `{}` when there
is nothing to say — never `allow`, which agy ignores in headless runs (agy issue #1053), so the hook
only ever restricts. The same rules judge every harness (docs/design/agy-guard.md).

Every deny / ask is appended to `.orkcraft/warder.jsonl` of the project the session works in
(redacted, cut to 160 chars) so the Warder orc in orkcraft shows ❓ with the reason. An internal error never blocks a tool call (the
error is logged) — a guard must not brick the sessions it guards. Standard library only.
"""
from __future__ import annotations

import datetime as dt
import fnmatch
import json
import os
import re
import shlex
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def main_repo(root: Path) -> Path:
    """The main checkout even when this copy runs in a git worktree (orkcraft orkspaces), so every
    orkspace's Warder log lands where orkcraft reads it."""
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


LOG = main_repo(REPO) / ".orkcraft" / "warder.jsonl"      # a session outside any git project
EXCERPT = 160

DENY, ASK = "deny", "ask"

SECRET_NAMES = ("id_rsa", "id_dsa", "id_ecdsa", "id_ed25519", ".netrc", ".pgpass", ".npmrc", ".pypirc",
                ".git-credentials")
SECRET_GLOBS = ("*.pem", "*.key", "*.p12", "*.pfx", "*.keystore", "*.jks")
SECRET_DIRS = (".ssh", ".gnupg")
ENV_OK = (".env.example", ".env.sample", ".env.template", ".env.dist")
SELF = ("orkcraft/hooks/warder.py", "scripts/warder_hook.py", ".claude/settings.json", ".claude/settings.local.json",
        ".codex/hooks.json", ".codex/config.toml", ".agents/hooks.json", ".cursor/hooks.json",
        ".pi/extensions/orkcraft.ts")
AGY_GLOBAL = Path.home() / ".gemini" / "config" / "hooks.json"   # agy's hooks for every folder, headless steps' too
HERMES_GLOBAL = Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes") / "config.yaml"   # Hermes' hooks
# Programs that may name a secret file without reading it.
HARMLESS = {"ls", "stat", "test", "[", "file", "realpath", "dirname", "basename", "echo"}
_TOKEN = re.compile(r"(sk-[A-Za-z0-9_-]{8,}|gh[pousr]_[A-Za-z0-9]{8,}|xox[a-z]-[A-Za-z0-9-]{8,}|AKIA[A-Z0-9]{12,}"
                    r"|[A-Za-z0-9+/_-]{40,})")
_PIPE_SHELL = re.compile(r"\b(curl|wget|fetch)\b[^|;&]*\|\s*(sudo\s+)?(ba|z|da|k|fi)?sh\b")
_FORK_BOMB = re.compile(r":\s*\(\s*\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:")


def is_secret(path: str) -> bool:
    p = path.replace("\\", "/").strip().strip("'\"")
    if not p:
        return False
    parts = [x for x in p.split("/") if x]
    if not parts:
        return False
    name = parts[-1]
    if name.endswith(".pub") or name == "known_hosts":
        return False
    if name == ".env" or (name.startswith(".env.") and name not in ENV_OK):
        return True
    if name in SECRET_NAMES or any(fnmatch.fnmatch(name, g) for g in SECRET_GLOBS):
        return True
    if any(d in parts for d in SECRET_DIRS):
        return True
    if name == "credentials" and ".aws" in parts:
        return True
    return False


_HEREDOC = re.compile(r"<<(-?)\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\2")
_PATHLIKE = re.compile(r"^[A-Za-z0-9_./~+@%-]+$")


def strip_heredocs(command: str) -> str:
    """Drop here-document bodies: they are data fed to a program (code, text), not commands."""
    lines = command.split("\n")
    out, i = [], 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        m = _HEREDOC.search(line)
        i += 1
        if m:
            delim, dash = m.group(3), m.group(1) == "-"
            while i < len(lines) and (lines[i].strip() if dash else lines[i]) != delim:
                i += 1
            i += 1  # the delimiter line
    return "\n".join(out)


def _segments(command: str) -> list[list[str]]:
    """The command split into simple commands (on newlines and ; && || | &), each as argv."""
    segments: list[list[str]] = []
    for line in command.split("\n"):
        try:
            lexer = shlex.shlex(line, posix=True, punctuation_chars=";&|")
            lexer.whitespace_split = True
            tokens = list(lexer)
        except ValueError:  # unbalanced quotes (e.g. a string spanning lines): a rough split
            tokens = line.split()
        current: list[str] = []
        for tok in tokens:
            if tok and set(tok) <= set(";&|"):
                if current:
                    segments.append(current)
                current = []
            else:
                current.append(tok)
        if current:
            segments.append(current)
    return segments


def _strip_prefix(argv: list[str]) -> tuple[list[str], bool]:
    """Drop env assignments and wrappers (sudo, env, nice, time, command, exec); report sudo."""
    sudo = False
    i = 0
    while i < len(argv):
        a = argv[i]
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", a):
            i += 1
        elif a in ("sudo", "doas"):
            sudo = True
            i += 1
            while i < len(argv) and argv[i].startswith("-"):
                i += 1
        elif a in ("env", "nice", "time", "command", "exec", "nohup", "xargs"):
            i += 1
            while i < len(argv) and argv[i].startswith("-"):
                i += 1
        else:
            break
    return argv[i:], sudo


WRITERS = {"tee", "sed", "cp", "mv", "rm", "truncate", "install", "ln", "dd", "perl", "awk", "patch"}


def _is_self(token: str, cwd: Path) -> bool:
    piece = token.lstrip(">").strip()
    if not piece or not _PATHLIKE.match(piece):
        return False
    return self_name(cwd / os.path.expanduser(piece)) is not None


def self_name(path: Path) -> str | None:
    """How Warder names one of its own files, or None for any other file."""
    try:
        resolved = path.resolve()
        if resolved == AGY_GLOBAL.resolve():
            return "~/.gemini/config/hooks.json"
        if resolved == HERMES_GLOBAL.resolve():
            return "~/.hermes/config.yaml"
        rel = resolved.relative_to(REPO).as_posix()
    except (ValueError, OSError, RuntimeError):
        return None
    return rel if rel in SELF else None


def _danger_target(target: str, cwd: Path) -> bool:
    t = target.strip()
    if t in ("/", "/*", "~", "~/", "~/*", "$HOME", "${HOME}", "$HOME/", "*", ".", "./", "..", "../", "./*", ".git"):
        return True
    expanded = os.path.expanduser(os.path.expandvars(t))
    try:
        resolved = (cwd / expanded).resolve() if not os.path.isabs(expanded) else Path(expanded).resolve()
    except (OSError, RuntimeError):
        return False
    home = Path.home().resolve()
    return resolved in (Path("/"), home, REPO, REPO / ".git") or resolved == cwd.resolve() or len(resolved.parts) <= 2


def judge_bash(command: str, cwd: Path) -> tuple[str, str] | None:
    command = strip_heredocs(command)
    if _FORK_BOMB.search(command):
        return DENY, "fork bomb"
    if _PIPE_SHELL.search(command):
        return DENY, "piping a download into a shell runs unreviewed code — download, read, then run"
    verdict: tuple[str, str] | None = None
    for raw in _segments(command):
        argv, sudo = _strip_prefix(raw)
        if not argv:
            if raw and os.path.basename(raw[-1]) in ("env", "printenv"):   # a bare `env` dumps everything
                verdict = verdict or (ASK, "prints environment variables, which may hold tokens")
            continue
        prog = os.path.basename(argv[0])
        args = argv[1:]
        flags = "".join(a[1:] for a in args if a.startswith("-") and not a.startswith("--"))
        longs = {a for a in args if a.startswith("--")}
        # secrets: any secret path named by a program that may read, copy or stage it
        if prog not in HARMLESS:
            for a in args:
                for piece in re.split(r"[=:<>]", a):
                    if _PATHLIKE.match(piece) and is_secret(piece):
                        return DENY, f"{piece} looks like a secret (keys, tokens, .env) — Warder keeps it out of sessions"
        # Warder's own files: rewriting them from a shell is still an edit of the guard.
        writes = prog in WRITERS or any(">" in a for a in raw)
        if writes and any(_is_self(a, cwd) for a in args):
            verdict = verdict or (ASK, "rewrites Warder's own configuration from a shell")
        if prog == "rm" and ("r" in flags.lower() or "--recursive" in longs):
            targets = [a for a in args if not a.startswith("-")]
            if any(_danger_target(t, cwd) for t in targets):
                return DENY, "recursive delete of /, ~, the repository or .git"
        if prog in ("mkfs",) or prog.startswith("mkfs."):
            return DENY, "formatting a filesystem"
        if prog == "dd" and any(a.startswith("of=/dev/") for a in args):
            return DENY, "dd onto a device"
        if prog in ("chmod", "chown") and ("R" in flags or "--recursive" in longs) and any(
                _danger_target(a, cwd) for a in args if not a.startswith("-")):
            return DENY, f"recursive {prog} of /, ~ or the repository"
        if prog == "git" and args:
            sub = args[0]
            rest = args[1:]
            if sub == "push" and ("--force" in rest or any(re.match(r"^-[a-zA-Z]*f", a) for a in rest)
                                  or any(a.startswith("+") for a in rest)):
                return DENY, "force-push rewrites shared history — use --force-with-lease on your own branch"
            if sub == "reset" and "--hard" in rest:
                verdict = verdict or (ASK, "git reset --hard discards uncommitted work")
            elif sub == "clean" and any(re.match(r"^-[a-zA-Z]*f", a) or a == "--force" for a in rest):
                verdict = verdict or (ASK, "git clean -f deletes untracked files")
            elif sub in ("checkout", "restore") and ("." in rest or "--" in rest and rest[-1] == "."):
                verdict = verdict or (ASK, f"git {sub} . discards every uncommitted change")
            elif sub == "branch" and ("-D" in rest or "--delete" in rest and "--force" in rest):
                verdict = verdict or (ASK, "force-deleting a branch")
            elif sub == "stash" and rest[:1] in (["drop"], ["clear"]):
                verdict = verdict or (ASK, "dropping stashed work")
        if prog in ("printenv",) or (prog in ("env", "set", "export") and not args):
            verdict = verdict or (ASK, "prints environment variables, which may hold tokens")
        if sudo:
            verdict = verdict or (ASK, "runs as root")
    return verdict


def _paths_of(tool_input: dict) -> list[str]:
    out = []
    for key, value in tool_input.items():
        if isinstance(value, str) and ("path" in key or key in ("file", "glob", "pattern")):
            out.append(value)
    return out


_PATCH_FILE = re.compile(r"^\*\*\* (?:(?:Add|Update|Delete) File|Move to): (.+)$", re.MULTILINE)


def patch_paths(patch: str) -> list[str]:
    """The files a Codex `apply_patch` touches: its `*** Add / Update / Delete File:` and `*** Move to:` lines."""
    return [p.strip() for p in _PATCH_FILE.findall(patch)]


def judge(tool_name: str, tool_input: dict, cwd: Path) -> tuple[str, str] | None:
    if tool_name == "Bash":
        return judge_bash(str(tool_input.get("command") or ""), cwd)
    paths = _paths_of(tool_input)
    if tool_name == "apply_patch":                        # Codex: the patch names the files it edits
        paths = patch_paths(str(tool_input.get("command") or ""))
    if tool_name in ("Grep", "Glob"):
        paths = [str(tool_input.get("path") or "")] + ([str(tool_input["glob"])] if tool_input.get("glob") else [])
    for p in paths:
        if p and is_secret(p):
            return DENY, f"{p} looks like a secret (keys, tokens, .env) — Warder keeps it out of sessions"
    if tool_name in ("Edit", "Write", "MultiEdit", "NotebookEdit", "apply_patch"):
        for p in paths:
            if p and (name := self_name(cwd / os.path.expanduser(p))):
                return ASK, f"{name} configures Warder itself"
    return None


# agy's tools, as the Claude Code tool judged in their place (unknown ones keep their name: paths only).
AGY_TOOLS = {"run_command": "Bash", "view_file": "Read", "list_dir": "Read", "grep_search": "Read",
             "write_to_file": "Write", "edit_file": "Edit", "replace_file_content": "Edit",
             "multi_replace_file_content": "MultiEdit"}


def _agy_paths(args: dict) -> list[str]:
    """The file paths in an agy tool's arguments (`TargetFile`, `AbsolutePath`, `SearchPath`, …),
    never their content."""
    return [v for k, v in args.items() if isinstance(v, str) and v and "content" not in k.lower()
            and ("path" in k.lower() or "file" in k.lower() or "dir" in k.lower())]


def from_agy(payload: dict) -> tuple[str, dict, Path]:
    """An agy hook payload as (tool, tool_input, cwd) in Claude Code's shape."""
    call = payload.get("toolCall") if isinstance(payload.get("toolCall"), dict) else {}
    args = call.get("args") if isinstance(call.get("args"), dict) else {}
    name = str(call.get("name") or "")
    roots = [w for w in payload.get("workspacePaths") or [] if isinstance(w, str) and w]
    cwd = Path(str(args.get("Cwd") or (roots[0] if roots else "") or os.getcwd()))
    tool = AGY_TOOLS.get(name, name)
    if tool == "Bash":
        return tool, {"command": str(args.get("CommandLine") or "")}, cwd
    return tool, {f"path{i}": p for i, p in enumerate(_agy_paths(args))}, cwd


# Hermes, Cursor and pi: their tools, as the Claude Code tool judged in their place.
HERMES_TOOLS = {"terminal": "Bash", "read_file": "Read", "search_files": "Grep", "write_file": "Write", "patch": "Edit"}
CURSOR_TOOLS = {"Shell": "Bash", "Read": "Read", "Grep": "Grep", "Write": "Write", "Delete": "Write"}
PI_TOOLS = {"bash": "Bash", "read": "Read", "grep": "Grep", "find": "Grep", "ls": "Read", "edit": "Edit", "write": "Write"}
NAMES = {"hermes": HERMES_TOOLS, "cursor": CURSOR_TOOLS, "pi": PI_TOOLS}


def from_named(harness: str, payload: dict) -> tuple[str, dict, Path]:
    """A Hermes, Cursor or pi payload (`tool_name`, `tool_input`, `cwd`; Cursor's `command` on
    beforeShellExecution, its `workspace_roots`) as (tool, tool_input, cwd) in Claude Code's shape."""
    name = str(payload.get("tool_name") or ("Shell" if payload.get("command") else ""))
    tool_input = payload.get("tool_input") if isinstance(payload.get("tool_input"), dict) else {}
    if not tool_input and payload.get("command"):
        tool_input = {"command": str(payload["command"])}
    roots = [w for w in payload.get("workspace_roots") or [] if isinstance(w, str) and w]
    cwd = Path(str(payload.get("cwd") or (roots[0] if roots else "") or os.getcwd()))
    tool = NAMES[harness].get(name, name)
    if tool == "Bash":
        return tool, {"command": str(tool_input.get("command") or tool_input.get("cmd") or "")}, cwd
    return tool, {k: v for k, v in tool_input.items() if isinstance(v, str) and "content" not in k.lower()}, cwd


def answer(harness: str, decision: str, reason: str) -> str:
    """What each tool reads on stdout as a refusal (deny) or a question (ask)."""
    said = f"🛡️ Warder: {reason}"
    if harness in ("agy", "pi"):                          # pi: its extension (hooks/pi_extension.py) reads this
        return json.dumps({"decision": decision, "reason": said}, ensure_ascii=False)
    if harness == "hermes":                               # "approve" hands it to Hermes' own approval gate
        return json.dumps({"action": "approve", "message": said} if decision == ASK
                          else {"decision": "block", "reason": said}, ensure_ascii=False)
    if harness == "cursor":
        return json.dumps({"permission": decision, "user_message": said, "agent_message": said}, ensure_ascii=False)
    return json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": decision,
                                              "permissionDecisionReason": said}})


def redact(text: str) -> str:
    text = _TOKEN.sub("***", text.replace("\n", " "))
    return text if len(text) <= EXCERPT else text[: EXCERPT - 1] + "…"


def log(entry: dict, cwd: Path | None = None) -> None:
    project = project_of(str(cwd)) if cwd else None
    path = project / ".orkcraft" / "warder.jsonl" if project else LOG
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


def main() -> int:
    harness = sys.argv[1] if len(sys.argv) > 1 else "claude"
    agy = harness == "agy"
    payload: dict = {}
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        if agy:
            tool, tool_input, cwd = from_agy(payload)
        elif harness in NAMES:
            tool, tool_input, cwd = from_named(harness, payload)
        else:
            tool = str(payload.get("tool_name") or "")
            tool_input = payload.get("tool_input") if isinstance(payload.get("tool_input"), dict) else {}
            cwd = Path(str(payload.get("cwd") or os.getcwd()))
        verdict = judge(tool, tool_input, cwd)
    except Exception as e:  # never block on our own bug — but leave a trace
        log({"ts": dt.datetime.now().isoformat(timespec="seconds"), "decision": "error", "reason": redact(repr(e))})
        verdict = None
    if verdict is None:
        if agy or harness == "cursor":
            print("{}")                                   # they read every hook's stdout as its answer
        return 0
    decision, reason = verdict
    if decision == ASK and harness == "codex":           # Codex parses "ask" but does not support it yet
        decision, reason = DENY, f"{reason} — Codex cannot ask, so Warder stops it; run it yourself if you mean it"
    if tool == "apply_patch":
        subject = ", ".join(patch_paths(str(tool_input.get("command") or "")))
    else:
        subject = tool_input.get("command") or next(iter(_paths_of(tool_input)), "")
    session = _first_of(payload, "conversationId" if agy else "session_id", "conversation_id")
    log({"ts": dt.datetime.now().isoformat(timespec="seconds"), "decision": decision, "tool": tool,
         "reason": reason, "subject": redact(str(subject)), "session": session[:64]}, cwd)
    print(answer(harness, decision, reason))             # agy: deny or ask only — it ignores an allow (#1053)
    return 0


def _first_of(payload: dict, *keys: str) -> str:
    return next((str(payload[k]) for k in keys if isinstance(payload, dict) and payload.get(k)), "")


if __name__ == "__main__":
    sys.exit(main())
