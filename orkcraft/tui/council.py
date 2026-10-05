"""The Council and checkpoints: the Fast Path review, the camp's own git, Z revert, a building's goal and 👍 / 👎.

A part of `OrkcraftApp` (app.py): its methods run with the app as `self`.
"""
from __future__ import annotations

from typing import Any, Callable


from orkcraft import scroll
from orkcraft.realm import checkpoint, fastpath, feedback, catalog, pipes
from orkcraft.realm.buildings import TOWN_HALL
from orkcraft.screens.council_review import CouncilProgress, CouncilVerdict
from orkcraft.screens.feedback_modal import DislikeModal
from orkcraft.screens.town_hall import TownHallView

from orkcraft.core import runners


class CouncilMixin:
    def _taken_building_ids(self) -> set[str]:
        """Ids a new building may not take: loaded buildings and every building the scroll remembers
        (a custom building whose spec file was deleted still has its scroll entry)."""
        return {b.id for b in self.buildings} | {b.id for b in self.scroll.buildings}

    def cycle_goal(self, building_id: str) -> str | None:
        """🪙 Thrift → ⚖️ Balance → 💎 Quality → 🪙: what the retros improve the building towards."""
        b = self.scroll.building(building_id)
        if b is None:
            return None
        goal = scroll.GOALS[(scroll.GOALS.index(b.aim) + 1) % len(scroll.GOALS)]
        b.goal = None if goal == "balance" else goal
        self.desktop.save()
        what = {"thrift": "the retros will make it cheaper", "balance": "cheaper where it is liked, better where it is not",
                "quality": "the retros will make its results better — it may spend more (up to twice the prompt)"}[goal]
        self.notify(f"{self._title_of(building_id)}: {what}",
                    title=f"{scroll.GOAL_ICONS[goal]} {scroll.GOAL_TITLES[goal]}")
        self._console_refresh()
        return goal

    def _title_of(self, building_id: str) -> str:
        b = self.scroll.building(building_id) if self.scroll is not None else None
        return f"{b.icon} {b.title}".strip() if b else building_id

    def like_building(self, building_id: str) -> bool:
        """K 👍: the building's last result becomes a reference."""
        out = feedback.like(self.repo_root, building_id)
        if out is None:
            self.notify("nothing to rate yet — it has sent no result", title="👍")
            return False
        self.notify(f"{self._title_of(building_id)}: its last result is a reference now", title="👍 Good")
        self._refresh_hall()
        return True

    def dislike_building(self, building_id: str) -> None:
        """F 👎: what went wrong? Broken inputs penalise its suppliers upstream, its logic only it."""
        out = feedback.last_output(self.repo_root, building_id) or {}
        cascade = [(self._title_of(b), feedback.CASCADE[hop - 1])
                   for b, hop in feedback.suppliers(self.repo_root, self.scroll, building_id)]

        def done(answer: tuple[str, str] | None) -> None:
            if answer is None:
                return
            incident = feedback.dislike(self.repo_root, self.scroll, building_id, *answer)
            who = ", ".join(f"{self._title_of(b)} −{p:g}" for b, p in incident.blamed.items()) or "nobody"
            self.notify(f"incident saved · {who}", title=f"👎 {self._title_of(building_id)}")
            self._refresh_hall()

        self.push_screen(DislikeModal(self._title_of(building_id), str(out.get("value", "")), cascade), done)

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
        if self.demo:
            return None
        try:
            self.desktop.save()
        except Exception:
            pass
        return checkpoint.commit(self.repo_root, kind, building, reason, self.config.layout_file)

    def action_revert_building(self) -> None:
        bid = self.focus_state.building_id if self.focus_state.mode == "building" else None
        if bid:
            self.revert_building(bid)

    def revert_building(self, building_id: str) -> bool:
        """Z: this building back to its previous checkpoint — its files, incoming roads and garrison;
        nothing else in the camp changes."""
        before = checkpoint.building_before(self.repo_root, building_id)
        if before is None:
            self.notify("no earlier checkpoint for this building", title="↶ Revert")
            return False
        parent, spec, entry, files = before
        if entry is None and spec is None:
            self.notify("this is the building's first checkpoint — demolish it with X instead", title="↶ Revert")
            return False
        checkpoint.restore_files(self.repo_root, building_id, spec, files)
        current = self.scroll.building(building_id) if self.scroll is not None else None
        if current is not None and entry is not None:
            old = scroll.TownScroll.from_dict({"active_orkspace_id": "x", "orkspaces": [], "buildings": [entry]}).buildings[0]
            known = {b.id for b in self.scroll.buildings}
            current.roads = [r for r in old.roads if r.source in known]
            current.garrison, current.actions = old.garrison, old.actions
            current.title, current.icon = old.title, old.icon
        if spec is not None:
            spec = catalog.migrate(spec)
            self.custom_specs[building_id] = spec
            pipes.set_typed(building_id, catalog.events_of(spec))
            view = self._custom_view(building_id)
            if view is not None:
                view.spec = spec
                refresh = getattr(view, "refresh_data", None)
                if refresh is not None:
                    refresh()
        self._roads_changed()
        self.refresh_roster()
        self.checkpoint("revert", building_id, f"back to {parent[:8]}")
        self.notify(f"back to checkpoint {parent[:8]}", title=f"↶ {building_id}")
        return True
