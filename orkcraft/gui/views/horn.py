"""📯 The Horn in the GUI: the table (road or event → sound), the calls, mute, quiet hours and the
cooldown. The page plays the sounds (Web Audio): the hut card counts what the worker asked it to play
(core/workers/horn.py), and `audio` hands it the file."""
from __future__ import annotations

import base64
import datetime as dt

from orkcraft.gui.views import ActError, text
from orkcraft.realm import catalog, horn

CALLS = 200                     # the whole log the worker keeps
AUDIO_MAX = 8_000_000           # bytes: a longer file is not a notification sound
MIME = {".wav": "audio/wav", ".mp3": "audio/mpeg", ".ogg": "audio/ogg", ".aiff": "audio/aiff", ".aif": "audio/aiff",
        ".m4a": "audio/mp4", ".flac": "audio/flac"}
WHY = {"muted": "muted", "quiet": "quiet hours", "cooldown": "cooldown", "none": "its sound is none"}


def card(w) -> dict:
    """Closed: the mute toggle and the volume slider draw from this; `plays` tells the page to play `played`;
    how many calls it sounded and kept quiet today, the last call, and the quiet hours (and whether they
    hold now)."""
    today = dt.date.today().isoformat()
    calls = [c for c in w.calls if c.at[:10] == today]
    last = w.calls[0] if w.calls else None
    return {"muted": w.muted, "plays": w.plays, "played": w.played,
            "today": sum(1 for c in calls if c.heard), "kept": sum(1 for c in calls if not c.heard),
            "last": ({"sound": last.sound, "title": last.title or (catalog.event_label(last.event) or last.event),
                      "at": last.at, "heard": last.heard, "why": WHY.get(last.played, "")} if last else None),
            "quiet": w.quiet, "quiet_now": bool(w.quiet) and horn.in_quiet(w.quiet)}


def detail(w) -> dict:
    names = w.titles()
    rows = []
    for source, event in w.rows():
        sound = w.sound_of(source, event)
        rows.append({"source": source, "event": event, "from": names.get(source, source),
                     "label": "everything else" if event == "*" else (catalog.event_label(event) or event),
                     "sound": sound, "file": horn.is_file(sound)})
    calls = [{"at": c.at, "from": names.get(c.source, c.source), "event": catalog.event_label(c.event) or c.event,
              "title": c.title, "sound": c.sound, "heard": c.heard, "why": WHY.get(c.played, "")}
             for c in w.calls[:CALLS]]
    return {"rows": rows, "calls": calls, "muted": w.muted, "quiet": w.quiet, "cooldown": w.cooldown,
            "default": w.default, "problems": w.problems,
            "sounds": [{"id": k, "about": v} for k, v in horn.SOUNDS.items()]}


def _row(args: dict) -> tuple[str, str]:
    event = text(args, "event", 200) or "*"
    return ("" if event == "*" else text(args, "source", 200)), event


def _cycle(w, args: dict) -> str:
    return w.cycle(*_row(args))


def _set(w, args: dict) -> bool:
    sound = text(args, "sound", 1000).strip()
    if not horn.sound_ok(sound):
        raise ActError(f"No sound {sound!r}: choose {', '.join(horn.SOUNDS)} or an audio file")
    if horn.is_file(sound) and horn.sound_file(w.repo_root, sound) is None:
        raise ActError(f"{sound}: no such file")
    return w.set_sound(*_row(args), sound)


def _test(w, args: dict) -> str:
    return w.test(*_row(args))


def _mute(w, args: dict) -> bool:
    on = args.get("on")
    return w.mute(None if on is None else bool(on))


def _settings(w, args: dict) -> bool:
    """Quiet hours, the cooldown and the default sound, each checked as the spec checks it."""
    changes: dict = {}
    if "quiet" in args:
        quiet = text(args, "quiet", 40).strip()
        if not horn.quiet_ok(quiet):
            raise ActError("Quiet hours look like 22:00-08:00")
        changes["quiet"] = quiet
    if "cooldown" in args:
        try:
            cooldown = int(args["cooldown"])
        except (TypeError, ValueError):
            raise ActError("The cooldown is a number of seconds") from None
        if not 0 <= cooldown <= 600:
            raise ActError("The cooldown is 0 to 600 seconds")
        changes["cooldown"] = cooldown
    if "default" in args:
        default = text(args, "default", 1000).strip()
        if not horn.sound_ok(default):
            raise ActError(f"No sound {default!r}")
        changes["default"] = default
    if not changes:
        return False
    if not w.save_config(changes):
        raise ActError("Not saved")
    w.changed()
    return True


def _audio(w, args: dict) -> dict:
    """A sound as the page plays it: a data URL of its file ("" for bell and none, which the page makes
    itself). Only a sound the horn may play: a built-in one or a file its table names."""
    sound = text(args, "sound", 1000).strip()
    own = set(w.table.values()) | {w.default}
    if sound not in horn.SOUNDS and sound not in own:
        raise ActError(f"The horn has no sound {sound!r}")
    path = horn.sound_file(w.repo_root, sound)
    if path is None:
        return {"sound": sound, "url": ""}
    try:
        if path.stat().st_size > AUDIO_MAX:
            raise ActError(f"{sound}: too long for a sound")
        data = path.read_bytes()
    except OSError as e:
        raise ActError(f"{sound}: {e.strerror or e}") from None
    mime = MIME.get(path.suffix.lower(), "audio/wav")
    return {"sound": sound, "url": f"data:{mime};base64,{base64.b64encode(data).decode()}"}


ACTS = {"cycle": _cycle, "set": _set, "test": _test, "mute": _mute, "settings": _settings, "audio": _audio}
