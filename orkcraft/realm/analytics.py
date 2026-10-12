"""📊 The town's analytics: every building's day logs over a period (realm/day_log.py), with what each day added up
to, as one zip — to hand to someone (or an agent) who checks how the buildings work and what they cost.

    analytics.days_kept(root)                        the days with logs, newest first
    analytics.summary(root, days, titles, decisions, dislikes)    per day and building: calls, time, tokens, …
    analytics.pack(root, days, titles, decisions, dislikes)       the zip (and every day in it marked as asked for)

The zip: `README.md` (what is where, how to read it, the period added up), `summary.json` (the same, for a script),
and `<day>/<building>/` with `calls.jsonl`, `calls/<n>-<who>.json` (each call in full: prompt, output, errors, the
tool's trail), `decisions.jsonl` (an Agent pool's steward: hires, reworks, waits) and `dislikes.jsonl` (the 👎 that
day on that building, with what the person said). No face here: the GUI serves it (gui/server.py `/api/analytics`).
"""
from __future__ import annotations

import io
import json
import zipfile
from collections import Counter
from pathlib import Path
from typing import Callable

from orkcraft.realm import call_log, day_log

REWORKS = ("follow-up", "reuse", "retier")      # a steward's decisions that send work back or again


def days_kept(root: Path) -> list[str]:
    folder = root / call_log.DAYS
    found = [d.name for d in folder.iterdir() if d.is_dir() and day_log._day(d.name)] if folder.is_dir() else []
    return sorted(found, reverse=True)


def _buildings(root: Path, day: str) -> list[str]:
    folder = root / call_log.DAYS / day
    return sorted(p.name for p in folder.iterdir() if p.is_dir()) if folder.is_dir() else []


def summary(root: Path, days: list[str], titles: dict[str, str],
            decisions: Callable[[str, str], list[dict]], dislikes: Callable[[str, str], list[dict]]) -> dict:
    """{"days": [{day, buildings: [{id, title, calls, seconds, tokens, cost, failed, by: [totals], decisions: {action:
    n}, reworks, dislikes}]}], "total": {…}, "by_building": {id: {…}}} over `days` (oldest first)."""
    out, total, per = [], Counter(), {}
    for day in sorted(days):
        rows = []
        for bid in _buildings(root, day):
            lines = call_log.read(call_log.day_folder(root, day, bid))
            acts = Counter(str(d.get("action") or "") for d in decisions(bid, day))
            row = {"id": bid, "title": titles.get(bid, bid), "calls": len(lines),
                   "seconds": round(sum(float(x.get("seconds") or 0) for x in lines), 1),
                   "tokens": sum(int(x.get("tokens") or 0) for x in lines),
                   "cost": round(sum(float(x.get("cost") or 0) for x in lines), 4),
                   "failed": sum(1 for x in lines if x.get("code")),
                   "by": call_log.totals(lines), "decisions": dict(acts),
                   "reworks": sum(acts[a] for a in REWORKS), "dislikes": len(dislikes(bid, day))}
            rows.append(row)
            for k in ("calls", "seconds", "tokens", "cost", "failed", "reworks", "dislikes"):
                total[k] += row[k]
                per.setdefault(bid, Counter({"days": 0}))[k] += row[k]
            per[bid]["days"] += 1
        out.append({"day": day, "buildings": rows})
    rnd = lambda c: {k: round(v, 4) if isinstance(v, float) else v for k, v in c.items()}
    return {"days": out, "total": rnd(total), "by_building": {b: {"title": titles.get(b, b), **rnd(c)}
                                                              for b, c in per.items()}}


def _row(r: dict) -> str:
    return (f"{r['calls']} call{'' if r['calls'] == 1 else 's'}, {r['seconds']:.0f} s, {r['tokens']:,} tokens"
            + (f", ${r['cost']:.2f}" if r.get("cost") else "") + (f", {r['failed']} failed" if r.get("failed") else "")
            + (f", {r['reworks']} rework{'' if r['reworks'] == 1 else 's'}" if r.get("reworks") else "")
            + (f", {r['dislikes']} 👎" if r.get("dislikes") else ""))


def readme(s: dict) -> str:
    days = [d["day"] for d in s["days"]]
    period = f"{days[0]} – {days[-1]}" if len(days) > 1 else (days[0] if days else "no day")
    out = [f"# Orkcraft analytics · {period}", "",
           "Every model call the town's buildings made in these days, and what they decided. Each",
           "`<day>/<building>/` holds `calls.jsonl` (a line each call: who, what for, model, seconds, tokens, cost,",
           "the tool's usage), `calls/<n>-<who>.json` (the call itself: `prompt` what went in, `stdout` what came out,",
           "`stderr`, `trail` how it worked when the AI tool keeps a session), `decisions.jsonl` (an Agent pool's",
           "steward: whom it hired, what it sent back, what waited) and `dislikes.jsonl` (the 👎, with what was said).",
           "`summary.json` is this page for a script.", "",
           "How to read it: start with the buildings and days that cost the most or got a 👎; in their `calls.jsonl`",
           "find the costly calls, then read those calls in full — is the same context sent again, a model higher",
           "than the job needs, work sent back that a clearer first prompt would have done right?", "",
           "## The period", "", f"- All buildings: {_row(s['total'])}" if s["total"] else "- No model call."]
    for bid, r in sorted(s["by_building"].items(), key=lambda kv: -kv[1].get("tokens", 0)):
        out.append(f"- {r['title']} (`{bid}`, {r['days']} day{'' if r['days'] == 1 else 's'}): {_row(r)}")
    for d in reversed(s["days"]):
        out += ["", f"## {d['day']}", ""]
        for r in d["buildings"]:
            out.append(f"- **{r['title']}** (`{r['id']}`): {_row(r)}")
            out += [f"  - {t['who'] or 'the tool'} · {t['purpose'] or 'work'}: {_row({**t, 'failed': 0})}" for t in r["by"]]
            if r["decisions"]:
                out.append("  - decisions: " + ", ".join(f"{a} {n}" for a, n in sorted(r["decisions"].items())))
        if not d["buildings"]:
            out.append("- No model call.")
    return "\n".join(out) + "\n"


def pack(root: Path, days: list[str], titles: dict[str, str],
         decisions: Callable[[str, str], list[dict]], dislikes: Callable[[str, str], list[dict]]) -> bytes:
    """The period as one zip; every building's day in it is marked as asked for (kept, realm/day_log.py)."""
    s = summary(root, days, titles, decisions, dislikes)
    buf = io.BytesIO()
    jsonl = lambda rows: "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows)
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("README.md", readme(s))
        z.writestr("summary.json", json.dumps(s, ensure_ascii=False, indent=1))
        for d in s["days"]:
            for r in d["buildings"]:
                folder = call_log.day_folder(root, d["day"], r["id"])
                base = f"{d['day']}/{r['id']}"
                lines = call_log.read(folder)
                z.writestr(f"{base}/calls.jsonl", jsonl(lines))
                for x in lines:
                    z.writestr(f"{base}/calls/{str(x.get('raw') or '').removesuffix('.gz')}",
                               json.dumps(call_log.raw(folder, x), ensure_ascii=False, indent=1))
                if rows := decisions(r["id"], d["day"]):
                    z.writestr(f"{base}/decisions.jsonl", jsonl(rows))
                if rows := dislikes(r["id"], d["day"]):
                    z.writestr(f"{base}/dislikes.jsonl", jsonl(rows))
                if folder.is_dir():
                    (folder / day_log.ASKED).touch()
    return buf.getvalue()
