"""The steward in the console: W, its watch and its report, and D, a redesign of the building's
window, as jobs (gui/jobs.py); a proposal is applied when the person takes it.

A part of `Console` (console.py): its methods run with the console as `self`.
"""
from __future__ import annotations

import copy

from orkcraft.core import buildings as core_buildings
from orkcraft.core import runners
from orkcraft.design import ui
from orkcraft.gui.jobs import ConsoleError, plain
from orkcraft.realm import builders, steward


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
