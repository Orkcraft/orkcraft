"""Town presets for onboarding: a whole town by domain (design: docs/design/onboarding.md).

    DOMAINS                      engineering · design · management · indie, each with its mascot
    of_domain("design")          the presets of a domain
    buildings_of("solo_forge")   what the preset raises — () for now: every preset is a stub
    save_order(root, prompt)     "Didn't find it?": the town described in words, waiting in the Town Hall

A town preset will be a piece of the Town Scroll (buildings, roads, layout). Until they are drawn,
every preset raises an empty town (the Town Hall alone), and a custom prompt waits as an order
for the Town Hall's Builder.
"""
from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass
from pathlib import Path

ORDER = Path(".orkcraft") / "town" / "order.json"


@dataclass(frozen=True)
class Domain:
    id: str
    title: str
    icon: str
    mascot: str          # orc · elf · knight · skeleton
    art: tuple[str, ...]


@dataclass(frozen=True)
class TownPreset:
    id: str
    domain: str
    icon: str
    title: str
    blurb: str
    buildings: tuple[str, ...] = ()     # building types it raises; () = a stub, the empty town
    needs_agent: bool = False           # unavailable when onboarding chose no tool

    @property
    def stub(self) -> bool:
        return not self.buildings


ORC = ("   ,      ,   ",
       "  /(.-\"\"-.)\\  ",
       "  \\  o  o  /  ",
       "   | v  v |   ",
       "   \\ '--' /   ",
       "  _/`----`\\_  ",
       " /  ORC   \\_\\ ")
ELF = ("      /\\      ",
       "  <\\ (  ) />  ",
       "    \\ -- /    ",
       "   /|    |\\   ",
       "  / | ** | \\  ",
       "    |    |    ",
       "    / ELF\\    ")
KNIGHT = ("     _||_     ",
          "    /____\\    ",
          "    |-==-|    ",
          "    \\____/    ",
          "  [|  ++  |]  ",
          "   |  ++  |   ",
          "   /KNIGHT\\   ")
SKELETON = ("    .----.    ",
            "   ( o  o )   ",
            "    | ^^ |    ",
            "    '-==-'    ",
            "   --|##|--   ",
            "     |##|     ",
            "  /SKELETON\\  ")

DOMAINS: tuple[Domain, ...] = (
    Domain("engineering", "Engineering", "⚔️", "orc", ORC),
    Domain("design", "Design", "🧝", "elf", ELF),
    Domain("management", "Management", "🛡", "knight", KNIGHT),
    Domain("indie", "Indie", "💀", "skeleton", SKELETON),
)

PRESETS: tuple[TownPreset, ...] = (
    TownPreset("solo_forge", "engineering", "🛠", "Solo Forge", "one developer: tasks → agents → tests → merge"),
    TownPreset("review_gate", "engineering", "🔍", "Review Gate", "PR review and diff inspection"),
    TownPreset("bug_hunt", "engineering", "🐛", "Bug Hunt", "bug reports triaged and fixed in worktrees"),
    TownPreset("release_train", "engineering", "🚀", "Release Train", "changelog, tests, cutting a release"),
    TownPreset("mockup_grove", "design", "🎨", "Mockup Grove", "an idea → mockup variants → a pick"),
    TownPreset("design_system", "design", "📐", "Design System", "tokens, components, consistency checks"),
    TownPreset("asset_pipeline", "design", "🖼", "Asset Pipeline", "generating assets and accepting them in the Loot Vault"),
    TownPreset("critique_circle", "design", "🗣", "Critique Circle", "the Orc Council argues over design decisions"),
    TownPreset("war_room", "management", "📋", "War Room", "tasks, statuses, a daily digest"),
    TownPreset("inbox_keep", "management", "📨", "Inbox Keep", "mail, GitHub and webhooks sorted into tasks"),
    TownPreset("sprint_drum", "management", "🥁", "Sprint Drum", "sprint planning, calendar, retro"),
    TownPreset("ledger_tower", "management", "📊", "Ledger Tower", "metrics, spend, reports"),
    TownPreset("game_jam", "indie", "🎮", "Game Jam", "a fast prototype, tasks and builds"),
    TownPreset("one_skeleton_studio", "indie", "🏚", "One-Skeleton Studio", "code, copy and marketing in one town"),
    TownPreset("launch_crypt", "indie", "📣", "Launch Crypt", "landing page, posts, collecting feedback"),
    TownPreset("side_quest", "indie", "🧪", "Side Quest", "a light town for a pet project"),
)


def domain(domain_id: str) -> Domain:
    return next((d for d in DOMAINS if d.id == domain_id), DOMAINS[0])


def of_domain(domain_id: str) -> list[TownPreset]:
    return [p for p in PRESETS if p.domain == domain_id]


def preset(preset_id: str) -> TownPreset | None:
    return next((p for p in PRESETS if p.id == preset_id), None)


def buildings_of(preset_id: str) -> tuple[str, ...]:
    p = preset(preset_id)
    return p.buildings if p is not None else ()


# -- the pending order: a town described in words -------------------------------------------------

def save_order(root: Path, prompt: str, domain_id: str = "") -> Path:
    path = Path(root) / ORDER
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"prompt": prompt.strip(), "domain": domain_id, "seen": False,
            "ts": dt.datetime.now().isoformat(timespec="seconds")}
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def pending_order(root: Path | None) -> dict | None:
    if root is None:
        return None
    try:
        data = json.loads((Path(root) / ORDER).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and str(data.get("prompt", "")).strip() else None


def mark_order_seen(root: Path) -> None:
    order = pending_order(root)
    if order is None or order.get("seen"):
        return
    order["seen"] = True
    (Path(root) / ORDER).write_text(json.dumps(order, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
