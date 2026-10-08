"""What a phone sees of the town and may do in it: the mobile API, v1 (docs/design/mobile.md).

Stage 0 of that doc: no phone talks to the town yet. What stands is the surface it will use, on the
host's own command table, so the GUI's page and tests reach it today the same way a phone will:

    host.command("mobile.hello")                     # {"name", "version", "api", "commands", ...}
    host.command("mobile.snapshot")                  # the town, small: HUD, questions, buildings
    host.command("mobile.snapshot", {"since": rev})  # {"v", "rev", "same": True} when nothing changed
    host.command("mobile.chat")                      # the Town Hall's last messages, Markdown as plain text
    news(before, after)                              # what a push would say between two snapshots

The compact snapshot is derived from the page's (`Host.snapshot`, gui/state.py), never from the
town directly, so the two cannot disagree. Text that may carry emoji comes twice, as it is and
`_plain` (today's words without emoji: `modes.plain`), as in the page's snapshot.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Callable

from orkcraft import __version__
from orkcraft.gui import markdown
from orkcraft.gui import places as gui_places
from orkcraft.realm import lexicon, modes

API = 1                  # the mobile API's version: a change that breaks a client raises it
CONTEXT_LINES = 3        # of a question's screen, the last lines a phone shows
CHAT_MESSAGES = 20       # of the Town Hall's chat, the most a phone reads at once

# What a phone may ask of the host (v1): the host's command → the acts it may name, when it is
# "act" (type id → acts). Everything else stays on the desktop (docs/design/mobile.md §3).
COMMANDS: dict[str, Any] = {
    "mobile.hello": None,
    "mobile.snapshot": None,
    "mobile.chat": None,
    "orders.answer": None,
    "orders.follow": None,
    "halt": None,
    "place.report": None,
    "you.dnd": None,             # Do not disturb is the person's, wherever they set it (docs/design/portrait.md §5)
    "you.look": None,
    "act": {"pit": ("drop", "drop_file"), "town_hall": ("ask",)},
}

_LEVELS = {"ok": 0, "warn": 1, "over": 2}


def allowed(host, name: str, args: dict | None = None) -> bool:
    """Whether a phone may send this command: on the list, and an `act` only one the list names for
    that building's type. The listener for phones (stage 1) asks it before `host.command`."""
    if name not in COMMANDS:
        return False
    acts = COMMANDS[name]
    if acts is None:
        return True
    args = args or {}
    bid = str(args.get("id", ""))
    bs = host.town.scroll.building(bid)
    if bs is None or bs.demolished:
        return False
    return str(args.get("act", "")) in acts.get(host.type_of(bid), ())


def guard(name: str, args: dict, device: dict | None = None) -> dict:
    """A phone's command as the host gets it, after `allowed`: a drop into The Pit is the phone's own
    text, never read as paths on this machine (a phone names no path, docs/design/mobile.md §7); a place
    report names the phone it came from, as the listener knows it, whatever the report says."""
    args = dict(args)
    if name == "place.report":
        args["device"], args["device_id"] = (device or {}).get("name", ""), (device or {}).get("id", "")
    if name == "act" and args.get("act") == "drop":
        args["args"] = {**(args.get("args") if isinstance(args.get("args"), dict) else {}), "paths": False}
    return args


def hello(host) -> dict[str, Any]:
    """The handshake: what this town speaks, so a phone built for another version says so, and the
    glossary (key, word, the Camp word it replaced), so an app built once says words added later."""
    return {"name": "orkcraft", "version": __version__, "api": API,
            "commands": sorted(COMMANDS), "acts": {k: list(v) for k, v in COMMANDS["act"].items()},
            "words": [{"key": k, "word": w, "was": was} for k, w, was in lexicon.glossary()],
            "places": gui_places.names(host)}


def _alert(a: dict) -> dict[str, Any]:
    advice = a.get("advice")
    return {"id": a["id"], "title": a["title"], "who": a.get("who", ""), "building": a.get("building", ""),
            "options": [list(o) for o in a.get("options") or []],
            "context": list(a.get("context") or [])[-CONTEXT_LINES:],
            "advice": {"key": advice["key"], "why": advice["why"]} if advice else None,
            "waited": a.get("waited", 0.0)}


def _building(b: dict) -> dict[str, Any]:
    return {"id": b["id"], "title": b["title"], "title_plain": modes.plain(b["title"]),
            "type": b["type"], "state": b.get("state", ""),
            "alert": (b.get("alert") or {}).get("id") or None}


def _hud(h: dict) -> dict[str, Any]:
    keys = ("gold", "gold_level", "show_gold", "quota", "quota_level", "agents_working", "agents",
            "alerts", "quiet", "hour_plain")
    return {k: h.get(k) for k in keys}


def _portrait(p: dict) -> dict[str, Any]:
    """The portrait's sheet on the phone: the look, the monogram and Do not disturb (docs/design/portrait.md §5)."""
    return {"look": p.get("look", "camp"), "mono": p.get("mono", ""), "dnd": dict(p.get("dnd") or {})}


def compact(full: dict[str, Any]) -> dict[str, Any]:
    """The page's snapshot, small enough for a phone on a slow link: the HUD's spend and quota, the
    questions that wait (the longest first), each building as its title, type, state and question,
    and how many sessions run. `rev` names this content: the same town, the same `rev`."""
    out = {
        "v": API,
        "project": full.get("project", ""),
        "demo": bool(full.get("demo")),
        "look": full.get("look", "camp"),
        "portrait": _portrait(full.get("portrait") or {}),
        "resources": dict(full.get("resources") or {}),
        "hud": _hud(full.get("hud") or {}),
        "alerts": [_alert(a) for a in full.get("alerts") or []],
        "buildings": [_building(b) for b in full.get("buildings") or []],
        "sessions_running": sum(1 for s in full.get("sessions") or [] if s.get("running")),
    }
    out["rev"] = hashlib.sha256(json.dumps(out, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]
    return out


def snapshot(host, args: dict | None = None) -> dict[str, Any]:
    """`mobile.snapshot`: the compact town, or only `{"v", "rev", "same": True}` when the phone's
    `since` is still the town's `rev` (a phone that comes back asks with what it had)."""
    snap = compact(host.snapshot())
    since = (args or {}).get("since")
    if isinstance(since, str) and since == snap["rev"]:
        return {"v": API, "rev": snap["rev"], "same": True}
    return snap


def news(before: dict[str, Any] | None, after: dict[str, Any]) -> list[dict[str, Any]]:
    """What a push says between two compact snapshots: a question that came (each once), spend or a
    quota that crossed into `warn` or `over`. Nothing on the first look (`before` None): a phone that
    pairs sees the town, it is not woken for what already waited."""
    if before is None:
        return []
    out: list[dict[str, Any]] = []
    seen = {a["id"] for a in before.get("alerts") or []}
    for a in after.get("alerts") or []:
        if a["id"] not in seen:
            out.append({"kind": "alert", "id": a["id"], "title": a["title"], "who": a.get("who", "")})
    old, new = before.get("hud") or {}, after.get("hud") or {}
    for key in ("gold_level", "quota_level"):
        was, now = _LEVELS.get(old.get(key) or "ok", 0), _LEVELS.get(new.get(key) or "ok", 0)
        if now > was and now >= _LEVELS["warn"]:
            out.append({"kind": key.removesuffix("_level"), "level": new[key],
                        "text": new.get(key.removesuffix("_level"), "")})
    return out


def plain_markdown(text: str) -> str:
    """Markdown as the text a person reads: no marks, no markup; a code block keeps its lines."""
    out: list[str] = []
    for tok in markdown._md().parse((text or "")[:markdown.LIMIT]):
        if tok.type == "inline":
            for child in tok.children or []:
                if child.type in ("text", "code_inline"):
                    out.append(child.content)
                elif child.type in ("softbreak", "hardbreak"):
                    out.append("\n")
        elif tok.type in ("fence", "code_block"):
            out.append(tok.content.rstrip("\n") + "\n\n")
        elif tok.type in ("paragraph_close", "heading_close") and not tok.hidden:
            out.append("\n\n")
        elif tok.type == "list_item_open":
            out.append("- ")
        elif tok.type in ("list_item_close", "tr_close", "bullet_list_close", "ordered_list_close", "table_close"):
            out.append("\n")
        elif tok.type in ("th_close", "td_close"):
            out.append("  ")
    return re.sub(r"\n{3,}", "\n\n", "".join(out)).strip()


def chat(host, args: dict | None = None) -> dict[str, Any]:
    """`mobile.chat`: the last messages of the Town Hall's chat (`limit`, at most CHAT_MESSAGES), so a
    phone that asked the Warchief reads his answer. Markdown comes as plain text in the words it was
    written in (emoji aside: `modes.strip_emoji`, never `modes.plain`); a card he gave (a
    building to raise, work for a specialist) is only `offer`: it is answered at the desk."""
    hall = host.town.worker("town_hall")
    if hall is None:
        return {"warchief": "", "thinking": False, "chat": []}
    try:
        limit = min(max(int((args or {}).get("limit") or CHAT_MESSAGES), 1), CHAT_MESSAGES)
    except (TypeError, ValueError):
        limit = CHAT_MESSAGES
    msgs = [{"who": m.get("who", ""), "text": modes.strip_emoji(plain_markdown(str(m.get("text", "")))),
             "ts": str(m.get("ts", "")), "error": bool(m.get("error")), "offer": isinstance(m.get("card"), dict)}
            for m in hall.chat[-limit:]]
    return {"warchief": hall.warchief, "thinking": bool(hall.thinking), "chat": msgs}


def commands(host) -> dict[str, Callable[[dict], Any]]:
    """The host's commands this module adds (`Host.commands`)."""
    return {"mobile.hello": lambda a: hello(host), "mobile.snapshot": lambda a: snapshot(host, a),
            "mobile.chat": lambda a: chat(host, a), "place.report": lambda a: gui_places.report(host, a)}
