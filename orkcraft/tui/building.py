"""Building: presets, the wizard, from scratch (interview → blueprint → sandbox), the ghost and raising a checked spec.

A part of `OrkcraftApp` (app.py): its methods run with the app as `self`.
"""
from __future__ import annotations

from typing import Any, Callable


from orkcraft.realm import blueprint, fastpath, builders, catalog, masonry, pipes
from orkcraft.tui import silhouettes
from orkcraft.realm.buildings import TOWN_HALL
from orkcraft.widgets.hut import footprint
from orkcraft.screens.build_flow import BuildFailed, BuildPreview, BuildProgress
from orkcraft.screens import builder_interview as bp_chat
from orkcraft.screens.builder_interview import BlueprintReview, BuilderChat, BuilderInterview
from orkcraft.tui.views import make_view
from orkcraft.screens.build_wizard import BuildReview, BuildWizard
from orkcraft.realm import town_builder
from orkcraft.screens.dialogs import TextPrompt
from orkcraft.screens.orders import BuildModal
from orkcraft.realm import workshop
from orkcraft.wm import Window

from orkcraft.core import buildings as core_buildings
from orkcraft.core import runners


class BuildingMixin:
    def action_build_window(self, initial_prompt: str = "") -> None:
        def done(prompt: str | None) -> None:
            if not prompt:
                return
            self._start_build(prompt)

        self.push_screen(BuildModal(initial_prompt=initial_prompt), done)

    def _start_build(self, prompt: str) -> None:
        self.push_screen(BuildProgress())

        def _worker() -> None:
            existing_ids = self._taken_building_ids()
            runner = runners.BUILD_RUNNER or builders.claude_runner
            result = builders.build(prompt, self.repo_root, existing_ids=existing_ids, runner=runner)
            self.call_from_thread(self._on_build_finished, prompt, result)

        self.run_worker(_worker, thread=True, name="mason_artisan_build")

    def _on_build_finished(self, prompt: str, result: builders.BuildResult) -> None:
        self._log_build_request(prompt, result)
        self._show_build_result(prompt, result)

    def _log_build_request(self, prompt: str, result: builders.BuildResult | town_builder.TownPlan) -> None:
        """Every build request, kept in `.orkcraft/build-requests.jsonl`."""
        core_buildings.log_build_request(self.core, prompt, result)

    def _show_build_result(self, prompt: str, result: builders.BuildResult) -> None:
        if isinstance(self.screen, BuildProgress):
            self.screen.dismiss(None)

        if result.ok and result.spec:
            spec = result.spec

            def on_preview_done(confirmed: bool | None) -> None:
                if confirmed:
                    self.review_and_raise(spec)

            self.push_screen(BuildPreview(spec, result), on_preview_done)
        else:
            def on_failed_done(action: str | None) -> None:
                if action == "retry":
                    self.action_build_window(initial_prompt=prompt)

            self.push_screen(BuildFailed(result), on_failed_done)

    def _type_spec(self, type_id: str) -> dict | None:
        """A camp building's spec from the catalog: the type's defaults and a free id."""
        return core_buildings.type_spec(self.core, type_id)

    def build_from_type(self, type_id: str) -> bool:
        """A camp building straight from the catalog: the type's defaults, no model call."""
        spec = self._type_spec(type_id)
        return spec is not None and self.raise_spec(spec)

    def preset_params(self, type_id: str) -> None:
        """A preset's step 2: this building's name, icon, description and settings.
        Presets are reviewed code — no Council, no model call."""
        spec = self._type_spec(type_id)
        if spec is None:
            return
        t = catalog.TYPES[type_id]

        def check(s: dict) -> list[str]:
            return masonry.validate_spec(s, self.repo_root, self._taken_building_ids())

        def done(final: dict | None) -> None:
            if final:
                self.place_and_raise(final)

        self.push_screen(BuildReview(spec, check=check, heading=f"🏗 FROM A PRESET · 2/3 — {t.icon} {t.title}: "
                                                               "this building's name and settings"), done)

    def _scratch_sources(self) -> list[tuple[str, str]]:
        sources = []
        for b in self.scroll.buildings_in(self.scroll.active_orkspace_id):
            if b.demolished or b.id == TOWN_HALL:
                continue
            for ev in pipes.TYPED.get(b.id, ()):
                sources.append((f"{b.id}:{ev}", f"{b.icon} {b.title} → {pipes.label(ev)}"))
        return sources

    def action_build_scratch(self, previous: dict | None = None, history: list | None = None,
                             rejected: dict | None = None) -> None:
        """From scratch: a conversation with the Builder. A rejected blueprint comes
        back here — what the operator says after it is the Builder's feedback for the next draft."""
        sources = self._scratch_sources()
        runner = runners.BUILD_RUNNER or builders.claude_runner
        opening = ("What should I change in the blueprint?" if rejected is not None else bp_chat.GREETING)
        start = len(history or [])

        def done(answer: dict | str | None) -> None:
            if answer == "form":
                self.push_screen(BuilderInterview(sources, previous), lambda iv: iv and self.start_blueprint(iv))
            elif isinstance(answer, dict):
                notes = [t for who, t in (answer.get("history") or [])[start + 1:] if who == "operator"]
                self.start_blueprint(answer, "\n".join(notes) if rejected is not None else "", rejected)

        self.push_screen(BuilderChat(sources, lambda h: blueprint.talk(h, sources, runner), history, opening), done)

    def start_blueprint(self, interview: dict, feedback: str = "", previous: dict | None = None) -> None:
        self.push_screen(BuildProgress("🛠 The Builder drafts a script, the Council and the sandbox check it…"))
        taken = self._taken_building_ids() | masonry.ID_RESERVED

        def _worker() -> None:
            result = blueprint.build(interview, taken, runners.BUILD_RUNNER or builders.claude_runner, feedback, previous)
            verdict, runs = self.check_blueprint(result.blueprint, light=True) if result.ok else (None, [])
            self.call_from_thread(self._on_blueprint, interview, result, verdict, runs)

        self.run_worker(_worker, thread=True, name="builder_blueprint")

    def check_blueprint(self, bp: dict, light: bool = False) -> tuple[fastpath.Verdict, list[workshop.Run]]:
        """The Council on the blueprint (rules; the light model too when `light`), then — unless a
        rule blocks it — its script on the mock carts in the sandbox. Safe off the UI thread."""
        spec = blueprint.to_spec(bp)
        runner = (runners.FASTPATH_RUNNER or fastpath.light_runner(self.repo_root)) if light and not self.demo else None
        model = str(fastpath.settings(self.repo_root).get("fast_model") or "")
        taken = self._taken_building_ids()
        verdict = fastpath.review(fastpath.Subject("building", bp["id"], spec, bp.get("script") or ""),
                                  self.repo_root, taken, runner, model)
        runs = [] if verdict.blocked else workshop.sandbox(bp.get("script") or "", bp["runtime"], bp.get("mocks") or [])
        return verdict, runs

    def _on_blueprint(self, interview: dict, result: blueprint.Result, verdict: fastpath.Verdict | None,
                      runs: list[workshop.Run]) -> None:
        if isinstance(self.screen, BuildProgress):
            self.screen.dismiss(None)
        if not result.ok or verdict is None:
            def on_failed(action: str | None) -> None:
                if action == "retry":
                    self.action_build_scratch(interview)
            self.push_screen(BuildFailed(result), on_failed)
            return
        bp = result.blueprint

        def done(choice: tuple[str, object] | None) -> None:
            if choice is None:
                fastpath.log(self.repo_root, verdict, "cancelled")
                return
            action, value = choice
            if action == "reject":
                fastpath.log(self.repo_root, verdict, "cancelled")
                if interview.get("history"):                 # back to the conversation with the Builder
                    self.action_build_scratch(previous=interview, history=interview["history"], rejected=bp)
                else:
                    self.push_screen(TextPrompt("✗ What should the Builder change?"),
                                     lambda note: note and self.start_blueprint(interview, note, bp))
                return
            final = dict(value)
            fastpath.log(self.repo_root, verdict, "overridden" if verdict.objections else "approved")
            self.raise_blueprint(final)

        self.push_screen(BlueprintReview(bp, verdict, runs, self.check_blueprint, result.cost_usd), done)

    def raise_blueprint(self, bp: dict) -> bool:
        """An approved blueprint: its script and blueprint go into the camp's git with the building,
        then the roads it asked for. True when it was raised at once (no ghost to place)."""
        def before() -> None:
            workshop.save_script(self.repo_root, bp["id"], bp["runtime"], bp["script"])
            workshop.save_blueprint(self.repo_root, bp["id"], bp)

        def after() -> None:
            for item in bp.get("inputs") or []:
                source, _, event = str(item).partition(":")
                if source and event:
                    self.add_road(bp["id"], source, event, None)

        return self.place_and_raise(blueprint.to_spec(bp), before=before, after=after)

    def place_and_raise(self, spec: dict, before: Callable[[], Any] | None = None,
                        after: Callable[[], Any] | None = None) -> bool:
        """The last step of a build: its ghost walks the town — Enter or a click
        raises it there, Esc builds nothing. Without a town on screen it is raised at once.
        True when it was raised at once."""
        label = f"{spec.get('icon', '')} {spec.get('title', '')}".strip()
        sil = silhouettes.styled(silhouettes.of(spec), self.desktop.plain)
        size = footprint(sil, silhouettes.label(len(self.desktop.huts) + 1, label, sil.width),
                         len(catalog.quick_actions_of(spec)))

        def raise_at(hut: list[float] | None) -> bool:
            if before is not None:
                before()
            ok = self.raise_spec(spec, hut=hut)
            if ok and after is not None:
                after()
            return ok

        def done(frac: tuple[float, float] | None) -> None:
            if frac is None:
                self.notify(f"{label}: nothing was built", title="👻 Build cancelled")
                return
            raise_at(list(frac))

        if self.desktop.start_ghost(label, size, done):
            self.notify("arrows or the mouse move it · Enter or a click builds · Esc cancels",
                        title=f"👻 Place {label}")
            return False
        return raise_at(None)

    def raise_spec(self, spec: dict, hut: list[float] | None = None, quiet: bool = False) -> bool:
        """Save a checked spec and raise its building in the active orkspace (at `hut`, the
        fractions of the town where its ghost settled). `quiet`: one of many (a town plan) — no toast,
        no focus, no commit of its own."""
        building = core_buildings.raise_spec(self.core, spec, hut)
        if building is None:
            return False
        spec = building.spec
        active_ork = self.scroll.active_orkspace
        next_number = len(active_ork.buildings) if active_ork else 1
        self.desktop.add_window(Window(make_view(building), window_id=building.id, title=building.label,
                                       number=next_number))
        self.desktop.save()
        active_ork = self.scroll.active_orkspace
        self.core.record(building.id, "building_raised",
                         orkspace=active_ork.name if active_ork else self.scroll.active_orkspace_id)
        self.refresh_roster()
        if quiet:
            return True
        self.notify(f"🏗️ {spec['title']} raised", title="Build")
        self.set_focus_state("building", building_id=building.id)
        self.checkpoint("create", building.id, f"raise {spec.get('type') or 'custom'} {spec['title']}")
        return True

    def action_build_wizard(self) -> None:
        def done(choice: tuple[str | None, str] | None) -> None:
            if choice:
                self.start_wizard_build(*choice)

        self.push_screen(BuildWizard(), done)

    def start_wizard_build(self, type_id: str | None, request: str) -> None:
        self.push_screen(BuildProgress())

        def _worker() -> None:
            runner = runners.BUILD_RUNNER or builders.claude_runner
            result = builders.propose(request, self.repo_root, type_id, self._taken_building_ids(), runner)
            self.call_from_thread(self._on_wizard_proposal, type_id, request, result)

        self.run_worker(_worker, thread=True, name="foreman_build")

    def _on_wizard_proposal(self, type_id: str | None, request: str, result: builders.BuildResult) -> None:
        self._log_build_request(request, result)
        if isinstance(self.screen, BuildProgress):
            self.screen.dismiss(None)
        if not (result.ok and result.spec):
            def on_failed(action: str | None) -> None:
                if action == "retry":
                    self.action_build_wizard()
            self.push_screen(BuildFailed(result), on_failed)
            return
        spec = result.spec
        if (spec.get("type") or catalog.DEFAULT_TYPE) == catalog.DEFAULT_TYPE:
            # Mason & Artisan's panes: their own preview
            self.push_screen(BuildPreview(spec, result), lambda ok: ok and self.review_and_raise(spec))
            return

        def check(s: dict) -> list[str]:
            return masonry.validate_spec(s, self.repo_root, self._taken_building_ids())

        def done(final: dict | None) -> None:
            if final:
                self.review_and_raise(final)

        self.push_screen(BuildReview(spec, len(result.attempts), result.cost_usd, check), done)
