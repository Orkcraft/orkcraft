"""🎯 The Catapult in the GUI: what is loaded and what it waits for, the schema check, the shots
(request, answer, code) and, in browser mode, the forms with their fields and a picture of each form
from the last runs. The loading, the shots and the overseer's work are the worker's
(core/workers/catapult.py); the schema and the address are the keeper's to write."""
from __future__ import annotations

import base64
import json

from orkcraft.gui.views import ActError, text
from orkcraft.realm import catapult_mcp as cm, catapult_web as cw, harnesses
from orkcraft.realm.catapult_mcp import routes as cm_routes

SHOTS = 30
JSON_LIMIT = 40_000              # characters of a loaded value shown
PICTURE_LIMIT = 4_000_000        # bytes of a screenshot sent to the page


def _plain(s: str) -> str:
    return " ".join(str(s).replace("🔥", "").replace("🔧", "").replace("🔭", "").replace("🔑", "")
                    .replace("🧠", "").replace("🎯", "").replace("🧪", "").split())


def _line(w) -> tuple[str, str]:
    """The closed card's one line and its tone."""
    load, waits, queued = w.load, w.wait_for, len(w.queue)
    more = f" +{queued}" if queued else ""
    if w.login_needed:
        return ("token refused" if w.mcp_mode else "log in"), "fire"
    if w.asking:
        return "waits for your yes", "fire"
    if w.firing:
        return (f"fill {w.progress}" if w.browser and w.progress else "firing…") + more, "wait"
    if w.busy:
        word = w.busy.split(" ")[0]
        return {"🔧": "repairing…", "🔭": "scouting…", "🔑": "logging in…", "🧠": "mapping…"}.get(word, "busy…"), "wait"
    if w.waiting:
        return "waits" + more, "fire"
    if w.held:
        return "put off" + (f" +{queued - 1}" if queued > 1 else ""), "fire"     # the shot put off is queued too
    if w.paused:
        return "stopped" + more, "wait"
    have = len(waits) - len(load.missing(waits)) if waits else 0
    if waits and load.missing(waits) and (have or not w.shots):      # half loaded (or never fired)
        return f"wait {have}/{len(waits)}{more}", "muted"
    if load.items and not waits:
        return f"{len(load.items)} loaded{more}", "muted"
    if w.shots:
        mark, tone = _mark(w.shots[0])
        return mark + more, tone
    return "idle", "muted"


def _target(w) -> str:
    """Where it sends, short: `POST api.example.com/releases`, or a browser's forms."""
    cfg = w.config
    if w.browser:
        n = len(w.forms)
        return f"{n} form{'' if n == 1 else 's'} · then {'press submit' if cfg.get('finish') == 'press' else 'hand over'}"
    if w.mcp_mode:
        if not w.server:
            return "no MCP server set — to: slack"
        route = w.route
        tool = cm_routes.short_tool(w.mcp_tool(route)) or "learns its tool"
        track = w.track(route)
        how = {"direct": cm_routes.title(cm.direct(route) or {}), "local": "local server, no model"}.get(track, "")
        if track == "carrier":
            who, _ = w.carrier_choice()
            how = f"via {harnesses.need(who).title} — a model call" if who else "no carrier"
        return f"{w.server} · {tool} · {how}"
    url = str(cfg.get("url") or "")
    return f"{cfg.get('method') or 'POST'} {url.split('://', 1)[-1]}" if url else "no address set — dry runs only"


def _mark(s) -> tuple[str, str]:
    if s.dry:
        return ("dry run", "muted") if s.ok else ("✗ dry run", "error")
    done = "✓ sent" if s.track else "✓ filled"
    return ((f"✓ {s.status}" if s.status else done), "ok") if s.ok else (f"✗ {s.status or 'error'}", "error")


def card(w) -> dict:
    """Closed (docs/design/building-views.md): the headline `line` — `wait 2/3`, `3 loaded`, `firing…` /
    `fill 2/5`, `log in`, else `✓ 201` / `✗ 422` — with where it sends, what is loaded and what the schema
    says of it, and the last shot."""
    line, tone = _line(w)
    out = {"line": line, "tone": tone, "browser": w.browser, "target": _target(w),
           "loaded": len(w.load.items), "waits": len(w.wait_for), "problem": "", "last": None}
    if w.load.items:
        try:
            _, problems = w.check_now()
        except Exception:                 # a schema that cannot be read says so in the window
            problems = []
        out["problem"] = problems[0] if problems else ""
    if w.shots:
        s = w.shots[0]
        mark, t = _mark(s)
        out["last"] = {"mark": mark, "tone": t, "at": s.at}
    return out


def _json(value) -> str:
    try:
        out = json.dumps(value, ensure_ascii=False, indent=2)
    except (TypeError, ValueError):
        out = str(value)
    return out if len(out) <= JSON_LIMIT else out[:JSON_LIMIT] + "\n…"


def _shot(w, s) -> dict:
    return {"at": s.at, "when": s.at[5:16].replace("T", " "), "ok": s.ok, "dry": s.dry, "status": s.status, "track": s.track,
            "url": s.url, "body": s.body, "answer": s.answer, "error": s.error,
            "screens": [{"form": r["form"], "path": r["path"]} for r in w.screens(s.at)]}


def _form(w, form: cw.Form, body, pictures: dict[str, str]) -> dict:
    d = w.fdir(form)
    page_map = cw.load_map(d)
    p = w.form_plan(form, body) if page_map is not None else None
    steps = []
    for s in (p.steps if p else []):
        value = "" if body is None or s.literal is not None else str(cw.pick(body, s.path))[:80]
        steps.append({"label": s.label, "from": f'"{s.literal}"' if s.literal is not None else s.path, "by": s.by,
                      "value": value})
    return {"name": form.name, "url": str((page_map or {}).get("url") or form.url), "goal": form.goal,
            "scouted": page_map is not None, "submit": w._submit(form) if page_map is not None else form.submit,
            "reached_by": cw.path_text(page_map) if page_map else "", "fields": len((page_map or {}).get("fields") or []),
            "steps": steps, "unfilled": list(p.unfilled) if p else [], "unused": list(p.unused) if p else [],
            "problems": list(p.problems) if p else [], "by_hand": cw.edited_by_hand(d),
            "script": str((d / "fill.py").relative_to(w.repo_root)) if (d / "fill.py").exists() else "",
            "picture": pictures.get(form.name, "")}


def detail(w) -> dict:
    cfg = w.config
    load = w.load
    body, problems = w.check_now()
    pictures: dict[str, str] = {}
    for r in w.screens():                    # the newest picture of each form
        pictures[r["form"]] = r["path"]
    return {
        "mode": "browser" if w.browser else "mcp" if w.mcp_mode else "api", "url": str(cfg.get("url") or ""),
        "target": _target(w), "mcp": w.mcp_state() if w.mcp_mode else None,
        "method": str(cfg.get("method") or "POST"), "schema": str(cfg.get("schema") or ""),
        "confirm": bool(cfg.get("confirm")), "finish": str(cfg.get("finish") or "leave"),
        "key": str(cfg.get("key") or ""), "ttl": int(cfg.get("ttl") or 0),
        "token": bool(cfg.get("token_env")),
        "wait_for": [{"source": s, "loaded": s in load.items} for s in w.wait_for],
        "loaded": [{"source": s, "json": _json(v)} for s, v in load.items.items()],
        "body": _json(body) if body is not None else "", "problems": problems,
        "state": _plain(w.state_text()), "line": _line(w)[0], "firing": w.firing, "busy": _plain(w.busy),
        "progress": w.progress, "step": w.step, "login": _plain(w.login_needed), "paused": w.paused,
        "held": _json(w.queue.items[0]["body"]) if w.held and len(w.queue) else "",
        "queued": len(w.queue), "failed": w.failed is not None,
        "asking": {"title": _plain(w.asking["title"]), "text": w.asking["text"]} if w.asking else None, "overseer": w.overseer,
        "shots": [_shot(w, s) for s in w.shots[:SHOTS]],
        "forms": [_form(w, f, body, pictures) for f in w.forms] if w.browser else [],
    }


def _fire(w, args: dict) -> bool:
    return w.fire()


def _dry(w, args: dict) -> bool:
    return w.fire(dry=True)


def _answer(w, args: dict) -> None:
    """Fire (`yes`), put it off (it waits at the front of the queue) or let it go (`drop`)."""
    if not w.asking:
        raise ActError("No shot waits for a yes")
    w.answer(bool(args.get("yes")), drop=bool(args.get("drop")))


def _resume(w, args: dict) -> bool:
    if not w.resume():
        raise ActError("The queue is not stopped")
    return True


def _drop(w, args: dict) -> bool:
    what = text(args, "what", 10)
    if what not in ("next", "failed", "load"):
        raise ActError("Drop the next shot, the failed one or the load")
    if not w.drop(what):
        raise ActError({"next": "No shot is queued", "failed": "No shot failed", "load": "Nothing is loaded"}[what])
    return True


def _confirm(w, args: dict) -> bool:
    """Ask before every shot, or not: the `confirm` setting, changed in the command view and in full."""
    want = bool(args.get("on"))
    if bool(w.config.get("confirm")) != want and not w.toggle_confirm():
        raise ActError("The setting was not saved")
    return want


def _need_browser(w) -> None:
    if not w.browser or not w.forms:
        raise ActError("Browser mode with its forms first — ask the keeper")
    if w.simulated:
        raise ActError("The sandbox opens no browsers")
    if w.busy:
        raise ActError(f"Busy: {_plain(w.busy)}")


def _scout(w, args: dict) -> bool:
    _need_browser(w)
    return w.scout()


def _login(w, args: dict) -> bool:
    _need_browser(w)
    return w.login()


def _map(w, args: dict) -> bool:
    _need_browser(w)
    return w.map_fields()


def _finish(w, args: dict) -> str:
    if not w.browser:
        raise ActError("Only a browser Catapult presses submit")
    w.toggle_finish()
    return str(w.config.get("finish") or "leave")


def _picture(w, args: dict) -> str:
    """A screenshot the worker kept, as a data URL (only one of its own)."""
    rel = text(args, "path", 1000)
    if rel not in {r["path"] for r in w.screens()}:
        raise ActError("That picture is no longer kept")
    try:
        data = (w.repo_root / rel).read_bytes()
    except OSError as e:
        raise ActError(str(e)) from None
    if len(data) > PICTURE_LIMIT:
        raise ActError("The picture is too large to show here — open it in Lake")
    return "data:image/png;base64," + base64.b64encode(data).decode()


def _need_mcp(w) -> None:
    if not w.mcp_mode:
        raise ActError("Only a Catapult in mode mcp sends through an MCP server")


def _use_direct(w, args: dict) -> bool:
    """Send by the learned direct path (the first shot on it still asks)."""
    _need_mcp(w)
    pick = args.get("pick", 0)
    if not isinstance(pick, int) or not w.use_direct(pick):
        raise ActError("No direct path is learned yet — a carried shot teaches it")
    return True


def _keep_carrier(w, args: dict) -> bool:
    _need_mcp(w)
    if not w.keep_carrier():
        raise ActError("Nothing is learned yet")
    return True


def _allow_local(w, args: dict) -> bool:
    """Let the Catapult start the local server itself: no model per shot."""
    _need_mcp(w)
    if not w.allow_local(bool(args.get("on"))):
        raise ActError("The setting was not saved")
    return bool(args.get("on"))


ACTS = {"fire": _fire, "dry_run": _dry, "answer": _answer, "resume": _resume, "drop": _drop, "confirm": _confirm, "scout": _scout, "login": _login,
        "map": _map, "finish": _finish, "picture": _picture,
        "use_direct": _use_direct, "keep_carrier": _keep_carrier, "allow_local": _allow_local}
