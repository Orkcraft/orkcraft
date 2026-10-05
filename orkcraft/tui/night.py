"""Quiet hours: the Elders' advice on the orks' questions, the orks' own improvements of the camp and their probation, the day's schedule.

A part of `OrkcraftApp` (app.py): its methods run with the app as `self`.
"""
from __future__ import annotations

import contextlib
import datetime as dt

from textual import work

from orkcraft.realm import checkpoint, fastpath, optimize, weekly
from orkcraft.realm.orcs import Alert
from orkcraft.screens import onboarding
from orkcraft.realm import elders, evolution
from orkcraft.screens.changes import ChangesModal
from orkcraft import autonomy
from orkcraft.screens.autonomy import AutonomyStep
from orkcraft import settings

from orkcraft.core import runners
from orkcraft.core.night import Night


class NightMixin:
    def tick_schedule(self) -> None:
        """Every half minute: Shift turns Office on and off, quiet hours begin and end (schedule.py)."""
        self.desktop.apply_schedule()
        self.refresh_hud()
        if self.night.tick(self.desktop.quiet):
            self._elders_morning()
            self.night.morning()
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
        """What the orcs may apply themselves tonight (core/night.py)."""
        return self.night.candidates(self.desktop.machine.autonomy)

    def _evolve_subject(self, c: dict) -> fastpath.Subject:
        """What the Council looks at for one change: the building, the orc or the road as it would be."""
        return self.night.subject(c)

    @staticmethod
    def council_lets(verdict: fastpath.Verdict) -> bool:
        """The Council lets the orcs apply a change themselves: no block, no objection, no Warder warning."""
        return Night.council_lets(verdict)

    def _evolve_consider(self) -> None:
        taken = self.night.next_change(self.desktop.quiet, self.desktop.machine.autonomy,
                                       self.gold_exhausted_quietly())
        if taken is not None:
            self._evolve_work(*taken)

    def gold_exhausted_quietly(self) -> bool:
        return self.treasury.exhausted(quiet=True)

    @work(thread=True, group="evolve")
    def _evolve_work(self, c: dict, subject: fastpath.Subject) -> None:
        runner = runners.FASTPATH_RUNNER or fastpath.light_runner(self.repo_root)
        verdict = fastpath.review(subject, self.repo_root, self._taken_building_ids() - {subject.id}, runner=runner)
        self.call_from_thread(self._evolve_apply, c, verdict)

    def _evolve_apply(self, c: dict, verdict: fastpath.Verdict) -> None:
        """Applied by the orcs only while it is still quiet and the Council let it; else it stays a proposal."""
        if not self.desktop.quiet or not self.council_lets(verdict):
            self.night.changed(False)
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
        self.night.changed(ok)

    def _probation_tick(self, now: dt.datetime | None = None) -> None:
        """Every few minutes: a change on probation with a 👎 or more failures since goes back by
        itself (the operator is told); one that lived through 24 hours is kept."""
        now = now or dt.datetime.now()
        if not self.night.probation_due():
            return
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
        """A restart keeps the advice still to follow and tonight's judged questions (core/night.py)."""
        self.night.restore()

    def elders_state(self) -> str:
        """The lamp on the Town Hall (core/night.py `elders_state`)."""
        return self.night.elders_state(self.roster.alerts, self.desktop.quiet, self.desktop.machine.autonomy)

    def advice_for(self, alert: Alert) -> elders.Decision | None:
        return self.night.advice_for(alert)

    def _elders_consider(self) -> None:
        """One question at a time goes to the Elders: quiet hours, autonomy from 1, budget left."""
        alert = self.night.next_question(self.roster.alerts, self.desktop.quiet, self.desktop.machine.autonomy)
        if alert is not None:
            self._elders_work(alert, self._alert_who_map().get(alert.id, ""))

    @work(thread=True, group="elders")
    def _elders_work(self, alert: Alert, who: str) -> None:
        runner = runners.ELDERS_RUNNER or fastpath.light_runner(self.repo_root)
        decision = elders.judge(alert, runner, elders.limits(self.repo_root)[1])
        self.call_from_thread(self._elders_done, alert, who, decision)

    def _elders_done(self, alert: Alert, who: str, decision: elders.Decision) -> None:
        """The Elders' advice is kept for the operator, or — at ⛓️‍💥 Free orcs, while it is still quiet and the
        same question waits — their key goes to the agent (core/night.py `judged`)."""
        send = self.night.judged(alert, decision, who, self.roster.alerts, self.desktop.quiet,
                                 self.desktop.machine.autonomy)
        if send is not None:
            self.chat.send(alert.ref, send.encode())                    # no focus: they sleep
        self.refresh_roster()
        self._refresh_hall()

    def _elders_morning(self) -> None:
        words = self.night.morning_words(self.roster.alerts)
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
