"""📜 A building's day, to hand to someone who checks its work: every model call it made (what went in, what came
out, how it worked) and what it decided, as one zip.

    day_log.days(root, building)                 the days kept for it, newest first
    day_log.pack(root, building, day, extra)     the zip: README.md, calls.jsonl, a calls/ file each, `extra` files
    day_log.clear(root, today, disliked, keep)   the morning's clearing (below)

The calls are written by realm/call_log.py into `.orkcraft/logs/<day>/<building>/`. A day is cleared at the start
of the next one, building by building, unless its log was asked for (`pack` marks it) or the building got a 👎 that
day: then it is kept for KEEP_DAYS, for whoever looks into it. While the town keeps its logs for analysis (`keep`:
the Council's `logs_for_analysis`, a switch in Town settings) every day is kept, KEEP_ANALYSIS days, for a period
to be downloaded at once (realm/analytics.py). No face here: the GUI serves the zip (gui/server.py).
"""
from __future__ import annotations

import datetime as dt
import io
import json
import shutil
import zipfile
from pathlib import Path
from typing import Callable

from orkcraft.realm import call_log

ASKED = ".asked"                  # in a building's day folder: its log was taken, keep the day
KEEP_DAYS = 14                    # how long a day that was asked for or disliked is kept
KEEP_ANALYSIS = 30                # how long every day is kept while the logs are kept for analysis


def days(root: Path, building: str) -> list[str]:
    folder = root / call_log.DAYS
    found = [d.name for d in folder.iterdir() if call_log.day_folder(root, d.name, building).is_dir()] \
        if folder.is_dir() else []
    return sorted(found, reverse=True)


def _day(text: str) -> dt.date | None:
    try:
        return dt.date.fromisoformat(text)
    except ValueError:
        return None


def clear(root: Path, today: dt.date, disliked: Callable[[str, str], bool], keep: bool = False) -> list[str]:
    """Each building's day before `today`: removed unless its log was asked for or `disliked(building, day)`; those
    stay KEEP_DAYS. With `keep` (the logs kept for analysis) every day stays KEEP_ANALYSIS. What was removed, as
    `<day>/<building>`."""
    gone = []
    folder = root / call_log.DAYS
    for day_dir in sorted(folder.iterdir()) if folder.is_dir() else ():
        day = _day(day_dir.name)
        if day is None or day >= today:
            continue
        for b in [p for p in day_dir.iterdir() if p.is_dir()]:
            age = (today - day).days
            if keep and age <= KEEP_ANALYSIS:
                continue
            if age > KEEP_DAYS or not ((b / ASKED).exists() or disliked(b.name, day_dir.name)):
                shutil.rmtree(b, ignore_errors=True)
                gone.append(f"{day_dir.name}/{b.name}")
        if not any(day_dir.iterdir()):
            day_dir.rmdir()
    return gone


def readme(building: str, title: str, day: str, lines: list[dict], decisions: list[dict]) -> str:
    """What the zip holds, and the day's calls added up, for whoever opens it first."""
    out = [f"# {title} · {day}", "",
           f"Every model call the building `{building}` made that day, and what it decided. `calls.jsonl` has a line",
           "each call (who, what for, model, seconds, tokens, cost, the tool's usage); `calls/<n>-<who>.json` the call",
           "itself: `prompt` (what went in), `stdout` (what came out), `stderr`, and `trail` (how it worked: the",
           "AI tool's own session, with its thinking and tool calls, when the tool keeps one).", ""]
    if lines:
        out += ["## Calls", ""]
        for t in call_log.totals(lines):
            usage = ", ".join(f"{k} {v:,}" for k, v in t["usage"].items())
            out.append(f"- {t['who'] or 'the tool'} · {t['purpose']}: {t['calls']} call{'' if t['calls'] == 1 else 's'}, "
                       f"{t['seconds']:.0f} s, {t['tokens']:,} tokens" + (f" ({usage})" if usage else "")
                       + (f", ${t['cost']:.4f}" if t["cost"] else ""))
        out += [""] + [f"- {x.get('at', '')[11:19]} #{x.get('n')} {x.get('who') or 'the tool'} · {x.get('purpose')} · "
                       f"{x.get('tool')}{':' + x['model'] if x.get('model') else ''} · {x.get('seconds', 0):.0f} s · "
                       f"{x.get('tokens') or 0:,} tokens" + ("" if not x.get("code") else f" · exited {x['code']}")
                       for x in lines]
    else:
        out += ["No model call that day."]
    if decisions:
        out += ["", "## Decisions", ""] + [f"- {d.get('at', '')[11:19]} {d.get('action', '')}: "
                                          f"{(d.get('orc') + ' — ') if d.get('orc') else ''}{d.get('why', '')}"
                                          for d in decisions]
    return "\n".join(out) + "\n"


def pack(root: Path, building: str, day: str, title: str = "", decisions: list[dict] | None = None,
         extra: dict[str, str] | None = None) -> bytes:
    """The building's day as a zip, and the day marked as asked for (it is kept)."""
    folder = call_log.day_folder(root, day, building)
    lines = call_log.read(folder)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("README.md", readme(building, title or building, day, lines, decisions or []))
        z.writestr("calls.jsonl", "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in lines))
        for x in lines:
            z.writestr(f"calls/{str(x.get('raw') or '').removesuffix('.gz')}",
                       json.dumps(call_log.raw(folder, x), ensure_ascii=False, indent=1))
        if decisions:
            z.writestr("decisions.jsonl", "".join(json.dumps(d, ensure_ascii=False) + "\n" for d in decisions))
        for name, text in (extra or {}).items():
            z.writestr(name, text)
    if folder.is_dir():
        (folder / ASKED).touch()
    return buf.getvalue()
