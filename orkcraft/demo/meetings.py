"""The Meetings orkspace of the dashboard set: a mail that asks to meet becomes an event, and the event
gets a brief from the project's notes before it starts.

    Inbox ──mail──▶ Triage (a Clan Fire that routes) ──new meeting──▶ Calendar (a War Drum)
                                                                      │ prepare   ▲ brief (return road)
                    Notes (a Scroll Dump) ──with the notes──▶ Agents at work (a Barracks) ──brief──▶ Results

The Inbox hears a mail: Alex asks to meet tomorrow about the new project. Triage reads it — a risk
analyst, a tone reader and a productivity pulse that looks at how full the day is — and its steward
decides it is a meeting, when, and what it is called (`ROUTE: meeting`, `TASK:`, `WHEN:`). The cart
reaches the Calendar, which adds the event (realm/daybook.py `find_when`) and, since it prepares new
events at once (`prepare_new`), asks for its brief: `meeting soon` goes to Agents at work. The Barracks
reads its notes first (`notes`): the task goes to Notes, which sends it back with the pages that
matter — the project's goals, its decisions so far, its open questions — and an ork writes the brief.
The brief lands in Results and comes back to the Calendar by a return road, where the event wears it.

The sandbox runs no model: the clan's verdicts and the ork's brief are written beforehand in their
buildings' `simulated.json` (`prepare`). `tools/landing_flow.py --flow meeting` plays it and films it.
"""
from __future__ import annotations

import datetime as dt
import json
from dataclasses import asdict
from pathlib import Path

from orkcraft.demo.seeds import state_dir

ID = "meetings"
POST, TRIAGE, DRUM, NOTES, CAMP, LOOT = "meet_post", "meet_triage", "meet_drum", "meet_notes", "meet_camp", "meet_loot"
CALENDAR_FILE = "MEETINGS.ics"
SOURCES = "project/notes"                 # the notes Notes' wiki is made from
WIKI = "llm-wiki/project"

MAIL = {"source": "mail", "title": "Alex Kim: Can we meet tomorrow to go over the new project?",
        "body": "Hi! Could we meet tomorrow for half an hour to go over the plan for the new project? I'd like to "
                "agree on the first steps and who does what. Any time before lunch works for me. Thanks, Alex"}
EVENT = "New project kickoff with Alex"
WHEN = "tomorrow 11:00, 30 min"
BRIEF_TITLE = "Brief ready: New project kickoff"
BRIEF_LINK = "https://example.com/docs/new-project-brief"


def _typed(bid: str, kind: str, title: str, icon: str, orc: str, role: str, roof: str | None = None, **config) -> dict:
    spec = {"id": bid, "type": kind, "title": title, "icon": icon, "summary": role, "orc": {"name": orc, "role": role}}
    if config:
        spec["config"] = config
    if roof:
        spec["roof"] = roof
    return spec


MEETINGS = {
    "id": ID, "name": "Meetings", "icon": "📅", "biome": "forest", "git": {"enabled": False},
    "segment": "Everyone",
    "story": "A mail that asks to meet becomes an event in the calendar, and the event gets a brief from the "
             "project's notes",
    "nodes": [],
    "files": {},
    "buildings": [
        _typed(POST, "watchtower", "Inbox", "🗼", "Lookout", "my mailbox", "chimney",
               host="gmail", user_env="DEMO_MAIL_USER", password_env="DEMO_MAIL_PASSWORD"),
        _typed(TRIAGE, "council", "Triage", "🪔", "Chieftains", "reads every message, says what it is", "pagoda",
               steward_prompt="Decide what each message is: a meeting to put in the calendar (with its title and "
                              "time, in the first free slot that suits everyone), or a task.",
               members=["Risk analyst:claude", "Tone reader:claude", "Productivity pulse:claude"],
               routes=["meeting", "task"], max_cycles=1, budget_usd=1.0),
        _typed(DRUM, "war_drum", "Calendar", "🥁", "Drummer", "my meetings, each with its brief", "flag",
               ics=CALENDAR_FILE, prepare_new=True, beats=["meeting"]),
        _typed(NOTES, "scrolls", "Notes", "📜", "Scroll Scrapper", "the project's notes, decisions and questions",
               "dome", topic="general", wiki=WIKI, sources=[SOURCES], auto_ingest=False),
        _typed(CAMP, "barracks", "Agents at work", "🏕️", "Grunts", "agents prepare what my meetings need", "tent",
               max_orcs=1, providers=["claude"], worktrees=False, budget_usd=2.0, notes=[NOTES],
               orders="Write a short brief for the meeting from the project's notes: where we are, what is decided, "
                      "what is open, an agenda."),
        _typed(LOOT, "loot", "Results", "📦", "Quartermaster", "what the agents delivered", "snow", path="results"),
    ],
    # The flow reads left to right along the top (the inbox, triage, the calendar), then back along the
    # bottom: the notes feed the agents, whose brief goes to the results — clear of the Town Hall's corner.
    "huts": {POST: (0.0, 0.06), TRIAGE: (0.34, 0.06), DRUM: (0.7, 0.0), NOTES: (0.0, 0.62), CAMP: (0.35, 0.66),
             LOOT: (0.52, 1.0)},
    "layout": [(0.0, 0.0, 0.3, 0.46), (0.35, 0.0, 0.3, 0.46), (0.7, 0.0, 0.3, 0.46), (0.0, 0.54, 0.3, 0.46),
               (0.35, 0.54, 0.3, 0.46), (0.7, 0.54, 0.3, 0.46)],
    "roads": [
        (TRIAGE, POST, "mail.received", "mail", None, None),
        (DRUM, TRIAGE, "team.routed", "new-meeting", None, {"route": ["meeting"]}),
        (CAMP, DRUM, "calendar.event_upcoming", "prepare-a-brief", None, None),
        (CAMP, NOTES, "knowledge.chunks", "with-the-notes", None, None),
        (DRUM, CAMP, "pool.done", "the-brief", None, {"returns": True}),
        (LOOT, CAMP, "pool.done", "brief-ready", None, None),
    ],
    "payloads": {
        (POST, "mail.received"): ("text", MAIL["body"], MAIL["title"]),
        (TRIAGE, "team.routed"): ("text", f"When: {WHEN}\n\n{MAIL['body']}", EVENT),
        (DRUM, "calendar.event_upcoming"): ("text", f"11:00–11:30 {EVENT}", EVENT),
        (NOTES, "knowledge.chunks"): ("text", f"**Task:** {EVENT}", EVENT),
        (CAMP, "pool.done"): ("text", BRIEF_TITLE, EVENT),
    },
}


def _rule(match: str, text: str, seconds: float = 2.2) -> dict:
    return {"match": match, "say": text, "seconds": seconds}


# What the clan says of the mail (realm/team.py `scripted`): it is a meeting, tomorrow at 11:00.
TRIAGE_SCRIPT = {
    "members": {
        "Risk analyst": [_rule("new project", "APPROVE: Low risk: an internal planning meeting.", 3.0)],
        "Tone reader": [_rule("new project", "APPROVE: Friendly; any time before lunch suits Alex.")],
        "Productivity pulse": [_rule("new project", "APPROVE: Tomorrow is full until 11:00; 11:00–11:30 is free.",
                                                    2.6)],
    },
    "steward": [
        _rule("new project", f"DECISION: approve\nROUTE: meeting\nTASK: {EVENT}\nWHEN: {WHEN}\n"
                             "The first free slot before lunch.", 2.6),
    ],
}

BRIEF = f"""{BRIEF_TITLE}

From 3 notes: the goals, the decisions so far, the open questions.

Brief: {BRIEF_LINK}

## Where we are
The new project helps customers book a visit online. The first version is due at the end of November.

## Decided
- Start with the booking page and email reminders; payments come later.
- Mia leads design, Sam leads the build.

## Open
- Who owns customer support at launch?
- Do we need a mobile app in the first version?

## Agenda (30 min)
1. Goals and the November date (5 min)
2. First steps and who does what (15 min)
3. The open questions (10 min)
"""

CAMP_SCRIPT = {"work": [_rule("kickoff", BRIEF, 9.0)]}

# Notes' wiki: the project's pages (what a brief is made from) and a few that are not about it.
WIKI_PAGES = {
    "index.md": "# Index — project notes\n\n- [New project](pages/project/index.md) — goals, decisions, open "
                "questions\n- [Team](pages/team/index.md) — how we work\n",
    "pages/project/index.md": "# New project\n\n- [goals](goals.md)\n- [decisions](decisions.md)\n"
                              "- [open questions](open-questions.md)\n",
    "pages/project/goals.md": "---\nkind: project\nsources: [../../project/notes/kickoff-notes.md]\nupdated: "
                              "2026-10-01\n---\n# New project: goals\n\nThe new project helps customers book a visit "
                              "online. First version: the end of November.\n",
    "pages/project/decisions.md": "---\nkind: project\nsources: [../../project/notes/decisions.md]\nupdated: "
                                  "2026-10-02\n---\n# New project: decisions so far\n\n- The booking page and email "
                                  "reminders first; payments later.\n- Mia leads design, Sam leads the build.\n",
    "pages/project/open-questions.md": "---\nkind: project\nsources: [../../project/notes/questions.md]\nupdated: "
                                       "2026-10-03\n---\n# New project: open questions\n\n- Who owns customer support "
                                       "at launch?\n- A mobile app in the first version?\n",
    "pages/team/index.md": "# Team\n\n- [how we work](how-we-work.md)\n- [holidays](holidays.md)\n",
    "pages/team/how-we-work.md": "---\nkind: team\nsources: [../../project/notes/team.md]\nupdated: 2026-09-20\n"
                                 "---\n# How we work\n\nStand-up at 9:30; reviews on Fridays.\n",
    "pages/team/holidays.md": "---\nkind: team\nsources: [../../project/notes/team.md]\nupdated: 2026-09-20\n---\n"
                              "# Holidays\n\nThe office is closed between Christmas and New Year.\n",
    "log.md": "# Log\n\n## 2026-10-03\nTook in project/notes/*.\n",
}

SOURCE_NOTES = {
    "kickoff-notes.md": "# Kickoff notes\n\nCustomers book a visit online. First version by the end of November.\n",
    "decisions.md": "# Decisions\n\n- 2026-09-30: booking page and email reminders first, payments later.\n"
                    "- 2026-10-02: Mia leads design, Sam leads the build.\n",
    "questions.md": "# Open questions\n\n- Support at launch: who?\n- Mobile app in v1?\n",
    "team.md": "# Team\n\nStand-up 9:30, reviews on Fridays. Office closed between Christmas and New Year.\n",
}


def calendar(now: dt.datetime) -> str:
    """The calendar: one meeting later today (when the day has room for it), and tomorrow busy until
    11:00 and again after lunch — 11:00–11:30 is free."""
    def at(t: dt.datetime) -> str:
        return t.strftime("%Y%m%dT%H%M%S")

    tomorrow = (now + dt.timedelta(days=1)).replace(second=0, microsecond=0)
    events = [("t1", tomorrow.replace(hour=9, minute=30), 15, "Team stand-up"),
              ("t2", tomorrow.replace(hour=10, minute=0), 60, "Design review"),
              ("t3", tomorrow.replace(hour=14, minute=0), 60, "Client call")]
    later = now.replace(second=0, microsecond=0, minute=0) + dt.timedelta(hours=2)
    if later.date() == now.date() and later.hour < 23:
        events.insert(0, ("d1", later, 30, "Budget check-in"))
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//orkcraft//demo//EN"]
    for uid, start, minutes, title in events:
        lines += ["BEGIN:VEVENT", f"UID:{uid}@meetings", f"DTSTART:{at(start)}",
                  f"DTEND:{at(start + dt.timedelta(minutes=minutes))}", f"SUMMARY:{title}", "END:VEVENT"]
    return "\r\n".join(lines + ["END:VCALENDAR"]) + "\r\n"


def seed_files(root: Path, now: dt.datetime) -> None:
    """Before the sandbox's first commit: the calendar, the project's notes and Notes' wiki of them,
    with a manifest that says every note is taken in."""
    from orkcraft.realm import wiki
    from orkcraft.sources import lore
    (root / CALENDAR_FILE).write_text(calendar(now), encoding="utf-8")
    for name, text in SOURCE_NOTES.items():
        (root / SOURCES / name).parent.mkdir(parents=True, exist_ok=True)
        (root / SOURCES / name).write_text(text, encoding="utf-8")
    cfg = next(b["config"] for b in MEETINGS["buildings"] if b["id"] == NOTES)
    wroot = wiki.root_of(root, cfg["wiki"], cfg["topic"])
    wiki.scaffold(wroot, cfg["topic"])
    for rel, text in WIKI_PAGES.items():
        (wroot / rel).parent.mkdir(parents=True, exist_ok=True)
        (wroot / rel).write_text(text, encoding="utf-8")
    lib = lore.Library(lore.from_config(cfg, root))
    lib.scan()
    prints = wiki.Fingerprints(root)
    wiki.save_manifest(wroot, {n.path: prints.of(n) for n in lib.notes()})


def prepare(root: Path, now: dt.datetime) -> None:
    """The orkspace's state: what the Inbox heard before, the scripts of the clan and the ork."""
    from orkcraft.realm import watch

    def ago(minutes: int) -> str:
        return (now - dt.timedelta(minutes=minutes)).isoformat(timespec="seconds")

    signals = [
        watch.Signal(ago(150), "mail", "Lee Park: Photos from Friday", "", "301", read=True),
        watch.Signal(ago(60), "mail", "Billing: Your invoice for September", "Paid automatically.", "302", read=True),
    ]
    sd = state_dir(root, "watchtower", POST)
    sd.mkdir(parents=True, exist_ok=True)
    (sd / "signals.jsonl").write_text("".join(json.dumps(asdict(s)) + "\n" for s in signals), encoding="utf-8")
    (sd / "state.json").write_text(json.dumps({"read": [s.key for s in signals], "last_uid": 302}), encoding="utf-8")
    for kind, bid, script in (("council", TRIAGE, TRIAGE_SCRIPT), ("barracks", CAMP, CAMP_SCRIPT)):
        folder = state_dir(root, kind, bid)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "simulated.json").write_text(json.dumps(script, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
