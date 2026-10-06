"""The town's own settings in the GUI, from the HUD's menu (js/settings.js): how freely the orks decide
(autonomy.py — the level a building without its own follows) and its two waits on the clock, minutes a
question waits and hours you are around a change waits. As the TUI's F10 → Ork autonomy.

    host.commands.update(town_settings.commands(host))
"""
from __future__ import annotations

from typing import Any, Callable

from orkcraft import autonomy, settings


def read(host) -> dict[str, Any]:
    m = host.town.machine
    return {"autonomy": autonomy.word(m.autonomy), "wait": m.autonomy_wait, "rebuild": m.rebuild_wait,
            "waits": list(autonomy.QUESTION_WAITS), "rebuilds": list(autonomy.REBUILD_WAITS),
            "levels": [{"id": autonomy.word(lv.n), "icon": lv.icon, "title": lv.title, "questions": lv.questions,
                        "improves": lv.improves} for lv in autonomy.LEVELS]}


def change(host, args: dict) -> dict[str, Any]:
    """The level (`autonomy`: chains | clock | free) and the waits (`wait` minutes, `rebuild` hours) given."""
    m = host.town.machine
    if args.get("autonomy") in autonomy.WORDS:
        m.autonomy = autonomy.of(args["autonomy"])
    if args.get("wait") is not None:
        m.autonomy_wait = autonomy.wait_of(args.get("wait"))
    if args.get("rebuild") is not None:
        m.rebuild_wait = autonomy.rebuild_of(args.get("rebuild"))
    settings.save(m)
    lv = autonomy.LEVELS[m.autonomy]
    host.town.toast(f"a question waits {m.autonomy_wait} min, a change {m.rebuild_wait} h you are around"
                    if m.autonomy == autonomy.CLOCK else lv.questions, title=f"{lv.icon} {lv.title}")
    host.on_change()
    return read(host)


def commands(host) -> dict[str, Callable[[dict], Any]]:
    return {"town.settings": lambda a: read(host), "town.settings.set": lambda a: change(host, a)}
