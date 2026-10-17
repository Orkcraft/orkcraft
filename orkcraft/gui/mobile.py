"""What a phone sees of the town and may do in it: the mobile API, v1 (docs/design/mobile.md).

Stage 0 of that doc: no phone talks to the town yet. What stands is the surface it will use, on the
host's own command table, so the GUI's page and tests reach it today the same way a phone will:

    host.command("mobile.hello")                     # {"name", "version", "api", "commands", ...}
    host.command("mobile.snapshot")                  # the town, small: HUD, questions, buildings
    host.command("mobile.snapshot", {"since": rev})  # {"v", "rev", "same": True} when nothing changed
    host.command("mobile.chat")                      # the Town Hall's last messages, Markdown as plain text
    host.command("mobile.beat")                      # the phone is in front of the person: a beat of their look
    host.command("mobile.look_done")                 # the person read "since your last look" on the phone
    host.command("audio.fetch", {"building": "g", "episode": "1a2b3c4d", "offset": 0})   # an episode, in chunks
    news(before, after)                              # what a push would say between two snapshots
    host.command("ideas.board")                      # the board in focus: every `ideas.*` (gui/ideas.py)

The compact snapshot is derived from the page's (`Host.snapshot`, gui/state.py), never from the
town directly, so the two cannot disagree. Text that may carry emoji comes twice, as it is and
`_plain` (today's words without emoji: `modes.plain`), as in the page's snapshot.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
from typing import Any, Callable

from orkcraft import __version__
from orkcraft.gui import markdown
from orkcraft.gui import places as gui_places
from orkcraft.realm import catalog, lexicon, modes

API = 1                  # the mobile API's version: a change that breaks a client raises it
CONTEXT_LINES = 3        # of a question's screen, the last lines a phone shows
CHAT_MESSAGES = 20       # of the Town Hall's chat, the most a phone reads at once
AUDIO_CHUNK = 512 * 1024 # of an episode's file, what one `audio.fetch` sends (base64 keeps it under a frame)

# What a phone may ask of the host (v1): the host's command → the acts it may name, when it is
# "act" (type id → acts). Everything else stays on the desktop (docs/design/mobile.md §3).
COMMANDS: dict[str, Any] = {
    "mobile.hello": None,
    "mobile.snapshot": None,
    "mobile.chat": None,
    "mobile.beat": None,         # "since your last look" (core/last_look.py), the phone's face
    "mobile.look_done": None,
    "orders.answer": None,
    "orders.follow": None,
    "halt": None,
    "place.report": None,
    "you.dnd": None,             # Do not disturb is the person's, wherever they set it (docs/design/portrait.md §5)
    "you.look": None,
    "audio.fetch": None,         # an Audio briefing's episode, in chunks: the one file a phone reads (audio-briefing.md §8)
    # a building's quick action, as the desktop's card presses it: only one `quick` names (docs/design/mobile.md §10)
    "building.input": None,
    # Task Fields: a to-do, a note or a task written on the phone (the widget, docs/design/mobile.md §10)
    # read only: an ork's console, a building's Info, a task's history (the v3 camp's sheets, docs/design/mobile.md §12)
    "ork.console": None,
    "info": None,
    "cart.waybill": None,
    # the board in focus (spec 29a §6): every board command, the phone first (decisions §43.10)
    **{f"ideas.{c}": None for c in ("board", "page", "add", "say", "plan", "start", "move", "edit", "track_add",
                                    "track_set", "todo", "drop", "stop", "review_list", "diff", "merge", "back", "drop_task",
                                    "stop_task", "agents", "task", "into", "log", "logs", "goal_save", "goal", "read_now", "roles",
                                    "role_save", "role_drop", "kind_set", "doc")},
    # an Agent pool: its ork's question answered (A2's, pinned on its task) and one ork stopped from the 🥩 list
    "act": {"pit": ("drop", "drop_file"), "town_hall": ("ask",), "fields": ("add",), "barracks": ("answer", "stop_ork")},
}
_BY_BUILDING = {"act", "building.input"}    # the commands `allowed` checks against the building they name

_LEVELS = {"ok": 0, "warn": 1, "over": 2}
IDEA_NEWS = ("asks", "plan", "failed", "done")    # an idea that enters one of these states: a push

# Quick actions a phone never presses: they read the computer (its clipboard, a path on it).
QUICK_NEVER = frozenset({"pit.paste", "knowledge.add"})
# Quick actions that reach outside the camp or take work in at once: the phone asks once before it presses them.
QUICK_ASK = frozenset({"catapult.fire", "forge.merge", "loot.accept_all", "generator.accept_all"})


def quick(actions: list[dict]) -> list[dict[str, Any]]:
    """Of a building's quick actions (its card's, {id, label}), the ones a phone may press: each an input (catalog
    `QUICK_INPUTS`), never one that only changes what the desktop's window shows or reads the computer. `takes`:
    "text" when it needs a line of text; `ask`: the phone confirms it first."""
    out = []
    for a in actions:
        how = catalog.QUICK_INPUTS.get(a["id"])
        if how is None or a["id"] in QUICK_NEVER:
            continue
        out.append({"id": a["id"], "label": a["label"], "takes": "text" if how[1] else "", "ask": a["id"] in QUICK_ASK})
    return out


def allowed(host, name: str, args: dict | None = None) -> bool:
    """Whether a phone may send this command: on the list, an `act` only one the list names for that
    building's type, and a `building.input` only one of the building's quick actions `quick` lets a phone
    press. The listener for phones (stage 1) asks it before `host.command`."""
    if name not in COMMANDS:
        return False
    acts = COMMANDS[name]
    if name not in _BY_BUILDING:
        return True
    args = args or {}
    bid = str(args.get("id", ""))
    bs = host.town.scroll.building(bid)
    if bs is None or bs.demolished:
        return False
    if name == "building.input":
        spec = host.town.spec_of(bid)
        card = [{"id": a.id, "label": a.label} for a in catalog.quick_actions_of(spec)] if spec else []
        return str(args.get("input", "")) in {q["id"] for q in quick(card)}
    act = str(args.get("act", ""))
    if act not in acts.get(host.type_of(bid), ()):
        return False
    if host.type_of(bid) == "barracks" and act == "answer":
        return _pool_question(host, bid, args.get("args"))
    return True


def _pool_question(host, bid: str, args) -> bool:
    """An Agent pool's answer from a phone only to an ork's own question (its `asks` block, ork-console.md §4): never
    a draft's yes (it posts outside the camp), a new persona's, nor a plan the steward sends back."""
    task_id = str((args if isinstance(args, dict) else {}).get("task", ""))
    w = host.town.worker(bid)
    task = w.state.task(task_id) if task_id and w is not None and hasattr(w, "state") else None
    return (task is not None and task.status == "asked" and task.ask_kind == "question" and not task.draft
            and not task.persona_waits)


def guard(name: str, args: dict, device: dict | None = None) -> dict:
    """A phone's command as the host gets it, after `allowed`: a drop into The Pit is the phone's own
    text, never read as paths on this machine (a phone names no path, docs/design/mobile.md §7); a place
    report names the phone it came from, as the listener knows it, whatever the report says; a quick action
    is pressed by the person, never by a bench."""
    args = dict(args)
    if name == "place.report":
        args["device"], args["device_id"] = (device or {}).get("name", ""), (device or {}).get("id", "")
    if name == "act" and args.get("act") == "drop":
        args["args"] = {**(args.get("args") if isinstance(args.get("args"), dict) else {}), "paths": False}
    if name.startswith("ideas.") or name == "halt":
        args["device"] = "phone"               # the event log says which window it was (spec 33 §9), whatever the page sends
    if name == "building.input":
        args["by"] = "person"                  # the person, on their phone: never a bench
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


def _spot(hut) -> list[float] | None:
    """Where the person put the building on the desktop's town, as fractions of the room (the camp the phone draws)."""
    try:
        return [round(float(hut[0]), 2), round(float(hut[1]), 2)] if hut else None
    except (TypeError, ValueError, IndexError):
        return None


def _ork_key(b: dict) -> str:
    """The ork whose console a tap on the building's steward opens (as js/camp/town.js `orkKey`): its stopped or held
    ork, else the one asking or at work, else an Agent pool's first; "" — its steward's Info instead."""
    if b.get("signal") and b["signal"].get("key"):
        return b["signal"]["key"]
    g = b.get("garrison") or []
    o = (next((x for x in g if x.get("status") == "asking"), None) or next((x for x in g if x.get("status") == "busy"), None)
         or (g[0] if g and b.get("type") == "barracks" else None))
    return (o.get("ref") or f"{b['id']}/{str(o.get('name', '')).lower()}") if o else ""


def _todo(b: dict) -> int:
    """A Task board's To Do lane, the carts its siding shows."""
    lanes = ((b.get("card") or {}).get("lanes") or []) if b.get("type") == "fields" else []
    lane = next((x for x in lanes if x.get("id") == "todo"), lanes[0] if lanes else None)
    return int((lane or {}).get("count") or 0)


def _building(b: dict) -> dict[str, Any]:
    return {"id": b["id"], "title": b["title"], "title_plain": modes.plain(b["title"]),
            "type": b["type"], "state": b.get("state", ""), "spot": _spot(b.get("hut")),
            "alert": (b.get("alert") or {}).get("id") or None,
            "quick": quick(b.get("quick") or []),     # the card's own pick (gui/state.py)
            # the v3 camp (pwa/camp.js): its steward by its orkish name, its growth, its status, its siding
            "ork_name": b.get("ork_name", ""), "ork_key": _ork_key(b), "level": b.get("level") or 0,
            "goal": b.get("goal", "balance"), "status": [modes.plain(x) for x in (b.get("status_plain") or [])[:2]],
            "signal": (b.get("signal") or {}).get("kind") or "", "todo": _todo(b)}


CARTS_MAX = 40            # the newest carts a phone gets: what rolls and what stands


def _carts(full: dict) -> list[dict[str, Any]]:
    """The carts on the roads, small: which two buildings, rolling or standing and why, what they carry, their chip
    and what their way spent so far (None: not recorded)."""
    ends = {r["id"]: (r["from"], r["to"]) for r in full.get("roads") or [] if "id" in r}
    out = []
    for c in (full.get("carts") or [])[-CARTS_MAX:]:
        if c.get("road") not in ends:
            continue
        a, z = ends[c["road"]]
        out.append({"id": c["id"], "from": a, "to": z, "state": c.get("state", ""), "stands": bool(c.get("stands")),
                    "age": c.get("age", 0), "load": c.get("load", ""), "ref": c.get("ref", ""),
                    "title": modes.plain(c.get("title", ""))[:60], "tokens": c.get("tokens"), "cost": c.get("cost")})
    return out


def _orkspaces(full: dict) -> list[dict[str, Any]]:
    """The town's orkspaces as a phone picks one: its name, mark, biome (the ground the phone wears), its
    buildings and how many of its orks ask or work."""
    return [{"id": o["id"], "name": o["name"], "icon": o.get("icon", ""), "biome": o.get("biome", ""),
             "buildings": list(o.get("buildings") or []), "questions": o.get("questions", 0),
             "working": o.get("working", 0)} for o in full.get("orkspaces") or []]


def _roads(full: dict) -> list[list[str]]:
    """The roads between the town's buildings as [from, to] pairs, each once: what the phone groups its grid by
    and lights on a long press. Not what a road carries (that stays on the desktop)."""
    ids = {b["id"] for b in full.get("buildings") or []}
    return [list(pair) for pair in sorted({(r["from"], r["to"]) for r in full.get("roads") or []
                                           if r.get("from") in ids and r.get("to") in ids and r["from"] != r["to"]})]


WIDGET_TOP = 5            # of the widget's to-dos, notes and each lane's cards, the most a phone gets


def _widget(full: dict) -> dict[str, Any] | None:
    """The Task Fields the phone keeps open (the first one on a board with the person's to-dos): its to-dos and
    notes, the orks' lanes, and where a new note or task goes down the roads (the buildings' titles, as they are
    and plain), so the
    phone says what writing one starts. None when the town has no such board."""
    b = next((b for b in full.get("buildings") or [] if b.get("type") == "fields"
              and ((b.get("card") or {}).get("todos") is not None or (b.get("card") or {}).get("error"))), None)
    if b is None:
        return None
    c = b["card"]
    titles = {x["id"]: x.get("title", "") for x in full.get("buildings") or []}

    def goes(prefix: str) -> list[dict[str, str]]:
        to = sorted({r["to"] for r in full.get("roads") or []
                     if r.get("from") == b["id"] and str(r.get("event", "")).startswith(prefix) and r.get("to") in titles})
        return [{"id": t, "title": titles[t], "title_plain": modes.plain(titles[t])} for t in to]

    top = lambda part: {**part, "top": list(part.get("top") or [])[:WIDGET_TOP]} if part else None  # noqa: E731
    return {"id": b["id"], "error": c.get("error", ""), "todos": top(c.get("todos")), "notes": top(c.get("ideas")),
            "lanes": [{"id": ln["id"], "label": ln["label"], "count": ln["count"], "top": ln["top"][:WIDGET_TOP]}
                      for ln in c.get("lanes") or []],
            "todo_lane": c.get("todo_lane", ""), "note_lane": c.get("note_lane", ""),
            "sends": {"task": goes("tasks."), "note": goes("notes.")}}


SLOT_ROWS = 20           # of the 🥩 list, the most rows a phone gets


def _slots(full: dict) -> dict[str, Any]:
    """🥩 The ork slots (core/slots.py) as a phone lists them: each ork at work or asking, its line, how long, its
    spend; `stop` only where a phone may stop it (an Agent pool's ork: `stop_ork`), never a terminal's interrupt."""
    s = full.get("slots") or {}
    rows = []
    for r in (s.get("rows") or [])[:SLOT_ROWS]:
        stop = r.get("stop") or {}
        args = stop.get("args") or {}
        can = stop.get("command") == "act" and args.get("act") == "stop_ork"
        rows.append({"key": r.get("key", ""), "name": r.get("name", ""), "state": r.get("state", ""),
                     "mark": r.get("mark", ""), "word": r.get("word", ""), "line": r.get("line", ""),
                     "building": r.get("building_id", ""), "since_s": r.get("since_s"), "spend": r.get("spend", 0.0),
                     "tool": r.get("tool", ""), "asks": bool(r.get("answer")),
                     "stop": {"id": args.get("id", ""), "ork": (args.get("args") or {}).get("ork", "")} if can else None})
    return {"working": s.get("working", 0), "limit": s.get("limit", 0), "asks": s.get("asks", 0),
            "fire": s.get("fire", 0), "rows": rows}


def _pool_questions(full: dict) -> list[dict[str, Any]]:
    """An Agent pool ork's questions (A2: its `asks` block, pinned on top of its task) as a phone answers them: the
    task they are pinned on and why it waits are their context; each question's answers are one tap, or a line."""
    out = []
    for r in (full.get("slots") or {}).get("rows") or []:
        a = r.get("answer") or {}
        if a.get("kind") != "pool":
            continue
        qs = [{"text": str(q.get("text", "")), "options": [str(o) for o in q.get("options") or []]}
              for q in a.get("questions") or [] if isinstance(q, dict)]
        if not qs and a.get("question"):
            qs = [{"text": str(a["question"]), "options": []}]
        out.append({"id": f"pool:{a.get('building', '')}:{a.get('task', '')}", "building": a.get("building", ""),
                    "task": a.get("task", ""), "who": r.get("name", ""), "cart": r.get("cart", ""),
                    "wait": (r.get("wait") or {}).get("line", ""), "assumptions": r.get("assumptions", 0),
                    "waited": float(r.get("since_s") or 0), "questions": qs})
    return out


def _last_look(d: dict[str, Any] | None) -> dict[str, Any] | None:
    """"Since your last look" (realm/last_look.py `digest`) as the phone's first line: the questions stand in Answers,
    so only how many came; what was built, the problems and the cost as they are (each list at most three)."""
    if not d:
        return None
    q = d.get("questions") or {}
    items = q.get("items") or []
    return {"since": d.get("since", ""), "at": d.get("at", ""), "away": d.get("away", ""), "empty": bool(d.get("empty")),
            "headline": d.get("headline", ""), "working": d.get("working", ""),
            "built": {"items": [{"line": i.get("line", ""), "kind": i.get("kind", ""), "building": i.get("building", "")}
                                for i in (d.get("built") or {}).get("items") or []],
                      "more": (d.get("built") or {}).get("more", 0), "summary": (d.get("built") or {}).get("summary", ""),
                      "moved": (d.get("built") or {}).get("moved", 0)},
            "questions": {"count": len(items) + q.get("more", 0), "new": sum(1 for i in items if i.get("new"))},
            "problems": {"items": [{"id": p.get("id", ""), "line": p.get("line", ""), "title": p.get("title", ""),
                                    "waits": p.get("waits", ""), "building": p.get("building", "")}
                                   for p in (d.get("problems") or {}).get("items") or []],
                         "more": (d.get("problems") or {}).get("more", 0)},
            "cost": [c.get("line", "") for c in d.get("cost") or []]}


def _ideas(full: dict) -> dict[str, Any] | None:
    """Where an idea dropped on the phone goes (cut-list.md §3a): the first Task board's Ideas lane (its first lane of
    notes), its title as it is and plain. None when the town has no working Task board."""
    for b in full.get("buildings") or []:
        c = b.get("card") or {}
        if b.get("type") != "fields" or c.get("error") or not c.get("note_lane"):
            continue
        lane = next((n for n in c.get("notes") or [] if n.get("id") == c["note_lane"]), None)
        return {"id": b["id"], "lane": c["note_lane"], "label": (lane or {}).get("label") or "Ideas",
                "title": b.get("title", ""), "title_plain": modes.plain(b.get("title", ""))}
    return None


def _hud(h: dict) -> dict[str, Any]:
    keys = ("gold", "gold_level", "show_gold", "quota", "quota_level", "agents_working", "agents",
            "alerts", "quiet", "hour_plain")
    return {k: h.get(k) for k in keys}


def _portrait(p: dict) -> dict[str, Any]:
    """The portrait's sheet on the phone: the look, the monogram and Do not disturb (docs/design/portrait.md §5), and
    `sleep`, one quiet line when the host is on battery and may sleep (gui/away.py `phone_line`; decisions §18)."""
    return {"look": p.get("look", "camp"), "mono": p.get("mono", ""), "role": p.get("role", ""), "dnd": dict(p.get("dnd") or {}),
            "sleep": str(p.get("sleep") or "")}


def _episodes(buildings: list[dict]) -> list[dict[str, Any]]:
    """The finished episodes of every Audio briefing (its card's), newest first: what a phone may download.
    No transcript and no text of the source (docs/design/audio-briefing.md §8)."""
    out = [{**e, "building": b["id"], "building_title": modes.plain(b.get("title", ""))}
           for b in buildings if b.get("type") == "gramophone"
           for e in ((b.get("card") or {}).get("episodes") or [])]
    return sorted(out, key=lambda e: e.get("at", ""), reverse=True)


def compact(full: dict[str, Any], last_look: dict[str, Any] | None = None) -> dict[str, Any]:
    """The page's snapshot, small enough for a phone on a slow link: the HUD's spend and quota, the
    questions that wait (the longest first), each building as its title, type, state, question and spot,
    the 🥩 list, and how many sessions run; `last_look`: the phone's own greeting (core/last_look.py, face
    "phone"). `rev` names this content: the same town, the same `rev`."""
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
        "orkspaces": _orkspaces(full),
        "active_orkspace": full.get("active_orkspace", ""),
        "widget": _widget(full),
        "ideas": _ideas(full),
        "roads": _roads(full),
        "carts": _carts(full),
        "travel": full.get("travel", 0),
        "score": {k: (full.get("score") or {}).get(k) for k in ("results", "tokens", "cost", "trend", "dislikes",
                                                                 "reworks", "guard", "lean", "recorded")},
        "sessions_running": sum(1 for s in full.get("sessions") or [] if s.get("running")),
        "episodes": _episodes(full.get("buildings") or []),
        "slots": _slots(full),
        "pool_questions": _pool_questions(full),
        "last_look": _last_look(last_look),
        # the board in focus (spec 29a §6): the focus, the board's rev (look again when it moves), how many ideas
        # need the person, and each idea's state (what `news` pushes when it changes)
        "focus": full.get("focus", ""),
        "ideas_rev": int(full.get("ideas_rev") or 0),
        "needs_you": int(full.get("needs_you") or 0),
        "idea_states": [{k: str(i.get(k, "")) for k in ("slug", "title", "state")}
                        for i in full.get("idea_states") or []],
        # Review (spec 33 §5): how many results wait, which (what `news` pushes), and what is left of each AI tool
        "review_count": int(full.get("review_count") or 0),
        "review_results": [{k: str(r.get(k, "")) for k in ("idea", "task", "title")}
                           for r in full.get("review_results") or []],
        "limits": [{"provider": str(x.get("provider", "")), "name": str(x.get("name", "")), "left": x.get("left"),
                    "rows": [dict(r) for r in x.get("rows") or []]} for x in full.get("limits") or []],
    }
    out["rev"] = hashlib.sha256(json.dumps(out, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]
    return out


def phone_snapshot(host) -> dict[str, Any]:
    """The compact town as a phone gets it: with the phone's own "since your last look"."""
    look = getattr(host, "last_look", None)
    return compact(host.snapshot(), look.snapshot(face="phone") if look is not None else None)


def snapshot(host, args: dict | None = None) -> dict[str, Any]:
    """`mobile.snapshot`: the compact town, or only `{"v", "rev", "same": True}` when the phone's
    `since` is still the town's `rev` (a phone that comes back asks with what it had)."""
    snap = phone_snapshot(host)
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
    had = {(e["building"], e["id"]) for e in before.get("episodes") or []}
    for e in after.get("episodes") or []:
        if (e["building"], e["id"]) not in had:
            out.append({"kind": "episode", "building": e["building"], "id": e["id"], "title": e.get("title", ""),
                        "seconds": e.get("seconds", 0)})
    was_in = {i["slug"]: i["state"] for i in before.get("idea_states") or []}
    for i in after.get("idea_states") or []:
        if i["state"] in IDEA_NEWS and was_in.get(i["slug"]) != i["state"]:
            out.append({"kind": "idea", "slug": i["slug"], "title": i["title"], "state": i["state"]})
    seen_results = {(r["idea"], r["task"]) for r in before.get("review_results") or []}
    for r in after.get("review_results") or []:
        if (r["idea"], r["task"]) not in seen_results:
            out.append({"kind": "result", "slug": r["idea"], "task": r["task"], "title": r["title"]})
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
    phone that asked the Workchief reads his answer. Markdown comes as plain text in the words it was
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


def audio_fetch(host, args: dict | None = None) -> dict[str, Any]:
    """`audio.fetch` {building, episode, offset}: a chunk of a finished episode's file, base64, and whether it
    was the last. Only an Audio briefing's own episode, named by its id, never a path."""
    args = args or {}
    bid, eid = str(args.get("building", "")), str(args.get("episode", ""))
    bs = host.town.scroll.building(bid) if bid else None
    if bs is None or bs.demolished or host.type_of(bid) != "gramophone":
        raise ValueError("No such Audio briefing")
    worker = host.town.worker(bid)
    try:
        offset = max(0, int(args.get("offset") or 0))
        data, size = worker.chunk(eid, offset, AUDIO_CHUNK)
    except (TypeError, ValueError):
        raise ValueError("offset is not a number") from None
    except (FileNotFoundError, OSError, AttributeError):
        raise ValueError("No such episode") from None
    e = worker.get(eid) or {}
    return {"building": bid, "episode": eid, "kind": e.get("kind", ""), "offset": offset, "size": size,
            "data": base64.b64encode(data).decode("ascii"), "done": offset + len(data) >= size}


def commands(host) -> dict[str, Callable[[dict], Any]]:
    """The host's commands this module adds (`Host.commands`)."""
    return {"mobile.hello": lambda a: hello(host), "mobile.snapshot": lambda a: snapshot(host, a),
            "mobile.chat": lambda a: chat(host, a), "place.report": lambda a: gui_places.report(host, a),
            "audio.fetch": lambda a: audio_fetch(host, a),
            "mobile.beat": lambda a: host.last_look.beat(face="phone"),
            "mobile.look_done": lambda a: host.last_look.done(face="phone")}
