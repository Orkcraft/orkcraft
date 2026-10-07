"""🌾 Task Fields' context, plan and personal cards: a part of `FieldsWorker` (core/workers/fields.py),
its methods run with the worker as `self`. What it keeps lives beside the board (realm/cardlore.py).

    context 📜   `find_context`: the town's Scroll Dumps (`wikis`, default every one) give the pages that
                 share the card's words — no model, nothing leaves the machine
    plan 🧭      `plan_preview` says what would leave (cleaned by realm/privacy.py), `plan` asks the light
                 model off the town's thread, `plan_to_todos` makes its steps to-dos
    personal 🔒  `private`, `set_private`: a personal card never reaches a model
"""
from __future__ import annotations

import threading

from orkcraft.core import runners
from orkcraft.realm import cardlore, privacy, tasklist
from orkcraft.realm.tasklist import MINE

TITLE = "🌾 Task Fields"


def card_text(card: tasklist.Task) -> str:
    title = tasklist.plain(card.title)
    return f"{title}\n\n{card.body}" if card.body else title


class CardLore:
    @property
    def lore(self) -> cardlore.Lore:
        if getattr(self, "_lore", None) is None or self._lore.dir != self.state_dir:
            self._lore = cardlore.Lore(self.state_dir)
        return self._lore

    def _mark(self, card: tasklist.Task | None, private: bool) -> tasklist.Task | None:
        if card is not None and private:
            self.lore.set_private(card.id, True)
            self.changed()
        return card

    def private(self, card_id: str) -> bool:
        """The card never reaches a model: the person said so, or it is a to-do and `private_todos` is on."""
        said = self.lore.private(card_id)
        if said is not None:
            return said
        card = self.card(card_id)
        return card is not None and card.kind == MINE and bool(self.config.get("private_todos"))

    def set_private(self, card_id: str, private: bool | None = None) -> bool:
        """Mark a card personal (or not; None flips it). What it is now."""
        if self.card(card_id) is None:
            return False
        now = (not self.private(card_id)) if private is None else bool(private)
        self.lore.set_private(card_id, now)
        self.changed()
        return now

    @property
    def wikis(self) -> list[str]:
        """The Scroll Dumps a card's context comes from: `wikis`, else every one in the town."""
        named = self.config.get("wikis")
        if isinstance(named, list):
            return [str(b) for b in named]
        from orkcraft.core.workers import type_id
        return [bid for bid, spec in sorted(self.town.custom_specs.items())
                if type_id(spec) == "scrolls" and not spec.get("demolished")]

    def find_context(self, card_id: str) -> int:
        """Ask the wikis for the pages that matter for the card (the words they share; no model). How many
        it found; none found, the card has no context."""
        card = self.card(card_id)
        if card is None:
            return 0
        task, pages, seen = card_text(card), [], set()
        for bid in self.wikis:
            try:
                look_up = getattr(self.town.worker(bid), "look_up", None)
            except Exception:  # a wiki that cannot start gives no context; the card stays as it is
                continue
            if look_up is None:
                continue
            for n in look_up(task, self.building_id, tasklist.plain(card.title)):
                if n.path in seen:
                    continue
                seen.add(n.path)
                try:
                    mtime = (self.repo_root / n.path).stat().st_mtime
                except OSError:
                    continue
                pages.append(cardlore.Page(n.path, n.title, mtime))
        self.lore.set_context(card.id, pages[:cardlore.STEPS])
        self.changed()
        return len(pages)

    def plan_runner(self):
        """The model a plan is asked of, and its name; (None, why) when there is none to call."""
        if runners.FASTPATH_RUNNER is not None:
            return runners.FASTPATH_RUNNER, "test"
        if self.simulated or self.town.demo:
            return None, "No model runs in the demo"
        if not self.town.budget_ok():
            return None, "The budget is spent"
        from orkcraft.realm import builders, fastpath
        chosen = str(self.config.get("plan_model") or "").strip()
        if chosen:
            return (lambda prompt: builders.main_runner(prompt, chosen)), chosen
        runner = fastpath.light_runner(self.repo_root)
        if runner is None:
            return None, "The light model is switched off (Council settings)"
        return runner, str(fastpath.settings(self.repo_root).get("fast_model") or "haiku")

    def _outgoing(self, card: tasklist.Task, pages: list[str] | None = None):
        """What a plan of the card would send: the cleaned ask, the scrub, and the pages it takes."""
        chosen = [p for p in self.lore.context(card.id) if pages is None or p.path in pages]
        scrub = privacy.scrub(card_text(card))
        todo = scrub.text
        texts = []
        for p in chosen:
            try:
                text = (self.repo_root / p.path).read_text(encoding="utf-8")[:cardlore.PAGE_CHARS]
            except OSError:
                continue
            texts.append((p.title, privacy.scrub(text, scrub).text))
        return cardlore.plan_prompt(todo, texts), todo, scrub, chosen

    def plan_preview(self, card_id: str) -> dict:
        """What Plan would send, before it goes: the to-do as it leaves (cleaned), what was taken out, the
        pages it takes along and the model; `allowed` False with `why` when it may not go."""
        card = self.card(card_id)
        if card is None:
            return {"allowed": False, "why": "That card is gone from the board"}
        if card.kind != MINE:
            return {"allowed": False, "why": "A plan is for a to-do of your own"}
        if self.private(card_id):
            return {"allowed": False, "why": "It is personal: it is never sent to a model"}
        runner, model = self.plan_runner()
        _, todo, scrub, pages = self._outgoing(card)
        return {"allowed": runner is not None, "why": "" if runner is not None else model, "model": model,
                "text": todo, "taken_out": privacy.said(scrub.found),
                "pages": [{"path": p.path, "title": p.title} for p in pages], "asked": not self.lore.plan_ok}

    def plan(self, card_id: str, pages: list[str] | None = None, trust: bool = False) -> bool:
        """Ask a light model for the to-do's steps, with the chosen pages of its context (all of them when
        None); off the town's thread, the plan kept once written. True when it started."""
        card = self.card(card_id)
        if card is None or card.kind != MINE or self.private(card_id) or card_id in self.planning:
            return False
        runner, model = self.plan_runner()
        if runner is None:
            self.toast(model, title=TITLE, severity="warning")
            return False
        if trust:
            self.lore.trust_plans()
        prompt, _, scrub, chosen = self._outgoing(card, pages)
        self.lore.log_sent(card_id, len(prompt), model, [p.path for p in chosen], scrub.found)
        self.planning.add(card_id)
        self.plan_error = ""
        self.changed()

        def work() -> None:
            try:
                steps = cardlore.parse_plan(privacy.restore(runner(prompt)[0], scrub.table))
                error = "" if steps else "The model gave no steps"
            except Exception as e:  # a model that cannot be reached leaves the to-do as it was
                steps, error = [], f"No plan: {str(e)[:120]}"
            self.town.call(self._planned, card_id, steps, model, error)

        threading.Thread(target=work, daemon=True, name=f"fields-plan-{self.building_id}").start()
        return True

    def _planned(self, card_id: str, steps: list[str], model: str, error: str) -> None:
        self.planning.discard(card_id)
        if steps and self.card(card_id) is not None:
            self.lore.keep_plan(card_id, steps, model)
        if error:
            self.plan_error = error
            self.toast(error, title=TITLE, severity="warning")
        self.changed()

    def plan_to_todos(self, card_id: str) -> int:
        """The plan's steps become to-dos of their own (personal when the to-do is). How many were added."""
        private = self.private(card_id)
        added = 0
        for step in self.lore.plan(card_id):
            if self._mark(self.add(step, MINE), private) is not None:
                added += 1
        return added
