"""🎒 An orc's inventory: the model it thinks with (and its tier), and the tools it reached for
lately — read from the transcripts of its runs (`.orkcraft/sessions.jsonl`, written by the
session hook). Read-only; a transcript is parsed once per change of its file.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path

from orkcraft.realm import tiers
from orkcraft.realm.orcs import RESIDENT, WORKER, Orc
from orkcraft.sources import transcripts
from orkcraft.sources.sessions import HARNESS_AGY, Session, collect_sessions, sessions_for_orc

RECENT_RUNS = 5          # the tools of this many latest runs
_RUNS: dict[str, tuple[float, int, transcripts.Run]] = {}


@dataclass
class ToolUse:
    name: str
    count: int
    last: dt.datetime | None


def short_tool(name: str) -> str:
    """`mcp__github__get_file_contents` → `github·get_file_contents`; built-ins stay as they are."""
    if name.startswith("mcp__"):
        server, _, tool = name[5:].partition("__")
        return f"{server}·{tool}" if tool else server
    return name


def read_run(path: str) -> transcripts.Run | None:
    """A transcript's run, cached by the file's mtime and size."""
    try:
        st = Path(path).stat()
    except OSError:
        return None
    hit = _RUNS.get(path)
    if hit is not None and hit[:2] == (st.st_mtime, st.st_size):
        return hit[2]
    run = transcripts.read_run(path)
    _RUNS[path] = (st.st_mtime, st.st_size, run)
    return run


def sessions_of(repo_root: Path, orc: Orc) -> list[Session]:
    """The orc's runs, newest first: a garrison orc's by its ref, a War Tent session by its key."""
    everything = collect_sessions(repo_root)
    if orc.category == RESIDENT:
        found = sessions_for_orc(everything, orc.ref)
    elif orc.category == WORKER:
        found = [s for s in everything if s.key == orc.ref]
    else:
        found = []
    return sorted(found, key=lambda s: s.last or s.started or dt.datetime.min, reverse=True)


def recent_tools(repo_root: Path, orc: Orc, runs: int = RECENT_RUNS) -> list[ToolUse]:
    """The tools of its latest runs, the most recently used first, with how often."""
    uses: dict[str, ToolUse] = {}
    for session in sessions_of(repo_root, orc)[:runs]:
        if session.harness == HARNESS_AGY or not session.transcript:
            continue
        run = read_run(session.transcript)
        for step in run.steps if run else []:
            if step.kind != "tool" or not step.tool:
                continue
            u = uses.setdefault(step.tool, ToolUse(step.tool, 0, None))
            u.count += 1
            if step.ts is not None and (u.last is None or step.ts > u.last):
                u.last = step.ts
    return sorted(uses.values(), key=lambda u: (u.last.timestamp() if u.last else 0.0, u.count), reverse=True)


def models_of(orc: Orc, live_model: str = "") -> list[tuple[str | None, str]]:
    """(tier, model) per harness step — the live session's model when it runs one."""
    from orkcraft.realm.unit_info import short_model

    if live_model:
        return [(tiers.tier_of_model(live_model), short_model(live_model))]
    if orc.kind in ("chain", "script"):
        return []
    out = []
    for step in orc.harness:
        model = tiers.step_model(step) or tiers.DEFAULT_MODEL.get(str(step.get("harness", "")), "")
        out.append((tiers.step_tier(step), short_model(model) if model else f"{step.get('harness', '?')} default"))
    return out
