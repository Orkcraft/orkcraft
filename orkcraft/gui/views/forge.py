"""⚒️ The Forge in the GUI: the branches with their PRs, tests and changes; the chosen one's commits,
files, test output, merges and PR comments; the settings. The looks, the tests and the merge are the
worker's (core/workers/forge.py). The page asks the person before every merge."""
from __future__ import annotations

import time

from orkcraft.gui import markdown
from orkcraft.gui.views import ActError, text

REFRESH_S = 30.0              # as the TUI
BRANCHES = 60


def refresh(w) -> None:
    w.refresh()


def _merge(r, at: str = "") -> dict:
    why = "conflict" if r.conflicts else r.error
    return {"ok": r.ok, "branch": r.branch, "why": why[:60], "at": at}


def _last(w) -> dict | None:
    """The last merge and when (`HH:MM` today, else `MM-DD`)."""
    if w.last_merge is None:
        return None
    at = w.merges[-1][0] if w.merges and w.merges[-1][1] is w.last_merge else ""
    today = time.strftime("%Y-%m-%d")
    return _merge(w.last_merge, at[11:16] if at.startswith(today) else at[5:10])


def card(w) -> dict:
    """Closed (docs/design/building-views.md): how many branches, the PRs open, a merge that waits for a yes,
    and the last merge with when (`merging …` meanwhile)."""
    snap = w.snap
    if snap is None:
        return {"looking": True}
    if snap.error:
        return {"error": " ".join(snap.error.split())[:60]}
    rows = [b for b in snap.branches if b.name != snap.base]
    return {"branches": len(rows), "prs": sum(1 for b in rows if b.pr is not None and b.pr.state in ("OPEN", "DRAFT")),
            "merging": w.merging, "asking": w.asking, "last": _last(w)}


def _tests(w, name: str) -> str:
    if name in w.testing or w.merging == name:
        return "running"
    t = w.tests.get(name)
    return "" if t is None else "passed" if t["ok"] else "failed"


def _branch(w, b) -> dict:
    pr = b.pr
    return {"name": b.name, "current": b.current, "when": b.when, "subject": b.subject,
            "ahead": b.ahead, "behind": b.behind, "files": b.files, "added": b.added, "removed": b.removed,
            "pr": {"number": pr.number, "state": pr.state.lower(), "title": pr.title, "url": pr.url} if pr else None,
            "tests": _tests(w, b.name)}


def _chosen(w) -> dict | None:
    b = w.branch(w.picked) if w.picked else None
    if b is None:
        return None
    test = w.tests.get(b.name)
    comments = w.comments.get(b.name, []) if b.pr is not None else []
    return {
        "name": b.name, "commits": w.commits, "files": w.files,
        "test": {"ok": test["ok"], "at": test["at"], "output": test["output"][-6000:]} if test else None,
        "merges": [{"at": at, "ok": r.ok, "commit": r.commit[:10], "error": r.error, "conflicts": r.conflicts,
                    "message": r.message} for at, r in reversed(w.merges_of(b.name))],
        "comments": None if comments is None else [
            {"author": c["author"], "at": c["at"][:16].replace("T", " "), "state": c["state"],
             "html": markdown.render(c["body"])} for c in comments],
        "comments_known": b.pr is None or b.name in w.comments,
    }


def detail(w) -> dict:
    snap = w.snap
    cfg = w.config
    out = {"looking": snap is None, "error": " ".join(snap.error.split()) if snap else "", "base": w.base,
           "prs_known": bool(snap and snap.prs_known), "merging": w.merging, "asking": w.asking,
           "testing": sorted(w.testing), "picked": w.picked,
           "settings": {"base": str(cfg.get("base") or ""), "test_cmd": str(cfg.get("test_cmd") or ""),
                        "confirm": bool(cfg.get("confirm")), "remote": str(cfg.get("remote") or "")},
           "last": _last(w),
           "branches": [], "chosen": _chosen(w)}
    if snap is not None and not snap.error:
        rows = sorted(snap.branches, key=lambda b: b.name != snap.base)       # the base first
        out["branches"] = [_branch(w, b) for b in rows[:BRANCHES]]
    return out


def _name(w, args: dict) -> str:
    name = text(args, "branch", 300)
    if w.branch(name) is None:
        raise ActError(f"No branch {name!r} — it may be gone; look again")
    return name


def _pick(w, args: dict) -> None:
    w.pick(_name(w, args))


def _merge_act(w, args: dict) -> bool:
    name = _name(w, args)
    if name == w.base:
        raise ActError(f"{name} is the base")
    if w.merging:
        raise ActError(f"Already merging {w.merging}")
    return w.merge(name)


def _decline(w, args: dict) -> None:
    w.decline()


def _test(w, args: dict) -> bool:
    if not w.config.get("test_cmd"):
        raise ActError("No test command set — say it in the settings")
    return w.test(_name(w, args))


def _diff(w, args: dict) -> dict:
    name = _name(w, args)
    try:
        return {"title": f"{name} against {w.base}", "text": w.diff(name)}
    except (RuntimeError, OSError, ValueError) as e:
        raise ActError(str(e)) from None


def _pr(w, args: dict) -> str:
    url = w.pr_url(_name(w, args))
    if not url:
        raise ActError("This branch has no pull request")
    return url


def _look(w, args: dict) -> None:
    w.refresh()


def _settings(w, args: dict) -> bool:
    changes = {}
    for key in ("base", "test_cmd", "remote"):
        if key in args:
            changes[key] = " ".join(text(args, key, 500).split()) if key != "test_cmd" else text(args, key, 2000).strip()
    if "confirm" in args:
        changes["confirm"] = bool(args["confirm"])
    if not changes:
        raise ActError("Nothing to change")
    ok = w.save_config(changes)
    if ok and "base" in changes:
        w.refresh()
    return ok


ACTS = {"pick": _pick, "merge": _merge_act, "decline": _decline, "test": _test, "diff": _diff, "pr": _pr,
        "look": _look, "settings": _settings}
