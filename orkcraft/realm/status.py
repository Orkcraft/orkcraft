"""● One status, everywhere (docs/design/ork-console.md §5, §19; cart-waybill.md §4): the same states and marks
wherever an ork or a building is drawn, and every wait with why, until when and how to skip it.

    s = status.OrkStatus("Grunt", status.THINKING, building="Agent pool", cart="Fix the login")
    s.line()                       # "Grunt · Agent pool · thinking · on «Fix the login»"
    s.mark("camp"), s.mark("office")      # "💭" / "Thinking"

    w = status.timer(240, skip=status.Skip("start", "Start now", {"task": "t1"}))
    w.line                         # "starts on its own in 4 min"
    w.as_dict(now)                 # {why, line, until, in_s, skip: {act, label, args}}

Never colour alone: each state has a shape (Camp) and a short word (Office), so either look, and a person who does
not tell colours apart, read the same. Colours are the design system's (`design-system/`), not this module's. The
words are the plain ones: a status is a label, not the camp's voice (CLAUDE.md, Wording). Pure module, no face.
"""
from __future__ import annotations

import datetime as dt
import time
from dataclasses import asdict, dataclass, field

# An ork (§5): state → (Camp mark, Office word, asks for attention: 0 no · 1 softly · 2 yes).
RESTING, THINKING, TOOL, READY, ASKS, ERROR, STOPPED = "resting", "thinking", "tool", "ready", "asks", "error", "stopped"
ORK_STATES: dict[str, tuple[str, str, int]] = {
    RESTING: ("Zz", "Resting", 0),
    THINKING: ("💭", "Thinking", 0),
    TOOL: ("🔧", "Running", 0),
    READY: ("📜", "Done", 1),
    ASKS: ("❓", "Asks", 2),
    ERROR: ("✖", "Error", 2),
    STOPPED: ("■", "Stopped by you", 0),
}
# A building (§5): state → (Camp mark, Office word). A question is the ork's, a stop is the building's.
WORKING, IDLE, BURNING, SMOULDERING = "working", "idle", "burning", "smouldering"
BUILDING_STATES: dict[str, tuple[str, str]] = {
    WORKING: ("⚙", "Working"),
    IDLE: ("·", "Idle"),
    BURNING: ("🔥", "Stopped: question / error"),
    SMOULDERING: ("♨", "Stopped by you"),
}

# Why something waits (§19). Each has its line; a wait with no line here is a bug (§19).
APPROVAL = "approval"      # its plan / draft / new persona waits for the person's yes
ANSWER = "answer"          # its ork asked: waits for the person's answer
TIMER = "timer"            # starts (or is decided) on its own after a while (Autonomy)
AFTER = "after"            # another task first
AREA = "area"              # an older task works on the same files
ORK = "ork"                # its own ork (a follow-up) is busy
SLOT = "slot"              # no free ork slot
HIRING = "hiring"          # an ork is being hired for it
LIMIT = "limit"            # held for a limit's reset, or the budget is spent
STEWARD = "steward"        # the steward sorts or plans it
QUIET = "quiet"            # quiet hours
PAUSED = "paused"          # the person paused the building
QUEUE = "queue"            # next in line, nothing else holds it
WAITS = (APPROVAL, ANSWER, TIMER, AFTER, AREA, ORK, SLOT, HIRING, LIMIT, STEWARD, QUIET, PAUSED, QUEUE)


@dataclass
class Skip:
    """The way past a wait: a building's act (`act` with `args`) under a plain label (Approve, Start now…)."""
    act: str
    label: str
    args: dict = field(default_factory=dict)


@dataclass
class Wait:
    why: str                         # one of WAITS
    line: str                        # what the person reads: "after «Fix the login»"
    until: float | None = None       # epoch seconds when it ends by itself; None: it does not
    skip: Skip | None = None

    def as_dict(self, now: float | None = None) -> dict:
        now = time.time() if now is None else now
        return {"why": self.why, "line": self.line, "until": self.until,
                "in_s": max(round(self.until - now), 0) if self.until is not None else None,
                "skip": asdict(self.skip) if self.skip else None}


def when(seconds: float, now: float | None = None) -> str:
    """"in 4 min" for a short while, "at 14:00" for a longer one (today), "on Oct 15, 08:00" past today."""
    seconds = max(seconds, 0)
    if seconds < 60:
        return "in under a minute"
    if seconds < 3600:
        return f"in {round(seconds / 60)} min"
    now = time.time() if now is None else now
    at = dt.datetime.fromtimestamp(now + seconds)
    today = dt.datetime.fromtimestamp(now).date()
    return f"at {at:%H:%M}" if at.date() == today else f"on {at:%b} {at.day}, {at:%H:%M}"


def timer(seconds: float, what: str = "starts on its own", skip: Skip | None = None, now: float | None = None) -> Wait:
    now = time.time() if now is None else now
    return Wait(TIMER, f"{what} {when(seconds, now)}", now + max(seconds, 0), skip)


def quoted(title: str) -> str:
    return f"«{' '.join((title or '').split())[:80]}»"


@dataclass
class OrkStatus:
    """An ork's one status: who, where, in what state, doing what, on which cart (cart-waybill.md §4)."""
    name: str
    state: str = RESTING
    building: str = ""               # its building's title
    what: str = ""                   # thinking about / the tool it runs ("pytest")
    cart: str = ""                   # the title of what it works on
    cart_id: str = ""
    assumptions: int = 0             # marked on its result (§4)
    wait: Wait | None = None

    def mark(self, look: str = "camp") -> str:
        camp, office, _ = ORK_STATES.get(self.state, ORK_STATES[RESTING])
        if look == "office":
            if self.state == READY and self.assumptions:
                return f"{office} · {self.assumptions} assumption{'' if self.assumptions == 1 else 's'}"
            return office
        return camp + (f" + {self.assumptions}" if self.state == READY and self.assumptions else "")

    @property
    def attention(self) -> int:
        return ORK_STATES.get(self.state, ORK_STATES[RESTING])[2]

    def doing(self) -> str:
        """The state as a few plain words: "running pytest", "asks you", "done · 2 assumptions"."""
        if self.state == TOOL:
            return f"running {self.what}" if self.what else "running a tool"
        if self.state == THINKING:
            return f"thinking: {self.what}" if self.what else "thinking"
        if self.state == ASKS:
            return "asks you"
        if self.state == READY:
            n = self.assumptions
            return "done" + (f" · {n} assumption{'' if n == 1 else 's'}" if n else "")
        return ORK_STATES.get(self.state, ORK_STATES[RESTING])[1].lower()

    def line(self) -> str:
        """"Grunt · Agent pool · running pytest · on «Fix the login»" (§4 of cart-waybill.md), with its wait."""
        parts = [self.name, self.building, self.doing(), f"on {quoted(self.cart)}" if self.cart else ""]
        if self.wait is not None:
            parts.append(self.wait.line)
        return " · ".join(p for p in parts if p)

    def as_dict(self, look: str = "camp", now: float | None = None) -> dict:
        return {"name": self.name, "state": self.state, "mark": self.mark(look), "word": self.mark("office"),
                "attention": self.attention, "building": self.building, "what": self.what, "cart": self.cart,
                "cart_id": self.cart_id, "assumptions": self.assumptions, "doing": self.doing(), "line": self.line(),
                "wait": self.wait.as_dict(now) if self.wait else None}


def building_state(working: bool, asks_blocking: bool = False, error: bool = False, stopped: bool = False) -> str:
    """A building's state (§5): it burns when its flow cannot go on without the person — an ork's question that
    blocks it, or an error; it smoulders when the person stopped it; else it works or idles."""
    if asks_blocking or error:
        return BURNING
    if stopped:
        return SMOULDERING
    return WORKING if working else IDLE
