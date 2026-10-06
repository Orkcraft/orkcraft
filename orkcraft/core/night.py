"""Quiet hours, without a face: the Elders' advice on the orks' questions (realm/elders.py) and the
orks' own improvements of the camp with their probation (realm/evolution.py).

`Night` keeps what the hours remember (the advice, the questions already judged, tonight's counts)
and decides what goes next. The face runs the model calls on its worker threads, sends an answer
into a terminal, and shows the morning's words.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import json
import time

from orkcraft import autonomy
from orkcraft.core.town import Town
from orkcraft.realm import elders, evolution, fastpath, optimize, steward, weekly
from orkcraft.realm.buildings import TOWN_HALL
from orkcraft.realm.orcs import Alert

PROBATION_CHECK_S = 300.0  # how often the orks' changes on probation are looked at


class Night:
    def __init__(self, town: Town) -> None:
        self.town = town
        # 🏛 The Elders' advice on the orks' questions, by question mark (elders.mark).
        self.advice: dict[str, elders.Decision] = {}
        self.elders_seen: set[str] = set()
        self.elders_busy = False
        self.elders_count = 0
        self.quiet_since: str | None = None
        # 🔧 The orks' own self-improvement.
        self.evolve_busy = False
        self.evolve_tried: set[str] = set()
        self.evolve_count = 0
        self.probation_at = 0.0          # 0: never looked yet

    # -- the hours ------------------------------------------------------------------------------

    def tick(self, quiet: bool, now: dt.datetime | None = None) -> bool:
        """Quiet hours begin or go on (remembered from when); True when they just ended — the morning."""
        if quiet and self.quiet_since is None:
            self.quiet_since = (now or dt.datetime.now()).isoformat(timespec="seconds")
            return False
        if not quiet and self.quiet_since is not None:
            return True
        return False

    def morning(self) -> None:
        """The day begins: tonight's counts start again."""
        self.quiet_since, self.elders_count, self.evolve_count = None, 0, 0

    # -- 🏛 the Elders --------------------------------------------------------------------------

    def restore(self) -> None:
        """A restart keeps what the log knows: the advice still to follow, and tonight's judged questions
        (so they are not judged, paid for and counted twice)."""
        if self.town.demo:
            return
        night = elders.restore(self.town.repo_root, self.quiet_since)
        self.advice.update(night.advice)
        self.elders_seen |= night.seen
        self.elders_count = max(self.elders_count, night.count)

    def advice_for(self, alert: Alert) -> elders.Decision | None:
        d = self.advice.get(elders.mark(alert))
        return d if d is not None and d.advised else None

    def elders_state(self, alerts: list[Alert], quiet: bool, level: int) -> str:
        """The lamp on the Town Hall: `advice` (some waits for you), `watch` (quiet hours, they read the
        questions), `rest` (by day), `off` (autonomy ⛓️ Ask me), `full` (tonight's questions are used up)."""
        if any(self.advice_for(a) is not None for a in alerts):
            return "advice"
        if not autonomy.advises(level):
            return "off"
        if not quiet:
            return "rest"
        return "full" if self.elders_count >= elders.limits(self.town.repo_root)[0] else "watch"

    def next_question(self, alerts: list[Alert], quiet: bool, level: int) -> Alert | None:
        """One question at a time goes to the Elders: quiet hours, autonomy from 1, budget left. The
        one returned is taken: marked judged, counted, the Elders busy until `judged`."""
        town = self.town
        if (town.demo or self.elders_busy or not quiet or not autonomy.advises(level)
                or self.elders_count >= elders.limits(town.repo_root)[0]):
            return None
        budget = town.scroll.budget.gold_session_limit_usd
        if budget > 0 and town.snapshot.spent_usd >= budget:
            return None
        pending = [a for a in alerts if elders.qualifies(a) and elders.mark(a) not in self.elders_seen]
        if not pending:
            return None
        alert = pending[0]
        self.elders_seen.add(elders.mark(alert))
        self.elders_busy = True
        self.elders_count += 1
        return alert

    def judged(self, alert: Alert, decision: elders.Decision, who: str, alerts: list[Alert], quiet: bool,
               level: int) -> str | None:
        """The Elders' answer is in. At ⛓️‍💥 Free orks (autonomy.answers) they answer themselves: the key to
        send is returned — only while it is still quiet and the very same question still waits, and never
        when the Warder flagged the screen (⚠: that advice is the operator's to follow). Otherwise the
        advice is kept for the operator and None is returned. Logged either way."""
        self.elders_busy = False
        mark = elders.mark(alert)
        send = None
        if (decision.advised and not decision.warn and autonomy.answers(level) and quiet
                and any(elders.mark(a) == mark for a in alerts)):
            key = decision.key or ""
            send = key if key.isdigit() else f"{key}\r"
        else:
            self.advice[mark] = decision
        elders.log(self.town.repo_root, alert, decision, who, sent=send is not None)
        return send

    def morning_words(self, alerts: list[Alert]) -> list[str]:
        """What the Elders did while the operator was away."""
        answered = [r for r in elders.since(self.town.repo_root, self.quiet_since or "") if r.get("sent")]
        waiting = [a for a in alerts if self.advice_for(a) is not None]
        words = []
        if answered:
            words.append(f"{len(answered)} question(s) answered by the Elders — the Town Hall lists them")
        if waiting:
            words.append(f"{len(waiting)} have their advice — ! opens them, a follows it, A for all")
        return words

    # -- 🔧 the orks improve the camp themselves ------------------------------------------------

    def _freedom(self, c: dict) -> str | None:
        """The autonomy that rules a change: the Town Hall's for the Town retro's, else its building's."""
        b = self.town.scroll.building(TOWN_HALL if c["source"] == "weekly" else c["building"])
        return b.autonomy if b is not None else None

    def candidates(self, level: int) -> list[dict]:
        """What the daily proposal, the latest weekly report and the stewards left, that this level (or
        the building's own autonomy) lets the orks apply themselves and that was not applied or tried yet."""
        root = self.town.repo_root
        done = evolution.applied_keys(root)
        out: list[dict] = []
        for p in optimize.pending(root):
            out.append({"key": p.id, "change": p.action, "source": "daily", "building": p.building, "proposal": p,
                        "made": p.ts})
        report = weekly.latest(root)
        if report is not None and dt.datetime.fromisoformat(report.ts) > dt.datetime.now() - dt.timedelta(days=7):
            for item in report.items:
                if item.applicable and item.n not in report.applied and item.n not in report.declined:
                    key = (f"w{report.ts[:10]}-{item.n}" if item.change in optimize.ACTIONS
                           else f"weekly:{report.ts}:{item.n}")
                    out.append({"key": key, "change": item.change, "source": "weekly", "building": item.building,
                                "report": report, "item": item, "made": report.ts})
        for b in self.town.scroll.buildings:
            data = steward.load_report(root, b.id)
            for i, prop in enumerate((data or {}).get("proposals") or []):
                replay = prop.get("replay") or {}
                if prop.get("type") == "demote" and not replay.get("ready"):
                    continue
                out.append({"key": f"steward:{b.id}:{data.get('ts', '')}:{i}", "change": str(prop.get("type")),
                            "source": "steward", "building": b.id, "data": data, "index": i,
                            "made": str(data.get("ts") or "")})
        return [c for c in out if evolution.may_apply(c["change"], level, self._freedom(c), c["made"])
                and c["key"] not in done and c["key"] not in self.evolve_tried]

    def subject(self, c: dict) -> fastpath.Subject:
        """What the Council looks at for one change: the building, the ork or the road as it would be."""
        town, bid = self.town, c["building"]
        if c["source"] == "steward":
            prop = c["data"]["proposals"][c["index"]]
            if c["change"] in ("filter", "new_road"):
                return fastpath.Subject("road", bid, {"source": prop.get("from") or bid, "target": bid,
                                                      "event": prop.get("event", ""), "filter": prop.get("filter") or {}})
            b = town.scroll.building(bid)
            orc = b.garrison.handler(str(prop.get("orc"))) if b is not None else None
            data = {k: v for k, v in dataclasses.asdict(orc).items() if v is not None} if orc is not None else {"id": str(prop.get("orc"))}
            data.update({"kind": "chain", "chain": prop.get("chain") or []} if c["change"] == "demote"
                        else {"run": prop.get("run") or {}})
            return fastpath.Subject("agent", bid, {"orc": data})
        if c["source"] == "weekly" and c["change"] == "add_building":
            spec = weekly.new_spec(c["item"])
            return fastpath.Subject("building", spec["id"], spec)
        if c["source"] == "weekly" and c["change"] == "set_config":
            spec = dict(town.custom_specs.get(bid) or {})
            spec["config"] = {**(spec.get("config") or {}), str(c["item"].data["key"]): c["item"].data.get("value")}
            return fastpath.Subject("building", bid, spec)
        p = c.get("proposal")
        if p is None:
            item = c["item"]
            p = optimize.Proposal(c["key"], c["report"].ts, bid, item.change, str(item.data.get("target")),
                                  item.before, item.after, item.why)
            c["proposal"] = p
        if p.action == "script":
            return fastpath.Subject("building", bid, dict(town.custom_specs.get(bid) or {}), script=p.after)
        if p.target.startswith("orc:"):
            b = town.scroll.building(bid)
            orc = b.garrison.handler(p.target[4:]) if b is not None else None
            data = {k: v for k, v in dataclasses.asdict(orc).items() if v is not None} if orc is not None else {"id": p.target[4:]}
            data.update({"kind": "chain", "chain": json.loads(p.after), "orders": ""} if p.action == "chain"
                        else {"orders": p.after})
            return fastpath.Subject("agent", bid, {"orc": data})
        spec = dict(town.custom_specs.get(bid) or {})
        key = "steward_prompt" if p.target == "steward" else "orders"
        spec["config"] = {**(spec.get("config") or {}), key: p.after}
        return fastpath.Subject("building", bid, spec)

    @staticmethod
    def council_lets(verdict: fastpath.Verdict) -> bool:
        """The Council lets the orks apply a change themselves: no block, no objection, no Warder warning."""
        return not verdict.blocked and not verdict.objections and not verdict.of("warder")

    def next_change(self, quiet: bool, level: int, exhausted: bool) -> tuple[dict, fastpath.Subject] | None:
        """The next change the orks may try tonight, with what the Council will look at; the one
        returned is taken (tried, the orks busy until `changed`)."""
        if (self.town.demo or self.evolve_busy or not quiet or self.evolve_count >= evolution.MAX_PER_NIGHT
                or exhausted):                          # the level, and each building's autonomy: `candidates`
            return None
        candidates = self.candidates(level)
        if not candidates:
            return None
        c = candidates[0]
        self.evolve_tried.add(c["key"])
        try:
            subject = self.subject(c)
        except (KeyError, ValueError, TypeError, AttributeError):
            return None
        self.evolve_busy = True
        return c, subject

    def changed(self, ok: bool) -> None:
        self.evolve_busy = False
        if ok:
            self.evolve_count += 1

    def probation_due(self) -> bool:
        """Every few minutes (never in the demo): time to look at the changes on probation."""
        if self.town.demo or (self.probation_at and time.monotonic() - self.probation_at < PROBATION_CHECK_S):
            return False
        self.probation_at = time.monotonic()
        return True
