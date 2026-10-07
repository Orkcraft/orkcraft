"""Who the operator is and what their first town is for (design: docs/design/onboarding.md).

    ROLES, INDUSTRIES                       the onboarding's first question: who you are, where you work
    for_role("aso_manager", day)            the role's intents, the ones that fit your day first
    intent("review_desk").plan              a whole town, in the Town Builder's answer shape
    templates_text("aso_manager")           the role's templates, for the Town Builder to adapt

An intent is a ready town for a job a role does: buildings from the catalog and plain roads, in the
shape `town_builder.check` takes, so a picked intent is raised with no model call. When none fits,
the interview (realm/interview.py) asks about the operator's sources, outputs and problems, and the
Town Builder adapts the role's templates to the answers.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Choice:
    id: str
    icon: str
    title: str

    @property
    def label(self) -> str:
        return f"{self.icon} {self.title}"


@dataclass(frozen=True)
class Role:
    id: str
    icon: str
    title: str
    mascot: str                               # orc · elf · lich · gnome · goblin · knight · skeleton
    sources: tuple[str, ...] = ()             # interview options most people in the role use
    outputs: tuple[str, ...] = ()
    nick: str = ""                            # the mascot's name: Burnout Peon, The Jira Lich, Indie Knight…

    @property
    def label(self) -> str:
        return f"{self.icon} {self.title}"


@dataclass(frozen=True)
class Intent:
    id: str
    role: str
    icon: str
    title: str
    blurb: str
    plan: dict = field(hash=False, compare=False)
    day: tuple[str, ...] = ()                 # the parts of a day it takes over (interview.DAY ids)

    @property
    def label(self) -> str:
        return f"{self.icon} {self.title}"


OTHER = "other"

MASCOTS: dict[str, tuple[str, ...]] = {
    "orc": ("   ,      ,   ",
            "  /(.-\"\"-.)\\  ",
            "  \\  o  o  /  ",
            "   | v  v |   ",
            "   \\ '--' /   ",
            "  _/`----`\\_  ",
            " /  ORK   \\_\\ "),
    "elf": ("      /\\      ",
            "  <\\ (  ) />  ",
            "    \\ -- /    ",
            "   /|    |\\   ",
            "  / | ** | \\  ",
            "    |    |    ",
            "    / ELF\\    "),
    "knight": ("     _||_     ",
               "    /____\\    ",
               "    |-==-|    ",
               "    \\____/    ",
               "  [|  ++  |]  ",
               "   |  ++  |   ",
               "   /KNIGHT\\   "),
    "gnome": ("      /\\      ",
              "     /  \\     ",
              "    /____\\    ",
              "   ( o  o )   ",
              "   (  <>  )   ",
              "    \\_~~_/    ",
              "   /GNOME\\    "),
    "lich": ("   _/\\/\\/\\_   ",
             "   \\ .--. /   ",
             "    ( xx )    ",
             "   /|~~~~|\\   ",
             "  / | ** | \\  ",
             "    |____|    ",
             "    /LICH\\    "),
    "goblin": ("  ,        ,  ",
               "  \\`.____.'/  ",
               "   ( o  O )   ",
               "  < \\ ww / >  ",
               "   _|    |_ $ ",
               "  / |____| \\  ",
               "   /GOBLIN\\   "),
    "skeleton": ("    .----.    ",
                 "   ( o  o )   ",
                 "    | ^^ |    ",
                 "    '-==-'    ",
                 "   --|##|--   ",
                 "     |##|     ",
                 "  /SKELETON\\  "),
}

ROLES: tuple[Role, ...] = (
    Role("engineer", "🛠", "Software engineer", "orc",
         ("github", "jira", "slack", "sentry", "repo"), ("github", "jira", "slack"), "Burnout Peon"),
    Role("qa", "🧪", "QA engineer", "orc",
         ("jira", "github", "sentry", "repo"), ("jira", "slack", "md_reports"), "Bug Ork"),
    Role("eng_manager", "🧭", "Engineering manager", "lich",
         ("jira", "github", "slack", "gcal", "confluence"), ("confluence", "slack", "md_reports"), "The Jira Lich"),
    Role("product_manager", "📋", "Product manager", "lich",
         ("jira", "confluence", "analytics", "slack", "mail"), ("confluence", "jira", "slack"), "Roadmap Wraith"),
    Role("designer", "🎨", "Product designer", "elf",
         ("figma", "jira", "notion", "slack"), ("figma", "jira", "slack"), "Gradient-Sick Elf"),
    Role("game_designer", "🎮", "Game designer", "elf",
         ("confluence", "gsheets", "jira", "files"), ("confluence", "gsheets", "jira"), "Lore Elf"),
    Role("aso_manager", "📈", "ASO manager", "gnome",
         ("app_store", "google_play", "aso_tools", "analytics", "gsheets"), ("gsheets", "app_store", "slack"),
         "Keyword Gnome"),
    Role("marketing", "📣", "Marketing / growth manager", "gnome",
         ("analytics", "gsheets", "crm", "slack", "notion"), ("gdocs", "slack", "asana"), "Growth-Hack Gnome"),
    Role("data_analyst", "📊", "Data analyst", "goblin",
         ("analytics", "gsheets", "files", "jira"), ("gsheets", "md_reports", "slack"), "Data-Mining Goblin"),
    Role("founder", "🛡", "Founder / indie maker", "knight",
         ("mail", "github", "analytics", "notion"), ("github", "notion", "mail"), "Indie Knight"),
    Role(OTHER, "🧩", "Someone else", "skeleton", ("mail", "slack", "gdrive", "files"), ("gdocs", "slack", "mail"),
         "Wandering Skeleton"),
)

INDUSTRIES: tuple[Choice, ...] = (
    Choice("gaming", "🎮", "Gaming"),
    Choice("fintech", "💳", "Fintech"),
    Choice("ecommerce", "🛒", "E-commerce"),
    Choice("saas", "☁️", "SaaS / B2B"),
    Choice("health", "🩺", "Health"),
    Choice("media", "📺", "Media and content"),
    Choice("edtech", "🎓", "Education"),
    Choice("agency", "🤝", "Agency / outsourcing"),
    Choice(OTHER, "🧩", "Something else"),
)

INDUSTRY_SOURCES: dict[str, tuple[str, ...]] = {
    "gaming": ("app_store", "google_play", "analytics"),
    "fintech": ("jira", "confluence", "sentry"),
    "ecommerce": ("analytics", "crm", "gsheets"),
    "saas": ("jira", "zendesk", "crm"),
    "health": ("jira", "confluence", "zendesk"),
    "media": ("analytics", "gdrive", "notion"),
    "edtech": ("analytics", "zendesk", "gdrive"),
    "agency": ("asana", "slack", "mail"),
}


# -- the templates: whole towns in the Town Builder's answer shape --------------------------------

def _b(key: str, type_: str, title: str, icon: str, why: str, **config) -> dict:
    b = {"key": key, "type": type_, "title": title, "icon": icon, "why": why}
    return {**b, "config": config} if config else b


def _r(src: str, event: str, dst: str, why: str, route: str = "") -> dict:
    r = {"from": src, "event": event, "to": dst, "why": why}
    return {**r, "route": route} if route else r


def _plan(title: str, summary: str, buildings: list[dict], roads: list[dict]) -> dict:
    return {"title": title, "summary": summary, "buildings": buildings, "roads": roads}


INTENTS: tuple[Intent, ...] = (
    # -- 🛠 software engineer ----------------------------------------------------------------------
    Intent("solo_forge", "engineer", "🛠", "Solo Forge", "tasks → agents in worktrees → tests → merge",
           _plan("Solo Forge", "One developer: tasks go to agents, finished branches are tested and merged.",
                 [_b("tasks", "fields", "Tasks", "📋", "what to do, one card per change"),
                  _b("crew", "barracks", "Agent crew", "🏕️", "agents take tasks in their own worktrees"),
                  _b("merge", "forge", "Merge forge", "⚒️", "tests a finished branch and squash-merges it"),
                  _b("diffs", "lake", "Diff view", "🌊", "the diff of every opened PR, side by side")],
                 [_r("tasks", "tasks.created", "crew", "a new task goes to a free agent"),
                  _r("crew", "pool.done", "merge", "a finished branch goes to tests and merge"),
                  _r("merge", "git.pr_opened", "diffs", "you read the diff before merging")]),
           day=("build", "review")),
    Intent("review_gate", "engineer", "🔍", "Review Gatehouse", "PRs come in, a clan of agents reviews, you read the verdict",
           _plan("Review Gatehouse", "Every pull request is reviewed by agents before you look at it.",
                 [_b("prs", "watchtower", "Pull requests", "🗼", "GitHub events of the repository"),
                  _b("review", "council", "Review fire", "🪔", "an architect, a tester and a security agent review it",
                     members=["Architect:claude", "Tester:claude", "Security:claude"], veto=["Security"]),
                  _b("notes", "loot", "Review notes", "📦", "the clan's reports, to accept or drop")],
                 [_r("prs", "watch.github", "review", "a new PR is reviewed at once"),
                  _r("review", "team.artifact_ready", "notes", "the verdict lands where you read it")]),
           day=("review",)),
    Intent("bug_hunt", "engineer", "🐛", "Bug Hunt", "paste a bug report, it is triaged and fixed in a worktree",
           _plan("Bug Hunt", "Bug reports are triaged by rules and fixed by agents in worktrees.",
                 [_b("reports", "pit", "Bug reports", "🕳️", "paste a stack trace or a ticket link"),
                  _b("triage", "signpost", "Triage", "🚏", "routes by severity, no model",
                     rules=["bug: matches (?i)bug|crash|error|exception|traceback|broken"]),
                  _b("fixers", "barracks", "Fixers", "🏕️", "agents reproduce and fix in worktrees"),
                  _b("merge", "forge", "Merge forge", "⚒️", "tests and merges the fix")],
                 [_r("reports", "pit.text", "triage", "every report is sorted first"),
                  _r("triage", "signpost.routed", "fixers", "real bugs go to the fixers", "bug"),
                  _r("fixers", "pool.done", "merge", "a fix is tested and merged")]),
           day=("firefight", "build")),
    # -- 🧭 engineering manager --------------------------------------------------------------------
    Intent("team_pulse", "eng_manager", "💓", "War Drum Report", "what the team shipped, as a weekly digest",
           _plan("War Drum Report", "GitHub activity milled into a weekly digest of what shipped and what is stuck.",
                 [_b("activity", "watchtower", "Team activity", "🗼", "PRs, reviews and releases from GitHub"),
                  _b("digest", "mill", "Digest", "⚙️", "groups the week's events by person and project"),
                  _b("reports", "loot", "Weekly reports", "📦", "the digest, ready to send"),
                  _b("load", "crag", "Throughput", "🪨", "tasks moved per day")],
                 [_r("activity", "watch.github", "digest", "every event feeds the digest"),
                  _r("digest", "mill.done", "reports", "the digest becomes a report")]),
           day=("reports", "metrics")),
    Intent("incident_room", "eng_manager", "🚨", "Alarm Tower", "alerts sound, agents draft the postmortem",
           _plan("Alarm Tower", "Alerts are announced at once and every incident ends with a postmortem draft.",
                 [_b("alerts", "watchtower", "Alerts", "🗼", "webhooks from monitoring"),
                  _b("alarm", "horn", "Alarm", "📯", "a sound you cannot miss"),
                  _b("scribes", "barracks", "Incident scribes", "🏕️", "agents reconstruct what happened"),
                  _b("review", "council", "Postmortem fire", "🪔", "an SRE and a dev agent review the draft",
                     members=["SRE:claude", "Developer:claude"]),
                  _b("postmortems", "loot", "Postmortems", "📦", "drafts to review and publish")],
                 [_r("alerts", "watch.webhook", "alarm", "every alert is heard"),
                  _r("alerts", "watch.webhook", "scribes", "the scribes start collecting the timeline"),
                  _r("scribes", "pool.done", "review", "the draft is reviewed; a rework goes back to the scribes"),
                  _r("review", "team.approved", "postmortems", "the draft waits for you")]),
           day=("firefight",)),
    Intent("one_on_ones", "eng_manager", "🤝", "1:1 War Tent", "your calendar preps every 1:1 and keeps the action items",
           _plan("1:1 War Tent", "The day's meetings are prepared from your notes; action items become tasks.",
                 [_b("calendar", "war_drum", "Calendar", "🥁", "today's 1:1s and syncs"),
                  _b("notes", "scrolls", "Meeting notes", "🗑️", "what was said, per person"),
                  _b("prep", "mill", "Prep sheet", "⚙️", "the last notes and open items for each meeting"),
                  _b("actions", "fields", "Action items", "📋", "what you promised, as tasks")],
                 [_r("calendar", "calendar.day_schedule", "prep", "every morning the day's meetings are prepared"),
                  _r("notes", "knowledge.changed", "actions", "new notes surface their action items")]),
           day=("meetings", "planning")),
    # -- 📋 product manager ------------------------------------------------------------------------
    Intent("war_room", "product_manager", "🗺", "War Room", "tasks, mail and the calendar in one daily digest",
           _plan("War Room", "Requests from mail become tasks; every morning a digest of the day and the board.",
                 [_b("inbox", "watchtower", "Inbox", "🗼", "mail from the team and stakeholders"),
                  _b("board", "fields", "Board", "📋", "every request as a task"),
                  _b("calendar", "war_drum", "Calendar", "🥁", "the day's meetings"),
                  _b("digest", "mill", "Morning digest", "⚙️", "meetings and moved tasks in one page"),
                  _b("reports", "loot", "Digests", "📦", "the daily pages")],
                 [_r("inbox", "mail.received", "board", "a request becomes a task"),
                  _r("calendar", "calendar.day_schedule", "digest", "the day starts with a digest"),
                  _r("digest", "mill.done", "reports", "the digest is kept")]),
           day=("mail", "planning", "meetings")),
    Intent("prd_forge", "product_manager", "📜", "PRD Forge", "research drops in, an agent drafts the PRD, a clan reviews it",
           _plan("PRD Forge", "Research notes and links feed an agent that drafts PRDs; a clan of agents reviews each one.",
                 [_b("drops", "pit", "Research drops", "🕳️", "interview notes, links, screenshots"),
                  _b("research", "scrolls", "Research base", "🗑️", "everything you learned, as a wiki"),
                  _b("writers", "barracks", "PRD writers", "🏕️", "an agent drafts the PRD"),
                  _b("review", "council", "PRD fire", "🪔", "a PM, an engineer and a designer agent review it",
                     members=["Product manager:claude", "Engineer:claude", "Designer:claude"]),
                  _b("prds", "loot", "PRDs", "📦", "drafts to accept and publish")],
                 [_r("drops", "pit.text", "research", "new research goes through the wiki"),
                  _r("research", "knowledge.chunks", "writers", "the draft starts with the wiki's map"),
                  _r("writers", "pool.done", "review", "every draft is reviewed; a rework goes back to the writer"),
                  _r("review", "team.approved", "prds", "the PRD waits for you")]),
           day=("reports", "research")),
    Intent("feedback_loop", "product_manager", "🔁", "Feedback Signpost", "user feedback sorted into requests and insights",
           _plan("Feedback Signpost", "Feedback from support and mail is sorted: requests to the board, the rest to insights.",
                 [_b("feedback", "watchtower", "Feedback", "🗼", "support webhooks and mail"),
                  _b("sort", "signpost", "Sorter", "🚏", "a request, a bug or an insight — by rules",
                     rules=["request: matches (?i)feature|please add|would love|wish|request|bug|crash"]),
                  _b("requests", "fields", "Feature requests", "📋", "requests as tasks, with votes"),
                  _b("insights", "scrolls", "Insights", "🗑️", "everything else, searchable")],
                 [_r("feedback", "watch.webhook", "sort", "every message is sorted"),
                  _r("sort", "signpost.routed", "requests", "requests go to the board", "request"),
                  _r("sort", "signpost.unmatched", "insights", "the rest is kept as insight")]),
           day=("users", "planning")),
    # -- 🎨 product designer -----------------------------------------------------------------------
    Intent("mockup_grove", "designer", "🌳", "Mockup Grove", "a brief → mockup variants → you pick",
           _plan("Mockup Grove", "A brief becomes several mockup variants; you accept the one to keep.",
                 [_b("briefs", "pit", "Briefs", "🕳️", "paste a brief or drop a sketch"),
                  _b("studio", "barracks", "Variant studio", "🏕️", "agents draw variants in parallel"),
                  _b("picks", "loot", "Variants", "📦", "accept the variant to keep")],
                 [_r("briefs", "pit.text", "studio", "a brief starts the variants"),
                  _r("studio", "pool.done", "picks", "every variant waits for your pick")]),
           day=("build",)),
    Intent("design_system", "designer", "📐", "Token Smithy", "tokens change, the build and checks run",
           _plan("Token Smithy", "Token files are watched; every change is built and checked for consistency.",
                 [_b("tokens", "forest", "Tokens", "🌲", "the design tokens folder"),
                  _b("build", "mill", "Token build", "⚙️", "tokens → css, tailwind, ts"),
                  _b("output", "loot", "Built tokens", "📦", "the build, to accept"),
                  _b("issues", "fields", "Consistency issues", "📋", "what failed the checks")],
                 [_r("tokens", "files.changed", "build", "a change is built at once"),
                  _r("build", "mill.done", "output", "the build waits for review"),
                  _r("build", "mill.failed", "issues", "a failed check becomes a task")]),
           day=("build", "review")),
    Intent("critique_circle", "designer", "🗣", "Critique Circle", "a clan reviews a design proposal from every side",
           _plan("Critique Circle", "Design proposals go to a clan of agents that reviews them; the reports are kept.",
                 [_b("questions", "pit", "Design proposals", "🕳️", "a screen, a link, a decision to check"),
                  _b("council", "council", "Critique fire", "🪔", "a UX, a brand and an accessibility agent",
                     members=["UX:claude", "Brand:claude", "Accessibility:claude"], veto=["Accessibility"]),
                  _b("decisions", "loot", "Decisions", "📦", "every review and why")],
                 [_r("questions", "pit.text", "council", "a proposal starts the critique"),
                  _r("council", "team.artifact_ready", "decisions", "the review is kept")]),
           day=("review", "meetings")),
    # -- 📈 ASO manager ----------------------------------------------------------------------------
    Intent("keyword_tracker", "aso_manager", "🔑", "Keyword Lookout", "rankings collected weekly, diffed, reported",
           _plan("Keyword Lookout", "Every week agents collect keyword rankings; the Mill diffs them into a report.",
                 [_b("schedule", "watchtower", "Weekly schedule", "🗼", "fires every Monday morning"),
                  _b("collectors", "barracks", "Rank collectors", "🏕️", "agents pull rankings per store and country"),
                  _b("diff", "mill", "Rank diff", "⚙️", "this week against last, per keyword"),
                  _b("reports", "loot", "ASO reports", "📦", "the weekly report, ready to share"),
                  _b("drops", "crag", "Rank drops", "🪨", "warns when a keyword falls")],
                 [_r("schedule", "watch.cron", "collectors", "the week starts with fresh rankings"),
                  _r("collectors", "pool.done", "diff", "rankings are compared"),
                  _r("diff", "mill.done", "reports", "the diff becomes the report")]),
           day=("metrics", "reports")),
    Intent("review_desk", "aso_manager", "⭐", "Review War Tent", "store reviews sorted, replies drafted for approval",
           _plan("Review War Tent", "New store reviews are sorted; agents draft replies, bugs become tasks.",
                 [_b("reviews", "watchtower", "Store reviews", "🗼", "review alerts by webhook or mail"),
                  _b("sort", "signpost", "Review sorter", "🚏", "complaints apart from the rest, no model",
                     rules=["bug: matches (?i)crash|bug|broken|error|freez|doesn.t work", "reply: else"]),
                  _b("writers", "barracks", "Reply writers", "🏕️", "agents draft a reply in the reviewer's language"),
                  _b("replies", "loot", "Replies to approve", "📦", "accept to post"),
                  _b("bugs", "fields", "Bugs from reviews", "📋", "what users say is broken")],
                 [_r("reviews", "watch.webhook", "sort", "every review is sorted"),
                  _r("sort", "signpost.routed", "writers", "reviews that need an answer get a draft", "reply"),
                  _r("writers", "pool.done", "replies", "the draft waits for you"),
                  _r("sort", "signpost.routed", "bugs", "complaints become tasks", "bug")]),
           day=("users",)),
    Intent("listing_lab", "aso_manager", "🧪", "Listing Forge", "competitors and ideas → listing variants to test",
           _plan("Listing Forge", "Competitor listings and ideas feed agents that draft listing variants for A/B "
                                  "tests; a clan reviews them.",
                 [_b("competitors", "pit", "Competitor drops", "🕳️", "links and screenshots of other listings"),
                  _b("notes", "scrolls", "Market notes", "🗑️", "what competitors do, as a wiki"),
                  _b("experiments", "fields", "Experiments", "📋", "the A/B tests to run"),
                  _b("writers", "barracks", "Copywriters", "🏕️", "agents draft listing variants"),
                  _b("council", "council", "Listing fire", "🪔", "a copywriter, an ASO and a brand agent review them",
                     members=["Copywriter:claude", "ASO:claude", "Brand:claude"]),
                  _b("variants", "loot", "Listing variants", "📦", "titles, subtitles, screenshot captions")],
                 [_r("competitors", "pit.link", "notes", "a competitor's move is noted"),
                  _r("experiments", "tasks.created", "writers", "a new experiment gets its variants"),
                  _r("writers", "pool.done", "council", "variants are reviewed; a rework goes back to the writer"),
                  _r("council", "team.approved", "variants", "variants wait for your pick")]),
           day=("research", "build")),
    # -- 📣 marketing / growth ---------------------------------------------------------------------
    Intent("campaign_report", "marketing", "📊", "Campaign Tally", "metrics milled into a weekly report",
           _plan("Campaign Tally", "A weekly schedule pulls the numbers; the Mill writes the report.",
                 [_b("schedule", "watchtower", "Weekly schedule", "🗼", "fires before the weekly sync"),
                  _b("analysts", "barracks", "Number pullers", "🏕️", "agents export the campaign numbers"),
                  _b("report", "mill", "Report mill", "⚙️", "numbers into the report template"),
                  _b("reports", "loot", "Reports", "📦", "ready to share")],
                 [_r("schedule", "watch.cron", "analysts", "the week's numbers are pulled"),
                  _r("analysts", "pool.done", "report", "numbers become the report"),
                  _r("report", "mill.done", "reports", "the report is kept")]),
           day=("metrics", "reports")),
    Intent("content_mill", "marketing", "✍️", "Content Mill", "ideas → drafts → approved posts",
           _plan("Content Mill", "Ideas are drafted by agents into posts you approve.",
                 [_b("ideas", "pit", "Ideas", "🕳️", "paste an idea or a link"),
                  _b("calendar", "fields", "Content plan", "📋", "what goes out when"),
                  _b("writers", "barracks", "Writers", "🏕️", "agents draft posts in your voice"),
                  _b("posts", "loot", "Posts to approve", "📦", "accept to publish")],
                 [_r("ideas", "pit.text", "calendar", "every idea lands on the plan"),
                  _r("calendar", "tasks.created", "writers", "a planned post gets a draft"),
                  _r("writers", "pool.done", "posts", "the draft waits for you")]),
           day=("build", "planning")),
    Intent("launch_crypt", "marketing", "🚀", "Launch Catapult", "a launch plan, its copy and the posts going out",
           _plan("Launch Catapult", "The launch plan drives the copy; approved posts go out through an API.",
                 [_b("plan", "fields", "Launch plan", "📋", "every launch step as a task"),
                  _b("copy", "barracks", "Copywriters", "🏕️", "agents write the launch copy"),
                  _b("approved", "loot", "Copy to approve", "📦", "accept what goes out"),
                  _b("publish", "catapult", "Publisher", "🎯", "sends approved posts to your tool's API")],
                 [_r("plan", "tasks.created", "copy", "each step gets its copy"),
                  _r("copy", "pool.done", "approved", "the copy waits for you"),
                  _r("approved", "generator.accepted", "publish", "what you accept goes out")]),
           day=("build", "planning")),
    # -- 📊 data analyst ---------------------------------------------------------------------------
    Intent("ledger_tower", "data_analyst", "📒", "Ledger Tower", "scheduled metric reports, cleaned and charted",
           _plan("Ledger Tower", "On a schedule the data is pulled, cleaned by the Mill and turned into reports.",
                 [_b("schedule", "watchtower", "Report schedule", "🗼", "daily or weekly"),
                  _b("pull", "barracks", "Query runners", "🏕️", "agents run the queries and exports"),
                  _b("clean", "mill", "Clean and shape", "⚙️", "CSV → tidy JSON, no model"),
                  _b("reports", "loot", "Reports", "📦", "the finished reports")],
                 [_r("schedule", "watch.cron", "pull", "the schedule starts the queries"),
                  _r("pull", "pool.done", "clean", "raw exports are cleaned"),
                  _r("clean", "mill.done", "reports", "clean data becomes the report")]),
           day=("reports", "metrics")),
    Intent("anomaly_watch", "data_analyst", "📉", "Anomaly Watchtower", "metric alerts routed to an alarm and investigations",
           _plan("Anomaly Watchtower", "Metric alerts are checked by rules; real anomalies sound and open an investigation.",
                 [_b("alerts", "watchtower", "Metric alerts", "🗼", "webhooks from your analytics"),
                  _b("rules", "signpost", "Thresholds", "🚏", "which alerts matter, by rules",
                     rules=["anomaly: matches (?i)critical|anomal|spike|drop|breach"]),
                  _b("alarm", "horn", "Alarm", "📯", "a sound for a real anomaly"),
                  _b("cases", "fields", "Investigations", "📋", "one task per anomaly")],
                 [_r("alerts", "watch.webhook", "rules", "every alert is checked"),
                  _r("rules", "signpost.routed", "alarm", "a real anomaly is heard", "anomaly"),
                  _r("rules", "signpost.routed", "cases", "and becomes an investigation", "anomaly")]),
           day=("metrics", "firefight")),
    Intent("adhoc_desk", "data_analyst", "❓", "Question Pit", "questions in, agents answer with queries and charts",
           _plan("Question Pit", "Paste a question; agents answer it with queries, you read the result.",
                 [_b("questions", "pit", "Questions", "🕳️", "paste what someone asked"),
                  _b("analysts", "barracks", "Analyst agents", "🏕️", "agents write and run the query"),
                  _b("view", "lake", "Answer view", "🌊", "the answer with its query"),
                  _b("answers", "loot", "Answers", "📦", "kept for the next time it is asked")],
                 [_r("questions", "pit.text", "analysts", "every question gets an analyst"),
                  _r("analysts", "pool.done", "view", "you read the answer"),
                  _r("analysts", "pool.done", "answers", "and it is kept")]),
           day=("users", "research")),
    # -- 🧪 QA engineer ----------------------------------------------------------------------------
    Intent("regression_run", "qa", "🔁", "Regression Raid", "every PR runs the suites; failures become bugs",
           _plan("Regression Raid", "Opened PRs are tested by agents; failures become bug tasks, passes become reports.",
                 [_b("branches", "forge", "Branches", "⚒️", "PRs and their branches"),
                  _b("runners", "barracks", "Test runners", "🏕️", "agents run and extend the suites"),
                  _b("bugs", "fields", "Bugs", "📋", "every failure as a task"),
                  _b("reports", "loot", "Test reports", "📦", "what passed, what was added")],
                 [_r("branches", "git.pr_opened", "runners", "a new PR is tested"),
                  _r("runners", "pool.failed", "bugs", "a failure becomes a bug"),
                  _r("runners", "pool.done", "reports", "a pass leaves a report")]),
           day=("review", "build")),
    Intent("bug_triage", "qa", "🗂", "Bug Triage Signpost", "reports from everywhere sorted onto one board",
           _plan("Bug Triage Signpost", "Bug reports from mail and pastes are sorted by rules onto one board.",
                 [_b("mail", "watchtower", "Bug mail", "🗼", "reports by mail or webhook"),
                  _b("paste", "pit", "Pasted reports", "🕳️", "logs and screenshots"),
                  _b("sort", "signpost", "Triage rules", "🚏", "severity first, the rest after",
                     rules=["urgent: matches (?i)crash|data loss|outage|p0|critical", "bug: else"]),
                  _b("board", "fields", "Bug board", "📋", "one place for every bug")],
                 [_r("mail", "mail.received", "sort", "mail reports are sorted"),
                  _r("paste", "pit.text", "sort", "pasted reports too"),
                  _r("sort", "signpost.routed", "board", "urgent bugs land on the board", "urgent"),
                  _r("sort", "signpost.routed", "board", "and every other bug too", "bug")]),
           day=("firefight", "users")),
    Intent("release_check", "qa", "✅", "Release Fire", "a go / no-go review before every release",
           _plan("Release Fire", "Before a release a clan of agents reviews the open bugs and test results.",
                 [_b("board", "fields", "Release checklist", "📋", "what must pass"),
                  _b("council", "council", "Go / no-go fire", "🪔", "a QA, a dev and a product agent review it",
                     members=["QA:claude", "Developer:claude", "Product:claude"], veto=["QA"]),
                  _b("verdicts", "loot", "Verdicts", "📦", "the decision with its reasons")],
                 [_r("board", "tasks.status_changed", "council", "the checklist moves, the clan reviews it"),
                  _r("council", "team.artifact_ready", "verdicts", "the verdict is kept")]),
           day=("review", "planning")),
    # -- 🎮 game designer --------------------------------------------------------------------------
    Intent("balance_lab", "game_designer", "⚖️", "Balance Scales", "configs change, balance sheets are rebuilt",
           _plan("Balance Scales", "Game configs are watched; the Mill rebuilds balance sheets you can inspect.",
                 [_b("configs", "forest", "Game configs", "🌲", "the balance and economy files"),
                  _b("sheets", "mill", "Balance sheets", "⚙️", "curves and tables from the configs"),
                  _b("view", "lake", "Balance view", "🌊", "the sheets, side by side with the last ones")],
                 [_r("configs", "files.changed", "sheets", "a change rebuilds the sheets"),
                  _r("sheets", "mill.done", "view", "you see what changed")]),
           day=("build", "metrics")),
    Intent("gdd_council", "game_designer", "📖", "GDD Fire", "ideas → an agent writes GDD pages → a clan reviews them",
           _plan("GDD Fire", "Ideas and references go to an agent that writes GDD pages; a clan reviews each one.",
                 [_b("ideas", "pit", "Ideas", "🕳️", "a mechanic, a reference, a sketch"),
                  _b("gdd", "scrolls", "GDD", "🗑️", "the design document, as a wiki"),
                  _b("writers", "barracks", "GDD writers", "🏕️", "an agent writes the page"),
                  _b("council", "council", "Design fire", "🪔", "a designer, a producer and a player agent review it",
                     members=["Designer:claude", "Producer:claude", "Player:claude"]),
                  _b("pages", "loot", "GDD pages", "📦", "pages to accept into the GDD")],
                 [_r("ideas", "pit.text", "gdd", "an idea goes through the GDD"),
                  _r("gdd", "knowledge.chunks", "writers", "the writer knows what is decided"),
                  _r("writers", "pool.done", "council", "every page is reviewed; a rework goes back to the writer"),
                  _r("council", "team.approved", "pages", "the page waits for you")]),
           day=("build", "reports")),
    Intent("game_jam", "game_designer", "🕹", "Game Jam Camp", "a fast prototype: tasks, agents, builds",
           _plan("Game Jam Camp", "A prototype in days: tasks to agents, branches merged as they pass.",
                 [_b("tasks", "fields", "Jam board", "📋", "what the prototype needs"),
                  _b("crew", "barracks", "Jam crew", "🏕️", "agents build features in parallel"),
                  _b("merge", "forge", "Build forge", "⚒️", "tests and merges each feature")],
                 [_r("tasks", "tasks.created", "crew", "each task gets an agent"),
                  _r("crew", "pool.done", "merge", "finished features are merged")]),
           day=("build",)),
    # -- 💀 founder / indie ------------------------------------------------------------------------
    Intent("one_skeleton_studio", "founder", "🏚", "One-Knight Studio", "code, copy and releases in one town",
           _plan("One-Knight Studio", "One board for everything; agents code and write, you accept and merge.",
                 [_b("tasks", "fields", "Everything board", "📋", "code, copy and chores"),
                  _b("crew", "barracks", "Crew", "🏕️", "agents for code and for copy"),
                  _b("merge", "forge", "Merge forge", "⚒️", "code is tested and merged"),
                  _b("drafts", "loot", "Drafts", "📦", "copy and docs to accept")],
                 [_r("tasks", "tasks.created", "crew", "every task gets an agent"),
                  _r("crew", "pool.done", "merge", "code goes to merge"),
                  _r("crew", "pool.done", "drafts", "copy goes to drafts")]),
           day=("build", "planning")),
    Intent("inbox_keep", "founder", "📨", "Inbox Keep", "mail and GitHub sorted into tasks",
           _plan("Inbox Keep", "Mail and GitHub events are sorted by rules into tasks; the rest is muted.",
                 [_b("inbox", "watchtower", "Inbox", "🗼", "mail and GitHub"),
                  _b("sort", "signpost", "Sorter", "🚏", "what needs you, by rules",
                     rules=["you: matches (?i)urgent|asap|review requested|mention|invoice|deadline|\\?"]),
                  _b("tasks", "fields", "To answer", "📋", "what needs you, as tasks")],
                 [_r("inbox", "mail.received", "sort", "mail is sorted"),
                  _r("inbox", "watch.github", "sort", "GitHub too"),
                  _r("sort", "signpost.routed", "tasks", "what needs you becomes a task", "you")]),
           day=("mail", "users")),
    Intent("side_quest", "founder", "🧪", "Side Quest", "a light town for a pet project",
           _plan("Side Quest", "Drop ideas, keep a small board, let one agent help.",
                 [_b("ideas", "pit", "Ideas", "🕳️", "anything worth doing"),
                  _b("board", "fields", "Board", "📋", "the next few things"),
                  _b("helper", "barracks", "Helper", "🏕️", "one agent at a time")],
                 [_r("ideas", "pit.text", "board", "an idea becomes a task"),
                  _r("board", "tasks.created", "helper", "the helper picks it up")]),
           day=("build",)),
    # -- 🧩 someone else ---------------------------------------------------------------------------
    Intent("task_desk", OTHER, "📋", "Task Camp", "requests from mail become tasks, agents help with them",
           _plan("Task Camp", "Requests from mail become tasks; agents draft what they can.",
                 [_b("inbox", "watchtower", "Inbox", "🗼", "your mail"),
                  _b("board", "fields", "Tasks", "📋", "every request as a task"),
                  _b("helpers", "barracks", "Helpers", "🏕️", "agents draft answers and documents"),
                  _b("drafts", "loot", "Drafts", "📦", "what the helpers made")],
                 [_r("inbox", "mail.received", "board", "a request becomes a task"),
                  _r("board", "tasks.created", "helpers", "a task gets a helper"),
                  _r("helpers", "pool.done", "drafts", "the draft waits for you")]),
           day=("mail", "build")),
    Intent("report_mill", OTHER, "📝", "Report Mill", "a scheduled report from your files",
           _plan("Report Mill", "On a schedule your files are milled into a report.",
                 [_b("schedule", "watchtower", "Schedule", "🗼", "when the report is due"),
                  _b("files", "forest", "Source files", "🌲", "the folder the numbers live in"),
                  _b("mill", "mill", "Report mill", "⚙️", "files into the report template"),
                  _b("reports", "loot", "Reports", "📦", "ready to send")],
                 [_r("schedule", "watch.cron", "mill", "the schedule starts the report"),
                  _r("files", "files.changed", "mill", "new data refreshes it"),
                  _r("mill", "mill.done", "reports", "the report is kept")]),
           day=("reports",)),
    Intent("knowledge_base", OTHER, "📚", "Scroll Library", "notes and documents you can ask questions of",
           _plan("Scroll Library", "Drop documents in; ask questions, agents answer from them.",
                 [_b("drops", "pit", "Drops", "🕳️", "documents and links"),
                  _b("base", "scrolls", "Knowledge", "🗑️", "everything, searchable"),
                  _b("helpers", "barracks", "Answerers", "🏕️", "agents answer from the base")],
                 [_r("drops", "pit.text", "helpers", "a question gets an answer"),
                  _r("base", "knowledge.chunks", "helpers", "answers cite the base")]),
           day=("research", "reports")),
)


def role(role_id: str) -> Role:
    return next((r for r in ROLES if r.id == role_id), ROLES[-1])


# The classes of orkcraft.dev, each the role its card stands for: the page hands its pick to
# `orkcraft --role <class>`, and the onboarding opens on that role (its nick is the class's name).
CLASSES: dict[str, str] = {
    "peon": "engineer", "knight": "founder", "elf": "designer",
    "lich": "eng_manager", "gnome": "marketing", "goblin": "data_analyst",
}


def role_id_of(word: str) -> str | None:
    """A role from what `--role` was given: a role's id (`founder`) or a class of orkcraft.dev
    (`knight`); None for anything else."""
    w = (word or "").strip().lower().replace("-", "_")
    if w in CLASSES:
        return CLASSES[w]
    return w if any(r.id == w for r in ROLES) else None


def class_kin(word: str) -> str:
    """The kin a class of orkcraft.dev names (`gnome` → gnome, `peon` → orc) when that kin has more than one
    role, so the onboarding asks which; "" for a role's own id or a kin with one role."""
    w = (word or "").strip().lower().replace("-", "_")
    if w not in CLASSES:
        return ""
    kin = role(CLASSES[w]).mascot
    return kin if sum(r.mascot == kin for r in ROLES) > 1 else ""


def industry(industry_id: str) -> Choice | None:
    return next((i for i in INDUSTRIES if i.id == industry_id), None)


def intent(intent_id: str) -> Intent | None:
    return next((i for i in INTENTS if i.id == intent_id), None)


def fit(it: Intent, day: tuple[str, ...] | list[str]) -> int:
    """How many parts of the operator's day the intent takes over (a role's own part — an ork's
    "writing code" — counts as its general one, "hands-on work")."""
    from orkcraft.realm.interview import day_general
    return len(set(it.day) & set(day_general(day)))


def for_role(role_id: str, day: tuple[str, ...] | list[str] = ()) -> list[Intent]:
    """The role's intents, those that fit the operator's day first (otherwise in their own order)."""
    mine = [i for i in INTENTS if i.role == role_id]
    return sorted(mine, key=lambda i: -fit(i, day))


def mascot(role_id: str) -> tuple[str, ...]:
    return MASCOTS[role(role_id).mascot]


def nick(role_id: str) -> str:
    return role(role_id).nick


def templates_text(role_id: str) -> str:
    """The role's templates as JSON, for the Town Builder to start from."""
    return "\n".join(json.dumps(i.plan, ensure_ascii=False) for i in for_role(role_id))
