"""R in the console: the Recruiter (a description → its handler to look at), then the Council's Fast
Path before it is hired, as jobs (gui/jobs.py).

A part of `Console` (console.py): its methods run with the console as `self`.
"""
from __future__ import annotations

import copy

from orkcraft.core import bus, runners
from orkcraft.gui.jobs import ConsoleError, plain
from orkcraft.realm import builders, fastpath, pipes, recruiter, tiers


class RecruiterMixin:
    def recruit_ask(self, args: dict) -> str:
        """R → a description → the Recruiter (one model call per attempt) → its handler to look at."""
        bs = self._spec(args)
        prompt = self._text(args, "prompt")
        if not prompt:
            raise ConsoleError("Describe what the ork should do")
        return self._recruit(bs.id, prompt)

    def _recruit(self, building_id: str, prompt: str, road: list[tuple[str, str]] | None = None) -> str:
        """`road` [(source, event)]: a road with a rule — the handler is made for exactly those roads."""
        self._budget()
        snapshot, harnesses = copy.deepcopy(self.town.scroll), self.harnesses()
        work = lambda: recruiter.recruit(prompt, snapshot, building_id,  # noqa: E731
                                         runner=runners.RECRUIT_RUNNER or builders.main_runner, road=road,
                                         harnesses=harnesses)
        return self._job("recruit", building_id, "The Recruiter is choosing chain → script → agent…", work,
                         self._recruited)

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
