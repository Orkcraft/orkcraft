"""📜 A day read by the Elders (docs/design/improve-buildings.md §13): Improve, or the night, hands a day's logs to the
Mechanic (quality per token) and the Farseer (what the person needed); each reads the day's hotspots
(realm/hotspots.py: found by code, a few calls in full) and says what to change. A finding must cite a hotspot it
rests on: one that cites none, or one the day does not have, is dropped — no proof, no finding.

    day_review.run(root, day, ask, titles, decisions, dislikes)   a Review, kept in `.orkcraft/council/days/<day>.json`
    day_review.load(root, day)                                    the kept one, or None
    day_review.warchief_text(review)                              what the Warchief is asked to go through

`ask(name, prompt) -> (text, cost)` is the model seam (builders.ask on the main tool, in the GUI); a councillor whose
ask fails is said in `errors` and the other's findings stand. No face here: gui/day_review.py runs it.
"""
from __future__ import annotations

import datetime as dt
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable

from orkcraft.design import agents
from orkcraft.realm import hotspots

DIR = Path(".orkcraft") / "council" / "days"
WHO = ("mechanic", "farseer")
TITLES = {"mechanic": "the Mechanic", "farseer": "the Farseer"}
KINDS = ("setting", "prompt", "rule", "step", "tier", "road", "code", "drop")
MAX_FINDINGS = 6                          # each councillor's, at most

PROMPT = """{persona}

---

You read one day of Orkcraft, a town of AI agents: its buildings take work in, call AI tools, and pass work on. The
day is {day}. Code found its hotspots below; each has an id (H1, H2, …), what is wrong or costly, and an excerpt of
the call it rests on (its prompt's head and tail, its output).

{digest}

Say at most {most} findings, the most worth changing first. Each rests on one hotspot or more (their ids); a finding
without one is dropped. Each has one change, the cheapest that would fix it, of a kind among: {kinds}.
Answer with JSON only:
{{"findings": [{{"hotspots": ["H1"], "building": "<its id>", "what": "what is wrong, in one sentence",
"why": "why it matters: tokens, time, or what the person had to do", "change": {{"kind": "prompt",
"what": "exactly what to change, where"}}}}]}}
If nothing is worth changing, answer {{"findings": []}}."""


@dataclass
class Finding:
    who: str                              # mechanic | farseer
    building: str
    what: str
    why: str
    kind: str
    change: str
    hotspots: list[str] = field(default_factory=list)


@dataclass
class Review:
    day: str
    at: str = ""
    hotspots: list[dict] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    cost: float = 0.0
    errors: list[str] = field(default_factory=list)

    @property
    def said(self) -> str:
        """One line: what the Elders found in the day."""
        if not self.hotspots:
            return f"{self.day}: nothing in the logs worth a look"
        n = len(self.findings)
        return (f"{self.day}: {len(self.hotspots)} hotspot{'' if len(self.hotspots) == 1 else 's'}, "
                f"{n} change{'' if n == 1 else 's'} offered")


def prompt(who: str, day: str, digest: str) -> str:
    return PROMPT.format(persona=agents.persona(who), day=day, digest=digest, most=MAX_FINDINGS,
                         kinds=", ".join(KINDS))


def parse(who: str, text: str, known: set[str], buildings: set[str]) -> list[Finding]:
    """The findings of an answer that rest on hotspots the day has; the rest dropped."""
    from orkcraft.realm import builders
    data = builders.extract_json(text) or {}
    out = []
    for f in (data.get("findings") if isinstance(data, dict) else None) or []:
        if not isinstance(f, dict):
            continue
        cited = [str(h) for h in f.get("hotspots") or [] if str(h) in known]
        change = f.get("change") if isinstance(f.get("change"), dict) else {}
        what, how = str(f.get("what") or "").strip(), str(change.get("what") or "").strip()
        if not cited or not what or not how:
            continue
        kind = str(change.get("kind") or "").strip().lower()
        b = str(f.get("building") or "").strip()
        out.append(Finding(who, b if b in buildings else "", what[:400], str(f.get("why") or "").strip()[:400],
                           kind if kind in KINDS else "rule", how[:800], cited))
    return out[:MAX_FINDINGS]


def run(root: Path, day: str, ask: Callable[[str, str], tuple[str, float | None]], titles: dict[str, str],
        decisions: Callable[[str, str], list[dict]], dislikes: Callable[[str, str], list[dict]]) -> Review:
    """The day's hotspots, read by both councillors; kept, and returned. No hotspot: no model is asked."""
    spots = hotspots.find(root, day, titles, decisions, dislikes)
    review = Review(day, dt.datetime.now().isoformat(timespec="seconds"), [asdict(h) for h in spots])
    if spots:
        digest = hotspots.digest(spots)
        known, buildings = {h.id for h in spots}, {h.building for h in spots}
        for who in WHO:
            try:
                text, cost = ask(who, prompt(who, day, digest))
            except Exception as e:  # an AI tool that fails: said, the other councillor's findings stand
                review.errors.append(f"{TITLES[who]}: {str(e)[:200]}")
                continue
            review.cost = round(review.cost + float(cost or 0.0), 4)
            review.findings += parse(who, text, known, buildings)
    save(root, review)
    return review


def save(root: Path, review: Review) -> None:
    path = root / DIR / f"{review.day}.json"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(review), ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass


def load(root: Path, day: str) -> Review | None:
    try:
        data = json.loads((root / DIR / f"{day}.json").read_text(encoding="utf-8"))
        return Review(**{**data, "findings": [Finding(**f) for f in data.get("findings") or []]})
    except (OSError, ValueError, TypeError):
        return None


def warchief_text(review: Review, titles: dict[str, str]) -> str:
    """The findings, for the Warchief to offer one by one: apply or skip. A code change is written down, not made."""
    lines = []
    for f in review.findings:
        where = f"@{titles.get(f.building, f.building)}" if f.building else "the town"
        lines.append(f"- {where} — {TITLES[f.who]}: {f.what} ({f.why}) Change ({f.kind}): {f.change} "
                     f"[{', '.join(f.hotspots)}]")
    return (f"The Mechanic and the Farseer read the logs of {review.day} and found these. Go through them one by one: "
            "for each, offer the change as one I can apply or skip. A code change is not made here: say it, and that "
            "the Test bench can try it.\n" + "\n".join(lines))
