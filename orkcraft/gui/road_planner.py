"""Listen in words: the receiver's steward reads what the person wants and offers roads to lay
(realm/road_planner.py), as a job (gui/jobs.py), on its own tool and its tier for roads (realm/steward.py). A plain road is laid at once; a road with a rule goes
on to the Recruiter, whose handler the Council reviews before it is hired (gui/recruiter.py).

A part of `Console` (console.py): its methods run with the console as `self`.
"""
from __future__ import annotations

import copy

from orkcraft.core import roads as core_roads
from orkcraft.core import runners
from orkcraft.gui.jobs import ConsoleError, plain
from orkcraft.realm import pipes, road_planner, steward


class RoadPlannerMixin:
    def road_plan(self, args: dict) -> str:
        """{to, from?, prompt, among?}: `from` when the road was drawn from a building, else the planner
        picks the source among the town's buildings (`among`: the ones the person sees)."""
        target = self._spec({"id": args.get("to")})
        source = args.get("from") if isinstance(args.get("from"), str) and args.get("from") else None
        if source is not None and self.town.scroll.building(source) is None:
            raise ConsoleError("No such building")
        prompt = self._text(args, "prompt", road_planner.ORDER_LIMIT)
        if not prompt:
            raise ConsoleError("Say what it should listen to")
        among = [str(x) for x in args["among"]] if isinstance(args.get("among"), list) else None
        tgt, sources = core_roads.contract(self.town, target.id, source, among)
        self._budget()
        snapshot = copy.deepcopy(self.town.scroll)
        runner = steward.runner_for(snapshot.building(target.id), "roads", runners.ROAD_RUNNER)
        work = lambda: road_planner.plan(prompt, tgt, sources, snapshot, runner)  # noqa: E731
        return self._job("road", target.id, f"{plain(target.title)}'s steward is looking for the road…", work,
                         lambda job, result: self._road_planned(job, result, source or ""))

    def _road_planned(self, job: dict, result: road_planner.RoadPlan, source: str) -> None:
        if not result.ok and not result.missing:
            job.update(state="failed", error=f"No road found: {result.error or 'the steward gave none'}")
            return
        titles = {b.id: plain(b.title) for b in self.town.scroll.buildings}
        job["view"] = {
            "from": source,
            "options": [{"index": i, "say": o.say, "from": titles.get(o.source, o.source),
                         "event": plain(pipes.label(o.event.partition("#")[0])) + (
                             f" · {o.event.partition('#')[2]}" if "#" in o.event else ""),
                         "match": o.match, "rule": o.rule} for i, o in enumerate(result.options)],
            "missing": result.missing,
            "cost": f"${result.cost_usd:.2f}" if result.cost_usd is not None else "",
        }
        job.update(state="ready", text="", _plan=result, _accept=self._lay_planned)

    def _lay_planned(self, job: dict, args: dict) -> str:
        """The person picked an option: a plain road is laid; a rule goes to the Recruiter (a new job)."""
        options = job["_plan"].options
        index = args.get("index")
        if not isinstance(index, int) or not 0 <= index < len(options):
            raise ConsoleError("Pick a road")
        o, bid = options[index], job["building"]
        if o.rule:
            self.jobs.pop(job["id"], None)
            return self._recruit(bid, o.rule, road=[(o.source, o.event)])
        road = core_roads.lay(self.town, bid, o.source, o.event, None, match=o.match)
        if road is None:
            raise ConsoleError("The road was refused (see the note)")
        self.jobs.pop(job["id"], None)
        self.host.on_change()
        return f"{bid}:{road.id}"
