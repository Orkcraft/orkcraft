"""The town's own settings in the GUI, from the HUD's menu (js/settings.js): how freely the orks decide
(autonomy.py — the level a building without its own follows) and its two waits on the clock, minutes a
question waits and hours you are around a change waits. As the TUI's F10 → Ork autonomy. Whether flames
climb the roof of a building whose ork waits for you (`fire`, per machine). And whether
anonymous usage stats are shared (core/usage.py), asked once by its own small dialog. Which updates
install by themselves (`updates`; its commands are gui/updates.py's). And the AI tools: which are on
(`tools`) and the main tool every decision runs on, and every step that names `main` (realm/harnesses.py);
the model each tier runs on, per tool (`tier_model`; settings.MachineSettings.tier_models, which wins over
the newest of the tier's family, realm/model_families.py).
Whether the 🌙 Night round looks over the boards at night (`round`: `round_at` in the council's settings),
what its last night found, and Look now (`round.now`; docs/design/night-round.md).

    host.commands.update(town_settings.commands(host))
"""
from __future__ import annotations

import threading
from typing import Any, Callable

from orkcraft import __version__, autonomy, settings
from orkcraft.core import updates, usage
from orkcraft.realm import builders, fastpath, harnesses, model_families, nightround, tiers
from orkcraft.sources import pricing


def _tools(m) -> dict[str, Any]:
    on = {t for t, c in m.tools.items() if c.enabled}
    return {"tools": [{"id": h.id, "title": h.title, "mark": h.mark, "on": h.id in on}
                      for h in harnesses.REGISTRY.values()],
            "main_tool": m.main_tool, "main_now": builders.main_tool(m), "tier_models": _tier_models(m)}


def _latest(name: str, listed: list[str]) -> tuple[str, str]:
    """(text, model) of the newest of a family or a tool's alias: `Latest Gemini Flash High · 3.8`."""
    model = model_families.newest(name, listed) if model_families.is_family(name) else ""
    v = model_families.version_of(name, model) if model else None
    return f"Latest {model_families.words(name)}" + (f" · {'.'.join(map(str, v))}" if v else ""), model


def _price(model: str) -> str:
    """`$4 / $20 per million tokens in / out` when the price tables know the model's family, else ""."""
    p = pricing.price_for(model) or pricing.openai_price_for(model) if model else None
    return f"${p.input:g} / ${p.output:g} per million tokens in / out" if p else ""


def _listing(tools: list) -> None:
    """Ask the tools that can say which models they have, and have not been asked, out of the way."""
    for h in tools:
        threading.Thread(target=lambda h=h: h.pick(h.default_model or next(iter(h.families))),
                         name=f"models-{h.id}", daemon=True).start()


def _tier_models(m) -> list[dict[str, Any]]:
    """Per tool that is on, per tier: what it runs on, what can be chosen (the newest of each family, the
    models the tool listed, the one typed), and its price when known. Never asks a tool: its list comes
    from the cache, and a tool not asked yet is asked in the background."""
    on = [h for h in harnesses.REGISTRY.values() if m.tools.get(h.id) and m.tools[h.id].enabled]
    _listing([h for h in on if h.models_cmd and h.families and model_families.cached(h.id) is None])
    out = []
    for h in on:
        listed = model_families.cached(h.id) or []
        names = list(dict.fromkeys(h.models.values()))
        rows = []
        for tier in tiers.TIERS:
            chosen = str(m.tier_models.get(h.id, {}).get(tier) or "")
            own = h.models.get(tier, "")
            options = [["", _latest(own, listed)[0] if own else "Its own default"]]
            options += [[n, _latest(n, listed)[0]] for n in names if n != own]
            options += [[x, x] for x in listed if [x, x] not in options]
            if chosen and not any(o[0] == chosen for o in options):
                options.append([chosen, chosen])
            pick = chosen or own
            if model_families.is_family(pick):
                text, model = _latest(pick, listed)
            else:
                text, model = (pick, pick) if pick == chosen else (_latest(pick, listed)[0] if pick else "Its own default", pick)
            rows.append({"tier": tier, "label": tiers.label(tier), "chosen": chosen, "now": text,
                         "price": _price(model or pick), "options": options})
        out.append({"id": h.id, "title": h.title, "mark": h.mark, "lists": h.models_cmd is not None, "tiers": rows})
    return out


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
    if isinstance(args.get("tier_model"), dict):       # the model of a tier on a tool; "" back to the latest
        a = args["tier_model"]
        tool, tier, model = a.get("tool"), a.get("tier"), str(a.get("model") or "").strip()
        if tool in harnesses.REGISTRY and tier in tiers.TIERS:
            mine = dict(m.tier_models.get(tool, {}))
            mine.pop(tier, None)
            if model:
                mine[tier] = model
            m.tier_models = settings.clean_tier_models({**m.tier_models, tool: mine})
            settings.save(m)
            kept = m.tier_models.get(tool, {}).get(tier, "")
            host.town.toast(f"{harnesses.title(tool)} runs {tiers.label(tier)} on "
                            f"{kept or 'the latest model of its family'}", title="AI tools")
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
