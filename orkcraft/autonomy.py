"""How much the orks do on their own (design: docs/design/barracks-planning.md §2, the onboarding step).

    LEVELS[machine.autonomy]          0 ⛓️ chains · 1 ⏳ timer · 2 ⛓️‍💥 free orks
    waits(level, quiet, minutes)      how long a decision waits for the operator before the orks take
                                      it: None never (chains), 0 at once, else minutes
    answers(level)                    the orks (the Elders, the stewards) may decide themselves at all
    of(value)                         a stored value → a level: the words, and the old 0..3 numbers
    claude_snippet(level)             what to paste into Claude Code's settings for this level (📋)
    agy_command(level)                how to start agy for this level (📋)
    codex_command(level)              how to start Codex for this level (📋)

One rule for every decision the orks could take for the operator — an agent's question (the Elders,
realm/elders.py), a new persona of a Barracks, a self-improvement (realm/evolution.py):

- **⛓️ Chains** — it waits for the operator. The Elders only advise, in quiet hours; the operator
  follows the advice with one key.
- **⏳ Timer** — it waits `autonomy_wait` minutes (5–10), then the orks decide; in quiet hours nobody
  is there to answer, so they do not wait. Silence never makes the camp spend more: of the
  self-improvements, only what makes a building cheaper or simpler.
- **⛓️‍💥 Free orks** — the orks decide at once; the operator sees the list afterwards.

At every level: what the Warder's rules block waits for the operator, only a one-time yes is sent
(never "always"), a removal is never the orks', and every change has the Council, a checkpoint and
probation. The agents' own permission settings (what Claude Code, agy and Codex do without asking)
follow the level too — the operator sets them with the guide below; the 🛡 Warder hook still denies
the dangerous commands whatever they allow.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

CHAINS, TIMER, FREE = 0, 1, 2
WORDS = ("chains", "timer", "free")
DEFAULT_LEVEL = TIMER
# The old four stops, never bolder than they were: ask me and morning advice wait, routine has a timer.
OLD_NUMBERS = {0: CHAINS, 1: CHAINS, 2: TIMER, 3: FREE}
DEFAULT_WAIT, MIN_WAIT, MAX_WAIT = 7, 5, 10       # ⏳ minutes


@dataclass(frozen=True)
class Level:
    n: int
    icon: str
    title: str
    questions: str       # what happens to the agents' questions and the stewards' new personas
    improves: str        # what the orks do about improving the camp (realm/evolution.py)


LEVELS: tuple[Level, ...] = (
    Level(CHAINS, "⛓️", "Chains",
          "every decision waits for you; in quiet hours the 🏛 Elders leave advice, `a` follows it.",
          "proposals wait for your click."),
    Level(TIMER, "⏳", "Timer",
          "a decision waits for you a few minutes, then the orks take it; in quiet hours they do not wait.",
          "in quiet hours the orks apply what makes a building cheaper or simpler — a shorter prompt, an "
          "agent made a chain, a run policy, a road filter."),
    Level(FREE, "⛓️‍💥", "Free orks",
          "the orks decide at once; you see the list of what they did.",
          "also a script instead of an agent, a richer prompt for a ⚖️ / 💎 building, a new plain road, a setting, "
          "a building from the catalog. "
          "Never a removal."),
)

# What every self-applied change goes through, shown under the levels that apply changes.
SAFEGUARDS = ("the Council's review, a checkpoint each (Z takes it back), 24 h on probation — a 👎 or more "
              "failed runs take it back by itself — and the list of changes after quiet hours.")


def of(value: object) -> int:
    """A stored value → a level: "chains" / "timer" / "free", an old number 0..3, else the default."""
    if isinstance(value, str) and value in WORDS:
        return WORDS.index(value)
    if isinstance(value, int) and not isinstance(value, bool) and value in OLD_NUMBERS:
        return OLD_NUMBERS[value]
    return DEFAULT_LEVEL


def word(level: int) -> str:
    return WORDS[max(0, min(len(WORDS) - 1, level))]


def wait_of(value: object) -> int:
    """⏳ minutes, within MIN_WAIT..MAX_WAIT."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return int(max(MIN_WAIT, min(MAX_WAIT, value)))
    return DEFAULT_WAIT


def waits(level: int, quiet: bool, minutes: int = DEFAULT_WAIT) -> float | None:
    """How many minutes a decision waits for the operator before the orks take it; None: it waits for
    the operator, however long. In quiet hours nobody is there, so ⏳ does not wait."""
    if level <= CHAINS:
        return None
    if level >= FREE or quiet:
        return 0
    return float(minutes)


def answers(level: int) -> bool:
    """May the orks decide anything for the operator at all (after the wait)?"""
    return level >= TIMER


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


def claude_settings(level: int) -> dict | None:
    """The permission block for Claude Code at this level; None when nothing is to be changed."""
    if level < TIMER:
        return None
    perms: dict = {"allow": list(_ROUTINE) + (list(_FREE) if level >= FREE else []), "ask": list(_ASK),
                   "deny": list(_DENY)}
    out: dict = {"permissions": perms}
    if level >= FREE:
        out["permissions"]["defaultMode"] = "acceptEdits"
    return out


def claude_snippet(level: int) -> str:
    data = claude_settings(level)
    return json.dumps(data, indent=2) if data else ""


def agy_command(level: int) -> str:
    """How to start agy at this level, or "" when it stays as it is."""
    return "agy --mode accept-edits --sandbox" if level >= FREE else ""


def codex_command(level: int) -> str:
    """How to start Codex at this level, or "" when it stays as it is: from ⏳ it works in its sandbox
    (the project, no network) without asking and asks only to step out of it."""
    return "codex --sandbox workspace-write --ask-for-approval on-request" if level >= TIMER else ""


def claude_line(level: int) -> str:
    if not claude_settings(level):
        return "nothing to change — it asks before it acts."
    return f"its permissions for this level → paste into {CLAUDE_FILE} (or {CLAUDE_FILE_ALL})."


def agy_line(level: int) -> str:
    if level < TIMER:
        return "nothing to change — it asks before it acts."
    if level == TIMER:
        return "keeps asking (no per-command allow list known); the Elders advise."
    return f"start it with `{agy_command(level)}` (check `agy --help`)."


def codex_line(level: int) -> str:
    if level < TIMER:
        return "nothing to change — it asks before it acts."
    return f"start it with `{codex_command(level)}`: it works in its sandbox and asks only to leave it."


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
    if "codex" in tools:
        lines.append(f"Codex: {codex_line(level)}")
        if codex_command(level):
            lines.append(f"    {codex_command(level)}")
    if level >= FREE:
        lines.append("The 🏛 Elders answer routine questions for you at once (a one-time yes or no); "
                     "every answer is in .orkcraft/council/elders.jsonl. Move the slider down to stop it.")
    elif answers(level):
        lines.append("The 🏛 Elders answer a routine question for you when it has waited the timer — at once in "
                     "quiet hours (a one-time yes or no); every answer is in .orkcraft/council/elders.jsonl.")
    else:
        lines.append("Orkcraft never presses yes for an agent at this level: the Elders only advise.")
    return "\n".join(lines)
