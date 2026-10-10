"""🧪 The Test bench as a building (docs/design/test-bench.md §2): its roads say what it tests and where its results go.

    a road in   from a building: that building is tested — its cases run in a copy of it with its own settings,
                beside the bare AI tool (core/bench.py); what it sends along the road is only noted
    a chain     a road out carrying `lab.case` into a building, and a road back in from a building that the
                first one leads to: every building on the way is tested as one — a case's input goes into the
                first, what comes out of the last is checked (core/bench_kits.py `run_chain`)
    a road out  carrying anything else: each run's report goes there (`lab.report`), what its building missed
                (`lab.missed`), and the findings sent with Make tasks (`lab.finding`)

The runs, the reviews and the cases are the bench's (gui/bench.py drives them, a face being needed for its
processes and threads); this worker knows the roads, keeps what it heard and what it ran, and says it.
"""
from __future__ import annotations

import datetime as dt

from orkcraft import scroll as ts
from orkcraft.core.workers import Worker
from orkcraft.realm import bench, catalog, lab_cases, lexicon

HEARD = 20                       # carts from the buildings it tests it remembers
TEXT_KEPT = 8000                 # of each cart: what a chain sent is what its run checks
CHAIN = "chain:"                 # a chain's id: `chain:<first>:<last>`
CASE_EVENT = "lab.case"          # the road into a chain it tests


class LabWorker(Worker):
    TYPE = "lab"

    def start(self) -> None:
        self.heard: list[dict] = []          # what the buildings it tests sent: newest first
        self.last: dict = {}                 # building id → its last run here: {run, case, verdict, passed, at}
        self.chosen = ""                     # the building its window shows, when it tests more than one
        self._looked: set[str] = set()       # buildings whose kept runs were read
        self.state = lab_cases.load(self.state_dir)   # its goal, settings, cases, results, proposals (realm/lab_cases.py)

    # -- its own work: a goal, its cases, what they said, what to change ------------------------------------------

    def keep(self) -> None:
        lab_cases.save(self.state_dir, self.state)
        self.changed()

    def set_goal(self, goal: str) -> None:
        self.state["goal"] = " ".join(goal.split())[:1000]
        self.keep()

    def set_settings(self, **values) -> None:
        self.state["settings"].update({k: v for k, v in values.items() if k in lab_cases.blank()["settings"]})
        self.keep()

    def cases_of(self, subject_id: str) -> list[dict]:
        return list(self.state["cases"].get(subject_id) or [])

    def add_cases(self, subject_id: str, cases: list[dict]) -> int:
        have = self.state["cases"].setdefault(subject_id, [])
        room = lab_cases.MAX_CASES - len(have)
        have.extend(cases[:max(room, 0)])
        self.keep()
        return min(len(cases), max(room, 0))

    def remove_case(self, subject_id: str, case_id: str) -> bool:
        have = self.state["cases"].get(subject_id) or []
        kept = [c for c in have if c["id"] != case_id]
        if len(kept) == len(have):
            return False
        self.state["cases"][subject_id] = kept
        self.state["results"].get(subject_id, {}).pop(case_id, None)
        self.keep()
        return True

    def results_of(self, subject_id: str) -> dict:
        return dict(self.state["results"].get(subject_id) or {})

    def set_proposals(self, subject_id: str, items: list[dict]) -> None:
        self.state["proposals"][subject_id] = {"at": dt.datetime.now().isoformat(timespec="seconds"),
                                              "goal": self.state["goal"], "items": items}
        self.keep()

    def entries(self, subject: dict) -> list[dict]:
        """Where a case's input may go in: a chain's buildings that take a cart (its first one first); a building
        alone, itself."""
        from orkcraft.realm import catalog_reference
        ids = subject.get("chain") or [subject["id"]]
        out = []
        for n, bid in enumerate(ids):
            kind = self._type(bid)
            takes = catalog_reference.TAKES.get(kind, "")
            if n == 0 or kind in catalog_reference.ACCEPTS:
                out.append({"id": bid, "title": self.town.title_of(bid), "word": lexicon.term(kind), "type": kind,
                            "takes": takes or ("a message, as from mail" if kind == "watchtower" else "")})
        return out

    def flow_spec(self, subject: dict) -> dict:
        """The scheme a copy stands for a case of its own: a chain as it is; a building alone as a chain of one whose
        every event comes back."""
        if subject["type"] == CHAIN.rstrip(":"):
            return self.chain_spec(subject)
        bid, kind = subject["id"], subject["type"]
        events = [e.id for e in catalog.TYPES[kind].events] if kind in catalog.TYPES else []
        return {"id": bid, "buildings": [{"id": bid, "type": kind, "title": self.town.title_of(bid),
                                          "config": dict((self.town.spec_of(bid) or {}).get("config") or {})}],
                "roads": [], "first": bid, "last": bid, "back_events": events, "back_filter": {},
                "about": f"{self.town.title_of(bid)} ({lexicon.term(kind)}: "
                         f"{catalog.TYPES[kind].summary.split(';')[0] if kind in catalog.TYPES else ''})"}

    def last_of(self, s: dict) -> dict | None:
        """The last run of a building it tests: its own, else the latest kept of its type (a road laid after a run)."""
        if s["id"] not in self.last and s["id"] not in self._looked:
            self._looked.add(s["id"])                    # read once: a card asks on every look of the town
            r = next((x for x in bench.runs(self.repo_root, s["type"])
                      if s["type"] != CHAIN.rstrip(":") or x.subject == s["id"]), None)
            if r is not None:
                self.last[s["id"]] = self._line(r)
        return self.last.get(s["id"])

    # -- its roads -----------------------------------------------------------------------------------------

    def subjects(self) -> list[dict]:
        """What it tests: each chain (a road out with `lab.case` to its first building, a road back from its last),
        then each building whose road comes in and ends no chain; with its type and whether it can run yet."""
        from orkcraft.core import bench as runs
        me = self.town.scroll.building(self.building_id)
        sources = []
        for road in (me.roads if me is not None else []):
            if road.source not in sources and road.source != self.building_id and self._standing(road.source):
                sources.append(road.source)
        out, ended = [], set()
        for first in self.chain_starts():
            ahead = self._ahead(first)
            for last in sources:
                if last not in ahead:
                    continue
                chain = self._between(first, last, ahead)
                if len(chain) < 2:
                    continue                            # a chain of one is the building itself
                ended.add(last)
                titles = [self.town.title_of(b).split(" ", 1)[-1] for b in chain]
                out.append({"id": f"{CHAIN}{first}:{last}", "type": CHAIN, "chain": chain, "first": first,
                            "last": last, "title": " → ".join(titles), "word": "chain",
                            "first_type": self._type(first), "can_run": True})
        for src in sources:
            if src in ended:
                continue
            kind = self._type(src)
            out.append({"id": src, "type": kind, "title": str((self.town.spec_of(src) or {}).get("title") or src),
                        "word": lexicon.term(kind), "can_run": kind in runs.TYPES})
        return out

    def _standing(self, bid: str) -> bool:
        return self.town.spec_of(bid) is not None and self.town.scroll.building(bid) is not None

    def _type(self, bid: str) -> str:
        return catalog.type_of(self.town.spec_of(bid)).id

    def chain_starts(self) -> list[str]:
        """The buildings its `lab.case` roads go into: where a chain it tests begins."""
        return [b.id for b, road in ts.outgoing(self.town.scroll, self.building_id)
                if road.event == CASE_EVENT and self._standing(b.id)]

    def _ahead(self, first: str) -> set[str]:
        """Every building `first` leads to along roads, itself included, never through the Test bench."""
        seen, todo = {first}, [first]
        while todo:
            for b, _road in ts.outgoing(self.town.scroll, todo.pop()):
                if b.id not in seen and b.id != self.building_id:
                    seen.add(b.id)
                    todo.append(b.id)
        return seen

    def _between(self, first: str, last: str, ahead: set[str]) -> list[str]:
        """The buildings on a way from `first` to `last`, in the order the roads reach them."""
        behind, todo = {last}, [last]
        while todo:
            for road in ts.incoming(self.town.scroll, todo.pop()):
                if road.source in ahead and road.source not in behind:
                    behind.add(road.source)
                    todo.append(road.source)
        on = ahead & behind
        order, todo, seen = [], [first], {first}
        while todo:                                     # breadth first from the first: the order a cart goes
            bid = todo.pop(0)
            order.append(bid)
            for b, _road in ts.outgoing(self.town.scroll, bid):
                if b.id in on and b.id not in seen:
                    seen.add(b.id)
                    todo.append(b.id)
        return order

    def chain_spec(self, subject: dict) -> dict:
        """What a copy needs to stand a chain: its buildings with their settings, the roads between them, and the
        road its last building sends back to the Test bench."""
        chain = subject["chain"]
        buildings = [{"id": b, "type": self._type(b), "title": self.town.title_of(b),
                      "config": dict((self.town.spec_of(b) or {}).get("config") or {})} for b in chain]
        roads = [{"target": b, "source": r.source, "event": r.event, "filter": dict(r.filter or {}), "handler": r.handler}
                 for b in chain for r in ts.incoming(self.town.scroll, b) if r.source in chain]
        back = next((r for r in ts.incoming(self.town.scroll, self.building_id) if r.source == subject["last"]), None)
        about = "; ".join(f"{self.town.title_of(b['id'])} ({lexicon.term(b['type'])}: "
                          f"{catalog.TYPES[b['type']].summary.split(';')[0] if b['type'] in catalog.TYPES else ''})"
                          for b in buildings)
        return {"id": subject["id"], "buildings": buildings, "roads": roads, "first": chain[0], "last": subject["last"],
                "back_event": back.event if back else "", "back_filter": dict(back.filter or {}) if back else {},
                "about": about}

    def subject(self) -> dict | None:
        found = self.subjects()
        return next((s for s in found if s["id"] == self.chosen), found[0] if found else None)

    def pick(self, building_id: str) -> bool:
        if not any(s["id"] == building_id for s in self.subjects()):
            return False
        self.chosen = building_id
        self.changed()
        return True

    def targets(self) -> list[str]:
        """The buildings its roads go to with its results (not the `lab.case` road into a chain it tests)."""
        return [b.id for b, road in ts.outgoing(self.town.scroll, self.building_id) if road.event != CASE_EVENT]

    # -- what comes and what it says ----------------------------------------------------------------------------

    def receive(self, payload, title: str, markdown: str) -> None:
        self.heard = ([{"from": payload.source, "title": title or payload.title,
                        "at": dt.datetime.now().isoformat(timespec="seconds"),
                        "text": (markdown or str(payload.value))[:TEXT_KEPT]}] + self.heard)[:HEARD]
        self.changed()

    @staticmethod
    def _line(r: bench.Report) -> dict:
        b = r.building
        return {"run": r.id, "case": r.case, "at": r.at, "passed": b.passed if b else None,
                "verdict": bench.verdict(b) if b else "the bare AI tool only",
                "bare": bench.verdict(r.bare) if r.bare else ""}

    def reported(self, building_id: str, r: bench.Report) -> None:
        """A run of a building it tests ended: its report down its roads, and what the building missed; a case of
        its own keeps what it said against the bare AI tool."""
        self.last[building_id] = self._line(r)
        if any(c["id"] == r.case for c in self.cases_of(building_id)):
            self.state["results"].setdefault(building_id, {})[r.case] = lab_cases.result_of(r)
            lab_cases.save(self.state_dir, self.state)
        word = "chain" if r.type == CHAIN.rstrip(":") else lexicon.term(r.type)
        name = next((s["title"] for s in self.subjects() if s["id"] == building_id), self.town.title_of(building_id))
        title = f"{name} · {r.case} · {self._line(r)['verdict']}"
        self.emit("lab.report", bench.analysis(r, word), title, ref=f"{self.building_id}:{r.id}")
        missed = [x for x in (r.building.checks if r.building else []) if not x.get("ok")]
        if r.building is not None and (missed or r.building.error or r.building.passed is False):
            lines = [f"- {x['name']}" + (f" — {x['detail']}" if x.get("detail") else "") for x in missed]
            why = r.building.error or (r.building.check_tail[-600:] if r.building.check_tail else "")
            body = f"**{word}** missed on **{r.case}** (run {r.id}).\n\n" + "\n".join(lines) + (f"\n\n{why}" if why else "")
            self.emit("lab.missed", body, f"{word} missed: {r.case}", ref=f"{self.building_id}:{r.id}")
        self.changed()

    def finding(self, title: str, body: str) -> bool:
        """A finding sent with Make tasks, down its roads; False when no road takes it."""
        return bool(self.emit("lab.finding", body, title))

    def mini_status(self) -> list[str]:
        s = self.subject()
        if s is None:
            return ["No building to test: pull a road from one into it"]
        last = self.last_of(s)
        return [f"Tests {s['title']}"] + ([f"{last['case']}: {last['verdict']}"] if last else ["No run yet"])

    def status(self) -> str:
        s = self.subject()
        last = self.last_of(s) if s else None
        return "ERROR" if last and last.get("passed") is False else ""
