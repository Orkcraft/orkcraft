"""The Wiki's quality check (docs/design/wiki-librarian.md §8): a part of `ScrollsWorker` (scrolls.py);
its methods run with the worker as `self`.

At every refresh the rules look over the pages (realm/wikicheck.py, cached until a page changes), and
`keep_quality` starts the librarian's lint when `check` says it is due: `weekly` (default) or `daily`
since the last check — the clock starts when the wiki is first seen, so a new setting never spends at
once —, `ingest` after each take-in, `off` never. A check counts from when it starts, so a failing one
is not retried before its time. `check_now` and `fix` (links and indexes, what the rules found) are the
person's. The state is `quality.json`: `seen` and `last`.
"""
from __future__ import annotations

import datetime as dt
import json

from orkcraft.realm import wikicheck

FIXABLE = ("link", "structure")


def _at(text: str) -> dt.datetime | None:
    try:
        return dt.datetime.fromisoformat(str(text)) if text else None
    except ValueError:
        return None


class QualityMixin:
    _rules_key: tuple = ()
    _rules: list = []
    _ingested = False                              # a take-in finished since the last check (`check: ingest`)
    quality_total = 0                              # the problems as of the last refresh (the card's)

    @property
    def check(self) -> str:
        return wikicheck.schedule_of(self.config)

    def _quality_file(self):
        return self.state_dir / "quality.json"

    def load_quality(self) -> dict:
        try:
            data = json.loads(self._quality_file().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        return data if isinstance(data, dict) else {}

    def _save_quality(self, data: dict) -> None:
        path = self._quality_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=1), encoding="utf-8")

    def rule_problems(self) -> list[wikicheck.Problem]:
        key = tuple((n.path, n.mtime) for n in self.pages)
        if key != self._rules_key:
            self._rules_key, self._rules = key, wikicheck.rule_problems(self.wiki_root)
        return self._rules

    def problems(self) -> list[wikicheck.Problem]:
        """What rules find now and what the last lint found, each once."""
        out, seen = [], set()
        for p in [*self.rule_problems(), *wikicheck.lint_problems(self.wiki_root)]:
            if (p.kind, p.page, p.text) not in seen:
                seen.add((p.kind, p.page, p.text))
                out.append(p)
        return out

    def keep_quality(self, now: dt.datetime | None = None) -> bool:
        """Start the scheduled check when it is due; True when it started."""
        now = now or self.clock()
        self.quality_total = len(self.problems()) if self.pages else 0
        state = self.load_quality()
        if not state.get("seen"):
            state["seen"] = now.isoformat(timespec="seconds")
            self._save_quality(state)
        if self.running or self.last_error or not self.pages:
            return False
        check = self.check
        due = (check == "ingest" and self._ingested) or \
            wikicheck.due(check, _at(state.get("last")) or _at(state.get("seen")), now)
        if not due or self.out_of_gold():
            return False
        return self._start_check("schedule" if check != "ingest" else "ingest", now)

    def check_now(self) -> bool:
        return self._start_check("manual", self.clock())

    def _start_check(self, trigger: str, now: dt.datetime) -> bool:
        started = self.lint(trigger)
        if started:
            self._ingested = False
            state = self.load_quality()
            state["last"] = now.isoformat(timespec="seconds")
            self._save_quality(state)
        return started

    def fix(self) -> bool:
        """The librarian fixes the links and indexes the rules found; True when it started."""
        problems = [p for p in self.rule_problems() if p.kind in FIXABLE]
        if not problems:
            self.toast("The rules find no broken links or indexes.", title="📜 Nothing to fix")
            return False
        if self.running or self.out_of_gold("the fix") or not self._prepare():
            return False
        return self._run("lint", wikicheck.fix_prompt(problems, sorted(self._protected())), "fix links and indexes",
                         "manual", None, f"wiki({self.topic}): fix links and indexes")

    def quality_view(self) -> dict:
        state = self.load_quality()
        problems = self.problems()
        last = _at(state.get("last"))
        nxt = wikicheck.next_at(self.check, last or _at(state.get("seen")))
        cost = None
        try:
            cost = next((j.cost_usd for j in self.log.read(30) if j.title.startswith("lint") and j.outcome == "done"), None)
        except (OSError, ValueError):
            pass
        return {"check": self.check, "last": f"{last:%Y-%m-%d %H:%M}" if last else "",
                "next": f"{nxt:%Y-%m-%d %H:%M}" if nxt else "", "cost": cost,
                "counts": wikicheck.counts(problems), "total": len(problems),
                "fixable": sum(1 for p in problems if p.by == "rules" and p.kind in FIXABLE),
                "problems": [p.as_dict() for p in problems[:100]]}
