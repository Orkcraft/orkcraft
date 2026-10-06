"""📦 Loot Vault in the GUI: the queue of held carts (what, from where, what the chain cost), the
changed files, what passed; the chosen cart with the chain it came through, step by step. Every
decision is the worker's (core/workers/loot.py); a cart is edited in Lake, in its draft file."""
from __future__ import annotations

import re

from orkcraft.core.workers.loot import label as _label
from orkcraft.gui.views import ActError, text
from orkcraft.realm import feedback, gate, pipes

REFRESH_S = 10.0              # as the TUI
ITEMS = 50
VALUE = 20_000                # characters of a cart shown in the window (Lake has it all)
STORED = 40
GIST = 3                      # what passed lately: the Command Card shows its first lines and links
_LINK = re.compile(r"https?://[^\s)>\]]+")


def refresh(w) -> None:
    w.refresh()


def _waiting_cost(items) -> str:
    toks = [i.tokens for i in items if i.tokens is not None]
    costs = [i.cost for i in items if i.cost is not None]
    return pipes.spent(sum(toks) if toks else None, sum(costs) if costs else None)


def card(w) -> dict:
    """Closed (docs/design/building-views.md): `N to review` or `all reviewed ✓`, `passed: N` and what
    the waiting carts cost."""
    if w.error:
        return {"error": " ".join(w.error.split())[:60]}
    waiting = [i for i in w.queue.items if i.status in (gate.HELD, gate.NEEDS_YOU)]
    return {"to_review": len(waiting), "needs_you": sum(1 for i in waiting if i.status == gate.NEEDS_YOU),
            "files": sum(1 for g in w.rows if not g.reviewed), "passed": len(w.stored),
            "cost": _waiting_cost(waiting)}


def _chain(hops, names: dict[str, str]) -> list[dict]:
    return [{"building": names.get(h.building, h.building), "who": h.orc, "kind": h.kind,
             "spent": pipes.spent(h.tokens, h.cost), "outcome": h.outcome, "branch": h.branch} for h in hops]


def _item(w, it: gate.Item, names: dict[str, str]) -> dict:
    files = w.branches.get(it.id)
    return {"id": it.id, "status": it.status, "title": it.title or it.ref, "label": _label(it), "kind": it.kind,
            "source": names.get(it.source, it.source), "spent": pipes.spent(it.tokens, it.cost),
            "attempts": it.attempts, "why": list(it.why), "notes": list(it.notes), "at": it.at[:16].replace("T", " "),
            "value": it.value[:VALUE], "cut": len(it.value) > VALUE, "chain": _chain(it.hops, names),
            "total": pipes.spent(*pipes.trail_totals(it.hops)), "maker": names.get(w.maker(it), w.maker(it)),
            "edited": w.edited(it), "worktree": it.worktree,
            "branch": {"name": files[0].branch, "files": [{"path": g.path, "change": g.change} for g in files[1]]}
            if files else None}


def _gist(w, path: str) -> dict:
    """What a kept cart says, in short: its first lines (Markdown marks and links aside) and its links."""
    try:
        text_ = (w.repo_root / path).read_text(encoding="utf-8")[:4000]
    except (OSError, ValueError):
        return {"lines": [], "links": []}
    lines = []
    for ln in text_.splitlines()[1:]:                    # the file's first line repeats its title
        if re.match(r"^\*\*.*\*\* — |^_.*_$", ln.strip()):   # `**Title** — who did it`, `_from … · when_`
            continue
        ln = ln.strip(" #*-—")
        if ln and len(lines) < 3:
            lines.append(ln[:200])
    links = [u for u in dict.fromkeys(_LINK.findall(text_)) if not any(u in ln for ln in lines)]
    return {"outcome": _LINK.sub("", lines[0]).strip(" :—") if lines else "", "lines": lines[1:],
            "links": links[:3]}


def detail(w) -> dict:
    names = w.names()
    open_items = w.queue.open()
    stored = w.stored[:STORED]
    toks = [x.tokens for x in w.stored if x.tokens is not None]
    costs = [x.cost for x in w.stored if x.cost is not None]
    return {
        "error": w.error, "scope": str(w.config.get("path") or "") or "the working tree",
        "review": str(w.config.get("review") or "rules"),
        "counts": {s: w.queue.count(s) for s in (gate.HELD, gate.NEEDS_YOU, gate.REWORK)},
        "waiting_cost": _waiting_cost([i for i in open_items if i.status != gate.REWORK]),
        "queue": [_item(w, it, names) for it in open_items[:ITEMS]],
        "files": [{"path": g.path, "change": g.change, "reviewed": g.reviewed} for g in w.rows[:500]],
        "rejected": [{"index": i, "path": r["path"], "at": r["at"]} for i, r in enumerate(w.rejected[:100])],
        "stored": [{"index": i, "at": x.at[:16].replace("T", " "), "title": x.title, "path": x.path,
                    "source": names.get(x.source, x.source), "spent": pipes.spent(x.tokens, x.cost),
                    "chain": _chain(x.hops, names)} for i, x in enumerate(stored)],
        "delivered": [{"title": x.title, "at": x.at[11:16], **_gist(w, x.path)} for x in stored[:GIST]],
        "passed": len(w.stored), "passed_spent": pipes.spent(sum(toks) if toks else None, sum(costs) if costs else None),
        "reasons": [{"tag": t, "label": label} for t, label, _ in feedback.REASONS],
    }


def _held(w, args: dict, statuses=gate.OPEN) -> gate.Item:
    item = w.queue.get(text(args, "item", 200))
    if item is None or item.status not in statuses:
        raise ActError("That cart is no longer waiting here")
    return item


def _accept(w, args: dict) -> None:
    item = _held(w, args, (gate.HELD, gate.NEEDS_YOU))
    if w.edited(item):
        w.accept_draft(item)                      # the person's version, edited in Lake
    else:
        w.accept_item(item)


def _edit(w, args: dict) -> dict:
    """The cart's draft file, to open in Lake; Accept then takes what it says."""
    item = _held(w, args, (gate.HELD, gate.NEEDS_YOU))
    if item.kind != pipes.TEXT:
        raise ActError("Only a text cart is edited — this one is a file: open it")
    path = w.draft_path(item)
    return {"path": str(path.relative_to(w.repo_root)), "title": f"edit: {item.title or item.ref}"}


def _discard_edit(w, args: dict) -> None:
    w.draft_path(_held(w, args), make=False).unlink(missing_ok=True)
    w.changed()


def _rework(w, args: dict) -> str:
    item = _held(w, args, (gate.HELD,))
    reason = " ".join(text(args, "reason", 2000).split())
    tag = text(args, "tag", 40)
    if tag and tag not in {t for t, _, _ in feedback.REASONS}:
        raise ActError("No such reason")
    label = next((lb for t, lb, _ in feedback.REASONS if t == tag), "")
    reason = f"{label}: {reason}" if label and reason else (reason or label)
    if not reason:
        raise ActError("Say why it goes back")
    return w.rework_item(item, reason, tag)


def _drop(w, args: dict) -> None:
    w.drop(_held(w, args))


def _accept_all(w, args: dict) -> int:
    return w.accept_all()


def _accept_files(w, args: dict) -> int:
    return w.accept_files()


def _rel(w, args: dict) -> str:
    rel = text(args, "path", 2000)
    if rel not in {g.path for g in w.rows}:
        raise ActError("That file is no longer changed")
    return rel


def _file_accept(w, args: dict) -> None:
    w.accept(_rel(w, args))
    w.refresh()


def _file_reject(w, args: dict) -> None:
    try:
        w.reject(_rel(w, args))
    except (RuntimeError, OSError, ValueError) as e:
        raise ActError(str(e)) from None
    w.refresh()


def _file_restore(w, args: dict) -> None:
    try:
        r = w.rejected[int(args.get("index", -1))]
    except (IndexError, TypeError, ValueError):
        raise ActError("That file is no longer kept aside") from None
    try:
        w.restore(r["path"], r["at"])
    except (OSError, ValueError) as e:
        raise ActError(str(e)) from None
    w.refresh()


def _preview(w, args: dict) -> dict:
    """A changed file's diff (or a file on a waiting cart's branch), as text."""
    rel = text(args, "path", 2000)
    iid = text(args, "item", 200)
    try:
        if iid:
            found = w.branches.get(iid)
            if found is None or not any(g.path == rel for g in found[1]):
                raise ActError("That file is no longer on the cart's branch")
            return {"path": rel, "text": found[0].preview(rel)}
        return {"path": rel, "text": w.review.preview(_rel(w, args))}
    except (RuntimeError, OSError, ValueError) as e:
        raise ActError(str(e)) from None


ACTS = {"accept": _accept, "edit": _edit, "discard_edit": _discard_edit, "rework": _rework, "drop": _drop,
        "accept_all": _accept_all, "accept_files": _accept_files, "file_accept": _file_accept,
        "file_reject": _file_reject, "file_restore": _file_restore, "preview": _preview}
