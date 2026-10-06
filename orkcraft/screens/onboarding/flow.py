"""🧭 Onboarding, the flow: pushes the steps one after another and applies what was chosen."""
from __future__ import annotations

import threading
from dataclasses import replace
from typing import Callable

from orkcraft import settings, tools
from orkcraft.realm import interview
from orkcraft.screens.autonomy import AutonomyStep
from orkcraft.screens.onboarding.common import CUSTOM, EMPTY, agy_warder_line, hide_skip
from orkcraft.screens.onboarding.person import PersonStep, QuestionsStep, XpStep
from orkcraft.screens.onboarding.town import IntentStep
from orkcraft.screens.onboarding.machine import DETECTED, ToolsStep, detect_all


XP, PERSON, TOOLS, INTENT, RULES = "xp", "person", "tools", "intent", "rules"
WHO_KEYS = ("role", "role_other", "industry", "industry_other", "day", "day_other")
INTERVIEW_STEPS = tuple(f"q:{p.id}" for p in interview.INTERVIEW)


class Onboarding:
    """Pushes the steps one after another, Back and Skip included, and applies what was chosen.

    The first answer — how well the operator knows orkestration — picks the path:
      🐣 new / 🪓 some   who you are (and your day) · your AI tools · the town (· 2 interview pages) · camp rules
      🤘 punk ork        your AI tools · camp rules, then an empty town to build themselves
    The AI tools are looked for in the background from the start, so their step opens ready. A
    newcomer gets no Skip after the first step. The person's part is asked when the machine is new
    or the profile is missing; the town for a project with none yet. `on_town(choice)` is called at
    the end with {"preset", "role", "warder", "prompt", "answers", "expert"} (an empty town on
    skip); the app raises it."""

    def __init__(self, app, machine_steps: bool, town_step: bool, on_town: Callable[[dict], None],
                 statuses: list[tools.ToolStatus] | None = None) -> None:
        self.app = app
        self.machine_steps = machine_steps
        self.town_step = town_step
        self.on_town = on_town
        self.detected: DETECTED | None = (statuses, []) if statuses is not None else None
        self.machine = settings.load()
        self.profile = dict(self.machine.profile)
        self.answers: dict = {}
        self.choice: dict = {}
        self.picked: dict[str, settings.ToolChoice] | None = None
        self.autonomy = self.machine.autonomy
        self.autonomy_wait = self.machine.autonomy_wait
        self.rebuild_wait = self.machine.rebuild_wait
        self.warder = True
        self.day: dict | None = None
        self.ask_person = machine_steps or not self.profile.get("orchestration") or (
            not self.expert and not self.profile.get("role"))
        self.steps = self._plan()
        self.i = 0
        if machine_steps and self.detected is None:
            threading.Thread(target=self._detect, daemon=True).start()

    def _detect(self) -> None:
        """In the background from the first step: the tools step opens with them found."""
        detected = detect_all()
        if self.detected is None:
            self.detected = detected

    @property
    def expert(self) -> bool:
        return self.profile.get("orchestration") == interview.EXPERT

    @property
    def novice(self) -> bool:
        return self.profile.get("orchestration") == interview.NEW

    def _plan(self) -> list[str]:
        """The steps of this run, from what is known so far (the first answer reshapes them)."""
        steps: list[str] = []
        if self.ask_person:
            steps.append(XP)
            if not self.expert:
                steps.append(PERSON)
        if self.machine_steps:
            steps.append(TOOLS)
        if self.town_step and not self.expert:
            steps.append(INTENT)
            if self._interviewing:
                steps += list(INTERVIEW_STEPS)
        if self.machine_steps:
            steps.append(RULES)
        return steps

    def start(self) -> None:
        if self.steps:
            self._show()
        elif self.town_step:                  # a punk ork's new project: nothing to ask
            self.warder = False
            self._finish()

    @property
    def step(self) -> str:
        return f"step {self.i + 1} of {len(self.steps)}" if len(self.steps) > 1 else ""

    @property
    def claude_on(self) -> bool:
        tools_ = {**self.machine.tools, **(self.picked or {})}
        return tools_.get("claude", settings.ToolChoice()).enabled

    def _show(self) -> None:
        name, back, last = self.steps[self.i], self.i > 0, self.i == len(self.steps) - 1
        done = lambda result: self._done(name, result)  # noqa: E731
        if name == XP:
            screen = XpStep(self.profile.get("orchestration", ""), self.step, can_back=back)
        elif name == PERSON:
            screen = PersonStep(self.profile, self.step, can_back=back)
        elif name == TOOLS:
            screen = ToolsStep(self.machine, self.detected, self.step, can_back=back, show_warder=self.town_step,
                               chosen=self.picked, warder=self.warder, ratings=self.profile.get("ai_tools"))
        elif name == INTENT:
            screen = IntentStep(self.profile, self.step, back, last and not self._interviewing,
                                show_warder=TOOLS not in self.steps and self.claude_on, choice=self.choice,
                                builder=self.claude_on,
                                agy_line=agy_warder_line(self.machine.agy_warder_checked,
                                                         self.detected[0] if self.detected else None))
        elif name in INTERVIEW_STEPS:
            page = interview.INTERVIEW[INTERVIEW_STEPS.index(name)]
            screen = QuestionsStep(page, self.answers, {**self.profile, "role": self.choice.get("role", "")},
                                   self.step, back, last)
        else:
            enabled = tuple(t for t, c in {**self.machine.tools, **(self.picked or {})}.items() if c.enabled)
            screen = AutonomyStep(self.autonomy, enabled or ("claude", "agy"), step=self.step, look=self.machine,
                                  wait=self.autonomy_wait, rebuild=self.rebuild_wait)
        self.app.push_screen(screen, done)
        if self.novice and name != XP:
            self.app.call_after_refresh(hide_skip, screen)

    @property
    def _interviewing(self) -> bool:
        return self.choice.get("preset") == CUSTOM

    def _done(self, name: str, result: dict | str | None) -> None:
        if result is None:
            return
        if result == "back":
            self.i = max(0, self.i - 1)
            self._show()
            return
        if result == "skip" or (isinstance(result, dict) and result.get("action") == "skip"):
            if isinstance(result, dict):
                self.picked = result.get("tools") or {}
            self._skip()
            return
        assert isinstance(result, dict)
        if name == XP:
            self.profile["orchestration"] = result["orchestration"]
            self.steps = self._plan()
        elif name == PERSON:
            keep = {k: v for k, v in self.profile.items() if k not in WHO_KEYS}
            self.profile = {**keep, **result["profile"]}
        elif name == TOOLS:
            self.picked = result.get("tools") or {}
            self.detected = result.get("detected") or self.detected
            self.warder = bool(result.get("warder"))
            if result.get("ratings"):
                self.profile["ai_tools"] = result["ratings"]
            else:
                self.profile.pop("ai_tools", None)
        elif name == INTENT:
            self.choice = result
            self.warder = result.get("warder", self.warder) if TOOLS not in self.steps else self.warder
            self.steps = self._plan()
        elif name in INTERVIEW_STEPS:
            page = interview.INTERVIEW[INTERVIEW_STEPS.index(name)]
            for q in page.questions:
                self.answers.pop(f"{q.id}_other", None)
            self.answers.update(result["answers"])
        elif name == RULES:
            self.autonomy = int(result.get("autonomy", self.autonomy))
            self.autonomy_wait = int(result.get("autonomy_wait", self.autonomy_wait))
            self.rebuild_wait = int(result.get("rebuild_wait", self.rebuild_wait))
            self.day = {"mode": result.get("mode", self.machine.mode), "quiet": result.get("quiet"),
                        "office": self.machine.office, "office_days": self.machine.office_days}
        self.i += 1
        if self.i < len(self.steps):
            self._show()
        else:
            self._finish()

    def _save_machine(self, day: dict | None) -> None:
        """The profile, and — when the machine's part was asked — tools, autonomy, mode and the day."""
        machine = replace(self.machine, profile=settings.clean_profile(self.profile))
        if not self.machine_steps:
            settings.save(machine)
            desktop = getattr(self.app, "desktop", None)
            if desktop is not None:
                desktop.machine.profile = machine.profile
            self.machine = machine
            return
        tools_ = dict(self.machine.tools)
        tools_.update(self.picked or {})
        machine = replace(machine, tools=tools_, onboarded=True, autonomy=self.autonomy,
                          autonomy_wait=self.autonomy_wait, rebuild_wait=self.rebuild_wait)
        if not self.machine.onboarded and day is None:
            machine.mode = settings.DEFAULT_MODE
        desktop = getattr(self.app, "desktop", None)
        apply_day = getattr(self.app, "apply_day", None)
        if desktop is not None and apply_day is not None:
            desktop.machine = machine
            settings.save(machine)
            apply_day(day or {"mode": machine.mode, "quiet": machine.quiet, "office": machine.office,
                              "office_days": machine.office_days})
            machine = desktop.machine
        else:
            if day:
                machine.mode, machine.quiet, machine.office = day["mode"], day["quiet"], day["office"]
            settings.save(machine)
        self.machine = machine

    def _finish(self) -> None:
        self._save_machine(self.day)
        if not self.town_step:
            return
        choice = {"preset": self.choice.get("preset") or EMPTY, "role": self.choice.get("role", ""),
                  "warder": self.warder and self.claude_on, "prompt": "", "answers": {}, "expert": self.expert}
        if choice["preset"] == CUSTOM:
            choice["answers"] = dict(self.answers)
            choice["prompt"] = interview.summary({**self.profile, "role": self.profile.get("role", "")},
                                                 self.answers)
        self.on_town(choice)

    def _skip(self) -> None:
        if self.picked is None and self.detected is not None:          # skipped before the tools: the found ones
            self.picked = {st.id: settings.ToolChoice(enabled=st.found and st.tool.available, billing=st.billing)
                           for st in self.detected[0]}
        self._save_machine(None)
        if self.town_step:
            self.on_town({"preset": EMPTY, "role": "", "warder": False, "prompt": "", "answers": {}})
