"""The onboarding in the window (docs/design/gui-onboarding.md): your AI tools, who you are, the tools the
orks may use, your first town, and the town going up while you watch.

A project with no town yet opens on it. Each step is skipped when its answer is already known: the class
the landing page gave (`orkcraft --role`), a class with one role, a machine with no MCP server. Nothing is
written until the town is chosen; then the machine's part is saved and the town rises one step a tick,
so the map fills in front of the person while the Autonomy card waits in a corner (js/onboarding.js).

    ob = Onboarding(host)                 # active on a first run, unless ORKCRAFT_ONBOARDING=0
    host.commands.update(ob.commands())   # onboarding.tools · .role · .mcp · .town · .survey · …
    ob.snapshot()                         # the snapshot's `onboarding`, None when there is none
    ob.tick(now)                          # from the host's clock: the next raising step
"""
from __future__ import annotations

import threading
import time
from dataclasses import replace
from typing import Any, Callable
from urllib.parse import urlencode

from orkcraft import settings, tools
from orkcraft.core import buildings, roads, runners
from orkcraft.env import getenv
from orkcraft.realm import biomes, builders, checkpoint, intents, interview, mcp, town_builder, town_presets

TOOLS, WHO, MCP, TOWN, SURVEY, RAISING = "tools", "who", "mcp", "town", "survey", "raising"
RAISE_STEP_S = 0.8          # between two raising steps: slow enough to see each building go up
ISSUES = "https://github.com/Orkcraft/orkcraft/issues/new"
BEST = ("code", "copy", "data", "search", "tickets")      # what a tool is best at, on the survey
BEST_TITLES = {"code": "Code", "copy": "Copy and content", "data": "Data and numbers", "search": "Search and research",
               "tickets": "Tickets"}


class OnboardingError(Exception):
    """A step the page sent that cannot be taken; its text is shown to the person."""


def wanted(town) -> bool:
    return town.first_run and not town.demo and getenv("ONBOARDING").lower() not in ("0", "false", "no", "off")


class Onboarding:
    def __init__(self, host, detect: Callable[[], list[tools.ToolStatus]] | None = None,
                 detect_others: Callable[[], list[tools.Other]] | None = None,
                 servers: Callable[[], list[mcp.Server]] | None = None) -> None:
        self.host = host
        self.active = wanted(host.town)
        self.step = TOOLS
        machine = host.town.machine
        self.profile = dict(machine.profile)
        self.kin = intents.role(self.profile["role"]).mascot if self.profile.get("role") else ""
        self.role_given = bool(self.profile.get("role"))         # the landing page's class (settings.preset_role)
        self.statuses: list[tools.ToolStatus] | None = None
        self.others: list[tools.Other] = []
        self.picked: dict[str, settings.ToolChoice] = {}
        self.warder = True
        self.servers: list[mcp.Server] = []
        self.mcp_on: list[str] = []
        self.raising: dict[str, Any] | None = None
        self._queue: list[tuple[str, Callable[[], Any], str]] = []    # (label, act, building id or "")
        self._next_at = 0.0
        self._plan_title = ""
        if self.active:
            find = servers or (lambda: mcp.found(repo=host.town.repo_root))
            self.servers = find()
            self.mcp_on = [s.id for s in self.servers]
            self._finder = threading.Thread(target=self._detect, daemon=True,
                                            args=(detect or (lambda: tools.detect()), detect_others or (lambda: tools.detect_others())))
            self._finder.start()

    # -- what the page sees ------------------------------------------------------------------------

    def _detect(self, detect, detect_others) -> None:
        """The AI tools, on a thread: `--version` runs for each. The page shows them when they are in."""
        try:
            found, others = detect(), detect_others()
        except Exception:                           # a broken tool never stops the onboarding
            found, others = [], []
        self.host.town.call(self._detected, found, others)

    def _detected(self, found: list[tools.ToolStatus], others: list[tools.Other]) -> None:
        self.statuses, self.others = found, others
        self.picked = {st.id: settings.ToolChoice(enabled=st.found and st.tool.available, billing=st.billing)
                       for st in found}
        self.host.on_change()

    def steps(self) -> list[str]:
        """The steps of this run, from what is known so far."""
        out = [TOOLS]
        if not self.role_given:
            out.append(WHO)
        if self.servers:
            out.append(MCP)
        out.append(TOWN)
        return out

    @staticmethod
    def _classes() -> list[dict]:
        """Every role as a class card, each kin's second role with the next stage's head so the two differ."""
        out, seen = [], {}
        for r in intents.ROLES:
            seen[r.mascot] = seen.get(r.mascot, 0) + 1
            out.append({"id": r.id, "nick": r.nick, "title": r.title, "kin": r.mascot, "stage": seen[r.mascot],
                        "biome": biomes.HOMES.get(r.mascot, "dirt")})
        return out

    def _tools_rows(self) -> list[dict]:
        rows = []
        for st in self.statuses or []:
            if not st.found:
                continue
            choice = self.picked.get(st.id, settings.ToolChoice())
            rows.append({"id": st.id, "title": st.tool.title, "version": st.version, "logged_in": st.logged_in,
                         "login": st.tool.login, "enabled": choice.enabled, "billing": choice.billing})
        return rows

    def _towns(self) -> list[dict]:
        role = self.profile.get("role") or ""
        if not role:
            return []
        on = set(self.mcp_on)
        glyphs = [s.glyph or s.id for s in self.servers if s.id in on]
        out = []
        for it in intents.for_role(role):
            plan = it.plan
            out.append({
                "id": it.id, "title": it.title, "icon": it.icon, "blurb": it.blurb,
                "summary": plan.get("summary", ""),
                "buildings": [{"key": b["key"], "type": b["type"], "title": b["title"], "why": b.get("why", ""),
                               # what an agent uses shows on the building that runs agents or sends things out
                               "badges": glyphs[:3] if b["type"] in ("barracks", "catapult") else []}
                              for b in plan.get("buildings", [])],
                "roads": [{"from": r["from"], "to": r["to"], "why": r.get("why", "")}
                          for r in plan.get("roads", [])]})
        return out

    def _survey(self) -> dict:
        role = self.profile.get("role") or ""
        out: dict[str, Any] = {}
        for page in interview.INTERVIEW:
            for q in page.questions:
                out[q.id] = [{"id": c.id, "title": c.title, "common": common} for c, common in page.options(q, role)]
        out["best"] = [{"id": b, "title": BEST_TITLES[b]} for b in BEST]
        return out

    def snapshot(self) -> dict[str, Any] | None:
        if not self.active:
            return None
        steps = self.steps()
        machine = self.host.town.machine
        claude_on = self.picked.get("claude", machine.tools.get("claude", settings.ToolChoice())).enabled
        return {
            "step": self.step, "steps": steps,
            "n": steps.index(self.step) if self.step in steps else len(steps) - 1,
            "tools": {"ready": self.statuses is not None, "rows": self._tools_rows(),
                      "missing": [st.tool.title for st in self.statuses or [] if not st.found],
                      "others": [{"id": o.id, "title": o.title} for o in self.others], "warder": self.warder},
            "classes": self._classes(),
            "kin": self.kin, "role": self.profile.get("role", ""),
            "nick": intents.nick(self.profile["role"]) if self.profile.get("role") else "",
            "biome": biomes.home_of(self.profile),
            "mcp": {"servers": [s.to_dict() for s in self.servers], "on": list(self.mcp_on)},
            "towns": self._towns(), "survey": self._survey() if self.step == SURVEY else None,
            "planner": runners.BUILD_RUNNER is not None or claude_on,
            "raising": self.raising,
        }

    # -- the page's commands -----------------------------------------------------------------------

    def commands(self) -> dict[str, Callable[[dict], Any]]:
        return {"onboarding.tools": self.set_tools, "onboarding.request": self.request,
                "onboarding.role": self.set_role, "onboarding.mcp": self.set_mcp,
                "onboarding.town": self.set_town, "onboarding.survey": self.set_survey,
                "onboarding.back": self.back, "onboarding.skip": self.skip, "onboarding.close": self.close}

    def _live(self) -> None:
        if not self.active or self.step == RAISING:
            raise OnboardingError("The onboarding is not open")

    def _go(self, after: str) -> dict | None:
        steps = self.steps()
        i = steps.index(after) if after in steps else -1
        self.step = steps[i + 1] if i + 1 < len(steps) else TOWN
        self.host.on_change()
        return self.snapshot()

    def set_tools(self, args: dict) -> dict | None:
        """Which tools the orks run on and how each is paid for; whether the Security reviewer guards the project."""
        self._live()
        for tid, c in (args.get("tools") or {}).items():
            if tid in self.picked and isinstance(c, dict):
                billing = c.get("billing") if c.get("billing") in ("subscription", "api") else self.picked[tid].billing
                self.picked[tid] = settings.ToolChoice(enabled=bool(c.get("enabled")), billing=billing)
        if isinstance(args.get("warder"), bool):
            self.warder = args["warder"]
        return self._go(TOOLS) if args.get("next") else self.snapshot()

    def request(self, args: dict) -> dict:
        """A tool the orks cannot run on yet: a filled-in GitHub issue for the browser. Nothing is sent from here."""
        name = str(args.get("name") or "").strip()[:80]
        if not name:
            raise OnboardingError("Name the tool")
        link = str(args.get("link") or "").strip()[:300]
        note = str(args.get("note") or "").strip()[:1000]
        body = "\n\n".join(x for x in (f"Tool: {name}", f"Link: {link}" if link else "",
                                       f"What orks would do with it: {note}" if note else "") if x)
        return {"url": f"{ISSUES}?{urlencode({'title': f'Support {name}', 'body': body, 'labels': 'tool request'})}"}

    def set_role(self, args: dict) -> dict | None:
        self._live()
        role = str(args.get("role") or "")
        if not any(r.id == role for r in intents.ROLES):
            raise OnboardingError("No such role")
        self.profile["role"] = role
        self.kin = intents.role(role).mascot
        return self._go(WHO)

    def set_mcp(self, args: dict) -> dict | None:
        self._live()
        known = {s.id for s in self.servers}
        self.mcp_on = [s for s in args.get("on") or [] if s in known]
        return self._go(MCP) if args.get("next") else self.snapshot()

    def back(self, args: dict) -> dict | None:
        self._live()
        steps = self.steps() + ([SURVEY] if self.step == SURVEY else [])
        i = steps.index(self.step) if self.step in steps else 0
        self.step = steps[max(0, i - 1)]
        self.host.on_change()
        return self.snapshot()

    def set_town(self, args: dict) -> dict | None:
        """A ready town (`preset`), the survey (`custom`) or an empty town (`empty`)."""
        self._live()
        if args.get("custom"):
            if not self.snapshot()["planner"]:
                raise OnboardingError("The town planner runs on Claude Code, and it is off")
            self.step = SURVEY
            self.host.on_change()
            return self.snapshot()
        if args.get("empty"):
            return self._begin(None, "")
        it = intents.intent(str(args.get("preset") or ""))
        if it is None or it.role != self.profile.get("role"):
            raise OnboardingError("No such town for this class")
        return self._begin(it, "")

    def set_survey(self, args: dict) -> dict | None:
        """The survey's answers become the Town planner's order; the town is drawn from it, then raised."""
        self._live()
        answers: dict[str, Any] = {}
        for qid in interview.ALL_QUESTIONS:
            picked = [str(x)[:40] for x in args.get(qid) or [] if isinstance(x, str)][:20]
            if picked:
                answers[qid] = picked
        for key in ("sources_other", "outputs_other"):
            if str(args.get(key) or "").strip():
                answers[key] = str(args[key]).strip()[:200]
        best, notes = [], []
        for tid, r in (args.get("best") or {}).items():
            if not isinstance(r, dict):
                continue
            title = str(r.get("title") or tid)[:40]
            if r.get("best") in BEST:
                best.append(f"{title} — {BEST_TITLES[r['best']].lower()}")
            if str(r.get("note") or "").strip():
                notes.append(f"{title}: {str(r['note']).strip()[:200]}")
        words = str(args.get("words") or "").strip()[:2000]
        prompt = interview.summary(self.profile, answers)
        if best:
            prompt += "\nMy AI tools are best at: " + "; ".join(best) + "."
        if notes:
            prompt += "\nNotes on my tools: " + "; ".join(notes)
        if words:
            prompt += f"\nIn my words: {words}"
        if self.mcp_on:
            prompt += "\nMCP servers the orks may use: " + ", ".join(self.mcp_on) + "."
        return self._begin(None, prompt, answers)

    def skip(self, args: dict) -> dict | None:
        """An empty town, the tools found kept on, no Security reviewer."""
        self._live()
        self.warder = False
        return self._begin(None, "")

    def close(self, args: dict) -> None:
        """The town stands: the onboarding leaves the page."""
        if self.raising and self.raising["phase"] in ("done", "failed"):
            self.active = False
            self.host.on_change()

    # -- raising the town --------------------------------------------------------------------------

    def _save_machine(self) -> None:
        town = self.host.town
        m = town.machine
        profile = dict(self.profile)
        profile["kin"] = self.kin
        profile["mcp"] = list(self.mcp_on)
        tools_ = dict(m.tools)
        tools_.update(self.picked)
        town.machine = replace(m, profile=settings.clean_profile(profile), tools=tools_, onboarded=True)
        settings.save(town.machine)

    def _begin(self, it: intents.Intent | None, prompt: str, answers: dict | None = None) -> dict | None:
        town = self.host.town
        self._save_machine()
        title = it.title if it else ("Your town" if prompt else "An empty town")
        self.step = RAISING
        self.raising = {"title": title, "phase": "raising", "steps": [], "buildings": [], "error": ""}
        self._step("The camp's records", lambda: checkpoint.ensure(town.repo_root))
        if self.warder and self.picked.get("claude", settings.ToolChoice()).enabled:
            def guard() -> None:
                from orkcraft.hooks import install as hooks_install
                hooks_install.install_all(town.repo_root, agy=None if town.machine.agy_warder_checked else False)
            self._step("The Security reviewer guards this project", guard)
        if it is not None:
            plan, errors = town_builder.check(it.plan, town.repo_root, town.taken_ids())
            if errors:                                  # the templates are tested; never expected
                self._fail("; ".join(errors[:3]))
            else:
                self._plan(plan)
        elif prompt:
            town_presets.save_order(town.repo_root, prompt, self.profile.get("role", ""), answers or {})
            self.raising["phase"] = "planning"
            self._planner = threading.Thread(target=self._draw, args=(prompt,), daemon=True)
            self._planner.start()
        else:
            self._step("The town stands", lambda: None)
        if self.raising["steps"]:
            self.raising["steps"][0]["state"] = "now"
        self._next_at = 0.0
        self.host.on_change()
        return self.snapshot()

    def _step(self, label: str, act: Callable[[], Any], building: str = "") -> None:
        self._queue.append((label, act, building))
        self.raising["steps"].append({"label": label, "state": "next"})

    def _plan(self, plan: town_builder.TownPlan) -> None:
        town = self.host.town
        for spec in plan.specs:
            self.raising["buildings"].append({"id": spec["id"], "title": spec.get("title", spec["id"]),
                                              "type": spec.get("type", ""), "state": "planned"})
            self._step(f"Raising {spec.get('title', spec['id'])}",
                       lambda spec=spec: buildings.raise_spec(town, spec, None), spec["id"])
        for r in plan.roads:
            self._step(f"A road {r.source} → {r.target}",
                       lambda r=r: roads.lay(town, r.target, r.source, r.subscription, None, quiet=True))
        self._plan_title = plan.title

    def _draw(self, prompt: str) -> None:
        """The Town planner draws the town from the survey, on a thread (a model call)."""
        town = self.host.town
        role = self.profile.get("role", "")
        runner = runners.BUILD_RUNNER or builders.claude_runner
        try:
            result = town_builder.plan(prompt, town.repo_root, town.taken_ids(), runner,
                                       templates=intents.templates_text(role) if role else "")
        except Exception as e:                      # the planner failing leaves the order in the Town Hall
            result = town_builder.TownPlan(error=str(e))
        town.call(self._drawn, result)

    def _drawn(self, result: town_builder.TownPlan) -> None:
        if not result.ok:
            self._fail(f"{result.error or 'no plan'}. The order waits in the Town Hall.")
            return
        self.raising["title"] = result.title or self.raising["title"]
        self.raising["phase"] = "raising"
        self._plan(result)
        if not self._queue:
            self._done()
        elif all(st["state"] != "now" for st in self.raising["steps"]):
            self.raising["steps"][len(self.raising["steps"]) - len(self._queue)]["state"] = "now"
        self.host.on_change()

    def _fail(self, error: str) -> None:
        self.raising["phase"] = "failed"
        self.raising["error"] = error
        self.host.on_change()

    def tick(self, now: float | None = None) -> None:
        """One raising step, at most every `RAISE_STEP_S`: the map changes in front of the person."""
        if not self._queue or self.raising is None or self.raising["phase"] not in ("raising", "planning"):
            return
        now = time.monotonic() if now is None else now
        if now < self._next_at:
            return
        self._next_at = now + RAISE_STEP_S
        i = len(self.raising["steps"]) - len(self._queue)
        label, act, building = self._queue.pop(0)
        step = self.raising["steps"][i]
        try:
            act()
            step["state"] = "done"
        except Exception as e:                     # one building that will not stand never stops the rest
            step["state"] = "failed"
            self.host.town.toast(f"{label}: {e}", title="Setting up the town", severity="warning")
        for b in self.raising["buildings"]:
            if b["id"] == building:
                b["state"] = "standing" if step["state"] == "done" else "failed"
        if self._queue:
            self.raising["steps"][i + 1]["state"] = "now"
            nxt = self._queue[0][2]
            for b in self.raising["buildings"]:
                if b["id"] == nxt:
                    b["state"] = "raising"
        elif self.raising["phase"] == "raising":
            self._done()
        self.host.on_change()

    def _done(self) -> None:
        town = self.host.town
        self.raising["phase"] = "done"
        title = self._plan_title or self.raising["title"]
        town_presets.close_order(town.repo_root, title)
        town.save()
        town.checkpoint("create", "camp", f"onboarding: {title}")
        town.first_run = False
