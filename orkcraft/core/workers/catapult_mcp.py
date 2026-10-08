"""🎯 The Catapult's `mode: mcp` (docs/design/catapult-mcp.md): a shot goes to an MCP server — through
its learned direct path, a local server you allowed, or the AI tool that has the server (the carrier).

The worker's part; the parts without a face are in realm/catapult_mcp/. `McpShots` is mixed into
CatapultWorker (core/workers/catapult.py) and uses its queue, its asking and its `_done`.

    _shoot_mcp(body)    picks the track, asks when it must (confirm, or the first shot of a new track or
                        carrier), fires in a thread
    learning            after a carried shot: its arguments → a template, the template → direct routes
                        (recipes); route.json is committed, the window offers the direct path
    breaks              a refused token holds the queue (the hut burns); a refused call on a direct or
                        local track is carried once and learned again
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from orkcraft.realm import catapult as cp, catapult_mcp as cm, harnesses, mcp
from orkcraft.realm.catapult_mcp import carrier as carry_, local, routes, templates as tp
from orkcraft.realm.jobs import now_iso


FOUND_TTL_S = 10


class McpShots:
    carry_runner = None                # tests put a fake carrier process here: (argv, cwd, env) → CompletedProcess
    smtp = None                        # … a fake SMTP connection: (host, port) → server
    mcp_home: Path | None = None       # … and a home with the AI tools' configs
    learn_runner = None                # … a fake model for mapping argument names
    _found: tuple[float, dict[str, list[str]]] | None = None     # which tools have which server, and when read

    # -- what it is ---------------------------------------------------------------------------------

    @property
    def mcp_mode(self) -> bool:
        return self.config.get("mode") == "mcp"

    @property
    def server(self) -> str:
        return str(self.config.get("to") or "").strip()

    @property
    def route(self) -> dict:
        return cm.load(self.repo_root, self.building_id)

    def mcp_tool(self, route: dict | None = None) -> str:
        """The full MCP tool name: the `tool` setting, else what was learned, else ""."""
        tool = str(self.config.get("tool") or "").strip()
        if tool:
            return tool if tool.startswith("mcp__") else f"mcp__{self.server}__{tool}"
        route = self.route if route is None else route
        return str(route.get("tool") or "") if str(route.get("server") or "").lower() == self.server.lower() else ""

    def mcp_template(self, route: dict | None = None):
        """What a shot sends: the `args` setting, else the learned template, else None (a learning shot)."""
        if self.config.get("args"):
            return tp.from_lines([str(x) for x in self.config.get("args") or []])
        route = self.route if route is None else route
        return route.get("args") if self.mcp_tool(route) and route.get("tool") == self.mcp_tool(route) else None

    def _machine(self):
        from orkcraft.realm import builders
        return builders._machine()

    def _servers(self) -> dict[str, list[str]]:
        """Which tools have which server, read again at most every FOUND_TTL_S (the window asks often)."""
        now = time.monotonic()
        cached = self._found
        if cached is None or now - cached[0] > FOUND_TTL_S:
            cached = (now, {s.id: list(s.tools) for s in mcp.found(self.mcp_home, self.repo_root)})
            self._found = cached
        return cached[1]

    def carrier_choice(self) -> tuple[str, str]:
        machine = self._machine()
        servers = self._servers()
        enabled = {t: c.enabled for t, c in machine.tools.items()}
        billing = {t: c.billing for t, c in machine.tools.items()}
        from orkcraft.realm import builders
        return carry_.choose(self.server, servers, enabled, billing, str(self.config.get("via") or ""),
                             builders.main_tool(machine))

    def launch(self) -> mcp.Launch | None:
        return mcp.launch(self.server, self.mcp_home, self.repo_root) if self.config.get("local") else None

    def track(self, route: dict | None = None) -> str:
        """The track the next shot takes: direct, local or carrier."""
        route = self.route if route is None else route
        d = cm.direct(route)
        if route.get("on") and d and not routes.missing(d):
            return "direct"
        if self.config.get("local") and self.mcp_tool(route) and self.mcp_template(route) is not None and self.launch():
            return "local"
        return "carrier"

    # -- a shot -------------------------------------------------------------------------------------

    def _shoot_mcp(self, body, start: int = 0) -> bool:
        server = self.server
        if not server:
            return self._problem(body, "(no server)", "no MCP server set — `to: slack`")
        route = self.route
        tool, tmpl = self.mcp_tool(route), self.mcp_template(route)
        args = None
        if tmpl is not None:
            try:
                args = tp.render(tmpl, body)
            except tp.Missing as e:
                return self._problem(body, f"{server} · {routes.short_tool(tool)}", str(e))
        if self.simulated:
            return self._dry(body)
        track = self.track(route)
        if track == "direct":
            d = cm.direct(route)
            first = not route.get("proven")
            go = lambda: self._fire_direct(d, body)
            title, text = f"🎯 Send to {routes.title(d)}?", routes.preview(d, body)
        elif track == "local":
            first = not route.get("local_proven")
            go = lambda: self._fire_local(tool, args, body)
            title, text = f"🎯 Send to {server} (local server)?", json.dumps(args, ensure_ascii=False, indent=1)
        else:
            who, why = self.carrier_choice()
            if not who:
                return self._wait_mcp(body, start, why)
            if self.out_of_gold():
                return self._wait_mcp(body, start, "the 🪙 budget is spent — a carried shot waits")
            first = not route or route.get("carrier") != who or tmpl is None
            go = lambda: self._fire_carrier(who, tool, args, body)
            h = harnesses.need(who)
            what = routes.short_tool(tool) if tool else "a tool it picks"
            title = f"🎯 Send to {server} ({what}) via {h.title}?"
            text = json.dumps(args if args is not None else body, ensure_ascii=False, indent=1)
        if first and not self.config.get("confirm"):
            text = "The first shot through this path asks.\n\n" + text
        if self.must_confirm() or first:
            self._ask(title, text[:900], go, body, start)
            return True
        go()
        return True

    def _wait_mcp(self, body, start: int, why: str) -> bool:
        """The shot cannot go now (no carrier, no budget): it waits at the front of the queue."""
        self.firing = False
        self.queue.push(body, start, front=True)
        first = not self.waiting
        self.waiting = why
        if first:
            self.emit("catapult.failed", f"{self.server}: {why}", "waits")
        self.changed()
        return False

    def _thread(self, name: str, work) -> None:
        self.firing = True
        self.changed()
        threading.Thread(target=work, daemon=True, name=f"catapult-{name}-{self.building_id}").start()

    def _fire_direct(self, d: dict, body) -> None:
        opener = type(self).opener
        smtp = type(self).smtp

        def work() -> None:
            kw = {"opener": opener} if opener else {}
            shot, kind = routes.send(d, body, smtp=smtp, **kw)
            shot.track = "direct"
            self._later(self._mcp_done, shot, kind, body, "direct")

        self._thread("direct", work)

    def _fire_local(self, tool: str, args, body) -> None:
        launch = self.launch()
        server = self.server

        def work() -> None:
            c = local.call(launch, routes.short_tool(tool), args, cwd=self.repo_root) if launch else \
                local.Called(False, error=f"{server} is not a local server any more", kind="other")
            shot = cp.Shot(now_iso(), c.ok, 0, f"{server} · {routes.short_tool(tool)} (local)",
                           json.dumps(args, ensure_ascii=False)[:cp.ANSWER_KEEP], c.answer[:cp.ANSWER_KEEP], c.error,
                           track="local")
            self._later(self._mcp_done, shot, c.kind, body, "local")

        self._thread("local", work)

    def _fire_carrier(self, who: str, tool: str, args, body, relearn: bool = False) -> None:
        server, goal, root = self.server, str(self.config.get("goal") or ""), self.repo_root
        runner = type(self).carry_runner
        learner = type(self).learn_runner
        if learner is None and self.town.budget_ok():
            from orkcraft.realm import builders
            learner = builders.main_runner

        def work() -> None:
            started = time.time()
            c = carry_.carry(who, server, tool, args, goal, body, root, run=runner)
            tmpl, options, cost = None, [], 0.0
            if c.ok:
                tmpl = tp.learn(c.args, body) if args is None else self.mcp_template()
                try:
                    options, cost = routes.derive(server, c.tool, tmpl, runner=learner)
                except Exception:
                    options = []
            self._later(self._carried, c, body, who, tmpl, options, cost, started, relearn)

        self._thread("carry", work)

    # -- after a shot ---------------------------------------------------------------------------------

    def _carried(self, c: carry_.Carried, body, who: str, tmpl, options: list, cost: float, started: float,
                 relearn: bool) -> None:
        h = harnesses.get(who)
        tool = c.tool or self.mcp_tool()
        shot = cp.Shot(now_iso(), c.ok, 0, f"{self.server} · {routes.short_tool(tool) or '?'} via {h.title if h else who}",
                       json.dumps(c.args if c.args is not None else body, ensure_ascii=False)[:cp.ANSWER_KEEP],
                       c.answer[:cp.ANSWER_KEEP], c.error, track="carrier")
        self._record("carry", started, c.ok, (c.cost or 0.0) + cost, c.error)
        if not c.ok and c.kind == "auth" and not c.tool:
            self.firing = False
            cp.log(self.state_dir, shot)
            self.shots = cp.shots(self.state_dir)
            self._wait_mcp(body, 0, c.error)
            return
        if c.ok:
            self._learn(c, body, who, tmpl, options, relearn)
        self._done(shot, body)

    def _learn(self, c: carry_.Carried, body, who: str, tmpl, options: list, relearn: bool) -> None:
        old = self.route
        route = {"server": self.server, "tool": c.tool, "args": tmpl, "carrier": who, "learned": now_iso(),
                 "options": options, "pick": 0, "on": False, "proven": False, "kept": bool(old.get("kept")),
                 "local_proven": bool(old.get("local_proven")) and old.get("tool") == c.tool}
        before = cm.direct(old)
        if before and old.get("on"):                       # a path in use stays in use, proven again
            same = [i for i, o in enumerate(options) if routes.title(o) == routes.title(before)]
            route.update(pick=same[0] if same else 0, on=bool(same))
        cm.save(self.repo_root, self.building_id, route)
        try:
            (self.state_dir / "sample.json").parent.mkdir(parents=True, exist_ok=True)
            (self.state_dir / "sample.json").write_text(json.dumps({"args": c.args, "cart": body}, ensure_ascii=False),
                                                        encoding="utf-8")
        except OSError:
            pass
        changed = old.get("tool") != c.tool or old.get("args") != tmpl or [routes.title(o) for o in old.get("options") or []] \
            != [routes.title(o) for o in options]
        if not changed and not relearn:
            return
        what = f"{self.overseer} learned {routes.short_tool(c.tool)}: " + tp.describe(tmpl).replace("\n", "; ")
        self._commit(what[:200])
        if relearn:
            self.emit("catapult.repaired", f"{self.overseer}: learned {self.server} again — {tp.describe(tmpl)}", "learned again")
        d = cm.direct(route)
        if d and not route["on"] and not route["kept"]:
            need = routes.missing(d)
            self.toast(f"A direct path: {routes.title(d)}" + (f" — set {', '.join(need)}" if need else "")
                       + ". Use it in the window.", title=f"🎯 {self.overseer} learned a path")

    def _mcp_done(self, shot: cp.Shot, kind: str, body, track: str) -> None:
        route = self.route
        if shot.ok:
            key = "proven" if track == "direct" else "local_proven"
            if not route.get(key):
                route[key] = True
                cm.save(self.repo_root, self.building_id, route)
                self._commit(f"the {track} path to {self.server} proved itself")
            self._done(shot, body)
            return
        if kind == "auth":
            self.firing = False
            cp.log(self.state_dir, shot)
            self.queue.push(body, 0, front=True)
            first = not self.login_needed
            self.login_needed = f"{shot.url}: {shot.error or 'the token is refused'} — fix it, then Resume"
            if first:
                self.emit("catapult.failed", f"{self.server}: {shot.error or 'the token is refused'}", "token refused")
            self.refresh()
            return
        if kind == "path" and self.config.get("repair", True):
            who, _ = self.carrier_choice()
            if who and self.town.budget_ok():
                self.firing = False
                cp.log(self.state_dir, shot)
                self.toast(f"{shot.error or 'refused'} — {self.overseer} carries it once and learns the path again",
                           title=f"🎯 {self.server}")
                self._fire_carrier(who, self.mcp_tool(), None, body, relearn=True)
                return
        self._done(shot, body)

    # -- the person's choices -----------------------------------------------------------------------

    def use_direct(self, pick: int = 0) -> bool:
        route = self.route
        if not 0 <= pick < len(route.get("options") or []):
            return False
        route.update(pick=pick, on=True, proven=False, kept=False)
        cm.save(self.repo_root, self.building_id, route)
        self._commit(f"use {routes.title(cm.direct(route))} for {self.server}")
        self.changed()
        return True

    def keep_carrier(self) -> bool:
        route = self.route
        if not route:
            return False
        route.update(on=False, kept=True)
        cm.save(self.repo_root, self.building_id, route)
        self._commit(f"keep carrying {self.server}")
        self.changed()
        return True

    def allow_local(self, on: bool) -> bool:
        if not self.save_config({"local": bool(on) or None}):
            return False
        self.changed()
        return True

    # -- the hut burns: a refused token or a shot that waits asks in Answers ----------------------------

    def orders_alert(self):
        if not self.mcp_mode or not (self.login_needed or self.waiting):
            return super().orders_alert()
        queued = len(self.queue)
        why = self.login_needed or self.waiting
        title = f"🎯 {self.overseer}: " + ("the token is refused" if self.login_needed else f"{self.server} waits")
        return ("mcp", title, [why, f"{queued} shot{'s' if queued != 1 else ''} wait in the queue"],
                [("1", "Resume — it is fixed"), ("2", "Later")])

    def answer_alert(self, key: str) -> str | None:
        if self.mcp_mode and key == "1":
            self.resume()
            return None
        return super().answer_alert(key)

    # -- the dry run and the window -----------------------------------------------------------------

    def dry_text(self, body) -> tuple[str, str]:
        """(where, what): the dry run of a shot in mode mcp, nothing sent."""
        route, server = self.route, self.server
        tool, tmpl = self.mcp_tool(route), self.mcp_template(route)
        track = self.track(route)
        parts = []
        if tmpl is None:
            who, why = self.carrier_choice()
            parts.append(f"carrier: {harnesses.need(who).title if who else why}\n"
                         f"a first shot: the carrier picks {'the call to ' + tool if tool else 'a tool of ' + server}, "
                         "the Loader learns from it")
            return f"{server} (learning)", "\n\n".join(parts)
        try:
            args = tp.render(tmpl, body)
        except tp.Missing as e:
            return server, f"✗ {e}"
        parts.append(f"{routes.short_tool(tool)}\n" + json.dumps(args, ensure_ascii=False, indent=1))
        d = cm.direct(route)
        if track == "direct" or d:
            parts.append(("direct path (in use)" if track == "direct" else "direct path (learned, not in use)")
                         + f": {routes.title(d)}\n" + routes.preview(d, body))
            need = routes.missing(d)
            if need:
                parts.append("not set: " + ", ".join(need))
            sample = self.sample()
            if sample:
                parts.append("the proof — the carried shot sent:\n" + json.dumps(sample.get("args"), ensure_ascii=False, indent=1)
                             + "\n\nthe direct path, for that cart:\n" + routes.preview(d, sample.get("cart")))
        if track == "carrier":
            who, why = self.carrier_choice()
            parts.insert(0, f"carrier: {harnesses.need(who).title + ' — a model call' if who else why}")
        else:
            parts.insert(0, f"{track}: no model")
        return f"{server} · {routes.short_tool(tool)}", "\n\n".join(parts)

    def sample(self) -> dict:
        try:
            data = json.loads((self.state_dir / "sample.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def mcp_state(self) -> dict:
        """What the window shows of mode mcp."""
        route = self.route
        tool = self.mcp_tool(route)
        track = self.track(route)
        who, why = self.carrier_choice() if track == "carrier" else ("", "")
        d = cm.direct(route)
        launch = mcp.launch(self.server, self.mcp_home, self.repo_root)
        return {
            "server": self.server, "tool": routes.short_tool(tool), "track": track,
            "carrier": harnesses.need(who).title if who else "", "no_carrier": why,
            "args": tp.describe(self.mcp_template(route)) if self.mcp_template(route) is not None else "",
            "learned": str(route.get("learned") or ""),
            "options": [{"title": routes.title(o), "needs": routes.needs(o), "missing": routes.missing(o),
                         "note": str(o.get("note") or "")} for o in route.get("options") or []],
            "pick": int(route.get("pick") or 0), "on": bool(route.get("on")), "proven": bool(route.get("proven")),
            "kept": bool(route.get("kept")), "direct": routes.title(d) if d else "",
            "local": bool(self.config.get("local")),
            "launch": {"command": launch.command.split("/")[-1], "where": launch.where} if launch else None,
            "waiting": self.waiting,
        }
