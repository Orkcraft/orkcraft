"""Orcs (units), their triggers and statuses, and passive ❓ alerts.

Agents never open a modal themselves: an orc that needs the operator gets status
`alert` (❓) with an `Alert` attached; the modal opens only on an explicit click
or hotkey.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

TRIGGERS = {"on_demand": ("🔨", "On Demand"), "cron": ("🕒", "Cron"), "webhook": ("⚡", "Webhook")}
# An orc waiting for orders sets its building on fire: the RTS cue that something on the
# map needs you. The question itself, in its modal, keeps ❓.
ALERT_ICON = "🔥"
STATUS_ICONS = {"idle": "💤", "busy": "⚙", "alert": ALERT_ICON, "frozen": "🧊", "draft": "📜"}

COUNCIL = "council"
BUILDER = "builder"
RESIDENT = "resident"
WORKER = "worker"

_OPTION = re.compile(
    r"^\s*(?:[❯>›▶→\-*•]\s*)?(?:\[(\d+)\]|\((\d+)\)|(\d+)(?:[.)]|(?:\s*[:-])))\s+(.+?)\s*$"
)
_YES_NO = re.compile(
    r"^(.*?)(?:\[([yY]/[nN]|[nN]/[yY])\]|\(([yY]/[nN]|[nN]/[yY])\)|\(([yY]es/[nN]o)\))\s*:?\s*$"
)
PROMPT_SCAN_LINES = 18


@dataclass
class Trigger:
    type: str = "on_demand"   # on_demand | cron | webhook
    expression: str = ""      # cron expression or webhook path

    @property
    def icon(self) -> str:
        return TRIGGERS.get(self.type, ("🔨", ""))[0]

    @property
    def label(self) -> str:
        icon, name = TRIGGERS.get(self.type, ("🔨", self.type))
        return f"{icon} {name}" + (f" {self.expression}" if self.expression else "")

    def to_dict(self) -> dict:
        return {"type": self.type, "expression": self.expression}

    @classmethod
    def from_dict(cls, data: object) -> Trigger:
        if not isinstance(data, dict):
            return cls()
        t = str(data.get("type") or "on_demand")
        return cls(t if t in TRIGGERS else "on_demand", str(data.get("expression") or ""))


@dataclass
class Alert:
    """Why an orc needs the operator, with numbered quick answers."""
    id: str
    title: str
    context: list[str] = field(default_factory=list)
    options: list[tuple[str, str]] = field(default_factory=list)  # (key, label)
    source: str = "terminal"   # terminal | ticket
    ref: str = ""              # terminal key or node id


@dataclass
class Orc:
    name: str
    role: str
    category: str
    trigger: Trigger = field(default_factory=Trigger)
    status: str = "idle"
    task: str = ""
    building: str | None = None   # building id for residents
    alert: Alert | None = None
    ref: str = ""                 # terminal key (workers), agent key (council), "<building_id>/<orc_id>" (residents)
    lead: bool = False            # the building's steward (v3) / lead (v2)
    session: str = ""             # War Tent terminal key when deployed
    kind: str = "agent"           # chain | script | agent | hybrid
    harness: list[dict] = field(default_factory=list)
    roads: list[str] = field(default_factory=list)   # labels of the incoming roads it works on
    run: dict = field(default_factory=dict)           # effective re-run policy
    why: str = ""

    @property
    def status_icon(self) -> str:
        return STATUS_ICONS.get(self.status, "·")

    @property
    def icon(self) -> str:
        from orkcraft.realm.looks import kind_icon
        return kind_icon(self.kind)

    @property
    def scheme(self) -> str:
        """Harness letters, e.g. `C` or `A→C` (empty for chains, scripts and orcs without one)."""
        from orkcraft.realm.looks import scheme_plain
        return scheme_plain(self.harness, self.kind)

    @property
    def badge(self) -> str:
        """Unit Frame text: `🧌 Name C 🔨 💤`."""
        scheme = f" {self.scheme}" if self.scheme else ""
        return f"{self.icon} {self.name}{scheme} {self.trigger.icon} {self.status_icon}"


def garrison_badge(orcs: list[Orc]) -> str:
    """Window frame text: `🧌 Smith+2 🔨 🔥`."""
    if not orcs:
        return ""
    lead = next((o for o in orcs if o.lead), orcs[0])
    others = len(orcs) - 1
    plus = f"+{others}" if others > 0 else ""
    if any(o.status == "alert" for o in orcs):
        status_icon = ALERT_ICON
    elif any(o.status == "busy" for o in orcs):
        status_icon = "⚙"
    else:
        status_icon = lead.status_icon
    scheme = f" {lead.scheme}" if lead.scheme else ""
    return f"{lead.icon} {lead.name}{plus}{scheme} {lead.trigger.icon} {status_icon}"


def detect_prompt(lines: list[str]) -> tuple[str, list[tuple[str, str]]] | None:
    """A numbered menu or yes/no confirmation prompt at the bottom of a terminal screen.

    Returns (question, [(key, label), …]) when the last lines hold:
    1. options numbered 1, 2, … in order (question is nearest line above them), or
    2. a yes/no confirmation prompt like [y/N], (y/n), etc.
    """
    tail = [l for l in lines if l.strip()][-PROMPT_SCAN_LINES:]
    if not tail:
        return None

    # Check for numbered menu first
    for start in range(len(tail)):
        opts: list[tuple[str, str]] = []
        for line in tail[start:]:  # the menu must begin exactly at `start`
            m = _OPTION.match(line)
            if not m:
                break
            num_str = m.group(1) or m.group(2) or m.group(3)
            if not num_str or int(num_str) != len(opts) + 1:
                break
            opts.append((num_str, m.group(4).strip()))
        if len(opts) >= 2:
            above = [l.strip() for l in tail[:start] if l.strip()]
            question = next((l for l in reversed(above) if "?" in l), above[-1] if above else "")
            return question.strip("│ ╭╮╰╯─"), opts

    # Check for yes/no confirmation prompt at the bottom
    last_line = tail[-1].strip("│ ╭╮╰╯─ ")
    m_yn = _YES_NO.search(last_line)
    if m_yn:
        q_prefix = m_yn.group(1).strip()
        above = [l.strip("│ ╭╮╰╯─ ") for l in tail[:-1] if l.strip()]
        if q_prefix:
            question = q_prefix
        elif above:
            question = next((l for l in reversed(above) if "?" in l), above[-1])
        else:
            question = "Confirm action"
        return question.strip("│ ╭╮╰╯─:? ") + "?", [("y", "Yes"), ("n", "No")]

    return None


def clarification_text(body: str) -> str:
    """Open questions of a ticket (`## Clarification Needed` without comments)."""
    m = re.search(r"^##\s+Clarification Needed\s*$", body, re.MULTILINE)
    if not m:
        return ""
    rest = body[m.end():]
    nxt = re.search(r"^##\s", rest, re.MULTILINE)
    text = rest[: nxt.start()] if nxt else rest
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    return text.strip()
