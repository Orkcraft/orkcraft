"""When a script-first building's ork wakes (docs/design/script-first.md §4), without a face.

A script-first building (realm/script_first.py) calls no model on its carts, its ticks or its schedules.
Its ork — the building's keeper (core/keeper.py) — wakes on two things only, once each:

    an error   the worker says its work failed (`status()` ERROR, unless its ERROR is a reading it shows:
               `Worker.ERROR_IS_FAILURE`), or the last run of one of its handlers ended in `error`. Once per
               spell: it wakes when the building goes ill after it was well, not again while it stays ill.
    a 👎       an explicit 👎 on the building (or on its steward), once per incident; 👎s that come
               together are one wake.

    wakes.start(town)                  # the town opens: older 👎s are not news
    for w in wakes.due(town):          # free: the workers' state, the runs, the incidents
        if face_ran_the_keeper(w.building, w.request):
            wakes.taken(town, w)       # remembered (`.orkcraft/script_first/`), logged

`due` changes nothing but the memory of a building that got well again; a wake the face could not run
(the budget is spent, a wake of the building still open) is due again at the next look.
"""
from __future__ import annotations

from dataclasses import dataclass

from orkcraft.core.town import Town
from orkcraft.realm import feedback, script_first

WAKE_CHECK_S = 5.0          # how often a face asks (the Host's clock)
ERROR = "error"
DISLIKE = "dislike"


@dataclass(frozen=True)
class Wake:
    building: str
    why: str                # error | dislike
    detail: str             # what failed, or the 👎's note
    request: str            # what its keeper is asked, in words
    marks: tuple[str, ...] = ()   # dislike: the incidents it covers


def _failure(town: Town, building_id: str) -> str:
    """What failed in the building now, "" when nothing did."""
    w = town.workers.get(building_id)
    if w is not None and w.ERROR_IS_FAILURE:
        try:
            ill = w.status() == "ERROR"
        except Exception:                     # a worker that cannot say is not woken on
            ill = False
        if ill:
            return _detail(w) or "its card shows a failure with no reason given — open it to see"
    last: dict[str, object] = {}
    for run in list(getattr(town.roads, "runs", []) or []):
        if run.target == building_id:
            last[run.orc_id] = run
    for run in last.values():
        if getattr(run, "outcome", "") == "error":
            return f"its handler {run.orc_id} failed: {getattr(run, 'error', '')}".strip()
    return ""


def _detail(w) -> str:
    """The worker's own words for what failed, by what it keeps (no worker has to know about wakes)."""
    for error in (getattr(w, "error", ""), getattr(w, "last_error", ""), getattr(getattr(w, "snap", None), "error", "")):
        if isinstance(error, str) and error.strip():
            return error.strip()
    errors = getattr(w, "errors", None)
    if isinstance(errors, dict) and errors:
        return "; ".join(str(e) for e in list(errors.values())[:5])
    day = getattr(w, "day", None)
    if getattr(day, "errors", None):
        return "; ".join(str(e) for e in day.errors[:5])
    runs = getattr(w, "runs", None)
    if runs:
        run = runs[0]
        text = str(getattr(run, "error", "") or getattr(run, "err", "") or "").strip()
        if text:
            return f"its last run failed: {text}"
    rules = getattr(w, "rules_text", None)
    if rules is not None:
        from orkcraft.realm import signpost
        problems = signpost.rules_of(rules)[1]
        if problems:
            return "its rules: " + "; ".join(problems[:5])
    try:                                      # the warning line its card shows
        lines = list(getattr(w, "mini_status", lambda: [])() or [])
    except Exception:
        lines = []
    for line in lines:
        if isinstance(line, str) and line.startswith("⚠"):
            return line.lstrip("⚠ ").strip()
    return ""


def _key(i: feedback.Incident) -> str:
    return f"{i.ts}|{i.building}|{i.kind}|{i.note[:80]}"


def _incidents(town: Town, building_id: str, mine: dict) -> list[feedback.Incident]:
    """Its explicit 👎s no wake took yet (`mine`: the building's memory), oldest first. Incidents are stamped to
    the second, so the ones at the cursor's second are told apart by their key."""
    after, seen = str(mine.get("disliked") or ""), set(mine.get("seen") or [])
    rows = [i for i in feedback.incidents(town.repo_root, 200)
            if i.source == feedback.EXPLICIT and i.ts >= after and _key(i) not in seen
            and (i.building == building_id or i.building.startswith(f"{building_id}/"))]
    return sorted(rows, key=lambda i: i.ts)


def error_request(title: str, detail: str) -> str:
    return (f"{title} failed: {detail}\nChange its settings so it does not fail this way again. If its settings "
            f"are right and what failed is outside it (a file, a service, what it was sent), change nothing and say "
            f"what the person should look at.")


def dislike_request(title: str, rows: list[feedback.Incident]) -> str:
    lines = []
    for i in rows[-3:]:
        what = feedback.KINDS.get(i.kind, i.kind)
        lines.append(f"- {what}; their note: {i.note or '(none)'}; its result then: {i.output[:600] or '(none)'}")
    return (f"The person gave {title} a 👎:\n" + "\n".join(lines) + "\nChange its settings so its next result is "
            f"what they want. If its inputs were broken, change nothing and say which building to look at.")


def due(town: Town) -> list[Wake]:
    """The wakes due now, for script-first buildings only. Free."""
    repo = town.repo_root
    memory = script_first.state(repo)
    changed, out = False, []
    for b in town.scroll.buildings:
        if b.demolished or not script_first.is_script_first(town.spec_of(b.id), b):
            continue
        mine = memory.get(b.id, {})
        failed = _failure(town, b.id)
        if not failed and mine.get("ill"):
            memory[b.id] = {**mine, "ill": False}            # well again: the next error wakes it
            changed = True
        title = town.title_of(b.id)
        if failed and not mine.get("ill"):
            out.append(Wake(b.id, ERROR, failed, error_request(title, failed)))
        rows = _incidents(town, b.id, mine)
        if rows:
            out.append(Wake(b.id, DISLIKE, rows[-1].note or "👎", dislike_request(title, rows),
                            tuple(_key(i) for i in rows)))
    if changed:
        script_first.save_state(repo, memory)
    return out


def start(town: Town) -> None:
    """The town opens: the 👎s given before its buildings were watched for wakes do not wake them."""
    memory = script_first.state(town.repo_root)
    fresh = [b.id for b in town.scroll.buildings if "disliked" not in memory.get(b.id, {})]
    if not fresh:
        return
    for bid in fresh:
        old = _incidents(town, bid, {})
        memory[bid] = {**memory.get(bid, {}), "disliked": old[-1].ts if old else "",
                       "seen": [_key(i) for i in old if i.ts == old[-1].ts]}
    script_first.save_state(town.repo_root, memory)


def taken(town: Town, wake: Wake) -> dict:
    """The face ran the wake: remembered so it is not due again, and logged."""
    memory = script_first.state(town.repo_root)
    mine = dict(memory.get(wake.building, {}))
    if wake.why == ERROR:
        mine["ill"] = True
    else:
        newest = max(k.split("|", 1)[0] for k in wake.marks) if wake.marks else ""
        if newest > str(mine.get("disliked") or ""):
            mine["disliked"], mine["seen"] = newest, []
        mine["seen"] = (list(mine.get("seen") or []) + [k for k in wake.marks if k.startswith(newest + "|")])[-50:]
    memory[wake.building] = mine
    script_first.save_state(town.repo_root, memory)
    return script_first.log(town.repo_root, wake.building, wake.why, wake.detail)
