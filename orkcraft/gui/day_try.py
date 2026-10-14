"""🔧 A day's findings measured (docs/design/improve-buildings.md §13): what the Mechanic and the Farseer found in a day's
logs (gui/day_review.py) goes to a Test bench that tests the building, as one of its proposals — first, and kept when
the Mechanic writes its own again. **Try in the Test bench** puts it on the virtual building (settings and prompts
through the building's keeper, code in the bench's copy of the package: gui/lab_runs.py `try_change`) and runs the
bench's cases, so the numbers say whether it is better. A pull request goes only from the Test bench, when its cases
are ahead (realm/lab_pr.py `ready`), shown before it goes and sent by the person; what the logs hold never goes in one.

At night every finding of the day just read is handed to its Test bench (free); the night's improvements
(gui/improve_night.py) then try the settings and prompt ones first. A code change waits for the person's Try.

    day_try.findings(host, day)         [{n, who, building, title, what, why, kind, change, bench, can, tried}]
    day_try.hand(host, day)             every finding with a Test bench, handed to it: how many
    day_try.attempt(host, day, n)       one finding, tried and measured: what to say now
"""
from __future__ import annotations

import datetime as dt

from orkcraft.realm import catalog, day_review

AREA = {"setting": "settings", "tier": "settings", "prompt": "prompt", "rule": "prompt", "step": "prompt",
        "drop": "prompt", "code": "code", "road": "roads"}


class TryError(Exception):
    """A finding that cannot be tried; its text is shown to the person."""


def benches(host, building: str) -> list[tuple[object, dict]]:
    """The Test benches that test `building` (alone or in a chain), with what they test."""
    town = host.town
    out = []
    for b in town.scroll.buildings:
        if b.demolished or catalog.type_of(town.spec_of(b.id)).id != "lab":
            continue
        w = town.worker(b.id)
        for s in (w.subjects() if w is not None else []):
            if building in (s.get("chain") or [s["id"]]):
                out.append((w, s))
    return out


def _pid(day: str, n: int) -> str:
    return f"d{day}-{n}"


def _proposal(host, review: day_review.Review, n: int) -> dict:
    f = review.findings[n]
    by = day_review.TITLES[f.who].removeprefix("the ").capitalize()
    return {"id": _pid(review.day, n), "area": AREA.get(f.kind, "prompt"), "title": f.what[:200],
            "detail": f"{f.change} — {f.why}".strip(" —")[:2000], "where": host.town.title_of(f.building),
            "effect": f.why[:300], "from": f"{by}, in the logs of {day_review.label(review.day)} ({', '.join(f.hotspots)})"}


def findings(host, day: str) -> list[dict]:
    review = day_review.load(host.town.repo_root, day)
    out = []
    for n, f in enumerate(review.findings if review else []):
        found = benches(host, f.building) if f.building else []
        can = ("" if found and f.kind != "road" else
               "Roads change on the map, not on a Test bench" if f.kind == "road" else
               "No Test bench tests it: raise one (Build → Test bench) and pick it" if f.building else
               "It names no building")
        out.append({"n": n, "who": day_review.TITLES[f.who], "building": f.building,
                    "title": host.town.title_of(f.building) if f.building else "the town", "what": f.what,
                    "why": f.why, "kind": f.kind, "change": f.change, "hotspots": f.hotspots,
                    "bench": found[0][0].title if found and not can else "", "can": can, "tried": f.tried})
    return out


def hand(host, day: str) -> int:
    """Every finding of `day` a Test bench can try, handed to it as a proposal (free: nothing is run)."""
    review = day_review.load(host.town.repo_root, day)
    handed = 0
    for n, f in enumerate(review.findings if review else []):
        found = benches(host, f.building) if f.building and f.kind != "road" else []
        if found:
            w, s = found[0]
            w.add_proposal(s["id"], _proposal(host, review, n))
            handed += 1
    return handed


def attempt(host, day: str, n: int) -> str:
    """Finding `n` of `day` on its Test bench's virtual building, then the bench's cases run: the numbers decide."""
    root = host.town.repo_root
    review = day_review.load(root, day)
    if review is None or not 0 <= n < len(review.findings):
        raise TryError("That finding is gone: read the day again")
    f = review.findings[n]
    row = findings(host, day)[n]
    if row["can"]:
        raise TryError(row["can"])
    w, s = benches(host, f.building)[0]
    p = _proposal(host, review, n)
    w.add_proposal(s["id"], p)
    lab = host.bench.lab
    cases = [c["id"] for c in w.cases_of(s["id"])]

    def tried(ok: bool) -> None:
        if not ok:
            return
        if not cases:
            host.town.toast(f"Tried on the virtual {host.town.title_of(f.building)}. {w.title} has no cases yet: add a "
                            "case set, then Run, to see whether it is better", title="Improve")
            return
        try:
            lab.run(w, s, cases)
        except Exception as e:  # a run that cannot start (one is on): said, the change stays on the virtual building
            host.town.toast(f"Tried on the virtual {host.town.title_of(f.building)}; its cases did not run: {e}",
                            title="Improve", severity="warning")

    try:
        lab.try_change(w, s, p["id"], f.building, after=tried)
    except Exception as e:  # lab_runs.LabError and the like: said as they are
        raise TryError(str(e)) from None
    f.tried = dt.datetime.now().isoformat(timespec="seconds")
    day_review.save(root, review)
    return (f"{w.title} is trying it on the virtual {host.town.title_of(f.building)}"
            + (f", then runs its {len(cases)} case{'' if len(cases) == 1 else 's'}" if cases else "")
            + ". Its window has the numbers, and Send to Orkline when they are better")
