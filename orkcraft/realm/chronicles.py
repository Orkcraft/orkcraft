"""Building Chronicles: the append-only audit log of a building's mutations (event sourcing).

Every event is one JSON line in `.orkcraft/history/buildings/<building_id>.events.jsonl`
(`scroll.append_event`). Only the types below exist; fields are short scalars — never file
contents, transcripts or secrets. A building with `chronicles.enabled: false` records nothing.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from orkcraft import scroll as ts

FIELD_CHARS = 200

# type → (icon, template). Templates use the event's own fields.
EVENTS: dict[str, tuple[str, str]] = {
    "building_raised": ("🏗", "raised in {orkspace}"),
    "building_demolished": ("💥", "demolished"),
    "building_moved": ("🧭", "moved to orkspace {orkspace}"),
    "pinned": ("📌", "pinned"),
    "unpinned": ("📍", "unpinned"),
    "orc_recruited": ("🧌", "{orc} joined the garrison"),
    "orc_dismissed": ("🗑", "{orc} left the garrison"),
    "orders_changed": ("📜", "{orc}: orders / trigger changed ({trigger})"),
    "orc_deployed": ("⚔", "{orc} deployed ({harness})"),
    "orc_returned": ("🏁", "{orc}'s session ended"),
    "orc_halted": ("🛑", "{orc} halted"),
    "rally_set": ("🚩", "rally point ──► {target} ({mode})"),
    "rally_cleared": ("✂", "rally point cleared"),
    "payload_received": ("📥", "received {kind} from {source}"),
    "handler_ran": ("🪧", "{orc} ran on {roads} road(s): {outcome}"),
    "road_subscribed": ("🛤", "road from {source} ({event}) → {handler}"),
    "road_removed": ("🚧", "road from {source} ({event}) removed"),
    "road_changed": ("🔀", "road from {source}: handler → {handler}"),
    "steward_report": ("🔎", "steward: {findings} finding(s), {proposals} proposal(s)"),
    "proposal_applied": ("✅", "applied: {what}"),
    "card_moved": ("🗂", "{id} → {to}"),
    "card_created": ("🆕", "{id} created"),
    "card_archived": ("🗄", "{id} archived"),
}


def _clean(value: Any) -> Any:
    if isinstance(value, bool) or isinstance(value, (int, float)) or value is None:
        return value
    text = str(value).replace("\n", " ")
    return text if len(text) <= FIELD_CHARS else text[: FIELD_CHARS - 1] + "…"


def record(repo_root: Path, scroll: ts.TownScroll | None, building_id: str, type_: str,
           by: str = "operator", **fields: Any) -> Path | None:
    """Append one event; None when the building's chronicles are disabled.

    Raises ValueError for an event type that is not in `EVENTS` (a programming error).
    """
    if type_ not in EVENTS:
        raise ValueError(f"unknown chronicle event {type_!r}")
    spec = scroll.building(building_id) if scroll is not None else None
    if spec is not None and spec.chronicles.get("enabled") is False:
        return None
    event = {"type": type_, "by": _clean(by), **{k: _clean(v) for k, v in fields.items() if k not in ("ts", "building")}}
    return ts.append_event(repo_root, building_id, event)


def describe(event: dict[str, Any]) -> tuple[str, str]:
    """(icon, sentence) for one stored event; unknown types and missing fields degrade gracefully."""
    icon, template = EVENTS.get(str(event.get("type")), ("·", str(event.get("type", "event"))))

    class _Fields(dict):
        def __missing__(self, key: str) -> str:
            return "?"

    return icon, template.format_map(_Fields(event))


def history(repo_root: Path, building_id: str, limit: int = 200) -> list[dict[str, Any]]:
    """Newest first, for the Building Chronicles overlay."""
    return list(reversed(ts.read_events(repo_root, building_id, limit)))
