"""👎 → a case (docs/design/check.md §7, step 2): a result the person disliked becomes a test case of its building, made
of what came into it, what it made and what the person said — so the evals grow from real failures, not only from
written ones. No face, no model.

    regressions.record_input(root, building, kind, value, source, title)   the last cart into a building (delivery)
    regressions.from_dislike(root, building, note, kind)    a 👎 kept as a case → the case, or None when nothing came in
    regressions.cases(root, building)                       the building's cases from 👎, oldest first

A case is a Test bench case (realm/lab_cases.py `new_case`): its input the cart that came in, its `entry` the
building, `source` "dislike", `why` what the person said and what it made then. A Test bench that tests the building
takes them in (core/workers/lab.py `take_regressions`). The input stays on this machine, as the feedback does.
"""
from __future__ import annotations

import datetime as dt
import json
import uuid
from pathlib import Path

DIR = Path(".orkcraft") / "feedback"
IN_KEEP = 6000                     # characters of a cart's value kept as a case's input
OUT_SHOWN = 300                    # of what it made, in the case's why


def _input_file(root: Path, building: str) -> Path:
    return root / DIR / "last" / f"{building}.in.json"


def record_input(root: Path, building: str, kind: str, value: str, source: str = "", title: str = "") -> None:
    try:
        path = _input_file(root, building)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"ts": dt.datetime.now().isoformat(timespec="seconds"), "kind": kind,
                                    "value": str(value)[:IN_KEEP], "source": source, "title": title},
                                   ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def last_input(root: Path, building: str) -> dict | None:
    try:
        data = json.loads(_input_file(root, building).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) and str(data.get("value") or "").strip() else None
    except (OSError, ValueError):
        return None


def _cases_file(root: Path, building: str) -> Path:
    return root / DIR / "cases" / f"{building}.jsonl"


def from_dislike(root: Path, building: str, note: str = "", kind: str = "logic", output: str = "") -> dict | None:
    """The 👎 kept as a case of the building; None when no cart came into it this session (nothing to run again).
    A 👎 for broken inputs is the suppliers' fault, not this building's: it makes no case here."""
    got = last_input(root, building)
    if got is None or kind == "inputs":
        return None
    day = dt.date.today().isoformat()
    first = " ".join(str(got.get("title") or got["value"]).split())[:60]
    said = " ".join(note.split())[:200]
    case = {"id": f"d{uuid.uuid4().hex[:6]}", "title": f"👎 {day}: {said or first}"[:120], "text": got["value"],
            "entry": building, "expect": [], "source": "dislike", "at": dt.datetime.now().isoformat(timespec="seconds"),
            "why": (f"Disliked on {day}" + (f": {said}" if said else "") +
                    (f". What it made then: {' '.join(output.split())[:OUT_SHOWN]}" if output.strip() else ""))[:300]}
    try:
        path = _cases_file(root, building)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(case, ensure_ascii=False) + "\n")
    except OSError:
        return None
    return case


def cases(root: Path, building: str) -> list[dict]:
    try:
        rows = _cases_file(root, building).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for row in rows:
        try:
            c = json.loads(row)
        except ValueError:
            continue
        if isinstance(c, dict) and c.get("id") and c.get("text"):
            out.append(c)
    return out
