"""👍 / 👎 on a building's steward: what the operator thinks of its last result.

    👍  the last result becomes a reference (`references.jsonl`) — what good looks like
    👎  a questionnaire: what went wrong?
          inputs  what came in was broken → the buildings that fed it are penalised along the
                  roads, upstream: 1 for the nearest supplier, half for the next hop, a quarter
                  for the one after (the session's graph is the roads that delivered)
          logic   the building itself got it wrong → only it is penalised
        either way an incident is written (`incidents.jsonl`) with the output and the note

Most of what the operator thinks is never pressed as 👍 / 👎: it is in what they do with a result.
`signal` keeps those too — an accepted, edited, sent-back or dropped cart in a Loot, the format of
an ork's file changed in a Lake, a pull request merged or closed, a change taken back with `Z`, a
result nobody opened. Each has a `source` and a `weight` (`WEIGHTS`): a 👍 / 👎 weighs 1, a quiet
signal less, so that one of them alone never moves a retro. A good one is a reference, a bad one
an incident, like the buttons'; readers add the weights (`liked`, `disliked`) and act from `ENOUGH`.

A 👎 weighs on whoever is to blame (`Incident.blamed`): for its own logic the building it was told
about; for broken inputs its suppliers — 1, ½, ¼ by hop, times the signal's weight — and not the
building itself, which only passed on what it got. The retros and probation read it that way, so a
supplier that keeps breaking what comes after it is the one they look at.

Everything lives in `.orkcraft/feedback/`: the last output of every building (what is rated), the
references, the incidents and `scores.json` ({building: {likes, dislikes, penalty, liked,
disliked, by}}: the buttons pressed, the penalty, the weighted sums and the weight by source),
which the retros read.
"""
from __future__ import annotations

import datetime as dt
import json
from orkcraft.realm.jobs import now_iso
from dataclasses import asdict, dataclass, field
from pathlib import Path

DIR = Path(".orkcraft") / "feedback"
OUT_KEEP = 2000
CASCADE = (1.0, 0.5, 0.25)          # the penalty by hop upstream
KINDS = {"inputs": "the inputs were broken — what came in was wrong",
         "logic": "its own logic was wrong — the inputs were fine"}
EXPLICIT = "explicit"
# What a signal weighs, by what the operator did (a 👍 / 👎 weighs 1).
WEIGHTS = {
    EXPLICIT: 1.0,
    "loot.accepted": 0.34,         # a held cart accepted as it was
    "loot.accepted_all": 0.1,      # … with ✓ Accept all, many at once
    "loot.filled": 0.34,           # accepted after only adding to it
    "loot.touched": 0.34,          # accepted after small fixes
    "loot.reshaped": 0.5,          # accepted after changing its format
    "loot.rewritten": 0.75,        # accepted after rewriting it
    "loot.rework": 0.5,            # sent back with a reason
    "loot.needs_you": 0.5,         # the rework rounds did not fix it
    "loot.dropped": 0.5,           # thrown away
    "loot.file_rejected": 0.34,    # one file of a held cart's branch rejected, the rest kept
    "lake.touched": 0.2,           # an ork's file: small fixes
    "lake.reshaped": 0.5,          # … its format changed
    "lake.rewritten": 0.5,         # … rewritten
    "pr.merged": 1.0,              # its pull request merged
    "pr.closed": 0.5,              # … closed without merging (a duplicate says nothing)
    "revert": 1.0,                 # a change of the orks taken back with Z
    "usage.ignored": 0.1,          # a result nobody opened in IGNORED_AFTER
}
# How a signal reads in the Town Hall and the retros.
LABELS = {EXPLICIT: "👍 / 👎", "loot.accepted": "accepted in a Loot", "loot.accepted_all": "accepted with all",
          "loot.filled": "filled in and accepted", "loot.touched": "fixed and accepted",
          "loot.reshaped": "reformatted and accepted", "loot.rewritten": "rewritten and accepted",
          "loot.rework": "sent back", "loot.needs_you": "rework did not fix it", "loot.dropped": "dropped in a Loot",
          "loot.file_rejected": "a file of it rejected in a Loot",
          "lake.touched": "fixed in a Lake", "lake.reshaped": "reformatted in a Lake", "lake.rewritten": "rewritten in a Lake",
          "pr.merged": "pull request merged", "pr.closed": "pull request closed", "revert": "taken back with Z",
          "usage.ignored": "nobody opened it"}
# What says the result was bad, not that it was not needed: a result nobody opened is about use
# (the Town retro may remove the building), never a reason to spend more on its quality.
NOT_QUALITY = frozenset({"usage.ignored"})
STRONG = frozenset({EXPLICIT, "pr.merged"})     # likes that shield a building from a thrift retro
AUTHOR_KINDS = frozenset({"agent", "hybrid", "task"})   # hops that write; a team reviews, a chain or script carries
ENOUGH = 1.0                       # the weight from which readers treat signals as a 👍 / 👎
# Why a cart goes back, offered as chips (the reason is still free text): the tag, the label, and
# whether it blames the inputs (the hops before the maker) or the maker's own logic.
REASONS = (("wrong", "did the wrong thing", "logic"), ("incomplete", "incomplete", "logic"),
           ("format", "wrong format or style", "logic"), ("facts", "facts are wrong", "logic"),
           ("inputs", "what came in was wrong", "inputs"), ("cost", "too expensive for what it is", "logic"))


@dataclass
class Incident:
    ts: str
    building: str
    kind: str                    # inputs | logic
    note: str
    output: str
    blamed: dict[str, float] = field(default_factory=dict)
    source: str = EXPLICIT       # what the operator did (WEIGHTS)
    weight: float = 1.0
    tag: str = ""                # a reason chip (REASONS)
    edit: str = ""               # the person's edit of the output, as a diff

    def share(self, building: str) -> float:
        """What this incident weighs on `building`: its part of the blame. For broken inputs that is
        the suppliers', by the cascade, and not the building it was told about; with nobody blamed
        (no supplier known) the building itself pays."""
        if self.blamed:
            return float(self.blamed.get(building, 0.0))
        return self.weight if building == self.building else 0.0

    def blames(self, building: str) -> bool:
        return self.share(building) > 0


def _dir(root: Path) -> Path:
    return root / DIR


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
        path.write_text(json.dumps({"ts": now_iso(), "event": event, "value": str(value)[:OUT_KEEP]},
                                   ensure_ascii=False), encoding="utf-8")
        _append(_dir(root) / building / "journal.jsonl", {"ts": now_iso(), "event": event, "chars": len(str(value))})
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
        path.write_text(json.dumps({"since": data.get("since") or now_iso(), "edges": sorted(edges)}), encoding="utf-8")
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


def _weighed(changes: dict[str, dict[str, float]], building: str, source: str, weight: float, good: bool) -> None:
    """`liked` / `disliked` as the readers count them (a result nobody opened is in `by` only)."""
    row = changes.setdefault(building, {})
    if source not in NOT_QUALITY:
        row["liked" if good else "disliked"] = row.get("liked" if good else "disliked", 0) + weight
    row[f"by.{source}"] = row.get(f"by.{source}", 0) + (weight if good else -weight)


def _bump(root: Path, changes: dict[str, dict[str, float]]) -> dict[str, dict]:
    """Add `changes` to the scores; a `by.<source>` key goes into the row's `by` (the weight by source)."""
    data = scores(root)
    for bid, delta in changes.items():
        row = data.setdefault(bid, {"likes": 0, "dislikes": 0, "penalty": 0.0})
        for k, v in delta.items():
            if k.startswith("by."):
                by = row.setdefault("by", {})
                by[k[3:]] = round(by.get(k[3:], 0) + v, 3)
            else:
                row[k] = round(row.get(k, 0) + v, 3)
    path = _dir(root) / "scores.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return data


def like(root: Path, building: str, out: dict | None = None) -> dict | None:
    """👍: the last result (or `out`, a past one the Town retro asked about) is a reference. None
    when there is nothing to rate yet."""
    out = out if out is not None else last_output(root, building)
    if out is None:
        return None
    _append(_dir(root) / building / "references.jsonl", {"ts": now_iso(), **out})
    changes = {building: {"likes": 1}}
    _weighed(changes, building, EXPLICIT, 1.0, True)
    _bump(root, changes)
    return out


def blame(root: Path, scroll, building: str, kind: str) -> dict[str, float]:
    """Who pays for a 👎: the building alone for its logic; its suppliers, by hop, for broken inputs."""
    if kind == "logic":
        return {building: 1.0}
    return {src: CASCADE[hop - 1] for src, hop in suppliers(root, scroll, building)}


def dislike(root: Path, scroll, building: str, kind: str, note: str = "", out: dict | None = None) -> Incident:
    """👎 with the questionnaire's answer: the penalties and an incident (on its last result, or `out`)."""
    kind = kind if kind in KINDS else "logic"
    blamed = blame(root, scroll, building, kind) or {building: 1.0}     # nobody feeds it: only it pays
    changes: dict[str, dict[str, float]] = {b: {"penalty": p} for b, p in blamed.items()}
    changes.setdefault(building, {})["dislikes"] = 1
    for b, p in blamed.items():                                          # the 👎 weighs on whoever is to blame
        _weighed(changes, b, EXPLICIT, p, False)
    _bump(root, changes)
    out = (out if out is not None else last_output(root, building)) or {}
    incident = Incident(now_iso(), building, kind, note.strip()[:1000], str(out.get("value", ""))[:OUT_KEEP], blamed)
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


def rated_since(root: Path, ts: str) -> bool:
    """Did the operator rate anything since `ts` (an ISO time) — a 👍 / 👎, or what they did with
    results weighing as much (`ENOUGH`)?"""
    total = sum(i.weight for i in incidents(root, 1000) if str(i.ts) >= ts and i.source not in NOT_QUALITY)
    for path in _dir(root).glob("*/references.jsonl"):
        total += sum(_weight(r) for r in _tail(path, 200) if str(r.get("ts", "")) >= ts)
    return total >= ENOUGH - 1e-9


def _weight(ref: dict) -> float:
    try:
        return float(ref.get("weight", 1.0))
    except (TypeError, ValueError):
        return 1.0


def liked(root: Path, building: str, since: str = "", strong: bool = False) -> float:
    """The weight of what was liked of `building` since `since`: 👍 1 each, quiet signals less;
    `strong`: only 👍 and merged pull requests (`STRONG`)."""
    return round(sum(_weight(r) for r in references(root, building, 1000) if str(r.get("ts", "")) > since
                     and (not strong or r.get("source", EXPLICIT) in STRONG)), 3)


def disliked(root: Path, building: str, since: str = "", rows: list[Incident] | None = None,
             quality: bool = False) -> float:
    """What the incidents since `since` weigh on `building` — the ones told about it for its own
    logic, and its part of the cascade when it fed broken inputs to another (`Incident.share`;
    `rows`: incidents already read).
    A result nobody opened is not a dislike (`NOT_QUALITY`); `quality`: nor is "too expensive" —
    the reasons to make a 💎 building better, which spends more, are about what it made, not its cost."""
    rows = rows if rows is not None else incidents(root, 1000)
    return round(sum(i.share(building) for i in rows if i.ts >= since and i.source not in NOT_QUALITY
                     and not (quality and i.tag == "cost")), 3)


def fed_broken(root: Path, building: str, since: str = "", rows: list[Incident] | None = None) -> float:
    """What `building` carries since `since` for the broken inputs it fed others: its part of the
    cascade of incidents told about a building after it (`rows`: incidents already read)."""
    rows = rows if rows is not None else incidents(root, 1000)
    return round(sum(i.share(building) for i in rows if i.ts >= since and i.kind == "inputs"
                     and i.building != building and i.source not in NOT_QUALITY), 3)


def blaming(root: Path, building: str, since: str = "", limit: int = 1000) -> list[Incident]:
    """The incidents since `since` that weigh on `building`, newest first (not results nobody opened)."""
    return [i for i in incidents(root, limit) if i.ts >= since and i.blames(building) and i.source not in NOT_QUALITY]


def references(root: Path, building: str, limit: int = 5) -> list[dict]:
    return _tail(_dir(root) / building / "references.jsonl", limit)


def _rank(ref: dict) -> int:
    """How good an example a reference is: the operator's own version or a 👍 first, a merged pull
    request next, a quiet acceptance last."""
    source = ref.get("source", EXPLICIT)
    if source == EXPLICIT or (source.startswith("loot.") and _weight(ref) == 0):
        return 0
    return 1 if source in STRONG else 2


def examples(root: Path, building: str, limit: int = 3) -> list[dict]:
    """The references to show an ork's prompt as what good looks like: the best kind first, the
    newest within a kind — so a stream of quiet acceptances never pushes out a 👍 or a correction."""
    rows = references(root, building, 200)                      # newest first
    return sorted(rows, key=_rank)[:limit]


# -- what the operator does with results ----------------------------------------------------------

def _hops(trail) -> list[str]:
    """The buildings of a trail of `pipes.Hop`s or their dicts, in order."""
    return [h.building if hasattr(h, "building") else str((h or {}).get("building", "")) for h in trail or ()]


def _kinds(trail) -> list[str]:
    return [h.kind if hasattr(h, "kind") else str((h or {}).get("kind", "")) for h in trail or ()]


def maker(trail, fallback: str = "") -> str:
    """The building that wrote a cart: the last hop of its trail that writes (an agent, a hybrid, a
    War Tent task) — not a Clan Fire that reviewed it or a chain that carried it after — else its
    last hop, else `fallback`. A cart with no trail was made by no ork: "" unless `fallback`."""
    hops, kinds = _hops(trail), _kinds(trail)
    for b, k in zip(reversed(hops), reversed(kinds)):
        if b and k in AUTHOR_KINDS:
            return b
    return next((b for b in reversed(hops) if b), fallback)


def trail_blame(trail, made_by: str, kind: str) -> dict[str, float]:
    """Who pays, read from the cart's own trail rather than the session's roads: the maker for its
    logic; for broken inputs the buildings before it, the nearest first, by `CASCADE`."""
    if kind != "inputs":
        return {made_by: 1.0}
    hops = _hops(trail)
    if made_by in hops:
        hops = hops[:len(hops) - 1 - hops[::-1].index(made_by)]        # what came before its last hop
    before: list[str] = []
    for b in reversed(hops):
        if b and b != made_by and b not in before:
            before.append(b)
    return {b: CASCADE[i] for i, b in enumerate(before[:len(CASCADE)])} or {made_by: 1.0}


def signal(root: Path, building: str, good: bool, source: str, value: str | None = None, note: str = "",
           tag: str = "", kind: str = "logic", blamed: dict[str, float] | None = None, edit: str = "",
           weight: float | None = None) -> Incident | dict | None:
    """What the operator did with a result of `building`, kept like a 👍 / 👎 of `WEIGHTS[source]`:
    a good one is a reference (`value`, else its last result), a bad one an incident whose penalty,
    `blamed` (default: the building), is scaled by the weight. None when there is nothing to keep."""
    if not building:
        return None
    w = float(weight if weight is not None else WEIGHTS.get(source, 0.5))
    if value is None:
        value = str((last_output(root, building) or {}).get("value", ""))
    changes: dict[str, dict[str, float]] = {}
    if good:
        if not value:
            return None
        ref = {"ts": now_iso(), "event": source, "value": str(value)[:OUT_KEEP], "source": source, "weight": w}
        if note:
            ref["note"] = note[:1000]
        _append(_dir(root) / building / "references.jsonl", ref)
        _weighed(changes, building, source, w, True)
        _bump(root, changes)
        return ref
    shares = blamed or {building: 1.0}
    penalties = {b: round(p * w, 3) for b, p in shares.items()}
    for b, p in penalties.items():
        changes.setdefault(b, {})["penalty"] = p
        _weighed(changes, b, source, p, False)
    _bump(root, changes)
    incident = Incident(now_iso(), building, kind if kind in KINDS else "logic", note.strip()[:1000],
                        str(value)[:OUT_KEEP], penalties, source, w, tag, edit[:OUT_KEEP])
    _append(_dir(root) / "incidents.jsonl", asdict(incident))
    return incident


def reason_tag(text: str) -> tuple[str, str]:
    """(tag, kind) of a reason that starts with a chip's label (`REASONS`); ("", "logic") otherwise."""
    low = (text or "").strip().lower()
    for tag, label, kind in REASONS:
        if low.startswith(label) or low.startswith(f"[{tag}]"):
            return tag, kind
    return "", "logic"


# -- results nobody opened ------------------------------------------------------------------------

VIEWS = "views.json"
IGNORED_AFTER = dt.timedelta(hours=24)
VIEWS_KEEP = 200


def _views(root: Path) -> list[dict]:
    try:
        rows = json.loads((_dir(root) / VIEWS).read_text(encoding="utf-8"))
        return rows if isinstance(rows, list) else []
    except (OSError, ValueError):
        return []


def _save_views(root: Path, rows: list[dict]) -> None:
    try:
        path = _dir(root) / VIEWS
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rows[-VIEWS_KEEP:], ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def await_view(root: Path, viewer: str, made_by: str, title: str = "") -> None:
    """A result of `made_by` is waiting in `viewer` (a Lake, a Loot's store) for the operator to look."""
    if not viewer or not made_by or made_by == viewer:
        return
    rows = _views(root)
    rows.append({"ts": now_iso(), "viewer": viewer, "by": made_by, "title": str(title)[:120]})
    _save_views(root, rows)


def viewed(root: Path, viewer: str) -> int:
    """The operator opened `viewer`: what waited there was seen. Returns how many."""
    rows = _views(root)
    left = [r for r in rows if r.get("viewer") != viewer]
    if len(left) != len(rows):
        _save_views(root, left)
    return len(rows) - len(left)


def sweep_unseen(root: Path, now: dt.datetime | None = None) -> list[dict]:
    """Results that waited longer than `IGNORED_AFTER` and were never opened: a light 👎 each
    (`usage.ignored`) on the building that made them. Returns them."""
    now = now or dt.datetime.now()
    edge = (now - IGNORED_AFTER).isoformat(timespec="seconds")
    rows = _views(root)
    old = [r for r in rows if str(r.get("ts", "")) < edge]
    if not old:
        return []
    _save_views(root, [r for r in rows if str(r.get("ts", "")) >= edge])
    for r in old:
        signal(root, str(r.get("by", "")), False, "usage.ignored", value=str(r.get("title", "")),
               note=f"nobody opened it in {r.get('viewer')} for a day")
    return old


# -- an orc's own 👍 / 👎 ----------------------------------------------------------------------------

def orc_key(building: str, orc_id: str) -> str:
    """Scores of an orc sit beside its building's, under `<building>/<orc>`."""
    return f"{building}/{orc_id}"


def rate_orc(root: Path, building: str, orc_id: str, good: bool, note: str = "") -> dict[str, dict]:
    """👍 / 👎 on an orc's work: counted for the orc; a 👎 with a note is an incident too."""
    key = orc_key(building, orc_id)
    if not good:
        _append(_dir(root) / "incidents.jsonl",
                asdict(Incident(now_iso(), key, "logic", note.strip()[:1000], "", {key: 1.0})))
    return _bump(root, {key: {"likes": 1} if good else {"dislikes": 1}})
