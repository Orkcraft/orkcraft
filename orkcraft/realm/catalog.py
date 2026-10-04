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
from collections.abc import Collection
from typing import Any

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
        art="burrow", orc="Scavenger"),
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
                _e("watch.mention", "mention", TEXT, "you were mentioned or written to: Slack, Jira, Confluence, Figma")),
        actions=(_a("mail.open_new", "Open new", "✉", "open the newest new signal"),
                 _a("watch.read_all", "Read all", "✓", "mark every signal read"),
                 _a("mail.refresh", "Check now", "↻", "check every source now")),
        config={"host": (str, None, False), "user_env": (str, None, False), "password_env": (str, None, False),
                "folder": (str, None, False), "port": (int, (1, 65535), False),
                "github": (str, None, False), "cron": (str, None, False),
                "webhook_port": (int, (1024, 65535), False), "webhook_secret_env": (str, None, False),
                "feeds": (list, None, False), "intent": (str, None, False)},
        art="watchtower", orc="Lookout"),
    BuildingType(
        "signpost", "Signpost", "🚏", "S",
        "a crossroads post: rules (if / switch) send what arrives down one of its roads, no model",
        "the last route taken, how many routes", "the rules and what went where",
        events=(_e("signpost.routed", "routed", TEXT, "what arrived, sent down the route its rule picked"),
                _e("signpost.unmatched", "no rule", TEXT, "no rule matched what arrived")),
        config={"rules": (list, None, False)},
        art="spire", orc="Grot Pointa"),
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
        art="mill", orc="Miller"),
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
        "a board of cards: tasks in To Do / In Progress / Done and sticky notes in lanes of their own "
        "(Ideas, Questions…); a note becomes a task by moving into a status lane",
        "counts per status, the notes, * when something is new",
        "the lanes; add, move, open, colour and send cards",
        events=(_e("tasks.status_changed", "task moved", NODE, "a task changed its status (from → to)"),
                _e("tasks.created", "task added", NODE, "a new task was added (or a note became one)"),
                _e("notes.created", "note added", TEXT, "a sticky note was added: its title and text"),
                _e("tasks.sent", "card sent", TEXT, "the operator sent a card on (s): its title and text")),
        actions=(_a("tasks.new", "New task", "+", "add a card to the focused lane"),
                 _a("notes.new", "New note", "🗒", "add a sticky note")),
        config={"path": (str, None, False), "mode": (str, ("board", "tasks", "notes"), False),
                "lanes": (list, None, False)},
        art="burrow", orc="Taskmaster"),
    BuildingType(
        "barracks", "Barracks", "🏕️", "M",
        "agents work tasks in parallel, each task on its own branch; the steward keeps the rules, answers "
        "the orks' questions, reviews the work (tests + the diff, up to 3 reworks) and opens a pull request for "
        "code and documents that go out (a meeting's prep and other local documents get none)",
        "each ork with its model and task, the queue, the reviews, 🔥 when the steward asks you",
        "the steward (rules, questions for you), the orks, the queue, the tasks with their PRs and the decisions",
        events=(_e("pool.assigned", "task assigned", TEXT, "a task went to an ork (new, follow-up or rework)"),
                _e("pool.done", "task accepted", TEXT, "the steward accepted a task: the report and its pull request"),
                _e("pool.failed", "task failed", TEXT, "a task failed or was rejected after its reworks"),
                _e("pool.question", "question for you", TEXT, "the steward needs the operator's answer"),
                _e("pool.idle", "queue empty", TEXT, "every task is done, the orks are idle")),
        actions=(_a("pool.hire", "Hire / answer", "+", "answer the steward's question when it asks, else hire an ork"),
                 _a("pool.pause", "Pause / resume", "⏸", "stop or resume taking tasks")),
        config={"max_orcs": (int, (1, 10), False), "budget_usd": (float, (0, 200), False),
                "providers": (list, None, False), "worktrees": (bool, None, False), "orders": (str, None, False),
                "session_tasks": (int, (1, 20), False), "max_reworks": (int, (0, 10), False),
                "test_cmd": (str, None, False), "steward": (str, None, False), "base": (str, None, False)},
        art="barracks", orc="Grunts", agentic=True),
    BuildingType(
        "council", "Clan Fire", "🪔", "M",
        "the clan reviews a document from every side (PM, architect, marketing…); the steward lets it go, "
        "sends it back for rework or asks you",
        "the clan and who holds a veto, 🔥 when the steward asks", "each review, the steward's decision, the report",
        events=(_e("team.approved", "approved", TEXT, "the steward let the document go: the document as it is"),
                _e("team.rework", "rework", TEXT, "sent back: the steward's comments, each review, the document"),
                _e("team.artifact_ready", "review report", FILE, "the full review: every verdict and the decision")),
        actions=(_a("team.add", "Add member", "+", "add a member: role and model; its brief is a file"),
                 _a("team.start", "Review", "▶", "review a document (a path or text), or answer the steward")),
        config={"steward_prompt": (str, None, False), "members": (list, None, False), "veto": (list, None, False),
                "max_cycles": (int, (1, 10), False), "budget_usd": (float, (0, 100), False),
                "moderator": (str, None, False),
                "goal": (str, None, False), "max_rounds": (int, (1, 20), False)},     # the old debate's; kept loading
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
                   "a meeting starts in `lead` (2h): time to prepare its document; tagged [meet:<id>]"),
                _e("calendar.doc_opened", "doc opened", FILE, "Enter on a meeting with a document: the document")),
        actions=(_a("calendar.new", "New event", "+", "add an event"),
                 _a("calendar.prepare", "Prepare doc", "📄", "send `meeting soon` for the selected meeting now")),
        config={"ics": (str, None, False), "day_starts": (str, None, False), "lead": (str, None, False)},
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
                _e("knowledge.chunks", "wiki context", TEXT, "a task with the wiki's map, for the agent to read from"),
                _e("wiki.updated", "wiki updated", TEXT, "an ingest finished: the pages added, changed, marked stale"),
                _e("wiki.linted", "wiki linted", TEXT, "a lint finished: the problems it found"),
                _e("wiki.review", "spot-check", TEXT, "a sample of freshly written pages, for the Council to check")),
        actions=(_a("wiki.ingest", "Ingest", "⟳", "take the new and changed sources into the wiki now"),
                 _a("wiki.lint", "Lint", "🧹", "check the wiki for contradictions, stale facts, orphans"),
                 _a("knowledge.add", "Add base", "+", "connect a folder as a source")),
        config={"paths": (list, None, False), "sources": (list, None, False), "wiki": (str, None, False),
                "topic": (str, ("general", "codebase", "team", "design"), False),
                "harness": (str, ("claude", "agy"), False), "model": (str, None, False),
                "auto_ingest": (bool, None, False), "commit": (bool, None, False),
                "review_sample": (int, (0, 10), False), "council": (str, None, False)},
        art="library", orc="Scroll Scrapper"),
    BuildingType(
        "lake", "Lake of Insight", "🌊", "L",
        "the inspector: a file, a git diff side by side, Markdown, diagrams, a local URL as text",
        "what it shows now", "the view of what arrived; ↗ opens a URL in the browser",
        events=(_e("lake.viewed", "viewed", TEXT, "something was opened in the Lake"),),
        actions=(_a("lake.open", "Open in browser", "↗", "open what it shows in the browser"),),
        config={"url": (str, None, False)},
        art="spire", orc="Seer"),
    BuildingType(
        "forge", "The Forge", "⚒️", "M",
        "closes the loop: branches with their PRs and changes; runs the tests, settles conflicts and "
        "squash-merges a ready branch into the base",
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
        "telemetry carved in stone: horizontal bars of budgets, vertical bars of load",
        "a small bar chart and the current value", "the chart and its values",
        events=(_e("charts.threshold", "threshold", TEXT, "a value crossed its warning or critical line"),),
        actions=(_a("crag.flip", "Flip", "⇅", "vertical or horizontal bars"),
                 _a("crag.next", "Next", "⟳", "chart the next source")),
        config={"source": (str, ("limits", "spend", "tokens", "runs", "orcs", "tasks", "cpu", "road"), False),
                "orientation": (str, ("vertical", "horizontal"), False),
                "window": (str, ("1h", "24h", "7d"), False),
                "warn": (float, (0, 1e9), False), "crit": (float, (0, 1e9), False)},
        art="rookery", orc="Crag Carver"),
    BuildingType(
        "catapult", "The Catapult", "🎯", "S",
        "the strict way out: waits for data from several roads (fan-in), checks it against a JSON Schema "
        "and sends it to an external API — or, where a site has no API, closes a whole intent in the browser: "
        "its ork finds each form, a Playwright script fills them in turn and presses submit or hands them to you",
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
                "mode": (str, ("api", "browser"), False), "forms": (list, None, False),
                "fields": (list, None, False), "finish": (str, ("leave", "press"), False),
                "repair": (bool, None, False), "key": (str, None, False), "ttl": (int, (0, 10080), False)},
        art="workshop", orc="Loader"),
    BuildingType(
        "town_hall", "Town Hall", "🏰", "L",
        "the town's own building: build new buildings, audit the town; its agents watch security, "
        "usability and spend; live sessions and quotas live here",
        "Warder's alerts, today's spend, the lowest quota",
        "the hall's agents and the last audit, the sessions, the quotas",
        events=(_e("hall.audit_done", "audit done", TEXT, "an audit finished: its findings"),),
        actions=(_a("hall.preset", "Preset", "📜", "build from a preset: what you need, name it, place it"),
                 _a("hall.scratch", "New", "🛠", "build from scratch: the Builder asks, writes a script, tests it"),
                 _a("hall.audit", "Audit", "🔍", "audit the town: security, usability, spend")),
        art="great_hall", orc="Chieftain"),
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
        out["config"] = {"max_orcs": 1, "providers": [cfg.get("harness") or "claude"],
                         **({"orders": cfg["skill"]} if cfg.get("skill") else {})}
    return out
SYSTEM_TYPES = frozenset({"town_hall"})        # built by orkcraft itself, never offered in the wizard
SCRATCH_TYPES = frozenset({"workshop"})        # only the Builder's interview makes these
MAX_QUICK_ACTIONS = 2


def type_of(spec: dict | None) -> BuildingType:
    tid = (spec or {}).get("type") or DEFAULT_TYPE
    return TYPES.get(ALIASES.get(tid, tid), TYPES[DEFAULT_TYPE])


def size_of(spec: dict | None) -> tuple[int, int]:
    """The hut size (w, h) a spec asks for, else its type's."""
    t = type_of(spec)
    return SIZES.get((spec or {}).get("size") or t.size, SIZES[t.size])


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


def validate(spec: dict) -> list[str]:
    """What a schema cannot check: the type exists, its events, actions, size and config."""
    errors: list[str] = []
    spec = migrate(spec)
    tid = spec.get("type") or DEFAULT_TYPE
    t = TYPES.get(tid)
    if t is None:
        return [f"type: unknown {tid!r}; choose one of {', '.join(TYPES)}"]
    if spec.get("size") is not None and spec["size"] not in SIZES:
        errors.append(f"size: {spec['size']!r} is not one of {', '.join(SIZE_ORDER)}")
    if spec.get("roof"):
        from orkcraft.realm import huts
        if spec["roof"] not in huts.ROOFS:
            errors.append(f"roof: no {spec['roof']!r}; choose one of {', '.join(huts.ROOFS)} or none")
    for ev in spec.get("events") or []:
        if t.event(ev) is None:
            errors.append(f"events: {tid} does not send {ev!r}; it sends {', '.join(e.id for e in t.events) or 'nothing typed'}")
    actions = spec.get("quick_actions") or []
    if len(actions) > MAX_QUICK_ACTIONS:
        errors.append(f"quick_actions: at most {MAX_QUICK_ACTIONS}")
    for a in actions:
        if t.action(a) is None:
            errors.append(f"quick_actions: {tid} has no action {a!r}; it has {', '.join(x.id for x in t.actions) or 'none'}")
    config = spec.get("config") or {}
    for key, value in config.items():
        rule = t.config.get(key)
        if rule is None:
            errors.append(f"config: {tid} takes no {key!r}; it takes {', '.join(t.config) or 'nothing'}")
            continue
        typ, allowed, _ = rule
        if typ is bool:
            ok_type = isinstance(value, bool)
        elif typ is float:
            ok_type = isinstance(value, (int, float)) and not isinstance(value, bool)
        else:
            ok_type = isinstance(value, typ) and not isinstance(value, bool)
        if not ok_type:
            errors.append(f"config: {key} must be {typ.__name__}")
        elif isinstance(allowed, tuple) and typ in (int, float) and not allowed[0] <= value <= allowed[1]:
            errors.append(f"config: {key} must be between {allowed[0]} and {allowed[1]}")
        elif isinstance(allowed, tuple) and typ is str and value not in allowed:
            errors.append(f"config: {key} must be one of {', '.join(allowed)}")
        elif typ is str and len(value) > 300:
            errors.append(f"config: {key} is too long")
        elif typ is list and (len(value) > 10 or not all(isinstance(x, str) and len(x) <= 300 for x in value)):
            errors.append(f"config: {key} must be up to 10 strings")
    if tid == "scrolls" and isinstance(config.get("wiki"), str):
        w = config["wiki"].strip()
        if not w or w.startswith(("/", "~")) or ".." in w.replace("\\", "/").split("/"):
            errors.append("config: wiki must be a folder inside the project")
    if tid == "mill" and isinstance(config.get("steps"), list):
        from orkcraft.realm import mill
        errors += [f"config: steps: {e}" for e in mill.check(config["steps"])]
    if tid == "workshop" and isinstance(config.get("schedule"), str) and config["schedule"].strip():
        from orkcraft.realm import watch
        if not watch.schedule_ok(config["schedule"]):
            errors.append("config: schedule: say `every 15m`, `hourly`, `daily 05:00`, `weekly mon 09:00` or a 5-field cron")
    if tid == "watchtower":
        from orkcraft.realm import watch
        if isinstance(config.get("cron"), str) and not watch.schedule_ok(config["cron"]):
            errors.append("config: cron: say `every 15m`, `hourly`, `daily 05:00`, `weekly mon 09:00` or a 5-field cron")
        if isinstance(config.get("github"), str) and not watch.REPO.match(config["github"]):
            errors.append("config: github must be owner/repo")
        if isinstance(config.get("feeds"), list):
            from orkcraft.realm import feeds
            errors += [f"config: feeds: {e}" for e in feeds.check(config["feeds"])]
            if not config.get("webhook_port") and any("secret=" in str(x) for x in config["feeds"]):
                errors.append("config: feeds: secret= is for webhooks — set webhook_port too")
    if tid == "horn":
        from orkcraft.realm import horn
        if isinstance(config.get("sounds"), list):
            errors += [f"config: sounds: {e}" for e in horn.parse(config["sounds"])[1]]
        if isinstance(config.get("default"), str) and not horn.sound_ok(config["default"]):
            errors.append(f"config: default: choose {', '.join(horn.SOUNDS)} or an audio file")
        if isinstance(config.get("quiet"), str) and not horn.quiet_ok(config["quiet"]):
            errors.append("config: quiet: say `22:00-08:00`")
    if tid == "catapult":
        from orkcraft.realm import catapult_web
        if isinstance(config.get("forms"), list):
            errors += [f"config: forms: {e}" for e in catapult_web.parse_forms(config["forms"])[1]]
        if isinstance(config.get("fields"), list):
            errors += [f"config: fields: {e}" for e in catapult_web.parse_rules(config["fields"])[1]]
        if config.get("mode") == "browser" and not config.get("forms"):
            errors.append("config: mode: browser needs forms — `name = https://… | what to open`")
    if tid == "signpost" and isinstance(config.get("rules"), list):
        from orkcraft.realm import signpost
        errors += [f"config: rules: {e}" for e in signpost.rules_of(config["rules"])[1]]
    if tid != DEFAULT_TYPE:
        for key, (_, _, required) in t.config.items():
            if required and key not in config:
                errors.append(f"config: {tid} needs {key!r}")
    return errors


# What the operator wants done → the camp buildings that do it (the preset picker's first step).
# Every type stands under exactly one intent, in the order the operator is likely to need it.
INTENTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Take in what I drop, paste or receive", ("pit", "watchtower")),
    ("Sort and transform it — no model", ("signpost", "mill")),
    ("Plan and track the work", ("fields", "war_drum")),
    ("Put agents to work", ("barracks", "council")),
    ("Know the project: files, notes, diffs", ("forest", "scrolls", "lake")),
    ("Ship the results: merge, keep, send", ("forge", "loot", "catapult")),
    ("Watch load, limits and spend", ("crag",)),
    ("Hear what comes in", ("horn",)),
)


# -- what the builders read -------------------------------------------------------------------------
# The catalog is the only thing the Foreman and the Town Builder know of the buildings, so it says
# what a type does with a cart, what it does outside the camp and how each setting is written.
# tests/test_catalog_docs.py keeps these in step with the views and the config of TYPES.

# What a cart on a plain road makes the building do. A type that is not here only shows the cart
# as a note: a plain road into it does nothing.
TAKES: dict[str, str] = {
    "signpost": "anything: the first rule that matches picks a route and the cart goes on as signpost.routed "
                "(else signpost.unmatched)",
    "mill": "text, or a file (its content): runs the steps on it → mill.done / mill.failed",
    "horn": "anything: plays the sound its table picks for that source and event",
    "fields": "anything: the cart becomes a card — a task in To Do (a note in `notes` mode); its title, else "
              "its first line, the rest its text → tasks.created / notes.created",
    "barracks": "anything: the cart becomes a task for an ork (the title names it, the text is the brief); "
                "its steward reviews the work → pool.done (with the pull request) / pool.failed",
    "council": "a document (text or a file, usually a Barracks result): the clan reviews it → team.approved "
               "(let go) or team.rework (sent back straight to the Barracks that wrote it), team.artifact_ready "
               "(the report)",
    "scrolls": "a task (the cart's title and text): goes on with the wiki's map → knowledge.chunks; a Clan Fire's "
               "verdict lands in reviews.md",
    "war_drum": "a cart tagged [meet:<id>] (e.g. Barracks' pool.done for its event_upcoming): the meeting's "
                "document → calendar.doc_opened when opened",
    "lake": "a file, a diff, Markdown, a branch or a URL: shows it",
    "forge": "a cart naming one of the repository's branches (e.g. Barracks' pool.done): tests it and "
             "squash-merges it into the base",
    "loot": "anything finished: by its rules it passes (loot.passed) or waits for the operator, who accepts it "
            "or sends it back to a Barracks for rework (loot.rework); stored → loot.stored",
    "crag": "the first number in the cart: a sample of the `road` source",
    "catapult": "anything: loads it under its source building; fires once every building of `wait_for` has loaded",
    "workshop": "anything (a file as its content): its script runs on the cart",
}

# What a building does outside the camp on its own: the network, merges, money.
EFFECTS: dict[str, str] = {
    "watchtower": "reads mail (IMAP), GitHub and the `feeds` (Slack, Jira, Confluence, Figma) over the network; "
                  "listens for webhooks on 127.0.0.1; an `intent` runs a light model",
    "barracks": "runs agents (spends money) in git worktrees; pushes an accepted task's branch and opens a pull request "
                "(code and documents that go out; local documents stay)",
    "council": "runs agents (spends money); members read the repository and the web",
    "scrolls": "runs its librarian agent (spends money); commits the wiki's folder; reads Confluence when a source names it",
    "forge": "merges into the base branch without asking unless `confirm`",
    "lake": "fetches `url` over the network",
    "war_drum": "fetches `ics` when it is a URL",
    "catapult": "sends HTTP requests to `url` without asking unless `confirm`; in browser mode fills web forms "
                "and presses submit when `finish: press`",
    "mill": "a `script:` step runs a command; an `agent:` step runs a model (spends money)",
    "workshop": "runs its script; its steward prompt runs a model",
}

# How each setting is written, with an example: the Builder fills config from these alone.
CONFIG_HELP: dict[str, dict[str, str]] = {
    "watchtower": {
        "host": "IMAP server for mail, e.g. imap.gmail.com (mail is off without it)",
        "user_env": "the environment variable that holds the mail login, e.g. MAIL_USER",
        "password_env": "the environment variable that holds the mail password, e.g. MAIL_PASSWORD",
        "folder": "the mail folder to read (default INBOX)",
        "port": "IMAP port (default 993, SSL)",
        "github": "owner/repo whose events to watch through `gh`, e.g. acme/api",
        "cron": "when watch.cron fires: `every 15m`, `every 2h`, `hourly`, `daily 05:00`, "
                "`weekly mon 09:00` or a 5-field cron",
        "webhook_port": "listen for POSTs on http://127.0.0.1:<port>/",
        "webhook_secret_env": "the environment variable with a secret a webhook must carry "
                              "(X-Orkcraft-Token, or GitHub's X-Hub-Signature-256)",
        "feeds": "one line per service, options naming environment variables, never tokens: "
                 "`slack: token=SLACK_TOKEN channels=C0123`, `jira: site=acme.atlassian.net user=ATL_EMAIL "
                 "token=ATL_TOKEN`, `confluence: … spaces=DOC`, `figma: token=FIGMA_TOKEN files=AbC123`; "
                 "`secret=` names a webhook's secret",
        "intent": "what to listen for, e.g. `user feedback about the app`: a light model lets only matching signals "
                  "down the roads",
    },
    "signpost": {
        "rules": "one rule per line, the first match wins: `<route>: contains <text>`, `<route>: matches <regex>`, "
                 "`<route>: kind <text|file|node>`, `<route>: source <building>`, `<route>: event <event id>`, "
                 "`<route>: <field> == <value>` (or !=; field: title, value, source, event, kind or a JSON key), "
                 "`<route>: else` last. A route is lowercase a-z 0-9 _ -. "
                 "e.g. [\"urgent: contains urgent\", \"bugs: matches (?i)bug|crash\", \"rest: else\"]",
    },
    "mill": {
        "steps": "one step per line, in order: `lines`, `grep: <regex>`, `drop: <regex>`, "
                 "`replace: <regex> => <with>`, `trim`, `lower`, `dedupe`, `csv`, `json`, "
                 "`extract: <field> = <regex>`, `pick: a, b`, `sort: <field> [desc]`, `limit: <n>`, "
                 "`filter: <field> <eq|ne|contains|matches> <value>`, `count`, `to_json`, "
                 "`template: <md with {field}>`, `join[: <sep>]`, `script: <command>`, `agent: <ask>` "
                 "(a read-only model step), `script: <command> || agent: <ask>` (the agent when the script fails). "
                 "e.g. [\"lines\", \"grep: TODO\", \"limit: 20\", \"join\"]",
        "env": "environment variables a `script:` step may see besides a clean PATH, e.g. [\"API_TOKEN\"]",
        "model": "the model of `agent:` steps, e.g. sonnet (default Claude Code's own)",
    },
    "horn": {
        "sounds": "one line per key, the most precise wins: `<building>/<event>: <sound>`, `<event>: <sound>`, "
                  "`<building>: <sound>`, `*: <sound>`; a sound is horn, chime, alarm, drum, ding, bell, none "
                  "or an audio file. e.g. [\"mail.received: chime\", \"*: none\"]",
        "default": "the sound when no line matches (default horn)",
        "muted": "true keeps it quiet",
        "quiet": "quiet hours, e.g. 22:00-08:00",
        "cooldown": "seconds between two sounds of one key (default 2)",
    },
    "fields": {
        "path": "TASKS.md (one ## section per lane) or a folder with todo/ in-progress/ done/ and a subfolder "
                "per lane of notes (default TASKS.md)",
        "mode": "board (default: every lane), tasks (the three status lanes, a kanban) or notes (a wall of stickers)",
        "lanes": "lanes of notes that are always there, e.g. [\"Ideas\", \"Questions\"]",
    },
    "barracks": {
        "max_orcs": "how many orks work at once (default 3)",
        "budget_usd": "the most the barracks may spend, in USD",
        "providers": "who may be hired, `harness[:model]`: claude or agy, e.g. [\"claude:sonnet\", \"agy\"]",
        "worktrees": "each ork in its own git worktree (default true)",
        "orders": "standing orders: the steward's rules, given to every ork with each task",
        "session_tasks": "tasks one ork session takes before it rolls over with a handoff (default 5)",
        "max_reworks": "how many times the steward sends a task back before asking the operator (default 3)",
        "test_cmd": "the command that must pass before the steward reads the diff, e.g. `pytest -q`",
        "steward": "`harness[:model]` of the steward that answers and reviews (default claude)",
        "base": "the branch each task is cut from and its pull request targets (default the current one)",
    },
    "council": {
        "steward_prompt": "the steward's brief: when to let a document go, when to send it back, when to ask you "
                          "(longer briefs live in steward.md)",
        "members": "`Role:harness[:model]`, 2-4 of them, e.g. [\"Product manager:claude\", \"Architect:agy\"]",
        "veto": "roles whose VETO blocks approval, e.g. [\"Security\"]",
        "max_cycles": "reworks of one document before the operator decides (default 3)",
        "budget_usd": "the most one review may spend, in USD (default 2)",
        "moderator": "`harness[:model]` of the steward (default claude)",
        "goal": "an older debate's setting: read as the steward's brief when steward_prompt is empty",
        "max_rounds": "an older debate's setting; still loads, not used",
    },
    "war_drum": {
        "ics": "an .ics file in the project or an https URL (+ adds events to its own file)",
        "day_starts": "when calendar.day_schedule goes out, HH:MM (default 08:00)",
        "lead": "how long before a meeting calendar.event_upcoming goes out, e.g. 2h, 1d, 1h30m (default 2h)",
    },
    "forest": {"path": "the folder to show (default the project)"},
    "scrolls": {
        "paths": "folders of notes (the older `sources`), e.g. [\"docs\", \"notes\"]",
        "sources": "what the wiki is made from, read-only: a notes folder `docs`, `code:src`, `git:<rev>[:<folder>]`, "
                   "`confluence:<SPACE>[@<site>]`, e.g. [\"docs\", \"code:src\"]",
        "wiki": "the wiki's folder (default llm-wiki/<topic>/)",
        "topic": "codebase, team, design or general: the sections and rules it starts with",
        "harness": "the librarian's agent: claude (default) or agy",
        "model": "the librarian's model, e.g. sonnet",
        "auto_ingest": "ingest by itself once the sources settle (default true)",
        "commit": "commit every change of the wiki's folder (default true)",
        "review_sample": "pages of each ingest spot-checked (default 2, 0: none)",
        "council": "the id of a Clan Fire that spot-checks them (without it the sample goes out as wiki.review)",
    },
    "lake": {"url": "a page to show on open, e.g. a local dev server http://localhost:3000"},
    "forge": {
        "remote": "not used yet",
        "base": "the branch to merge into (default main)",
        "test_cmd": "the command that must pass before a merge, e.g. `pytest -q`",
        "confirm": "true asks before every merge",
    },
    "loot": {
        "path": "the folder whose generated files wait for review (default the working tree)",
        "review": "rules (default: hold what a rule below catches), always or never",
        "sources": "hold carts from these buildings (ids; keys in a town plan)",
        "paths": "hold changes to these paths, e.g. [\"auth/**\", \"migrations/**\"]",
        "max_cost_usd": "hold a cart whose chain cost more, in USD",
        "max_tokens": "hold a cart whose chain used more tokens",
        "max_files": "hold a change of more files",
        "on_failed": "true holds a cart whose last step failed",
        "external": "true holds what leaves the town (into a Catapult)",
        "max_rework": "times a cart may be sent back before it stays for you (default 3)",
        "rework_tokens": "tokens a cart's chain may spend before it is no longer sent back",
    },
    "crag": {
        "source": "what to chart: limits, spend, tokens, runs, orcs, tasks, cpu, or road (numbers that come by road)",
        "orientation": "vertical (over time) or horizontal (broken down)",
        "window": "1h, 24h or 7d (default 24h)",
        "warn": "a value over it sends charts.threshold",
        "crit": "a value over it sends charts.threshold, critical",
    },
    "catapult": {
        "url": "where to send, http or https",
        "method": "POST, PUT or PATCH (default POST)",
        "schema": "a JSON Schema file in the project the body must pass, e.g. schemas/report.json",
        "wait_for": "the buildings (their ids; keys in a town plan) that must all have sent a cart before it fires; each needs a "
                    "road into the Catapult. Without it every cart fires",
        "token_env": "the environment variable whose token goes as Authorization: Bearer",
        "confirm": "true asks before every shot",
        "mode": "api (default: an HTTP request) or browser (fill the web forms of `forms`)",
        "forms": "browser mode, in fill order: `name = start address | what to open | button` (the last two optional)",
        "fields": "browser mode, which field gets what: `Event name = title`, `Category = \"Major update\"`, "
                  "`images/Banner = banner` for one form",
        "finish": "browser mode: leave (default: you check and press) or press (submit by itself)",
        "repair": "browser mode: false stops the ork repairing a script the site broke (default true)",
        "key": "a body path grouping carts into one shot, e.g. version.tag (two releases never mix)",
        "ttl": "minutes a loaded cart may wait before it is dropped (0: forever)",
    },
    "workshop": {
        "runtime": "python or bash",
        "layout": "log, table or card",
        "steward_prompt": "what the model does with carts the script hands over (exit 3)",
        "inputs": "the events the script expects",
        "schedule": "run on its own: `every 15m`, `hourly`, `daily 05:00`, `weekly mon 09:00` or a 5-field cron",
    },
}


def takes(type_id: str) -> str:
    """What a cart on a plain road makes a building of this type do; "" — nothing."""
    return TAKES.get(ALIASES.get(type_id, type_id), "")


def _param_text(param: Param) -> str:
    typ, allowed, required = param
    if isinstance(allowed, tuple) and typ is str:
        kind = " | ".join(allowed)
    elif isinstance(allowed, tuple) and allowed[1] < 1e9:
        kind = f"number {allowed[0]:g}-{allowed[1]:g}"
    else:
        kind = {str: "text", int: "number", float: "number", bool: "true/false", list: "list of text"}.get(typ, "text")
    return kind + (", required" if required else "")


def catalog_text(types: list[BuildingType] | None = None,
                 detail: bool | Collection[str] = True) -> str:
    """The catalog for the builders' prompts: one block per type. `detail` — True, or the type ids
    whose settings are spelled out with their syntax; the others list only the names."""
    lines = []
    for t in types if types is not None else TYPES.values():
        lines.append(f"- {t.id} ({t.icon} {t.title}, size {t.size}): {t.summary}")
        lines.append(f"    hut shows: {t.preview}; open: {t.full}")
        lines.append(f"    takes from a road: {takes(t.id) or 'nothing — a road into it only shows a note'}")
        if t.events:
            lines.append("    events: " + "; ".join(f"{e.id} [{e.kind}] — {e.help}" for e in t.events))
        if t.actions:
            lines.append("    quick actions: " + "; ".join(f"{a.id} ({a.glyph} {a.label})" for a in t.actions))
        if EFFECTS.get(t.id):
            lines.append(f"    acts outside the camp: {EFFECTS[t.id]}")
        if not t.config:
            continue
        if detail is True or (detail is not False and t.id in detail):
            lines.append("    config:")
            help_ = CONFIG_HELP.get(t.id, {})
            lines.extend(f"      {k} ({_param_text(p)}): {help_.get(k, '')}".rstrip(": ") for k, p in t.config.items())
        else:
            lines.append("    config: " + ", ".join(f"{k}{'' if r[2] else '?'}" for k, r in t.config.items()))
    return "\n".join(lines)
