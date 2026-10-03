"""🎺 The Bugle: a sound for every cart that comes down its roads.

The table says which sound answers which event, one line each, the most precise key wins:

    <building>/<event>: <sound>     that event from that building
    <event>: <sound>                that event from anywhere      (mail.received: chime)
    <building>: <sound>             anything from that building   (gate_pit: ding)
    *: <sound>                      everything else (else: the `default` setting)

A sound is one of the built-in ones (SOUNDS: synthesized once into `.orkcraft/bugle/sounds/`),
`bell` (the terminal's own bell), `none` (stay quiet), or a path to an audio file of your own
(.wav, .mp3, .ogg, .aiff, .m4a, .flac). It plays through the system's player (afplay, paplay,
pw-play, aplay, ffplay; winsound on Windows); with none of them the terminal bell rings instead.

Pure module, no Textual.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import wave
from dataclasses import dataclass
from pathlib import Path

RATE = 22050
BELL, NONE = "bell", "none"
AUDIO = (".wav", ".mp3", ".ogg", ".aiff", ".aif", ".m4a", ".flac")
KEY = re.compile(r"^(\*|[\w-]{1,64}(/[\w.-]{1,64})?|[\w.-]{1,64})$")
KEEP = 200

# name → what it sounds like (the help of the table editor and of the picker)
SOUNDS: dict[str, str] = {
    "horn": "a bugle call: three rising notes",
    "chime": "two soft bells",
    "alarm": "a two-tone siren",
    "drum": "two beats of a war drum",
    "ding": "one short ding",
    BELL: "the terminal's bell",
    NONE: "nothing",
}
CYCLE = tuple(SOUNDS)                    # Enter in the open building walks this order
DEFAULT = "horn"


# -- the table ------------------------------------------------------------------------------------

def is_file(sound: str) -> bool:
    return str(sound).lower().endswith(AUDIO)


def sound_ok(sound: str) -> bool:
    return sound in SOUNDS or is_file(sound)


def parse(lines: list[str]) -> tuple[dict[str, str], list[str]]:
    """`key: sound` lines → {key: sound}, and what could not be read."""
    table, problems = {}, []
    for i, line in enumerate(lines, 1):
        key, sep, sound = str(line).partition(":")
        key, sound = key.strip(), sound.strip()
        if not sep or not key or not sound:
            problems.append(f"line {i}: say `event: sound`")
        elif not KEY.match(key):
            problems.append(f"line {i}: {key!r} is not an event, a building or *")
        elif not sound_ok(sound):
            problems.append(f"line {i}: no sound {sound!r}; choose {', '.join(SOUNDS)} or an audio file")
        else:
            table[key] = sound
    return table, problems


def pick(table: dict[str, str], source: str, event: str, default: str = DEFAULT) -> tuple[str, str]:
    """(sound, the key that chose it) for a cart of `event` from `source`; ("…", "") is the default."""
    for key in (f"{source}/{event}", event, source, "*"):
        if key in table:
            return table[key], key
    return default, ""


def put(lines: list[str], key: str, sound: str) -> list[str]:
    """The table with `key` set to `sound` (in its place when it was there, else at the end)."""
    out, done = [], False
    for line in lines:
        k = str(line).partition(":")[0].strip()
        if k == key:
            if not done:
                out.append(f"{key}: {sound}")
            done = True
        else:
            out.append(str(line))
    return out if done else out + [f"{key}: {sound}"]


def next_sound(sound: str) -> str:
    return CYCLE[(CYCLE.index(sound) + 1) % len(CYCLE)] if sound in CYCLE else CYCLE[0]


def quiet_ok(spec: str) -> bool:
    return not str(spec).strip() or _hours(spec) is not None


def _hours(spec: str) -> tuple[int, int] | None:
    m = re.match(r"^\s*(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})\s*$", str(spec))
    if not m:
        return None
    h1, m1, h2, m2 = map(int, m.groups())
    if h1 > 23 or h2 > 23 or m1 > 59 or m2 > 59:
        return None
    return h1 * 60 + m1, h2 * 60 + m2


def in_quiet(spec: str, now: dt.datetime | None = None) -> bool:
    """`22:00-08:00`: the hours the bugle keeps quiet (they may run over midnight)."""
    hours = _hours(spec) if spec else None
    if hours is None:
        return False
    now = now or dt.datetime.now()
    t, (a, b) = now.hour * 60 + now.minute, hours
    return a <= t < b if a <= b else (t >= a or t < b)


# -- the built-in sounds --------------------------------------------------------------------------

def _tone(freq: float, secs: float, harmonics=(1.0,), attack: float = 0.01, decay: float = 0.0,
          square: bool = False) -> list[float]:
    n = int(RATE * secs)
    out = []
    for i in range(n):
        t = i / RATE
        if square:
            v = 1.0 if math.sin(2 * math.pi * freq * t) >= 0 else -1.0
            v *= 0.35
        else:
            v = sum(a * math.sin(2 * math.pi * freq * (k + 1) * t) for k, a in enumerate(harmonics))
            v /= sum(harmonics)
        env = min(1.0, t / attack) if attack else 1.0
        env *= math.exp(-decay * t) if decay else min(1.0, (secs - t) / 0.03)
        out.append(v * env)
    return out


def _rest(secs: float) -> list[float]:
    return [0.0] * int(RATE * secs)


def samples(name: str) -> list[float]:
    """The built-in sound `name` as samples in -1..1."""
    brass = (1.0, 0.6, 0.4, 0.25, 0.15)
    if name == "horn":
        return (_tone(392.0, 0.16, brass, 0.02) + _rest(0.04) + _tone(523.25, 0.16, brass, 0.02) + _rest(0.04)
                + _tone(659.25, 0.45, brass, 0.02))
    if name == "chime":
        return _tone(1318.5, 0.35, (1.0, 0.3), 0.005, 6.0) + _tone(987.77, 0.6, (1.0, 0.3), 0.005, 5.0)
    if name == "alarm":
        return sum((_tone(f, 0.18, square=True) for f in (880.0, 660.0) * 3), [])
    if name == "drum":
        beat = _tone(70.0, 0.22, (1.0, 0.5), 0.003, 14.0)
        return beat + _rest(0.08) + beat
    if name == "ding":
        return _tone(1760.0, 0.4, (1.0, 0.2), 0.003, 9.0)
    return []


def render(path: Path, name: str, volume: float = 0.6) -> Path:
    """Write the built-in sound `name` as a 16-bit mono WAV (once: an existing file is kept)."""
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = b"".join(struct.pack("<h", int(max(-1.0, min(1.0, s * volume)) * 32767)) for s in samples(name))
    tmp = path.with_suffix(".tmp")
    with wave.open(str(tmp), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(frames)
    tmp.replace(path)
    return path


def sound_file(repo_root: Path, sound: str) -> Path | None:
    """The file to play for `sound`: a built-in one rendered into the cache, or the user's own."""
    if sound in (BELL, NONE):
        return None
    if is_file(sound):
        p = Path(os.path.expanduser(sound))
        p = p if p.is_absolute() else repo_root / p
        return p if p.is_file() else None
    if sound not in SOUNDS:
        return None
    return render(repo_root / ".orkcraft" / "bugle" / "sounds" / f"{sound}.wav", sound)


# -- playing ----------------------------------------------------------------------------------------

PLAYERS = (("afplay",), ("paplay",), ("pw-play",), ("aplay", "-q"), ("ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"))


def player() -> tuple[str, ...] | None:
    """The command that plays a file here, or None (then the terminal bell rings)."""
    if sys.platform == "win32":
        return ("winsound",)
    for cmd in PLAYERS:
        if shutil.which(cmd[0]):
            return cmd
    return None


def play(path: Path, cmd: tuple[str, ...] | None) -> bool:
    """Play `path` without waiting for it. False when there is nothing to play it with."""
    if cmd is None:
        return False
    try:
        if cmd == ("winsound",):
            import winsound  # type: ignore[import-not-found]
            winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC)
            return True
        subprocess.Popen([*cmd, str(path)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
        return True
    except (OSError, ImportError, RuntimeError):
        return False


# -- the log ----------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Call:
    at: str
    source: str
    event: str
    title: str
    sound: str
    played: str             # how: player | bell | muted | quiet | cooldown | none

    @property
    def heard(self) -> bool:
        return self.played in ("player", "bell")


def log(state_dir: Path, call: Call) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    with (state_dir / "calls.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(call.__dict__, ensure_ascii=False) + "\n")


def calls(state_dir: Path, keep: int = KEEP) -> list[Call]:
    """The calls, newest first."""
    try:
        lines = (state_dir / "calls.jsonl").read_text(encoding="utf-8").splitlines()[-keep:]
    except OSError:
        return []
    out = []
    for line in reversed(lines):
        try:
            out.append(Call(**json.loads(line)))
        except (ValueError, TypeError):
            continue
    return out
