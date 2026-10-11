"""🏛 The Elders improve the town at night (docs/design/improve-buildings.md §8): the Mechanic and the Alchemist, the
Improve buildings' orks (design/agents/), at work while the person is away, within the night's budget (the Council's
`improve_per_night_usd`, $1 by default) and the town's autonomy.

**The Mechanic**, one Test bench at a time: one that ran its cases by day (so the night knows what they cost) and
has a goal. Its proposals are written again; the first settings or prompt change not tried yet is tried on the
virtual building (its keeper); the cases run again on it; the goal's mean decides:

    better, and the autonomy lets it        saved for good, by the orks: on probation, back by itself on a 👎
    better, the autonomy does not           left on the virtual building: Save changes waits for the person
    not better                              taken back

The autonomy (autonomy.py, the building's own else the town's): ⛓️‍💥 unchained saves what is better; 🕰 on the clock
only what is cheaper or faster with no loss of quality; ⛓️ in chains saves nothing. Roads and code are never
the night's: a road is the setup's, code goes only as a pull request the person sends.

**The Alchemist**, one UX bench at a time whose building's cards were never laid out: its cards laid out so each
size says what matters most (one checked call). Applied when unchained, else a draft that waits in the bench.

What they did is said in the morning, in one toast, and kept (`.orkcraft/council/improve.jsonl`).

    improve = ImproveNight(host); improve.tick(quiet, exhausted); improve.morning() → lines
"""
from __future__ import annotations

import datetime as dt
import json
import time
from pathlib import Path

from orkcraft import autonomy
from orkcraft.core.workers.lab import CODE
from orkcraft.realm import card_docs, catalog, fastpath, lab_cases, lab_envs

LOG = Path(".orkcraft") / "council" / "improve.jsonl"
CHECK_S = 120.0                 # how often the night looks for a bench to work on
ASK_USD = 0.10                  # a proposal, a keeper's change, a layout: counted at this against the budget
MARGIN = 0.03                   # the goal's mean must move at least this far to count as better
TRIABLE = ("settings", "prompt")
NIGHT_ASK = ("Lay the cards out so each size says what matters most to the person: the small card one headline, "
             "the medium one what it is doing now, the large one everything that helps; hide what does not.")


def better(before: dict, after: dict, metric: str) -> tuple[bool, bool]:
    """(better on the goal's metric with no loss of quality, and is that a cheaper or faster one)."""
    key = {"tokens": "tokens", "time": "time"}.get(metric, "quality")
    b, a = before.get(key), after.get(key)
    if a is None or b is None:
        return False, False
    kept = before.get("quality") is None or after.get("quality") is None or after["quality"] >= before["quality"]
    if key == "quality":
        return a > b + MARGIN, False
    return (a < b - MARGIN) and kept, (a < b - MARGIN) and kept


class ImproveNight:
    def __init__(self, host) -> None:
        self.host = host
        self.town = host.town
        self.spent = 0.0                     # tonight's, as counted (realm/lab_envs.py estimate, ASK_USD a call)
        self.done: set[str] = set()          # benches looked at tonight
        self.busy = ""                       # the bench at work now
        self.checked = -CHECK_S
        self.lines: list[str] = []           # what the morning says

    def budget(self) -> float:
        try:
            return max(float(fastpath.settings(self.town.repo_root).get("improve_per_night_usd", 1.0)), 0.0)
        except (TypeError, ValueError):
            return 1.0

    def morning(self) -> list[str]:
        out, self.lines, self.done, self.spent = self.lines, [], set(), 0.0
        return out

    def _say(self, who: str, line: str) -> None:
        self.lines.append(f"{who}: {line}")
        try:
            path = self.town.repo_root / LOG
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"at": dt.datetime.now().isoformat(timespec="seconds"), "who": who,
                                    "line": line, "spent": round(self.spent, 2)}, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def _finish(self, bid: str) -> None:
        self.busy = ""
        self.done.add(bid)

    def _level(self, bid: str) -> int:
        b = self.town.scroll.building(bid) if self.town.scroll is not None else None
        return autonomy.rules_of(b, getattr(self.town.machine, "autonomy", autonomy.DEFAULT_LEVEL)).level

    def tick(self, quiet: bool, exhausted: bool = False, now: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        if not quiet or exhausted or self.busy or self.town.demo or now - self.checked < CHECK_S:
            return
        self.checked = now
        engine = getattr(self.host, "bench", None)
        for b in self.town.scroll.buildings:
            if b.demolished or b.id in self.done:
                continue
            kind = catalog.type_of(self.town.spec_of(b.id)).id
            if kind == "lab" and engine is not None:
                self._mechanic(self.town.worker(b.id), engine.lab)
            elif kind == "ux_lab":
                self._alchemist(self.town.worker(b.id))
            else:
                continue
            if self.busy:
                return

    # -- the Mechanic -------------------------------------------------------------------------------------------------

    def _mechanic(self, w, lab) -> None:
        bid = w.building_id
        s = w.subject()
        cases = w.cases_of(s["id"]) if s else []
        est = lab_envs.estimate(cases, w.results_of(s["id"]), len(cases)) if s else {}
        if not s or not cases or not w.state["goal"].strip() or not est:
            self._finish(bid)                # nothing to measure, or never run by day: the night cannot price it
            return
        need = est["cost"] + 2 * ASK_USD
        if self.spent + need > self.budget():
            self._finish(bid)
            self._say("Mechanic", f"{w.title}: left for another night — its cases cost about ${est['cost']:.2f}, "
                                  f"more than the night has left")
            return
        metric = lab_cases.metric_of(w.state["goal"])
        before = lab_envs.summary_of(cases, w.results_of(s["id"]))
        tried = set(w.state.setdefault("night_tried", []))
        self.busy = bid
        self.spent += ASK_USD

        def proposed() -> None:
            items = (w.state["proposals"].get(s["id"]) or {}).get("items") or []
            p = next((x for x in items if x["area"] in TRIABLE and x["title"] not in tried), None)
            if p is None:
                self._finish(bid)
                return
            w.state["night_tried"] = [*tried, p["title"]][-40:]
            self.spent += ASK_USD
            try:
                lab.try_change(w, s, p["id"], after=lambda ok: changed(ok, p))
            except Exception:                # a proposal that cannot be tried: the night goes on to another bench
                self._finish(bid)

        def changed(ok: bool, p: dict) -> None:
            if not ok:
                self._finish(bid)
                return
            self.spent += est["cost"]
            try:
                lab.run(w, s, [c["id"] for c in cases], then=lambda: judged(p))
            except Exception:
                self._finish(bid)

        def judged(p: dict) -> None:
            after = lab_envs.summary_of(cases, w.results_of(s["id"]))
            good, cheaper = better(before, after, metric)
            mine = [c for c in w.changes_of(s["id"]) if c["kind"] != CODE and c.get("title") == p["title"]]
            target = mine[-1]["building"] if mine else ""
            fmt = (lambda v: "—" if v is None else f"{v:+.1f}") if metric == "quality" else \
                (lambda v: "—" if v is None else f"{v:+.0%}")
            moved = f"{metric} against the bare tool {fmt(before.get(metric))} → {fmt(after.get(metric))}"
            level = self._level(target) if target else autonomy.CHAINS
            if good and (level >= autonomy.FREE or (level >= autonomy.CLOCK and cheaper)):
                saved, wrong = w.save_changes(s["id"], by="orcs")
                self._say("Mechanic", f"{self.town.title_of(target)}: {p['title']} — saved ({moved}); on probation"
                          if saved else f"{self.town.title_of(target)}: {p['title']} — better, but not saved: "
                          f"{'; '.join(wrong[:1])}")
            elif good:
                self._say("Mechanic", f"{self.town.title_of(target)}: {p['title']} — better ({moved}); it waits "
                                      "on the virtual building for you: Save changes")
            else:
                for c in mine:
                    w.take_back(s["id"], c["id"])
                self._say("Mechanic", f"{w.title}: tried {p['title']} — not better ({moved}), taken back")
            self._finish(bid)

        try:
            lab.propose(w, s, after=proposed)
        except Exception:
            self._finish(bid)

    # -- the Alchemist ------------------------------------------------------------------------------------------------

    def _alchemist(self, w) -> None:
        bid = w.building_id
        tid = w.target
        if not tid or not w.first_of_type() or card_docs.load(tid) is not None or w.card \
                or self.spent + ASK_USD > self.budget():
            self._finish(bid)
            return
        self.busy = bid
        self.spent += ASK_USD
        name = catalog.TYPES[tid].title

        def laid(ok: bool) -> None:
            if not ok:
                self._finish(bid)
                return
            if self._level(w.first_of_type()) >= autonomy.FREE and not w.card_apply():
                self._say("Alchemist", f"{name}: its cards laid out so each size says what matters most — applied "
                                       "(Reset in the UX bench takes it back)")
            else:
                self._say("Alchemist", f"{name}: a new layout of its cards waits in the UX bench: Apply or Reset")
            self._finish(bid)

        try:
            w.card_ask(NIGHT_ASK, after=laid)
        except Exception:
            self._finish(bid)
