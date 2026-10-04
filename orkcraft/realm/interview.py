"""The onboarding's questions with options: your day, your AI tools and — when no intent fits —
the interview.

    ORCHESTRATION                    how well the operator knows agent orkestration: the first question
    day_options(role)                a typical day as chips, the role's own first (an ork's: code, tests…)
    USES                             what an AI tool is good for, or weak at (👍 / 👎 on the tools step)
    INTERVIEW                        where work comes from and goes → what hurts
    page.options(q, role, industry)  a question's options, the ones common for the role first
    summary(profile, answers)        everything said, as the Town Builder's order

Answers are {question id: [option ids]} plus {question id + "_other": text}. Options are data,
never code: the Town Builder only reads their titles.
"""
from __future__ import annotations

from dataclasses import dataclass

from orkcraft.realm import intents
from orkcraft.realm.intents import Choice


def _c(*rows: tuple[str, str, str]) -> tuple[Choice, ...]:
    return tuple(Choice(*r) for r in rows)


DAY = _c(("mail", "📨", "Inbox"), ("meetings", "🗣", "Meetings"), ("build", "🛠", "Hands-on work"),
         ("review", "🔍", "Reviews"), ("reports", "📝", "Reports"), ("metrics", "📈", "Metrics"),
         ("planning", "🗺", "Planning"), ("users", "💬", "Users"), ("research", "🔬", "Research"),
         ("firefight", "🔥", "Incidents"))
# A role's own parts of a day, first among the chips; each counts as a general one for the intents.
DAY_BY_MASCOT: dict[str, tuple[Choice, ...]] = {
    "orc": _c(("code", "⌨️", "Writing code"), ("tests", "🧪", "Tests and CI"), ("deploys", "🚢", "Deploys")),
    "lich": _c(("status", "📋", "Status updates"), ("one_on_ones", "👥", "1:1s"), ("hiring", "🤝", "Hiring")),
    "elf": _c(("mockups", "🎨", "Mockups"), ("design_system", "🧩", "Design system"), ("playtests", "🎮", "Playtests")),
    "gnome": _c(("campaigns", "📣", "Campaigns"), ("content", "✍️", "Content"), ("listings", "🔑", "Store listings")),
    "goblin": _c(("queries", "🧮", "Queries"), ("dashboards", "📊", "Dashboards")),
    "knight": _c(("customers", "🤝", "Customers"), ("shipping", "🚀", "Shipping"), ("fundraising", "💰", "Fundraising")),
}
DAY_AS = {"code": "build", "tests": "review", "deploys": "firefight", "status": "reports", "one_on_ones": "meetings",
          "hiring": "meetings", "mockups": "build", "design_system": "build", "playtests": "research",
          "campaigns": "planning", "content": "build", "listings": "metrics", "queries": "research",
          "dashboards": "metrics", "customers": "users", "shipping": "build", "fundraising": "reports"}
ALL_DAY = DAY + tuple(c for extra in DAY_BY_MASCOT.values() for c in extra)


def day_options(role_id: str) -> list[Choice]:
    """The chips of a typical day: the role's own first, then the general ones."""
    return list(DAY_BY_MASCOT.get(intents.role(role_id).mascot, ())) + list(DAY) if role_id else list(DAY)


def day_general(day: list[str] | tuple[str, ...]) -> list[str]:
    """A day in the general parts the intents know (a role's own part counts as its general one)."""
    return list(dict.fromkeys(DAY_AS.get(d, d) for d in day))


SOURCES = _c(("jira", "🟦", "Jira"), ("confluence", "📘", "Confluence"), ("linear", "🟪", "Linear"),
             ("asana", "🟥", "Asana"), ("notion", "⬛", "Notion"), ("github", "🐙", "GitHub"),
             ("gitlab", "🦊", "GitLab"), ("slack", "💬", "Slack"), ("mail", "📨", "Email"),
             ("gcal", "📅", "Calendar"), ("gdrive", "📁", "Google Drive / Docs"), ("gsheets", "🟩", "Google Sheets"),
             ("figma", "🎨", "Figma"), ("app_store", "🍏", "App Store Connect"),
             ("google_play", "▶️", "Google Play Console"), ("aso_tools", "🔑", "AppTweak / Sensor Tower"),
             ("analytics", "📈", "Amplitude / Mixpanel / GA"), ("sentry", "🚨", "Sentry / monitoring"),
             ("zendesk", "🎧", "Zendesk / Intercom"), ("crm", "🤝", "HubSpot / Salesforce"),
             ("files", "📄", "CSV / Excel files"), ("repo", "🌲", "This repository"))
OUTPUTS = _c(("jira", "🟦", "Jira"), ("confluence", "📘", "Confluence"), ("asana", "🟥", "Asana"),
             ("linear", "🟪", "Linear"), ("notion", "⬛", "Notion"), ("slack", "💬", "Slack"),
             ("mail", "📨", "Email"), ("gdocs", "📁", "Google Docs / Drive"), ("gsheets", "🟩", "Google Sheets"),
             ("figma", "🎨", "Figma"), ("github", "🐙", "Pull requests"), ("app_store", "🍏", "Store listings"),
             ("md_reports", "📝", "Reports in the repository"), ("dashboard", "🪨", "A dashboard in Orkcraft"),
             ("api", "🎯", "A webhook or any API"))
PAINS = _c(("copy_paste", "📋", "Copying data between tools by hand"), ("reports_slow", "⏳", "Reports take hours"),
           ("missed", "🕳", "Things slip through the cracks"), ("noise", "🔔", "Too many notifications"),
           ("context", "🔀", "Constant context switching"), ("waiting", "🐢", "Waiting on others and reviews"),
           ("stale", "🕸", "Docs and statuses go stale"), ("repetitive", "🔁", "The same routine every week"),
           ("no_overview", "🌫", "No single view of what is going on"))
USES = (("code", "code"), ("architecture", "architecture"), ("docs", "documentation"),
        ("search", "search: web, Jira"), ("tickets", "tickets"))
USE_TITLES = dict(USES)


@dataclass(frozen=True)
class Level:
    id: str
    icon: str
    title: str
    blurb: str

    @property
    def label(self) -> str:
        return f"{self.icon} {self.title}"


NEW, SOME, EXPERT = "new", "some", "expert"
ORCHESTRATION: tuple[Level, ...] = (
    Level(NEW, "🐣", "New to it", "I chat with AI now and then; I have never run agents. Walk me through."),
    Level(SOME, "🪓", "Some", "I use Claude Code, Cursor or similar, but rarely more than one agent at a time."),
    Level(EXPERT, "🤘", "Punk ork", "I orkestrate agents already. Skip the interview, I will build the town myself."),
)
def level(level_id: str) -> Level | None:
    return next((lv for lv in ORCHESTRATION if lv.id == level_id), None)


@dataclass(frozen=True)
class Question:
    id: str
    title: str
    choices: tuple[Choice, ...]
    other: str = ""               # the free-text field's placeholder; "" = no field
    suggest: str = ""             # "sources" / "outputs": the role's common options go first


@dataclass(frozen=True)
class Page:
    id: str
    title: str
    hint: str
    questions: tuple[Question, ...]

    def options(self, q: Question, role_id: str = "", industry_id: str = "") -> list[tuple[Choice, bool]]:
        """(choice, common for the role) — the common ones first, in the role's order."""
        common: list[str] = []
        if q.suggest:
            common = list(getattr(intents.role(role_id), q.suggest, ()))
            if q.suggest == "sources":
                common += [s for s in intents.INDUSTRY_SOURCES.get(industry_id, ()) if s not in common]
        by_id = {c.id: c for c in q.choices}
        first = [(by_id[c], True) for c in common if c in by_id]
        return first + [(c, False) for c in q.choices if c.id not in common]


INTERVIEW: tuple[Page, ...] = (
    Page("flow", "Where does your work come from, and where does it go?",
         "The Builder gives each source a way into the town and each place a way out.",
         (Question("sources", "Comes from", SOURCES, other="other sources", suggest="sources"),
          Question("outputs", "Goes to", OUTPUTS, other="other places", suggest="outputs"))),
    Page("pains", "What hurts in the way you work now?",
         "The Builder answers each problem with a building or a road.",
         (Question("pains", "Problems", PAINS, other="anything else the Builder should know"),)),
)

ALL_QUESTIONS: dict[str, Question] = {q.id: q for p in INTERVIEW for q in p.questions}


def titles(question_id: str, ids: list[str]) -> list[str]:
    choices = ALL_DAY if question_id == "day" else ALL_QUESTIONS[question_id].choices \
        if question_id in ALL_QUESTIONS else ()
    by_id = {c.id: c.title for c in choices}
    return [by_id[i] for i in ids if i in by_id]


def who(profile: dict) -> str:
    """"ASO manager in Gaming" — the role and the industry, the operator's own words where given."""
    r = profile.get("role", "")
    role_title = profile.get("role_other", "").strip() if r == intents.OTHER else intents.role(r).title if r else ""
    i = profile.get("industry", "")
    ind = intents.industry(i)
    ind_title = profile.get("industry_other", "").strip() if i == intents.OTHER else ind.title if ind else ""
    return " in ".join(x for x in (role_title, ind_title) if x) or "someone"


def summary(profile: dict, answers: dict) -> str:
    """Everything the operator said, one line per question — the Town Builder's order."""
    lines = [f"I am {who(profile)}."]
    lv = level(profile.get("orchestration", ""))
    if lv:
        lines.append(f"Agent orkestration: {lv.title.lower()} — {lv.blurb}")
    for qid, label in (("day", "My day"), ("sources", "My data comes from"), ("outputs", "Results go to"),
                       ("pains", "Problems now")):
        bag = profile if qid == "day" else answers
        parts = titles(qid, list(bag.get(qid) or []))
        other = str(bag.get(f"{qid}_other") or "").strip()
        if other:
            parts.append(other)
        if parts:
            lines.append(f"{label}: {'; '.join(parts)}.")
    rated = ai_tools_text(profile.get("ai_tools") or {})
    if rated:
        lines.append(f"AI tools I use: {rated}.")
    return "\n".join(lines)


def ai_tools_text(ai_tools: dict) -> str:
    """"Claude Code — 👍 documentation, 👎 tickets; Cursor — 👍" (titles as the tools step showed them)."""
    parts = []
    for rating in ai_tools.values():
        if not isinstance(rating, dict) or not (rating.get("like") or rating.get("dislike")):
            continue
        bits = []
        if rating.get("like"):
            bits.append("👍 " + USE_TITLES.get(rating.get("good", ""), "liked") if rating.get("good") else "👍")
        if rating.get("dislike"):
            bits.append("👎 " + USE_TITLES.get(rating.get("weak", ""), "") if rating.get("weak") else "👎")
        parts.append(f"{rating.get('title', '?')} — {', '.join(b.strip() for b in bits)}")
    return "; ".join(parts)
