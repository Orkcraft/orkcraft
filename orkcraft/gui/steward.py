"""The steward in the console: W, its watch and its report, and D, a redesign of the building's
window, as jobs (gui/jobs.py); a proposal is applied when the person takes it.

A part of `Console` (console.py): its methods run with the console as `self`.
"""
from __future__ import annotations

import copy
import dataclasses

from orkcraft.core import buildings as core_buildings
from orkcraft.core import runners
from orkcraft.design import ui
from orkcraft.gui.jobs import ConsoleError, plain
from orkcraft.realm import fastpath, roads, steward


class StewardMixin:
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
            report = steward.watch(repo, snapshot, bs.id, carts=carts, runs=runs, budget_ok=budget_ok,
                                   runner=steward.runner_for(snapshot.building(bs.id), "watch", runners.STEWARD_RUNNER))
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
            script = str(p.get("script") or "") if p.get("type") == "demote" else ""
            ready = p.get("type") != "demote" or bool(script) or (rep.get("score", 0) >= steward.READY_SCORE
                                                                 and rep.get("total", 0) >= 1)
            replayed = (f"replay {rep.get('exact', 0)}/{rep.get('total', 0)} exact · agrees {rep.get('score', 0):.0%}"
                        + (f" · {rep['escalated']} left to the steward" if rep.get("escalated") else "")) if rep else ""
            proposals.append({"index": i, "type": str(p.get("type", "")), "why": plain(str(p.get("why", ""))),
                              "ready": bool(ready) and p.get("type") != "note",
                              "replay": replayed or ("A script: Apply sends it to the Council, then replays it on the "
                                                     "rule's recorded runs; it replaces the rule only if they agree"
                                                     if script else ""),
                              "saves": plain(str(p.get("saves") or "")), "script": script[:1500],
                              "outline": ui.outline(p["ui"]) if p.get("type") == "ui" and isinstance(p.get("ui"), dict) else ""})
        cost = data.get("cost_usd")
        b = self.town.scroll.building(job["building"])
        names = {h.id: h.name for h in b.garrison.handlers} if b is not None else {}
        kinds = {h.id: h.kind for h in b.garrison.handlers} if b is not None else {}
        job["view"] = {"ts": str(data.get("ts", ""))[:16].replace("T", " "),
                       "rules": [plain(f"{'📜' if kinds.get(r['orc']) == 'steward' else '🧌'} {names.get(r['orc'], r['orc'])} · "
                                       f"{r['runs']} runs · ${float(r['usd']):.2f}") for r in data.get("rules") or []],
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
            done = next((p for p in job["view"]["proposals"] if p["index"] == index and p.get("applied")), None)
            if done is not None:
                return done["applied"]
            p = data["proposals"][index]
            if p.get("type") == "demote" and p.get("script") and not p.get("reviewed"):
                return self._review_script(job, index)       # the person took it: now the Council, then the replay
            what = core_buildings.apply_steward(self.town, job["building"], data, index, by="you")
            if what is None:
                raise ConsoleError("It could not be applied (see the note)")
        # A report's other proposals wait for the person, each taken or left on its own: the report closes
        # when they are all taken (or when the person closes it); a redesign is one layout and closes now.
        for p in job["view"]["proposals"]:
            if p["index"] == index:
                p["applied"] = plain(what)
        if job["kind"] == "redesign" or not any(p["ready"] and not p.get("applied") for p in job["view"]["proposals"]):
            self.jobs.pop(job["id"], None)
        self._saved()
        self.town.toast(f"{plain(what)} — Revert takes it back", title=f"Steward · {job['title']}")
        return what

    def _review_script(self, job: dict, index: int) -> None:
        """A script the steward wrote, applied by the person (their review): the Council's Fast Path reads it, then
        it is replayed on the rule's recorded runs; only a clean review and an agreeing replay replace the rule."""
        data, bid = job["_data"], job["building"]
        p = data["proposals"][index]
        b = self.town.scroll.building(bid)
        orc = b.garrison.handler(str(p.get("orc"))) if b is not None else None
        if orc is None:
            raise ConsoleError("That handler is gone")
        repo, demo = self.town.repo_root, self.town.demo
        kind = "hybrid" if p.get("hybrid") else "script"
        candidate = {**orc.to_dict(), "kind": kind, "harness": [], "script": {"path": steward.script_path(bid, orc.id)}}
        subject = fastpath.Subject("agent", orc.name, {"building": bid, "orc": candidate,
                                                       "roads": [r.to_dict() for r in b.roads_of(orc.id)]}, str(p["script"]))
        runner = None if demo else (runners.FASTPATH_RUNNER or fastpath.light_runner(repo))
        model = str(fastpath.settings(repo).get("fast_model") or "")
        examples = roads.read_examples(repo, bid, orc.id)

        def work():
            verdict = fastpath.review(subject, repo, set(), runner, model)
            if verdict.blocked:
                return verdict, None
            return verdict, steward.replay_script(str(p["script"]), examples, repo, hybrid=bool(p.get("hybrid")))

        def done(job: dict, result) -> None:
            verdict, rep = result
            view = next(x for x in job["view"]["proposals"] if x["index"] == index)
            if rep is None:
                fastpath.log(repo, verdict, "rejected")
                view.update(ready=False, replay="The Council rejected it: " + "; ".join(
                    plain(n.text) for n in verdict.notes if n.severity == "block")[:300])
            else:
                view["replay"] = (f"replay {rep.exact}/{rep.total} exact · agrees {rep.score:.0%}"
                                  + (f" · {rep.escalated} left to the steward" if rep.escalated else ""))
                if not rep.ready:
                    view.update(ready=False, replay=view["replay"] + " — not enough: the rule stays")
                else:
                    fastpath.log(repo, verdict, "approved")
                    p.update(reviewed=True, replay={**dataclasses.asdict(rep), "ready": True})
                    what = core_buildings.apply_steward(self.town, bid, data, index, by="you")
                    if what is None:
                        view["ready"] = False
                    else:
                        view["applied"] = plain(what)
                        self._saved()
                        self.town.toast(f"{plain(what)} — Revert takes it back", title=f"Steward · {job['title']}")
            job.update(state="ready", text="", _accept=self._apply_proposal)     # last: the page sees it settled

        self._run(job, "The Council reads the script, then it is replayed…", work, done)
        return None

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
                                    runner=steward.runner_for(snapshot.building(bs.id), "redesign", runners.STEWARD_RUNNER))

        def done(job: dict, report: steward.StewardReport) -> None:
            if not report.proposals:
                why = report.error or "; ".join(report.errors[:3]) or "no layout came back"
                job.update(state="failed", error=f"Not redesigned: {why}")
                return
            self._show_report(job, {"ts": "", "cost_usd": report.cost_usd,
                                    "findings": [{"summary": request[:200]}],
                                    "proposals": [p.to_dict() for p in report.proposals]})

        return self._job("redesign", bs.id, "The steward is redrawing the window…", work, done)
