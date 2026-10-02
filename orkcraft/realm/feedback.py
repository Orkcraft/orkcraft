"""👍 / 👎 on a building's steward: what the operator thinks of its last result.

    👍  the last result becomes a reference (`references.jsonl`) — what good looks like
    👎  a questionnaire: what went wrong?
          inputs  what came in was broken → the buildings that fed it are penalised along the
                  roads, upstream: 1 for the nearest supplier, half for the next hop, a quarter
                  for the one after (the session's graph is the roads that delivered)
          logic   the building itself got it wrong → only it is penalised
        either way an incident is written (`incidents.jsonl`) with the output and the note

Everything lives in `.orkcraft/feedback/`: the last output of every building (what is rated), the
references, the incidents and `scores.json` ({building: {likes, dislikes, penalty}}), which the
self-improvement of stages 8–9 reads.
"""
from __future__ import annotations

import datetime as dt
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

DIR = Path(".orkcraft") / "feedback"
OUT_KEEP = 2000
CASCADE = (1.0, 0.5, 0.25)          # the penalty by hop upstream
KINDS = {"inputs": "the inputs were broken — what came in was wrong",
         "logic": "its own logic was wrong — the inputs were fine"}


@dataclass
class Incident:
    ts: str
    building: str
    kind: str                    # inputs | logic
    note: str
    output: str
    blamed: dict[str, float] = field(default_factory=dict)


def _dir(root: Path) -> Path:
    return root / DIR


def _now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def _append(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _tail(path: Path, limit: int) -> list[dict]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()[-limit:]
    except OSError:
        return []
    out = []
    for line in reversed(lines):
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


# -- what is rated ----------------------------------------------------------------------------------

def record_output(root: Path, building: str, event: str, value: str, source: str = "") -> None:
    """The building's latest result (and, for the cascade, who delivered into it this session)."""
    path = _dir(root) / "last" / f"{building}.json"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"ts": _now(), "event": event, "value": str(value)[:OUT_KEEP]},
                                   ensure_ascii=False), encoding="utf-8")
        _append(_dir(root) / building / "journal.jsonl", {"ts": _now(), "event": event, "chars": len(str(value))})
    except OSError:
        pass


def journal(root: Path, building: str, days: int = 7) -> dict:
    """The steward's journal: how the building was used and how well it did —
    its runs (the ledger), its results, 👍 / 👎 — counted by a script, no model."""
    from orkcraft.realm import metrics
    since = dt.datetime.now() - dt.timedelta(days=days)
    rows = [r for r in metrics._read(root / metrics.LEDGER, since) if r.get("building") == building]
    outs = [r for r in _tail(_dir(root) / building / "journal.jsonl", 10_000)
            if str(r.get("ts", "")) >= since.isoformat(timespec="seconds")]
    sc = scores(root).get(building, {})
    return {"runs": len(rows), "ok": sum(1 for r in rows if r.get("outcome") == "done"),
            "failed": sum(1 for r in rows if r.get("outcome") == "error"),
            "tokens": sum(int(r.get("tokens") or 0) for r in rows), "cost": round(sum(float(r.get("cost") or 0) for r in rows), 4),
            "results": len(outs), "events": sorted({str(r.get("event")) for r in outs}),
            "likes": int(sc.get("likes", 0)), "dislikes": int(sc.get("dislikes", 0)),
            "last": outs[0]["ts"] if outs else ""}


def record_delivery(root: Path, target: str, source: str) -> None:
    """A cart from `source` reached `target`: an edge of the session's graph."""
    path = _dir(root) / "session.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    edges = set(map(tuple, data.get("edges", [])))
    if (source, target) in edges:
        return
    edges.add((source, target))
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"since": data.get("since") or _now(), "edges": sorted(edges)}), encoding="utf-8")
    except OSError:
        pass


def start_session(root: Path) -> None:
    (_dir(root) / "session.json").unlink(missing_ok=True)


def last_output(root: Path, building: str) -> dict | None:
    try:
        data = json.loads((_dir(root) / "last" / f"{building}.json").read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


# -- the session's graph ----------------------------------------------------------------------------

def suppliers(root: Path, scroll, building: str, depth: int = len(CASCADE)) -> list[tuple[str, int]]:
    """(building, hop) upstream of `building`: the roads that delivered this session, else the roads."""
    try:
        edges = [tuple(e) for e in json.loads((_dir(root) / "session.json").read_text(encoding="utf-8"))["edges"]]
    except (OSError, ValueError, KeyError, TypeError):
        edges = []
    feeds: dict[str, set[str]] = {}
    for src, tgt in edges:
        feeds.setdefault(tgt, set()).add(src)
    if not edges and scroll is not None:
        for b in scroll.buildings:
            for r in b.roads:
                feeds.setdefault(b.id, set()).add(r.source)
    out, seen, frontier = [], {building}, [building]
    for hop in range(1, depth + 1):
        nxt = []
        for b in frontier:
            for src in sorted(feeds.get(b, ())):
                if src not in seen:
                    seen.add(src)
                    out.append((src, hop))
                    nxt.append(src)
        frontier = nxt
    return out


# -- scores -----------------------------------------------------------------------------------------

def scores(root: Path) -> dict[str, dict]:
    try:
        data = json.loads((_dir(root) / "scores.json").read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _bump(root: Path, changes: dict[str, dict[str, float]]) -> dict[str, dict]:
    data = scores(root)
    for bid, delta in changes.items():
        row = data.setdefault(bid, {"likes": 0, "dislikes": 0, "penalty": 0.0})
        for k, v in delta.items():
            row[k] = round(row.get(k, 0) + v, 3)
    path = _dir(root) / "scores.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return data


def like(root: Path, building: str) -> dict | None:
    """👍: the last result is a reference. None when there is nothing to rate yet."""
    out = last_output(root, building)
    if out is None:
        return None
    _append(_dir(root) / building / "references.jsonl", {"ts": _now(), **out})
    _bump(root, {building: {"likes": 1}})
    return out


def blame(root: Path, scroll, building: str, kind: str) -> dict[str, float]:
    """Who pays for a 👎: the building alone for its logic; its suppliers, by hop, for broken inputs."""
    if kind == "logic":
        return {building: 1.0}
    return {src: CASCADE[hop - 1] for src, hop in suppliers(root, scroll, building)}


def dislike(root: Path, scroll, building: str, kind: str, note: str = "") -> Incident:
    """👎 with the questionnaire's answer: the penalties and an incident."""
    kind = kind if kind in KINDS else "logic"
    blamed = blame(root, scroll, building, kind)
    changes: dict[str, dict[str, float]] = {b: {"penalty": p} for b, p in blamed.items()}
    changes.setdefault(building, {})["dislikes"] = 1
    _bump(root, changes)
    out = last_output(root, building) or {}
    incident = Incident(_now(), building, kind, note.strip()[:1000], str(out.get("value", ""))[:OUT_KEEP], blamed)
    _append(_dir(root) / "incidents.jsonl", asdict(incident))
    return incident


def incidents(root: Path, limit: int = 20) -> list[Incident]:
    rows = []
    for r in _tail(_dir(root) / "incidents.jsonl", limit):
        try:
            rows.append(Incident(**r))
        except TypeError:
            continue
    return rows


def references(root: Path, building: str, limit: int = 5) -> list[dict]:
    return _tail(_dir(root) / building / "references.jsonl", limit)
