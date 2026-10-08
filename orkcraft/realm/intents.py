"""Who the operator is and what their first town is for (design: docs/design/onboarding.md).

    ROLES, INDUSTRIES                       the onboarding's first question: who you are, where you work
    RHYTHMS                                 a role's three towns: every day, every week, every month
    for_role("aso_manager", day)            the role's intents, the ones that fit your day first
    intent("review_desk").plan              a whole town, in the Town Builder's answer shape
    templates_text("aso_manager")           the role's templates, for the Town Builder to adapt

An intent is a ready town for a job a role does: buildings from the catalog and plain roads, in the
shape `town_builder.check` takes, so a picked intent is raised with no model call. A role has one
for each rhythm: its daily work, what it does every week (a retro, a report) and every month or
quarter (goals, reviews); the week's and the month's start on a Watchtower's schedule. When none fits,
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
    rhythm: str = "day"                       # how often it does its work: day · week · month (RHYTHMS)

    @property
    def label(self) -> str:
        return f"{self.icon} {self.title}"


OTHER = "other"

# How often a ready town does its work: a role's three towns are one of each, in this order.
RHYTHMS: dict[str, str] = {"day": "Every day", "week": "Every week", "month": "Every month"}

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


def _schedule(expr: str, why: str) -> dict:
    """The Watchtower that starts a week's or a month's work: its `cron` fires watch.cron."""
    return _b("schedule", "watchtower", "Schedule", "🗼", why, cron=expr)


WEEKLY_FRI = "weekly fri 14:00"
MONTHLY = "0 9 1 * *"                         # the first of the month, 09:00


# Every role has three towns, one per rhythm: what it does every day, every week, and every month or
# quarter. The day's town comes first: it pays off on the first day; the week's and the month's run
# by themselves on their schedule.
INTENTS: tuple[Intent, ...] = (
    # -- 🛠 software engineer ----------------------------------------------------------------------
    Intent("solo_forge", "engineer", "🛠", "Ticket Grind", "your Jira tickets → agents in worktrees → tests → merge",
           _plan("Ticket Grind", "Your tickets become cards; agents take them in worktrees, finished branches are "
                                 "tested and merged. Teammates' PRs get a clan's review first.",
                 [_b("inbox", "watchtower", "Jira and GitHub", "🗼", "tickets assigned to you, mentions, PRs"),
                  _b("board", "fields", "Today's tickets", "📋", "one card per ticket, To Do → Done"),
                  _b("crew", "barracks", "Agent crew", "🏕️", "agents take a ticket in their own worktree",
                     orders="Read the ticket and its comments, implement it on its own branch with tests, and name "
                            "the ticket in the pull request."),
                  _b("merge", "forge", "Merge forge", "⚒️", "tests a finished branch and squash-merges it"),
                  _b("review", "council", "Review fire", "🪔", "an architect and a tester review teammates' PRs",
                     members=["Architect:main", "Tester:main"]),
                  _b("notes", "loot", "Review notes", "📦", "the clan's verdicts, before you read the PR")],
                 [_r("inbox", "watch.mention", "board", "a ticket that names you becomes a card"),
                  _r("board", "tasks.created", "crew", "a new card goes to a free agent"),
                  _r("crew", "pool.done", "merge", "a finished branch goes to tests and merge"),
                  _r("crew", "pool.done", "board", "the card moves to Done"),
                  _r("inbox", "watch.github", "review", "a teammate's PR is reviewed at once"),
                  _r("review", "team.artifact_ready", "notes", "the verdict lands where you read it")]),
           day=("build", "review"), rhythm="day"),
    Intent("debt_sweep", "engineer", "🧹", "Debt Sweep", "every Friday: dependencies, flaky tests, TODOs and your week",
           _plan("Debt Sweep", "Every Friday agents update dependencies, chase flaky tests and new TODOs in small "
                               "branches, and write what you did this week.",
                 [_schedule(WEEKLY_FRI, "fires every Friday afternoon"),
                  _b("sweepers", "barracks", "Sweepers", "🏕️", "agents do the week's upkeep, one branch each",
                     orders="Once a week: update outdated dependencies one per branch, fix or mark flaky tests, and "
                            "list the TODOs added this week. Then write my week: what shipped, what is stuck."),
                  _b("merge", "forge", "Merge forge", "⚒️", "each fix's branch is tested and merged"),
                  _b("debt", "fields", "Debt list", "📋", "what the sweepers could not finish"),
                  _b("week", "loot", "My week", "📦", "the week's summary, for the standup or a status")],
                 [_r("schedule", "watch.cron", "sweepers", "Friday starts the sweep"),
                  _r("sweepers", "pool.done", "merge", "each fix's branch goes to tests and merge"),
                  _r("sweepers", "pool.done", "week", "the week's summary waits for you"),
                  _r("sweepers", "pool.failed", "debt", "what could not be done stays on the list")]),
           day=("build", "reports"), rhythm="week"),
    Intent("release_chronicle", "engineer", "📜", "Release Chronicle",
           "every month: release notes, tech debt to plan, facts for your review",
           _plan("Release Chronicle", "On the first of the month agents read the merged PRs and closed tickets: "
                                      "release notes, debt with estimates, your facts for the review.",
                 [_schedule(MONTHLY, "fires on the first of the month"),
                  _b("codebase", "scrolls", "Codebase wiki", "🗑️", "what the code does and what was decided",
                     topic="codebase"),
                  _b("scribes", "barracks", "Chroniclers", "🏕️", "agents read the month's PRs and tickets",
                     orders="Once a month: from last month's merged PRs and closed tickets write the release notes, "
                            "a list of tech debt with rough estimates for planning, and what I shipped and why it "
                            "mattered, for my review."),
                  _b("review", "council", "Chronicle fire", "🪔", "a tech lead and a product agent check it",
                     members=["Tech lead:main", "Product manager:main"]),
                  _b("docs", "loot", "Monthly documents", "📦", "release notes and plans to accept")],
                 [_r("schedule", "watch.cron", "codebase", "the month starts from the wiki"),
                  _r("codebase", "knowledge.chunks", "scribes", "the chroniclers know the code"),
                  _r("scribes", "pool.done", "review", "every document is checked; a rework goes back"),
                  _r("review", "team.approved", "docs", "the documents wait for you")]),
           day=("reports", "planning"), rhythm="month"),
    # -- 🧪 QA engineer ----------------------------------------------------------------------------
    Intent("bug_patrol", "qa", "🐛", "Bug Patrol", "bugs from everywhere sorted, reproduced and filed with steps",
           _plan("Bug Patrol", "Bug reports from Jira, Slack and mail are sorted by rules; agents reproduce each one "
                               "and add the steps and a failing test.",
                 [_b("inbox", "watchtower", "Bug reports", "🗼", "mentions in Jira and Slack, bug mail"),
                  _b("paste", "pit", "Pasted reports", "🕳️", "logs and screenshots"),
                  _b("sort", "signpost", "Triage rules", "🚏", "severity first, no model",
                     rules=["urgent: matches (?i)crash|data loss|outage|p0|critical", "bug: else"]),
                  _b("alarm", "horn", "Alarm", "📯", "a sound for an urgent bug"),
                  _b("board", "fields", "Bug board", "📋", "one place for every bug"),
                  _b("repro", "barracks", "Reproducers", "🏕️", "agents reproduce a bug and write its test",
                     orders="Reproduce the bug, write the steps and a failing test on a branch, and say where in "
                            "the code it breaks.")],
                 [_r("inbox", "watch.mention", "sort", "every report is sorted"),
                  _r("inbox", "mail.received", "sort", "mail reports too"),
                  _r("paste", "pit.text", "sort", "pasted reports too"),
                  _r("sort", "signpost.routed", "alarm", "an urgent bug is heard", "urgent"),
                  _r("sort", "signpost.routed", "board", "urgent bugs land on the board", "urgent"),
                  _r("sort", "signpost.routed", "board", "and every other bug too", "bug"),
                  _r("board", "tasks.created", "repro", "every bug is reproduced"),
                  _r("repro", "pool.done", "board", "the card gets the steps")]),
           day=("firefight", "users"), rhythm="day"),
    Intent("regression_run", "qa", "🔁", "Regression Raid", "every week the full suites run; failures become bugs",
           _plan("Regression Raid", "Every Thursday agents run the full and slow suites on main; failures become "
                                    "bugs, and the run becomes the week's QA report.",
                 [_schedule("weekly thu 18:00", "fires every Thursday evening"),
                  _b("runners", "barracks", "Test runners", "🏕️", "agents run the suites and read the failures",
                     orders="Once a week: run the full and the slow end-to-end suites on main. Reproduce each "
                            "failure; mark a flaky test with how often it fails."),
                  _b("bugs", "fields", "Bugs", "📋", "every failure as a task"),
                  _b("report", "mill", "QA report", "⚙️", "the run as the week's report",
                     steps=["agent: turn this test run into a weekly QA report: pass rate, new failures, flaky "
                            "tests, what to fix first"]),
                  _b("reports", "loot", "Weekly reports", "📦", "ready to share")],
                 [_r("schedule", "watch.cron", "runners", "the week ends with a full run"),
                  _r("runners", "pool.failed", "bugs", "a failure becomes a bug"),
                  _r("runners", "pool.done", "report", "the run becomes the report"),
                  _r("report", "mill.done", "reports", "the report is kept")]),
           day=("review", "reports"), rhythm="week"),
    Intent("coverage_audit", "qa", "🗺", "Coverage Audit", "every month: test plans against what shipped, the risks",
           _plan("Coverage Audit", "On the first of the month agents compare the test plans with what shipped; "
                                   "a clan reviews the gaps and the risks for the next release.",
                 [_schedule(MONTHLY, "fires on the first of the month"),
                  _b("plans", "scrolls", "Test plans", "🗑️", "the test plans and cases, as a wiki"),
                  _b("auditors", "barracks", "Auditors", "🏕️", "agents find what is not tested",
                     orders="Once a month: compare the test plans with what shipped last month. List the untested "
                            "areas, the outdated cases and the top risks for the next release, and draft the "
                            "missing cases."),
                  _b("council", "council", "Risk fire", "🪔", "a QA, a dev and a product agent review it",
                     members=["QA:main", "Developer:main", "Product:main"], veto=["QA"]),
                  _b("verdicts", "loot", "Coverage review", "📦", "the gaps and the new cases to accept")],
                 [_r("schedule", "watch.cron", "plans", "the month starts from the test plans"),
                  _r("plans", "knowledge.chunks", "auditors", "the auditors know the plans"),
                  _r("auditors", "pool.done", "council", "the audit is reviewed; a rework goes back"),
                  _r("council", "team.approved", "verdicts", "the review waits for you")]),
           day=("planning", "review"), rhythm="month"),
    # -- 🧭 engineering manager --------------------------------------------------------------------
    Intent("one_on_ones", "eng_manager", "🤝", "1:1 Lodge", "every 1:1 and standup prepared from the calendar",
           _plan("1:1 Lodge", "Before each meeting an agent prepares it from the person's PRs, tickets and your "
                                 "notes; mentions and action items become your to-dos.",
                 [_b("calendar", "war_drum", "Calendar", "🥁", "today's 1:1s, standups and syncs", lead="1h"),
                  _b("prep", "barracks", "Meeting prep", "🏕️", "an agent prepares each meeting",
                     orders="For the meeting: who is in it, their PRs, tickets moved and blockers since the last "
                            "one, the open action items, and three questions to ask."),
                  _b("notes", "scrolls", "Team notes", "🗑️", "what was said, per person", topic="team"),
                  _b("mentions", "watchtower", "Mentions", "🗼", "where you are mentioned in Slack and Jira"),
                  _b("actions", "fields", "Action items", "📋", "what you promised, as to-dos")],
                 [_r("calendar", "calendar.event_upcoming", "prep", "an hour before, the meeting is prepared"),
                  _r("prep", "pool.done", "calendar", "the brief opens from the meeting"),
                  _r("notes", "knowledge.changed", "actions", "new notes surface their action items"),
                  _r("mentions", "watch.mention", "actions", "a mention that needs you becomes a to-do")]),
           day=("meetings", "planning"), rhythm="day"),
    Intent("team_pulse", "eng_manager", "💓", "Retro Drum", "every Friday: what shipped, what slipped, a retro board",
           _plan("Retro Drum", "Every Friday agents gather the week from GitHub and Jira into a digest and a retro "
                               "board with the facts under each point; a clan checks it.",
                 [_schedule(WEEKLY_FRI, "fires every Friday afternoon"),
                  _b("scribes", "barracks", "Week scribes", "🏕️", "agents gather the team's week",
                     orders="Once a week: what the team shipped, what slipped and why, cycle time against last "
                            "week, the incidents. Then a retro board: went well, went badly, to try, with the facts "
                            "under each, and last retro's action items with their status."),
                  _b("review", "council", "Retro fire", "🪔", "an engineer, a product and an agile coach agent",
                     members=["Engineer:main", "Product manager:main", "Agile coach:main"]),
                  _b("reports", "loot", "Retro pack", "📦", "the digest and the board, ready to share"),
                  _b("load", "crag", "Throughput", "🪨", "tasks moved per day", source="tasks", window="7d")],
                 [_r("schedule", "watch.cron", "scribes", "Friday starts the week's digest"),
                  _r("scribes", "pool.done", "review", "the digest is checked; a rework goes back"),
                  _r("review", "team.approved", "reports", "the retro pack waits for you")]),
           day=("reports", "meetings"), rhythm="week"),
    Intent("quarter_ledger", "eng_manager", "🎯", "Quarter Ledger", "every month: goals' status, capacity, review facts",
           _plan("Quarter Ledger", "On the first of the month agents check every quarterly goal against its epics, "
                                   "plan next month's capacity and gather facts for reviews.",
                 [_schedule(MONTHLY, "fires on the first of the month"),
                  _b("goals", "scrolls", "Goals and decisions", "🗑️", "the quarter's goals, as a wiki", topic="team"),
                  _b("planners", "barracks", "Planners", "🏕️", "agents read the epics and the month",
                     orders="Once a month: the status of every quarterly goal from its epics (done, on track, at "
                            "risk, with the evidence), next month's capacity (holidays, on-call, hiring), and what "
                            "each person shipped and led, for their review."),
                  _b("council", "council", "Goals fire", "🪔", "a director, a product and a staff engineer agent",
                     members=["Engineering director:main", "Product manager:main", "Staff engineer:main"]),
                  _b("reports", "loot", "Quarter report", "📦", "the status and the plan to accept")],
                 [_r("schedule", "watch.cron", "goals", "the month starts from the goals"),
                  _r("goals", "knowledge.chunks", "planners", "the planners know the goals"),
                  _r("planners", "pool.done", "council", "the report is reviewed; a rework goes back"),
                  _r("council", "team.approved", "reports", "the report waits for you")]),
           day=("planning", "reports"), rhythm="month"),
    # -- 📋 product manager ------------------------------------------------------------------------
    Intent("war_room", "product_manager", "🗺", "War Room", "mail sorted into tasks, every meeting with its brief",
           _plan("War Room", "Requests from mail become tasks; every meeting gets a brief before it starts; every "
                             "morning a digest of the day.",
                 [_b("inbox", "watchtower", "Inbox", "🗼", "mail and mentions from the team and stakeholders"),
                  _b("sort", "signpost", "Sorter", "🚏", "what needs you, by rules",
                     rules=["you: matches (?i)\\?|please|can you|deadline|asap|review|approve|decide"]),
                  _b("board", "fields", "Board", "📋", "every request as a task"),
                  _b("calendar", "war_drum", "Calendar", "🥁", "the day's meetings", day_starts="08:30"),
                  _b("prep", "barracks", "Meeting prep", "🏕️", "an agent writes each meeting's brief",
                     orders="A one-page brief for the meeting: its goal, the decisions needed, the facts from the "
                            "tickets, docs and mail."),
                  _b("digest", "mill", "Morning digest", "⚙️", "meetings and what needs you, in one page",
                     steps=["agent: turn today's schedule into a short morning digest: each meeting and what it "
                            "needs from me"]),
                  _b("reports", "loot", "Digests", "📦", "the daily pages")],
                 [_r("inbox", "mail.received", "sort", "mail is sorted"),
                  _r("inbox", "watch.mention", "sort", "mentions too"),
                  _r("sort", "signpost.routed", "board", "a request becomes a task", "you"),
                  _r("calendar", "calendar.event_upcoming", "prep", "before a meeting its brief is written"),
                  _r("prep", "pool.done", "calendar", "the brief opens from the meeting"),
                  _r("calendar", "calendar.day_schedule", "digest", "the day starts with a digest"),
                  _r("digest", "mill.done", "reports", "the digest is kept")]),
           day=("mail", "meetings", "planning"), rhythm="day"),
    Intent("product_review", "product_manager", "🔦", "Signal Fire",
           "every Monday: last week's numbers and feedback, three things to look at",
           _plan("Signal Fire", "Every Monday agents compare last week's metrics, feedback and releases, and propose "
                                "three things to look at, each with its evidence.",
                 [_schedule("weekly mon 09:00", "fires every Monday morning"),
                  _b("analysts", "barracks", "Week readers", "🏕️", "agents read analytics, feedback and releases",
                     orders="Once a week: last week's key metrics against the week before, the top themes in user "
                            "feedback, what shipped. Then three things to look at this week, each with its evidence, "
                            "and the points for the sprint retro."),
                  _b("review", "council", "Signal fire", "🪔", "a PM, an engineer and a designer agent review it",
                     members=["Product manager:main", "Engineer:main", "Designer:main"]),
                  _b("reports", "loot", "Weekly review", "📦", "the page, ready to share")],
                 [_r("schedule", "watch.cron", "analysts", "Monday starts with last week"),
                  _r("analysts", "pool.done", "review", "the review is checked; a rework goes back"),
                  _r("review", "team.approved", "reports", "the page waits for you")]),
           day=("metrics", "users", "reports"), rhythm="week"),
    Intent("roadmap_council", "product_manager", "🧭", "Roadmap Moot",
           "every month: goals and key results, the roadmap in step with Jira",
           _plan("Roadmap Moot", "On the first of the month agents check each goal and key result against the "
                                    "epics and analytics, and bring the roadmap in step.",
                 [_schedule(MONTHLY, "fires on the first of the month"),
                  _b("product", "scrolls", "Product wiki", "🗑️", "goals, decisions, research", topic="general"),
                  _b("planners", "barracks", "Planners", "🏕️", "agents read the epics and the numbers",
                     orders="Once a month: the status of each quarterly goal and key result from the epics and the "
                            "analytics (on track or at risk, with numbers), the roadmap page brought in step with "
                            "Jira, and at the quarter's end a draft of next quarter's goals."),
                  _b("council", "council", "Roadmap fire", "🪔", "a head of product, an engineer and an analyst",
                     members=["Head of product:main", "Engineering lead:main", "Data analyst:main"]),
                  _b("reports", "loot", "Goals report", "📦", "the status and the roadmap to accept")],
                 [_r("schedule", "watch.cron", "product", "the month starts from the product wiki"),
                  _r("product", "knowledge.chunks", "planners", "the planners know the goals"),
                  _r("planners", "pool.done", "council", "the report is reviewed; a rework goes back"),
                  _r("council", "team.approved", "reports", "the report waits for you")]),
           day=("planning", "reports"), rhythm="month"),
    # -- 🎨 product designer -----------------------------------------------------------------------
    Intent("mockup_grove", "designer", "🌳", "Mockup Grove", "a brief → mockup variants → a critique → you pick",
           _plan("Mockup Grove", "A brief becomes mockup variants that a clan critiques; Figma comments and Jira "
                                 "mentions become your list of changes.",
                 [_b("briefs", "pit", "Briefs", "🕳️", "paste a brief or drop a sketch"),
                  _b("studio", "barracks", "Variant studio", "🏕️", "agents draw variants in parallel"),
                  _b("critique", "council", "Critique fire", "🪔", "a UX and an accessibility agent review them",
                     members=["UX:main", "Accessibility:main"], veto=["Accessibility"]),
                  _b("picks", "loot", "Variants", "📦", "accept the variant to keep"),
                  _b("mentions", "watchtower", "Figma and Jira", "🗼", "comments on your files, mentions"),
                  _b("changes", "fields", "Changes asked", "📋", "every comment that asks for a change")],
                 [_r("briefs", "pit.text", "studio", "a brief starts the variants"),
                  _r("studio", "pool.done", "critique", "every variant is critiqued; a rework goes back"),
                  _r("critique", "team.approved", "picks", "the variants wait for your pick"),
                  _r("mentions", "watch.comment", "changes", "a comment becomes a change to make"),
                  _r("mentions", "watch.mention", "changes", "a mention too")]),
           day=("build", "review"), rhythm="day"),
    Intent("crit_circle", "designer", "🗣", "Critique Circle", "every week: the design changes checked, the crit agenda",
           _plan("Critique Circle", "Every Thursday agents gather the week's design changes, check them against the "
                                    "design system and prepare the design critique.",
                 [_schedule("weekly thu 15:00", "fires every Thursday afternoon"),
                  _b("auditors", "barracks", "Crit prep", "🏕️", "agents gather the week's design changes",
                     orders="Once a week: the Figma files changed and the tickets moved to design review; check each "
                            "against the design system (tokens, components, accessibility) and write the critique's "
                            "agenda: each item, its question, its link."),
                  _b("council", "council", "Critique fire", "🪔", "a UX, a brand and an accessibility agent",
                     members=["UX:main", "Brand:main", "Accessibility:main"], veto=["Accessibility"]),
                  _b("agenda", "loot", "Crit agenda", "📦", "the agenda and the findings")],
                 [_r("schedule", "watch.cron", "auditors", "Thursday starts the crit prep"),
                  _r("auditors", "pool.done", "council", "the findings are reviewed; a rework goes back"),
                  _r("council", "team.approved", "agenda", "the agenda waits for you")]),
           day=("review", "meetings"), rhythm="week"),
    Intent("design_system", "designer", "📐", "Token Smithy", "every month: the design system's health and changelog",
           _plan("Token Smithy", "On the first of the month agents check the design system: unused and duplicate "
                                 "parts, drift between Figma and code, accessibility debt.",
                 [_schedule(MONTHLY, "fires on the first of the month"),
                  _b("system", "scrolls", "Design system wiki", "🗑️", "tokens, components and their rules",
                     topic="design"),
                  _b("keepers", "barracks", "System smiths", "🏕️", "agents audit the system",
                     orders="Once a month: the tokens and components unused or duplicated, the drift between Figma "
                            "and the code, the accessibility debt, and the system's changelog for the team."),
                  _b("council", "council", "System fire", "🪔", "a designer, a front-end and an accessibility agent",
                     members=["Designer:main", "Front-end:main", "Accessibility:main"]),
                  _b("reports", "loot", "Health report", "📦", "the report and the changelog to accept"),
                  _b("issues", "fields", "System debt", "📋", "what the audit could not settle")],
                 [_r("schedule", "watch.cron", "system", "the month starts from the system's wiki"),
                  _r("system", "knowledge.chunks", "keepers", "the smiths know the rules"),
                  _r("keepers", "pool.done", "council", "the audit is reviewed; a rework goes back"),
                  _r("keepers", "pool.failed", "issues", "what failed becomes a task"),
                  _r("council", "team.approved", "reports", "the report waits for you")]),
           day=("build", "review"), rhythm="month"),
    # -- 🎮 game designer --------------------------------------------------------------------------
    Intent("gdd_council", "game_designer", "📖", "GDD Fire", "ideas → GDD pages → a clan; configs → balance sheets",
           _plan("GDD Fire", "Ideas become GDD pages a clan reviews; every change of the game configs rebuilds the "
                             "balance sheets you compare with the last ones.",
                 [_b("ideas", "pit", "Ideas", "🕳️", "a mechanic, a reference, a sketch"),
                  _b("gdd", "scrolls", "GDD", "🗑️", "the design document, as a wiki"),
                  _b("writers", "barracks", "GDD writers", "🏕️", "an agent writes the page"),
                  _b("council", "council", "Design fire", "🪔", "a designer, a producer and a player agent review it",
                     members=["Designer:main", "Producer:main", "Player:main"]),
                  _b("pages", "loot", "GDD pages", "📦", "pages to accept into the GDD"),
                  _b("configs", "forest", "Game configs", "🌲", "the balance and economy files"),
                  _b("sheets", "mill", "Balance sheets", "⚙️", "curves and tables from the configs"),
                  _b("view", "lake", "Balance view", "🌊", "the sheets, side by side with the last ones")],
                 [_r("ideas", "pit.text", "gdd", "an idea goes through the GDD"),
                  _r("gdd", "knowledge.chunks", "writers", "the writer knows what is decided"),
                  _r("writers", "pool.done", "council", "every page is reviewed; a rework goes back to the writer"),
                  _r("council", "team.approved", "pages", "the page waits for you"),
                  _r("configs", "files.changed", "sheets", "a change rebuilds the sheets"),
                  _r("sheets", "mill.done", "view", "you see what changed")]),
           day=("build", "metrics"), rhythm="day"),
    Intent("playtest_circle", "game_designer", "🎮", "Playtest Circle", "every week: playtests and data → what to change",
           _plan("Playtest Circle", "Every Friday agents sum up the week's playtest notes and build data, and "
                                    "propose what to change next; a clan reviews it.",
                 [_schedule("weekly fri 16:00", "fires every Friday afternoon"),
                  _b("notes", "scrolls", "Playtest notes", "🗑️", "what testers said and did", topic="general"),
                  _b("readers", "barracks", "Playtest readers", "🏕️", "agents read the notes and the data",
                     orders="Once a week: what players did, where they got stuck and the balance outliers, from the "
                            "playtest notes and the build's analytics; then what to change next, each change with "
                            "its evidence."),
                  _b("council", "council", "Playtest fire", "🪔", "a designer, a producer and a player agent",
                     members=["Designer:main", "Producer:main", "Player:main"]),
                  _b("changes", "loot", "Changes to make", "📦", "the week's findings to accept")],
                 [_r("schedule", "watch.cron", "notes", "the week starts from the notes"),
                  _r("notes", "knowledge.chunks", "readers", "the readers know what testers said"),
                  _r("readers", "pool.done", "council", "the findings are reviewed; a rework goes back"),
                  _r("council", "team.approved", "changes", "the changes wait for you")]),
           day=("research", "reports"), rhythm="week"),
    Intent("milestone_scales", "game_designer", "⚖️", "Milestone Scales",
           "every month: economy review, the GDD against the build, the next scope",
           _plan("Milestone Scales", "On the first of the month agents review the economy over the month's data, the "
                                     "GDD pages out of step and the next milestone's scope.",
                 [_schedule(MONTHLY, "fires on the first of the month"),
                  _b("gdd", "scrolls", "GDD", "🗑️", "the design document, as a wiki", topic="design"),
                  _b("planners", "barracks", "Economy readers", "🏕️", "agents read the month's data and the GDD",
                     orders="Once a month: the economy review (currency sources and sinks, progression pace, "
                            "retention by level), the GDD pages out of step with the build, and the scope of the "
                            "next milestone."),
                  _b("council", "council", "Milestone fire", "🪔", "a designer, a producer and an economy agent",
                     members=["Designer:main", "Producer:main", "Economy analyst:main"]),
                  _b("reports", "loot", "Milestone review", "📦", "the review and the scope to accept")],
                 [_r("schedule", "watch.cron", "gdd", "the month starts from the GDD"),
                  _r("gdd", "knowledge.chunks", "planners", "the readers know what is decided"),
                  _r("planners", "pool.done", "council", "the review is checked; a rework goes back"),
                  _r("council", "team.approved", "reports", "the review waits for you")]),
           day=("planning", "metrics"), rhythm="month"),
    # -- 📈 ASO manager ----------------------------------------------------------------------------
    Intent("review_desk", "aso_manager", "⭐", "Review Lodge", "store reviews sorted, replies drafted for approval",
           _plan("Review Lodge", "New store reviews are sorted; agents draft replies, bugs become tasks.",
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
           day=("users",), rhythm="day"),
    Intent("keyword_tracker", "aso_manager", "🔑", "Keyword Watch", "every Monday: rankings collected, diffed, reported",
           _plan("Keyword Watch", "Every Monday agents collect keyword rankings; they are diffed with last week's into a report.",
                 [_schedule("weekly mon 09:00", "fires every Monday morning"),
                  _b("collectors", "barracks", "Rank collectors", "🏕️", "agents pull rankings per store and country",
                     orders="Once a week: our keyword ranks per store and country and those of three competitors."),
                  _b("diff", "mill", "Rank diff", "⚙️", "this week against last, per keyword"),
                  _b("reports", "loot", "ASO reports", "📦", "the weekly report, ready to share"),
                  _b("drops", "crag", "Rank drops", "🪨", "warns when a keyword falls")],
                 [_r("schedule", "watch.cron", "collectors", "the week starts with fresh rankings"),
                  _r("collectors", "pool.done", "diff", "rankings are compared"),
                  _r("diff", "mill.done", "reports", "the diff becomes the report")]),
           day=("metrics", "reports"), rhythm="week"),
    Intent("listing_lab", "aso_manager", "🧪", "Listing Lab", "every month: competitors, test results, new variants",
           _plan("Listing Lab", "On the first of the month agents read competitors' listings and the month's A/B "
                                  "results and draft the next variants; a clan reviews them.",
                 [_schedule(MONTHLY, "fires on the first of the month"),
                  _b("notes", "scrolls", "Market notes", "🗑️", "what competitors do, as a wiki", topic="general"),
                  _b("writers", "barracks", "Copywriters", "🏕️", "agents draft listing variants",
                     orders="Once a month: what competitors changed in their listings (titles, screenshots, "
                            "ratings), the results of this month's A/B tests, and listing variants for the next."),
                  _b("council", "council", "Listing fire", "🪔", "a copywriter, an ASO and a brand agent review them",
                     members=["Copywriter:main", "ASO:main", "Brand:main"]),
                  _b("variants", "loot", "Listing variants", "📦", "titles, subtitles, screenshot captions")],
                 [_r("schedule", "watch.cron", "notes", "the month starts from the notes"),
                  _r("notes", "knowledge.chunks", "writers", "the writers know the market"),
                  _r("writers", "pool.done", "council", "variants are reviewed; a rework goes back to the writer"),
                  _r("council", "team.approved", "variants", "variants wait for your pick")]),
           day=("research", "build"), rhythm="month"),
    # -- 📣 marketing / growth ---------------------------------------------------------------------
    Intent("content_mill", "marketing", "✍️", "Content Press", "ideas → drafts → approved posts",
           _plan("Content Press", "Ideas are drafted by agents into posts you approve.",
                 [_b("ideas", "pit", "Ideas", "🕳️", "paste an idea or a link"),
                  _b("calendar", "fields", "Content plan", "📋", "what goes out when"),
                  _b("writers", "barracks", "Writers", "🏕️", "agents draft posts in your voice"),
                  _b("posts", "loot", "Posts to approve", "📦", "accept to publish"),
                  _b("mentions", "watchtower", "Mentions", "🗼", "where the brand is mentioned in Slack")],
                 [_r("ideas", "pit.text", "calendar", "every idea lands on the plan"),
                  _r("mentions", "watch.mention", "calendar", "a mention worth answering lands there too"),
                  _r("calendar", "tasks.created", "writers", "a planned post gets a draft"),
                  _r("writers", "pool.done", "posts", "the draft waits for you")]),
           day=("build", "planning"), rhythm="day"),
    Intent("campaign_report", "marketing", "📊", "Campaign Tally", "every Friday: campaign numbers milled into a report",
           _plan("Campaign Tally", "Every Friday agents pull the campaign numbers; a template turns them into the report.",
                 [_schedule("weekly fri 10:00", "fires before the weekly sync"),
                  _b("analysts", "barracks", "Number pullers", "🏕️", "agents export the campaign numbers",
                     orders="Once a week: spend, clicks, signups and cost per signup by campaign, against last "
                            "week; name what to cut and what to scale."),
                  _b("report", "mill", "Report mill", "⚙️", "numbers into the report template"),
                  _b("reports", "loot", "Reports", "📦", "ready to share")],
                 [_r("schedule", "watch.cron", "analysts", "the week's numbers are pulled"),
                  _r("analysts", "pool.done", "report", "numbers become the report"),
                  _r("report", "mill.done", "reports", "the report is kept")]),
           day=("metrics", "reports"), rhythm="week"),
    Intent("growth_council", "marketing", "🚀", "Growth Moot", "every month: channels against the plan, next month's split",
           _plan("Growth Moot", "On the first of the month agents review every channel against the plan and draft "
                                   "next month's plan and budget; a clan reviews it.",
                 [_schedule(MONTHLY, "fires on the first of the month"),
                  _b("planners", "barracks", "Growth planners", "🏕️", "agents read the month's numbers",
                     orders="Once a month: each channel's spend, cost per customer and conversion against the plan, "
                            "the campaigns to scale or cut, the content that worked, and next month's plan with the "
                            "budget split."),
                  _b("council", "council", "Growth fire", "🪔", "a marketing lead, an analyst and a brand agent",
                     members=["Marketing lead:main", "Analyst:main", "Brand:main"]),
                  _b("plans", "loot", "Monthly plan", "📦", "the review and the plan to accept")],
                 [_r("schedule", "watch.cron", "planners", "the month starts with its numbers"),
                  _r("planners", "pool.done", "council", "the plan is reviewed; a rework goes back"),
                  _r("council", "team.approved", "plans", "the plan waits for you")]),
           day=("planning", "metrics"), rhythm="month"),
    # -- 📊 data analyst ---------------------------------------------------------------------------
    Intent("adhoc_desk", "data_analyst", "❓", "Question Den", "questions answered with queries; anomalies checked",
           _plan("Question Den", "Paste a question and an agent answers it with a query; every morning yesterday's "
                                 "metrics are checked, and an anomaly alert sounds and gets a first look.",
                 [_b("questions", "pit", "Questions", "🕳️", "paste what someone asked"),
                  _b("watch", "watchtower", "Alerts and morning", "🗼", "metric alerts by webhook; fires at 08:00",
                     cron="daily 08:00"),
                  _b("rules", "signpost", "Thresholds", "🚏", "which alerts matter, by rules",
                     rules=["anomaly: matches (?i)critical|anomal|spike|drop|breach"]),
                  _b("alarm", "horn", "Alarm", "📯", "a sound for a real anomaly"),
                  _b("analysts", "barracks", "Analyst agents", "🏕️", "agents write and run the query",
                     orders="Answer with the query, the result and two sentences. On the morning schedule check "
                            "yesterday's key metrics and report only anomalies."),
                  _b("answers", "loot", "Answers", "📦", "kept for the next time it is asked")],
                 [_r("questions", "pit.text", "analysts", "every question gets an analyst"),
                  _r("watch", "watch.cron", "analysts", "the morning check"),
                  _r("watch", "watch.webhook", "rules", "every alert is checked"),
                  _r("rules", "signpost.routed", "alarm", "a real anomaly is heard", "anomaly"),
                  _r("rules", "signpost.routed", "analysts", "and gets a first look", "anomaly"),
                  _r("analysts", "pool.done", "answers", "the answer is kept")]),
           day=("users", "metrics", "firefight"), rhythm="day"),
    Intent("ledger_tower", "data_analyst", "📒", "Ledger Tower", "every Monday: metric reports, cleaned and charted",
           _plan("Ledger Tower", "Every Monday the data is pulled, cleaned by a script and turned into reports.",
                 [_schedule("weekly mon 08:00", "fires every Monday morning"),
                  _b("pull", "barracks", "Query runners", "🏕️", "agents run the queries and exports",
                     orders="Once a week: run the weekly report's queries and exports as CSV."),
                  _b("clean", "mill", "Clean and shape", "⚙️", "CSV → tidy JSON, no model"),
                  _b("reports", "loot", "Reports", "📦", "the finished reports")],
                 [_r("schedule", "watch.cron", "pull", "the schedule starts the queries"),
                  _r("pull", "pool.done", "clean", "raw exports are cleaned"),
                  _r("clean", "mill.done", "reports", "clean data becomes the report")]),
           day=("reports", "metrics"), rhythm="week"),
    Intent("metric_audit", "data_analyst", "🔬", "Metric Audit",
           "every month: definitions checked, stale dashboards, a deep-dive",
           _plan("Metric Audit", "On the first of the month agents check each key metric against its query and "
                                 "dashboards and write the month's deep-dive; a clan reviews it.",
                 [_schedule(MONTHLY, "fires on the first of the month"),
                  _b("defs", "scrolls", "Metric definitions", "🗑️", "what each metric means and how it is counted",
                     topic="general"),
                  _b("auditors", "barracks", "Auditors", "🏕️", "agents check queries and dashboards",
                     orders="Once a month: check each key metric's definition against its query and dashboards, "
                            "list broken or stale dashboards and unused tables, and write the month's deep-dive: "
                            "the trend that matters, with its cuts."),
                  _b("council", "council", "Data fire", "🪔", "an analyst, a data engineer and a product agent",
                     members=["Analyst:main", "Data engineer:main", "Product manager:main"]),
                  _b("reports", "loot", "Monthly audit", "📦", "the audit and the deep-dive to accept")],
                 [_r("schedule", "watch.cron", "defs", "the month starts from the definitions"),
                  _r("defs", "knowledge.chunks", "auditors", "the auditors know the definitions"),
                  _r("auditors", "pool.done", "council", "the audit is reviewed; a rework goes back"),
                  _r("council", "team.approved", "reports", "the audit waits for you")]),
           day=("research", "reports"), rhythm="month"),
    # -- 🛡 founder / indie ------------------------------------------------------------------------
    Intent("inbox_keep", "founder", "📨", "Inbox Keep", "mail and GitHub sorted into tasks, agents take them",
           _plan("Inbox Keep", "Mail and GitHub are sorted by rules into tasks; agents code and write, you accept "
                               "copy and code is tested and merged.",
                 [_b("inbox", "watchtower", "Inbox", "🗼", "mail and GitHub"),
                  _b("sort", "signpost", "Sorter", "🚏", "what needs you, by rules",
                     rules=["you: matches (?i)urgent|asap|review requested|mention|invoice|deadline|\\?"]),
                  _b("tasks", "fields", "Everything board", "📋", "code, copy and errands"),
                  _b("crew", "barracks", "Crew", "🏕️", "agents for code and for copy"),
                  _b("merge", "forge", "Merge forge", "⚒️", "code is tested and merged"),
                  _b("drafts", "loot", "Drafts", "📦", "copy and replies to accept")],
                 [_r("inbox", "mail.received", "sort", "mail is sorted"),
                  _r("inbox", "watch.github", "sort", "GitHub too"),
                  _r("sort", "signpost.routed", "tasks", "what needs you becomes a task", "you"),
                  _r("tasks", "tasks.created", "crew", "every task gets an agent"),
                  _r("crew", "pool.done", "merge", "code goes to merge"),
                  _r("crew", "pool.done", "drafts", "copy goes to drafts")]),
           day=("mail", "build"), rhythm="day"),
    Intent("week_ledger", "founder", "📒", "Week Ledger", "every Sunday: signups, revenue, support and a changelog",
           _plan("Week Ledger", "Every Sunday evening an agent puts the week on one page and drafts the changelog "
                                "post from the merged PRs.",
                 [_schedule("weekly sun 18:00", "fires every Sunday evening"),
                  _b("scribes", "barracks", "Week scribes", "🏕️", "an agent reads the numbers and the repository",
                     orders="Once a week: signups, revenue, churn and support on one page against last week, what "
                            "shipped, the three things that matter next week, and a changelog post from the merged "
                            "PRs."),
                  _b("week", "loot", "Weekly page", "📦", "the page and the post to accept")],
                 [_r("schedule", "watch.cron", "scribes", "Sunday sums up the week"),
                  _r("scribes", "pool.done", "week", "the page waits for you")]),
           day=("reports", "metrics"), rhythm="week"),
    Intent("investor_scroll", "founder", "💰", "Investor Scroll", "every month: the investor update, runway, roadmap check",
           _plan("Investor Scroll", "On the first of the month agents draft the investor update and the runway and "
                                    "check the roadmap against what customers asked; a clan reviews it.",
                 [_schedule(MONTHLY, "fires on the first of the month"),
                  _b("notes", "scrolls", "Company notes", "🗑️", "decisions, numbers, what customers asked",
                     topic="general"),
                  _b("writers", "barracks", "Update writers", "🏕️", "agents draft the update",
                     orders="Once a month: the investor update (metrics, wins, lows, asks), the runway from the "
                            "numbers in the notes, and the roadmap checked against what customers asked for."),
                  _b("council", "council", "Board fire", "🪔", "an investor, a customer and a finance agent",
                     members=["Investor:main", "Customer:main", "Finance:main"]),
                  _b("updates", "loot", "Monthly update", "📦", "the update to accept and send")],
                 [_r("schedule", "watch.cron", "notes", "the month starts from the notes"),
                  _r("notes", "knowledge.chunks", "writers", "the writers know the company"),
                  _r("writers", "pool.done", "council", "the update is reviewed; a rework goes back"),
                  _r("council", "team.approved", "updates", "the update waits for you")]),
           day=("reports", "planning"), rhythm="month"),
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
           day=("mail", "build"), rhythm="day"),
    Intent("report_mill", OTHER, "📝", "Report Press", "every Friday: a report from your files",
           _plan("Report Press", "Every Friday your files are milled into a report; new data refreshes it.",
                 [_schedule(WEEKLY_FRI, "fires every Friday afternoon"),
                  _b("files", "forest", "Source files", "🌲", "the folder the numbers live in"),
                  _b("mill", "mill", "Report mill", "⚙️", "files into the report template"),
                  _b("reports", "loot", "Reports", "📦", "ready to send")],
                 [_r("schedule", "watch.cron", "mill", "the schedule starts the report"),
                  _r("files", "files.changed", "mill", "new data refreshes it"),
                  _r("mill", "mill.done", "reports", "the report is kept")]),
           day=("reports",), rhythm="week"),
    Intent("month_review", OTHER, "📚", "Month Scroll", "every month: what was done, what is open, next month's plan",
           _plan("Month Scroll", "On the first of the month an agent reads your notes and documents and writes the "
                                 "month's review and next month's plan.",
                 [_schedule(MONTHLY, "fires on the first of the month"),
                  _b("base", "scrolls", "Knowledge", "🗑️", "your notes and documents, searchable", topic="general"),
                  _b("writers", "barracks", "Writers", "🏕️", "an agent writes the review",
                     orders="Once a month: what was done, what is still open and what changed in my notes and "
                            "documents; then a plan for next month."),
                  _b("reviews", "loot", "Monthly review", "📦", "the review and the plan to accept")],
                 [_r("schedule", "watch.cron", "base", "the month starts from the base"),
                  _r("base", "knowledge.chunks", "writers", "the writer knows what you keep"),
                  _r("writers", "pool.done", "reviews", "the review waits for you")]),
           day=("reports", "planning"), rhythm="month"),
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
