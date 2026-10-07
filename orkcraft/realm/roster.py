"""Clan roster: who is on the map right now and who is waiting for orders (❓)."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from orkcraft.realm.buildings import Building
from orkcraft.realm.orcs import (
    BUILDER, COUNCIL, RESIDENT, WORKER, Alert, Orc, Trigger, clarification_text, detect_prompt,
)
from orkcraft.scroll import OrcSpec
from orkcraft.realm.council import warder_events
from orkcraft.sources.agents import collect_agents

WORKER_NAMES = {"agy": "Grunt", "codex": "Goblin", "hermes": "Runner", "pi": "Kobold", "cursor": "Gremlin"}
# … a War Tent session's ork, by harness (Claude: Peon)
# A CLI that printed nothing for this long while showing a numbered menu is waiting.
PROMPT_IDLE_S = 1.0
COUNCIL_SYSTEM = "watchers"
BUILDERS = (
    ("Mason", "parses the prompt into a building spec (stage 4)"),
    ("Artisan", "proposes layouts for new buildings (stage 4)"),
)


@dataclass
class WorkerInfo:
    """A running Claude / agy session in the War Tent."""
    key: str
    harness: str
    title: str
    ticket: str | None
    lines: list[str]
    idle_s: float
    running: bool


@dataclass
class Roster:
    orcs: list[Orc] = field(default_factory=list)
    alerts: list[Alert] = field(default_factory=list)

    @property
    def active(self) -> int:
        return sum(
            o.status in ("busy", "alert")
            for o in self.orcs
            if o.category == WORKER or (o.category == RESIDENT and bool(o.session))
        )

    @property
    def agents(self) -> list[Orc]:
        """Every ork of the town: the buildings' garrisons (their keepers), the War Tent's sessions
        and the council; the builders are the town's own tools, not agents."""
        return [o for o in self.orcs if o.category != BUILDER]

    @property
    def working(self) -> int:
        """The agents at work right now (busy, or asking while at it)."""
        return sum(o.status in ("busy", "alert") for o in self.agents)

    def by_building(self, building_id: str) -> Orc | None:
        return next((o for o in self.orcs if o.building == building_id and o.lead),
                    next((o for o in self.orcs if o.building == building_id), None))

    def garrison(self, building_id: str) -> list[Orc]:
        members = [o for o in self.orcs if o.building == building_id and o.category == RESIDENT]
        lead_m = [o for o in members if o.lead]
        other_m = [o for o in members if not o.lead]
        return lead_m + other_m


COUNCIL_CACHE_S = 10
_council_cache: dict[str, tuple[float, list[Orc]]] = {}


def _council(repo_root: Path) -> list[Orc]:
    hit = _council_cache.get(str(repo_root))
    if hit and time.monotonic() - hit[0] < COUNCIL_CACHE_S:
        return [Orc(**vars(o)) for o in hit[1]]
    orcs = []
    for a in collect_agents(repo_root):
        if a.system != COUNCIL_SYSTEM:
            continue
        trigger = Trigger("cron", a.schedule) if a.schedule else Trigger()
        status = "busy" if a.busy else ("draft" if a.status == "draft" else "idle")
        orcs.append(Orc(a.orc or a.name.title(), a.description.split(".")[0], COUNCIL, trigger, status,
                        task=a.doing[0] if a.doing else "", ref=f"agent:{a.system}/{a.name}"))
    _council_cache[str(repo_root)] = (time.monotonic(), orcs)
    return [Orc(**vars(o)) for o in orcs]


WARDER = "Warder"


def _warder_watch(repo_root: Path, council: list[Orc], dismissed: set[str]) -> None:
    """Warder is live (the PreToolUse hook): its recent denies / asks become its ❓."""
    warder = next((o for o in council if o.name == WARDER), None)
    if warder is None:
        return
    if warder.status == "draft":
        warder.status = "idle"      # the hook runs regardless of the watcher's draft definition
    events = [e for e in warder_events(repo_root) if e.id not in dismissed]
    if not events:
        return
    latest = events[0]
    warder.task = f"{len(events)} blocked / questioned call(s) in 24 h"
    warder.status = "alert"
    warder.alert = Alert(
        id=latest.id,
        title=f"🛡️ Warder {'blocked' if latest.decision == 'deny' else 'asked about'}: {latest.reason}",
        context=[f"{e.ts[11:16]}  {e.decision:<4} {e.tool}: {e.subject}" for e in events[:10]],
        options=[("1", "Acknowledge (hide this one)"), ("2", "Keep it on the board")],
        source="warder", ref=latest.id,
    )


def _worker(w: WorkerInfo, n: int) -> Orc:
    orc = Orc(f"{WORKER_NAMES.get(w.harness, 'Peon')} #{n}", f"{w.harness} session", WORKER,
              Trigger(), "busy" if w.running else "idle",
              task=(f"{w.ticket} · " if w.ticket else "") + (w.title or w.harness), ref=w.key)
    if w.running and w.idle_s >= PROMPT_IDLE_S:
        prompt = detect_prompt(w.lines)
        if prompt is not None:
            question, options = prompt
            orc.status = "alert"
            orc.alert = Alert(
                id=f"term:{w.key}", title=question or f"{orc.name} asks", context=[l for l in w.lines if l.strip()][-10:],
                options=options, source="terminal", ref=w.key,
            )
    return orc



def build_roster(
    repo_root: Path,
    built: Iterable[tuple],
    workers: Iterable[WorkerInfo],
    dismissed: set[str],
    deployments: dict[str, str] | None = None,
) -> Roster:
    """`built`: (building, members, lead_id[, {orc id: [road labels]}]) for raised buildings.
    `deployments`: terminal key -> "<building_id>/<orc_id>".
    """
    if deployments is None:
        deployments = {}
    dep_by_ref = {ref: key for key, ref in deployments.items()}
    workers = list(workers)  # read twice below: a generator would leave the Warband empty
    worker_by_key = {w.key: w for w in workers}

    roster = Roster()
    ticket_alerts: list[Alert] = []

    for item in built:
        b, members, lead_id = item[:3]
        road_labels: dict[str, list[str]] = item[3] if len(item) > 3 else {}
        lead_m = [m for m in members if m.id == lead_id]
        other_m = [m for m in members if m.id != lead_id]
        ordered_members = lead_m + other_m if lead_m else list(members)
        effective_lead_id = lead_id or (ordered_members[0].id if ordered_members else "")

        for m in ordered_members:
            is_lead = (m.id == effective_lead_id)
            ref = f"{b.id}/{m.id}"
            orc = Orc(
                name=m.name,
                role=m.role or b.role,
                category=RESIDENT,
                trigger=Trigger.from_dict(m.trigger),
                status="idle",
                task=m.orders,
                building=b.id,
                ref=ref,
                lead=is_lead,
                kind=getattr(m, "kind", "agent"),
                harness=list(getattr(m, "harness", []) or []),
                roads=list(road_labels.get(m.id, [])),
                run=dict(m.run_policy) if hasattr(m, "run_policy") else {},
                why=getattr(m, "why", ""),
            )
            spec_status = getattr(m, "status", "idle")
            if spec_status in ("draft", "busy", "frozen"):
                orc.status = spec_status   # draft scripts; a scroll can also mark an orc at work / frozen
            elif spec_status == "alert" and f"spec:{ref}" not in dismissed:
                orc.status = "alert"
                orc.alert = Alert(id=f"spec:{ref}", title=m.orders or f"{m.name} waits for orders",
                                  context=[m.role or b.role], options=[("1", "Acknowledge")], source="warder", ref=ref)
            term_key = dep_by_ref.get(ref)
            if term_key:
                orc.session = term_key
                w = worker_by_key.get(term_key)
                if w is not None:
                    orc.status = "busy" if w.running else "idle"
                    if w.running and w.idle_s >= PROMPT_IDLE_S:
                        prompt = detect_prompt(w.lines)
                        if prompt is not None:
                            question, options = prompt
                            orc.status = "alert"
                            orc.alert = Alert(
                                id=f"term:{w.key}",
                                title=question or f"{orc.name} asks",
                                context=[l for l in w.lines if l.strip()][-10:],
                                options=options,
                                source="terminal",
                                ref=w.key,
                            )


            roster.orcs.append(orc)

    warband_workers = [w for w in workers if w.key not in deployments]
    for n, w in enumerate(warband_workers, 1):
        roster.orcs.append(_worker(w, n))

    council = _council(repo_root)
    _warder_watch(repo_root, council, dismissed)
    roster.orcs += council
    roster.orcs += [Orc(name, role, BUILDER) for name, role in BUILDERS]

    worker_alerts = [o.alert for o in roster.orcs if o.alert and o.category == WORKER]
    deployed_resident_alerts = [
        o.alert for o in roster.orcs
        if o.alert and o.category == RESIDENT and o.session and o.alert.source == "terminal"
    ]
    council_alerts = [o.alert for o in roster.orcs if o.alert and o.category == COUNCIL]
    spec_alerts = [o.alert for o in roster.orcs if o.alert and o.alert.id.startswith("spec:")]
    roster.alerts = worker_alerts + deployed_resident_alerts + council_alerts + spec_alerts + ticket_alerts
    return roster


def worker_infos(terminals: dict, titles: dict[str, tuple[str, str, str | None]]) -> list[WorkerInfo]:
    """From the War Tent's terminals: key → Terminal, titles: key → (harness, title, ticket)."""
    now = time.monotonic()
    out = []
    for key, term in terminals.items():
        harness, title, ticket = titles.get(key, ("claude", "", None))
        out.append(WorkerInfo(key, harness, title, ticket, term.text_lines(), now - term.last_output, term.running))
    return out
