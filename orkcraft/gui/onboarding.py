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

from orkcraft import schedule, settings, tools
from orkcraft.core import buildings, roads, runners
from orkcraft.env import getenv
from orkcraft.realm import (biomes, builders, checkpoint, harnesses, intents, interview, mcp, tool_errors, town_builder,
                           town_presets)

TOOLS, WHO, MCP, TOWN, SURVEY, RAISING = "tools", "who", "mcp", "town", "survey", "raising"
WARDED = harnesses.ids()    # the tools the Security reviewer's hooks guard (hooks/install.py): every one
GRID = (4, 3)               # where the planned buildings stand: four across, as js/town.js lays out a hut without a spot
ROW = 0.25                  # a row's step down the town: the quiet huts stand folded, so three rows keep to its top
OPEN = frozenset({"fields", "loot", "watchtower", "pit"})   # stand open: the person works in them every day
RAISE_STEP_S = 0.8          # between two raising steps: slow enough to see each building go up
ISSUES = "https://github.com/Orkcraft/orkcraft/issues/new"
KIN_WORDS = {"orc": "orks", "lich": "undead", "elf": "elves", "gnome": "gnomes", "goblin": "goblins",
             "knight": "knights", "skeleton": "skeletons"}     # "Two kinds of gnomes" on step 2
USES_MAX = 6                # the chips "The planner will use" starts with: the MCP servers on, then the class's usual
USES_MCP = 4                # …of which MCP servers at most, so the class's usual always shows too



def _open_in_lake(town, building_id: str, event: str) -> None:
    """What a planned building sends as `event` opens in the town's Lake window (a plan's road "to": "lake")."""
    b = town.scroll.building(building_id)
    if b is not None and event not in (b.open_in_lake or ()):
        b.open_in_lake = [*(b.open_in_lake or ()), event]

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
        self.again = False              # opened from the map's menu on a town that stands: no town step
        self.step = TOOLS
        machine = host.town.machine
        self.profile = dict(machine.profile)
        # The landing page named a class with two roles (`--role gnome`): step 2 shows only its two cards.
        kin = str(self.profile.get("kin") or "")
        self.only_kin = kin if not machine.onboarded and sum(r.mascot == kin for r in intents.ROLES) > 1 else ""
        if self.only_kin:
            self.profile.pop("role", None)
        self.kin = intents.role(self.profile["role"]).mascot if self.profile.get("role") else self.only_kin
        self.role_given = bool(self.profile.get("role"))         # the landing page's role (settings.preset_role)
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
        self._find = servers or (lambda: mcp.found(repo=host.town.repo_root))
        self._detectors = (detect or (lambda: tools.detect()), detect_others or (lambda: tools.detect_others()))
        if self.active:
            self._look()

    def _look(self) -> None:
        """The MCP servers at once (files only), the AI tools on a thread (`--version` runs for each)."""
        self.servers = self._find()
        known = set(self.profile.get("mcp") or []) if self.again else None
        self.mcp_on = [s.id for s in self.servers if known is None or s.id in known]
        self.statuses = None
        self._finder = threading.Thread(target=self._detect, args=self._detectors, daemon=True)
        self._finder.start()

    def start(self, args: dict) -> dict | None:
        """The map's menu → Set up again: your AI tools, who you are and the MCP servers once more, on a town
        that stands (never a town step). Saved when the last step is answered."""
        if self.active:
            return self.snapshot()
        machine = self.host.town.machine
        self.active, self.again, self.step = True, True, TOOLS
        self.profile = dict(machine.profile)
        self.only_kin, self.role_given = "", False
        self.kin = intents.role(self.profile["role"]).mascot if self.profile.get("role") else ""
        self.raising = None
        self._look()
        self.host.on_change()
        return self.snapshot()

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
        kept = self.host.town.machine.tools if self.again else {}    # set up again: what was chosen stays
        self.picked = {st.id: kept.get(st.id) or settings.ToolChoice(enabled=st.found and st.tool.available,
                                                                      billing=st.billing)
                       for st in found}
        self.host.on_change()

    def steps(self) -> list[str]:
        """The steps of this run, from what is known so far."""
        out = [TOOLS]
        if not self.role_given:
            out.append(WHO)
        if self.servers:
            out.append(MCP)
        if not self.again:
            out.append(TOWN)
        return out

    def _classes(self) -> list[dict]:
        """Every role as a class card with its own mascot (mascots/<role>-1.png), on its kin's biome; only the
        landing page's kin when it named one."""
        return [{"id": r.id, "nick": r.nick, "title": r.title, "kin": r.mascot, "sprite": r.id,
                 "biome": biomes.HOMES.get(r.mascot, "dirt")}
                for r in intents.ROLES if not self.only_kin or r.mascot == self.only_kin]

    def _tools_rows(self) -> list[dict]:
        rows = []
        for st in self.statuses or []:
            if not st.found:
                continue
            choice = self.picked.get(st.id, settings.ToolChoice())
            h = harnesses.get(st.id)
            rows.append({"id": st.id, "title": st.tool.title, "mark": h.mark if h else "", "version": st.version,
                         "logged_in": st.logged_in, "login": st.tool.login, "enabled": choice.enabled, "billing": choice.billing})
        return rows

    def _not_run_on(self) -> dict:
        """The tools the orks don't run on here: `missing` (not found), `others` (found, but no harness) and `cli`
        (an app here whose CLI the orks run on is not: Cursor's editor without cursor-agent). A tool found
        is never named again below the table."""
        statuses = self.statuses or []
        found = {st.id for st in statuses if st.found}
        others = [o for o in self.others if o.id not in found]
        cli = {o.id: h for o in others if (h := harnesses.get(o.id))}
        return {"missing": [st.tool.title for st in statuses if not st.found and st.id not in cli],
                "others": [{"id": o.id, "title": o.title} for o in others if o.id not in cli],
                "cli": [{"id": o.id, "title": o.title, "bin": cli[o.id].bin} for o in others if o.id in cli]}

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
                "rhythm": intents.RHYTHMS.get(it.rhythm, ""),
                "summary": plan.get("summary", ""),
                "buildings": [{"key": b["key"], "type": b["type"], "title": b["title"], "why": b.get("why", ""),
                               # what an agent uses shows on the building that runs agents or sends things out
                               "badges": glyphs[:3] if b["type"] in ("barracks", "catapult") else []}
                              for b in plan.get("buildings", [])],
                "roads": [{"from": r["from"], "to": r["to"], "why": r.get("why", "")}
                          for r in plan.get("roads", [])]})
        return out

    def _uses(self) -> list[dict]:
        """What the planner will use, prefilled: the MCP servers on, then where this class's work usually comes
        from and goes to; a source an MCP server already names is left out, and so is a second Slack."""
        role = intents.role(self.profile.get("role") or "")
        on = [x for x in self.servers if x.id in self.mcp_on][:USES_MCP]
        out = [{"id": f"mcp:{x.id}", "title": x.title, "mcp": True} for x in on]
        seen = {x.title.lower() for x in on}
        titles = {"src": {c.id: c.title for c in interview.SOURCES}, "out": {c.id: c.title for c in interview.OUTPUTS}}
        for kind, ids in (("src", role.sources), ("out", role.outputs)):
            for cid in ids:
                title = titles[kind].get(cid, "")
                low = title.lower()
                if not title or low in seen or any(m in low for m in seen):
                    continue
                seen.add(low)
                out.append({"id": f"{kind}:{cid}", "title": title, "mcp": False})
        return out[:USES_MAX]

    def _survey(self) -> dict:
        return {"starters": list(interview.STARTERS.get(self.profile.get("role") or "", ())), "uses": self._uses()}

    def snapshot(self) -> dict[str, Any] | None:
        if not self.active:
            return None
        steps = self.steps()
        machine = self.host.town.machine
        return {
            "step": self.step, "steps": steps,
            "n": steps.index(self.step) if self.step in steps else len(steps) - 1,
            "tools": {"ready": self.statuses is not None, "rows": self._tools_rows(), **self._not_run_on(),
                      "warder": self.warder, "warder_agy": self._warder_agy()},
            "classes": self._classes(), "only_kin": self.only_kin,
            "kin_word": KIN_WORDS.get(self.only_kin, self.only_kin),
            "kin": self.kin, "role": self.profile.get("role", ""),
            "nick": intents.nick(self.profile["role"]) if self.profile.get("role") else "",
            "biome": biomes.home_of(self.profile),
            "mcp": {"servers": [s.to_dict() for s in self.servers], "on": list(self.mcp_on)},
            "towns": self._towns(), "survey": self._survey() if self.step == SURVEY else None,
            "planner": self._planner_runner() is not None,
            "tool_titles": {t.id: t.title for t in tools.TOOLS},
            "again": self.again, "quiet": bool(machine.quiet),
            "raising": self.raising,
        }

    # -- the page's commands -----------------------------------------------------------------------

    def commands(self) -> dict[str, Callable[[dict], Any]]:
        return {"onboarding.tools": self.set_tools, "onboarding.request": self.request,
                "onboarding.role": self.set_role, "onboarding.mcp": self.set_mcp,
                "onboarding.town": self.set_town, "onboarding.survey": self.set_survey,
                "onboarding.back": self.back, "onboarding.skip": self.skip, "onboarding.close": self.close,
                "onboarding.start": self.start, "onboarding.cancel": self.cancel, "onboarding.quiet": self.set_quiet}

    def _warder_agy(self) -> str:
        """What the guard step says about agy when agy is chosen: unguarded until its hook was checked live."""
        if "agy" not in self._enabled():
            return ""
        from orkcraft.hooks import install as hooks_install
        return hooks_install.agy_warder_line(self.host.town.machine.agy_warder_checked, self.statuses)

    def _enabled(self) -> list[str]:
        machine = self.host.town.machine
        return [t for t, c in {**machine.tools, **self.picked}.items() if c.enabled]

    def _planner_runner(self):
        """What draws a town from the person's words: the tests' runner, else the main tool (builders.planner_runner:
        the chosen main tool if it is on, else the first on); None when no tool is on."""
        if runners.BUILD_RUNNER is not None:
            return runners.BUILD_RUNNER
        return builders.planner_runner(self._enabled(), self.host.town.machine.main_tool)

    def cancel(self, args: dict) -> None:
        """Set up again, left without saving (a first run has no way out but Skip)."""
        if self.again:
            self.active = self.again = False
            self.host.on_change()

    def set_quiet(self, args: dict) -> dict | None:
        """The Autonomy card's quiet hours: 23:00–08:00 on, or off (the hours themselves: Settings)."""
        m = self.host.town.machine
        m.quiet = (m.quiet or schedule.DEFAULT_QUIET) if args.get("on") else None
        settings.save(m)
        self.host.on_change()
        return self.snapshot()

    def _live(self) -> None:
        if not self.active or self.step == RAISING:
            raise OnboardingError("The onboarding is not open")

    def _go(self, after: str) -> dict | None:
        steps = self.steps()
        i = steps.index(after) if after in steps else -1
        if i + 1 >= len(steps) and self.again:           # set up again: the last step answered, nothing to raise
            self._save_machine()
            self.active = self.again = False
            self.host.town.toast("Your AI tools, your class and the MCP servers are saved", title="Set up again")
            self.host.on_change()
            return None
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
                raise OnboardingError("No AI tool that can plan a town is on")
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
        """What the town should do in the person's words, and the prefilled list of what the planner will use
        less what they left out (`keep`), plus what they added (`extra`). It becomes the Town planner's order;
        the town is drawn from it, then raised."""
        self._live()
        words = str(args.get("words") or "").strip()[:2000]
        if not words:
            raise OnboardingError("Say in a sentence or two what the town should do")
        keep = {str(x) for x in args.get("keep") or [] if isinstance(x, str)}
        shown = [u["id"] for u in self._uses()]
        answers: dict[str, Any] = {}
        for kind, qid in (("src", "sources"), ("out", "outputs")):
            ids = [u.split(":", 1)[1] for u in shown if u in keep and u.startswith(kind + ":")]
            if ids:
                answers[qid] = ids
        self.mcp_on = [m for m in self.mcp_on if f"mcp:{m}" in keep or f"mcp:{m}" not in shown]   # left out: off
        extra = [str(x).strip()[:80] for x in args.get("extra") or [] if isinstance(x, str) and str(x).strip()][:10]
        prompt = interview.summary(self.profile, answers)
        if extra:
            prompt += "\nAlso: " + "; ".join(extra) + "."
        if self.mcp_on:
            prompt += "\nMCP servers the orks may use: " + ", ".join(self.mcp_on) + "."
        prompt += f"\nIn my words: {words}"
        return self._begin(None, prompt, answers)

    def skip(self, args: dict) -> dict | None:
        """An empty town, the tools found kept on, no Security reviewer (set up again: leave, nothing saved)."""
        if self.again:
            return self.cancel(args)
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
        self._home()
        if self.warder and any(t in WARDED for t in self._enabled()):
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

    def _home(self) -> None:
        """The first town stands on its class's ground at once (realm/biomes.py), not at the next growth tick."""
        scroll = self.host.town.scroll
        space = next((o for o in scroll.orkspaces if o.id == scroll.active_orkspace_id), None)
        if space is not None:
            space.biome = biomes.home_of(self.profile)
            scroll.meta[biomes.SETTLED] = 1

    def _step(self, label: str, act: Callable[[], Any], building: str = "") -> None:
        self._queue.append((label, act, building))
        self.raising["steps"].append({"label": label, "state": "next"})

    def _plan(self, plan: town_builder.TownPlan) -> None:
        town = self.host.town
        cols, rows = GRID
        for i, spec in enumerate(plan.specs):
            # Each building's spot is known before it stands, so the map draws it there as a plan first.
            hut = [round((i % cols) / (cols - 1), 3), round(min(i // cols, rows - 1) * ROW, 3)]
            self.raising["buildings"].append({"id": spec["id"], "title": spec.get("title", spec["id"]),
                                              "type": spec.get("type", ""), "state": "planned", "hut": hut})
            fold = spec.get("type") not in OPEN
            self._step(f"Raising {spec.get('title', spec['id'])}",
                       lambda spec=spec, hut=hut, fold=fold: buildings.raise_spec(town, spec, hut, folded=fold), spec["id"])
        for r in plan.roads:
            self._step(f"A road {r.source} → {r.target}",
                       lambda r=r: roads.lay(town, r.target, r.source, r.subscription, None, quiet=True,
                                                 returns=r.returns))
        for bid, event in plan.opens:
            self._step(f"{bid} opens in Lake", lambda bid=bid, event=event: _open_in_lake(town, bid, event))
        self._plan_title = plan.title

    def _draw(self, prompt: str) -> None:
        """The Town planner draws the town from the survey, on a thread (a model call)."""
        town = self.host.town
        role = self.profile.get("role", "")
        runner = self._planner_runner() or builders.main_runner_of(self.host.town.machine)
        tool_errors.taken()                         # this thread's AI tool failures from here on
        try:
            result = town_builder.plan(prompt, town.repo_root, town.taken_ids(), runner,
                                       templates=intents.templates_text(role) if role else "")
        except Exception as e:                      # the planner failing leaves the order in the Town Hall
            result = town_builder.TownPlan(error=str(e))
        town.call(self._drawn, result)
        if not result.ok and (failed := tool_errors.taken()) is not None:   # Switch, Retry, Details (gui/failures.py)
            town.call(self.host.failures.report, failed, "Drawing your town", lambda: self._redraw(prompt))

    def _redraw(self, prompt: str) -> None:
        """Retry: the Town planner draws again, on the main tool as it is now."""
        if self.raising is None or self.raising["phase"] != "failed":
            return
        self.raising.update(phase="planning", error="")
        self._planner = threading.Thread(target=self._draw, args=(prompt,), daemon=True)
        self._planner.start()
        self.host.on_change()

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
