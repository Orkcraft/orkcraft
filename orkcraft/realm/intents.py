"""Who the operator is and what their first town is for (design: docs/design/onboarding.md).

    FOUNDER, role(FOUNDER)                  the one operator the onboarding asks for now: an indie maker
    for_role(FOUNDER)                       their intents: ready towns
    project_fit(root)                       ★ from the project itself: {intent id: why}
    intent("inbox_keep").plan               a whole town, in the Town Builder's answer shape
    templates_text(FOUNDER)                 the templates, for the Town Builder to adapt

An intent is a ready town for a job: buildings from the catalog and plain roads, in the shape
`town_builder.check` takes, so a picked intent is raised with no model call. When none fits, the
operator says in a phrase what the town should do, and the Town Builder adapts the templates to it.
Other roles (engineers, managers, designers…) are left out for now: an indie maker who already
works with AI comes first.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Role:
    id: str
    icon: str
    title: str
    mascot: str                               # knight
    nick: str = ""                            # the mascot's name: Indie Knight

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

    @property
    def label(self) -> str:
        return f"{self.icon} {self.title}"


FOUNDER = "founder"

MASCOTS: dict[str, tuple[str, ...]] = {
    "knight": ("     _||_     ",
               "    /____\\    ",
               "    |-==-|    ",
               "    \\____/    ",
               "  [|  ++  |]  ",
               "   |  ++  |   ",
               "   /KNIGHT\\   "),
}

ROLES: tuple[Role, ...] = (
    Role(FOUNDER, "🛡", "Founder / indie maker", "knight", "Indie Knight"),
)


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
    # -- 🛡 founder / indie ------------------------------------------------------------------------
    Intent("one_skeleton_studio", "founder", "🏚", "One-Knight Studio", "code, copy and releases in one town",
           _plan("One-Knight Studio", "One board for everything; agents code and write, you accept and merge.",
                 [_b("tasks", "fields", "Everything board", "📋", "code, copy and chores"),
                  _b("crew", "barracks", "Crew", "🏕️", "agents for code and for copy"),
                  _b("merge", "forge", "Merge forge", "⚒️", "code is tested and merged"),
                  _b("drafts", "loot", "Drafts", "📦", "copy and docs to accept")],
                 [_r("tasks", "tasks.created", "crew", "every task gets an agent"),
                  _r("crew", "pool.done", "merge", "code goes to merge"),
                  _r("crew", "pool.done", "drafts", "copy goes to drafts")])),
    Intent("inbox_keep", "founder", "📨", "Inbox Keep", "mail and GitHub sorted into tasks",
           _plan("Inbox Keep", "Mail and GitHub events are sorted by rules into tasks; the rest is muted.",
                 [_b("inbox", "watchtower", "Inbox", "🗼", "mail and GitHub"),
                  _b("sort", "signpost", "Sorter", "🚏", "what needs you, by rules",
                     rules=["you: matches (?i)urgent|asap|review requested|mention|invoice|deadline|\\?"]),
                  _b("tasks", "fields", "To answer", "📋", "what needs you, as tasks")],
                 [_r("inbox", "mail.received", "sort", "mail is sorted"),
                  _r("inbox", "watch.github", "sort", "GitHub too"),
                  _r("sort", "signpost.routed", "tasks", "what needs you becomes a task", "you")])),
    Intent("side_quest", "founder", "🧪", "Side Quest", "a light town for a pet project",
           _plan("Side Quest", "Drop ideas, keep a small board, let one agent help.",
                 [_b("ideas", "pit", "Ideas", "🕳️", "anything worth doing"),
                  _b("board", "fields", "Board", "📋", "the next few things"),
                  _b("helper", "barracks", "Helper", "🏕️", "one agent at a time")],
                 [_r("ideas", "pit.text", "board", "an idea becomes a task"),
                  _r("board", "tasks.created", "helper", "the helper picks it up")])),
)


def role(role_id: str) -> Role:
    """The role by its id; the founder for any other (a profile kept from before)."""
    return next((r for r in ROLES if r.id == role_id), ROLES[0])


def intent(intent_id: str) -> Intent | None:
    return next((i for i in INTENTS if i.id == intent_id), None)


def for_role(role_id: str) -> list[Intent]:
    return [i for i in INTENTS if i.role == role_id]


def mascot(role_id: str) -> tuple[str, ...]:
    return MASCOTS[role(role_id).mascot]


def nick(role_id: str) -> str:
    return role(role_id).nick


def templates_text(role_id: str) -> str:
    """The role's templates as JSON, for the Town Builder to start from."""
    return "\n".join(json.dumps(i.plan, ensure_ascii=False) for i in for_role(role_id))


# -- ★ from the project: what is already in the folder orkcraft runs in ---------------------------

CODE_FILES = ("pyproject.toml", "setup.py", "requirements.txt", "package.json", "deno.json", "Cargo.toml", "go.mod",
              "Gemfile", "composer.json", "pom.xml", "build.gradle", "build.gradle.kts", "pubspec.yaml",
              "Package.swift", "CMakeLists.txt", "mix.exs", "src")
AGENT_NOTES = ("CLAUDE.md", "AGENTS.md", "GEMINI.md", ".cursorrules", ".cursor", ".windsurfrules")
OURS = (".git", ".orkcraft", ".orkcraft.json", ".claude", ".codex")
FEW = 3                                    # this many things or fewer in the folder: a project just starting


def project_signs(root: Path | None) -> dict[str, list[str]]:
    """What the folder shows: {"code": [files], "notes": [an agent's notes], "github": [...]} and,
    when there is next to nothing, {"new": [...]}. Only names and the git config are read."""
    if root is None or not root.is_dir():
        return {}
    try:
        names = sorted(p.name for p in root.iterdir())
    except OSError:
        return {}
    out: dict[str, list[str]] = {}
    code = [n for n in CODE_FILES if n in names]
    notes = [n for n in AGENT_NOTES if n in names]
    if code:
        out["code"] = code
    if notes:
        out["notes"] = notes
    try:
        remote = "github.com" in (root / ".git" / "config").read_text(encoding="utf-8", errors="replace")
    except OSError:
        remote = False
    if remote or (root / ".github").is_dir():
        out["github"] = ["GitHub"]
    if not code and len([n for n in names if n not in OURS]) <= FEW:
        out["new"] = ["next to nothing yet"]
    return out


def project_fit(root: Path | None) -> dict[str, str]:
    """★ for the founder's towns, from the project: {intent id: why} — code or an agent's notes →
    One-Knight Studio, GitHub → Inbox Keep, a folder just starting → Side Quest."""
    signs = project_signs(root)
    out: dict[str, str] = {}
    if signs.get("code") or signs.get("notes"):
        bits = (["code"] if signs.get("code") else []) + (signs.get("notes") or [])[:2]
        out["one_skeleton_studio"] = f"★ {' and '.join(bits)} here"
    if signs.get("github"):
        out["inbox_keep"] = "★ the project is on GitHub"
    if signs.get("new"):
        out["side_quest"] = "★ the project is just starting"
    return out


def signs_text(root: Path | None) -> str:
    """"code (pyproject.toml), notes for agents (CLAUDE.md), GitHub" — for the Town Builder's order."""
    signs = project_signs(root)
    parts = []
    if signs.get("code"):
        parts.append(f"code ({', '.join(signs['code'])})")
    if signs.get("notes"):
        parts.append(f"notes for agents ({', '.join(signs['notes'])})")
    if signs.get("github"):
        parts.append("GitHub")
    if signs.get("new"):
        parts.append("next to nothing yet")
    return ", ".join(parts)
