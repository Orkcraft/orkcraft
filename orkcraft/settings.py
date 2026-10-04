"""Machine settings (`$XDG_CONFIG_HOME/orkcraft/settings.json`): what onboarding asks once per machine.

    s = settings.load()              # never raises; defaults for anything missing or broken
    s.tools["claude"].billing        # "subscription" | "api"
    s.mode                           # "camp" | "office" | "shift"
    s.quiet, s.office, s.office_days # 🌙 do-not-disturb and 👔 office hours (schedule.py)
    s.autonomy                       # 0..3: how much the orcs do on their own (autonomy.py)
    s.profile                        # who the operator is and how their day goes (realm/intents.py)
    settings.save(s)

The tools the operator leads and how each is paid for, the display mode and the day's schedule:
🧌 Camp — buildings wear their ASCII; 👔 Office — just frames; 🧌/👔 Shift — Office in office hours
on office days, Camp otherwise. A project may still override the mode with `preferences.mode` in
its Town Scroll (design: docs/design/onboarding.md).
Orkcraft never stores an API key here: `billing` only says how the CLI is paid for.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from orkcraft import schedule
from orkcraft.env import getenv
from orkcraft.schedule import Span

TOOLS = ("claude", "agy", "codex")
BILLINGS = ("subscription", "api")
MODES = ("camp", "office", "shift")
LEGACY_MODES = {"immersion": "camp", "plain": "office", "hidden": "office"}   # older names of camp / office
DEFAULT_MODE = "camp"
MODE_TITLES = {"camp": "🧌 Camp", "office": "👔 Office", "shift": "🧌/👔 Shift"}
PROFILE_TEXT = ("orchestration", "role", "role_other", "industry", "industry_other", "day_other")
PROFILE_LISTS = ("day",)


def mode_of(value: object) -> str | None:
    """A mode by its name, old names included; None when it is none of them."""
    value = LEGACY_MODES.get(str(value), value)
    return value if value in MODES else None


@dataclass
class ToolChoice:
    enabled: bool = False
    billing: str = "subscription"


@dataclass
class MachineSettings:
    tools: dict[str, ToolChoice] = field(default_factory=lambda: {t: ToolChoice() for t in TOOLS})
    mode: str = DEFAULT_MODE
    onboarded: bool = False       # the machine's part of onboarding is done
    quiet: Span | None = None     # 🌙 do-not-disturb hours; None = off
    office: Span = schedule.DEFAULT_OFFICE                      # 👔 Shift: office hours…
    office_days: tuple[int, ...] = schedule.DEFAULT_OFFICE_DAYS  # …on these days (0 = Monday)
    autonomy: int = 1             # 0 ask me · 1 morning advice · 2 routine · 3 free orcs (autonomy.py)
    profile: dict = field(default_factory=dict)   # orchestration, role, industry (+ _other), day, ai_tools

    def to_dict(self) -> dict:
        return {
            "tools": {t: {"enabled": c.enabled, "billing": c.billing} for t, c in self.tools.items()},
            "mode": self.mode,
            "onboarded": self.onboarded,
            "quiet": self.quiet.to_dict() if self.quiet else None,
            "office": self.office.to_dict(),
            "office_days": list(self.office_days),
            "autonomy": self.autonomy,
            "profile": self.profile,
        }

    @classmethod
    def from_dict(cls, data: dict) -> MachineSettings:
        s = cls()
        tools = data.get("tools") if isinstance(data.get("tools"), dict) else {}
        for t in TOOLS:
            raw = tools.get(t)
            if isinstance(raw, dict):
                billing = raw.get("billing")
                s.tools[t] = ToolChoice(enabled=bool(raw.get("enabled", False)),
                                        billing=billing if billing in BILLINGS else "subscription")
        s.mode = mode_of(data.get("mode")) or DEFAULT_MODE
        s.onboarded = bool(data.get("onboarded", False))
        s.quiet = Span.from_dict(data.get("quiet"))
        s.office = Span.from_dict(data.get("office")) or schedule.DEFAULT_OFFICE
        days = data.get("office_days")
        if isinstance(days, list):
            s.office_days = tuple(sorted({d for d in days if isinstance(d, int) and 0 <= d <= 6}))
        level = data.get("autonomy", 1)
        s.autonomy = level if isinstance(level, int) and not isinstance(level, bool) and 0 <= level <= 3 else 1
        s.profile = clean_profile(data.get("profile"))
        return s


def clean_profile(raw: object) -> dict:
    """Only the known keys, as strings and lists of strings; {} for anything else."""
    if not isinstance(raw, dict):
        return {}
    out: dict = {k: str(raw[k])[:200] for k in PROFILE_TEXT if isinstance(raw.get(k), str) and raw[k].strip()}
    for k in PROFILE_LISTS:
        if isinstance(raw.get(k), list):
            out[k] = [str(x)[:40] for x in raw[k] if isinstance(x, str)][:20]
    tools_ = raw.get("ai_tools")
    if isinstance(tools_, dict):
        rated = {}
        for t, r in list(tools_.items())[:20]:
            if not isinstance(r, dict):
                continue
            keep: dict = {k: bool(r.get(k)) for k in ("like", "dislike")}
            keep.update({k: str(r[k])[:40] for k in ("title", "good", "weak") if isinstance(r.get(k), str) and r[k]})
            rated[str(t)[:40]] = keep
        if rated:
            out["ai_tools"] = rated
    return out


def path() -> Path:
    """`$ORKCRAFT_SETTINGS_FILE`, else `$XDG_CONFIG_HOME/orkcraft/settings.json`."""
    env = getenv("SETTINGS_FILE")
    if env:
        return Path(env).expanduser()
    base = os.environ.get("XDG_CONFIG_HOME", "").strip() or str(Path.home() / ".config")
    return Path(base) / "orkcraft" / "settings.json"


def load(file: Path | None = None) -> MachineSettings:
    file = file or path()
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return MachineSettings()
    return MachineSettings.from_dict(data) if isinstance(data, dict) else MachineSettings()


def save(s: MachineSettings, file: Path | None = None) -> None:
    file = file or path()
    file.parent.mkdir(parents=True, exist_ok=True)
    tmp = file.with_suffix(file.suffix + ".tmp")
    tmp.write_text(json.dumps(s.to_dict(), indent=2) + "\n", encoding="utf-8")
    tmp.replace(file)
