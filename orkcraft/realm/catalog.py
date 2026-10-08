"""Building types: what a building is, how big its hut is, what it shows, what it can do
from the map and what it sends along roads.

A type is code (a view and the events it raises); a building is data — a spec that names its type,
picks a size, up to two quick actions and the events it sends, and fills the type's config. The
build wizard and the AI only choose from here: an event or an action a type does not declare can
never be raised, so a road can never wait for something nothing sends.

Every building also sends the two generic events of old: a selection (`on_selection_change`) and,
with a garrison, a finished task (`on_task_completed`).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from orkcraft.realm import harnesses

# -- sizes ------------------------------------------------------------------------------------------
# Hut sizes in terminal cells (a cell is about twice as tall as it is wide). The full view opens big,
# like every building; the hut is the preview on the map.
SIZES: dict[str, tuple[int, int]] = {"XS": (10, 5), "S": (14, 7), "M": (18, 9), "L": (26, 11)}
SIZE_ORDER = ("XS", "S", "M", "L")

# Payload kinds an event carries (pipes.Payload.kind).
TEXT, FILE, NODE = "text", "file", "node"

EVENT_ID = re.compile(r"^[a-z]+\.[a-z_]+$")


@dataclass(frozen=True)
class EventDef:
    id: str            # "mail.received"
    label: str         # shown on roads and in the wizard
    kind: str          # payload kind: text | file | node
    help: str          # one line for the wizard and the AI


@dataclass(frozen=True)
class ActionDef:
    id: str            # "tasks.new"
    label: str         # "New task"
    glyph: str         # what the hut button shows: "+", "▶", "✓"
    help: str


# config key → (python type, allowed values | (min, max) | None, required)
Param = tuple[type, Any, bool]


@dataclass(frozen=True)
class BuildingType:
    id: str
    title: str
    icon: str
    size: str                       # default hut size
    summary: str                    # what it is, for the wizard and the AI
    preview: str                    # what the hut shows
    full: str                       # what the open building shows
    events: tuple[EventDef, ...] = ()
    actions: tuple[ActionDef, ...] = ()
    config: dict[str, Param] = field(default_factory=dict)
    art: str = "workshop"           # hut art piece (realm/huts.py)
    orc: str = "Peon"               # default resident orc
    agentic: bool = False           # its work is done by agents (the Agents group of the wizard)
    folded: bool = False            # built with its hut folded to the title bar (docs/design/folded-cards.md)

    def event(self, event_id: str) -> EventDef | None:
        return next((e for e in self.events if e.id == event_id), None)

    def action(self, action_id: str) -> ActionDef | None:
        return next((a for a in self.actions if a.id == action_id), None)


def _e(id_: str, label: str, kind: str, help_: str) -> EventDef:
    return EventDef(id_, label, kind, help_)


def _a(id_: str, label: str, glyph: str, help_: str) -> ActionDef:
    return ActionDef(id_, label, glyph, help_)


TYPES: dict[str, BuildingType] = {t.id: t for t in (
    # -- 1. intake and routing -------------------------------------------------------------------------
    BuildingType(
        "pit", "The Pit", "🕳️", "XS",
        "intake without dialogs: drop files, paste links or text; the Scavenger sorts what came and sends it on",
        "the last thing dropped", "everything dropped, with its kind",
        events=(_e("drop.file", "file dropped", FILE, "a file was dropped: its path"),
                _e("pit.link", "link pasted", TEXT, "a link was pasted"),
                _e("pit.text", "text pasted", TEXT, "text was pasted")),
        actions=(_a("pit.paste", "Paste", "📋", "take what is in the clipboard"),),
        art="burrow", orc="Scavenger", folded=True),
    BuildingType(
        "watchtower", "Watchtower", "🗼", "M",
        "listens to the outside: a mailbox (IMAP, Gmail), GitHub events, comments and mentions in Slack, Jira, "
        "Confluence and Figma, a schedule, webhooks; an intent lets through only what you are after",
        "what is new per source", "the signals that came in, new ones marked; Enter reads one",
        events=(_e("mail.received", "new mail", TEXT, "a new message arrived: sender, subject, first lines"),
                _e("watch.github", "GitHub event", TEXT, "a GitHub event: PR, issue, release, check"),
                _e("watch.cron", "schedule", TEXT, "the schedule fired"),
                _e("watch.webhook", "webhook", TEXT, "a webhook arrived on localhost: its body"),
                _e("watch.comment", "comment", TEXT, "a new comment or message in Slack, Jira, Confluence or Figma"),
                _e("watch.mention", "mention", TEXT, "you were mentioned or written to: Slack, Jira, Confluence, Figma"),
                _e("watch.place", "place", TEXT, "a paired phone came to a place or left it: what the road was made for, "
                   "never the place or the time")),
        actions=(_a("mail.open_new", "Open new", "✉", "open the newest new signal"),
                 _a("watch.read_all", "Read all", "✓", "mark every signal read"),
                 _a("mail.refresh", "Check now", "↻", "check every source now")),
        config={"host": (str, None, False), "user": (str, None, False), "user_env": (str, None, False), "password_env": (str, None, False),
                "folder": (str, None, False), "port": (int, (1, 65535), False),
                "github": (str, None, False), "cron": (str, None, False),
                "webhook_port": (int, (1024, 65535), False), "webhook_secret_env": (str, None, False),
                "feeds": (list, None, False), "intent": (str, None, False), "wants": (dict, None, False),
                "places": (list, None, False), "places_keep_days": (int, (1, 365), False)},
        art="watchtower", orc="Lookout"),
    BuildingType(
        "signpost", "Signpost", "🚏", "S",
        "a crossroads post: rules (if / switch) send what arrives down one of its roads, no model",
        "the last route taken, how many routes", "the rules and what went where",
        events=(_e("signpost.routed", "routed", TEXT, "what arrived, sent down the route its rule picked"),
                _e("signpost.unmatched", "no rule", TEXT, "no rule matched what arrived")),
        config={"rules": (list, None, False)},
        art="spire", orc="Grot Pointa", folded=True),
    BuildingType(
        "mill", "The Mill", "⚙️", "XS",
        "changes what arrives, step by step (a map; a flat map when the result is records): regexes, "
        "CSV → JSON, numbers and dates, templates, a script — and an agent for what a script cannot do",
        "its steps, the last run, the queue", "the steps, what went in and what came out",
        events=(_e("mill.done", "milled", TEXT, "the changed result, one per cart in"),
                _e("mill.item", "each record", TEXT, "a flat map: one cart per record of the result (a JSON object)"),
                _e("mill.failed", "mill failed", TEXT, "a step failed: the error")),
        actions=(_a("mill.run", "Run", "▶", "run the steps on the last input"),),
        config={"steps": (list, None, False), "env": (list, None, False), "model": (str, None, False)},
        art="mill", orc="Miller", folded=True),
    BuildingType(
        "horn", "The Horn", "📯", "XS",
        "sound for what comes in: every cart down its roads plays a sound — you pick which sound for which event "
        "(built-in, the terminal bell or an audio file); mute, quiet hours, a cooldown",
        "the last sound it played, or muted", "each incoming event with its sound; the calls that sounded",
        events=(_e("horn.sounded", "sounded", TEXT, "a cart was announced: the sound and what came"),),
        actions=(_a("horn.test", "Test", "🔊", "play the sound of everything else"),
                 _a("horn.mute", "Mute", "🔇", "mute or unmute the horn")),
        config={"sounds": (list, None, False), "default": (str, None, False), "muted": (bool, None, False),
                "quiet": (str, None, False), "cooldown": (int, (0, 600), False)},
        art="watchtower", orc="Hornblower"),
    # -- 2. queues and execution -----------------------------------------------------------------------
    BuildingType(
        "fields", "Task Fields", "🌾", "M",
        "a board of cards: tasks for the orks in To Do / In Progress / Done, your own to-dos (a checklist) "
        "and sticky notes in lanes of their own (Ideas, Questions…); a note becomes a task by moving into a status lane. "
        "A cart is a new card: a task, or one of your to-dos when its route is one of `mine_routes`; the result of "
        "a task it sent (a Barracks' `pool.assigned` / `pool.done` on a return road) moves that card",
        "counts per status, the task in work, your open to-dos, the latest notes, * when something is new",
        "the lanes, your to-dos and the notes; add, move, open, tick off, colour and send cards; a card's "
        "context from the wikis, a to-do's plan, personal cards that never reach a model",
        events=(_e("tasks.status_changed", "task moved", NODE, "a task changed its status (from → to)"),
                _e("tasks.created", "task added", NODE, "a new task was added (or a note became one)"),
                _e("notes.created", "note added", TEXT, "a sticky note was added: its title and text"),
                _e("tasks.sent", "card sent", TEXT, "the operator sent a card on (s): its title and text")),
        actions=(_a("tasks.new", "New task", "+", "add a card to the focused lane"),
                 _a("notes.new", "New note", "🗒", "add a sticky note"),
                 _a("todos.new", "New chore", "☐", "add a to-do of your own")),
        config={"path": (str, None, False), "mode": (str, ("board", "tasks", "notes"), False),
                "lanes": (list, None, False), "mine_routes": (list, None, False), "send_new": (bool, None, False),
                "settle": (int, (0, 3600), False), "later_minutes": (int, (1, 1440), False),
                "wikis": (list, None, False), "private_todos": (bool, None, False), "plan_model": (str, None, False),
                "night_round": (bool, None, False)},
        art="burrow", orc="Taskmaster"),
    BuildingType(
        "barracks", "Barracks", "🏕️", "M",
        "agents work tasks in parallel, each task on its own branch; the steward keeps the rules, answers "
        "the orks' questions, reviews the work (tests + the diff, up to 3 reworks) and opens a pull request for "
        "code and documents that go out (a meeting's prep and other local documents get none)",
        "each ork with its model and task, the queue, the reviews, 🔥 when the steward asks you",
        "the steward (rules, questions for you), the orks, the queue, the tasks with their PRs and the decisions",
        events=(_e("pool.assigned", "task assigned", TEXT, "a task went to an ork (new, follow-up or rework)"),
                _e("pool.done", "task accepted", TEXT, "the steward accepted a task (or an approved post went out): the report, the files and "
                  "its pull request"),
                _e("pool.failed", "task failed", TEXT, "a task failed or was rejected after its reworks"),
                _e("pool.question", "question for you", TEXT, "the steward needs the operator's answer, or an ork's draft to post "
                  "(Jira, Confluence…) waits for approval: the draft, the report and the files; through a "
                  "Loot, accept lets the ork post it and rework sends it back"),
                _e("pool.idle", "queue empty", TEXT, "every task is done, the orks are idle")),
        actions=(_a("pool.answer", "Answer", "+", "answer the steward's question (🔥); the steward hires the orks itself"),
                 _a("pool.pause", "Pause / resume", "⏸", "stop or resume taking tasks"),
                 _a("pool.task", "New task", "✍", "write a task straight to the barracks: a title and a brief")),
        config={"max_orcs": (int, (1, 10), False), "budget_usd": (float, (0, 200), False),
                "providers": (list, None, False), "worktrees": (bool, None, False), "orders": (str, None, False),
                "session_tasks": (int, (1, 20), False), "max_reworks": (int, (0, 10), False),
                "test_cmd": (str, None, False), "steward": (str, None, False), "base": (str, None, False),
                "plan": (bool, None, False), "escalate": (bool, None, False),
                "notes": (list, None, False), "claims": (str, ("wait", "flag", "off"), False),
                "claim_wait": (int, (1, 1440), False), "claim_days": (int, (1, 90), False),
                "briefs": (bool, None, False), "briefs_dir": (str, None, False),
                "wants": (list, None, False), "want_by_source": (dict, None, False)},
        art="barracks", orc="Grunts", agentic=True),
    BuildingType(
        "council", "Clan Fire", "🪔", "M",
        "the clan reviews a document from every side (PM, architect, marketing…); the steward lets it go, "
        "sends it back for rework or asks you; a clan that routes (triage) also says who takes it on — you or an agent",
        "the clan and who holds a veto, 🔥 when the steward asks", "each review, the steward's decision, the report",
        events=(_e("team.approved", "approved", TEXT, "the steward let the document go: the document as it is"),
                _e("team.rework", "rework", TEXT, "sent back: the steward's comments, each review, the document"),
                _e("team.artifact_ready", "review report", FILE, "the full review: every verdict and the decision"),
                _e("team.routed", "routed", TEXT, "a clan that routes let it go and named who takes it on: the document "
                   "and its route (a road may wait for one route)")),
        actions=(_a("team.add", "Add member", "+", "add a member: role and model; its brief is a file"),
                 _a("team.start", "Review", "▶", "review a document (a path or text), or answer the steward")),
        config={"steward_prompt": (str, None, False), "members": (list, None, False), "veto": (list, None, False),
                "max_cycles": (int, (1, 10), False), "budget_usd": (float, (0, 100), False),
                "moderator": (str, None, False), "routes": (list, None, False),
                "goal": (str, None, False), "max_rounds": (int, (1, 20), False),      # the old debate's; kept loading
                "purpose": (str, None, False), "exits": (list, None, False), "notes": (list, None, False)},
        art="great_hall", orc="Chieftains", agentic=True),
    BuildingType(
        "war_drum", "War Drum", "🥁", "L",
        "the day's rhythm from a calendar (.ics file or URL): what is now, what is next",
        "what is now, what is next, how much is left today", "the day and the week; add an event",
        events=(_e("calendar.event_due", "event starts", TEXT, "an event is starting now"),
                _e("calendar.event_added", "event added", TEXT, "an event was added"),
                _e("calendar.event_removed", "event removed", TEXT, "an event was removed"),
                _e("calendar.day_schedule", "day schedule", TEXT, "the morning digest: today's events"),
                _e("calendar.event_upcoming", "meeting soon", TEXT,
                   "a meeting starts in `lead` (2h), or was just added with `prepare_new`: time to prepare its "
                   "document; titled by the meeting, tagged [meet:<id>], its ref the meeting's"),
                _e("calendar.doc_opened", "doc opened", FILE, "Enter on a meeting with a document: the document")),
        actions=(_a("calendar.new", "New event", "+", "add an event"),
                 _a("calendar.prepare", "Prepare doc", "📄", "send `meeting soon` for the selected meeting now"),
                 _a("calendar.import", "Import calendar", "⇩", "take in a .ics file, or subscribe to a calendar's ICS link")),
        config={"ics": (str, None, False), "day_starts": (str, None, False), "lead": (str, None, False),
                "prepare_new": (bool, None, False), "beats": (list, None, False), "imports": (dict, None, False)},
        art="war_tent", orc="Drummer"),
    # -- 3. storage, code and inspection ---------------------------------------------------------------
    BuildingType(
        "forest", "File Forest", "🌲", "L",
        "the repository as a tree; pick a file or folder as the target",
        "the top of the tree, how many files changed", "the whole tree; Enter picks, the preview shows",
        events=(_e("files.changed", "files changed", FILE, "files in the folder were added, changed or removed"),
                _e("files.selected", "path picked", FILE, "a file or folder was picked")),
        actions=(_a("files.open", "Open in OS", "↗", "open the folder in the system file manager"),),
        config={"path": (str, None, False)},
        art="library", orc="Woodcutter"),
    BuildingType(
        "scrolls", "Scroll Dump", "🗑️", "S",
        "one LLM wiki (codebase, team, design or general): the Scroll Scrapper turns read-only sources "
        "(notes, code, a git revision, a Confluence space) into linked pages and keeps them current by itself; "
        "pages people own stay theirs, the Council spot-checks, every change is committed",
        "the topic, pages, sources, what is not taken in yet", "the wiki's pages and the sources; i ingests, l lints",
        events=(_e("knowledge.changed", "knowledge changed", FILE, "a source or a wiki page was added or changed"),
                _e("knowledge.chunks", "wiki context", TEXT, "a task with the wiki's map and the pages that matter most for "
                   "it, for the agent to read from (also when a Barracks reads it first: `notes`)"),
                _e("wiki.updated", "wiki updated", TEXT, "an ingest finished: the pages added, changed, marked stale"),
                _e("wiki.linted", "wiki linted", TEXT, "a lint finished: the problems it found"),
                _e("wiki.review", "spot-check", TEXT, "a sample of freshly written pages, for the Council to check"),
                _e("wiki.noted", "note kept", FILE, "a Quick note was kept in the wiki's inbox: the note's file")),
        actions=(_a("wiki.note", "Quick note", "✎", "leave a note for the wiki: its section, tags and links suggested"),
                 _a("wiki.ingest", "Ingest", "⟳", "take the new and changed sources into the wiki now"),
                 _a("wiki.lint", "Lint", "🧹", "check the wiki for contradictions, stale facts, orphans"),
                 _a("knowledge.add", "Add base", "+", "connect a folder as a source")),
        config={"paths": (list, None, False), "sources": (list, None, False), "wiki": (str, None, False),
                "inbox": (str, None, False), "calendar": (str, None, False),
                "check": (str, ("weekly", "daily", "ingest", "off"), False), "suggest_model": (bool, None, False),
                "topic": (str, ("general", "codebase", "team", "design"), False),
                "harness": (str, harnesses.ids(), False), "model": (str, None, False),
                "auto_ingest": (bool, None, False), "commit": (bool, None, False),
                "review_sample": (int, (0, 10), False), "council": (str, None, False)},
        art="library", orc="Scroll Scrapper"),
    BuildingType(
        "mine", "The Mine", "⛏️", "M",
        "deep research on the open web, checked by more than one mind: every AI tool that can search the web "
        "searches the question on its own, their findings are checked against each other (two models, two sites), "
        "what is open is searched again or debated, what stays disputed you decide; the report goes to the Wiki "
        "(docs/design/mine.md)",
        "the question in work and its round; the sources each tool found, confirmed and disputed, the cost",
        "the plan, a column per tool, the findings marked confirmed / disputed / one source, the disputes waiting "
        "on you, the reports",
        events=(_e("mine.reported", "report", FILE, "a research is done: its report (in the Wiki's inbox, or the "
                   "Mine's own file); titled by the question with its counts"),
                _e("mine.asked", "disputed", TEXT, "a research waits on you: findings the tools disagree on"),
                _e("mine.failed", "research failed", TEXT, "a research failed: why")),
        actions=(_a("mine.new", "New research", "⛏", "ask a question: the plan, the tools and the limit before it starts"),),
        config={"tools": (list, None, False), "limit": (float, (0.1, 100), False),
                "month_limit": (float, (0, 1000), False), "rounds": (int, (0, 6), False),
                "min_models": (int, (1, 5), False), "min_domains": (int, (1, 10), False),
                "wait_answers": (str, None, False), "wiki": (str, None, False), "repeats": (list, None, False)},
        art="library", orc="Prospector", agentic=True),
    BuildingType(
        "gramophone", "The Gramophone", "📻", "S",
        "a result you can listen to on the road: a report, a summary or a wiki page becomes a short spoken episode "
        "(its steward writes the script, Gemini TTS speaks it) to play here or download to the phone "
        "(docs/design/audio-briefing.md)",
        "the last episode and its length, or the one being made",
        "the episodes with ▶ and download, their transcripts and costs; make one from pasted text; the key, the voice, "
        "the limit per episode",
        events=(_e("gramophone.done", "episode", TEXT, "an episode is ready: its transcript; titled by its source and "
                   "its length"),
                _e("gramophone.failed", "episode failed", TEXT, "an episode failed: why")),
        actions=(_a("gramophone.make", "Make an episode", "📻", "an episode of the last text that came, or of text you paste"),),
        config={"language": (str, ("auto", "ru", "en"), False), "minutes": (int, (2, 20), False),
                "voice": (str, None, False), "tts_model": (str, None, False), "model": (str, None, False),
                "key": (str, None, False), "cap_usd": (float, (0.05, 5), False), "keep": (int, (1, 200), False)},
        art="rookery", orc="Bard", agentic=True),
    BuildingType(
        "lake", "Lake of Insight", "🌊", "L",
        "the inspector: a file, a git diff side by side, Markdown, diagrams, a local URL as text; "
        "a text file on disk is edited in place and saves by itself",
        "what it shows now, or the file being edited", "the view of what arrived; ↗ opens a URL in the browser; "
        "e edits a file (autosave on a timer and on leaving)",
        events=(_e("lake.viewed", "viewed", TEXT, "something was opened in the Lake"),
                _e("lake.saved", "file edited", FILE, "a file edited in the Lake was saved: the file")),
        actions=(_a("lake.open", "Open in browser", "↗", "open what it shows in the browser"),
                 _a("lake.edit", "Edit", "✎", "edit the file it shows (again: save and close the editor)")),
        config={"url": (str, None, False), "autosave": (int, (1, 600), False)},
        art="spire", orc="Seer"),
    BuildingType(
        "forge", "The Forge", "⚒️", "M",
        "the repository's state: what comes in (branches, commits, pull requests) and what goes out "
        "(merges); runs a branch's tests and squash-merges it into the base when you say, conflicts named",
        "branches with PR state and +/− lines", "every branch: commits, PR, diff stat; merge",
        events=(_e("git.commit", "new commit", TEXT, "a branch got a new commit"),
                _e("git.pr_opened", "PR opened", TEXT, "a pull request was opened"),
                _e("git.pr_merged", "PR merged", TEXT, "a pull request was merged"),
                _e("forge.merged", "merged", TEXT, "a branch was squash-merged into the base"),
                _e("forge.conflict", "conflict", TEXT, "a merge stopped on conflicts or failing tests")),
        actions=(_a("forge.merge", "Merge", "⚒", "test and squash-merge the selected branch"),
                 _a("git.open_pr", "Open PR", "↗", "open the selected branch's pull request")),
        config={"remote": (str, None, False), "base": (str, None, False), "test_cmd": (str, None, False),
                "confirm": (bool, None, False)},
        art="forge", orc="Smith", agentic=True),
    # -- 4. results, telemetry and egress --------------------------------------------------------------
    BuildingType(
        "loot", "Loot Vault", "📦", "S",
        "the review checkpoint on a road: by its rules a cart passes at once or waits for a person, "
        "who accepts it, edits it or sends it back for rework (with what the chain cost)",
        "held, needs you, passed today", "the queue, a cart's trail and cost; accept, rework, restore",
        events=(_e("loot.passed", "passed", TEXT, "a cart passed: by the rules or accepted"),
                _e("loot.rework", "sent back", TEXT, "a cart was sent back to its source with the reason"),
                _e("loot.needs_you", "needs you", TEXT, "a cart ran out of rework rounds: the person fixes it"),
                _e("generator.accepted", "file accepted", FILE, "a generated file was accepted"),
                _e("generator.rejected", "file rejected", FILE, "a generated file was rejected"),
                _e("loot.stored", "stored", FILE, "something landed in ./loot/")),
        actions=(_a("loot.accept_all", "Accept all", "✓", "accept every held cart (not the ones that need you)"),
                 _a("generator.accept_all", "Accept files", "✓", "accept every changed file still waiting")),
        config={"path": (str, None, False), "review": (str, ("rules", "always", "never"), False),
                "sources": (list, None, False), "paths": (list, None, False),
                "max_cost_usd": (float, (0, 1000), False), "max_tokens": (int, (0, 100_000_000), False),
                "max_files": (int, (0, 10_000), False), "on_failed": (bool, None, False),
                "external": (bool, None, False), "max_rework": (int, (0, 10), False),
                "rework_tokens": (int, (0, 100_000_000), False)},
        art="vault", orc="Quartermaster", agentic=True),
    BuildingType(
        "crag", "Tally Crag", "🪨", "M",
        "charts: complex data at a glance — the numbers a road brings, spend, tokens, runs, quotas, load; "
        "horizontal bars break it down, vertical bars show it over time",
        "a small bar chart and the current value", "the chart and its values",
        events=(_e("charts.threshold", "threshold", TEXT, "a value crossed its warning or critical line"),),
        actions=(_a("crag.flip", "Flip", "⇅", "vertical or horizontal bars"),
                 _a("crag.next", "Next", "⟳", "chart the next source")),
        config={"source": (str, ("limits", "spend", "tokens", "runs", "orcs", "tasks", "cpu", "road"), False),
                "orientation": (str, ("vertical", "horizontal"), False),
                "window": (str, ("1h", "24h", "7d"), False),
                "warn": (float, (0, 1e9), False), "crit": (float, (0, 1e9), False),
                "charts": (list, None, False)},
        art="rookery", orc="Crag Carver"),
    BuildingType(
        "catapult", "The Catapult", "🎯", "S",
        "the strict way out: waits for data from several roads (fan-in), checks it against a JSON Schema "
        "and sends it to an external API — or through an MCP server your AI tools have (the tool that has it carries "
        "the first shot, then its ork learns a direct path) — or, where a site has no API, closes a whole intent in the "
        "browser: its ork finds each form, a Playwright script fills them in turn and presses submit or hands them to you",
        "what it waits for, the last shot", "the loaded data, the check, the request or the form, and its answer",
        events=(_e("catapult.sent", "sent", TEXT, "the request went out (or the form was filled): the answer"),
                _e("catapult.failed", "failed", TEXT, "the check, the request or the form failed"),
                _e("catapult.repaired", "repaired", TEXT, "the site changed: the overseer rewrote the fill script")),
        actions=(_a("catapult.fire", "Fire", "🎯", "send what is loaded now"),
                 _a("catapult.dry_run", "Dry run", "🧪", "show the request (or which field gets what) without sending it"),
                 _a("catapult.scout", "Scout", "🔭", "browser mode: the ork finds every form of the intent and writes their scripts")),
        config={"url": (str, None, False), "method": (str, ("POST", "PUT", "PATCH"), False),
                "schema": (str, None, False), "wait_for": (list, None, False),
                "token_env": (str, None, False), "confirm": (bool, None, False),
                "mode": (str, ("api", "browser", "mcp"), False), "forms": (list, None, False),
                "fields": (list, None, False), "finish": (str, ("leave", "press"), False),
                "repair": (bool, None, False), "key": (str, None, False), "ttl": (int, (0, 10080), False),
                "to": (str, None, False), "tool": (str, None, False), "via": (str, None, False),
                "args": (list, None, False), "goal": (str, None, False), "local": (bool, None, False)},
        art="workshop", orc="Loader"),
    BuildingType(
        "town_hall", "Town Hall", "🏰", "L",
        "the town's own building: build new buildings, audit the town; its agents watch security, "
        "usability and spend; live sessions and quotas live here",
        "Warder's alerts, today's spend, the lowest quota",
        "the hall's agents and the last audit, the sessions, the quotas",
        events=(_e("hall.audit_done", "audit done", TEXT, "an audit finished: its findings"),),
        actions=(_a("hall.build", "Build", "🏗", "build: from a preset, or new from scratch — one way in"),
                 _a("hall.audit", "Audit", "🔍", "audit the town: security, usability, spend")),
        art="great_hall", orc="Warchief"),
    BuildingType(
        "workshop", "Workshop", "🛠️", "S",
        "a building made from scratch: the Builder's script does the work on every cart; a "
        "steward prompt only where the script says it cannot (exit 3)",
        "the last run and its result", "the runs, their input and output; table or card by its layout",
        events=(_e("workshop.done", "done", TEXT, "the script's output"),
                _e("workshop.failed", "failed", TEXT, "the script failed: the error"),
                _e("workshop.alert", "alert", TEXT, "the script flagged its output (exit 4)")),
        actions=(_a("workshop.run", "Run", "▶", "run the script again on the last cart"),
                 _a("workshop.test", "Test", "🧪", "run the blueprint's mock carts in the sandbox")),
        config={"runtime": (str, ("python", "bash"), True), "layout": (str, ("log", "table", "card"), False),
                "steward_prompt": (str, None, False), "inputs": (list, None, False), "schedule": (str, None, False)},
        art="workshop", orc="Tinker"),
    BuildingType(
        "custom", "Custom (panes)", "🏗", "S",
        "panes of whitelisted widgets over whitelisted data (the Mason & Artisan building of old)",
        "the spec's mini lines", "the panes",
        art="workshop"),
)}
DEFAULT_TYPE = "custom"

# T1107: the 15 buildings of the camp took over the types of T1105. Specs of old keep loading.
ALIASES = {"dropzone": "pit", "mail": "watchtower", "tasks": "fields", "pool": "barracks", "team": "council",
           "campfire": "council", "clan_fire": "council",
           "calendar": "war_drum", "file_tree": "forest", "knowledge": "scrolls", "git": "forge",
           "generator": "loot", "charts": "crag",
           # the Totem's rules moved to the Signpost; the Totem's name and look wait for a building of their own
           # (when it comes, a "totem" spec with `rules` still has to load as a Signpost — see `migrate`)
           "totem": "signpost"}
# Events of old: a road, a spec's pick or a Horn's table that names one still finds the new event.
EVENT_ALIASES = {"totem.routed": "signpost.routed", "totem.unmatched": "signpost.unmatched"}


def event_id(event: str) -> str:
    """The current id of an event (an old id → its new one)."""
    return EVENT_ALIASES.get(event, event)


def migrate(spec: dict) -> dict:
    """A spec of an old type as its camp building (a copy; the file on disk is left as it is).

    Agent / Script folds in: a script becomes a Mill step, an agent a Barracks of one orc whose
    standing orders are the skill."""
    tid = spec.get("type")
    if ALIASES.get(tid, tid) == "council" and spec.get("icon") == "🔥":
        spec = {**spec, "icon": "🪔"}          # the Clan Fire's own icon; 🔥 means "waits for you"
    if tid == "totem":                         # the Totem's look stays the Totem's: the post wears its own
        spec = {**spec, "icon": "🚏" if spec.get("icon") in (None, "", "🗿") else spec["icon"],
                "title": "Signpost" if spec.get("title") == "Totem" else spec.get("title", "Signpost")}
    if tid in ALIASES:
        spec = {**spec, "type": ALIASES[tid]}
        if isinstance(spec.get("events"), list):
            spec["events"] = [event_id(str(e)) for e in spec["events"]]
        return spec
    if tid == "catapult" and isinstance(spec.get("config"), dict) and "page" in spec["config"]:
        cfg = dict(spec["config"])           # one page → the intent's first form
        page, submit = str(cfg.pop("page") or ""), str(cfg.pop("submit", "") or "")
        if page and not cfg.get("forms"):
            cfg["forms"] = [f"form = {page}" + (f" | | {submit}" if submit else "")]
        return {**spec, "config": cfg}
    if tid != "agent":
        return spec
    cfg = dict(spec.get("config") or {})
    out = {k: v for k, v in spec.items() if k not in ("config", "events", "quick_actions")}
    if cfg.get("harness") == "script":
        out["type"], out["config"] = "mill", ({"steps": [f"script: {cfg['skill']}"]} if cfg.get("skill") else {})
    else:
        out["type"] = "barracks"
        out["config"] = {"max_orcs": 1, "providers": [cfg.get("harness") or "main"],
                         **({"orders": cfg["skill"]} if cfg.get("skill") else {})}
    return out
SYSTEM_TYPES = frozenset({"town_hall"})        # built by orkcraft itself, never offered in the wizard
RETIRED_TYPES = frozenset({DEFAULT_TYPE, "forest", "lake"})   # an old scroll's still loads, none is built anew:
# Custom (panes); File tree (its folder watch and its picker go to other buildings); Inspector — the town's
# Lake window, never a building (realm/lake.py: a road into an old one becomes "open in Lake" on its source)
SCRATCH_TYPES = frozenset({"workshop"})        # only the Builder's interview makes these
GUI_ONLY = frozenset({"mine", "gramophone"})   # built after the TUI was deprecated: no terminal view (calm-town.md §9)
MAX_QUICK_ACTIONS = 2


def type_of(spec: dict | None) -> BuildingType:
    tid = (spec or {}).get("type") or DEFAULT_TYPE
    return TYPES.get(ALIASES.get(tid, tid), TYPES[DEFAULT_TYPE])


def events_of(spec: dict | None) -> list[str]:
    """The typed events this building sends: the spec's pick, else every event of its type."""
    t = type_of(spec)
    picked = (spec or {}).get("events")
    picked = None if picked is None else {event_id(str(e)) for e in picked}
    return [e.id for e in t.events if picked is None or e.id in picked]


def quick_actions_of(spec: dict | None) -> list[ActionDef]:
    """Up to two actions on the hut: the spec's pick, else the type's first ones."""
    t = type_of(spec)
    picked = (spec or {}).get("quick_actions")
    ids = picked if picked is not None else [a.id for a in t.actions]
    return [a for a in (t.action(i) for i in ids) if a is not None][:MAX_QUICK_ACTIONS]


def event_label(event_id: str) -> str | None:
    for t in TYPES.values():
        e = t.event(event_id)
        if e is not None:
            return e.label
    return None


def all_event_ids() -> frozenset[str]:
    return frozenset(e.id for t in TYPES.values() for e in t.events)


# -- the parts (checks, what the builders read): every name stays importable from here --------------
from orkcraft.realm.catalog_checks import (  # noqa: E402, F401
    validate,
)
from orkcraft.realm.catalog_reference import (  # noqa: E402, F401
    INTENTS, TAKES, _ANY, ACCEPTS, EFFECTS, CONFIG_HELP, takes, accepts, _param_text, catalog_text,
)
