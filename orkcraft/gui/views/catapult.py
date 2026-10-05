"""🎯 The Catapult in the GUI: what is loaded and what it waits for, the schema check, the shots
(request, answer, code) and, in browser mode, the forms with their fields and a picture of each form
from the last runs. The loading, the shots and the overseer's work are the worker's
(core/workers/catapult.py); the schema and the address are the keeper's to write."""
from __future__ import annotations

import base64
import json

from orkcraft.gui.views import ActError, text
from orkcraft.realm import catapult_web as cw

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
        return "log in", "fire"
    if w.asking:
        return "waits for your yes", "fire"
    if w.firing:
        return (f"fill {w.progress}" if w.browser and w.progress else "firing…") + more, "wait"
    if w.busy:
        word = w.busy.split(" ")[0]
        return {"🔧": "repairing…", "🔭": "scouting…", "🔑": "logging in…", "🧠": "mapping…"}.get(word, "busy…"), "wait"
    have = len(waits) - len(load.missing(waits)) if waits else 0
    if waits and load.missing(waits) and (have or not w.shots):      # half loaded (or never fired)
        return f"wait {have}/{len(waits)}{more}", "muted"
    if load.items and not waits:
        return f"{len(load.items)} loaded{more}", "muted"
    if w.shots:
        s = w.shots[0]
        if s.dry:
            return "dry run" + more, "muted"
        mark = (f"✓ {s.status}" if s.status else "✓ filled") if s.ok else f"✗ {s.status or 'error'}"
        return mark + more, "ok" if s.ok else "error"
    return "idle", "muted"


def card(w) -> dict:
    """Closed (docs/design/building-views.md): one line — `wait 2/3`, `3 loaded`, `firing…` / `fill 2/5`,
    `log in`, else `✓ 201` / `✗ 422`."""
    line, tone = _line(w)
    return {"line": line, "tone": tone, "browser": w.browser}


def _json(value) -> str:
    try:
        out = json.dumps(value, ensure_ascii=False, indent=2)
    except (TypeError, ValueError):
        out = str(value)
    return out if len(out) <= JSON_LIMIT else out[:JSON_LIMIT] + "\n…"


def _shot(w, s) -> dict:
    return {"at": s.at, "when": s.at[5:16].replace("T", " "), "ok": s.ok, "dry": s.dry, "status": s.status,
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
        "mode": "browser" if w.browser else "api", "url": str(cfg.get("url") or ""),
        "method": str(cfg.get("method") or "POST"), "schema": str(cfg.get("schema") or ""),
        "confirm": bool(cfg.get("confirm")), "finish": str(cfg.get("finish") or "leave"),
        "key": str(cfg.get("key") or ""), "ttl": int(cfg.get("ttl") or 0),
        "token": bool(cfg.get("token_env")),
        "wait_for": [{"source": s, "loaded": s in load.items} for s in w.wait_for],
        "loaded": [{"source": s, "json": _json(v)} for s, v in load.items.items()],
        "body": _json(body) if body is not None else "", "problems": problems,
        "state": _plain(w.state_text()), "line": _line(w)[0], "firing": w.firing, "busy": _plain(w.busy),
        "progress": w.progress, "step": w.step, "login": _plain(w.login_needed), "paused": w.paused,
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
    if not w.asking:
        raise ActError("No shot waits for a yes")
    w.answer(bool(args.get("yes")))


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


ACTS = {"fire": _fire, "dry_run": _dry, "answer": _answer, "confirm": _confirm, "scout": _scout, "login": _login,
        "map": _map, "finish": _finish, "picture": _picture}
