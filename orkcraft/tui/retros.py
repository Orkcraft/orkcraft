"""Retros: the Building retro's proposals, the Town retro's report and survey, the Peon's cleanup.

A part of `OrkcraftApp` (app.py): its methods run with the app as `self`.
"""
from __future__ import annotations

import copy
import functools
import datetime as dt

from orkcraft import scroll
from orkcraft.realm import audit, checkpoint, fastpath, feedback, housekeeping, optimize, weekly, builders, steward
from orkcraft.screens.proposal_modal import ProposalModal
from orkcraft.screens.retro_survey import RetroSurveyModal
from orkcraft.screens.weekly_modal import WeeklyReportModal
from orkcraft.realm import evolution, pressure, retro
from orkcraft.screens.dialogs import Confirm
from orkcraft.realm import workshop

from orkcraft.core import buildings as core_buildings
from orkcraft.core import runners


class RetrosMixin:
    def _daemon_chores(self) -> list[housekeeping.Chore]:
        out = []
        for w in self.desktop.windows:
            view = self._custom_view(w.window_id)
            if w.hidden and getattr(view, "hook", None) is not None:
                out.append(housekeeping.Chore("daemon", w.window_id, "a demolished building still listens (webhook)"))
        return out

    def cleanup(self, confirm: bool = True) -> list[str]:
        """F10 → 🧹: what piled up, shown first; Enter cleans it."""
        chores = housekeeping.scan(self.repo_root, {b.id for b in self.scroll.buildings}) + self._daemon_chores()
        if not chores:
            self.notify("nothing to clean", title="⛏ Peon")
            return []

        def go(yes: bool | None = True) -> list[str]:
            if not yes:
                return []
            done = housekeeping.clean(self.repo_root, [c for c in chores if c.kind != "daemon"])
            for c in chores:
                if c.kind == "daemon":
                    view = self._custom_view(c.path)
                    if view is not None and view.hook is not None:
                        view.hook.stop()
                        view.hook = None
                        done.append(f"stopped the webhook of {c.path}")
            self.notify("\n".join(done[:6]) + (f"\n… {len(done) - 6} more" if len(done) > 6 else ""), title="⛏ Cleaned")
            return done

        if not confirm:
            return go()
        listing = "\n".join(f"· {c.detail}: {c.path}" for c in chores[:12])
        self.push_screen(Confirm(f"🧹 Clean {len(chores)} thing(s)?", listing), go)
        return []

    def _maybe_optimize(self, now: dt.datetime) -> None:
        if self.demo or self.gold_exhausted():
            return
        expr = str(fastpath.settings(self.repo_root).get("optimize_at") or "")
        if expr and steward.due(expr, optimize.last_run(self.repo_root), now):
            optimize.mark_run(self.repo_root, now)
            self.optimize_now(interactive=False)

    def optimize_now(self, interactive: bool = True) -> bool:
        """Today's hungriest building the operator is not happy with → the Council's proposal (in a
        thread). False when there is nothing to propose."""
        goals = {b.id: b.aim for b in self.scroll.buildings if not b.demolished}
        cand = optimize.leader(self.repo_root, None, *self._quota_reads(), goals=goals)
        if cand is None:
            if interactive:
                self.notify("nothing to improve: the heaviest buildings are liked, and no 💎 one is disliked or failing",
                            title="🔧 Building retro")
            return False
        spec = self.custom_specs.get(cand.building)
        ps = optimize.parts(self.scroll, spec, cand.building, self.repo_root)
        if not ps:
            if interactive:
                self.notify(f"{self._title_of(cand.building)} is due, but has no model prompt to change",
                            title="🔧 Building retro")
            return False
        cfg = (spec or {}).get("config") or {}
        mocks = workshop.load_blueprint(self.repo_root, cand.building).get("mocks") or []
        runtime = str(cfg.get("runtime") or "python")
        if interactive:
            aim = cand.goal if cand.goal == (goals.get(cand.building) or "balance") else \
                f"{goals.get(cand.building)}→{cand.goal} (the limit is tight)"
            self.notify(f"the Council looks at {self._title_of(cand.building)} · {aim} · {cand.reason}",
                        title="🔧 Building retro")

        def _worker() -> None:
            result = optimize.propose(self.repo_root, cand, ps, runners.OPTIMIZE_RUNNER or builders.main_runner, runtime, mocks)
            self.call_from_thread(self._on_proposal, result, interactive)

        self.run_worker(_worker, thread=True, name="council_optimize")
        return True

    def _on_proposal(self, result: optimize.Result, interactive: bool) -> None:
        if result.proposal is None:
            if interactive:
                why = result.error or "; ".join(result.problems[:3]) or "no proposal"
                self.notify(why, title="🔧 The Council found nothing it could prove", severity="warning")
            return
        optimize.save(self.repo_root, result.proposal)
        self._refresh_hall()
        if len(self.screen_stack) > 1:              # the operator is busy in a dialog: leave it waiting
            self.notify(f"a proposal for {self._title_of(result.proposal.building)} waits — F10 → Building retro",
                        title="🔧 Building retro")
            return
        self.show_proposal(result.proposal)

    def open_proposals(self) -> None:
        waiting = optimize.pending(self.repo_root)
        if waiting:
            self.show_proposal(waiting[0])
        else:
            self.optimize_now(interactive=True)

    def show_proposal(self, p: optimize.Proposal) -> None:
        def done(choice: str | None) -> None:
            if choice == "apply":
                self.apply_proposal(p)
            elif choice == "dismiss":
                p.status = "dismissed"
                optimize.save(self.repo_root, p)
                self._refresh_hall()

        self.push_screen(ProposalModal(p, self._title_of(p.building)), done)

    def apply_proposal(self, p: optimize.Proposal, kind: str = "auto-improve") -> bool:
        """The change, a checkpoint `<kind>(<id>)` (Z takes it back), the proposal marked applied."""
        return core_buildings.apply_proposal(self.core, p, kind, by="orcs" if self._hushed else "you")

    def _maybe_weekly(self, now: dt.datetime) -> None:
        if self.demo or self.gold_exhausted():
            return
        expr = str(fastpath.settings(self.repo_root).get("weekly_at") or "")
        if expr and steward.due(expr, weekly.last_run(self.repo_root), now):
            weekly.mark_run(self.repo_root, now)
            self.weekly_audit_now(interactive=False)

    def open_weekly(self) -> None:
        report = weekly.latest(self.repo_root)
        fresh = report is not None and dt.datetime.fromisoformat(report.ts) > dt.datetime.now() - dt.timedelta(days=7)
        if fresh and any(i.applicable and i.n not in report.applied for i in report.items):
            self.show_weekly(report)
        else:
            self.weekly_audit_now(interactive=True)

    def weekly_audit_now(self, interactive: bool = True) -> None:
        """The heavy model over the whole camp (in a thread), then the report with checkboxes."""
        model = str(fastpath.settings(self.repo_root).get("weekly_model") or "opus")
        runner = runners.WEEKLY_RUNNER or functools.partial(builders.main_runner, model=model)
        snapshot, specs = copy.deepcopy(self.scroll), copy.deepcopy(self.custom_specs)
        rules = audit.run(self.repo_root, self.scroll, dict(self.custom_specs), self.snapshot.spent_usd,
                          self.scroll.budget.gold_session_limit_usd)
        self.notify(f"{model} looks over the camp — the report follows", title="🗓 Town retro")

        def _worker() -> None:
            result = weekly.run(self.repo_root, snapshot, specs, runner, model, rules)
            self.call_from_thread(self._on_weekly, result, interactive)

        self.run_worker(_worker, thread=True, name="weekly_audit")

    def _on_weekly(self, result: weekly.Result, interactive: bool) -> None:
        if result.report is None:
            self.notify(result.error or "no report", title="🗓 Town retro failed", severity="warning")
            return
        if len(self.screen_stack) > 1:
            self.notify("the Town retro's report waits — F10 → Town retro", title="🗓 Town retro")
            return
        self.show_weekly(result.report)

    def show_weekly(self, report: weekly.Report) -> None:
        """The Town retro: first the survey, when nothing was rated this week (realm/retro.py), then the report."""
        def done(picked: list[int] | None) -> None:
            if picked:
                self.apply_weekly(report, picked)

        def report_now(answers: list | None = None) -> None:
            if answers:
                self.rate_survey(answers)
            self.push_screen(WeeklyReportModal(report), done)

        if report.surveyed:
            report_now()
            return
        report.surveyed = True
        weekly.save(self.repo_root, report)
        limits, subs = self._quota_reads()
        samples = retro.pick(self.repo_root, self.scroll, pressure.measure(self.repo_root, limits, providers=subs)) \
            if retro.needed(self.repo_root) else []
        if not samples:
            report_now()
            return
        self.push_screen(RetroSurveyModal(samples, {s.building: self._title_of(s.building) for s in samples}),
                         report_now)

    def rate_survey(self, answers: list[tuple[retro.Sample, str]]) -> None:
        """The survey's 👍 / 👎, each on the very result it showed."""
        good = bad = 0
        for sample, kind in answers:
            if kind == "good":
                feedback.like(self.repo_root, sample.building, sample.as_output())
                good += 1
            elif kind in feedback.KINDS:
                feedback.dislike(self.repo_root, self.scroll, sample.building, kind, "the Town retro's survey",
                                 sample.as_output())
                bad += 1
        if good or bad:
            self.notify(f"👍 {good} · 👎 {bad} — the retros will go by them", title="🗓 Town retro")
            self._refresh_hall()

    def apply_weekly(self, report: weekly.Report, picked: list[int]) -> list[int]:
        """Each ticked item, checked again against the camp as it is now, applied as its own
        checkpoint `weekly(<id>)`; then the Town Scroll is saved and the touched daemons restart."""
        done, touched, failed = [], set(), []
        restart = report.restart
        for item in report.items:
            if item.n not in picked or item.n in report.applied:
                continue
            item = weekly.check_item(item, self.repo_root, self.scroll, self.custom_specs)
            if not item.applicable:
                failed.append(f"{item.title}: {'; '.join(item.problems) or 'advice only'}")
                continue
            bid = item.building
            ok = False
            if item.change in optimize.ACTIONS:
                p = optimize.Proposal(f"w{report.ts[:10]}-{item.n}", report.ts, bid, item.change,
                                      str(item.data.get("target")), item.before, item.after, item.why)
                ok = self.apply_proposal(p, kind="weekly")
            elif item.change == "remove_road":
                try:
                    scroll.unsubscribe(self.scroll, bid, str(item.data.get("road")))
                except ValueError as e:
                    failed.append(f"{item.title}: {e}")
                else:
                    self._roads_changed()
                    self.checkpoint("weekly", bid, f"remove road {item.data.get('road')}: {item.why[:60]}")
                    ok = True
            elif item.change == "remove_building":
                w = self.desktop.get_window(bid)
                if w is not None:
                    self.desktop.hide(w)
                    self.desktop.save()
                self.checkpoint("weekly", bid, f"remove: {item.why[:60]}")
                ok, restart = True, True
            elif item.change == "add_building":
                ok = self.raise_spec(weekly.new_spec(item))
                restart = restart or ok
            elif item.change == "set_config":
                spec = self.custom_specs[bid]
                new = dict(spec, config={**(spec.get("config") or {}), str(item.data["key"]): item.data.get("value")})
                problems = core_buildings.set_spec(self.core, bid, new)
                if problems:
                    failed.append(f"{item.title}: {'; '.join(problems)}")
                else:
                    self.checkpoint("weekly", bid, f"set {item.data['key']}: {item.why[:60]}")
                    ok = True
            if ok:
                done.append(item.n)
                touched.add(bid)
                if item.change not in optimize.ACTIONS:    # those are in the ledger already
                    where = weekly.new_spec(item)["id"] if item.change == "add_building" else bid
                    last = checkpoint.history(self.repo_root, where, 1)
                    evolution.record(self.repo_root, evolution.Change(
                        where, item.change, "weekly", item.title[:120], item.why[:200],
                        by="orcs" if self._hushed else "you", sha=last[0].sha if last else "",
                        key=f"weekly:{report.ts}:{item.n}"))
        self.desktop.save()
        for bid in touched:                                   # the daemons pick up what changed
            again = getattr(self._custom_view(bid), "restart", None)
            if again is not None:
                again()
        report.applied = sorted(set(report.applied) | set(done))
        weekly.save(self.repo_root, report)
        self._refresh_hall()
        msg = f"{len(done)} applied" + (f" · {len(failed)} not: " + " | ".join(failed[:3]) if failed else "")
        self.notify(msg, title="🗓 Town retro", severity="warning" if failed else "information")
        if restart and done and not self._hushed:
            self.push_screen(Confirm("🔄 Restart orkcraft now?", "the camp changed its buildings — a fresh start "
                                     "reloads everything (the Town Scroll is saved)"),
                             lambda yes: yes and self.restart_app())
        return done
