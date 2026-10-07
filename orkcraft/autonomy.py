"""How much the orks do on their own — the town's level and a building's own, one rule for both
(design: docs/design/barracks-planning.md §2, the onboarding step).

    LEVELS[level]                     0 ⛓️ in chains · 1 🕰 on the clock · 2 ⛓️‍💥 unchained
    rules_of(b, level, wait, rebuild) what rules a building: its own level and waits, else the town's
    waits(level, quiet, minutes)      how long a QUESTION waits for the operator before the orks take it:
                                      None never (chains), 0 at once, else minutes
    rebuilds(level, cheaper, awake_h, hours)   may the orks apply a REBUILD (a change of a building or
                                      the town) the operator left unanswered for `awake_h` awake hours
    answers(level)                    the orks (the Elders, the stewards) may decide themselves at all
    of(value)                         a stored value → a level: the words, `timer` and the old 0..3 numbers
    claude_snippet(level)             what to paste into Claude Code's settings for this level (📋)
    agy_command(level)                how to start agy for this level (📋)
    codex_command(level)              how to start Codex for this level (📋)

Two kinds of decision the orks could take for the operator, each with its own wait:

- **a question** — an agent's question (the Elders, realm/elders.py), a steward's (a Barracks: what to
  do with a task, a task sent back too often), a new persona. It holds work up now, so it waits
  minutes (`question wait`, 7 by default); in quiet hours nobody is there to answer, so it does not wait.
- **a rebuild** — a change of a building or of the town that a retro or a steward proposes
  (realm/evolution.py). It holds nothing up, so it waits hours (`rebuild wait`, 12 by default) — hours
  the operator is around: the camp open, outside quiet hours (realm/awake.py); a night asleep does not
  count. It is applied in the next quiet hours.

    ⛓️ in chains      it waits for the operator. The Elders only advise, in quiet hours; `a` follows it.
    🕰 on the clock   after its wait the orks decide. Silence never makes the camp spend more: of the
                      rebuilds only what makes a building cheaper or simpler.
    ⛓️‍💥 unchained     the orks decide at once; the operator sees the list afterwards.

The town's level and waits are the machine's (settings.py); a building may have its own (its steward's
window), else it follows the town's. At every level: what the Warder's rules block waits for the
operator, only a one-time yes is sent (never "always"), a draft to post outside waits for the operator,
a removal is never the orks', and every change has the Council, a checkpoint and probation. The agents'
own permission settings (what Claude Code, agy and Codex do without asking) follow the level too — the
operator sets them with the guide below; the 🛡 Warder hook still denies the dangerous commands whatever
they allow.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

CHAINS, CLOCK, FREE = 0, 1, 2
WORDS = ("chains", "clock", "free")
ICONS = {"chains": "⛓️", "clock": "🕰", "free": "⛓️‍💥"}
TITLES = {"chains": "In chains", "clock": "On the clock", "free": "Unchained"}
DEFAULT_LEVEL = CLOCK
# Older names, never bolder than they were: ask me and morning advice wait, routine has the clock.
OLD_WORDS = {"timer": CLOCK}
OLD_NUMBERS = {0: CHAINS, 1: CHAINS, 2: CLOCK, 3: FREE}
DEFAULT_WAIT, MIN_WAIT, MAX_WAIT = 7, 1, 60              # a question: minutes
DEFAULT_REBUILD, MIN_REBUILD, MAX_REBUILD = 12, 1, 48    # a rebuild: hours the operator is around
QUESTION_WAITS = (5, 7, 15, 30)                          # what the screens offer
REBUILD_WAITS = (6, 12, 24)


@dataclass(frozen=True)
class Level:
    n: int
    icon: str
    title: str
    questions: str       # what happens to the questions: the agents', the stewards', new personas
    improves: str        # what happens to the rebuilds (realm/evolution.py)


LEVELS: tuple[Level, ...] = (
    Level(CHAINS, ICONS["chains"], TITLES["chains"],
          "every decision waits for you; in quiet hours the 🏛 Elders leave advice, `a` follows it.",
          "proposals wait for your click."),
    Level(CLOCK, ICONS["clock"], TITLES["clock"],
          "a question waits for you a few minutes, then the orks decide; in quiet hours they do not wait.",
          "a change you leave unanswered for the hours you are around is applied in the next quiet hours — "
          "only what makes a building cheaper or simpler: a shorter prompt, an agent made a chain, a run "
          "policy, a road filter."),
    Level(FREE, ICONS["free"], TITLES["free"],
          "the orks decide at once; you see the list of what they did.",
          "applied in the next quiet hours, also a script instead of an agent, a richer prompt for a ⚖️ / 💎 "
          "building, a new plain road, a setting, a building from the catalog. Never a removal."),
)

# What every self-applied change goes through, shown under the levels that apply changes.
SAFEGUARDS = ("the Council's review, a checkpoint each (Z takes it back), 24 h on probation — a 👎 or more "
              "failed runs take it back by itself — and the list of changes after quiet hours.")


@dataclass(frozen=True)
class Rules:
    """What rules one building (or the town): its level and its two waits."""
    level: int
    wait: int            # a question: minutes
    rebuild: int         # a rebuild: hours the operator is around


def of(value: object) -> int:
    """A stored value → a level: "chains" / "clock" / "free" (or "timer"), an old number 0..3, else the default."""
    if isinstance(value, str) and value in WORDS:
        return WORDS.index(value)
    if isinstance(value, str) and value in OLD_WORDS:
        return OLD_WORDS[value]
    if isinstance(value, int) and not isinstance(value, bool) and value in OLD_NUMBERS:
        return OLD_NUMBERS[value]
    return DEFAULT_LEVEL


def word(level: int) -> str:
    return WORDS[max(0, min(len(WORDS) - 1, level))]


def _clamp(value: object, low: int, high: int, default: int) -> int:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return int(max(low, min(high, value)))
    return default


def wait_of(value: object) -> int:
    """A question's wait in minutes, within MIN_WAIT..MAX_WAIT."""
    return _clamp(value, MIN_WAIT, MAX_WAIT, DEFAULT_WAIT)


def rebuild_of(value: object) -> int:
    """A rebuild's wait in hours, within MIN_REBUILD..MAX_REBUILD."""
    return _clamp(value, MIN_REBUILD, MAX_REBUILD, DEFAULT_REBUILD)


def rules_of(b: object, level: int, wait: int = DEFAULT_WAIT, rebuild: int = DEFAULT_REBUILD) -> Rules:
    """A building's own level and waits (`autonomy`, `question_wait`, `rebuild_wait` of its spec), each one
    it has not set the town's (`level`, `wait`, `rebuild`)."""
    own = getattr(b, "autonomy", None)
    q, r = getattr(b, "question_wait", None), getattr(b, "rebuild_wait", None)
    return Rules(of(own) if own else level, wait_of(q) if q else wait, rebuild_of(r) if r else rebuild)


def waits(level: int, quiet: bool, minutes: int = DEFAULT_WAIT) -> float | None:
    """How many minutes a question waits for the operator before the orks take it; None: it waits for
    the operator, however long. In quiet hours nobody is there, so 🕰 does not wait."""
    if level <= CHAINS:
        return None
    if level >= FREE or quiet:
        return 0
    return float(minutes)


def rebuilds(level: int, cheaper: bool, awake_hours: float, hours: int = DEFAULT_REBUILD) -> bool:
    """May the orks apply a rebuild the operator has left unanswered for `awake_hours` hours they were
    around: never in chains; unchained at once; on the clock only a `cheaper` one, after `hours`."""
    if level <= CHAINS:
        return False
    if level >= FREE:
        return True
    return cheaper and awake_hours >= hours


def answers(level: int) -> bool:
    """May the orks decide anything for the operator at all (after the wait)?"""
    return level >= CLOCK


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
    if level < CLOCK:
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
    """How to start Codex at this level, or "" when it stays as it is: from 🕰 it works in its sandbox
    (the project, no network) without asking and asks only to step out of it."""
    return "codex --sandbox workspace-write --ask-for-approval on-request" if level >= CLOCK else ""


def claude_line(level: int) -> str:
    if not claude_settings(level):
        return "nothing to change — it asks before it acts."
    return f"its permissions for this level → paste into {CLAUDE_FILE} (or {CLAUDE_FILE_ALL})."


def agy_line(level: int) -> str:
    if level < CLOCK:
        return "nothing to change — it asks before it acts."
    if level == CLOCK:
        return "keeps asking (no per-command allow list known); the Elders advise."
    return f"start it with `{agy_command(level)}` (check `agy --help`)."


def codex_line(level: int) -> str:
    if level < CLOCK:
        return "nothing to change — it asks before it acts."
    return f"start it with `{codex_command(level)}`: it works in its sandbox and asks only to leave it."


def hermes_command(level: int) -> str:
    """Hermes asks only before a dangerous command (its approvals); ⛓️‍💥 starts it without asking."""
    return "hermes --yolo" if level >= FREE else ""


def hermes_line(level: int) -> str:
    if level < CLOCK:
        return "nothing to change — it asks before a dangerous command (approvals.mode: manual asks before every one)."
    if level == CLOCK:
        return "keep `approvals.mode: smart` in ~/.hermes/config.yaml: it asks only before a dangerous command."
    return f"start it with `{hermes_command(level)}`: it runs every command without asking; the Warder still stops the worst."


def pi_line(level: int) -> str:
    return ("it never asks before it acts, at any level: the Warder (orkcraft's pi extension) is its only guard; "
            "give it fewer tools with `--tools read,grep,find,ls` to keep it reading.")


def cursor_command(level: int) -> str:
    return "cursor-agent --force --sandbox enabled" if level >= FREE else ""


def cursor_line(level: int) -> str:
    if level < CLOCK:
        return "nothing to change — it asks before it acts."
    if level == CLOCK:
        return "allow routine commands in .cursor/cli.json `permissions.allow` (e.g. Shell(git), Shell(npm test)); deny wins."
    return f"start it with `{cursor_command(level)}`: commands run without asking, inside its sandbox."


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
    if "hermes" in tools:
        lines.append(f"Hermes Agent: {hermes_line(level)}")
    if "pi" in tools:
        lines.append(f"pi: {pi_line(level)}")
    if "cursor" in tools:
        lines.append(f"Cursor: {cursor_line(level)}")
    if level >= FREE:
        lines.append("The 🏛 Elders answer routine questions for you at once (a one-time yes or no); "
                     "every answer is in .orkcraft/council/elders.jsonl. Move the slider down to stop it.")
    elif answers(level):
        lines.append("The 🏛 Elders answer a routine question for you when it has waited its minutes — at once in "
                     "quiet hours (a one-time yes or no); every answer is in .orkcraft/council/elders.jsonl.")
    else:
        lines.append("Orkcraft never presses yes for an agent at this level: the Elders only advise.")
    return "\n".join(lines)
