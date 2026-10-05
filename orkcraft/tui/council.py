"""The Council and checkpoints: the Fast Path review, the camp's own git, Z revert, a building's goal and 👍 / 👎.

A part of `OrkcraftApp` (app.py): its methods run with the app as `self`.
"""
from __future__ import annotations

from typing import Any, Callable

from orkcraft.realm import fastpath
from orkcraft.realm.buildings import TOWN_HALL
from orkcraft.screens.council_review import CouncilProgress, CouncilVerdict
from orkcraft.screens.feedback_modal import DislikeModal
from orkcraft.screens.town_hall import TownHallView

from orkcraft.core import buildings as core_buildings
from orkcraft.core import runners


class CouncilMixin:
    def _taken_building_ids(self) -> set[str]:
        """Ids a new building may not take (core/town.py)."""
        return self.core.taken_ids()

    def cycle_goal(self, building_id: str) -> str | None:
        """🪙 Thrift → ⚖️ Balance → 💎 Quality → 🪙: what the retros improve the building towards."""
        goal = core_buildings.cycle_goal(self.core, building_id)
        if goal is not None:
            self._console_refresh()
        return goal

    def _title_of(self, building_id: str) -> str:
        return self.core.title_of(building_id)

    def like_building(self, building_id: str) -> bool:
        """K 👍: the building's last result becomes a reference."""
        return core_buildings.like(self.core, building_id)

    def dislike_building(self, building_id: str) -> None:
        """F 👎: what went wrong? Broken inputs penalise its suppliers upstream, its logic only it."""
        last, cascade = core_buildings.dislike_context(self.core, building_id)

        def done(answer: tuple[str, str] | None) -> None:
            if answer is not None:
                core_buildings.dislike(self.core, building_id, *answer)

        self.push_screen(DislikeModal(self._title_of(building_id), last, cascade), done)

    def review_and_raise(self, spec: dict) -> bool:
        """A building made from scratch: past the Council, then raised (presets skip this)."""
        return self.council_gate(fastpath.Subject("building", str(spec.get("id") or "?"), spec),
                                 lambda: self.place_and_raise(spec))

    def council_gate(self, subject: fastpath.Subject, on_approved: Callable[[], Any],
                     on_rejected: Callable[[str], Any] | None = None) -> bool:
        """Review `subject`, then `on_approved()` once it passes. A clean review (and a road with
        notes only) goes straight through; anything else shows the verdict. True when it went
        through at once."""
        existing = set(self._taken_building_ids()) if subject.kind == "building" else set()
        runner = None
        if not self.demo and (subject.kind != "road" or subject.data.get("handler_kind") in ("agent", "hybrid", "script")):
            runner = runners.FASTPATH_RUNNER or fastpath.light_runner(self.repo_root)
        model = str(fastpath.settings(self.repo_root).get("fast_model") or "")
        went: list[bool] = []

        def record(verdict: fastpath.Verdict, decision: str) -> None:
            fastpath.log(self.repo_root, verdict, decision)
            w = self.desktop.get_window(TOWN_HALL)
            view = next(iter(w.query(TownHallView)), None) if w is not None else None
            if view is not None:
                view.refresh_hall()

        def finish(verdict: fastpath.Verdict) -> None:
            if verdict.clean or (subject.kind == "road" and not verdict.blocked and not verdict.objections):
                record(verdict, "approved")
                if verdict.warnings:
                    self.notify("\n".join(f"⚠ {n.text}" for n in verdict.warnings), title="🏛 Council")
                went.append(True)
                on_approved()
                return

            def done(ok: bool | None) -> None:
                decision = ("overridden" if verdict.objections else "approved") if ok else \
                    "rejected" if verdict.blocked else "cancelled"
                record(verdict, decision)
                if ok:
                    on_approved()
                    return
                if verdict.blocked:
                    self.notify("\n".join(verdict.reasons()[:4]), title=f"🏛 Council rejected the {subject.kind}",
                                severity="warning")
                if on_rejected is not None:
                    on_rejected("; ".join(verdict.reasons()[:2]) or "sent back")

            self.push_screen(CouncilVerdict(verdict), done)

        if runner is None:
            finish(fastpath.review(subject, self.repo_root, existing))
            return bool(went)
        self.push_screen(CouncilProgress(subject.kind))

        def _worker() -> None:
            verdict = fastpath.review(subject, self.repo_root, existing, runner, model)
            self.call_from_thread(self._council_reviewed, verdict, finish)

        self.run_worker(_worker, thread=True, name="council_fast_path")
        return False

    def _council_reviewed(self, verdict: fastpath.Verdict, finish: Callable[[fastpath.Verdict], None]) -> None:
        if isinstance(self.screen, CouncilProgress):
            self.screen.dismiss(None)
        finish(verdict)

    def checkpoint(self, kind: str, building: str, reason: str) -> str | None:
        """Save the scroll and commit the change in the service repository (never in the demo)."""
        return self.core.checkpoint(kind, building, reason)

    def action_revert_building(self) -> None:
        bid = self.focus_state.building_id if self.focus_state.mode == "building" else None
        if bid:
            self.revert_building(bid)

    def revert_building(self, building_id: str) -> bool:
        """Z: this building back to its previous checkpoint — its files, incoming roads and garrison;
        nothing else in the camp changes."""
        return core_buildings.revert(self.core, building_id)
