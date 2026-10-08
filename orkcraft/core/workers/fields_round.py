"""🌾 Task Fields' part of the 🌙 Night round (docs/design/night-round.md): a part of `FieldsWorker`
(core/workers/fields.py), its methods run with the worker as `self`. core/retros.py runs the night: it asks
each board on the town's thread, calls the models off it, and gives the answers back here.

    round_look(commits, since, now)    the rules: the cards that lie, the commits and wiki pages that are
                                       theirs; for the first few (not personal) the ask for a model's words
    round_mark(asks)                   the 🌙 marks, each with what the model said (an ask it trimmed: none)
    round_ideas_ask(commits, diff, n)  the ask for at most `n` cleanup ideas from the day's code
    round_add_ideas(ideas, at)         the ideas as notes in Ideas (never a task, never a cart)
    round_ideas_where()                where each idea it gave is now: what became of it
"""
from __future__ import annotations

import datetime as dt
import time

from orkcraft.core import runners
from orkcraft.core.workers.fields_lore import card_text
from orkcraft.realm import builders, nightround, privacy, tasklist


class NightRound:
    @property
    def round_takes_part(self) -> bool:
        """A board takes part unless its settings say `night_round: false`."""
        return self.config.get("night_round") is not False

    def round_runner(self, use: str):
        """Its steward's model for the round's `use` (news | ideas), and its name; (None, why) when none may run."""
        if runners.ROUND_RUNNER is not None:
            return runners.ROUND_RUNNER, "test"
        if self.simulated or self.town.demo:
            return None, "no model runs in the demo"
        if not self.town.budget_ok():
            return None, "the budget is spent"
        return self.steward_runner(use), self.steward_pick(use).model or "the default model"

    # -- the cards that lie ---------------------------------------------------------------------------

    def round_look(self, found: list[nightround.Commit], since: float, now: dt.datetime) -> list[dict]:
        """What is new for the cards that lie, by the rules: the commits that share a card's words and its
        context's pages new or changed since `since` (epoch seconds). At most `CARDS_MAX`, those that lay
        longest first; for the first `TOLD_MAX` that are not personal, a `prompt` for a model."""
        self.refresh()
        cards = nightround.lying(self.cards)
        seen = nightround.first_seen(self.repo_root, self.building_id, [c.id for c in cards], now)
        cards.sort(key=lambda c: (-nightround.days_lain(seen, c.id, now), c.id))
        runner, model = self.round_runner("news")
        asks: list[dict] = []
        for card in cards:
            before = {p.path: p.mtime for p in self.lore.context(card.id)}
            self.find_context(card.id)
            pages = [p for p in self.lore.context(card.id)
                     if p.path not in before or p.mtime > max(before[p.path], since) + 1e-6]
            commits = nightround.theirs(card_text(card), found)
            if not commits and not pages:
                continue
            ask = {"card": card.id, "commits": [[c.sha, c.subject] for c in commits],
                   "pages": [[p.path, p.title] for p in pages], "prompt": "", "table": {}, "words": ""}
            told = sum(1 for a in asks if a["prompt"])
            if runner is not None and told < nightround.TOLD_MAX and not self.private(card.id):
                scrub = privacy.scrub(card_text(card))
                texts = []
                for p in pages:
                    try:
                        text = (self.repo_root / p.path).read_text(encoding="utf-8")[:nightround.PAGE_CHARS]
                    except OSError:
                        continue
                    texts.append((p.title, privacy.scrub(text, scrub).text))
                subjects = [nightround.Commit(c.sha, privacy.scrub(c.subject, scrub).text, c.files) for c in commits]
                ask["prompt"] = nightround.news_prompt(scrub.text, subjects, texts)
                ask["table"] = scrub.table
                ask["runner"] = runner
                self.lore.log_sent(card.id, len(ask["prompt"]), model, [p.path for p in pages], scrub.found)
            asks.append(ask)
            if len(asks) >= nightround.CARDS_MAX:
                break
        return asks

    def round_mark(self, asks: list[dict]) -> int:
        """The 🌙 marks: what the rules found, with the model's words. An ask the model trimmed (nothing of it
        matters to the card) leaves the card as it was. How many cards were marked."""
        marked = 0
        stamp = time.strftime("%Y-%m-%dT%H:%M:%S")
        for ask in asks:
            if ask.get("trimmed") or self.card(ask["card"]) is None:
                continue
            self.lore.set_news(ask["card"], {"at": stamp, "commits": ask["commits"], "pages": ask["pages"],
                                             "words": ask.get("words") or ""})
            marked += 1
        if marked:
            self.changed()
        return marked

    def news_seen(self, card_id: str) -> None:
        """The person read what is new for the card: the 🌙 mark goes."""
        self.lore.set_news(card_id, None)
        self.changed()

    # -- cleanup ideas --------------------------------------------------------------------------------

    def round_ideas_ask(self, found: list[nightround.Commit], changes: str, cap: int) -> dict | None:
        """The ask for at most `cap` cleanup ideas from the day's code; None when no model may run."""
        runner, model = self.round_runner("ideas")
        if runner is None or cap <= 0 or not found:
            return None
        have = [tasklist.plain(c.title) for c in self.cards]          # all of them: a duplicate is left out here
        shown = [tasklist.plain(c.title) for c in self.cards if not self.private(c.id)]   # a personal one never leaves
        scrub = privacy.scrub(changes)
        prompt = nightround.ideas_prompt(found, scrub.text, cap, shown)
        self.lore.log_sent("night-round", len(prompt), model, [], scrub.found)
        return {"prompt": prompt, "runner": runner, "cap": cap, "have": have, "table": scrub.table}

    def round_lane(self) -> str:
        """The lane its ideas go to: Ideas, made when the board has none ("" when it cannot be made)."""
        want = tasklist.slug(nightround.IDEA_LANE)
        if any(ln.id == want for ln in self.lanes):
            return want
        return self.add_lane(nightround.IDEA_LANE)

    def round_add_ideas(self, ideas: list[dict], at: str) -> list[str]:
        """Each idea a note in Ideas, marked 🌙 (no event: the round never sends work down a road). Their keys."""
        lane = self.round_lane() if ideas else ""
        keys = []
        for n, idea in enumerate(ideas, 1):
            try:
                card = self.store.add(idea["title"], lane, nightround.idea_body(idea))
            except (OSError, ValueError, KeyError):
                continue
            key = f"{at}-{n}"
            self.lore.set_idea(card.id, key)
            keys.append(key)
        if keys:
            self._sync(seen=False)            # new to the person: the hut's * says so
        return keys

    def round_ideas_where(self) -> dict[str, str]:
        """Where each idea the round gave is now: idea key → its card's lane (a deleted card is missing)."""
        self.refresh()
        lanes = {c.id: c.column for c in self.cards}
        return {key: lanes[cid] for key, cid in self.lore.ideas().items() if cid in lanes}


def ask_model(ask: dict) -> tuple[str, float]:
    """One of the round's asks, off the town's thread: the model's answer with what was taken out put back."""
    text, cost = ask["runner"](ask["prompt"])
    return privacy.restore(text or "", ask.get("table") or {}), float(cost or 0.0)


def parse_ideas(answer: str, ask: dict) -> list[dict]:
    return nightround.parse_ideas(builders.extract_json(answer), ask["cap"], ask["have"])

