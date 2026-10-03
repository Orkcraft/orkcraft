"""The onboarding's questions with options: your day, and — when no intent fits — the interview.

    ORCHESTRATION                    how well the operator knows agent orchestration: the first question
    AI_TOOLS, SKILLS, FREQS          each AI tool graded twice: experience and how often it is used
    growth(ai_tools)                 where the two differ: the growth zones
    DAY_PAGE                         a typical day and its rhythm (asked right after who you are)
    INTERVIEW                        sources → outputs → problems → what went wrong with AI
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


DAY = _c(("mail", "📨", "Inbox and messages"), ("meetings", "🗣", "Meetings and syncs"),
         ("build", "🛠", "Hands-on work: code, design, content"), ("review", "🔍", "Reviewing others' work"),
         ("reports", "📝", "Reports and documents"), ("metrics", "📈", "Watching metrics and dashboards"),
         ("planning", "🗺", "Planning and prioritising"), ("users", "💬", "Users, customers, reviews"),
         ("research", "🔬", "Research and competitors"), ("firefight", "🔥", "Incidents and urgent fixes"))
RHYTHM = _c(("daily", "☀️", "A daily summary or stand-up"), ("weekly", "📅", "A weekly report or sync"),
            ("monthly", "🗓", "A monthly review"), ("releases", "🚀", "Releases or launches"),
            ("sprints", "🥁", "Sprints and their rituals"), ("adhoc", "⚡", "Mostly ad hoc, no fixed rhythm"))
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
AI_USED = _c(("chatgpt", "🟢", "ChatGPT"), ("claude", "🟠", "Claude (chat)"), ("claude_code", "🧡", "Claude Code"),
             ("gemini", "🔷", "Gemini / Antigravity"), ("copilot", "🛩", "GitHub Copilot"), ("cursor", "🖱", "Cursor"),
             ("automations", "🔗", "Automations: Zapier, n8n, Make"), ("none", "🚫", "None yet"))
AI_PROBLEMS = _c(("no_data", "🔒", "No access to my data and tools"),
                 ("copy_context", "📋", "Copy-pasting context in and out"),
                 ("forgets", "🧠", "Forgets everything between sessions"), ("wrong", "🎲", "Makes things up"),
                 ("inconsistent", "🔀", "Different results every time"),
                 ("review_cost", "🔍", "Checking its work takes as long as doing it"),
                 ("security", "🛡", "Security or compliance concerns"), ("cost", "🪙", "Too expensive"),
                 ("not_tried", "🤷", "Haven't really tried"))


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
    Level(EXPERT, "🤘", "Punk orc", "I orchestrate agents already. Skip the interview, I will build the town myself."),
)
AI_TOOLS = tuple(c for c in AI_USED if c.id != "none")
SKILLS = (("none", "— none"), ("basic", "basic"), ("confident", "confident"), ("expert", "expert"))
FREQS = (("never", "never"), ("monthly", "monthly"), ("weekly", "weekly"), ("daily", "daily"))
SKILL_IDS = tuple(k for k, _ in SKILLS)
FREQ_IDS = tuple(k for k, _ in FREQS)


def level(level_id: str) -> Level | None:
    return next((lv for lv in ORCHESTRATION if lv.id == level_id), None)


def growth(ai_tools: dict) -> list[str]:
    """Where experience and use differ: 📈 used often but known little, 💤 known well but rarely used."""
    out: list[str] = []
    titles = {c.id: c.title for c in AI_TOOLS}
    for tid, grade in ai_tools.items():
        if tid not in titles or not isinstance(grade, dict):
            continue
        skill, freq = grade.get("skill", "none"), grade.get("freq", "never")
        si = SKILL_IDS.index(skill) if skill in SKILL_IDS else 0
        fi = FREQ_IDS.index(freq) if freq in FREQ_IDS else 0
        if fi >= 2 and si <= 1:
            out.append(f"📈 {titles[tid]}: {freq}, but {skill if si else 'no'} experience — worth learning deeper")
        elif si >= 2 and fi <= 1:
            out.append(f"💤 {titles[tid]}: {skill}, but used {freq} — a skill you barely use")
    return out


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


DAY_PAGE = Page("day", "How does your day go?",
                "What fills a typical day, and what comes back on a schedule. The town takes over the routine.",
                (Question("day", "A typical day is…", DAY, other="a typical day in your words"),
                 Question("rhythm", "It comes back as…", RHYTHM)))

INTERVIEW: tuple[Page, ...] = (
    Page("sources", "Where does your work come from?",
         "Pick every tool you take data from. The Builder gives each a way into the town.",
         (Question("sources", "Sources", SOURCES, other="other sources", suggest="sources"),)),
    Page("outputs", "Where does the result go?",
         "Pick where you put what you make. The Builder gives each a way out.",
         (Question("outputs", "Outputs", OUTPUTS, other="other places", suggest="outputs"),)),
    Page("pains", "What hurts in the way you work now?",
         "The Builder answers each problem with a building or a road.",
         (Question("pains", "Problems", PAINS, other="what else hurts"),)),
    Page("ai", "What went wrong with AI so far?",
         "So the town avoids what did not work for you.",
         (Question("ai_problems", "What went wrong", AI_PROBLEMS, other="anything else the Builder should know"),)),
)

ALL_QUESTIONS: dict[str, Question] = {q.id: q for p in (DAY_PAGE, *INTERVIEW) for q in p.questions}


def titles(question_id: str, ids: list[str]) -> list[str]:
    q = ALL_QUESTIONS.get(question_id)
    if q is None:
        return []
    by_id = {c.id: c.title for c in q.choices}
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
        lines.append(f"Agent orchestration: {lv.title.lower()} — {lv.blurb}")
    for qid, label in (("day", "My day"), ("rhythm", "Recurring"), ("sources", "My data comes from"),
                       ("outputs", "Results go to"), ("pains", "Problems now"),
                       ("ai_problems", "What went wrong with AI")):
        bag = profile if qid in ("day", "rhythm") else answers
        parts = titles(qid, list(bag.get(qid) or []))
        other = str(bag.get(f"{qid}_other") or "").strip()
        if other:
            parts.append(other)
        if parts:
            lines.append(f"{label}: {'; '.join(parts)}.")
    graded = ai_tools_text(profile.get("ai_tools") or {})
    if graded:
        lines.append(f"AI tools (experience, how often): {graded}.")
    zones = growth(profile.get("ai_tools") or {})
    if zones:
        lines.append("Growth zones: " + "; ".join(z[2:] for z in zones) + ".")
    return "\n".join(lines)


def ai_tools_text(ai_tools: dict) -> str:
    titles = {c.id: c.title for c in AI_TOOLS}
    return "; ".join(f"{titles[t]} ({g.get('skill', 'none')}, {g.get('freq', 'never')})"
                     for t, g in ai_tools.items() if t in titles and isinstance(g, dict))
