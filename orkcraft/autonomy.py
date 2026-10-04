"""How much the orcs do on their own (design: docs/design/onboarding.md, the autonomy step).

    LEVELS[machine.autonomy]          0 ask me · 1 morning advice · 2 routine on their own · 3 free orcs
    advises(level)                    the Elders judge the questions in quiet hours (realm/elders.py)
    answers(level)                    …and answer them themselves (⛓️‍💥 Free orcs only)
    claude_snippet(level)             what to paste into Claude Code's settings for this level (📋)
    agy_command(level)                how to start agy for this level (📋)

Autonomy comes from three places:
- **advice** (from 📜) — in quiet hours the Elders read the questions and advise; the operator
  follows the advice with one key in the morning;
- **the Elders' answers** (⛓️‍💥 only) — in quiet hours they send their one-time yes or no themselves;
  what the Warder's rules stop, and anything they would not advise, still waits for the operator;
- **the agents' own permission settings** (from 🧭) — what Claude Code and agy may do without asking,
  which the operator sets with the guide below. The 🛡 Warder hook still denies the dangerous
  commands in Claude Code sessions whatever the settings allow.
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
    questions: str       # what happens to the agents' questions
    improves: str        # what the orcs do about improving the camp (realm/evolution.py)


LEVELS: tuple[Level, ...] = (
    Level(0, "⛓️", "Ask me",
          "every question waits for you; nothing is judged while you are away.",
          "proposals wait for your click."),
    Level(1, "📜", "Morning advice",
          "in quiet hours the 🏛 Elders read them and leave advice; in the morning `a` follows it.",
          "proposals wait for your click."),
    Level(2, "🧭", "Routine on their own",
          "agents run the routine without asking (their settings, 📋 below); the Elders advise on the rest.",
          "in quiet hours the orks apply what makes a building cheaper or simpler — a shorter prompt, an "
          "agent made a chain, a run policy, a road filter."),
    Level(3, "⛓️‍💥", "Free orks",
          "in quiet hours the Elders answer routine ones themselves (a one-time yes or no, never 'always'); "
          "the risky ones wait for you.",
          "also a script instead of an agent, a new plain road, a setting, a building from the catalog. "
          "Never a removal."),
)

# What every self-applied change goes through, shown under the levels that apply changes.
SAFEGUARDS = ("the Council's review, a checkpoint each (Z takes it back), 24 h on probation — a 👎 or more "
              "failed runs take it back by itself — and the list of changes after quiet hours.")

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


def answers(level: int) -> bool:
    return level >= 3


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


def agy_command(level: int) -> str:
    """How to start agy at this level, or "" when it stays as it is."""
    return "agy --mode accept-edits --sandbox" if level >= 3 else ""


def claude_line(level: int) -> str:
    if not claude_settings(level):
        return "nothing to change — it asks before it acts."
    return f"its permissions for this level → paste into {CLAUDE_FILE} (or {CLAUDE_FILE_ALL})."


def agy_line(level: int) -> str:
    if level < 2:
        return "nothing to change — it asks before it acts."
    if level == 2:
        return "keeps asking (no per-command allow list known); the Elders advise."
    return f"start it with `{agy_command(level)}` (check `agy --help`)."


def guide(level: int, tools: tuple[str, ...] = ("claude", "agy")) -> str:
    """The guide as plain text (docs and tests); the screen shows the same lines with 📋 buttons."""
    lines: list[str] = []
    if "claude" in tools:
        lines.append(f"Claude Code: {claude_line(level)}")
        if claude_snippet(level):
            lines.append(claude_snippet(level))
    if "agy" in tools:
        lines.append(f"Antigravity: {agy_line(level)}")
        if agy_command(level):
            lines.append(f"    {agy_command(level)}")
    if answers(level):
        lines.append("In quiet hours the 🏛 Elders answer routine questions for you (a one-time yes or no); "
                     "every answer is in .orkcraft/council/elders.jsonl. Move the slider down to stop it.")
    else:
        lines.append("Orkcraft never presses yes for an agent at this level: the Elders only advise.")
    return "\n".join(lines)
