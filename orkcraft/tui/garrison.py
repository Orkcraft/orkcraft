"""The garrison: the Recruiter, the stewards' watch and proposals, an ork's orders, rating and model.

A part of `OrkcraftApp` (app.py): its methods run with the app as `self`.
"""
from __future__ import annotations

import copy
import datetime as dt
from typing import Any, Callable


from orkcraft import scroll
from orkcraft.scroll import OrcSpec
from orkcraft.realm import fastpath, feedback, builders, chronicles, recruiter, steward
from orkcraft.screens.orc_flow import OrcProgress, RecruitFailed, RecruitPreview, StewardView
from orkcraft.realm.orcs import Trigger, RESIDENT, Orc
from orkcraft.screens.garrison_modal import OrcModelModal
from orkcraft.realm import evolution
from orkcraft.screens.dialogs import TextPrompt
from orkcraft.screens.orders import UnitModal
from orkcraft.realm import tiers
from orkcraft.wm import Window

from orkcraft.core import runners


class GarrisonMixin:
    def on_window_badge_clicked(self, message: Window.BadgeClicked) -> None:
        self.open_unit(message.window)

    def harnesses(self) -> tuple[str, ...]:
        """The agent CLIs this machine runs (onboarding's tools); Claude and agy when none is chosen."""
        enabled = tuple(t for t, c in self.desktop.machine.tools.items() if c.enabled and t in scroll.HARNESSES)
        return enabled or ("claude", "agy")

    def recruit_from_prompt(self, building_id: str, prompt: str, road=None,
                            on_rejected: Callable[[str], Any] | None = None) -> None:
        """R → a description → the Recruiter (one Claude call per attempt, in a thread) → preview."""
        if self.gold_exhausted():
            self.notify("🪙 budget exhausted — the Recruiter costs a Claude call", title="Recruiter", severity="warning")
            return
        snapshot = copy.deepcopy(self.scroll)
        self.push_screen(OrcProgress("🧙 The Recruiter is choosing chain → script → agent…"))

        def _worker() -> None:
            result = recruiter.recruit(prompt, snapshot, building_id, runner=runners.RECRUIT_RUNNER or builders.claude_runner,
                                       road=road, harnesses=self.harnesses())
            self.call_from_thread(self._on_recruited, building_id, prompt, result, on_rejected)

        self.run_worker(_worker, thread=True, name="recruiter")

    def _on_recruited(self, building_id: str, prompt: str, result: recruiter.RecruitResult,
                      on_rejected: Callable[[str], Any] | None = None) -> None:
        if isinstance(self.screen, OrcProgress):
            self.screen.dismiss(None)
        spec = self.scroll.building(building_id)
        title = spec.title if spec else building_id
        if not result.ok:
            why = result.error or "; ".join(result.attempts[-1].errors[:2] if result.attempts else []) or "no handler"
            self.push_screen(RecruitFailed(result), lambda _: on_rejected and on_rejected(f"the Recruiter failed: {why}"))
            return
        titles = {b.id: f"{b.icon} {b.title}".strip() for b in self.scroll.buildings}

        def done(ok: bool | None) -> None:
            if ok:
                subject = fastpath.Subject("agent", str((result.orc or {}).get("name") or "orc"),
                                           {"building": building_id, "orc": result.orc, "roads": result.roads},
                                           result.script_source)
                self.council_gate(subject, hire, on_rejected=(lambda why: on_rejected(f"the Council: {why}"))
                                  if on_rejected else None)
            elif on_rejected:
                on_rejected("you declined the handler — try another prompt")

        def hire() -> None:
            try:
                orc = recruiter.apply(self.scroll, building_id, result, self.repo_root)
            except (ValueError, OSError) as e:
                self.notify(str(e), title="Recruiter", severity="error")
                return
            if orc.script is not None:          # the operator saw it and the Council passed it
                orc.script = {**orc.script, "reviewed": True}
                orc.status = "idle"
            self._roads_changed()
            self.refresh_roster()
            try:
                chronicles.record(self.repo_root, self.scroll, building_id, "orc_recruited", orc=orc.name)
            except OSError:
                pass
            self.notify(f"{orc.avatar} {orc.name} ({orc.kind}) joined {title}", title="Recruiter")

        self.push_screen(RecruitPreview(title, result, titles), done)

    def watch_building(self, building_id: str, interactive: bool = False) -> None:
        """The steward's watch in a thread: free metrics, a model only when there are findings."""
        if building_id in self._watching:
            return
        self._watching.add(building_id)
        snapshot = copy.deepcopy(self.scroll)
        carts, runs = list(self.roads.carts), list(self.roads.runs)
        budget_ok = not self.gold_exhausted()
        if interactive:
            self.push_screen(OrcProgress("🔎 The steward is looking at the building…"))

        def _worker() -> None:
            report = steward.watch(self.repo_root, snapshot, building_id, carts=carts, runs=runs,
                                   runner=runners.STEWARD_RUNNER or builders.claude_runner, budget_ok=budget_ok)
            try:
                steward.save_report(self.repo_root, report)
            except OSError:
                pass
            self.call_from_thread(self._on_watched, building_id, report, interactive)

        self.run_worker(_worker, thread=True, name=f"steward-{building_id}")

    def _on_watched(self, building_id: str, report: steward.StewardReport, interactive: bool) -> None:
        self._watching.discard(building_id)
        if isinstance(self.screen, OrcProgress):
            self.screen.dismiss(None)
        try:
            chronicles.record(self.repo_root, self.scroll, building_id, "steward_report",
                              findings=len(report.findings), proposals=len(report.proposals))
        except OSError:
            pass
        spec = self.scroll.building(building_id)
        title = spec.title if spec else building_id
        if interactive:
            self.open_steward_report(building_id)
        elif report.findings:
            self.notify(f"{len(report.findings)} finding(s), {len(report.proposals)} proposal(s) — select its ★ ork, W",
                        title=f"🔎 Steward · {title}")
        self.refresh_roster()

    def open_steward_report(self, building_id: str) -> None:
        data = steward.load_report(self.repo_root, building_id)
        if data is None:
            return
        spec = self.scroll.building(building_id)
        title = spec.title if spec else building_id

        def done(index: int | None) -> None:
            if index is None:
                return
            what = self.apply_steward_proposal(building_id, data, index, by="you")
            if what is None:
                return
            self.notify(f"✅ {what} — Z on it takes it back", title=f"Steward · {title}")

        self.push_screen(StewardView(title, data), done)

    def apply_steward_proposal(self, building_id: str, data: dict, index: int, by: str) -> str | None:
        """One steward proposal applied, with its own checkpoint (Z takes it back) and a line in the
        ledger of changes (realm/evolution.py). None when it could not be applied."""
        proposal = data["proposals"][index]
        try:
            what = steward.apply_proposal(self.scroll, building_id, proposal)
        except (ValueError, TypeError, KeyError) as e:
            self.notify(f"not applied: {e}", title="Steward", severity="warning")
            return None
        self._roads_changed()
        self.refresh_roster()
        try:
            chronicles.record(self.repo_root, self.scroll, building_id, "proposal_applied", what=what)
        except OSError:
            pass
        sha = self.checkpoint("auto-improve", building_id, f"steward: {what[:60]}") or ""
        evolution.record(self.repo_root, evolution.Change(
            building_id, str(proposal.get("type")), "steward", what, str(proposal.get("why") or "")[:200], by=by,
            sha=sha, key=f"steward:{building_id}:{data.get('ts', '')}:{index}"))
        return what

    def check_stewards(self) -> None:
        """Run each steward whose trigger is a schedule that came due since its last watch."""
        now = dt.datetime.now()
        self._maybe_optimize(now)
        self._maybe_weekly(now)
        for b in self.scroll.buildings:
            st = b.garrison.steward
            if b.demolished or st is None or st.trigger.get("type") != "cron":
                continue
            expr = str(st.trigger.get("expression") or "")
            last_report = steward.load_report(self.repo_root, b.id)
            try:
                last = dt.datetime.fromisoformat(last_report["ts"]) if last_report else None
            except (KeyError, ValueError):
                last = None
            if steward.due(expr, last, now):
                self.watch_building(b.id)

    def open_unit(self, w: Window, member: OrcSpec | None = None) -> None:
        b = self.building(w.window_id)
        b_spec = self.scroll.building(w.window_id)
        if b is None or b_spec is None:
            return
        if member is None:
            member = b_spec.garrison.lead
        if member is None:
            return
        ref = f"{w.window_id}/{member.id}"
        orc = next((o for o in self.roster.orcs if o.category == RESIDENT and o.ref == ref), None)
        if orc is None:
            orc = Orc(
                name=member.name,
                role=member.role or b.role,
                category=RESIDENT,
                trigger=Trigger.from_dict(member.trigger),
                status="idle",
                task=member.orders,
                building=w.window_id,
                ref=ref,
                lead=(member.id == b_spec.garrison.lead_orc_id),
            )

        def done(result: dict | None) -> None:
            if not result:
                return
            if result.get("answer") and orc.alert is not None:
                self.open_alert(orc.alert, orc.name)
                return
            trig = result["trigger"].to_dict()
            if "expression" in trig and not trig["expression"]:
                del trig["expression"]
            member.trigger = trig
            member.orders = result["context"]
            if "tier" in result:
                member.harness = tiers.with_tier(member.harness, result["tier"] or None)
            self.desktop.save()
            self.refresh_roster()
            try:
                chronicles.record(self.repo_root, self.scroll, w.window_id, "orders_changed",
                                  orc=member.name, trigger=result["trigger"].label)
            except OSError:
                pass
            self.notify(f"🧌 {member.name}: orders saved ({result['trigger'].label})", title="Orders")

        is_steward = member.id == b_spec.garrison.lead_orc_id
        tier = None if is_steward or not member.uses_model else (tiers.orc_tier(member.harness, member.kind) or "")
        self.push_screen(UnitModal(orc, b.label, member.orders, tier=tier), done)

    def _orc_ids(self, orc: Orc) -> tuple[str, str]:
        """(building id, orc id) of a garrison orc."""
        return tuple(orc.ref.split("/", 1)) if "/" in orc.ref else (orc.building or "", "")  # type: ignore[return-value]

    def like_orc(self, orc: Orc) -> None:
        """👍 on an orc's own work (its building's results are rated on the building)."""
        b_id, orc_id = self._orc_ids(orc)
        if not orc_id:
            return
        feedback.rate_orc(self.repo_root, b_id, orc_id, True)
        self.notify(f"{orc.name}: noted as good work", title="👍 Good")
        self._console_refresh()

    def dislike_orc(self, orc: Orc) -> None:
        """👎 on an orc's work: what went wrong (a note), kept as an incident."""
        b_id, orc_id = self._orc_ids(orc)
        if not orc_id:
            return

        def done(note: str | None) -> None:
            if note is None:
                return
            feedback.rate_orc(self.repo_root, b_id, orc_id, False, note)
            self.notify(f"{orc.name}: incident saved", title="👎 Bad")
            self._console_refresh()

        self.push_screen(TextPrompt(f"👎 {orc.name} — what went wrong?", placeholder="optional"), done)

    def open_orc_model(self, orc: Orc) -> None:
        """🎒 The inventory's model button: change a garrison orc's harness and tier."""
        b_id, orc_id = self._orc_ids(orc)
        b_spec = self.scroll.building(b_id) if b_id else None
        member = next((m for m in b_spec.garrison.members if m.id == orc_id), None) if b_spec else None
        if member is None or not member.uses_model:
            self.notify(f"{orc.name}: its model is not set here", title="🎒 Model")
            return

        def done(harness: list[dict] | None) -> None:
            if harness is None:
                return
            try:
                scroll.update_orc(self.scroll, b_id, orc_id, harness=harness)
            except ValueError as e:
                self.notify(str(e), title="🎒 Model", severity="error")
                return
            self.desktop.save()
            self.refresh_roster()
            self.notify(f"{member.name}: {tiers.label(tiers.orc_tier(harness, member.kind)) or 'CLI default model'}",
                        title="🎒 Model")

        self.push_screen(OrcModelModal(member.name, member.harness), done)
