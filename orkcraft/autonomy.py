"""How much the orcs do on their own (design: docs/design/onboarding.md, the autonomy step).

    LEVELS[machine.autonomy]          0 ask me · 1 morning advice · 2 routine on their own · 3 free orcs
    advises(level)                    the Elders leave advice in quiet hours (realm/elders.py)
    claude_snippet(level)             what to paste into Claude Code's settings for this level
    agy_note(level)                   how to start agy for this level

Orkcraft never answers an agent's question itself. Autonomy comes from two places only:
- **advice** — in quiet hours the Elders read the questions and advise; the operator follows the
  advice with one key in the morning;
- **the agents' own permission settings** — what Claude Code and agy may do without asking, which the
  operator sets with the guide below. The 🛡 Warder hook still denies the dangerous commands in Claude
  Code sessions whatever the settings allow.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

DEFAULT_LEVEL = 1


@dataclass(frozen=True)
class Level:
    n: int
    icon: str
    title: str
    what: str


LEVELS: tuple[Level, ...] = (
    Level(0, "🙋", "Ask me", "Every question waits for you; nothing is judged while you are away."),
    Level(1, "🌅", "Morning advice", "In quiet hours the 🏛 Elders read the orcs' questions and leave advice; "
                                    "in the morning you follow it with one key."),
    Level(2, "🧭", "Routine on their own", "Agents read, edit the project and run its tests without asking "
                                          "(their own settings, below); the Elders advise on the rest."),
    Level(3, "🧌", "Free orcs", "Agents accept their edits and run the usual project commands; they still ask "
                               "before a push, and the Warder still denies the dangerous. The Elders advise."),
)

CLAUDE_FILE = ".claude/settings.local.json"      # this project, only you (not committed)
CLAUDE_FILE_ALL = "~/.claude/settings.json"       # every project on this machine

_ROUTINE = ["Read", "Grep", "Glob", "Edit", "Write",
            "Bash(pytest *)", "Bash(python -m pytest *)", "Bash(npm test *)", "Bash(npm run test *)",
            "Bash(npm run lint *)", "Bash(ruff *)", "Bash(git status *)", "Bash(git diff *)", "Bash(git log *)",
            "Bash(git show *)", "Bash(ls *)"]
_FREE = ["Bash(npm run *)", "Bash(npm install *)", "Bash(pip install *)", "Bash(make *)", "Bash(git add *)",
         "Bash(git commit *)", "Bash(git checkout *)", "Bash(git switch *)", "Bash(git stash *)"]
_ASK = ["Bash(git push *)", "Bash(rm *)", "Bash(git reset *)", "Bash(git rebase *)"]
_DENY = ["Bash(git push --force *)", "Bash(rm -rf *)", "Bash(sudo *)", "Read(./.env)", "Read(./.env.*)"]


def advises(level: int) -> bool:
    return level >= 1


def claude_settings(level: int) -> dict | None:
    """The permission block for Claude Code at this level; None when nothing is to be changed."""
    if level < 2:
        return None
    perms: dict = {"allow": list(_ROUTINE) + (list(_FREE) if level >= 3 else []), "ask": list(_ASK),
                   "deny": list(_DENY)}
    out: dict = {"permissions": perms}
    if level >= 3:
        out["permissions"]["defaultMode"] = "acceptEdits"
    return out


def claude_snippet(level: int) -> str:
    data = claude_settings(level)
    return json.dumps(data, indent=2) if data else ""


def agy_note(level: int) -> str:
    if level < 2:
        return "Start agy as you do now: it asks before it acts."
    if level == 2:
        return ("agy has no per-command allow list that orkcraft knows of: keep it asking, and let the Elders "
                "advise. (Orkcraft's own agy jobs already run in its sandbox.)")
    return ("Start agy in its sandbox, accepting its edits — the way orkcraft runs its own agy jobs:\n"
            "    agy --mode accept-edits --sandbox\n"
            "Check `agy --help` for your version: the flags may differ.")


def guide(level: int, tools: tuple[str, ...] = ("claude", "agy")) -> str:
    """The whole guide for this level, as plain text (onboarding shows it; docs/autonomy.md explains)."""
    lines: list[str] = []
    if "claude" in tools:
        snippet = claude_snippet(level)
        if snippet:
            lines += [f"Claude Code — merge into {CLAUDE_FILE} (this project) or {CLAUDE_FILE_ALL} (every project):",
                      snippet, ""]
        else:
            lines += ["Claude Code — nothing to change: it asks before it acts.", ""]
    if "agy" in tools:
        lines += ["Antigravity (agy):", agy_note(level), ""]
    lines.append("Orkcraft never presses yes for an agent: these settings are yours, and so is every answer.")
    return "\n".join(lines)
