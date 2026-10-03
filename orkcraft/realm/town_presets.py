"""The town order: a town described in words, waiting in the Town Hall (design: docs/design/onboarding.md).

    save_order(root, prompt, role=…, answers=…)   the interview's summary, left by onboarding
    pending_order(root)                           what waits, or None
    close_order(root, town)                       the Town Builder raised it (realm/town_builder.py)

Ready towns for a role are intents (realm/intents.py). When none fits, the interview's answers are
an order: the Town Builder adapts the role's templates to it, and it waits in the Town Hall until a
plan is approved and raised.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

ORDER = Path(".orkcraft") / "town" / "order.json"


# -- the pending order: a town described in words -------------------------------------------------

def save_order(root: Path, prompt: str, role: str = "", answers: dict | None = None) -> Path:
    path = Path(root) / ORDER
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"prompt": prompt.strip(), "role": role, "answers": answers or {}, "seen": False,
            "ts": dt.datetime.now().isoformat(timespec="seconds")}
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def pending_order(root: Path | None) -> dict | None:
    if root is None:
        return None
    try:
        data = json.loads((Path(root) / ORDER).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or not str(data.get("prompt", "")).strip() or data.get("raised"):
        return None
    return data


def close_order(root: Path, town: str = "") -> None:
    """The Town Builder raised it: the order is kept as a record, no longer pending."""
    order = pending_order(root)
    if order is None:
        return
    order.update(raised=dt.datetime.now().isoformat(timespec="seconds"), town=town)
    (Path(root) / ORDER).write_text(json.dumps(order, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def mark_order_seen(root: Path) -> None:
    order = pending_order(root)
    if order is None or order.get("seen"):
        return
    order["seen"] = True
    (Path(root) / ORDER).write_text(json.dumps(order, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
