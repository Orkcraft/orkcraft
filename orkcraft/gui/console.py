"""The console's acts for the GUI: what the TUI's console and Command Card do to a selected building
or ork (screens/console.py, tui/garrison.py, tui/council.py), as the host's commands.

Quick ones answer at once (👍 / 👎, the goal, pin, revert, recruit by hand, orders, model, dismiss,
halt, the roads it listens to). The ones that call a model — the Recruiter, the Council's Fast Path,
the steward's watch and a redesign — run in a thread as a *job*: the snapshot carries every job
(`jobs`), the page shows it, and when it is ready the person takes it (`job.accept`) or lets it go
(`job.drop`). Nothing here shows anything: it changes the town and says so with a toast.

    console = Console(host)
    host.commands.update(console.commands())
"""
from __future__ import annotations

import copy
import itertools
import threading
from typing import Any, Callable

from orkcraft import scroll
from orkcraft.core import buildings as core_buildings
from orkcraft.core import bus
from orkcraft.core import roads as core_roads
from orkcraft.core import runners
from orkcraft.design import ui
from orkcraft.gui import info
from orkcraft.realm import builders, catalog, chronicles, fastpath, modes, pipes, recruiter, steward, tiers
from orkcraft.realm.orcs import TRIGGERS, Trigger

def plain(text: str) -> str:
    """What Office shows of a label: its words, no emoji (modes.text, realm/lexicon.py)."""
    return modes.text(text, modes.OFFICE)


class ConsoleError(Exception):
    """A console act the host refuses; the host turns it into a CommandError."""


def tier_choices() -> list[list[str]]:
    """The tier picker, as the TUI's (screens/garrison_modal.py): the heavy models first, then the CLI's own."""
    return [[t, plain(f"{tiers.label(t)} — {' · '.join(m[t] for m in tiers.MODELS.values())}")] for t in tiers.TIERS] + \
        [["", "CLI default model"]]


class Console:
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
            "building.goal": lambda a: core_buildings.cycle_goal(self.town, self._spec(a).id),
            "building.pin": self.pin,
            "building.revert": self.revert,
            "building.quick": self.quick,
            "building.recruit": self.recruit,
            "building.recruit_ask": self.recruit_ask,
            "building.redesign": self.redesign,
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
            # Shared by every type (docs/design/building-views.md §4): stubs until tracks L and K land.
            "lake.open": self.lake_open,
            "keeper.ask": self.keeper_ask,
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
        """The agent CLIs this machine runs (onboarding's tools); Claude and agy when none is chosen."""
        enabled = tuple(t for t, c in self.town.machine.tools.items() if c.enabled and t in scroll.HARNESSES)
        return enabled or ("claude", "agy")

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
            harness = str(step.get("harness", "claude"))
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

    def revert(self, args: dict) -> bool:
        ok = core_buildings.revert(self.town, self._spec(args).id)
        self.host.refresh_roster()
        return ok

    def quick(self, args: dict) -> bool:
        """One of the type's quick actions (the Command Card). Its handler comes with the type's own
        view; until then the person is told so, never left with a silent button."""
        bs = self._spec(args)
        t = catalog.type_of(self.town.spec_of(bs.id))
        act = t.action(str(args.get("action") or ""))
        if act is None:
            raise ConsoleError(f"{bs.title} has no such action")
        quick = getattr(self.town.worker(bs.id), "quick_action", None)      # a worker that does it
        if quick is not None and quick(act.id):
            return True
        self.town.toast(f"{act.label}: arrives with the {t.title} view", title=bs.title)
        return False

    # -- Lake and the keeper: what every type calls --------------------------------------------------

    def lake_open(self, args: dict) -> str:
        """A document opened in Lake: shown in the town's Lake building (the Lake window replaces this)."""
        kind = str(args.get("kind") or "text")
        value = self._text(args, "value", 2_000_000)
        if kind not in ("file", "text") or not value:
            raise ConsoleError("Nothing to open")
        lake = next((b for b in self.town.scroll.buildings if not b.demolished
                     and catalog.type_of(self.town.spec_of(b.id)).id == "lake"), None)
        worker = self.town.worker(lake.id) if lake is not None else None
        if worker is None:
            raise ConsoleError("Lake opens documents once the Lake window is here — no Lake in this town yet")
        worker.show_value(kind, value, self._text(args, "title", 200))
        return lake.id

    def keeper_ask(self, args: dict) -> None:
        """A building's keeper asked in plain words: arrives with the keeper (track K)."""
        self._spec(args)
        raise ConsoleError("The keeper takes requests soon — for now Redesign and the orks' orders")

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
            if pick is None or str(step.get("harness", "claude")) not in scroll.HARNESSES:
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

    # -- jobs: the model calls, in a thread ------------------------------------------------------------

    def public_jobs(self) -> list[dict[str, Any]]:
        return [{k: v for k, v in j.items() if not k.startswith("_")} for j in self.jobs.values()]

    def _job(self, kind: str, building_id: str, text: str, work: Callable[[], Any],
             done: Callable[[dict, Any], None]) -> str:
        """`work()` in a thread; `done(job, result)` back on the host's thread."""
        jid = f"{kind}-{next(self._ids)}"
        self.jobs[jid] = {"id": jid, "kind": kind, "building": building_id, "title": plain(self.town.title_of(building_id)),
                          "state": "running", "text": text, "error": "", "view": {}}
        self._run(self.jobs[jid], text, work, done)
        return jid

    def _run(self, job: dict, text: str, work: Callable[[], Any], done: Callable[[dict, Any], None]) -> None:
        jid = job["id"]
        job.update(state="running", text=text, _accept=None)

        def run() -> None:
            try:
                result, failed = work(), None
            except Exception as e:                   # a model call never takes the town down
                result, failed = None, f"{type(e).__name__}: {e}"
            self.town.call(self._finished, jid, result, failed, done)

        threading.Thread(target=run, daemon=True, name=f"gui-{jid}").start()
        self.host.on_change()

    def _finished(self, jid: str, result: Any, failed: str | None, done: Callable[[dict, Any], None]) -> None:
        job = self.jobs.get(jid)
        if job is None:                              # let go while it ran
            return
        if failed:
            job.update(state="failed", error=failed[:500])
        else:
            try:
                done(job, result)
            except Exception as e:
                job.update(state="failed", error=f"{type(e).__name__}: {e}"[:500])
        self.host.refresh_roster()

    def drop(self, args: dict) -> bool:
        """The person lets a job go: a running one finishes unseen, a ready one is not taken."""
        job = self.jobs.pop(self._word(args, "job"), None)
        if job is not None and job.get("_verdict") is not None and not job.get("_blocked"):
            fastpath.log(self.town.repo_root, job["_verdict"], "cancelled")
        self.host.on_change()
        return job is not None

    def accept(self, args: dict) -> Any:
        job = self.jobs.get(self._word(args, "job"))
        if job is None:
            raise ConsoleError("That is gone")
        accept = job.get("_accept")
        if job["state"] not in ("ready", "verdict") or accept is None:
            raise ConsoleError("Nothing to take yet")
        return accept(job, args)

    # -- R: the Recruiter, then the Council ------------------------------------------------------------

    def recruit_ask(self, args: dict) -> str:
        """R → a description → the Recruiter (one model call per attempt) → its handler to look at."""
        bs = self._spec(args)
        prompt = self._text(args, "prompt")
        if not prompt:
            raise ConsoleError("Describe what the ork should do")
        self._budget()
        snapshot, harnesses = copy.deepcopy(self.town.scroll), self.harnesses()
        work = lambda: recruiter.recruit(prompt, snapshot, bs.id, runner=runners.RECRUIT_RUNNER or builders.claude_runner,
                                         harnesses=harnesses)
        return self._job("recruit", bs.id, "The Recruiter is choosing chain → script → agent…", work, self._recruited)

    def _recruited(self, job: dict, result: recruiter.RecruitResult) -> None:
        if not result.ok:
            why = result.error or "; ".join(result.attempts[-1].errors[:2] if result.attempts else []) or "no handler"
            job.update(state="failed", error=f"The Recruiter failed: {why}")
            return
        orc = result.orc or {}
        titles = {b.id: b.title for b in self.town.scroll.buildings}
        job["view"] = {
            "name": orc.get("name", ""), "kind": orc.get("kind", "agent"), "why": plain(str(orc.get("why", ""))),
            "role": plain(str(orc.get("role", ""))), "orders": plain(str(orc.get("orders", ""))),
            "tier": plain(tiers.label(tiers.orc_tier(orc.get("harness") or [], orc.get("kind", "agent"))) or ""),
            "chain": len(orc.get("chain") or []), "script": result.script_source[:1500],
            "roads": [{"from": titles.get(r["from"], r["from"]), "event": pipes.label(r["event"])} for r in result.roads],
            "attempts": len(result.attempts),
            "cost": f"${result.cost_usd:.2f}" if result.cost_usd is not None else "",
        }
        job.update(state="ready", text="Hire it?", _result=result, _accept=self._council)

    def _council(self, job: dict, args: dict) -> str | None:
        """Hire → the Council's Fast Path first (rules, then a light model); a clean review hires."""
        result: recruiter.RecruitResult = job["_result"]
        bid = job["building"]
        if job["state"] == "verdict":                # the person read the objections and hires anyway
            if job.get("_blocked"):
                raise ConsoleError("The Council rejected it")
            fastpath.log(self.town.repo_root, job["_verdict"], "overridden")
            return self._hire(job)
        subject = fastpath.Subject("agent", str((result.orc or {}).get("name") or "orc"),
                                   {"building": bid, "orc": result.orc, "roads": result.roads}, result.script_source)
        repo, demo = self.town.repo_root, self.town.demo
        runner = None if demo else (runners.FASTPATH_RUNNER or fastpath.light_runner(repo))
        model = str(fastpath.settings(repo).get("fast_model") or "")
        def work() -> fastpath.Verdict:
            return fastpath.review(subject, repo, set(), runner, model)

        def done(job: dict, verdict: fastpath.Verdict) -> None:
            if verdict.clean:
                fastpath.log(repo, verdict, "approved")
                self._hire(job)
                return
            notes = [{"role": n.role, "severity": n.severity, "text": plain(n.text)}
                     for n in verdict.notes if n.severity != "ok"]
            job.update(state="verdict", text="The Council has notes", _verdict=verdict, _blocked=verdict.blocked,
                       _accept=self._council)
            job["view"] = {**job["view"], "notes": notes, "blocked": verdict.blocked}
            if verdict.blocked:
                fastpath.log(repo, verdict, "rejected")

        self._run(job, "The Council is looking at it…", work, done)
        return None

    def _hire(self, job: dict) -> str:
        bid = job["building"]
        try:
            orc = recruiter.apply(self.town.scroll, bid, job["_result"], self.town.repo_root)
        except (ValueError, OSError) as e:
            raise ConsoleError(str(e)) from None
        if orc.script is not None:                   # the person saw it and the Council passed it
            orc.script = {**orc.script, "reviewed": True}
            orc.status = "idle"
        self.jobs.pop(job["id"], None)
        self.town.publish(bus.ROADS)
        self._saved()
        self._record(bid, "orc_recruited", orc=orc.name)
        self.town.toast(f"{orc.name} ({orc.kind}) joined {self.town.title_of(bid)}", title="Recruiter")
        return f"{bid}/{orc.id}"

    # -- W: the steward's watch, and its report -------------------------------------------------------

    def watch(self, args: dict) -> str:
        bs, member, orc = self._member(args)
        if not orc.lead:
            raise ConsoleError("The watch is the steward's: pick its building's steward")
        if any(j["kind"] == "watch" and j["building"] == bs.id and j["state"] == "running" for j in self.jobs.values()):
            raise ConsoleError("The steward is looking already")
        repo, snapshot = self.town.repo_root, copy.deepcopy(self.town.scroll)
        carts, runs = list(self.town.roads.carts), list(self.town.roads.runs)
        budget_ok = not self.host.treasury.exhausted(quiet=True)

        def work() -> steward.StewardReport:
            report = steward.watch(repo, snapshot, bs.id, carts=carts, runs=runs,
                                   runner=runners.STEWARD_RUNNER or builders.claude_runner, budget_ok=budget_ok)
            try:
                steward.save_report(repo, report)
            except OSError:
                pass
            return report

        def done(job: dict, report: steward.StewardReport) -> None:
            self._record(bs.id, "steward_report", findings=len(report.findings), proposals=len(report.proposals))
            self._show_report(job, steward.load_report(repo, bs.id))

        return self._job("watch", bs.id, "The steward is looking at the building…", work, done)

    def report(self, args: dict) -> str:
        """The steward's last report, to read and apply a proposal from."""
        bs = self._spec(args)
        data = steward.load_report(self.town.repo_root, bs.id)
        if data is None:
            raise ConsoleError("Not watched yet — Watch now")
        jid = f"report-{next(self._ids)}"
        self.jobs[jid] = {"id": jid, "kind": "watch", "building": bs.id, "title": bs.title, "state": "ready",
                          "text": "", "error": "", "view": {}}
        self._show_report(self.jobs[jid], data)
        self.host.on_change()
        return jid

    def _show_report(self, job: dict, data: dict | None) -> None:
        if data is None:
            job.update(state="failed", error="The steward wrote no report")
            return
        proposals = []
        for i, p in enumerate(data.get("proposals", [])):
            rep = p.get("replay") or {}
            ready = p.get("type") != "demote" or (rep.get("score", 0) >= 0.8 and rep.get("total", 0) >= 1)
            proposals.append({"index": i, "type": str(p.get("type", "")), "why": plain(str(p.get("why", ""))),
                              "ready": bool(ready) and p.get("type") != "note",
                              "replay": f"replay {rep.get('exact', 0)}/{rep.get('total', 0)} exact · agrees "
                                        f"{rep.get('score', 0):.0%}" if rep else "",
                              "outline": ui.outline(p["ui"]) if p.get("type") == "ui" and isinstance(p.get("ui"), dict) else ""})
        cost = data.get("cost_usd")
        job["view"] = {"ts": str(data.get("ts", ""))[:16].replace("T", " "),
                       "findings": [plain(str(f.get("summary", ""))) for f in data.get("findings", [])],
                       "proposals": proposals, "cost": f"${cost:.2f}" if isinstance(cost, (int, float)) else ""}
        job.update(state="ready", text="", _data=data, _accept=self._apply_proposal)

    def _apply_proposal(self, job: dict, args: dict) -> str:
        index = args.get("index")
        data = job["_data"]
        if not isinstance(index, int) or not 0 <= index < len(data.get("proposals", [])):
            raise ConsoleError("Pick a proposal")
        if job["kind"] == "redesign":
            p = data["proposals"][index]
            problems = core_buildings.set_ui(self.town, job["building"], p.get("ui"), by="steward", why=p.get("why", ""))
            if problems:
                raise ConsoleError("\n".join(problems))
            what = "a new layout"
        else:
            what = core_buildings.apply_steward(self.town, job["building"], data, index, by="you")
            if what is None:
                raise ConsoleError("It could not be applied (see the note)")
        self.jobs.pop(job["id"], None)
        self._saved()
        self.town.toast(f"{plain(what)} — Revert takes it back", title=f"Steward · {job['title']}")
        return what

    # -- D: a redesign of the building's window ------------------------------------------------------

    def redesign(self, args: dict) -> str | None:
        """Say what should change in the window; its steward rewrites the UI document (one model call,
        checked against the type's contract); `default` puts the type's own layout back."""
        bs = self._spec(args)
        request = self._text(args, "request", 1000)
        if not request:
            raise ConsoleError("Say what should change")
        if request.lower() in ("default", "reset"):
            problems = core_buildings.set_ui(self.town, bs.id, None, by="you", why="back to the default layout")
            if problems:
                raise ConsoleError("\n".join(problems))
            self.town.toast("the type's own layout again", title=bs.title)
            return None
        self._budget()
        repo, snapshot = self.town.repo_root, copy.deepcopy(self.town.scroll)
        type_id = core_buildings.ui_type(self.town, bs.id)

        def work() -> steward.StewardReport:
            return steward.redesign(repo, snapshot, bs.id, type_id, request,
                                    runner=runners.STEWARD_RUNNER or builders.claude_runner)

        def done(job: dict, report: steward.StewardReport) -> None:
            if not report.proposals:
                why = report.error or "; ".join(report.errors[:3]) or "no layout came back"
                job.update(state="failed", error=f"Not redesigned: {why}")
                return
            self._show_report(job, {"ts": "", "cost_usd": report.cost_usd,
                                    "findings": [{"summary": request[:200]}],
                                    "proposals": [p.to_dict() for p in report.proposals]})

        return self._job("redesign", bs.id, "The steward is redrawing the window…", work, done)
