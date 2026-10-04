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
        "Confluence and Figma, a schedule, webhooks on localhost",
        "what came in last, unread mail", "the signals that came in; Enter reads one",
        events=(_e("mail.received", "new mail", TEXT, "a new message arrived: sender, subject, first lines"),
                _e("watch.github", "GitHub event", TEXT, "a GitHub event: PR, issue, release, check"),
                _e("watch.cron", "schedule", TEXT, "the schedule fired"),
                _e("watch.webhook", "webhook", TEXT, "a webhook arrived on localhost: its body"),
                _e("watch.comment", "comment", TEXT, "a new comment or message in Slack, Jira, Confluence or Figma"),
                _e("watch.mention", "mention", TEXT, "you were mentioned or written to: Slack, Jira, Confluence, Figma")),
        actions=(_a("mail.open_new", "Open new", "✉", "open the newest signal"),
                 _a("mail.refresh", "Check now", "↻", "check every source now")),
        config={"host": (str, None, False), "user_env": (str, None, False), "password_env": (str, None, False),
                "folder": (str, None, False), "port": (int, (1, 65535), False),
                "github": (str, None, False), "cron": (str, None, False),
                "webhook_port": (int, (1024, 65535), False), "webhook_secret_env": (str, None, False),
                "feeds": (list, None, False)},
        art="watchtower", orc="Lookout"),
    BuildingType(
        "totem", "Totem", "🗿", "S",
        "a crossroads: rules (if / switch) send what arrives down one of its roads, no model",
        "the rules, the last route taken", "the rules and what went where",
        events=(_e("totem.routed", "routed", TEXT, "what arrived, sent down the route its rule picked"),
                _e("totem.unmatched", "no rule", TEXT, "no rule matched what arrived")),
        config={"rules": (list, None, False)},
        art="spire", orc="Spirit Guide"),
    BuildingType(
        "mill", "The Mill", "⚙️", "S",
        "deterministic work without a model: regexes, CSV → JSON, templates, a script",
        "its steps, the last run", "the steps, what went in and what came out",
        events=(_e("mill.done", "milled", TEXT, "the clean result"),
                _e("mill.failed", "mill failed", TEXT, "a step failed: the error")),
        actions=(_a("mill.run", "Run", "▶", "run the steps on the last input"),),
        config={"steps": (list, None, False)},
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
        "a terminal kanban: to do, in progress, done, with dependencies",
        "counts per column, * when something is new", "the three columns; move and edit tasks",
        events=(_e("tasks.status_changed", "task moved", NODE, "a task changed its status (from → to)"),
                _e("tasks.created", "task added", NODE, "a new task was added")),
        actions=(_a("tasks.new", "New task", "+", "add a task to To Do"),),
        config={"path": (str, None, False)},
        art="burrow", orc="Taskmaster"),
    BuildingType(
        "barracks", "Barracks", "🏕️", "M",
        "a pool of workers in git worktrees: a follow-up goes to the orc who did the earlier task, a new "
        "task gets an idle or newly hired orc (the foreman picks the provider and model) or waits",
        "each orc with its model and task, the queue length, 🔥 when one asks",
        "the orcs, their worktrees and sessions, the queue and the foreman's decisions",
        events=(_e("pool.assigned", "task assigned", TEXT, "the foreman gave a task to an orc (new or follow-up)"),
                _e("pool.done", "task done", TEXT, "an orc finished a task: its result and branch"),
                _e("pool.failed", "task failed", TEXT, "an orc failed a task: the error"),
                _e("pool.idle", "queue empty", TEXT, "every task is done, the orcs are idle")),
        actions=(_a("pool.hire", "Hire orc", "+", "hire one more orc now"),
                 _a("pool.pause", "Pause / resume", "⏸", "stop or resume taking tasks")),
        config={"max_orcs": (int, (1, 10), False), "budget_usd": (float, (0, 200), False),
                "providers": (list, None, False), "worktrees": (bool, None, False), "orders": (str, None, False),
                "session_tasks": (int, (1, 20), False)},
        art="barracks", orc="Grunts", agentic=True),
    BuildingType(
        "council", "Orc Council", "🔥", "M",
        "2–4 agents with roles (architect, tester, security) debate until they agree on a decision or RFC",
        "the members and their roles, 🔥 when one asks", "the debate round by round, the decision",
        events=(_e("team.artifact_ready", "decision ready", FILE, "the council agreed: the decision"),),
        actions=(_a("team.add", "Add member", "+", "add a member: role and model"),
                 _a("team.start", "Start", "▶", "start a debate")),
        config={"goal": (str, None, False), "max_rounds": (int, (1, 20), False),
                "budget_usd": (float, (0, 100), False), "members": (list, None, False),
                "moderator": (str, None, False)},
        art="great_hall", orc="Chieftains", agentic=True),
    BuildingType(
        "war_drum", "War Drum", "🥁", "L",
        "the day's rhythm from a calendar (.ics file or URL): what is now, what is next",
        "what is now, what is next, how much is left today", "the day and the week; add an event",
        events=(_e("calendar.event_due", "event starts", TEXT, "an event is starting now"),
                _e("calendar.event_added", "event added", TEXT, "an event was added"),
                _e("calendar.event_removed", "event removed", TEXT, "an event was removed"),
                _e("calendar.day_schedule", "day schedule", TEXT, "the morning digest: today's events")),
        actions=(_a("calendar.new", "New event", "+", "add an event"),),
        config={"ics": (str, None, False), "day_starts": (str, None, False)},
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
        "the project's LLM wiki: the Scroll Scrapper turns read-only sources (notes, code, a git revision, "
        "a Confluence space) into linked pages, an index and a log, keeps them current and lints them",
        "pages, sources, what is not taken in yet", "the wiki's pages and the sources; i ingests, l lints",
        events=(_e("knowledge.changed", "knowledge changed", FILE, "a source or a wiki page was added or changed"),
                _e("knowledge.chunks", "wiki context", TEXT, "a task with the wiki's index, for the agent to read from"),
                _e("wiki.updated", "wiki updated", TEXT, "an ingest finished: the pages added, changed, marked stale"),
                _e("wiki.linted", "wiki linted", TEXT, "a lint finished: the problems it found")),
        actions=(_a("wiki.ingest", "Ingest", "⟳", "take the new and changed sources into the wiki"),
                 _a("wiki.lint", "Lint", "🧹", "check the wiki for contradictions, stale facts, orphans"),
                 _a("knowledge.add", "Add base", "+", "connect a folder as a source")),
        config={"paths": (list, None, False), "sources": (list, None, False), "wiki": (str, None, False),
                "harness": (str, ("claude", "agy"), False), "model": (str, None, False),
                "auto_ingest": (bool, None, False)},
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
        "the store of finished things: generated files to accept or roll back, reports and releases with "
        "what they cost",
        "files to review, what landed", "a file's preview; accept keeps it, reject rolls it back",
        events=(_e("generator.accepted", "file accepted", FILE, "a generated file was accepted"),
                _e("generator.rejected", "file rejected", FILE, "a generated file was rejected"),
                _e("loot.stored", "stored", FILE, "something landed in ./loot/")),
        actions=(_a("generator.accept_all", "Accept all", "✓", "accept every file still waiting"),),
        config={"path": (str, None, False)},
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
        "its orc finds each form, a Playwright script fills them in turn and presses submit or hands them to you",
        "what it waits for, the last shot", "the loaded data, the check, the request or the form, and its answer",
        events=(_e("catapult.sent", "sent", TEXT, "the request went out (or the form was filled): the answer"),
                _e("catapult.failed", "failed", TEXT, "the check, the request or the form failed"),
                _e("catapult.repaired", "repaired", TEXT, "the site changed: the overseer rewrote the fill script")),
        actions=(_a("catapult.fire", "Fire", "🎯", "send what is loaded now"),
                 _a("catapult.dry_run", "Dry run", "🧪", "show the request (or which field gets what) without sending it"),
                 _a("catapult.scout", "Scout", "🔭", "browser mode: the orc finds every form of the intent and writes their scripts")),
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
           "calendar": "war_drum", "file_tree": "forest", "knowledge": "scrolls", "git": "forge",
           "generator": "loot", "charts": "crag"}


def migrate(spec: dict) -> dict:
    """A spec of an old type as its camp building (a copy; the file on disk is left as it is).

    Agent / Script folds in: a script becomes a Mill step, an agent a Barracks of one orc whose
    standing orders are the skill."""
    tid = spec.get("type")
    if tid in ALIASES:
        return {**spec, "type": ALIASES[tid]}
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
    if tid == "totem" and isinstance(config.get("rules"), list):
        from orkcraft.realm import totem
        errors += [f"config: rules: {e}" for e in totem.rules_of(config["rules"])[1]]
    if tid != DEFAULT_TYPE:
        for key, (_, _, required) in t.config.items():
            if required and key not in config:
                errors.append(f"config: {tid} needs {key!r}")
    return errors


# What the operator wants done → the camp buildings that do it (the preset picker's first step).
# Every type stands under exactly one intent, in the order the operator is likely to need it.
INTENTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Take in what I drop, paste or receive", ("pit", "watchtower")),
    ("Sort and transform it — no model", ("totem", "mill")),
    ("Plan and track the work", ("fields", "war_drum")),
    ("Put agents to work", ("barracks", "council")),
    ("Know the project: files, notes, diffs", ("forest", "scrolls", "lake")),
    ("Ship the results: merge, keep, send", ("forge", "loot", "catapult")),
    ("Watch load, limits and spend", ("crag",)),
    ("Hear what comes in", ("horn",)),
)


def catalog_text(types: list[BuildingType] | None = None) -> str:
    """The catalog for the wizard's AI prompt: one block per type."""
    lines = []
    for t in types if types is not None else TYPES.values():
        lines.append(f"- {t.id} ({t.icon} {t.title}, size {t.size}): {t.summary}")
        lines.append(f"    hut shows: {t.preview}; open: {t.full}")
        if t.events:
            lines.append("    events: " + "; ".join(f"{e.id} — {e.help}" for e in t.events))
        if t.actions:
            lines.append("    quick actions: " + "; ".join(f"{a.id} ({a.glyph} {a.label})" for a in t.actions))
        if t.config:
            lines.append("    config: " + ", ".join(f"{k}{'' if r[2] else '?'}" for k, r in t.config.items()))
    return "\n".join(lines)
