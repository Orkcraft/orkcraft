"""📻 The Audio briefing's work (docs/design/audio-briefing.md): one episode at a time.

    a text ─▶ the script (its steward's model) ─▶ text for the ear ─▶ the price ─▶ speech (Gemini TTS) ─▶ the file

An episode is a dict kept in `.orkcraft/gramophone/<id>/episodes/<episode id>.json`, its transcript beside it
as `.md` and its audio as `.m4a` (or `.wav` without ffmpeg). What arrives while one is made waits in the queue.
An episode whose speech would cost more than `cap_usd` waits as `held` with its script, until **Speak anyway**.
The key is named, never kept in the spec: an environment variable or a login (`realm/logins.py`).
"""
from __future__ import annotations

import datetime as dt
import json
import re
import threading
import time
import uuid
from collections import deque
from pathlib import Path

from orkcraft.core import delivery
from orkcraft.core.workers import Worker
from orkcraft.realm import gramophone as gm
from orkcraft.realm import halt, logins, pipes, privacy, roads

INPUT_LIMIT = 200_000                 # what of a cart it takes
LOGIN = "gemini"                      # the login a key typed in the window is kept as
ID = re.compile(r"^[0-9a-f]{8}$")
ACTIVE = ("queued", "script", "speaking")
KEY_READ_S = 30.0


def _now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def _simulated_script(title: str) -> str:
    return f"(demo — simulated) A narrator would retell “{title or 'this text'}” here, for the road."


class GramophoneWorker(Worker):
    TYPE = "gramophone"

    def __init__(self, town, building_id: str) -> None:
        super().__init__(town, building_id)
        self.episodes: list[dict] = []           # newest first, the queued ones too
        self.queue: deque[str] = deque()         # episode ids waiting their turn
        self.running: dict | None = None
        self.sources: dict[str, str] = {}        # episode id → its source text, until its script is written
        self.cancel = threading.Event()
        self.lock = threading.RLock()
        self.last_input: tuple[str, str] = ("", "")
        self._halts = halt.count()
        self._key: tuple[str, float, str] | None = None     # (its setting, when read, the key)

    # -- settings -------------------------------------------------------------------------------------

    def _num(self, key: str, default: float) -> float:
        try:
            return float(self.config.get(key, default))
        except (TypeError, ValueError):
            return default

    @property
    def minutes(self) -> int:
        return int(self._num("minutes", gm.MINUTES))

    @property
    def cap(self) -> float:
        return self._num("cap_usd", gm.CAP_USD)

    @property
    def keep(self) -> int:
        return int(self._num("keep", gm.KEEP))

    @property
    def lang_setting(self) -> str:
        lang = str(self.config.get("language") or "auto")
        return lang if lang in gm.LANGUAGES else "auto"

    @property
    def voice(self) -> str:
        return str(self.config.get("voice") or gm.VOICE)

    @property
    def tts_model(self) -> str:
        return str(self.config.get("tts_model") or gm.MODEL)

    @property
    def key_ref(self) -> str:
        return str(self.config.get("key") or gm.KEY)

    def key(self) -> str:
        """The key its setting names, read at most every KEY_READ_S (every snapshot asks `has_key`)."""
        ref, now = self.key_ref, time.monotonic()
        if self._key is not None and self._key[0] == ref and now - self._key[1] < KEY_READ_S:
            return self._key[2]
        try:
            value = logins.resolve(ref)
        except Exception:                        # a keychain that cannot be read is no key
            value = ""
        self._key = (ref, now, value)
        return value

    def has_key(self) -> bool:
        return self.simulated or bool(self.key())

    def save_key(self, secret: str) -> bool:
        """Keep a key typed in the window as the login `gemini`, and name it in the settings."""
        secret = (secret or "").strip()
        if not secret:
            return False
        ref = logins.save(LOGIN, secret, service="gemini")
        self._key = None
        return self.save_config({"key": ref})

    # -- the episodes on disk ---------------------------------------------------------------------------

    @property
    def folder(self) -> Path:
        return self.state_dir / "episodes"

    def _path(self, eid: str, ext: str) -> Path:
        return self.folder / f"{eid}.{ext}"

    def save(self, e: dict) -> None:
        try:
            self.folder.mkdir(parents=True, exist_ok=True)
            self._path(e["id"], "json").write_text(json.dumps(e, ensure_ascii=False, indent=1), encoding="utf-8")
        except OSError:
            pass

    def load(self) -> None:
        found = []
        for p in self.folder.glob("*.json") if self.folder.is_dir() else []:
            try:
                e = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(e, dict) and ID.match(str(e.get("id", ""))):
                if e.get("status") in ACTIVE:       # the window closed while it worked: it did not finish
                    e["status"], e["error"] = "stopped", "Stopped when the town closed"
                found.append(e)
        self.episodes = sorted(found, key=lambda e: e.get("created", ""), reverse=True)

    def start(self) -> None:
        self.load()
        self.changed()

    def get(self, eid: str) -> dict | None:
        return next((e for e in self.episodes if e["id"] == eid), None)

    def transcript(self, eid: str) -> str:
        try:
            return self._path(eid, "md").read_text(encoding="utf-8")
        except OSError:
            return ""

    def file_of(self, eid: str) -> Path | None:
        """A finished episode's audio file: only one of its own, named by its id, never a path."""
        e = self.get(eid) if ID.match(eid or "") else None
        if e is None or e.get("status") != "done" or e.get("kind") not in ("m4a", "wav"):
            return None
        p = self._path(e["id"], e["kind"])
        return p if p.is_file() else None

    def chunk(self, eid: str, offset: int, size: int) -> tuple[bytes, int]:
        """`size` bytes of an episode's file from `offset`, and the file's size (the phone's download)."""
        p = self.file_of(eid)
        if p is None:
            raise FileNotFoundError(eid)
        total = p.stat().st_size
        with p.open("rb") as f:
            f.seek(max(0, min(int(offset), total)))
            return f.read(max(0, int(size))), total

    def ready(self, limit: int = 10) -> list[dict]:
        """The finished episodes, newest first, as a phone lists them: no text."""
        return [{"id": e["id"], "title": e.get("title", ""), "seconds": e.get("seconds", 0), "bytes": e.get("bytes", 0),
                 "kind": e.get("kind", ""), "at": e.get("ended", "")}
                for e in self.episodes if e.get("status") == "done"][:limit]

    def _prune(self) -> None:
        kept, done = [], 0
        for e in self.episodes:
            if e.get("status") in ACTIVE or e.get("status") == "held":
                kept.append(e)
                continue
            done += 1
            if done <= self.keep:
                kept.append(e)
                continue
            for ext in ("json", "md", "m4a", "wav"):
                self._path(e["id"], ext).unlink(missing_ok=True)
        self.episodes = kept

    def delete(self, eid: str) -> bool:
        e = self.get(eid)
        if e is None or e.get("status") in ACTIVE:
            return False
        for ext in ("json", "md", "m4a", "wav"):
            self._path(eid, ext).unlink(missing_ok=True)
        self.episodes = [x for x in self.episodes if x["id"] != eid]
        self.changed()
        return True

    # -- making one ---------------------------------------------------------------------------------------

    def make(self, text: str, title: str = "", trigger: str = "manual", trail: tuple = (), ref: str = "") -> str:
        """An episode of `text`: made now, or after what waits. Its id; ValueError when there is nothing to say."""
        text = (text or "").strip()
        if not text:
            raise ValueError("Nothing to speak: the text is empty")
        title = (title or "").strip() or next((ln.strip("# ").strip() for ln in text.splitlines() if ln.strip()), "")
        lang = self.lang_setting if self.lang_setting != "auto" else gm.language(text)
        e = {"id": uuid.uuid4().hex[:8], "title": title[:160], "lang": lang, "status": "queued", "step": "",
             "trigger": trigger, "created": _now(), "ended": "", "seconds": 0, "bytes": 0, "kind": "",
             "cost": 0.0, "cost_script": 0.0, "cost_speech": 0.0, "estimate": 0.0, "error": "",
             "trail": list(trail), "ref": ref, "minutes": self.minutes}
        self.last_input = (text[:INPUT_LIMIT], title)
        with self.lock:
            self.sources[e["id"]] = text[:INPUT_LIMIT]
            self.episodes.insert(0, e)
            self.queue.append(e["id"])
        self.save(e)
        self._next()
        self.changed()
        return e["id"]

    def make_again(self) -> str:
        text, title = self.last_input
        if not text:
            raise ValueError("Nothing has arrived yet: a road brings the text, or paste one")
        return self.make(text, title)

    def receive(self, payload, title: str, markdown: str) -> None:
        text = payload.value
        if payload.kind == pipes.FILE:
            root = self.repo_root.resolve()
            path = (root / payload.value).resolve()
            try:
                text = path.read_text(encoding="utf-8", errors="replace") if path.is_relative_to(root) else ""
            except OSError:
                text = ""
            text = text or markdown or ""
        try:
            self.make(text, title or payload.title, "road", tuple(payload.trail), payload.ref)
        except ValueError as e:
            self.toast(str(e), severity="warning")

    def speak_anyway(self, eid: str) -> bool:
        """A held episode (over its limit) spoken once, at the price it showed."""
        e = self.get(eid)
        if e is None or e.get("status") != "held":
            return False
        with self.lock:
            e.update(status="queued", force=True, error="")
            self.queue.append(eid)
        self.save(e)
        self._next()
        self.changed()
        return True

    def _next(self) -> None:
        with self.lock:
            if self.running is not None or not self.queue:
                return
            e = self.get(self.queue.popleft())
            if e is None:
                return
            self.running = e
        self.cancel, self._halts = threading.Event(), halt.count()
        threading.Thread(target=self._work, args=(e, self.cancel), daemon=True,
                         name=f"gramophone-{self.building_id}").start()

    def _step(self, e: dict, status: str, step: str = "") -> None:
        e["status"], e["step"] = status, step
        self.save(e)
        self.changed()

    def _script(self, e: dict, cancel: threading.Event) -> str:
        source = self.sources.pop(e["id"], "")
        if not source:
            raise RuntimeError("Its text is gone (the town closed before its script was written)")
        if self.simulated:
            return _simulated_script(e["title"])
        if not self.town.budget_ok():
            raise RuntimeError("🪙 The budget is spent: no script is written")
        clean = privacy.scrub(source).text
        prompt = gm.script_prompt(clean, e["title"], e["lang"], int(e.get("minutes") or self.minutes))
        runner = self.steward_runner("script", str(self.config.get("model") or ""))
        text, cost = runner(prompt)
        e["cost_script"] = round(float(cost or 0.0), 4)
        if cancel.is_set():
            raise InterruptedError("stopped")
        return str(text or "")

    def _work(self, e: dict, cancel: threading.Event) -> None:
        try:
            if not self.has_key():
                raise RuntimeError(f"No Gemini API key: set {gm.KEY} or save a key in the window")
            if not e.get("force") or not self._path(e["id"], "md").is_file():
                self._step(e, "script", "writing the script")
                spoken = gm.speakable(self._script(e, cancel))
                if not spoken:
                    raise RuntimeError("The script came back empty")
                self._path(e["id"], "md").write_text(f"# {e['title']}\n\n{spoken}\n", encoding="utf-8")
            else:
                spoken = self.transcript(e["id"]).split("\n\n", 1)[-1].strip()
            e["estimate"] = gm.estimate_usd(spoken, e["lang"])
            if e["estimate"] > self.cap and not e.get("force"):
                e["status"], e["step"] = "held", ""
                e["error"] = (f"This episode would cost ~${e['estimate']:.2f}, over its limit of ${self.cap:.2f}")
                self.town.call(self._finish, e)
                return
            if not self.simulated and not self.town.budget_ok():
                raise RuntimeError("🪙 The budget is spent: nothing is spoken")
            if self.simulated:
                pcm = gm.tone(2.0)
            else:
                pcm = gm.speak(spoken, self.key(), self.tts_model, self.voice, cancel,
                               progress=lambda n, of: self._step(e, "speaking", f"speaking {n}/{of}"))
            if cancel.is_set():
                raise InterruptedError("stopped")
            e["seconds"] = round(gm.seconds_of_pcm(pcm))
            e["cost_speech"] = 0.0 if self.simulated else gm.usd_for(gm.seconds_of_pcm(pcm))
            path = gm.encode(pcm, self._path(e["id"], "audio"))
            e["kind"], e["bytes"], e["status"] = path.suffix.lstrip("."), path.stat().st_size, "done"
        except InterruptedError:
            e["status"], e["error"] = "stopped", "Stopped by Stop all"
        except Exception as ex:                    # an episode that fails says why; the queue goes on
            e["status"], e["error"] = "failed", f"{ex}"[:400] or type(ex).__name__
        self.town.call(self._finish, e)

    def _finish(self, e: dict) -> None:
        e["cost"] = round(float(e.get("cost_script") or 0.0) + float(e.get("cost_speech") or 0.0), 4)
        e["step"], e["ended"] = "", _now() if e["status"] != "held" else ""
        e.pop("force", None)
        self.running = None
        self.save(e)
        ok, held = e["status"] == "done", e["status"] == "held"
        trail = tuple(e.get("trail") or ()) + (pipes.hop(self.building_id, "narrator", "agent", cost=e["cost"] or None,
                                                         outcome="done" if ok or held else "error",
                                                         since=e["created"], run=e["id"]),)
        if ok:
            minutes = max(1, round(e["seconds"] / 60))
            self.emit("gramophone.done", self.transcript(e["id"]), f"{e['title'][:80]} · {minutes} min",
                      trail=trail, ref=e.get("ref", ""))
        elif held:
            self.toast(e["error"] + " — Speak anyway in the window", severity="warning")
        else:
            self.emit("gramophone.failed", e["error"], e["title"], trail=trail, ref=e.get("ref", ""))
        if e["cost"] or e["status"] == "failed":
            delivery.ran(self.town, roads.HandlerRun(self.building_id, "narrator", "agent", e["id"], 0.0, 0.0,
                                                     outcome="done" if ok or held else "error", error=e.get("error", ""),
                                                     cost_usd=e["cost"] or None, trail=trail, ref=e.get("ref", "")))
        self._prune()
        self.changed()
        if not halt.stopped_since(self._halts):        # after 🛑 Stop all the queue waits
            self._next()

    # -- 🛑 and the hut -----------------------------------------------------------------------------------

    def halt(self) -> int:
        if self.running is None:
            return 0
        self.cancel.set()
        return 1

    def status(self) -> str:
        if self.running is not None:
            return "WORKING"
        last = next((e for e in self.episodes if e.get("status") not in ACTIVE), None)
        return "ERROR" if last is not None and last.get("status") == "failed" else ""

    def quick_action(self, action_id: str) -> bool:
        return False
