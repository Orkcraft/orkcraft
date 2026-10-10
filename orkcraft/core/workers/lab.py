"""🧪 The Test bench as a building (docs/design/test-bench.md §2): its roads say what it tests and where its results go.

    a road in   from a building: that building is tested — its cases run in a copy of it with its own settings,
                beside the bare AI tool (core/bench.py); what it sends along the road is only noted
    a road out  to any building: each run's report goes there (`lab.report`), what its building missed
                (`lab.missed`), and the findings sent with Make tasks (`lab.finding`)

The runs, the reviews and the cases are the bench's (gui/bench.py drives them, a face being needed for its
processes and threads); this worker knows the roads, keeps what it heard and what it ran, and says it.
"""
from __future__ import annotations

import datetime as dt

from orkcraft import scroll as ts
from orkcraft.core.workers import Worker
from orkcraft.realm import bench, catalog, lexicon

HEARD = 20                       # carts from the buildings it tests it remembers


class LabWorker(Worker):
    TYPE = "lab"

    def start(self) -> None:
        self.heard: list[dict] = []          # what the buildings it tests sent: newest first
        self.last: dict = {}                 # building id → its last run here: {run, case, verdict, passed, at}
        self.chosen = ""                     # the building its window shows, when it tests more than one
        self._looked: set[str] = set()       # buildings whose kept runs were read

    def last_of(self, s: dict) -> dict | None:
        """The last run of a building it tests: its own, else the latest kept of its type (a road laid after a run)."""
        if s["id"] not in self.last and s["id"] not in self._looked:
            self._looked.add(s["id"])                    # read once: a card asks on every look of the town
            r = next(iter(bench.runs(self.repo_root, s["type"])), None)
            if r is not None:
                self.last[s["id"]] = self._line(r)
        return self.last.get(s["id"])

    # -- its roads -----------------------------------------------------------------------------------------

    def subjects(self) -> list[dict]:
        """The buildings it tests: those whose road comes in, each with its type and whether its runs exist yet."""
        from orkcraft.core import bench as runs
        me = self.town.scroll.building(self.building_id)
        out, seen = [], set()
        for road in (me.roads if me is not None else []):
            src = road.source
            if src in seen or src == self.building_id:
                continue
            spec = self.town.spec_of(src)
            if spec is None or self.town.scroll.building(src) is None:
                continue
            seen.add(src)
            kind = catalog.type_of(spec).id
            out.append({"id": src, "type": kind, "title": str(spec.get("title") or src), "word": lexicon.term(kind),
                        "can_run": kind in runs.TYPES})
        return out

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
        """The buildings its roads go to: where its reports and findings arrive."""
        return [b.id for b, _road in ts.outgoing(self.town.scroll, self.building_id)]

    # -- what comes and what it says ----------------------------------------------------------------------------

    def receive(self, payload, title: str, markdown: str) -> None:
        self.heard = ([{"from": payload.source, "title": title or payload.title,
                        "at": dt.datetime.now().isoformat(timespec="seconds"),
                        "text": (markdown or str(payload.value))[:400]}] + self.heard)[:HEARD]
        self.changed()

    @staticmethod
    def _line(r: bench.Report) -> dict:
        b = r.building
        return {"run": r.id, "case": r.case, "at": r.at, "passed": b.passed if b else None,
                "verdict": bench.verdict(b) if b else "the bare AI tool only",
                "bare": bench.verdict(r.bare) if r.bare else ""}

    def reported(self, building_id: str, r: bench.Report) -> None:
        """A run of a building it tests ended: its report down its roads, and what the building missed."""
        self.last[building_id] = self._line(r)
        word = lexicon.term(r.type)
        title = f"{self.town.title_of(building_id)} · {r.case} · {self._line(r)['verdict']}"
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
