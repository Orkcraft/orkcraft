"""Rally pipes 🚩: what a building emits, what it accepts, and the safe payload helpers.

A rally point (`scroll.RallyPoint`) sends one kind of event from a source building to a target:

    on_selection_change  the source's cursor moved → a node id or a file path
    on_task_completed    a deployed garrison orc's session ended → its last screen as text
    on_stream            (not implemented yet — stage 7 ships the first two)

Payloads cross one hop only: a target never forwards what it received, so a chain A → B → C
is two separate pipes fired by their own sources. The scroll refuses loops anyway.
"""
from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from pathlib import Path

NODE, FILE, TEXT = "node", "file", "text"
ON_SELECTION, ON_TASK, ON_STREAM = "on_selection_change", "on_task_completed", "on_stream"
IMPLEMENTED_MODES = (ON_SELECTION, ON_TASK)

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


def set_typed(building_id: str, events: list[str] | tuple[str, ...]) -> None:
    if events:
        TYPED[building_id] = tuple(events)
    else:
        TYPED.pop(building_id, None)


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
class Payload:
    kind: str            # node | file | text
    value: str           # node id, repo-relative path, or markdown text
    source: str          # source building id
    mode: str
    title: str = ""


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
    a plain road only what the target can show (`modes_for`)."""
    if source_id == target_id:
        return []
    if handler:
        return emits(source_id, has_garrison)
    return [m for m in modes_for(source_id, target_id) if m in emits(source_id, has_garrison)]


def modes_for(source_id: str, target_id: str) -> list[str]:
    """The implemented pipe modes that make sense from `source_id` to `target_id`."""
    if source_id == target_id:
        return []
    accepts = RECEIVES.get(target_id, frozenset())
    modes = []
    kind = selection_kind(source_id)
    if kind is not None and kind in accepts:
        modes.append(ON_SELECTION)
    if TEXT in accepts:  # garrison sessions report when they end
        modes.append(ON_TASK)
    modes += [ev for ev in TYPED.get(source_id, ()) if _typed_kind(ev) in accepts]
    return modes


def can_receive(building_id: str) -> bool:
    return bool(RECEIVES.get(building_id))


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
