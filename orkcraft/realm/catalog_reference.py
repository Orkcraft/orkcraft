"""What the preset picker and the builders read of the catalog: intents, carts, effects and settings.

Part of orkcraft.realm.catalog, which re-exports every name here: import it from there."""
from __future__ import annotations

from collections.abc import Collection

from orkcraft.realm.catalog import ALIASES, FILE, NODE, TEXT, TYPES, BuildingType, Param, type_of


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
    "fields": "anything: the cart becomes a card — a task in To Do (a note in `notes` mode; one of your to-dos "
              "when its route is in mine_routes); its title, else its first line, the rest its text → tasks.created / "
              "notes.created. A cart about one of its own cards (a Barracks' pool.assigned / pool.done / pool.failed "
              "on a return road) moves that card: In Progress with the ork, Done with the result, back to To Do",
    "barracks": "anything: the cart becomes a task for an ork (the title names it, the text is the brief); "
                "its steward reviews the work → pool.done (with the pull request) / pool.failed; a post for a service is "
                "drafted first and waits for your approval as pool.question",
    "council": "a document (text or a file, usually a Barracks result): the clan reviews it → team.approved "
               "(let go) or team.rework (sent back straight to the Barracks that wrote it), team.artifact_ready "
               "(the report); a clan that routes also sends what it let go as team.routed with who takes it on",
    "scrolls": "a task (the cart's title and text): goes on with the wiki's map → knowledge.chunks; a Clan Fire's "
               "verdict lands in reviews.md",
    "war_drum": "a cart tagged [meet:<id>] or under a meeting's ref (e.g. Barracks' pool.done for its "
                "event_upcoming, on a return road): the meeting's document and its link → calendar.doc_opened when "
                "opened; any other cart with a `When:` line (a triage's team.routed for a meeting): a new event, "
                "titled as the cart → calendar.event_added",
    "lake": "a file, a diff, Markdown, a branch or a URL: shows it",
    "forge": "a cart naming one of the repository's branches (e.g. Barracks' pool.done): tests it and "
             "squash-merges it into the base",
    "loot": "anything finished: by its rules it passes (loot.passed) or waits for the operator, who accepts it "
            "or sends it back to a Barracks for rework (loot.rework); stored → loot.stored",
    "crag": "the first number in the cart: a sample of the `road` source",
    "catapult": "anything: loads it under its source building; fires once every building of `wait_for` has loaded",
    "workshop": "anything (a file as its content): its script runs on the cart",
}

# What payload kinds a plain road may bring each type of TAKES: a road whose event carries another kind
# is offered only with a handler. A type not here takes nothing by a plain road.
_ANY = frozenset({TEXT, FILE, NODE})
ACCEPTS: dict[str, frozenset[str]] = {
    "signpost": _ANY, "horn": _ANY, "fields": _ANY, "barracks": _ANY, "loot": _ANY, "catapult": _ANY,
    "workshop": _ANY, "lake": _ANY,
    "mill": frozenset({TEXT, FILE}), "council": frozenset({TEXT, FILE}), "war_drum": frozenset({TEXT, FILE}),
    "scrolls": frozenset({TEXT}), "forge": frozenset({TEXT}), "crag": frozenset({TEXT}),
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
    "lake": "fetches `url` over the network; writes the files you edit in it",
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
        "user": "the mailbox address as written (no secret), e.g. ann@gmail.com — in place of user_env",
        "user_env": "the environment variable that holds the mail login, e.g. MAIL_USER",
        "password_env": "the environment variable that holds the mail password, e.g. MAIL_PASSWORD, or a login kept on this machine (keychain:gmail-ann@gmail.com)",
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
        "model": "the model of `agent:` steps, e.g. sonnet (default its steward's: the tier picked for its agent "
                 "steps, else the building's goal's)",
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
        "mine_routes": "routes whose carts become your own to-dos instead of tasks for the orks, e.g. [\"human\"] "
                       "(a Clan Fire that triages names the route)",
        "send_new": "true: every new task goes down the roads as it is (tasks.sent), as if s were pressed — "
                    "a Barracks takes it and its results come back to the card on a return road",
        "wikis": "the Scroll Dumps a card's context comes from, e.g. [\"kb\"] (default every one in the town; [] none)",
        "private_todos": "true: every to-do of your own is personal — never sent to a model (no plan, its title its first words)",
        "plan_model": "the model a to-do's plan is asked of: a tier (laborer, warrior) or a model (default its "
                      "steward's: the tier picked for Plan the to-dos, else the building's goal's)",
    },
    "barracks": {
        "max_orcs": "how many orks work at once (default 3)",
        "budget_usd": "the most the barracks may spend, in USD",
        "providers": "who the steward may hire, `harness[:model]`: main (the main tool), claude, agy, codex, hermes, pi or cursor, e.g. [\"main\", \"agy\"]; "
                     "without a model the task's tier picks it (elder · warrior · laborer), a named model is kept",
        "worktrees": "each ork in its own git worktree (default true)",
        "orders": "standing orders: the steward's rules, given to every ork with each task",
        "session_tasks": "tasks one ork session takes before it rolls over with a handoff (default 5)",
        "max_reworks": "how many times the steward sends a task back before asking the operator (default 3)",
        "test_cmd": "the command that must pass before the steward reads the diff, e.g. `pytest -q`",
        "steward": "`harness[:model]` of the steward that plans, answers and reviews (default main, the main tool: an elder plans, "
                   "a warrior reviews a part, the building's goal picks who looks at the whole)",
        "plan": "false: every task goes whole to one ork, the steward never plans it into parts (default true)",
        "escalate": "false: a task sent back keeps its tier instead of going up one (default true)",
        "base": "the branch each task is cut from and its pull request targets (default the current one)",
        "notes": "Scroll Dumps a task reads first, e.g. [\"notes\"]: the task goes to them and comes back with the "
                 "pages that matter (knowledge.chunks on a road from them) before an ork takes it",
    },
    "council": {
        "steward_prompt": "the steward's brief: when to let a document go, when to send it back, when to ask you "
                          "(longer briefs live in steward.md)",
        "members": "`Role:harness[:model]`, 2-4 of them, e.g. [\"Product manager:main\", \"Architect:agy\"]",
        "purpose": "what the board reviews and what matters, in words; its clan and exits are set up from it",
        "exits": "where a judged document can go, `Name: when to take it`, e.g. [\"To development: ready to build\"]; "
                 "each is a route a road out waits for; Back to the author and Ask me are built in",
        "veto": "roles whose VETO blocks approval, e.g. [\"Security\"]",
        "max_cycles": "reworks of one document before the operator decides (default 3)",
        "budget_usd": "the most one review may spend, in USD (default 2)",
        "moderator": "`harness[:model]` of the steward (default its steward's tool, else main; its model the tier "
                     "picked for Let the document go, else the building's goal's)",
        "routes": "who it may route what it lets go to, e.g. [\"human\", \"agent\"] (triage): the steward names "
                  "one, team.routed carries it and each road out may wait for one route; when the steward "
                  "also names a time (WHEN:), the document goes on after a `When:` line (a War Drum adds the event)",
        "goal": "an older debate's setting: read as the steward's brief when steward_prompt is empty",
        "max_rounds": "an older debate's setting; still loads, not used",
    },
    "war_drum": {
        "ics": "an .ics file in the project or an https URL (+ adds events to its own file)",
        "day_starts": "when calendar.day_schedule goes out, HH:MM (default 08:00)",
        "lead": "how long before a meeting calendar.event_upcoming goes out, e.g. 2h, 1d, 1h30m (default 2h)",
        "prepare_new": "true: a new event (by a road or New event) sends calendar.event_upcoming at once, so its "
                       "document is prepared right away",
        "beats": "what the timeline shows: [\"meeting\", \"schedule\", \"limit\"] (default all three); "
                 "[\"meeting\"] for a calendar of meetings alone",
    },
    "forest": {"path": "the folder to show (default the project)"},
    "scrolls": {
        "paths": "folders of notes (the older `sources`), e.g. [\"docs\", \"notes\"]",
        "sources": "what the wiki is made from, read-only: a notes folder `docs`, `code:src`, `git:<rev>[:<folder>]`, "
                   "`confluence:<SPACE>[@<site>]`, e.g. [\"docs\", \"code:src\"]",
        "wiki": "the wiki's folder (default llm-wiki/<topic>/)",
        "topic": "codebase, team, design or general: the sections and rules it starts with",
        "harness": "the librarian's agent: main (the main tool, default) or one of claude, agy, codex, hermes, pi, cursor",
        "model": "the librarian's model, e.g. sonnet",
        "auto_ingest": "ingest by itself once the sources settle (default true)",
        "commit": "commit every change of the wiki's folder (default true)",
        "review_sample": "pages of each ingest spot-checked (default 2, 0: none)",
        "council": "the id of a Clan Fire that spot-checks them (without it the sample goes out as wiki.review)",
    },
    "lake": {"url": "a page to show on open, e.g. a local dev server http://localhost:3000",
             "autosave": "while a file is edited, save it every this many seconds when it changed (default 5); "
                         "it also saves when the editor loses focus"},
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
        "charts": "its dashboard, a chart per line: `Title = source [1h|24h|7d] [vertical|horizontal] [warn N] [crit N] "
                  "[all|command|full]` (where it shows: the hut too, the Command Card, the dashboard only); "
                  "without it one chart from the settings above",
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


def accepts(spec: dict | None) -> frozenset[str]:
    """The payload kinds a building of this spec takes by a plain road (none: only through a handler)."""
    return ACCEPTS.get(type_of(spec).id, frozenset()) if spec else frozenset()


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
