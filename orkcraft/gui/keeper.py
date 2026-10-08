"""Lake and the keeper in the console: what every type calls — a document opened in the town's Lake
window (gui/views/lake.py) and a building's keeper asked in plain words (core/keeper.py), as a job.

A part of `Console` (console.py): its methods run with the console as `self`.
"""
from __future__ import annotations

import copy
from typing import Any, Callable

from orkcraft.core import keeper, runners
from orkcraft.gui import markdown
from orkcraft.gui.jobs import ConsoleError, plain
from orkcraft.gui.views import ActError
from orkcraft.gui.views import lake as lake_view
from orkcraft.realm import steward


class KeeperMixin:
    def lake_open(self, args: dict) -> str:
        """A document opened in the town's Lake window, in a tab (gui/views/lake.py): the tab's id."""
        return self._lake_call(lambda a: lake_view.open_doc(self.town, a))(args)

    @staticmethod
    def _lake_call(fn: Callable[[dict], Any]) -> Callable[[dict], Any]:
        def call(args: dict) -> Any:
            try:
                return fn(args)
            except ActError as e:
                raise ConsoleError(str(e)) from None
        return call

    def keeper_ask(self, args: dict) -> str:
        """A building's keeper asked in plain words (core/keeper.py): its proposal comes back as a job — the
        change line by line and its answer (on a Lake selection, about it) — and Apply takes it."""
        bs = self._spec(args)
        request = self._text(args, "request")
        if not request:
            raise ConsoleError("Say what the building should do")
        spec = self.town.custom_specs.get(bs.id)
        if spec is None:
            raise ConsoleError(f"{bs.title} keeps no rules or settings for a keeper")
        if self.town.demo and runners.KEEPER_RUNNER is None:
            raise ConsoleError("The demo's keeper calls no model — run without --demo to ask it")
        self._budget()
        return self._keeper_job(bs.id, spec, request, keeper.selection_of(args.get("selection")))

    def keeper_wake(self, wake) -> bool:
        """A script-first building's ork woke (core/wakes.py): its keeper asked in the town's words, the same job
        as a keeper asked by hand, with a toast. False when it cannot run now — the budget is spent, or a wake of
        the building is still open in its console — and it is due again at the next look."""
        if any(j.get("_wake") and j["building"] == wake.building for j in self.jobs.values()):
            return False
        title = self.town.title_of(wake.building)
        what = "an error" if wake.why == "error" else "a 👎"
        spec = self.town.custom_specs.get(wake.building)
        if spec is None or (self.town.demo and runners.KEEPER_RUNNER is None):
            self.town.toast(f"its ork woke on {what}: {wake.detail}"[:300], title=title, severity="warning")
            return True                        # no settings to change, or the demo: logged and told, no model
        if self.host.treasury.exhausted(quiet=True):
            return False
        jid = self._keeper_job(wake.building, copy.deepcopy(spec), wake.request, None,
                               woke=f"Woke on {what}: {wake.detail}"[:300])
        self.jobs[jid]["_wake"] = True
        self.town.toast(f"its ork woke on {what} — a fix waits in its console", title=title, severity="warning")
        return True

    def _keeper_job(self, building_id: str, spec: dict, request: str, selection: dict | None, woke: str = "") -> str:
        """Its keeper asked (a thread); its proposal comes back as a ready job: the diff, its answer, Apply."""
        repo, spec, snapshot = self.town.repo_root, copy.deepcopy(spec), copy.deepcopy(self.town.scroll)
        others = set(self.town.custom_specs) - {building_id}

        def work() -> keeper.Proposal:
            return keeper.ask(repo, spec, snapshot, building_id, request, selection=selection, existing_ids=others,
                              runner=steward.runner_for(snapshot.building(building_id), "keeper", runners.KEEPER_RUNNER))

        def done(job: dict, p: keeper.Proposal) -> None:
            if p.error:
                job.update(state="failed", error=f"The keeper could not: {plain(p.error)}"[:500])
                return
            job["view"] = {"request": woke or request, "selection": selection, "kind": p.kind, "why": plain(p.why),
                           "answer": markdown.render(p.answer) if p.answer else "", "attempts": p.attempts,
                           "diff": p.diff(keeper.subject_of(spec)) if p.changes else [],
                           "cost": f"${p.cost_usd:.2f}" if p.cost_usd is not None else "", "woke": bool(woke)}
            job.update(state="ready", text="", _proposal=p, _request=request, _accept=self._keeper_apply)

        return self._job("keeper", building_id, "Its ork woke: the keeper is looking…" if woke else "The keeper is writing it…",
                         work, done)

    def _keeper_apply(self, job: dict, args: dict) -> str:
        p: keeper.Proposal = job["_proposal"]
        if not p.changes:
            raise ConsoleError("Nothing to change")
        problems = keeper.apply(self.town, job["building"], p, job["_request"])
        if problems:
            raise ConsoleError("\n".join(problems))
        self.jobs.pop(job["id"], None)
        self.host.on_change()
        self.town.toast(f"new {p.kind} — Revert takes it back", title=f"Keeper · {job['title']}")
        return p.kind
