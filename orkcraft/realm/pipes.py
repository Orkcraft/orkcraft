"""Rally pipes 🚩: what a building emits, what it accepts, and the safe payload helpers.

A rally point (`scroll.RallyPoint`) sends one kind of event from a source building to a target:

    on_selection_change  the source's cursor moved → a node id or a file path
    on_task_completed    a deployed garrison orc's session ended → its last screen as text
    on_stream            (not implemented yet — stage 7 ships the first two)

Payloads cross one hop only: a target never forwards what it received, so a chain A → B → C
is two separate pipes fired by their own sources. The scroll refuses loops anyway. What a cart
went through before travels with it all the same: its `trail` (each building and orc that worked
on it, with tokens and cost) and its `ref` (the thing being worked on, stable across hops).
"""
from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from pathlib import Path

NODE, FILE, TEXT = "node", "file", "text"
ON_SELECTION, ON_TASK, ON_STREAM = "on_selection_change", "on_task_completed", "on_stream"

# Who shows what. Scrying Spire renders anything; the Loot Chest keeps reports as files.
RECEIVES: dict[str, frozenset[str]] = {
    "scrying": frozenset({NODE, FILE, TEXT}),
    "loot": frozenset({TEXT}),
}
# The selection a building emits: the Loot Chest browses files, the graph windows nodes.
# Scrying Spire and the War Tent never emit a selection (they are viewers / terminals).
SELECTION_KIND: dict[str, str] = {"loot": FILE}
NO_SELECTION = frozenset({"scrying", "chat", "town_hall"})

# Typed events: what each typed building sends besides the two generic events, set by the
# app from the building specs (catalog.events_of). Their payload kind decides who can show them.
TYPED: dict[str, tuple[str, ...]] = {}
# What each typed building takes by a plain road (catalog.accepts): the payload kinds its worker acts on.
ACCEPTS: dict[str, frozenset[str]] = {}


def set_typed(building_id: str, events: list[str] | tuple[str, ...], accepts: frozenset[str] = frozenset()) -> None:
    if events:
        TYPED[building_id] = tuple(events)
    else:
        TYPED.pop(building_id, None)
    if accepts:
        ACCEPTS[building_id] = frozenset(accepts)
    else:
        ACCEPTS.pop(building_id, None)


def clear_typed() -> None:
    """Forget every typed building (one town at a time)."""
    TYPED.clear()
    ACCEPTS.clear()


def accepts(building_id: str) -> frozenset[str]:
    """The payload kinds a building shows or acts on when a plain road brings them."""
    return RECEIVES.get(building_id) or ACCEPTS.get(building_id, frozenset())


def label(event: str) -> str:
    """How an event reads on roads and cards: the generic ones, else the catalog's label."""
    if event in MODE_LABELS:
        return MODE_LABELS[event]
    from orkcraft.realm import catalog
    return catalog.event_label(event) or event


def _typed_kind(event: str) -> str:
    from orkcraft.realm import catalog
    for t in catalog.TYPES.values():
        e = t.event(event)
        if e is not None:
            return e.kind
    return TEXT


FILE_LIMIT_BYTES = 256 * 1024
REPORT_LINES = 40
MODE_LABELS = {ON_SELECTION: "selection", ON_TASK: "task completed", ON_STREAM: "stream"}


@dataclass(frozen=True)
class Hop:
    """One building's work on a cart: who, what it spent, where (a worktree), how it ended."""
    building: str
    orc: str = ""
    kind: str = ""                # agent | chain | script | hybrid | task
    tokens: int | None = None
    cost: float | None = None
    worktree: str = ""
    branch: str = ""
    outcome: str = ""
    at: str = ""
    base: str = ""                # what the branch was cut from: Loot lists the files of base...branch
    # What a person (or the steward) needs to read a chain afterwards, kept short: the trail never goes
    # into a prompt, the full record is the building's own (`run`).
    ms: int | None = None         # how long the cart was in this building: arrived (or started) → `at`
    model: str = ""               # the model (else the tool) that did the work; "a+b" when steps differ
    decision: str = ""            # the building's own call in a line (DECISION_CHARS): a verdict, a route, a
    #                               plan; or why it did not finish
    round: int | None = None      # 1 + how many times the same work came back here (None: the first time)
    run: str = ""                 # its own record of the work: a handler run, a task, a discussion

    def as_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v not in (None, "")}

    @property
    def started(self) -> str:
        """When the cart came in (`at` less `ms`); "" when the hop does not say how long."""
        if self.ms is None or not self.at:
            return ""
        try:
            return (dt.datetime.fromisoformat(self.at) - dt.timedelta(milliseconds=self.ms)).isoformat(timespec="seconds")
        except ValueError:
            return ""


@dataclass(frozen=True)
class Payload:
    kind: str            # node | file | text
    value: str           # node id, repo-relative path, or markdown text
    source: str          # source building id
    mode: str
    title: str = ""
    trail: tuple[Hop, ...] = field(default=(), compare=False)
    ref: str = ""        # the thing worked on, stable across hops and rework rounds
    route: str = field(default="", compare=False)   # who takes it on, as a Clan Fire that routes decided


DECISION_CHARS = 80


def hop(building: str, orc: str = "", kind: str = "", tokens: int | None = None, cost: float | None = None,
        worktree: str = "", branch: str = "", outcome: str = "", now: dt.datetime | None = None,
        base: str = "", since: str | float | None = None, model: str = "", decision: str = "",
        round: int | None = None, run: str = "") -> Hop:
    """One hop, ending now. `since`: when the cart came in (an ISO time, or seconds before now), for `ms`."""
    now = now or dt.datetime.now()
    first_line = " ".join(str(decision or "").strip().splitlines()[:1]).strip()
    return Hop(building, orc, kind, int(tokens) if tokens is not None else None,
               float(cost) if cost is not None else None, worktree, branch, outcome,
               now.isoformat(timespec="seconds"), base, _ms(since, now), str(model or ""),
               first_line[:DECISION_CHARS - 1] + "…" if len(first_line) > DECISION_CHARS else first_line,
               int(round) if round and int(round) > 1 else None, str(run or ""))


def _ms(since: str | float | None, now: dt.datetime) -> int | None:
    if since in (None, ""):
        return None
    if isinstance(since, (int, float)):
        return max(0, int(since * 1000))
    try:
        then = dt.datetime.fromisoformat(str(since))
    except ValueError:
        return None
    if then.tzinfo is not None:
        then = then.astimezone().replace(tzinfo=None)
    return max(0, int((now - then).total_seconds() * 1000))


def took(ms: int | None) -> str:
    """`850ms`, `42s`, `3m 05s`, `2h 10m`; "" when unknown."""
    if ms is None:
        return ""
    s = ms // 1000
    if s < 1:
        return f"{ms}ms"
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m {s % 60:02d}s"
    return f"{s // 3600}h {s % 3600 // 60:02d}m"


def merge_trails(*trails: tuple[Hop, ...]) -> tuple[Hop, ...]:
    """Several carts' trails as one (a handler ran on a batch): every hop once, in order of time."""
    seen, out = set(), []
    for t in trails:
        for h in t:
            if h not in seen:
                seen.add(h)
                out.append(h)
    return tuple(sorted(out, key=lambda h: h.at))


def trail_totals(trail: tuple[Hop, ...]) -> tuple[int | None, float | None]:
    """(tokens, cost) of the whole chain; None when no hop said."""
    toks = [h.tokens for h in trail if h.tokens is not None]
    costs = [h.cost for h in trail if h.cost is not None]
    return (sum(toks) if toks else None), (round(sum(costs), 4) if costs else None)


def _tok(n: int) -> str:
    return f"{n / 1000:.0f}k" if n >= 10_000 else f"{n / 1000:.1f}k" if n >= 1000 else str(n)


def spent(tokens: int | None, cost: float | None) -> str:
    return " ".join(x for x in ((f"{_tok(tokens)} tok" if tokens is not None else ""),
                                (f"${cost:.2f}" if cost is not None else "")) if x)


def trail_line(trail: tuple[Hop, ...], names: dict[str, str] | None = None) -> str:
    """`Barracks 12k tok $0.08 → Council 40k tok $0.31 = 52k tok $0.39`."""
    if not trail:
        return ""
    names = names or {}
    parts = [" ".join(x for x in (names.get(h.building, h.building), spent(h.tokens, h.cost)) if x) for h in trail]
    total = spent(*trail_totals(trail))
    return " → ".join(parts) + (f" = {total}" if total and len(trail) > 1 else "")


def trail_of(records: list[dict]) -> tuple[Hop, ...]:
    """The hops a stored trail (`Hop.as_dict` rows) names; unknown keys and bad rows are skipped."""
    out = []
    for r in records or ():
        if isinstance(r, dict) and r.get("building"):
            out.append(Hop(**{k: r[k] for k in Hop.__dataclass_fields__ if k in r}))
    return tuple(out)


def selection_kind(building_id: str) -> str | None:
    if building_id in NO_SELECTION:
        return None
    return SELECTION_KIND.get(building_id, NODE)


def emits(building_id: str, has_garrison: bool = True) -> list[str]:
    """The road events a building can send: its selection (if it has one) and, when it has a
    garrison, a deployed orc's finished task."""
    events = [ON_SELECTION] if selection_kind(building_id) is not None else []
    if has_garrison:
        events.append(ON_TASK)
    return events + list(TYPED.get(building_id, ()))


def road_events(source_id: str, target_id: str, has_garrison: bool = True, handler: bool = False) -> list[str]:
    """Events a road source → target can carry: a handler takes anything the source emits;
    a plain road only what the target shows or acts on (`modes_for`)."""
    if source_id == target_id:
        return []
    if handler:
        return emits(source_id, has_garrison)
    return [m for m in modes_for(source_id, target_id) if m in emits(source_id, has_garrison)]


def modes_for(source_id: str, target_id: str) -> list[str]:
    """The implemented pipe modes that make sense from `source_id` to `target_id`."""
    if source_id == target_id:
        return []
    kinds = accepts(target_id)
    modes = []
    kind = selection_kind(source_id)
    if kind is not None and kind in kinds:
        modes.append(ON_SELECTION)
    if TEXT in kinds:  # garrison sessions report when they end
        modes.append(ON_TASK)
    modes += [ev for ev in TYPED.get(source_id, ()) if _typed_kind(ev) in kinds]
    return modes


def read_file_payload(repo_root: Path, path: str | Path) -> tuple[str, str]:
    """(title, markdown) for a file the Loot Chest pointed at — never outside the repository.

    Symlinks are resolved first, so a link out of the repo is refused like `../..`. Big and
    binary files are not rendered, only described.
    """
    root = repo_root.resolve()
    try:
        target = (root / path).resolve() if not Path(path).is_absolute() else Path(path).resolve()
        rel = target.relative_to(root)
    except (OSError, ValueError):
        return "🚫 outside the repository", "_Rally pipes only carry files inside the repository._"
    if not target.is_file():
        return f"📁 {rel}", "_Not a file._"
    size = target.stat().st_size
    if size > FILE_LIMIT_BYTES:
        return f"📄 {rel}", f"_{size // 1024} KB — too big to preview (limit {FILE_LIMIT_BYTES // 1024} KB)._"
    data = target.read_bytes()
    if b"\0" in data[:4096]:
        return f"📄 {rel}", "_Binary file._"
    text = data.decode("utf-8", errors="replace")
    if target.suffix.lower() in (".md", ".markdown"):
        return f"📄 {rel}", text
    fence = "````" if "```" in text else "```"
    lang = target.suffix.lstrip(".")
    return f"📄 {rel}", f"{fence}{lang}\n{text}\n{fence}"


def task_report(orc_name: str, building_title: str, lines: list[str]) -> tuple[str, str]:
    """(title, markdown) of a finished garrison session: its last non-empty screen lines."""
    tail = [l.rstrip() for l in lines if l.strip()][-REPORT_LINES:]
    stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    title = f"🧌 {orc_name} · {building_title} — task completed"
    body = "\n".join(tail) or "(no output)"
    fence = "````" if "```" in body else "```"
    return title, f"_{stamp}_\n\n{fence}\n{body}\n{fence}\n"


def write_loot(repo_root: Path, source_id: str, title: str, markdown: str) -> Path:
    """Keep a report in `./loot/pipes/` under a generated name (never a caller-chosen path)."""
    folder = repo_root / "loot" / "pipes"
    folder.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    safe_source = re.sub(r"[^a-z0-9_-]", "_", source_id.lower())[:32] or "building"
    path = folder / f"{stamp}-{safe_source}.md"
    n = 2
    while path.exists():
        path = folder / f"{stamp}-{safe_source}-{n}.md"
        n += 1
    path.write_text(f"# {title}\n\n{markdown}", encoding="utf-8")
    return path
