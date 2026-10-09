"""The Agent pool's paths by the kind of work (docs/design/barracks-flows.md §5–7): what the pool takes, its
table *source → kind of work*, the `reply` path's prompt, and the look that tells a reply which is really
a code task.

    paths.wants_of({"wants": ["change", "reply"]})          == ("change", "reply")
    paths.table_of({"want_by_source": {"inbox": "reply"}})  == {"war_drum": "doc", "inbox": "reply"}
    paths.looks_like_code("Traceback (most recent call last): …")   → True

The text of a task may lower its path (a `change` that only asks a question runs as a trivial answer), never
raise it: nothing here reads a kind of work out of a message.

Pure module, no face.
"""
from __future__ import annotations

import re

from orkcraft.realm import pipes

# What a pool takes when its setting says nothing (§10): `routine` belongs to a Workshop, `know` to a Wiki.
DEFAULT_WANTS = (pipes.CHANGE, pipes.REPLY, pipes.DOC)
# Its table *source → kind of work* when its setting says nothing (§5 step 2), by building type (or id):
# the Calendar asks for a brief. The External listeners name a kind per source on the cart itself.
DEFAULT_BY_SOURCE = {"war_drum": pipes.DOC}
# Who decided the kind when no building named it on the cart (`PoolTask.want_by`): the pool's table, its sort.
TABLE, SORT = "@table", "@sort"


def wants_of(config: dict) -> tuple[str, ...]:
    """The kinds of work a pool takes (its `wants`), in the order of WANTS; the default when it names none."""
    got = config.get("wants")
    if not isinstance(got, (list, tuple)):
        return DEFAULT_WANTS
    named = {pipes.want_of(w) for w in got} - {""}
    return tuple(w for w in pipes.WANTS if w in named)


def table_of(config: dict) -> dict[str, str]:
    """Its table *source → kind of work*: the defaults under its own `want_by_source` (a building id or a
    type id → a kind; "" or an unknown word takes a default out)."""
    table = dict(DEFAULT_BY_SOURCE)
    got = config.get("want_by_source")
    for key, want in (got.items() if isinstance(got, dict) else ()):
        key = str(key).strip()
        if not key:
            continue
        if pipes.want_of(want):
            table[key] = pipes.want_of(want)
        else:
            table.pop(key, None)
    return table


def by_source(table: dict[str, str], source: str, source_type: str = "") -> str:
    """The table's kind for a cart from `source` (its id first, then its type); "" when it names none."""
    return table.get(source) or (table.get(source_type) if source_type else "") or ""


# -- the External listeners name a kind per source (§4) -------------------------------------------------

# What the quick-add offers for a source's carts (§9) and what it picks first, by service: a code tracker's work
# is a code change, a message wants a reply; a design or a wiki page has no kind (the pool's sort decides).
SOURCE_CHOICES = (pipes.CHANGE, pipes.REPLY, pipes.KNOW)
SOURCE_DEFAULTS = {"github": pipes.CHANGE, "gitlab": pipes.CHANGE, "jira": pipes.CHANGE,
                   "mail": pipes.REPLY, "gmail": pipes.REPLY, "slack": pipes.REPLY,
                   "discord": pipes.REPLY}


# A chat where people also ask for fixes may take both: a reply, or a code change when the message asks for one —
# the Lookout picks within the two (§6.1). Kept as the list `["reply", "change"]`, the reply first.
REPLY_OR_CHANGE = "reply+change"
BOTH_KINDS = {REPLY_OR_CHANGE: [pipes.REPLY, pipes.CHANGE]}
CHAT_SOURCES = ("slack", "discord")


def source_choices(source: str) -> tuple[str, ...]:
    """What the quick-add offers for `source`'s carts: the single kinds, and for a chat the reply-or-change too."""
    return SOURCE_CHOICES + ((REPLY_OR_CHANGE,) if source in CHAT_SOURCES else ())


def want_setting(choice: str) -> str | list[str]:
    """A quick-add choice as the tower's `wants` keeps it: a kind, or a list of kinds."""
    return list(BOTH_KINDS[choice]) if choice in BOTH_KINDS else choice


def choice_of_setting(value) -> str:
    """A source's `wants` value as the quick-add's choice ("" when it is none it offers)."""
    if isinstance(value, list):
        return next((c for c, kinds in BOTH_KINDS.items() if [pipes.want_of(x) for x in value] == kinds), "")
    return want_of_choice(value)


def source_of(service: str) -> str:
    """The signal source a quick-add service listens as: `gmail` is the tower's mail."""
    return "mail" if service == "gmail" else service


def want_of_choice(value) -> str:
    """One of SOURCE_CHOICES or REPLY_OR_CHANGE, else "" (none: the pool's sort decides)."""
    if str(value or "").strip().lower() in BOTH_KINDS:
        return str(value).strip().lower()
    want = pipes.want_of(value)
    return want if want in SOURCE_CHOICES else ""


def source_want(config: dict, source: str) -> str:
    """The kind of work a tower's carts from `source` ask for: its setting `wants` (source → kind), set in the
    quick-add or by an intent; "" when it names none (a tower set up before asks for none, as before)."""
    kinds = source_wants(config, source)
    return kinds[0] if kinds else ""


def source_wants(config: dict, source: str) -> tuple[str, ...]:
    """The kinds of work `source` allows, its default first: `wants` maps a source to one kind, or to a list
    the Lookout may choose from by the text (§6.1: `["reply", "change"]` — a reply unless it reads as a code
    change). Never more than the person listed."""
    got = config.get("wants")
    value = got.get(source) if isinstance(got, dict) else None
    words = value if isinstance(value, list) else [value]
    return tuple(dict.fromkeys(w for w in (pipes.want_of(x) for x in words) if w))


# -- the reply path -------------------------------------------------------------------------------------

# A message that is really a code task: a stack trace, a link into a repository, an ask to fix or merge.
_CODE = re.compile(
    r"Traceback \(most recent call last\)"
    r"|^\s+at [\w$.<>]+\(.*:\d+\)"                                  # a Java / JS stack frame
    r"|^\s*File \"[^\"]+\", line \d+"                               # a Python frame
    r"|\b(?:github|gitlab|bitbucket)\.(?:com|org)/[\w.-]+/[\w.-]+/(?:pull|merge_requests|issues|blob|tree|commit)\b"
    r"|\b(?:please|pls|can you|could you)\s+(?:fix|patch|refactor|merge|deploy|revert)\b"
    r"|\b(?:fix|patch) (?:the|this|a) (?:bug|crash|error|test|build)\b"
    r"|^```",
    re.I | re.M)


def looks_like_code(text: str) -> bool:
    """The message reads like a code task (§5): it is never run as a code change for that — the steward puts
    a card on the Task board for the person to decide."""
    return bool(_CODE.search(text or ""))


REPLY_RULES = (
    "Write the reply only: the text that would be sent, in the language of the message, polite and plain. "
    "Never promise a date, a price, money or anything else the person did not already commit to; never say "
    "anything private about other people. If a fact is not in the message, its thread or the notes below, do "
    "not make it up: say it will be checked. You have no terminal and change no files; nothing you write goes "
    "out before the person approves it.")


def reply_prompt(orc: str, keeper: str, orders: str, title: str, body: str) -> str:
    """What the reply's ork is told: the message and what it may do (harness mode `read`, §7)."""
    return "\n\n".join(p for p in [
        f"You are {orc}, an agent of an agent pool. Draft a reply to the message below; {keeper}, the steward, "
        "and then the person read it before anything is sent.",
        f"## {keeper}'s rules\n\n{orders}" if orders.strip() else "",
        f"## The message: {title}", body.strip(),
        REPLY_RULES] if p)


def draft_of(text: str) -> str:
    """The reply an ork wrote: what is under a `PUBLISH:` line when it wrote one, else its whole answer."""
    m = re.search(r"^\s*\**\s*PUBLISH\b\**\s*:.*$", text or "", re.I | re.M)
    return (text[m.end():] if m else text or "").strip()
