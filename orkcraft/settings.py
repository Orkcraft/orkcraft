"""Machine settings (`$XDG_CONFIG_HOME/orkcraft/settings.json`): what onboarding asks once per machine.

    s = settings.load()              # never raises; defaults for anything missing or broken
    s.tools["claude"].billing        # "subscription" | "api"
    s.quiet                          # 🌙 do-not-disturb hours (schedule.py)
    s.autonomy                       # 0 ⛓️ in chains · 1 🕰 on the clock · 2 ⛓️‍💥 unchained (autonomy.py)
    s.autonomy_wait                  # minutes a question waits for the operator (1..60)
    s.rebuild_wait                   # hours (the operator around) a rebuild waits (1..48)
    s.profile                        # who the operator is and how their day goes (realm/intents.py)
    s.growth                         # the operator's mascot stage and deeds (realm/growth.py)
    s.usage, s.install_id            # anonymous usage stats: None not asked yet (core/usage.py)
    settings.save(s)

The tools the operator leads and how each is paid for, and the quiet hours of their day (design:
docs/design/onboarding.md). There is one look now: `mode`, `office` and `office_days` of older
settings files still load and are ignored, and are no longer written.
Orkcraft never stores an API key here: `billing` only says how the CLI is paid for.
"""
from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from orkcraft import autonomy as autonomy_
from orkcraft.env import getenv
from orkcraft.schedule import Span

TOOLS = ("claude", "agy", "codex")
BILLINGS = ("subscription", "api")
PROFILE_TEXT = ("orchestration", "role", "role_other", "industry", "industry_other", "day_other")
PROFILE_LISTS = ("day",)


@dataclass
class ToolChoice:
    enabled: bool = False
    billing: str = "subscription"


@dataclass
class MachineSettings:
    tools: dict[str, ToolChoice] = field(default_factory=lambda: {t: ToolChoice() for t in TOOLS})
    onboarded: bool = False       # the machine's part of onboarding is done
    quiet: Span | None = None     # 🌙 do-not-disturb hours; None = off
    autonomy: int = autonomy_.DEFAULT_LEVEL   # 0 chains · 1 clock · 2 free; kept as a word (autonomy.py)
    autonomy_wait: int = autonomy_.DEFAULT_WAIT   # a question: minutes
    rebuild_wait: int = autonomy_.DEFAULT_REBUILD   # a rebuild: hours the operator is around
    profile: dict = field(default_factory=dict)   # orchestration, role, industry (+ _other), day, ai_tools
    growth: dict = field(default_factory=dict)    # stage (1–4) and deeds {id: date}: the operator's, every camp's
    # The 🛡 Warder's agy hook was checked on a live agy here (docs/design/agy-guard.md, smoke test):
    # only then does onboarding say the Warder guards agy and install its hook. Off until someone does.
    agy_warder_checked: bool = False
    usage: bool | None = None     # anonymous usage stats (core/usage.py): None until the operator answers
    install_id: str = ""          # a random id while they share them; forgotten when they stop
    fire: bool = True             # flames over a building whose ork has waited a minute or more (the GUI's huts)

    def to_dict(self) -> dict:
        return {
            "tools": {t: {"enabled": c.enabled, "billing": c.billing} for t, c in self.tools.items()},
            "onboarded": self.onboarded,
            "quiet": self.quiet.to_dict() if self.quiet else None,
            "autonomy": autonomy_.word(self.autonomy),
            "autonomy_wait": self.autonomy_wait,
            "rebuild_wait": self.rebuild_wait,
            "profile": self.profile,
            "growth": self.growth,
            "agy_warder_checked": self.agy_warder_checked,
            "usage": {"share": self.usage, "id": self.install_id},
            "fire": self.fire,
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
        s.onboarded = bool(data.get("onboarded", False))
        s.quiet = Span.from_dict(data.get("quiet"))
        s.autonomy = autonomy_.of(data.get("autonomy"))
        s.autonomy_wait = autonomy_.wait_of(data.get("autonomy_wait"))
        s.rebuild_wait = autonomy_.rebuild_of(data.get("rebuild_wait"))
        s.profile = clean_profile(data.get("profile"))
        s.growth = clean_growth(data.get("growth"))
        s.agy_warder_checked = data.get("agy_warder_checked") is True
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        s.usage = usage.get("share") if isinstance(usage.get("share"), bool) else None
        s.fire = data.get("fire") is not False
        install_id = usage.get("id")
        if s.usage:                   # a broken id is drawn again: the stats never carry what was in the file
            ok = isinstance(install_id, str) and re.fullmatch(r"[0-9a-f]{32}", install_id)
            s.install_id = install_id if ok else uuid.uuid4().hex
        return s


def clean_growth(raw: object) -> dict:
    """The mascot's stage (1–4) and the deeds done with their dates; {} for anything else."""
    if not isinstance(raw, dict):
        return {}
    out: dict = {}
    if isinstance(raw.get("stage"), int) and 1 <= raw["stage"] <= 4:
        out["stage"] = raw["stage"]
    deeds = raw.get("deeds")
    if isinstance(deeds, dict):
        out["deeds"] = {str(k)[:40]: str(v)[:20] for k, v in list(deeds.items())[:40] if isinstance(v, str)}
    return out


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


def preset_role(role_id: str, file: Path | None = None) -> bool:
    """`orkcraft --role`: the role the landing page was told, kept for the onboarding to open on.
    It never overrides a role the operator picked in an onboarding they finished. True when kept."""
    s = load(file)
    if s.onboarded and s.profile.get("role"):
        return False
    s.profile = {**s.profile, "role": role_id}
    save(s, file)
    return True


def save(s: MachineSettings, file: Path | None = None) -> None:
    file = file or path()
    file.parent.mkdir(parents=True, exist_ok=True)
    tmp = file.with_suffix(file.suffix + ".tmp")
    tmp.write_text(json.dumps(s.to_dict(), indent=2) + "\n", encoding="utf-8")
    tmp.replace(file)
