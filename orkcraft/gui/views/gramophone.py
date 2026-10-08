"""📻 The Audio briefing in the GUI (docs/design/audio-briefing.md §7): its card says the last episode and its length,
or the one being made; its window makes one from pasted text, lists the episodes with ▶ and download (the file
comes from `GET /api/audio/<building>/<episode>`, gui/server.py), their transcripts and costs, and its settings:
the key, the voice, the limit, and where the text goes. The making is the worker's (core/workers/gramophone.py)."""
from __future__ import annotations

from orkcraft.gui.views import ActError, text
from orkcraft.realm import gramophone as gm
from orkcraft.realm import logins

EPISODES = 50                 # episodes the window lists
PHONE = 10                    # episodes a phone's snapshot lists


def _ep(e: dict) -> dict:
    return {k: e.get(k, d) for k, d in (("id", ""), ("title", ""), ("lang", ""), ("status", ""), ("step", ""),
                                         ("trigger", ""), ("created", ""), ("ended", ""), ("seconds", 0), ("bytes", 0),
                                         ("kind", ""), ("cost", 0.0), ("estimate", 0.0), ("error", ""))}


def card(w) -> dict:
    """Closed: the one being made (its step), else the last episode; `episodes` are what a phone lists."""
    cur = w.running
    last = next((e for e in w.episodes if e.get("status") not in ("queued",)), None)
    out = {"has_key": w.has_key(), "queue": len(w.queue), "episodes": w.ready(PHONE)}
    if cur is not None:
        return {**out, "state": "running", "title": cur.get("title", ""), "step": cur.get("step", "")}
    if last is None:
        return {**out, "state": "none"}
    return {**out, "state": last.get("status", ""), "title": last.get("title", ""), "seconds": last.get("seconds", 0),
            "at": last.get("ended") or last.get("created", ""), "error": last.get("error", "")}


def _key_where(w) -> str:
    ref = w.key_ref
    return "a login on this machine" if logins.is_ref(ref) else f"${ref}"


def detail(w) -> dict:
    return {
        "episodes": [_ep(e) for e in w.episodes[:EPISODES]],
        "running": _ep(w.running) if w.running else None,
        "has_key": w.has_key(), "key_where": _key_where(w), "has_input": bool(w.last_input[0]),
        "settings": {"language": w.lang_setting, "minutes": w.minutes, "voice": w.voice, "cap_usd": w.cap,
                     "keep": w.keep, "tts_model": w.tts_model},
        "per_minute": gm.usd_for(60), "default_key": gm.KEY,
        "spent": round(sum(float(e.get("cost") or 0.0) for e in w.episodes), 4),
    }


def _make(w, args: dict) -> str:
    try:
        body = text(args, "text", 200_000)
        if body.strip():
            return w.make(body, text(args, "title", 300))
        return w.make_again()
    except ValueError as e:
        raise ActError(str(e)) from None


def _speak(w, args: dict) -> bool:
    if not w.speak_anyway(text(args, "id", 20)):
        raise ActError("That episode does not wait for its price")
    return True


def _delete(w, args: dict) -> bool:
    if not w.delete(text(args, "id", 20)):
        raise ActError("That episode cannot be deleted now")
    return True


def _transcript(w, args: dict) -> dict:
    eid = text(args, "id", 20)
    if w.get(eid) is None:
        raise ActError("No such episode")
    return {"id": eid, "text": w.transcript(eid)}


def _number(args: dict, key: str, kind=float):
    value = args.get(key)
    if value in (None, ""):
        return None
    try:
        return kind(value)
    except (TypeError, ValueError):
        raise ActError(f"{key} is not a number") from None


def _settings(w, args: dict) -> bool:
    changes: dict = {}
    if "language" in args:
        lang = text(args, "language", 10)
        if lang not in gm.LANGUAGES:
            raise ActError("Language: auto, ru or en")
        changes["language"] = None if lang == "auto" else lang
    if "voice" in args:
        changes["voice"] = text(args, "voice", 40).strip() or None
    for key, kind in (("minutes", int), ("cap_usd", float), ("keep", int)):
        if key in args:
            changes[key] = _number(args, key, kind)
    if "key" in args:
        ref = text(args, "key", 140).strip()
        changes["key"] = None if ref in ("", gm.KEY) else ref
    if not changes or not w.save_config(changes):
        raise ActError("The settings were not saved")
    return True


def _save_key(w, args: dict) -> bool:
    try:
        ok = w.save_key(text(args, "secret", 400))
    except (OSError, ValueError) as e:
        raise ActError(f"The key was not kept: {e}") from None
    if not ok:
        raise ActError("Paste a key first")
    return True


ACTS = {"make": _make, "speak": _speak, "delete": _delete, "transcript": _transcript, "settings": _settings,
        "save_key": _save_key}
