"""The town's own settings in the GUI, from the HUD's menu (js/settings.js): how freely the orks decide
(autonomy.py — the level a building without its own follows) and its two waits on the clock, minutes a
question waits and hours you are around a change waits. As the TUI's F10 → Ork autonomy. Whether flames
climb the roof of a building whose ork waits for you (`fire`, per machine). And whether
anonymous usage stats are shared (core/usage.py), asked once by its own small dialog. Which updates
install by themselves (`updates`; its commands are gui/updates.py's). And the AI tools: which are on
(`tools`) and the main tool every decision runs on, and every step that names `main` (realm/harnesses.py).
Whether the 🌙 Night round looks over the boards at night (`round`: `round_at` in the council's settings),
what its last night found, and Look now (`round.now`; docs/design/night-round.md).

    host.commands.update(town_settings.commands(host))
"""
from __future__ import annotations

from typing import Any, Callable

from orkcraft import __version__, autonomy, settings
from orkcraft.core import updates, usage
from orkcraft.realm import builders, fastpath, harnesses, nightround


def _tools(m) -> dict[str, Any]:
    on = {t for t, c in m.tools.items() if c.enabled}
    return {"tools": [{"id": h.id, "title": h.title, "mark": h.mark, "on": h.id in on}
                      for h in harnesses.REGISTRY.values()],
            "main_tool": m.main_tool, "main_now": builders.main_tool(m)}


def _round(host) -> dict[str, Any]:
    repo = host.town.repo_root
    at = str(fastpath.settings(repo).get("round_at") or "")
    last = nightround.nights(repo, 1)
    return {"on": bool(at), "at": at.replace("daily", "").strip() or fastpath.SETTINGS["round_at"].split()[-1],
            "said": nightround.said(last[-1] if last else None), "demo": host.town.demo}


def read(host) -> dict[str, Any]:
    m = host.town.machine
    return {"autonomy": autonomy.word(m.autonomy), "wait": m.autonomy_wait, "rebuild": m.rebuild_wait,
            "waits": list(autonomy.QUESTION_WAITS), "rebuilds": list(autonomy.REBUILD_WAITS),
            "levels": [{"id": autonomy.word(lv.n), "icon": lv.icon, "title": lv.title, "questions": lv.questions,
                        "improves": lv.improves} for lv in autonomy.LEVELS],
            "usage": m.usage, "usage_blocked": usage.blocked(), "fire": m.fire,
            "updates": m.updates, "updates_blocked": updates.blocked() or ("the demo" if host.town.demo else ""),
            "version": __version__, "round": _round(host), **_tools(m)}


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
    if isinstance(args.get("tools"), dict) or "main_tool" in args:      # the AI tools: said apart
        for t, on in (args.get("tools") or {}).items():
            if t in m.tools and isinstance(on, bool):
                m.tools[t] = settings.ToolChoice(enabled=on, billing=m.tools[t].billing)
        if "main_tool" in args:
            m.main_tool = args["main_tool"] if args["main_tool"] in harnesses.REGISTRY else ""
        settings.save(m)
        now = builders.main_tool(m)
        host.town.toast(f"Decisions and steps on main run on {harnesses.title(now)}", title="Main tool")
        host.on_change()
        return read(host)
    if isinstance(args.get("round"), bool):            # the Night round: on at its time, or off
        fastpath.save_settings(host.town.repo_root, {"round_at": fastpath.SETTINGS["round_at"] if args["round"] else ""})
        host.on_change()
        return read(host)
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


def round_now(host, args: dict) -> dict[str, Any]:
    """Look now: the Night round at once. What it said, and the settings as they are."""
    words = host.nightly.round_now()
    host.town.toast(words, title="🌙 Night round")
    return {**read(host), "round_said": words}


def commands(host) -> dict[str, Callable[[dict], Any]]:
    return {"town.settings": lambda a: read(host), "town.settings.set": lambda a: change(host, a),
            "usage.share": lambda a: share_usage(host, a), "round.now": lambda a: round_now(host, a)}
