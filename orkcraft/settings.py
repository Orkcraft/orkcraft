"""Machine settings (`$XDG_CONFIG_HOME/orkcraft/settings.json`): what onboarding asks once per machine.

    s = settings.load()              # never raises; defaults for anything missing or broken
    s.tools["claude"].billing        # "subscription" | "api"
    s.mode                           # "immersion" | "hidden" (the office mode; `plain` reads as hidden)
    settings.save(s)

The tools the operator leads and how each is paid for, and the display mode. A project may still
override the mode with `preferences.mode` in its Town Scroll (design: docs/design/onboarding.md).
Orkcraft never stores an API key here: `billing` only says how the CLI is paid for.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from orkcraft.env import getenv

TOOLS = ("claude", "agy", "codex")
BILLINGS = ("subscription", "api")
MODES = ("immersion", "hidden")
DEFAULT_MODE = "immersion"


@dataclass
class ToolChoice:
    enabled: bool = False
    billing: str = "subscription"


@dataclass
class MachineSettings:
    tools: dict[str, ToolChoice] = field(default_factory=lambda: {t: ToolChoice() for t in TOOLS})
    mode: str = DEFAULT_MODE
    onboarded: bool = False       # steps 1–2 of onboarding done on this machine

    def to_dict(self) -> dict:
        return {
            "tools": {t: {"enabled": c.enabled, "billing": c.billing} for t, c in self.tools.items()},
            "mode": self.mode,
            "onboarded": self.onboarded,
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
        if data.get("mode") in MODES:
            s.mode = data["mode"]
        elif data.get("mode") == "plain":         # the hidden mode's old name
            s.mode = "hidden"
        s.onboarded = bool(data.get("onboarded", False))
        return s


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
