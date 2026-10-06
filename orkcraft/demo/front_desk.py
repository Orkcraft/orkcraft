"""The Front Desk orkspace of the dashboard set: what comes in is triaged, then done by you or by the orks.

    Watchtower ──mail / slack──▶ Triage (a Clan Fire that routes)
        ├── task for human ──▶ Task Fields: one of your to-dos
        └── task for agent ──▶ Task Fields: a task in To Do ──▶ Barracks (an ork works it)
                                   ▲ started / result (return roads)  │ outcome
                                   └──────────────────────────────────┴──▶ Loot Vault

The Watchtower listens to a mailbox and a Slack channel. Everything it hears goes to Triage, whose
clan — a risk analyst, a tone reader, a priority checker, a deadline finder — gives each message a
short verdict; the steward names who takes it on. A message for the person lands in their to-dos; one
for an agent becomes a task the board sends to the Barracks by itself (`send_new`), and the Barracks'
progress comes back to the card over two return roads: In Progress with the ork, then Done with the
result. The outcome is also kept in the Loot Vault.

The sandbox runs no model: the clan's verdicts and the ork's report are written beforehand in their
buildings' `simulated.json` (`prepare`). `tools/landing_flow.py` plays the flow and films it.
"""
from __future__ import annotations

import datetime as dt
import json
from dataclasses import asdict
from pathlib import Path

from orkcraft.demo.seeds import state_dir

ID = "front_desk"
POST, TRIAGE, BOARD, CAMP, LOOT = "desk_post", "desk_triage", "desk_board", "desk_camp", "desk_loot"
BOARD_FILE = "DESK_TASKS.md"
SLACK = "slack: token=DEMO_SLACK_TOKEN channels=C0TEAM"

# The two messages the film plays (tools/landing_flow.py): one for the person, one for an agent.
MAIL = {"source": "mail", "title": "Dana Reyes: Can we move Thursday's review to next week?",
        "body": "Hi! I'm completely swamped this week and won't have the numbers ready by Thursday. Could we "
                "move the review to Tuesday or Wednesday next week? Sorry for the short notice. — Dana"}
CHAT = {"source": "slack", "title": "Sam in #team: Feedback summary by Friday?",
        "body": "Could someone pull together a short summary of last month's customer feedback and share it with "
                "the team by Friday? Thanks!"}
TICKET = "https://example.com/tickets/142"
SUMMARY_DOC = "https://example.com/docs/feedback-summary-september"


def _typed(bid: str, kind: str, title: str, icon: str, orc: str, role: str, roof: str | None = None, **config) -> dict:
    spec = {"id": bid, "type": kind, "title": title, "icon": icon, "summary": role, "orc": {"name": orc, "role": role}}
    if config:
        spec["config"] = config
    if roof:
        spec["roof"] = roof
    return spec


BOARD_TEXT = ("# Front desk\n\n## To Do\n\n## In Progress\n\n## Done\n- [x] Send the weekly update to the team\n"
              "  sent on Monday, 3 replies\n\n"
              "## My to-dos\n- [ ] Sign the supplier contract\n- [ ] Book a room for the offsite\n"
              "- [x] Approve the October budget\n\n"
              "## Ideas\n- 🟨 A shared calendar for the team\n")

FRONT_DESK = {
    "id": ID, "name": "Front Desk", "icon": "🛎️", "biome": "forest", "git": {"enabled": False},
    "segment": "Everyone",
    "story": "Mail and chat are triaged: what needs you lands in your to-dos, the rest an agent does by itself",
    "nodes": [],
    "files": {BOARD_FILE: BOARD_TEXT},
    "buildings": [
        _typed(POST, "watchtower", "Inbox", "🗼", "Lookout", "my mailbox and the team's Slack", "chimney",
               host="gmail", user_env="DEMO_MAIL_USER", password_env="DEMO_MAIL_PASSWORD", feeds=[SLACK]),
        _typed(TRIAGE, "council", "Triage", "🪔", "Chieftains", "reads every message, says who takes it on", "pagoda",
               steward_prompt="Decide who takes each message on: the person when it needs their judgement, their "
                              "calendar or a personal reply; an agent when it is routine and low risk.",
               members=["Risk analyst:claude", "Tone reader:claude", "Priority checker:claude",
                        "Deadline finder:claude"],
               routes=["human", "agent"], max_cycles=1, budget_usd=1.0),
        _typed(BOARD, "fields", "Tasks", "🌾", "Taskmaster", "my to-dos and the agents' tasks", "tiles",
               path=BOARD_FILE, mine_routes=["human"], send_new=True),
        _typed(CAMP, "barracks", "Agents at work", "🏕️", "Grunts", "agents do the routine tasks", "tent",
               max_orcs=2, providers=["claude"], worktrees=False, budget_usd=2.0,
               orders="Do the task, share the result where it was asked for, and say where it is."),
        _typed(LOOT, "loot", "Results", "📦", "Quartermaster", "what the agents delivered", "snow",
               path="results"),
    ],
    # The flow reads left to right: the inbox, triage, the board; the agents and their results below, clear of the
    # Command Card (bottom right) so a frame can show both.
    "huts": {POST: (0.0, 0.2), TRIAGE: (0.44, 0.2), BOARD: (0.92, 0.0), CAMP: (0.5, 0.74), LOOT: (0.0, 0.74)},
    "layout": [(0.0, 0.0, 0.3, 0.46), (0.35, 0.0, 0.3, 0.46), (0.7, 0.0, 0.3, 0.46), (0.35, 0.54, 0.3, 0.46),
               (0.7, 0.54, 0.3, 0.46)],
    "roads": [
        (TRIAGE, POST, "mail.received", "mail", None, None),
        (TRIAGE, POST, "watch.comment", "slack", None, None),
        (BOARD, TRIAGE, "team.routed", "task-for-human", None, {"route": ["human"]}),
        (BOARD, TRIAGE, "team.routed", "task-for-agent", None, {"route": ["agent"]}),
        (CAMP, BOARD, "tasks.sent", "task", None, None),
        (BOARD, CAMP, "pool.assigned", "started", None, {"returns": True}),
        (BOARD, CAMP, "pool.done", "result", None, {"returns": True}),
        (LOOT, CAMP, "pool.done", "result", None, None),
    ],
    "payloads": {
        (POST, "mail.received"): ("text", MAIL["body"], MAIL["title"]),
        (POST, "watch.comment"): ("text", CHAT["body"], f"slack · {CHAT['title']}"),
        (TRIAGE, "team.routed"): ("text", MAIL["body"], MAIL["title"]),
        (BOARD, "tasks.sent"): ("text", CHAT["body"], CHAT["title"]),
        (CAMP, "pool.assigned"): ("text", f"Grub (claude) ← {CHAT['title']}", CHAT["title"]),
        (CAMP, "pool.done"): ("text", "Feedback summary shared with the team", CHAT["title"]),
    },
}


def _rule(match: str, text: str, seconds: float = 2.2) -> dict:
    return {"match": match, "say": text, "seconds": seconds}


# What the clan says of each message (realm/team.py `scripted`): the mail needs the person, the Slack
# message is routine work for an agent. The first rule that matches the prompt speaks.
TRIAGE_SCRIPT = {
    "members": {
        "Risk analyst": [
            _rule("Thursday's review", "APPROVE: Low risk, but others plan around this meeting.", 3.0),
            _rule("feedback", "APPROVE: Low risk: an internal summary.", 3.0)],
        "Tone reader": [
            _rule("Thursday's review", "APPROVE: Stressed and apologetic: reply kindly."),
            _rule("feedback", "APPROVE: Friendly, a routine request.")],
        "Priority checker": [
            _rule("Thursday's review", "APPROVE: Medium: answer today."),
            _rule("feedback", "APPROVE: Low: nobody is blocked.")],
        "Deadline finder": [
            _rule("Thursday's review", "APPROVE: Before Thursday; Tue or Wed next week."),
            _rule("feedback", "APPROVE: Due Friday.")],
    },
    "steward": [
        _rule("Thursday's review", "DECISION: approve\nROUTE: human\nYour calendar and a personal reply: this one is yours.", 2.6),
        _rule("feedback", "DECISION: approve\nROUTE: agent\nRoutine and low risk: an agent can do it.", 2.6),
    ],
}

CAMP_SCRIPT = {"work": [
    _rule("feedback", "Feedback summary shared with the team in #team.\n\n"
                      f"Ticket created: #142 Feedback summary — {TICKET}\n"
                      f"Summary: {SUMMARY_DOC}\n\n"
                      "42 replies, 78% positive. Most asked for: faster exports. Most heard complaint: onboarding "
                      "takes too long.", 9.0),
]}


def prepare(root: Path, now: dt.datetime) -> None:
    """The desk's state: what the tower heard before, the scripts of the clan and the ork, the board seen."""
    from orkcraft.realm import tasklist, watch

    def ago(minutes: int) -> str:
        return (now - dt.timedelta(minutes=minutes)).isoformat(timespec="seconds")

    signals = [
        watch.Signal(ago(180), "mail", "Lee Park: Lunch on Friday?", "Are you free at 12:30?", "201", read=True),
        watch.Signal(ago(95), "slack", "Ann in #team: the slides are in the shared folder", "",
                     "https://slack.example/d1", read=True),
        watch.Signal(ago(40), "mail", "Billing: Your invoice for September", "Paid automatically.", "202", read=True),
    ]
    sd = state_dir(root, "watchtower", POST)
    sd.mkdir(parents=True, exist_ok=True)
    (sd / "signals.jsonl").write_text("".join(json.dumps(asdict(s)) + "\n" for s in signals), encoding="utf-8")
    (sd / "state.json").write_text(json.dumps({"read": [s.key for s in signals], "last_uid": 202}), encoding="utf-8")
    for kind, bid, script in (("council", TRIAGE, TRIAGE_SCRIPT), ("barracks", CAMP, CAMP_SCRIPT)):
        folder = state_dir(root, kind, bid)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "simulated.json").write_text(json.dumps(script, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    seen = state_dir(root, "fields", BOARD)
    seen.mkdir(parents=True, exist_ok=True)
    cards = tasklist.TaskList(root, BOARD_FILE).load()
    (seen / "seen.json").write_text(json.dumps(sorted(c.id for c in cards)), encoding="utf-8")
