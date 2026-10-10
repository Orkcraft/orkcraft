"""🧪 The Test bench for buildings whose work is not code (docs/design/test-bench.md §3.5): what the bare AI tool is
asked, how its answer reads, and the checks both sides' results go through. The building's side is
`core/bench_kits.py`; both make the same result, so one check judges them.

    kit = bench_kits.KITS["watchtower"]
    kit.prompt(case) → the bare AI tool's prompt      kit.parse(text) → a result
    kit.check(case, result) → [{"name", "ok", "detail"}]

A result per type:

    watchtower  {"messages": [{"n", "kept", "importance", "answer", "why"}]}
    fields      {"titles": [{"n", "title"}], "plans": [{"n", "steps": […]}]}
    war_drum    {"briefs": [{"n", "text"}]}

A check of words matches their stem (the first `STEM` letters), case and accents aside, so "booking" finds
"bookings"; a group of words passes when any of them is there.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import threading
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from orkcraft.realm import bench, jobs, tiers

STEM = 5
_JSON = re.compile(r"\{.*\}", re.S)
_WORD = re.compile(r"[^\W_]+", re.U)
TITLE_WORDS = (2, 5)          # a card's title: as the Task board asks (2–4 words), one more for a hyphenated name
PLAN_STEPS = (3, 7)


def _plain(text: str) -> str:
    """Lower case without accents (café → cafe); other scripts stay as they are."""
    return "".join(ch for ch in unicodedata.normalize("NFKD", text or "") if not unicodedata.combining(ch)).lower()


def _stems(text: str) -> set[str]:
    return {w[:STEM] for w in _WORD.findall(_plain(text))}


def has(text: str, words) -> bool:
    """Any of `words` (a word or a list of them) is in `text`, by its stem; a number or a code by itself."""
    found = _stems(text)
    low = _plain(text)
    for w in [words] if isinstance(words, str) else list(words):
        w = str(w)
        if any(c.isdigit() for c in w) or not w.isalpha():
            if _plain(w) in low:
                return True
        elif _plain(w)[:STEM] in found:
            return True
    return False


def _said(words) -> str:
    return " or ".join(f"“{w}”" for w in ([words] if isinstance(words, str) else words))


def answer_json(text: str) -> dict:
    m = _JSON.search(text or "")
    try:
        data = json.loads(m.group(0)) if m else {}
    except ValueError:
        data = {}
    return data if isinstance(data, dict) else {}


def _by_n(rows, key: str = "n") -> dict[int, dict]:
    out = {}
    for r in rows or []:
        try:
            out[int(r.get(key))] = r
        except (TypeError, ValueError, AttributeError):
            continue
    return out


@dataclass(frozen=True)
class Kit:
    type: str
    prompt: Callable[[bench.Case], str]
    parse: Callable[[str], dict]
    check: Callable[[bench.Case, dict], list[dict]]
    bare_use: str = ""            # the building's own model use whose tier the bare tool runs on, when none is picked


def _ok(name: str, ok: bool, detail: str = "") -> dict:
    return {"name": name, "ok": bool(ok), "detail": detail}


# -- External listeners ---------------------------------------------------------------------------------------

def _wt_prompt(c: bench.Case) -> str:
    rows = "\n\n".join(f"[{n}] from {m.get('sender') or 'unknown'} ({m.get('source') or 'mail'})\n"
                       f"Subject: {m.get('title', '')}\n{m.get('body', '')}"
                       for n, m in enumerate(c.inputs.get("messages") or [], 1))
    intent = c.inputs.get("intent") or ""
    return f"""You sort incoming messages for a person.
What they want to hear about: {intent or 'anything that needs them'}.

For each message say whether it is what they want to hear about (keep), how important it is (high, normal or
low), and who should answer it: "agent" (a routine reply an assistant can write), "person" (it needs them) or
"" (no answer needed).

<messages>
{rows}
</messages>

Answer with JSON only:
{{"messages": [{{"n": 1, "keep": true, "importance": "high", "answer": "person", "why": "a few words"}}]}}"""


def _wt_parse(text: str) -> dict:
    rows = []
    for r in answer_json(text).get("messages") or []:
        if isinstance(r, dict) and r.get("n") is not None:
            rows.append({"n": r.get("n"), "kept": bool(r.get("keep", r.get("kept"))),
                         "importance": str(r.get("importance") or ""), "answer": str(r.get("answer") or ""),
                         "why": str(r.get("why") or "")[:200]})
    return {"messages": rows}


def _wt_check(c: bench.Case, result: dict) -> list[dict]:
    got = _by_n(result.get("messages"))
    out = []
    for n, m in enumerate(c.inputs.get("messages") or [], 1):
        want, r, name = m.get("expect") or {}, got.get(n), f"#{n} {m.get('title', '')}"[:70]
        if r is None:
            out.append(_ok(name, False, "no verdict"))
            continue
        if "kept" in want:
            out.append(_ok(f"{name}: {'kept' if want['kept'] else 'left out'}", r["kept"] == want["kept"],
                           f"{'kept' if r['kept'] else 'left out'}" + (f" — {r['why']}" if r.get("why") else "")))
        if want.get("importance"):
            out.append(_ok(f"{name}: importance {want['importance']}", r["importance"] == want["importance"],
                           f"said {r['importance'] or 'nothing'}"))
        if "answer" in want:
            out.append(_ok(f"{name}: answered by {want['answer'] or 'nobody'}", r["answer"] == want["answer"],
                           f"said {r['answer'] or 'nobody'}"))
    return out


# -- Task board -----------------------------------------------------------------------------------------------

def _fd_prompt(c: bench.Case) -> str:
    titles = "\n".join(f"[{n}] {t['text']}" for n, t in enumerate(c.inputs.get("titles") or [], 1))
    plans = "\n\n".join(f"[{n}] {p['title']}\n{p.get('body', '')}" for n, p in enumerate(c.inputs.get("plans") or [], 1))
    return f"""Two jobs for a person's task board. The folder you are in is their project; read it if it helps.

1. Name each card below in 2 to 4 words, in the language it is written in:
{titles or '(none)'}

2. For each to-do below, write its plan: 3 to 7 numbered steps, short, in the order they are done:
{plans or '(none)'}

Answer with JSON only:
{{"titles": [{{"n": 1, "title": "…"}}], "plans": [{{"n": 1, "steps": ["…", "…", "…"]}}]}}"""


def _fd_parse(text: str) -> dict:
    data = answer_json(text)
    titles = [{"n": t.get("n"), "title": str(t.get("title") or "")} for t in data.get("titles") or [] if isinstance(t, dict)]
    plans = [{"n": p.get("n"), "steps": [str(s) for s in p.get("steps") or []][:20]}
             for p in data.get("plans") or [] if isinstance(p, dict)]
    return {"titles": titles, "plans": plans}


def _fd_check(c: bench.Case, result: dict) -> list[dict]:
    out = []
    titles = _by_n(result.get("titles"))
    for n, t in enumerate(c.inputs.get("titles") or [], 1):
        got = (titles.get(n) or {}).get("title", "").strip()
        words = len(got.split())
        name = f"title #{n}"
        out.append(_ok(f"{name}: {TITLE_WORDS[0]}–{TITLE_WORDS[1] - 1} words", TITLE_WORDS[0] <= words <= TITLE_WORDS[1],
                       f"“{got}”" if got else "no title"))
        for group in t.get("expect_words") or []:
            out.append(_ok(f"{name} says {_said(group)}", has(got, group), f"“{got}”"))
    plans = _by_n(result.get("plans"))
    for n, p in enumerate(c.inputs.get("plans") or [], 1):
        steps = (plans.get(n) or {}).get("steps") or []
        text = "\n".join(steps)
        name = f"plan of “{p['title']}”"
        out.append(_ok(f"{name}: {PLAN_STEPS[0]}–{PLAN_STEPS[1]} steps", PLAN_STEPS[0] <= len(steps) <= PLAN_STEPS[1],
                       f"{len(steps)} steps"))
        for group in p.get("expect_words") or []:
            out.append(_ok(f"{name} says {_said(group)}", has(text, group), text[:300]))
        if "[email-" in text or "[phone-" in text:
            out.append(_ok(f"{name}: no hidden marks left", False, "a [email-…] or [phone-…] mark came through"))
    return out


# -- Calendar (meeting briefs) --------------------------------------------------------------------------------

def events_of(c: bench.Case) -> list[dict]:
    return list(c.inputs.get("events") or [])


def when_of(e: dict, now: dt.datetime) -> tuple[dt.datetime, dt.datetime]:
    """An event's start and end: `day` days from `now`'s date at `at` (HH:MM), for `minutes`."""
    h, _, m = str(e.get("at") or "10:00").partition(":")
    start = dt.datetime.combine(now.date() + dt.timedelta(days=int(e.get("day", 1))), dt.time(int(h), int(m or 0)))
    return start, start + dt.timedelta(minutes=int(e.get("minutes", 60)))


def ics_of(c: bench.Case, now: dt.datetime) -> str:
    """The case's events as a calendar file: titles, times, attendees and descriptions."""
    def esc(v: str) -> str:
        return v.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//orkcraft//bench//EN"]
    for n, e in enumerate(events_of(c), 1):
        start, end = when_of(e, now)
        lines += ["BEGIN:VEVENT", f"UID:bench-{n}@orkcraft", f"DTSTART:{start:%Y%m%dT%H%M%S}", f"DTEND:{end:%Y%m%dT%H%M%S}",
                  f"SUMMARY:{esc(e.get('title', 'Meeting'))}"]
        if e.get("description"):
            lines.append(f"DESCRIPTION:{esc(e['description'])}")
        lines += [f"ATTENDEE;CN={a}:mailto:{a.split()[0].lower()}@example.com" for a in e.get("attendees") or []]
        lines.append("END:VEVENT")
    return "\r\n".join(lines + ["END:VCALENDAR"]) + "\r\n"


def _wd_prompt(c: bench.Case) -> str:
    now = dt.datetime.now()
    rows = []
    for n, e in enumerate(events_of(c), 1):
        start, end = when_of(e, now)
        who = f"\nWho: {', '.join(e['attendees'])}" if e.get("attendees") else ""
        rows.append(f"[{n}] {start:%a %d %b %H:%M}–{end:%H:%M} {e.get('title', '')}{who}\n{e.get('description', '')}")
    orders = c.inputs.get("orders") or ""
    return f"""Prepare a brief for each meeting below, for the person who will be in it. The folder you are in is their
project; read it if it helps.{(chr(10) + 'How a brief is written: ' + orders) if orders else ''}

{chr(10).join(rows)}

Answer with JSON only, each brief as Markdown:
{{"briefs": [{{"n": 1, "text": "…"}}]}}"""


def _wd_parse(text: str) -> dict:
    return {"briefs": [{"n": b.get("n"), "text": str(b.get("text") or "")}
                       for b in answer_json(text).get("briefs") or [] if isinstance(b, dict)]}


def _wd_check(c: bench.Case, result: dict) -> list[dict]:
    briefs = _by_n(result.get("briefs"))
    out = []
    for n, e in enumerate(events_of(c), 1):
        text = (briefs.get(n) or {}).get("text", "")
        name = f"brief of “{e.get('title', '')}”"
        out.append(_ok(f"{name} written", bool(text.strip()), f"{len(text)} characters"))
        if not text.strip():
            continue
        for head in e.get("expect_headings") or c.inputs.get("expect_headings") or []:
            heads = [ln.strip("# ").strip() for ln in text.splitlines() if ln.lstrip().startswith("#")]
            out.append(_ok(f"{name} has “{head}”", any(has(h, head) for h in heads), "; ".join(heads)[:200]))
        for group in e.get("expect_words") or []:
            out.append(_ok(f"{name} says {_said(group)}", has(text, group), text[:200]))
    return out


KITS: dict[str, Kit] = {
    "watchtower": Kit("watchtower", _wt_prompt, _wt_parse, _wt_check, "judge"),
    "fields": Kit("fields", _fd_prompt, _fd_parse, _fd_check, "plan"),
    "war_drum": Kit("war_drum", _wd_prompt, _wd_parse, _wd_check, ""),
}


def judged(side: bench.Side, c: bench.Case, kit: Kit, result: dict) -> bench.Side:
    """The side's result, its checks, and passed only when every check did."""
    side.result = result
    side.checks = kit.check(c, result)
    side.passed = bool(side.checks) and all(x["ok"] for x in side.checks)
    return side


def bare(c: bench.Case, workdir: Path, tool: str = "main", tier: str = "", cancel: threading.Event | None = None,
         runner=None) -> bench.Side:
    """The bare AI tool on the case: its kit's prompt, in a copy of the project it may read, one call; then the
    same checks as the building's result."""
    kit = KITS[c.type]
    model = tiers.resolve(tool, tier) if tier else ""
    side, start = bench.Side("bare", where=str(workdir), model=tier), time.monotonic()
    try:
        text, cost, tokens, _ = (runner or jobs.run_read)(tool, kit.prompt(c), workdir, cancel or threading.Event(), model)
        side.text, side.cost, side.tokens = (text or "")[:6000], float(cost or 0.0), int(tokens or 0)
        judged(side, c, kit, kit.parse(text))
    except (RuntimeError, OSError) as e:
        side.error = str(e)[:500] or type(e).__name__
    side.seconds = round(time.monotonic() - start, 1)
    return side
