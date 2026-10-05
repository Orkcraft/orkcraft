"""What the GUI shows of a building inside its window, one module per type with a worker.

Each module says what the page draws (`detail(worker)`, plain data), the acts the page may ask of
the worker (`ACTS`: name → fn(worker, args)), and, when the worker must look again by itself, how
often (`REFRESH_S` and `refresh(worker)`; the TUI's views run the same timers).

    views.of("lake").detail(worker)
    views.of("fields").ACTS["move"](worker, {"card": "t3", "lane": "done"})
"""
from __future__ import annotations

from types import ModuleType


class ActError(Exception):
    """An act the page asked for that cannot be done; its text is shown to the person."""


def of(type_id: str) -> ModuleType | None:
    from orkcraft.gui.views import fields, lake, scrolls
    return {"lake": lake, "fields": fields, "scrolls": scrolls}.get(type_id)


def text(args: dict, key: str, limit: int = 2_000_000) -> str:
    """A string argument, or ActError: the page sends what a person typed, never trusted for its type."""
    value = args.get(key, "")
    if not isinstance(value, str):
        raise ActError(f"{key} is not text")
    return value[:limit]
