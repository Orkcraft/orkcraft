"""The console's acts for the GUI: what the TUI's console and Command Card do to a selected building
or ork (screens/console/, tui/garrison.py, tui/council.py), as the host's commands.

Quick ones answer at once (👍 / 👎, the goal, pin, revert, recruit by hand, orders, model, dismiss,
halt, the roads it listens to). The ones that call a model — the Recruiter, the Council's Fast Path,
the steward's watch, a redesign and a request to the keeper — run in a thread as a *job*: the snapshot
carries every job (`jobs`), the page shows it, and when it is ready the person takes it (`job.accept`)
or lets it go (`job.drop`). Nothing here shows anything: it changes the town and says so with a toast.

Its parts, each a mixin with the console as `self`: the jobs (jobs.py), Lake and the keeper
(keeper.py), the Recruiter and the Council (recruiter.py), the steward's watch and a redesign
(steward.py).

    console = Console(host)
    host.commands.update(console.commands())
"""
from __future__ import annotations

import itertools
from typing import Any, Callable

from orkcraft import scroll
from orkcraft.core import buildings as core_buildings
from orkcraft.core import roads as core_roads
from orkcraft.gui import info
from orkcraft.gui.jobs import ConsoleError, JobsMixin, plain
from orkcraft.gui.keeper import KeeperMixin
from orkcraft.gui.recruiter import RecruiterMixin
from orkcraft.gui.road_planner import RoadPlannerMixin
from orkcraft.gui.steward import StewardMixin
from orkcraft.gui.views import lake as lake_view
from orkcraft.realm import catalog, chronicles, steward, tiers
from orkcraft.realm.orcs import TRIGGERS, Trigger


def tier_choices() -> list[list[str]]:
    """The tier picker, as the TUI's (screens/garrison_modal.py): the heavy models first, then the CLI's own."""
    return [[t, plain(f"{tiers.label(t)} — {' · '.join(m[t] for m in tiers.MODELS.values() if t in m)}")] for t in tiers.TIERS] + \
        [["", "CLI default model"]]


class Console(JobsMixin, KeeperMixin, RecruiterMixin, RoadPlannerMixin, StewardMixin):
    def __init__(self, host) -> None:
        self.host = host
        self.town = host.town
        self.jobs: dict[str, dict[str, Any]] = {}
        self._ids = itertools.count(1)

    def commands(self) -> dict[str, Callable[[dict], Any]]:
        return {
            "info": self.info,
            "history": lambda a: info.history(self.town, self.host.muster, self._spec(a).id, str(a.get("ork") or ""),
                                              str(a.get("tool") or "")),
            "building.like": lambda a: core_buildings.like(self.town, self._spec(a).id),
            "building.dislike_context": self.dislike_context,
            "building.dislike": self.dislike,
            "building.goal": lambda a: core_buildings.cycle_goal(self.town, self._spec(a).id, str(a.get("value") or "")),
            "building.autonomy": lambda a: core_buildings.set_autonomy(self.town, self._spec(a).id,
                                                                       str(a.get("value") or "") or None),
            "building.waits": lambda a: core_buildings.set_waits(self.town, self._spec(a).id,
                                                                 _int(a.get("question")), _int(a.get("rebuild"))),
            "building.pin": self.pin,
            "building.fold": self.fold,
            "building.revert": self.revert,
            "building.quick": self.quick,
            "building.recruit": self.recruit,
            "building.recruit_ask": self.recruit_ask,
            "building.redesign": self.redesign,
            "steward.models": self.steward_models,
            "roads.plan": self.road_plan,
            "road.handlers": self.road_handlers,
            "road.handler": self.road_handler,
            "ork.like": lambda a: self.rate_ork(a, True),
            "ork.dislike": lambda a: self.rate_ork(a, False),
            "ork.dismiss": self.dismiss,
            "ork.halt": self.halt_ork,
            "ork.orders": self.orders,
            "ork.model": self.model,
            "ork.watch": self.watch,
            "ork.report": self.report,
            "job.accept": self.accept,
            "job.drop": self.drop,
            # Shared by every type (docs/design/building-views.md §4).
            "lake.open": self.lake_open,
            "keeper.ask": self.keeper_ask,
            **{name: self._lake_call(fn) for name, fn in lake_view.commands(self.town).items()},
        }

    # -- helpers --------------------------------------------------------------------------------------

    def _spec(self, args: dict):
        bs = self.town.scroll.building(str(args.get("id", "")))
        if bs is None or bs.demolished:
            raise ConsoleError(f"No building {args.get('id')!r}")
        return bs

    @staticmethod
    def _word(args: dict, key: str) -> str:
        value = args.get(key, "")
        if not isinstance(value, str) or not value:
            raise ConsoleError(f"{key} is missing")
        return value[:500]

    @staticmethod
    def _text(args: dict, key: str, limit: int = 2000) -> str:
        value = args.get(key, "")
        return value.strip()[:limit] if isinstance(value, str) else ""

    def _ork(self, args: dict):
        orc = info.find_ork(self.host.muster, self._word(args, "ork"))
        if orc is None:
            raise ConsoleError("That ork is gone")
        return orc

    def _member(self, args: dict):
        """(building spec, orc spec, roster ork) of a garrison ork."""
        orc = self._ork(args)
        if "/" not in orc.ref:
            raise ConsoleError(f"{orc.name} is not in a garrison")
        b_id, orc_id = orc.ref.split("/", 1)
        bs = self.town.scroll.building(b_id)
        member = bs.garrison.orc(orc_id) if bs is not None else None
        if member is None:
            raise ConsoleError(f"{orc.name}: not found in its building")
        return bs, member, orc

    def _record(self, building_id: str, type_: str, **fields: Any) -> None:
        try:
            chronicles.record(self.town.repo_root, self.town.scroll, building_id, type_, **fields)
        except OSError:
            pass

    def _saved(self) -> None:
        self.town.save()
        self.host.refresh_roster()

    def harnesses(self) -> tuple[str, ...]:
        """The agent CLIs this machine runs (onboarding's tools); the main tool when none is chosen."""
        enabled = tuple(t for t, c in self.town.machine.tools.items() if c.enabled and t in scroll.HARNESSES)
        return enabled or ("main",)

    def _budget(self) -> None:
        if self.host.treasury.exhausted():
            raise ConsoleError("The budget is spent — this calls a model")

    # -- Info -----------------------------------------------------------------------------------------

    def info(self, args: dict) -> dict | None:
        """What the console's Info says of a building, or of one of its orks (`ork`: its ref)."""
        bs = self._spec(args)
        ref = args.get("ork")
        if ref:
            found = info.ork(self.town, self.host.muster, str(ref))
            if found is not None and found["garrison"]:
                _, member, _ = self._member({"ork": str(ref)})
                found.update(self._orders_of(member))
            return found
        found = info.building(self.town, self.host.muster, bs.id)
        if found is not None:
            found["tiers"] = tier_choices()          # the Recruit dialog's picker
        return found

    def _orders_of(self, member) -> dict[str, Any]:
        """What the orders and model dialogs edit: orders, trigger, tier and each harness step."""
        steps = []
        for step in member.harness:
            harness = str(step.get("harness", "main"))
            steps.append({"role": str(step.get("role", "run")), "harness": harness,
                          "tier": (tiers.step_tier(step) or "") if (step.get("tier") or step.get("model")) else "",
                          "editable": harness in scroll.HARNESSES})
        return {"orders": member.orders, "trigger": {"type": member.trigger.get("type", "on_demand"),
                                                     "expression": member.trigger.get("expression", "")},
                "triggers": [[k, name] for k, (_, name) in TRIGGERS.items()],
                "uses_model": bool(member.uses_model), "steps": steps,
                "harnesses": list(scroll.HARNESSES), "tiers": tier_choices()}

    def dislike_context(self, args: dict) -> dict:
        last, cascade = core_buildings.dislike_context(self.town, self._spec(args).id)
        return {"last": plain(last)[:2000], "cascade": [[plain(title), share] for title, share in cascade]}

    def dislike(self, args: dict) -> None:
        """👎: what went wrong — broken inputs (its suppliers pay) or its own logic."""
        kind = str(args.get("kind") or "logic")
        core_buildings.dislike(self.town, self._spec(args).id, kind if kind in ("inputs", "logic") else "logic",
                               self._text(args, "note"))

    def pin(self, args: dict) -> bool:
        """📌 A pinned building keeps its place: its hut is not dragged (the TUI keeps its window's)."""
        bs = self._spec(args)
        bs.pinned = not bs.pinned
        self.town.save()
        self._record(bs.id, "pinned" if bs.pinned else "unpinned")
        self.town.toast(f"{bs.title} {'pinned' if bs.pinned else 'unpinned'}", title="Pin")
        self.host.on_change()
        return bs.pinned

    def fold(self, args: dict) -> bool:
        """▸ A folded hut shows its title bar only (docs/design/folded-cards.md). The Town Hall never folds."""
        from orkcraft.realm.buildings import TOWN_HALL
        bs = self._spec(args)
        if bs.id == TOWN_HALL:
            raise ConsoleError("The Town Hall never folds")
        bs.folded = not bs.folded
        self.town.save()
        self._record(bs.id, "folded" if bs.folded else "unfolded")
        self.host.on_change()
        return bs.folded

    def steward_models(self, args: dict) -> dict:
        """Which tier its steward runs each of its tasks on (realm/steward.py USES); "" is the default."""
        bs = self._spec(args)
        models = args.get("models") if isinstance(args.get("models"), dict) else {}
        try:
            kept = steward.set_models(bs, {str(k): str(v) for k, v in models.items()})
        except ValueError as e:
            raise ConsoleError(str(e)) from None
        self._saved()
        self.town.toast(", ".join(f"{k}: {tiers.TIER_LABELS[v]}" for k, v in kept.items()) or "every task on the default",
                        title=f"{bs.title} · steward's models")
        return kept

    def revert(self, args: dict) -> bool:
        ok = core_buildings.revert(self.town, self._spec(args).id)
        self.host.refresh_roster()
        return ok

    def quick(self, args: dict) -> Any:
        """One of the type's quick actions (the Command Card): its view's act of the same id
        (gui/views/<type>.py `ACTS`), else its worker's `quick_action`; until a type has either the
        person is told so, never left with a silent button."""
        bs = self._spec(args)
        t = catalog.type_of(self.town.spec_of(bs.id))
        act = t.action(str(args.get("action") or ""))
        if act is None:
            raise ConsoleError(f"{bs.title} has no such action")
        from orkcraft.gui import views
        view, worker = views.of(t.id), self.town.worker(bs.id)
        fn = getattr(view, "ACTS", {}).get(act.id) if worker is not None else None
        if fn is not None:
            try:
                return fn(worker, {})
            except views.ActError as e:
                raise ConsoleError(str(e)) from None
        quick = getattr(worker, "quick_action", None)      # a worker that does it
        if quick is not None and quick(act.id):
            return True
        self.town.toast(f"{act.label}: arrives with the {t.title} view", title=bs.title)
        return False

    # -- the garrison ---------------------------------------------------------------------------------

    def recruit(self, args: dict) -> str:
        """R by hand: an agent with a name, a role, orders and a tier."""
        bs = self._spec(args)
        tier = str(args.get("tier") or "") or None
        try:
            orc = scroll.recruit(self.town.scroll, bs.id, self._text(args, "name", 60), role=self._text(args, "role", 200),
                                 orders=self._text(args, "orders"), tier=tier if tier in tiers.TIERS else None)
        except ValueError as e:
            raise ConsoleError(str(e)) from None
        self._saved()
        self._record(bs.id, "orc_recruited", orc=orc.name)
        self.town.toast(f"{orc.name} joined the {bs.title} garrison", title="Garrison")
        return f"{bs.id}/{orc.id}"

    def rate_ork(self, args: dict, good: bool) -> None:
        """👍 / 👎 on a garrison ork's own work (its building's results are rated on the building)."""
        bs, member, orc = self._member(args)
        core_buildings.rate_orc(self.town, bs.id, member.id, orc.name, good, self._text(args, "note"))

    def dismiss(self, args: dict) -> None:
        bs, member, orc = self._member(args)
        if orc.session and (s := self.host.sessions.live.get(orc.session)) is not None and s.running:
            raise ConsoleError("Halt it first")
        try:
            scroll.dismiss_orc(self.town.scroll, bs.id, member.id)
        except ValueError as e:
            raise ConsoleError(str(e)) from None
        self._saved()
        self._record(bs.id, "orc_dismissed", orc=orc.name)

    def halt_ork(self, args: dict) -> bool:
        orc = self._ork(args)
        term = info.terminal_of(orc)
        if not term or not self.host.sessions.interrupt(term):
            self.town.toast("nothing to halt", title="Halt")
            return False
        if orc.building:
            self._record(orc.building, "orc_halted", orc=orc.name)
        self.town.toast(f"Halted {orc.name}", title="Halt")
        return True

    def orders(self, args: dict) -> None:
        """T: an ork's orders and trigger (and a handler's tier), kept in the Town Scroll."""
        bs, member, orc = self._member(args)
        t = args.get("trigger") if isinstance(args.get("trigger"), dict) else {}
        kind = str(t.get("type") or "on_demand")
        if kind not in TRIGGERS:
            raise ConsoleError(f"No trigger {kind!r}")
        trigger = Trigger(kind, str(t.get("expression") or "").strip()[:200])
        trig = trigger.to_dict()
        if "expression" in trig and not trig["expression"]:
            del trig["expression"]
        changes: dict[str, Any] = {"trigger": trig, "orders": self._text(args, "orders", 4000)}
        if "tier" in args and member.uses_model and not orc.lead:
            tier = str(args.get("tier") or "")
            changes["harness"] = tiers.with_tier(member.harness, tier if tier in tiers.TIERS else None)
        try:
            scroll.update_orc(self.town.scroll, bs.id, member.id, **changes)
        except ValueError as e:
            raise ConsoleError(str(e)) from None
        self._saved()
        self._record(bs.id, "orders_changed", orc=member.name, trigger=trigger.label)
        self.town.toast(f"{member.name}: orders saved ({trigger.label})", title="Orders")

    def model(self, args: dict) -> str:
        """🎒 The Inventory's model: harness and tier per step (a tier replaces a model named outright)."""
        bs, member, orc = self._member(args)
        if not member.uses_model:
            raise ConsoleError(f"{member.name}: its model is not set here")
        wanted = args.get("steps") if isinstance(args.get("steps"), list) else []
        out: list[dict] = []
        for i, step in enumerate(member.harness):
            pick = wanted[i] if i < len(wanted) and isinstance(wanted[i], dict) else None
            if pick is None or str(step.get("harness", "main")) not in scroll.HARNESSES:
                out.append(dict(step))            # a pipeline keeps its own models
                continue
            harness = str(pick.get("harness") or step.get("harness"))
            if harness not in scroll.HARNESSES:
                raise ConsoleError(f"No harness {harness!r}")
            tier = str(pick.get("tier") or "")
            out += tiers.with_tier([{**step, "harness": harness}], tier if tier in tiers.TIERS else None)
        try:
            scroll.update_orc(self.town.scroll, bs.id, member.id, harness=out)
        except ValueError as e:
            raise ConsoleError(str(e)) from None
        self._saved()
        label = tiers.label(tiers.orc_tier(out, member.kind)) or "CLI default model"
        self.town.toast(f"{member.name}: {label}", title="Model")
        return label

    # -- the roads it listens to ----------------------------------------------------------------------

    def road_handlers(self, args: dict) -> dict:
        """Who may take a road's carts: its building's handlers, or plain."""
        key = self._word(args, "key")
        found = core_roads.handlers(self.town, key)
        if found is None:
            raise ConsoleError("No such road")
        target_id, road_id = scroll.split_key(key)
        _, road = scroll.find_road(self.town.scroll, road_id, target_id)
        return {"current": road.handler or "", "handlers": [[oid, plain(label)] for oid, label in found]}

    def road_handler(self, args: dict) -> bool:
        handler = args.get("handler") if isinstance(args.get("handler"), str) and args.get("handler") else None
        if not core_roads.set_handler(self.town, self._word(args, "key"), handler):
            raise ConsoleError("The road kept its handler (see the note)")
        self.town.save()
        return True


def _int(value: object) -> int | None:
    """A whole number from the page, or None (as the town)."""
    try:
        return int(value) if value not in (None, "", 0, "0") else None
    except (TypeError, ValueError):
        return None
