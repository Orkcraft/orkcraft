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
    s.updates                        # auto | critical | ask: which updates install by themselves (core/updates.py)
    s.phones, s.phone_port           # the paired phones (only their tokens' hashes) and their listener's port (gui/pairing.py)
    s.look                           # camp | office: how the GUI draws the town for this person (docs/design/portrait.md)
    s.dnd_until                      # Do not disturb: "" off, "on" until turned off, else an ISO time (disturb.py)
    settings.save(s)

The tools the operator leads and how each is paid for, and the quiet hours of their day (design:
docs/design/onboarding.md). There is one look now: `mode`, `office` and `office_days` of older
settings files still load and are ignored, and are no longer written. `look` is not a mode: it changes
only how the GUI draws (docs/design/portrait.md §3).
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
from orkcraft.realm import harnesses
from orkcraft.schedule import Span

TOOLS = harnesses.ids()
BILLINGS = ("subscription", "api")
PROFILE_TEXT = ("orchestration", "role", "role_other", "industry", "industry_other", "day_other", "kin")
PROFILE_LISTS = ("day", "mcp")   # mcp: the MCP servers the orks may use (gui/onboarding.py)
UPDATES = ("auto", "critical", "ask")   # core/updates.py POLICIES
LOOKS = ("camp", "office")               # the GUI's two looks; camp the default


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
    updates: str = "critical"     # which updates install by themselves when the town opens (core/updates.py)
    main_tool: str = ""           # the tool decisions run on (realm/harnesses.py); "" the first one on
    # The phones paired with this machine's towns (docs/design/mobile.md §2): id, name, the SHA-256 of the
    # device token (never the token), when paired and when last seen. The Town Scroll never holds them.
    phones: list = field(default_factory=list)
    phone_port: int = 0           # the phone listener's port, kept so a paired phone finds it again; 0 not chosen
    look: str = "camp"            # how the GUI draws the town for this person: camp | office (docs/design/portrait.md)
    dnd_until: str = ""           # Do not disturb: "" off, "on" until turned off, else when it ends (disturb.py)

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
            "updates": self.updates,
            "main_tool": self.main_tool,
            "phones": [dict(p) for p in self.phones],
            "phone_port": self.phone_port,
            "look": self.look,
            "dnd_until": self.dnd_until,
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
        s.updates = data["updates"] if data.get("updates") in UPDATES else "critical"
        s.main_tool = data["main_tool"] if data.get("main_tool") in TOOLS else ""
        s.phones = clean_phones(data.get("phones"))
        port = data.get("phone_port")
        s.phone_port = port if isinstance(port, int) and not isinstance(port, bool) and 1024 <= port <= 65535 else 0
        s.look = data["look"] if data.get("look") in LOOKS else "camp"
        s.dnd_until = clean_dnd(data.get("dnd_until"))
        install_id = usage.get("id")
        if s.usage:                   # a broken id is drawn again: the stats never carry what was in the file
            ok = isinstance(install_id, str) and re.fullmatch(r"[0-9a-f]{32}", install_id)
            s.install_id = install_id if ok else uuid.uuid4().hex
        return s


def clean_dnd(raw: object) -> str:
    """Do not disturb as stored: "on", an ISO time it ends at, else "" (off)."""
    if raw == "on":
        return "on"
    if isinstance(raw, str) and re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d(:\d\d)?", raw):
        return raw
    return ""


def clean_phones(raw: object) -> list[dict]:
    """The paired phones that are whole: an id, a name, a token's hash; anything else is dropped (a phone
    whose entry broke pairs again)."""
    out: list[dict] = []
    for p in raw if isinstance(raw, list) else []:
        if not isinstance(p, dict):
            continue
        pid, name, digest = p.get("id"), p.get("name"), p.get("hash")
        if not (isinstance(pid, str) and re.fullmatch(r"[0-9a-f]{16}", pid) and isinstance(digest, str)
                and re.fullmatch(r"[0-9a-f]{64}", digest) and isinstance(name, str) and name.strip()):
            continue
        if any(o["id"] == pid for o in out):
            continue
        out.append({"id": pid, "name": name.strip()[:60], "hash": digest,
                    "paired": str(p.get("paired") or "")[:32], "seen": str(p.get("seen") or "")[:32]})
    return out


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


def preset_role(role_id: str, file: Path | None = None, kin: str = "") -> bool:
    """`orkcraft --role`: the role the landing page was told, kept for the onboarding to open on.
    `kin`: the page named a class with two roles (gnome), so the GUI's onboarding asks which of the two.
    It never overrides a role the operator picked in an onboarding they finished. True when kept."""
    s = load(file)
    if s.onboarded and s.profile.get("role"):
        return False
    s.profile = {k: v for k, v in {**s.profile, "role": role_id, "kin": kin}.items() if k != "kin" or kin}
    save(s, file)
    return True


def _raw(file: Path) -> dict:
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write(file: Path, data: dict) -> None:
    file.parent.mkdir(parents=True, exist_ok=True)
    tmp = file.with_suffix(file.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    tmp.replace(file)


def save(s: MachineSettings, file: Path | None = None) -> None:
    """The settings as `s` has them, but the paired phones as the file has them: only `save_phones`
    writes those, so a town that loaded the settings before a phone was forgotten never brings it back."""
    file = file or path()
    data = s.to_dict()
    raw = _raw(file)
    data["phones"], data["phone_port"] = raw.get("phones", []), raw.get("phone_port", 0)
    _write(file, data)


def save_phones(phones: list[dict], port: int, file: Path | None = None) -> None:
    """The paired phones and their listener's port, everything else in the file as it is (gui/pairing.py)."""
    file = file or path()
    raw = _raw(file)
    raw["phones"], raw["phone_port"] = clean_phones(phones), port
    _write(file, raw)
