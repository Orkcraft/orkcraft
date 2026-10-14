"""🧪 What a Test bench's runs said, to hand over for an analysis (docs/design/test-bench.md §10.1): the latest runs of
what it tests side by side (each case's repeats pooled), every run in full with its model calls, and the
recommendations (the tech reviews of its buildings, the proposals) — as text to copy, or as a zip with every call
itself (`/api/bench/<test bench>`, gui/server.py).

    lab_export.latest(root, subject_id)        the latest series of each of its cases, newest first
    lab_export.summary(root, w, subject)       the table, for the window (its cases by their titles)
    lab_export.text(root, w, subject)          everything as one text
    lab_export.pack(root, w, subject)          (file name, zip)
"""
from __future__ import annotations

import datetime as dt
import io
import json
import zipfile
from dataclasses import asdict
from pathlib import Path

from orkcraft.realm import bench, bench_review, call_log, explain, lexicon

CHAIN = "chain"


def latest(root: Path, subject_id: str) -> list[bench.Report]:
    """Its runs (a Test bench runs what it tests as a chain, `Report.subject` its id), the latest series of each
    case."""
    return bench.latest([r for r in bench.runs(root, CHAIN) if r.subject == subject_id])


def _word(subject: dict) -> str:
    return "Scheme" if subject.get("type") == CHAIN else lexicon.term(str(subject.get("type") or ""))


def names(w, subject: dict) -> dict[str, str]:
    """Its cases' titles by their ids."""
    return {c["id"]: c["title"] for c in w.cases_of(subject["id"])}


def stories(root: Path, w, subject: dict, reports: list[bench.Report] | None = None) -> list[dict]:
    """Each case of its latest runs in words (realm/explain.py), by its title."""
    titles = names(w, subject)
    reports = latest(root, subject["id"]) if reports is None else reports
    return [explain.story(titles.get(g[0].case, g[0].case), g, {r.id: bench.calls_of(root, r) for r in g})
            for g in bench.by_case(reports)]


def advice(root: Path, w, subject: dict) -> list[dict]:
    """The reviewers' findings as changes to make ({what, why, who}), the most severe first."""
    order = {s: n for n, s in enumerate(bench_review.SEVERITIES)}
    out = []
    for _bid, kind in types_of(w, subject):
        for role, e in (bench_review.load(root, kind, "tech").get("roles") or {}).items():
            for f in e.get("findings") or []:
                out.append({"what": f.get("title", ""), "why": f.get("detail", ""), "who": e.get("title") or role,
                            "severity": f.get("severity", "medium"), "where": f.get("where", "")})
    return sorted(out, key=lambda f: order.get(f["severity"], 1))


def summary(root: Path, w, subject: dict) -> dict:
    """Its latest runs: each case in words, what to change and why, and the table ({} before the first run)."""
    reports = latest(root, subject["id"])
    if not reports:
        return {}
    told = stories(root, w, subject, reports)
    return {"text": bench.summary(reports, _word(subject), names=names(w, subject)), "runs": len(reports),
            "cases": len({r.case for r in reports}), "at": max(r.at for r in reports), "stories": told,
            "changes": explain.changes(told, advice(root, w, subject))}


def words(root: Path, w, subject: dict) -> str:
    """What the runs mean and what to change, as text."""
    told = stories(root, w, subject)
    if not told:
        return "No run yet."
    mark = {"good": "✓", "watch": "!", "bad": "✗"}
    out = [f"- {mark[s['status']]} {s['case']}: {s['summary']}" + "".join(f"\n  {d}" for d in s["details"])
           for s in told]
    out += ["", "What to change:"] + [f"- {c['what']} — {c['why']}"
                                      + (f" ({', '.join(c['cases'])})" if c["cases"] else f" ({c['from']})")
                                      for c in explain.changes(told, advice(root, w, subject))]
    return "\n".join(out)


def types_of(w, subject: dict) -> list[tuple[str, str]]:
    """The buildings it tests, one of each type: (building id, type)."""
    seen: dict[str, str] = {}
    for b in w.flow_spec(subject)["buildings"]:
        seen.setdefault(b["type"], b["id"])
    return [(bid, kind) for kind, bid in seen.items()]


def runs_text(root: Path, w, subject: dict, calls: bool = True) -> str:
    """The table, then each run in full (with its model calls when `calls`)."""
    reports = latest(root, subject["id"])
    if not reports:
        return "No run yet."
    word = _word(subject)
    parts = [bench.summary(reports, word, names=names(w, subject))]
    for r in reports:
        parts += ["", "---", "", bench.analysis(r, word, bench.calls_of(root, r) if calls else None)]
    return "\n".join(parts)


def recommendations(root: Path, w, subject: dict) -> str:
    """The tech reviews of its buildings and the Test bench's proposals, as text."""
    out = []
    for bid, kind in types_of(w, subject):
        kept = bench_review.load(root, kind, "tech")
        found = [(e.get("title") or role, f) for role, e in (kept.get("roles") or {}).items()
                 for f in e.get("findings") or []]
        if found:
            out += ["", f"## Tech review of the {lexicon.term(kind)} ({kept.get('at', '')}, Orkline {kept.get('version', '')})"]
            out += [f"- [{f.get('severity', '')}] {who}: {f.get('title', '')}\n  {f.get('detail', '')}"
                    + (f"\n  where: {f['where']}" if f.get("where") else "") for who, f in found]
    items = (w.state["proposals"].get(subject["id"]) or {}).get("items") or []
    if items:
        out += ["", "## The Test bench's proposals"]
        out += [f"- [{p.get('area', '')}] {p.get('title', '')}\n  {p.get('detail', '')}" for p in items]
    return "\n".join(out).strip() or "No recommendation yet."


def text(root: Path, w, subject: dict) -> str:
    title = str(subject.get("title") or subject["id"])
    return "\n".join([f"# Test bench: {title}", "", f"Exported {dt.datetime.now().isoformat(timespec='seconds')}.",
                      f"Goal of the testing: {w.state['goal'] or 'none written'}", "", "## In plain words", "",
                      words(root, w, subject), "", "## Runs", "",
                      runs_text(root, w, subject), "", "## Recommendations", "", recommendations(root, w, subject)])


def pack(root: Path, w, subject: dict) -> tuple[str, bytes]:
    """The text as README.md, then each run's report and every model call of it, prompt and output in full."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("README.md", text(root, w, subject))
        for r in latest(root, subject["id"]):
            z.writestr(f"runs/{r.id}/report.json", json.dumps(asdict(r), indent=2, ensure_ascii=False))
            for folder, lines in _calls(root, r):
                for x in lines:
                    name = str(x.get("raw") or "").removesuffix(".gz")
                    z.writestr(f"runs/{r.id}/calls/{x.get('side') or 'call'}-{name}",
                               json.dumps({"line": x, **call_log.raw(folder, x)}, ensure_ascii=False, indent=1))
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in subject["id"])[:60]
    return f"orkcraft-test-bench-{safe}-{dt.date.today().isoformat()}.zip", buf.getvalue()


def _calls(root: Path, r: bench.Report) -> list[tuple[Path, list[dict]]]:
    """Each folder its calls are in: its own, and the run its bare side was kept from."""
    own = root / bench.RUNS / r.id / "calls"
    out = [(own, call_log.read(own))]
    if r.bare is not None and r.bare.kept and r.bare.kept != r.id:
        kept = root / bench.RUNS / r.bare.kept / "calls"
        out.append((kept, [x for x in call_log.read(kept) if x.get("side") == "bare"]))
    return out


def findings(root: Path, w, subject: dict, limit: int = 40) -> list[str]:
    """What is wrong with what it tests, in words, for the Mechanic's proposals: its own runs' stories and changes
    (realm/explain.py), the last night check's on the same building types, and the person's 👎 cases."""
    out = []
    reports = latest(root, subject["id"])
    if reports:
        told = stories(root, w, subject, reports)
        out += [f"{st['case']}: {st['summary']} " + " ".join(st["details"]) for st in told if st["status"] != "good"]
        out += [f"To change: {c['what']} — {c['why']}" for c in explain.changes(told)]
    kinds = {kind for _bid, kind in types_of(w, subject)}
    from orkcraft import check_cli
    from orkcraft.realm import check
    folder = check_cli.latest(root)
    if folder is not None:
        try:
            data = json.loads((folder / "results.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        mine = [sc for sc in data.get("scenarios") or [] if sc.get("type") in kinds]
        if mine:
            told_ = check.told(root, folder.name, mine)
            every = [st for sc in told_["scenarios"] for st in sc["stories"]]
            out += [f"Night check, {st['case']}: {st['summary']} " + " ".join(st["details"])
                    for st in every if st["status"] != "good"]
            out += [f"Night check — to change: {c['what']} — {c['why']}" for c in told_["changes"]]
    out += [f"The person disliked it — {c['title']}: {c.get('why', '')}" for c in w.cases_of(subject["id"])
            if c.get("source") == "dislike"]
    return [" ".join(x.split())[:400] for x in out][:limit]


def trouble(root: Path, w, subject: dict) -> int:
    """How much is wrong with what it tests (for the night's order): the cases not good, and the 👎 cases."""
    told = stories(root, w, subject)
    return sum(st["status"] != "good" for st in told) + \
        sum(c.get("source") == "dislike" for c in w.cases_of(subject["id"]))
