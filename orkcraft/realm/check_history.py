"""✅ Every check remembered, and tonight read against the last time (docs/design/check.md §8): a case is better or worse
than it was, not only within its budget or not. No face, no model.

    check_history.add(root, series, data)        one check's cases, a line of `.orkcraft/check/history.jsonl`
    check_history.since(root, series)            what changed in it against each case's last check: [{case, …, said}]
    check_history.night_key(now)                 the night a moment belongs to (its evening's date)

A case is worse when it passed fewer of its runs than last time, or its building's median time or tokens grew by more
than `MOVED` (a fifth); better the other way round. What moved less is the noise of a few runs, and is not said.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from orkcraft.realm import bench

FILE = bench.BENCH.parent / "check" / "history.jsonl"
MOVED = 0.2


def add(root: Path, series: str, data: dict) -> dict:
    """The check's cases as one line: {series, at, green, cases: {"<scenario>/<case>": {…}}}."""
    cases = {}
    for sc in data.get("scenarios") or []:
        for c in sc.get("cases") or []:
            if not c.get("runs"):
                continue
            cases[f"{sc.get('id')}/{c.get('case')}"] = {
                k: c.get(k) for k in ("ok", "runs", "building", "bare", "time", "spend", "spend_by", "seconds",
                                      "tokens", "cost", "score")}
    line = {"series": series, "at": dt.datetime.now().isoformat(timespec="seconds"), "green": bool(data.get("green")),
            "idle": (data.get("idle") or {}).get("calls"), "cases": cases}
    path = root / FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False, default=str) + "\n")
    return line


def read(root: Path) -> list[dict]:
    try:
        text = (root / FILE).read_text(encoding="utf-8")
    except OSError:
        return []
    out = []
    for row in text.splitlines():
        try:
            line = json.loads(row)
        except ValueError:
            continue
        if isinstance(line, dict):
            out.append(line)
    return out


def _share(new, old) -> float | None:
    try:
        return (float(new) - float(old)) / float(old) if old else None
    except (TypeError, ValueError):
        return None


def since(root: Path, series: str) -> list[dict]:
    """Each case of the check `series` against its last earlier check: [{"case", "was", "at", "dir", "said"}],
    `dir` "worse" or "better", only for what moved past the noise. The worse first."""
    lines = read(root)
    now = next((x for x in lines if x.get("series") == series), None)
    if now is None:
        return []
    earlier = [x for x in lines if x.get("series", "") < series]
    out = []
    for key, c in (now.get("cases") or {}).items():
        was = next((x for x in reversed(earlier) if key in (x.get("cases") or {})), None)
        if was is None:
            continue
        p = was["cases"][key]
        said, worse = [], None
        if c.get("runs") and p.get("runs"):
            share_now, share_was = (c.get("building") or 0) / c["runs"], (p.get("building") or 0) / p["runs"]
            if share_now < share_was:
                said.append(f"passed {c.get('building')}/{c['runs']} runs, was {p.get('building')}/{p['runs']}")
                worse = True
            elif share_now > share_was:
                said.append(f"passed {c.get('building')}/{c['runs']} runs, was {p.get('building')}/{p['runs']}")
                worse = False if worse is None else worse
        for label, k in (("time", "seconds"), ("tokens", "tokens")):
            moved = _share(c.get(k), p.get(k))
            if moved is not None and abs(moved) > MOVED:
                said.append(f"{label} {'+' if moved > 0 else '−'}{abs(moved):.0%}")
                if moved > 0:
                    worse = True
                elif worse is None:
                    worse = False
        if said:
            out.append({"case": key, "was": p, "at": was.get("at", ""), "dir": "worse" if worse else "better",
                        "said": ", ".join(said) + f" since {str(was.get('at', ''))[:10]}"})
    return sorted(out, key=lambda x: x["dir"] != "worse")


def night_key(now: dt.datetime | None = None) -> str:
    """The night a moment belongs to: its evening's date (02:00 on the 13th is the night of the 12th)."""
    return ((now or dt.datetime.now()) - dt.timedelta(hours=12)).date().isoformat()
