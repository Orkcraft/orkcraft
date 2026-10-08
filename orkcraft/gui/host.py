"""The GUI's side of the town: it owns the `Town`, keeps its clocks and answers the page's commands.

The TUI's app does this for Textual (its timers, its `_wire_bus`); the host does it for the page,
with no toolkit at all. Everything here runs on one thread, the server's event loop: the town's
`call` hops back to it from a worker's thread, so services never race the page.

    host = Host(repo_root)
    host.on_change = lambda: ...       # the town changed: send a fresh snapshot
    host.on_toast = lambda data: ...   # a toast to show
    host.tick()                        # once a second: the roster, the roads, the treasury
    host.command("hut.move", {"id": "lake", "x": 0.4, "y": 0.2})
    host.on_detail = lambda building_id: ...   # an open building's own state changed
    host.detail("lake")                # what its window draws (gui/views/)
    host.command("act", {"id": "lake", "act": "edit"})
"""
from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Any, Callable

from orkcraft.core import bus
from orkcraft.core import runners, usage, wakes
from orkcraft.core.night import Night
from orkcraft.core.roster import Muster
from orkcraft.core.sessions import Sessions
from orkcraft.core.town import Town
from orkcraft.core.treasury import Treasury
from orkcraft.design import ui
from orkcraft.gui import accounts, builder, console, failures, growth, mobile, nightly, onboarding, state, town_settings, updates, views, you
from orkcraft.gui.views import lake as lake_view
from orkcraft import schedule
from orkcraft.realm import biomes, catalog, elders, fastpath, halt, modes
from orkcraft.sources import sessions as past

TELEMETRY_REFRESH_S = 5.0       # as the TUI (tui/base.py)
CART_TRAVEL_ENV = "ORKCRAFT_CART_TRAVEL_S"   # seconds a cart takes along a plain road (default 0: at once)


class CommandError(Exception):
    """A command the page sent that the host refuses; its text is shown to the person."""


class Host:
    def __init__(self, repo_root: Path | None = None, auto_commit: bool | None = None,
                 layout_file: Path | None = None, demo: bool = False) -> None:
        self.town = Town(repo_root, auto_commit, layout_file, demo=demo)
        self.treasury = Treasury(self.town)
        self.muster = Muster(self.town)
        self.sessions = Sessions(self.town)
        self.night = Night(self.town)               # quiet hours: the Elders' advice on the orks' questions
        self.night.restore()
        self.nightly = nightly.Nightly(self)       # …the retros and the orks' own changes (gui/nightly.py)
        self.town.budget_ok = lambda: not self.town.demo and not self.treasury.exhausted()
        # How long a cart is on a plain road before it arrives: 0 (at once) unless asked, e.g. to film a flow
        # slowly enough that a person sees each cart on its road before its building acts (tools/landing_flow.py).
        try:
            self.town.cart_travel_s = max(0.0, min(float(os.environ.get(CART_TRAVEL_ENV) or 0), 30.0))
        except ValueError:
            self.town.cart_travel_s = 0.0
        self.on_change: Callable[[], None] = lambda: None
        self.on_toast: Callable[[dict], None] = lambda data: None
        self.on_detail: Callable[[str], None] = lambda building_id: None
        self._telemetry_at = 0.0
        self._wakes_at = -wakes.WAKE_CHECK_S       # when the script-first buildings were last looked at (core/wakes.py)
        wakes.start(self.town)
        self._refreshed: dict[str, float] = {}     # building id → when its worker last looked again
        self._attached: dict[str, Any] = {}        # building id → the worker its view's `attach` was given
        self.raised_for: dict[tuple[str, str], str] = {}   # (type, request) → the building raised for it (gui/builder.py)
        self.town.bus.subscribe(bus.ANY, self._event)
        self.commands: dict[str, Callable[[dict], Any]] = {
            "orkspace.select": self._select_orkspace,
            "orkspace.new": self._new_orkspace,
            "hut.move": self._move_hut,
            "building.open": self._open_building,
            "halt": self._halt,
            "act": self._act,
            "sessions.new": lambda a: self._session_call(self.sessions.new, self._word(a, "harness")),
            "sessions.resume": lambda a: self._session_call(self.sessions.resume, self._word(a, "key")),
            "sessions.deploy": self._deploy,
            "sessions.past": self._past,
            "term.input": self._input,
            "term.resize": lambda a: self.sessions.resize(self._word(a, "key"), int(a.get("cols") or 0),
                                                          int(a.get("rows") or 0)),
            "term.interrupt": lambda a: self.sessions.interrupt(self._word(a, "key")),
            "term.stop": lambda a: self.sessions.stop(self._word(a, "key")),
            "term.forget": lambda a: self.sessions.forget(self._word(a, "key")),
            "orders.answer": self._answer,
            "orders.follow": self._follow,
            "town.catalog": lambda a: builder.catalog_types(),
            "town.build": lambda a: self._building(builder.build, a),
            "town.demolish": lambda a: self._building(builder.demolish, a),
            "roads.choices": lambda a: self._building(builder.road_choices, a),
            "roads.lay": lambda a: self._building(builder.lay_road, a),
            "roads.remove": lambda a: self._building(builder.remove_road, a),
        }
        self.failures = failures.Failures(self)    # an AI tool that failed: Switch, Retry, Details (gui/failures.py)
        self.commands.update(self.failures.commands())
        # The console of a selected building or ork (gui/console.py): Info, the garrison, the jobs.
        self.console = console.Console(self)
        self.commands.update(self.console.commands())
        self.commands.update(town_settings.commands(self))   # the HUD's menu: autonomy and its waits
        self.commands.update(accounts.commands(self))        # Settings → Accounts: a Google sign-in (gui/accounts.py)
        self.commands.update(mobile.commands(self))   # what a phone reads (gui/mobile.py, docs/design/mobile.md)
        self.growth = growth.Growth(self)           # levels, deeds, the mascot; the War Map's lands (gui/growth.py)
        self.commands.update(self.growth.commands())
        self.you = you.You(self)                    # the portrait's menu: the look, Do not disturb (gui/you.py)
        self.commands.update(self.you.commands())
        # Anonymous usage stats, only when the operator said yes (core/usage.py, docs/usage-stats.md)
        self.usage = usage.Usage(self.town.machine, face="gui", demo=demo)
        self._opened()
        self.updates = updates.Updates(self)        # what is out, installed with a click (gui/updates.py)
        self.commands.update(self.updates.commands())
        self.onboarding = onboarding.Onboarding(self)   # a project with no town yet opens on it (gui/onboarding.py)
        self.commands.update(self.onboarding.commands())
        lake_view.attach(self.town)                # Lake is the town's window: old Lake buildings leave the map
        for bs in self.town.scroll.buildings:      # a building with a worker works from the start
            if not bs.demolished:
                self._attach(bs.id, self.town.worker(bs.id))
        if demo:                                   # the sandbox's orks have screens (and questions) of their own
            from orkcraft.demo import live
            live.open_all(self.sessions, self.town.repo_root)

    # -- what the page sees --------------------------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        snap = state.snapshot(self.town, self.muster, self.treasury, self.limits(), live=self.sessions,
                              night=self.night)
        snap["jobs"] = self.console.public_jobs()       # the console's model calls (gui/console.py)
        snap["lake"] = lake_view.summary(self.town.lake)   # the Lake window's tabs (gui/views/lake.py)
        snap["growth"] = self.growth.snapshot()            # the news and the operator's mascot (gui/growth.py)
        snap["portrait"] = self.you.snapshot()             # the look, Do not disturb, what gathered (gui/you.py)
        snap["usage_ask"] = self.usage.should_ask()        # the one question about usage stats (js/settings.js)
        snap["update"] = self.updates.snapshot()           # a newer Orkcraft, if one is out (js/update.js)
        snap["onboarding"] = self.onboarding.snapshot()    # the first run's steps and the town going up (js/onboarding.js)
        return snap

    def limits(self) -> list:
        """The last quota reads the Town Hall made (its worker reads them again every 10 min), for the
        HUD's quota as the TUI's `_limits`; [] until it has read them."""
        hall = self.town.workers.get("town_hall")
        return list(getattr(hall, "limits", None) or [])

    def _event(self, event: bus.Event) -> None:
        if event.topic == bus.TOAST:
            data = {k: event.data.get(k) for k in ("message", "title", "severity", "timeout")}
            data["message_plain"] = modes.plain(str(data["message"] or ""))
            data["title_plain"] = modes.plain(str(data["title"] or ""))
            if not self.you.hold_toast(data):          # Do not disturb: only an error shows
                self.on_toast(data)
            return
        if event.topic == bus.TOOL_ERROR:              # an AI tool failed: its toast says what to do
            self.failures.show(event.data)
            return
        if event.topic == bus.ORDER:                   # the Warchief gave a specialist work: the console runs it
            self._order(event.data)
        if event.topic == bus.ROADS:                   # the roads changed: the scroll keeps them
            self.town.save()
        if event.topic in (bus.HALL, bus.ROADS):      # a rating, a change of the orks, a road: growth looks again
            self.growth.soon()
        if event.topic in (bus.WORKER, bus.SPEC, bus.UI) and event.data.get("building"):
            self.on_detail(str(event.data["building"]))
            if event.topic == bus.WORKER and self._alert_changed(str(event.data["building"])):
                self.refresh_roster()                  # it began or stopped asking: its hut burns, or not
                return
        self.on_change()

    def _order(self, data: dict) -> None:
        """An order of the Warchief's (core/warchief.py) as the console's job: the road planner, the
        Recruiter, a keeper. Its offer opens on the page when ready; a refusal goes back on his card."""
        kind, bid, words = data.get("kind"), str(data.get("building") or ""), str(data.get("order") or "")
        try:
            if kind == "road":
                self.console.road_plan({"to": bid, "from": data.get("source") or "", "prompt": words})
            elif kind == "recruit":
                self.console.recruit_ask({"id": bid, "prompt": words})
            elif kind == "keeper":
                self.console.keeper_ask({"id": bid, "request": words})
        except Exception as e:                     # ConsoleError, CommandError: said on the card
            hall = self.town.worker("town_hall")
            if hall is not None:
                hall.card_failed(str(data.get("card") or ""), str(e))

    def type_of(self, building_id: str) -> str:
        spec = self.town.spec_of(building_id)
        return catalog.type_of(spec).id if spec else building_id

    def detail(self, building_id: str) -> dict[str, Any] | None:
        """What a building's window draws: its UI document and, for a type the GUI draws, its worker's
        state (gui/views/). None for a building that is gone."""
        bs = self.town.scroll.building(building_id)
        if bs is None or bs.demolished:
            return None
        type_id = self.type_of(building_id)
        view, worker = views.of(type_id), self.town.worker(building_id)
        self._attach(building_id, worker)
        data = view.detail(worker) if view is not None and worker is not None else None
        return {"id": building_id, "type": type_id, "ui": ui.current(bs, type_id), "data": data}

    def _attach(self, building_id: str, worker) -> None:
        """Once per worker: its view's `attach(worker, host)` hands it what only the face knows (a
        Crag's `probe`: busy orks and quotas), as the TUI's views do when they mount."""
        if worker is None or self._attached.get(building_id) is worker:
            return
        self._attached[building_id] = worker
        attach = getattr(views.of(self.type_of(building_id)), "attach", None)
        if attach is not None:
            attach(worker, self)

    # -- the clocks ----------------------------------------------------------------------------

    def tick(self, now: float | None = None) -> None:
        """Once a second: the roads' timers, the roster (and its questions), the treasury every 5 s."""
        now = time.monotonic() if now is None else now
        try:
            self.town.roads.tick()
        except Exception as e:                     # a road's timer never stops the clock
            self.town.toast(str(e), title="Roads", severity="error")
        if now - self._telemetry_at >= TELEMETRY_REFRESH_S:
            self._telemetry_at = now
            self.treasury.refresh()
        for bid, w in list(self.town.workers.items()):     # the workers that look again by themselves
            view = views.of(self.type_of(bid))
            self._attach(bid, w)
            every = getattr(view, "REFRESH_S", 0)
            if every and now - self._refreshed.get(bid, -every) >= every:
                self._refreshed[bid] = now
                try:
                    view.refresh(w)
                except Exception as e:                 # one building's look never stops the clock
                    self.town.toast(f"{type(e).__name__}: {e}", title=self.town.title_of(bid), severity="error")
        self.refresh_roster()
        self._night()
        self._wakes(now)
        self.growth.tick(now)
        self.you.tick()
        self.usage.tick(now)
        self.updates.tick(now)
        self.onboarding.tick(now)

    def _wakes(self, now: float) -> None:
        """A script-first building's ork wakes on an error or a 👎 (core/wakes.py), as its keeper's job."""
        if now - self._wakes_at < wakes.WAKE_CHECK_S:
            return
        self._wakes_at = now
        try:
            for wake in wakes.due(self.town):
                if self.console.keeper_wake(wake):
                    wakes.taken(self.town, wake)
        except Exception as e:                     # a wake never stops the clock
            self.town.toast(f"{type(e).__name__}: {e}", title="Wakes", severity="error")

    # -- 🏛 quiet hours: the Elders (core/night.py), the retros and the orks' changes (gui/nightly.py) ----

    def _night(self) -> None:
        machine = self.town.machine
        quiet = schedule.quiet_now(machine)
        morning = self.night.tick(quiet)
        if morning:
            words = self.night.morning_words(self.muster.roster.alerts)
            if words:
                self.town.toast(".\n".join(words) + ".", title="While you were away, the Elders", timeout=15)
            self.night.morning()
        try:
            self.nightly.tick(quiet, morning)
        except Exception as e:                     # the night's work never stops the clock
            self.town.toast(f"{type(e).__name__}: {e}", title="Quiet hours", severity="error")
        alert = self.night.next_question(self.muster.roster.alerts, quiet, machine.autonomy,
                                         machine.autonomy_wait)
        if alert is None:
            return
        who = self.muster.who().get(alert.id, "")
        repo = self.town.repo_root

        def work() -> None:
            runner = runners.ELDERS_RUNNER or fastpath.light_runner(repo)
            decision = elders.judge(alert, runner, elders.limits(repo)[1])
            self.town.call(self._judged, alert, who, decision)

        threading.Thread(target=work, daemon=True, name="elders").start()

    def _judged(self, alert, who: str, decision) -> None:
        """The advice is kept for the person, or (from 🕰 on the clock, the same question still waits) their key
        goes to the session."""
        machine = self.town.machine
        send = self.night.judged(alert, decision, who, self.muster.roster.alerts, schedule.quiet_now(machine),
                                 machine.autonomy)
        if send is not None:
            self.sessions.write(alert.ref, send.encode())
        self.refresh_roster()

    def refresh_roster(self) -> None:
        """The roster again, with what each session's screen says now (its questions) and what each building
        asks (a worker's `orders_alert`: its hut burns)."""
        self.muster.rebuild(self.sessions.infos(), self.sessions.keys(), self._building_alerts())
        self.on_change()

    def _building_alerts(self) -> list[tuple]:
        out, asking = [], {}
        for bid, w in list(self.town.workers.items()):
            try:
                wanted = w.orders_alert()
            except Exception:                      # a building's question never breaks the roster
                wanted = None
            if wanted:
                key, title, context, options = wanted
                out.append((bid, key, title, list(context), list(options)))
                asking[bid] = key
        self._asking = asking
        return out

    def _alert_changed(self, building_id: str) -> bool:
        """Whether a building began or stopped asking since the roster was made."""
        w = self.town.workers.get(building_id)
        try:
            wanted = w.orders_alert() if w is not None else None
        except Exception:
            wanted = None
        return (wanted[0] if wanted else None) != getattr(self, "_asking", {}).get(building_id)

    def close(self) -> None:
        """The window closed: what an editor holds is written, what runs stops, the scroll is kept."""
        for bid, w in list(self.town.workers.items()):
            flush = getattr(views.of(self.type_of(bid)), "flush", None)
            if flush is not None:
                try:
                    flush(w)
                except Exception:
                    pass
        lake_view.flush_town(self.town.lake)
        self.sessions.close()
        self.town.close()
        self.town.save()
        self.usage.close()

    # -- the page's commands -------------------------------------------------------------------

    def command(self, name: str, args: dict | None = None) -> Any:
        fn = self.commands.get(name)
        if fn is None:
            raise CommandError(f"Unknown command: {name}")
        args = dict(args or {})
        try:
            result = fn(args)
        except (console.ConsoleError, growth.GrowthError, updates.UpdateError, onboarding.OnboardingError,
                you.YouError, accounts.AccountsError) as e:
            raise CommandError(str(e)) from None
        self._used(name, args, result)
        return result

    # -- anonymous usage stats (core/usage.py): which features, never what is in them -------------

    def _opened(self) -> None:
        m = self.town.machine
        self.usage.track("app_opened", face="gui",
                         tools=[t for t, c in m.tools.items() if c.enabled],
                         buildings=usage.count(sum(1 for b in self.town.scroll.buildings if not b.demolished)),
                         roads=usage.count(len(state.roads(self.town))))

    def _used(self, name: str, args: dict, result: Any) -> None:
        if name == "town.build" and isinstance(result, str):
            self.usage.track("building_built", type=self.type_of(result))
        elif name == "town.demolish" and result:
            self.usage.track("building_demolished")
        elif name == "roads.lay" and result:
            self.usage.track("road_laid")
        elif name == "sessions.new" and result:
            self.usage.track("session_opened", harness=args.get("harness"))
        elif name == "halt":
            self.usage.track("halted")

    def _spec(self, args: dict):
        bs = self.town.scroll.building(str(args.get("id", "")))
        if bs is None or bs.demolished:
            raise CommandError(f"No building {args.get('id')!r}")
        return bs

    def _select_orkspace(self, args: dict) -> None:
        oid = str(args.get("id", ""))
        if not any(o.id == oid for o in self.town.scroll.orkspaces):
            raise CommandError(f"No orkspace {oid!r}")
        self.town.scroll.active_orkspace_id = oid
        self.town.save()
        self.on_change()

    def _new_orkspace(self, args: dict) -> str:
        """A new empty orkspace, named by the person, and the town goes to it."""
        from orkcraft import scroll
        try:
            biome = args.get("biome") if args.get("biome") in scroll.BIOMES else biomes.for_new(self.town.scroll)
            ork = scroll.new_orkspace(self.town.scroll, self._word(args, "name")[:60], biome=biome)
        except ValueError as e:
            raise CommandError(str(e)) from None
        self.town.scroll.active_orkspace_id = ork.id
        self.town.save()
        self.on_change()
        return ork.id

    def _move_hut(self, args: dict) -> None:
        """A hut dragged on the town: its spot as fractions of the canvas, the person's own."""
        bs = self._spec(args)
        if bs.id == "town_hall":
            raise CommandError("The Town Hall stands in its corner")
        if bs.pinned:
            raise CommandError(f"{bs.title} is pinned — unpin it to move it")
        try:
            x, y = float(args["x"]), float(args["y"])
        except (KeyError, TypeError, ValueError):
            raise CommandError("A hut's spot is two numbers") from None
        bs.hut = [round(min(max(x, 0.0), 1.0), 4), round(min(max(y, 0.0), 1.0), 4)]
        self.town.save()
        self.on_change()

    def _open_building(self, args: dict) -> dict:
        bs = self._spec(args)
        w = self.town.worker(bs.id)
        return {"id": bs.id, "has_worker": w is not None}

    def _act(self, args: dict) -> Any:
        """One of a building's own acts (gui/views/<type>.py `ACTS`), done by its worker."""
        bs = self._spec(args)
        view, worker = views.of(self.type_of(bs.id)), self.town.worker(bs.id)
        fn = (view.ACTS.get(str(args.get("act", ""))) if view is not None and worker is not None else None)
        if fn is None:
            raise CommandError(f"{bs.title} cannot {args.get('act')!r} here")
        try:
            return fn(worker, dict(args.get("args") or {}))
        except views.ActError as e:
            raise CommandError(str(e)) from None

    @staticmethod
    def _word(args: dict, key: str) -> str:
        value = args.get(key, "")
        if not isinstance(value, str) or not value:
            raise CommandError(f"{key} is missing")
        return value[:500]

    @staticmethod
    def _session_call(fn, *a) -> Any:
        try:
            return fn(*a)
        except ValueError as e:
            raise CommandError(str(e)) from None

    def _deploy(self, args: dict) -> str | None:
        message = args.get("message") or ""
        key = self._session_call(self.sessions.deploy, self._word(args, "ork"), self.muster, self.treasury,
                                 str(message)[:4000])
        self.refresh_roster()
        return key

    def _past(self, args: dict) -> list[dict]:
        """This project's earlier sessions that can be reopened here, newest first."""
        found = [s for s in past.collect_sessions(self.town.repo_root) if s.resumable][:100]
        return [{"key": s.key, "harness": s.harness, "title": modes.strip_emoji(s.title or s.short_id),
                 "when": s.last.isoformat(timespec="minutes") if s.last else "", "live": s.key in self.sessions.live}
                for s in found]

    def _input(self, args: dict) -> bool:
        data = args.get("data", "")
        if not isinstance(data, str):
            raise CommandError("data is not text")
        return self.sessions.write(self._word(args, "key"), data.encode("utf-8", "surrogatepass")[:65536])

    def _answer(self, args: dict) -> bool:
        """The person answers a question (Orders): a session gets the key typed, the rest are acknowledged."""
        alert = self.muster.alert(self._word(args, "id"))
        if alert is None:
            raise CommandError("That question was answered already")
        if not self.muster.answer(alert, self._word(args, "key"), self.sessions.write, self._view_answer):
            raise CommandError("Not one of its answers")
        self.refresh_roster()
        return True

    def _view_answer(self, building_id: str, key: str) -> str | None:
        """An answer to a building's own question goes to its worker."""
        w = self.town.workers.get(building_id)
        try:
            return w.answer_alert(key) if w is not None else None
        except ValueError as e:
            raise CommandError(str(e)) from None

    def _building(self, fn, args: dict) -> Any:
        try:
            return fn(self, args)
        except builder.BuildError as e:
            raise CommandError(str(e)) from None

    def _follow(self, args: dict) -> bool:
        """The person follows the Elders' advice on a question: their key, sent as the person's own answer."""
        alert = self.muster.alert(self._word(args, "id"))
        advice = self.night.advice_for(alert) if alert is not None else None
        if advice is None or advice.key is None:
            raise CommandError("No advice waits on that question")
        return self._answer({"id": alert.id, "key": advice.key})

    def _halt(self, args: dict) -> int:
        """🛑 Halt All: every session interrupted, every agent process killed, the buildings' work stopped."""
        stopped = self.sessions.interrupt_all() + max(halt.halt_all(), self.town.halt())
        self.town.toast(f"Stopped {stopped} building{'s' if stopped != 1 else ''}" if stopped
                        else "Nothing was running", title="Halt All")
        return stopped
