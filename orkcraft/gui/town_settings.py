"""The town's own settings in the GUI, from the HUD's menu (js/settings.js): how freely the orks decide
(autonomy.py — the level a building without its own follows) and its two waits on the clock, minutes a
question waits and hours you are around a change waits. As the TUI's F10 → Ork autonomy. Whether flames
climb the roof of a building whose ork waits for you (`fire`, per machine). And whether
anonymous usage stats are shared (core/usage.py), asked once by its own small dialog. Which updates
install by themselves (`updates`; its commands are gui/updates.py's).

    host.commands.update(town_settings.commands(host))
"""
from __future__ import annotations

from typing import Any, Callable

from orkcraft import __version__, autonomy, settings
from orkcraft.core import updates, usage


def read(host) -> dict[str, Any]:
    m = host.town.machine
    return {"autonomy": autonomy.word(m.autonomy), "wait": m.autonomy_wait, "rebuild": m.rebuild_wait,
            "waits": list(autonomy.QUESTION_WAITS), "rebuilds": list(autonomy.REBUILD_WAITS),
            "levels": [{"id": autonomy.word(lv.n), "icon": lv.icon, "title": lv.title, "questions": lv.questions,
                        "improves": lv.improves} for lv in autonomy.LEVELS],
            "usage": m.usage, "usage_blocked": usage.blocked(), "fire": m.fire,
            "updates": m.updates, "updates_blocked": updates.blocked() or ("the demo" if host.town.demo else ""),
            "version": __version__}


def change(host, args: dict) -> dict[str, Any]:
    """The level (`autonomy`: chains | clock | free) and the waits (`wait` minutes, `rebuild` hours) given."""
    m = host.town.machine
    if args.get("autonomy") in autonomy.WORDS:
        m.autonomy = autonomy.of(args["autonomy"])
        host.usage.track("autonomy_set", level=args["autonomy"])
    if args.get("wait") is not None:
        m.autonomy_wait = autonomy.wait_of(args.get("wait"))
    if args.get("rebuild") is not None:
        m.rebuild_wait = autonomy.rebuild_of(args.get("rebuild"))
    if isinstance(args.get("fire"), bool):            # the flames over a building that waits: a look, said apart
        m.fire = args["fire"]
        settings.save(m)
        host.on_change()
        return read(host)
    settings.save(m)
    lv = autonomy.LEVELS[m.autonomy]
    host.town.toast(f"a question waits {m.autonomy_wait} min, a change {m.rebuild_wait} h you are around"
                    if m.autonomy == autonomy.CLOCK else lv.questions, title=f"{lv.icon} {lv.title}")
    host.on_change()
    return read(host)


def share_usage(host, args: dict) -> dict[str, Any]:
    """The operator's answer about usage stats (`share`: true | false); the first yes says hello."""
    m = host.town.machine
    was = host.usage.enabled()
    usage.share(m, args.get("share") is True)
    settings.save(m)
    if host.usage.enabled() and not was:
        host._opened()
    host.on_change()
    return read(host)


def commands(host) -> dict[str, Callable[[dict], Any]]:
    return {"town.settings": lambda a: read(host), "town.settings.set": lambda a: change(host, a),
            "usage.share": lambda a: share_usage(host, a)}
