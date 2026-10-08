"""📦 The Loot checkpoint: what passes a road at once and what waits for a person.

A cart reaching a Loot building is checked against its rules (the type's config): it **passes**
(`loot.passed` carries it on) or it is **held** in the queue for review. A held cart is accepted
(it passes), or rejected with a reason and sent back to its source for rework — at most
`max_rework` times (3) and while the chain spent less than `rework_tokens`; past that it stays
here as **needs you**, for the person to fix by hand. A cart that comes back with the same `ref`
is the same item, so the count survives the round trip.

    review          always | rules | never            (rules)
    sources         building ids whose carts are held
    paths           globs: a file cart, or a file of its worktree, under one of them is held
    max_cost_usd    the chain's cost above this is held
    max_tokens      the chain's tokens above this are held
    max_files       more changed files in its worktree than this is held
    on_failed       a hop that did not finish clean is held   (yes)
    external        held when `loot.passed` leaves the town    (no)
    max_rework      times a cart may go back                   (3)
    rework_tokens   no rework once the chain spent this many tokens

The queue is `.orkcraft/loot/<id>/queue.json` (local, git-ignored).
"""
from __future__ import annotations

import datetime as dt
import fnmatch
import json
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

from orkcraft.realm import pipes

DEFAULT_MAX_REWORK = 3
KEEP_DONE = 200                          # passed / rejected items kept for the history
HELD, REWORK, NEEDS_YOU, PASSED, DROPPED = "held", "rework", "needs_you", "passed", "dropped"
OPEN = (HELD, REWORK, NEEDS_YOU)


# -- the rules -----------------------------------------------------------------------------------------

@dataclass
class Context:
    """What the rules read besides the cart: its worktree's changed files, whether it leaves town."""
    files: list[str] = field(default_factory=list)
    external: bool = False


def _num(config: dict, key: str) -> float | None:
    try:
        v = config.get(key)
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _list(config: dict, key: str) -> list[str]:
    v = config.get(key) or []
    return [str(x) for x in v] if isinstance(v, list) else [str(v)]


def _matches(path: str, globs: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, g) or fnmatch.fnmatch(path, g.rstrip("/") + "/*")
               or path.startswith(g.rstrip("*").rstrip("/") + "/") for g in globs)


APPROVAL = "approval"                         # a hop's outcome: a draft waits for the person before it goes out
CLEAN = ("", "done", "approved", "rework", APPROVAL)   # a Clan Fire's verdict is how its review ended, not a failure


def reasons(payload: pipes.Payload, config: dict, ctx: Context | None = None,
            names: dict[str, str] | None = None) -> list[str]:
    """Why a cart is held, buildings named by `names` (id → title); empty when it passes."""
    ctx = ctx or Context()
    name = lambda bid: (names or {}).get(bid, bid)
    last = payload.trail[-1] if payload.trail else None
    if last is not None and last.outcome == APPROVAL:       # its maker waits for the person: never waved through
        return [f"{name(last.building)} waits for your approval before it goes out"]
    mode = str(config.get("review") or "rules")
    if mode == "never":
        return []
    if mode == "always":
        return ["every cart is reviewed"]
    why = []
    if payload.source in _list(config, "sources") or any(h.building in _list(config, "sources") for h in payload.trail):
        why.append(f"from {name(payload.source)}")
    if globs := _list(config, "paths"):
        files = ([payload.value] if payload.kind == pipes.FILE else []) + list(ctx.files)
        if hit := next((f for f in files if _matches(f, globs)), None):
            why.append(f"touches {hit}")
    tokens, cost = pipes.trail_totals(payload.trail)
    if (limit := _num(config, "max_cost_usd")) is not None and cost is not None and cost > limit:
        why.append(f"cost ${cost:.2f} > ${limit:.2f}")
    if (limit := _num(config, "max_tokens")) is not None and tokens is not None and tokens > limit:
        why.append(f"{tokens} tokens > {int(limit)}")
    if (limit := _num(config, "max_files")) is not None and len(ctx.files) > limit:
        why.append(f"{len(ctx.files)} files > {int(limit)}")
    last = payload.trail[-1] if payload.trail else None        # how the run that made it ended; an earlier
    if config.get("on_failed", True) and last is not None and last.outcome not in CLEAN:   # failed round was redone
        why.append(f"{name(last.building)} ended {last.outcome}")
    if config.get("external") and ctx.external:
        why.append("leaves the town")
    return why


def describe(config: dict, names: dict[str, str] | None = None) -> list[str]:
    """The rules as a person reads them: what waits for them, what passes by itself, how often a cart may
    go back. `names` turns building ids into their titles."""
    names = names or {}
    out = ["A draft an ork wants to publish always waits for your approval."]
    mode = str(config.get("review") or "rules")
    if mode == "always":
        out.append("Every cart waits for you.")
    elif mode == "never":
        out.append("Every other cart passes by itself.")
    else:
        if sources := _list(config, "sources"):
            out.append(f"A cart from {', '.join(names.get(x, x) for x in sources)} waits.")
        if paths := _list(config, "paths"):
            out.append(f"A cart that touches {', '.join(paths)} waits.")
        if (v := _num(config, "max_cost_usd")) is not None:
            out.append(f"A cart whose chain cost more than ${v:.2f} waits.")
        if (v := _num(config, "max_tokens")) is not None:
            out.append(f"A cart whose chain spent more than {int(v):,} tokens waits.")
        if (v := _num(config, "max_files")) is not None:
            out.append(f"A cart with more than {int(v)} changed files waits.")
        if config.get("on_failed", True):
            out.append("A cart from a run that did not finish clean waits.")
        if config.get("external"):
            out.append("A cart that leaves the town waits.")
        out.append("Anything else passes by itself.")
    if mode != "never":
        limit = int(v) if (v := _num(config, "max_rework")) is not None else DEFAULT_MAX_REWORK
        cap = _num(config, "rework_tokens")
        out.append(f"A cart goes back for rework at most {limit} time{'s' if limit != 1 else ''}"
                   + (f", and not once its chain spent {int(cap):,} tokens" if cap is not None else "")
                   + "; then it needs you.")
    return out


# -- the queue -----------------------------------------------------------------------------------------

@dataclass
class Item:
    id: str
    ref: str
    kind: str
    value: str
    source: str
    mode: str
    title: str
    trail: list[dict] = field(default_factory=list)
    status: str = HELD
    why: list[str] = field(default_factory=list)
    attempts: int = 0                    # times it went back for rework
    notes: list[str] = field(default_factory=list)   # the reasons it was sent back, the person's notes
    worktree: str = ""
    at: str = ""
    updated: str = ""
    rejected: list[dict] = field(default_factory=list)   # files of its branch the person rejected (Branch.reject)

    @property
    def hops(self) -> tuple[pipes.Hop, ...]:
        return pipes.trail_of(self.trail)

    @property
    def tokens(self) -> int | None:
        return pipes.trail_totals(self.hops)[0]

    @property
    def cost(self) -> float | None:
        return pipes.trail_totals(self.hops)[1]

    def payload(self, mode: str | None = None) -> pipes.Payload:
        return pipes.Payload(self.kind, self.value, self.source, mode or self.mode, self.title, self.hops, self.ref)


def _now(now: dt.datetime | None = None) -> str:
    return (now or dt.datetime.now()).isoformat(timespec="seconds")


def worktree_of(payload: pipes.Payload) -> str:
    """The worktree the cart's work happened in: the latest hop that names one."""
    return next((h.worktree for h in reversed(payload.trail) if h.worktree), "")


def branch_of(trail: tuple[pipes.Hop, ...]) -> pipes.Hop | None:
    """The latest hop that names both a worktree and a branch: where the cart's files were committed."""
    return next((h for h in reversed(trail) if h.worktree and h.branch), None)


class Queue:
    def __init__(self, state_dir: Path) -> None:
        self.path = state_dir / "queue.json"
        self.items: list[Item] = self._load()

    def _load(self) -> list[Item]:
        try:
            rows = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        out = []
        for r in rows if isinstance(rows, list) else []:
            try:
                out.append(Item(**{k: r[k] for k in Item.__dataclass_fields__ if k in r}))
            except (TypeError, KeyError):
                continue
        return out

    def save(self) -> None:
        done = [i for i in self.items if i.status not in OPEN][-KEEP_DONE:]
        self.items = [i for i in self.items if i.status in OPEN] + done
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps([asdict(i) for i in self.items], indent=1, ensure_ascii=False), encoding="utf-8")

    # -- what there is -------------------------------------------------------------------------------

    def open(self) -> list[Item]:
        """Waiting items, the ones that need the person first."""
        order = {NEEDS_YOU: 0, HELD: 1, REWORK: 2}
        return sorted((i for i in self.items if i.status in OPEN), key=lambda i: (order[i.status], i.at))

    def get(self, item_id: str) -> Item | None:
        return next((i for i in self.items if i.id == item_id), None)

    def by_ref(self, ref: str) -> Item | None:
        return next((i for i in reversed(self.items) if ref and i.ref == ref and i.status in OPEN), None)

    def count(self, status: str) -> int:
        return sum(i.status == status for i in self.items)

    # -- arrivals --------------------------------------------------------------------------------------

    def arrive(self, payload: pipes.Payload, why: list[str], now: dt.datetime | None = None) -> Item:
        """A cart that is held: a new item, or the next round of one sent back for rework."""
        t = _now(now)
        item = self.by_ref(payload.ref)
        fields = dict(kind=payload.kind, value=payload.value, source=payload.source, mode=payload.mode,
                      title=payload.title, trail=[h.as_dict() for h in payload.trail], why=why,
                      worktree=worktree_of(payload), updated=t)
        if item is not None:
            for k, v in fields.items():
                setattr(item, k, v)
            item.status = HELD
        else:
            iid = uuid.uuid4().hex[:8]
            item = Item(iid, payload.ref or f"loot-{iid}", status=HELD, at=t, **fields)
            self.items.append(item)
        self.save()
        return item

    # -- decisions -------------------------------------------------------------------------------------

    def accept(self, item: Item, value: str | None = None, now: dt.datetime | None = None) -> Item:
        if value is not None:
            item.value = value               # the person's edit
        item.status, item.updated = PASSED, _now(now)
        self.save()
        return item

    def can_rework(self, item: Item, config: dict) -> tuple[bool, str]:
        limit = int(_num(config, "max_rework") if _num(config, "max_rework") is not None else DEFAULT_MAX_REWORK)
        if item.attempts >= limit:
            return False, f"sent back {item.attempts} times"
        cap = _num(config, "rework_tokens")
        if cap is not None and (item.tokens or 0) >= cap:
            return False, f"the chain spent {item.tokens} tokens"
        return True, ""

    def rework(self, item: Item, reason: str, now: dt.datetime | None = None) -> Item:
        item.attempts += 1
        item.notes.append(reason)
        item.status, item.updated = REWORK, _now(now)
        self.save()
        return item

    def needs_you(self, item: Item, why: str, now: dt.datetime | None = None) -> Item:
        item.status, item.updated = NEEDS_YOU, _now(now)
        item.notes.append(why)
        self.save()
        return item

    def file_rejected(self, item: Item, entry: dict) -> Item:
        """One file of the cart's branch rejected: rolled back there, kept aside (`entry`, Branch.reject)."""
        item.rejected.append(entry)
        self.save()
        return item

    def file_restored(self, item: Item, entry: dict) -> Item:
        item.rejected = [r for r in item.rejected if r != entry]
        self.save()
        return item

    def drop(self, item: Item, now: dt.datetime | None = None) -> Item:
        item.status, item.updated = DROPPED, _now(now)
        self.save()
        return item


def rework_markdown(item: Item, reason: str, building_title: str) -> str:
    """What goes back to the source: the reason, the earlier reasons, and what it sent."""
    earlier = "".join(f"- {n}\n" for n in item.notes[:-1])
    files = "".join(f"- `{r['path']}`\n" for r in item.rejected)
    body = item.value if item.kind == pipes.TEXT else f"`{item.value}`"
    return (f"## Sent back for rework by {building_title} (round {item.attempts})\n\n**Why:** {reason}\n\n"
            + (f"Earlier notes:\n{earlier}\n" if earlier else "")
            + (f"Files the person rejected, put back on the branch as the base has them — leave them so:\n{files}\n"
               if files else "")
            + f"Send the fixed version.\n\n---\n\n{body}\n")
