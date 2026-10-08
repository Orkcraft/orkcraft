"""Raising a town: the end of onboarding, and the Town Builder's order → plan → approval → buildings and roads.

A part of `OrkcraftApp` (app.py): its methods run with the app as `self`.
"""
from __future__ import annotations

import functools
from typing import Any, Callable

from textual import work

from orkcraft.realm import checkpoint, builders
from orkcraft.screens import onboarding
from orkcraft.realm import intents, town_builder, town_presets
from orkcraft.screens.town_plan import TownPlanReview

from orkcraft.core import runners


class RaisingMixin:
    def _order_burns(self) -> bool:
        order = town_presets.pending_order(self.repo_root)
        return order is not None and not order.get("seen")

    def start_onboarding(self, machine_steps: bool | None = None, town_step: bool = True) -> None:
        """Who you are and the machine's part once per machine (or when asked, F10); the town for a
        project with none yet."""
        if machine_steps is None:
            machine_steps = not self.desktop.machine.onboarded
        onboarding.Onboarding(self, machine_steps, town_step, on_town=self.raise_town).start()

    def raise_town(self, choice: dict) -> None:
        """The end of onboarding: the camp's records and the Warder over the map, a progress bar along
        the bottom; then the intent's town, or the interview's order for the Town Builder."""
        steps = onboarding.raising_steps(choice)
        bar = onboarding.mount_raise_bar(self.screen, len(steps))
        self._raise_town_work(choice, steps, bar)

    @work(thread=True, exclusive=True, group="raise-town")
    def _raise_town_work(self, choice: dict, steps: list[str], bar) -> None:
        problems: list[str] = []
        for i, label in enumerate(steps):
            self.call_from_thread(bar.step, label + "…", i)
            try:
                if label.startswith("Opening"):
                    checkpoint.ensure(self.repo_root)
                elif "Warder" in label:
                    from orkcraft.hooks import install as hooks_install
                    checked = self.desktop.machine.agy_warder_checked   # agy's hook only once checked live
                    hooks_install.install_all(self.repo_root, agy=None if checked else False)
                elif "order" in label:
                    town_presets.save_order(self.repo_root, choice.get("prompt", ""), choice.get("role", ""),
                                            choice.get("answers") or {})
            except (OSError, ValueError, RuntimeError) as e:
                problems.append(f"{label}: {e}")
            onboarding.pause()
        self.call_from_thread(self._town_raised, choice, steps, bar, problems)

    def _town_raised(self, choice: dict, steps: list[str], bar, problems: list[str]) -> None:
        bar.step("The camp is ready", len(steps))
        self.desktop.save()
        it = intents.intent(choice.get("preset", ""))
        reason = f"onboarding: {it.title}" if it else f"onboarding: {choice.get('preset', 'empty')} town"
        checkpoint.commit(self.repo_root, "create", "camp", reason, self.config.layout_file)
        self.order_burning = self._order_burns()
        self.refresh_roster()
        self.set_timer(1.5, bar.remove)
        if problems:
            self.notify("\n".join(problems), title="🏗 Raising the town", severity="warning")
        if it is not None:
            plan, errors = town_builder.check(it.plan, self.repo_root, self._taken_building_ids())
            if errors:                                             # the templates are tested; never expected
                self.notify("\n".join(errors[:3]), title=f"🏗 {it.title}", severity="error")
            else:
                self.set_timer(1.6, lambda: self.raise_town_plan(plan))    # after the bar has gone
        elif choice.get("preset") == onboarding.CUSTOM and town_presets.pending_order(self.repo_root) is not None:
            self.set_timer(1.6, self.build_town_from_order)
        elif choice.get("expert"):
            self.notify("B build · Y roads · 🏰 Town Hall → 📜 Preset or 🛠 New · F10 → 📜 Town Builder.",
                        title="🤘 The town is yours to build", timeout=12)
        else:
            self.notify("B build · P presets · ? all keys.", title="🏰 The town stands", timeout=10)

    def build_town_from_order(self, note: str = "") -> None:
        order = town_presets.pending_order(self.repo_root)
        if order is None:
            self.notify("no town order waits in the Town Hall", title="📜 Town Builder")
            return
        if self.query(onboarding.RaiseBar):
            return                                                # one town at a time
        on = [t for t, choice in self.desktop.machine.tools.items() if choice.enabled]
        if runners.BUILD_RUNNER is None and builders.planner_tool(on) is None:
            self.order_burning = self._order_burns()
            self.notify("The Town Builder plans with Claude Code, Codex or agy, and all of them are off. "
                        "F10 → 🧭 Onboarding turns one on; the order keeps waiting in the 🏰 Town Hall.",
                        title="📜 Town Builder", severity="warning", timeout=12)
            return
        bar = onboarding.mount_raise_bar(self.screen, None)
        role = str(order.get("role") or "")
        bar.say(f"📜 The Town Builder is adapting a {intents.role(role).title.lower()} town to your answers…"
                if role else "📜 The Town Builder is drawing your town…")
        self._plan_town_work(order["prompt"], note, bar, intents.templates_text(role) if role else "")

    @work(thread=True, exclusive=True, group="town-builder")
    def _plan_town_work(self, order: str, note: str, bar, templates: str = "") -> None:
        runner = runners.BUILD_RUNNER or builders.main_runner_of(self.desktop.machine)
        result = town_builder.plan(order, self.repo_root, self._taken_building_ids(), runner, feedback=note,
                                   templates=templates)
        self.call_from_thread(self._on_town_plan, order, result, bar)

    def _on_town_plan(self, order: str, result: town_builder.TownPlan, bar) -> None:
        bar.remove()
        self._log_build_request(f"town: {order}", result)
        if not result.ok:
            self.order_burning = self._order_burns()
            self.notify(f"{result.error or 'no plan'}\nThe order keeps waiting in the 🏰 Town Hall.",
                        title="📜 Town Builder", severity="error", timeout=12)
            return

        def done(answer: dict | None) -> None:
            if answer is None:
                kept = town_presets.pending_order(self.repo_root) or {}
                town_presets.save_order(self.repo_root, order, kept.get("role", ""), kept.get("answers") or {})
                self.order_burning = True                         # later: it burns until the Hall is opened
                self.refresh_roster()
                self.notify("The order waits in the 🏰 Town Hall.", title="📜 Town Builder")
            elif answer.get("action") == "again":
                self.build_town_from_order(answer.get("note", ""))
            else:
                self.raise_town_plan(result)

        self.push_screen(TownPlanReview(order, result), done)

    def raise_town_plan(self, plan: town_builder.TownPlan) -> None:
        """Raise an approved plan: its buildings one by one, then its roads, with the bar along the bottom."""
        steps: list[tuple[str, Callable[[], Any]]] = []
        for spec in plan.specs:
            label = f"{spec.get('icon', '')} {spec.get('title', spec['id'])}".strip()
            steps.append((f"Raising {label}", functools.partial(self.raise_spec, spec, None, True)))
        for r in plan.roads:
            steps.append((f"Laying the road {r.source} → {r.target}",
                          functools.partial(self.add_road, r.target, r.source, r.subscription, None, True, r.returns)))
        bar = onboarding.mount_raise_bar(self.screen, len(steps))

        def run(i: int) -> None:
            if i == len(steps):
                bar.step("The town stands", len(steps))
                town_presets.close_order(self.repo_root, plan.title)
                self.order_burning = False
                self.checkpoint("create", "camp", f"town: {plan.title or 'from an order'}")
                self.desktop.set_active(None)                 # the whole town on the map, nothing open
                self.set_focus_state("neutral")
                self.refresh_roster()
                self.desktop.refresh_huts()
                self.set_timer(1.5, bar.remove)
                self.notify(f"{len(plan.specs)} buildings · {len(plan.roads)} roads. B build · Y roads · ? all keys.",
                            title=f"🏰 {plan.title or 'The town'} stands", timeout=10)
                return
            label, act = steps[i]
            bar.step(label + "…", i)
            try:
                act()
            except Exception as e:      # one building that will not stand must not stop the rest
                self.notify(f"{label}: {e}", title="🏗 Raising the town", severity="warning")
            self.set_timer(onboarding.STEP_PAUSE_S or 0.01, lambda: run(i + 1))

        run(0)
