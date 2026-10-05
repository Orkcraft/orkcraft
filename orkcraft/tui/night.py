"""Quiet hours: the Elders' advice on the orks' questions, the orks' own improvements of the camp and their probation, the day's schedule.

A part of `OrkcraftApp` (app.py): its methods run with the app as `self`.
"""
from __future__ import annotations

import contextlib
import dataclasses
import datetime as dt
import json
import time

from textual import work

from orkcraft.realm import checkpoint, fastpath, optimize, weekly, steward
from orkcraft.realm.orcs import Alert
from orkcraft.screens import onboarding
from orkcraft.realm import elders, evolution
from orkcraft.screens.changes import ChangesModal
from orkcraft import autonomy
from orkcraft.screens.autonomy import AutonomyStep
from orkcraft import settings

from orkcraft.core import runners
from orkcraft.tui.base import PROBATION_CHECK_S


class NightMixin:
    def tick_schedule(self) -> None:
        """Every half minute: Shift turns Office on and off, quiet hours begin and end (schedule.py)."""
        self.desktop.apply_schedule()
        self.refresh_hud()
        quiet = self.desktop.quiet
        if quiet and self._quiet_since is None:
            self._quiet_since = dt.datetime.now().isoformat(timespec="seconds")
        elif not quiet and self._quiet_since is not None:
            self._elders_morning()
            self._quiet_since, self._elders_count, self._evolve_count = None, 0, 0
            self.show_changes(only_unseen=True)                  # what the orcs changed overnight
        self._elders_consider()
        self._evolve_consider()
        self._probation_tick()

    @contextlib.contextmanager
    def hushed(self):
        """The orcs at work in quiet hours: no toasts and no dialogs — the ledger and the list tell."""
        if self._hushed:
            yield
            return
        self._hushed = True
        self.notify = lambda *a, **k: None                       # type: ignore[method-assign]
        try:
            yield
        finally:
            del self.notify
            self._hushed = False

    def _evolve_candidates(self) -> list[dict]:
        """What the daily proposal, the latest weekly report and the stewards left, that this level
        lets the orcs apply themselves and that was not applied or tried yet."""
        level, done = self.desktop.machine.autonomy, evolution.applied_keys(self.repo_root)
        out: list[dict] = []
        for p in optimize.pending(self.repo_root):
            out.append({"key": p.id, "change": p.action, "source": "daily", "building": p.building, "proposal": p})
        report = weekly.latest(self.repo_root)
        if report is not None and dt.datetime.fromisoformat(report.ts) > dt.datetime.now() - dt.timedelta(days=7):
            for item in report.items:
                if item.applicable and item.n not in report.applied:
                    key = (f"w{report.ts[:10]}-{item.n}" if item.change in optimize.ACTIONS
                           else f"weekly:{report.ts}:{item.n}")
                    out.append({"key": key, "change": item.change, "source": "weekly", "building": item.building,
                                "report": report, "item": item})
        for b in self.scroll.buildings:
            data = steward.load_report(self.repo_root, b.id)
            for i, prop in enumerate((data or {}).get("proposals") or []):
                replay = prop.get("replay") or {}
                if prop.get("type") == "demote" and not replay.get("ready"):
                    continue
                out.append({"key": f"steward:{b.id}:{data.get('ts', '')}:{i}", "change": str(prop.get("type")),
                            "source": "steward", "building": b.id, "data": data, "index": i})
        return [c for c in out if evolution.allowed(c["change"], level)
                and c["key"] not in done and c["key"] not in self._evolve_tried]

    def _evolve_subject(self, c: dict) -> fastpath.Subject:
        """What the Council looks at for one change: the building, the orc or the road as it would be."""
        bid = c["building"]
        if c["source"] == "steward":
            prop = c["data"]["proposals"][c["index"]]
            if c["change"] in ("filter", "new_road"):
                return fastpath.Subject("road", bid, {"source": prop.get("from") or bid, "target": bid,
                                                      "event": prop.get("event", ""), "filter": prop.get("filter") or {}})
            b = self.scroll.building(bid)
            orc = b.garrison.handler(str(prop.get("orc"))) if b is not None else None
            data = {k: v for k, v in dataclasses.asdict(orc).items() if v is not None} if orc is not None else {"id": str(prop.get("orc"))}
            data.update({"kind": "chain", "chain": prop.get("chain") or []} if c["change"] == "demote"
                        else {"run": prop.get("run") or {}})
            return fastpath.Subject("agent", bid, {"orc": data})
        if c["source"] == "weekly" and c["change"] == "add_building":
            spec = weekly.new_spec(c["item"])
            return fastpath.Subject("building", spec["id"], spec)
        if c["source"] == "weekly" and c["change"] == "set_config":
            spec = dict(self.custom_specs.get(bid) or {})
            spec["config"] = {**(spec.get("config") or {}), str(c["item"].data["key"]): c["item"].data.get("value")}
            return fastpath.Subject("building", bid, spec)
        p = c.get("proposal")
        if p is None:
            item = c["item"]
            p = optimize.Proposal(c["key"], c["report"].ts, bid, item.change, str(item.data.get("target")),
                                  item.before, item.after, item.why)
            c["proposal"] = p
        if p.action == "script":
            return fastpath.Subject("building", bid, dict(self.custom_specs.get(bid) or {}), script=p.after)
        if p.target.startswith("orc:"):
            b = self.scroll.building(bid)
            orc = b.garrison.handler(p.target[4:]) if b is not None else None
            data = {k: v for k, v in dataclasses.asdict(orc).items() if v is not None} if orc is not None else {"id": p.target[4:]}
            data.update({"kind": "chain", "chain": json.loads(p.after), "orders": ""} if p.action == "chain"
                        else {"orders": p.after})
            return fastpath.Subject("agent", bid, {"orc": data})
        spec = dict(self.custom_specs.get(bid) or {})
        key = "steward_prompt" if p.target == "steward" else "orders"
        spec["config"] = {**(spec.get("config") or {}), key: p.after}
        return fastpath.Subject("building", bid, spec)

    @staticmethod
    def council_lets(verdict: fastpath.Verdict) -> bool:
        """The Council lets the orcs apply a change themselves: no block, no objection, no Warder warning."""
        return not verdict.blocked and not verdict.objections and not verdict.of("warder")

    def _evolve_consider(self) -> None:
        if (self.demo or self._evolve_busy or not self.desktop.quiet or self._evolve_count >= evolution.MAX_PER_NIGHT
                or self.desktop.machine.autonomy < 2 or self.gold_exhausted_quietly()):
            return
        candidates = self._evolve_candidates()
        if not candidates:
            return
        c = candidates[0]
        self._evolve_tried.add(c["key"])
        try:
            subject = self._evolve_subject(c)
        except (KeyError, ValueError, TypeError, AttributeError):
            return
        self._evolve_busy = True
        self._evolve_work(c, subject)

    def gold_exhausted_quietly(self) -> bool:
        return self.treasury.exhausted(quiet=True)

    @work(thread=True, group="evolve")
    def _evolve_work(self, c: dict, subject: fastpath.Subject) -> None:
        runner = runners.FASTPATH_RUNNER or fastpath.light_runner(self.repo_root)
        verdict = fastpath.review(subject, self.repo_root, self._taken_building_ids() - {subject.id}, runner=runner)
        self.call_from_thread(self._evolve_apply, c, verdict)

    def _evolve_apply(self, c: dict, verdict: fastpath.Verdict) -> None:
        """Applied by the orcs only while it is still quiet and the Council let it; else it stays a proposal."""
        self._evolve_busy = False
        if not self.desktop.quiet or not self.council_lets(verdict):
            return
        with self.hushed():
            if c["source"] == "steward":
                ok = self.apply_steward_proposal(c["building"], c["data"], c["index"], by="orcs") is not None
            elif c["source"] == "daily" or c["change"] in optimize.ACTIONS:
                ok = self.apply_proposal(c["proposal"], kind="auto-improve" if c["source"] == "daily" else "weekly")
                if ok and c["source"] == "weekly":
                    c["report"].applied = sorted(set(c["report"].applied) | {c["item"].n})
                    weekly.save(self.repo_root, c["report"])
            else:
                ok = bool(self.apply_weekly(c["report"], [c["item"].n]))
        if ok:
            self._evolve_count += 1

    def _probation_tick(self, now: dt.datetime | None = None) -> None:
        """Every few minutes: a change on probation with a 👎 or more failures since goes back by
        itself (the operator is told); one that lived through 24 hours is kept."""
        now = now or dt.datetime.now()
        if self.demo or (self._probation_at and time.monotonic() - self._probation_at < PROBATION_CHECK_S):
            return
        self._probation_at = time.monotonic()
        reverted = []
        for change in evolution.on_probation(self.repo_root):
            reason = evolution.verdict(self.repo_root, change, now)
            if reason is None:
                if now >= change.until:
                    change.status = "kept"
                    evolution.update(self.repo_root, change)
                continue
            if self.revert_change(change, f"probation: {reason}"):
                reverted.append(change)
        if reverted:
            names = ", ".join(f"{self._title_of(c.building)} ({c.change})" for c in reverted[:3])
            self.notify(f"{names} — {reverted[0].note}", title=f"↩ {len(reverted)} change(s) by the orks taken back",
                        severity="warning", timeout=15)
            if not self.desktop.quiet:
                self.show_changes(only_unseen=True)

    def revert_change(self, change: evolution.Change, note: str, seen: bool = False) -> bool:
        """Take one change back — only when it is still its building's last checkpoint, so nothing
        newer is lost; otherwise it is marked stuck and the operator decides (Z on the building)."""
        last = checkpoint.history(self.repo_root, change.building, 1)
        if not change.sha or not last or last[0].sha != change.sha:
            change.status, change.note, change.seen = "stuck", f"{note} — changed since, Z on it decides", seen
            evolution.update(self.repo_root, change)
            return False
        with self.hushed():
            ok = self.revert_building(change.building)
        change.status, change.note, change.seen = ("reverted" if ok else "stuck"), note, seen
        evolution.update(self.repo_root, change)
        return ok

    def show_changes(self, only_unseen: bool = False) -> None:
        """🧾 The list of what the orcs changed: after quiet hours, after a probation revert, F10."""
        changes = evolution.unseen(self.repo_root) if only_unseen else \
            [c for c in evolution.load(self.repo_root) if c.by == "orcs"][-40:][::-1]
        if only_unseen and not changes:
            return
        titles = {c.building: self._title_of(c.building) for c in changes}

        def done(picked: str | None) -> None:
            evolution.mark_seen(self.repo_root)
            if picked:
                change = next((c for c in evolution.load(self.repo_root) if c.id == picked), None)
                if change is not None and change.status in ("probation", "kept", "stuck"):
                    if self.revert_change(change, "taken back by you", seen=True):
                        self.notify(f"{titles.get(change.building, change.building)}: {change.summary}",
                                    title="↩ Taken back")

        self.push_screen(ChangesModal(changes, titles), done)

    @staticmethod
    def elders_mark(alert: Alert) -> str:
        return elders.mark(alert)

    def _elders_restore(self) -> None:
        """A restart keeps what the log knows: the advice still to follow, and tonight's judged questions
        (so they are not judged, paid for and counted twice)."""
        if self.demo:
            return
        night = elders.restore(self.repo_root, self._quiet_since)
        self.advice.update(night.advice)
        self._elders_seen |= night.seen
        self._elders_count = max(self._elders_count, night.count)

    def elders_state(self) -> str:
        """The lamp on the Town Hall: `advice` (some waits for you), `watch` (quiet hours, they read the
        questions), `rest` (by day), `off` (autonomy ⛓️ Ask me), `full` (tonight's questions are used up)."""
        if any(self.advice_for(a) is not None for a in self.roster.alerts):
            return "advice"
        if not autonomy.advises(self.desktop.machine.autonomy):
            return "off"
        if not self.desktop.quiet:
            return "rest"
        return "full" if self._elders_count >= elders.limits(self.repo_root)[0] else "watch"

    def advice_for(self, alert: Alert) -> elders.Decision | None:
        d = self.advice.get(self.elders_mark(alert))
        return d if d is not None and d.advised else None

    def _elders_consider(self) -> None:
        """One question at a time goes to the Elders: quiet hours, autonomy from 1, budget left."""
        if (self.demo or self._elders_busy or not self.desktop.quiet
                or not autonomy.advises(self.desktop.machine.autonomy)
                or self._elders_count >= elders.limits(self.repo_root)[0]):
            return
        budget = self.scroll.budget.gold_session_limit_usd
        if budget > 0 and self.snapshot.spent_usd >= budget:
            return
        pending = [a for a in self.roster.alerts if elders.qualifies(a) and self.elders_mark(a) not in self._elders_seen]
        if not pending:
            return
        alert = pending[0]
        self._elders_seen.add(self.elders_mark(alert))
        self._elders_busy = True
        self._elders_count += 1
        self._elders_work(alert, self._alert_who_map().get(alert.id, ""))

    @work(thread=True, group="elders")
    def _elders_work(self, alert: Alert, who: str) -> None:
        runner = runners.ELDERS_RUNNER or fastpath.light_runner(self.repo_root)
        decision = elders.judge(alert, runner, elders.limits(self.repo_root)[1])
        self.call_from_thread(self._elders_done, alert, who, decision)

    def _elders_done(self, alert: Alert, who: str, decision: elders.Decision) -> None:
        """The Elders' advice is kept for the operator. At ⛓️‍💥 Free orcs (autonomy.answers) they also
        answer: their key goes to the agent — only while it is still quiet and the very same question
        still waits, so an answer never lands on a question that changed meanwhile, and never when the
        Warder flagged the screen (⚠: that advice is the operator's to follow)."""
        self._elders_busy = False
        mark = self.elders_mark(alert)
        sent = False
        if (decision.advised and not decision.warn and autonomy.answers(self.desktop.machine.autonomy)
                and self.desktop.quiet and any(self.elders_mark(a) == mark for a in self.roster.alerts)):
            key = decision.key or ""
            self.chat.send(alert.ref, (key if key.isdigit() else f"{key}\r").encode())   # no focus: they sleep
            sent = True
        else:
            self.advice[mark] = decision
        elders.log(self.repo_root, alert, decision, who, sent=sent)
        self.refresh_roster()
        self._refresh_hall()

    def _elders_morning(self) -> None:
        answered = [r for r in elders.since(self.repo_root, self._quiet_since or "") if r.get("sent")]
        waiting = [a for a in self.roster.alerts if self.advice_for(a) is not None]
        words = []
        if answered:
            words.append(f"{len(answered)} question(s) answered by the Elders — the Town Hall lists them")
        if waiting:
            words.append(f"{len(waiting)} have their advice — ! opens them, a follows it, A for all")
        if words:
            self.notify(".\n".join(words) + ".", title="🏛 While you were away, the Elders", timeout=15)

    def follow_advice(self, alert: Alert) -> bool:
        """The operator follows the Elders' advice on one question: their key, sent as their own answer."""
        d = self.advice_for(alert)
        if d is None or d.key is None:
            return False
        self.answer_alert(alert, d.key)
        return True

    def open_autonomy(self) -> None:
        """F10 → 🏛 Orc autonomy: the slider and the guide for the agents' own settings."""
        machine = self.desktop.machine
        tools_ = tuple(t for t, c in machine.tools.items() if c.enabled) or ("claude", "agy")

        def done(result: dict | str | None) -> None:
            if isinstance(result, dict):
                machine.autonomy = int(result.get("autonomy", machine.autonomy))
                settings.save(machine)
                lvl = autonomy.LEVELS[machine.autonomy]
                self.notify(f"❓ {lvl.questions}\n🔧 {lvl.improves}", title=f"{lvl.icon} {lvl.title}")

        self.push_screen(AutonomyStep(machine.autonomy, tools_, standalone=True), done)

    def open_day(self) -> None:
        """F10 → 🕰 Your day: the mode, the quiet hours and the office hours, on the day bar."""
        def done(result: dict | None) -> None:
            if result:
                self.apply_day(result)

        self.push_screen(onboarding.ModeStep(self.desktop.machine, standalone=True), done)

    def apply_day(self, result: dict) -> None:
        machine = self.desktop.machine
        machine.quiet, machine.office = result.get("quiet"), result.get("office") or machine.office
        machine.office_days = tuple(result.get("office_days", machine.office_days))
        settings.save(machine)
        self.desktop.set_mode(result.get("mode", machine.mode))
        self.desktop.apply_schedule()
        self.refresh_hud()
