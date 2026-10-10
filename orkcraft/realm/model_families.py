"""The newest model of a family, asked of the tool that runs it: the code names no version.

    newest("gemini-flash-high", ["gemini-3.7-flash-high", "gemini-3.8-flash-high"]) == "gemini-3.8-flash-high"
    resolve("codex", ("codex", "debug", "models"), parse_codex, "gpt-astra")   # "" when it lists none
    label("gemini-flash-high")       # "Gemini Flash High (3.8)": the version it runs on, from the cache

A **family** is a model id with its version left out after its first word: `gemini-pro-high` is
`gemini-<version>-pro-high`, `gpt-astra` is `gpt-<version>-astra`. A tool's tier table names families
(realm/harnesses.py); a run names the newest model of the family the tool lists. The list is asked of
the tool once a day and kept in the cache (`~/.cache/orkcraft/models.json`); when it cannot be had, or
the family is not in it, the run names no model and the tool runs on its own default. A model with a
version (a person's choice in the settings, a building, a task, an older town scroll) is never
resolved: it runs as written. `ORKCRAFT_MODEL_LIST=0` never asks a tool (the tests).

Pure module, no face.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable, Iterable

from orkcraft.env import getenv

TTL_S = 24 * 3600            # a tool's list is asked again after a day
FAILED_TTL_S = 3600          # … after an hour when it could not be had
ASK_TIMEOUT_S = 30

# Where a model must be named (an API call: the Gramophone's speech), the family's model when no list
# can be had. A CLI never needs it: it runs on its own default. Update here when a family moves on.
FALLBACK: dict[str, str] = {
    "gemini-flash-tts": "gemini-3.1-flash-tts-preview",
}

_FAMILY = re.compile(r"^[a-z]+(?:-[a-z]+)+$")
_TAIL = r"(?P<tail>-preview|-latest|-exp)?"
_lock = threading.Lock()
_memory: dict[str, dict] = {}


def is_family(model: str) -> bool:
    """`gemini-flash-high`, `gpt-astra`: words only, no version. `opus` (one word) is a tool's alias."""
    return bool(_FAMILY.match((model or "").strip().lower()))


def _pattern(family: str) -> re.Pattern:
    first, rest = family.lower().split("-", 1)
    return re.compile(rf"^{re.escape(first)}-(?P<v>\d+(?:\.\d+)*)-{re.escape(rest)}{_TAIL}$")


def version_of(family: str, model: str) -> tuple[int, ...] | None:
    """`(3, 8)` for gemini-3.8-flash-high in `gemini-flash-high`; None when it is not of the family."""
    m = _pattern(family).match((model or "").strip().lower())
    return tuple(int(p) for p in m.group("v").split(".")) if m else None


def family_of(model: str, families: Iterable[str]) -> str | None:
    """The one of `families` that `model` is (itself, or a version of it)."""
    m = (model or "").strip().lower()
    for f in families:
        if f and (m == f.lower() or (is_family(f) and version_of(f, m) is not None)):
            return f
    return None


def newest(family: str, models: Iterable[str]) -> str:
    """The highest version of `family` among `models` (a release over a preview of the same); "" if none."""
    best, best_key = "", None
    pat = _pattern(family)
    for model in models:
        m = pat.match(str(model).strip().lower())
        if not m:
            continue
        key = (tuple(int(p) for p in m.group("v").split(".")), m.group("tail") is None)
        if best_key is None or key > best_key:
            best, best_key = str(model).strip(), key
    return best


# -- what a tool lists ------------------------------------------------------------------------------

def parse_codex(stdout: str) -> list[str]:
    """`codex debug models`: `{"models": [{"slug": "gpt-6-astra", "visibility": "list"}, …]}`; hidden ones left out."""
    try:
        data = json.loads(stdout)
    except ValueError:
        return []
    models = data.get("models") if isinstance(data, dict) else data
    return [str(m["slug"]) for m in models or [] if isinstance(m, dict) and m.get("slug")
            and m.get("visibility") != "hide"]


def parse_agy(stdout: str) -> list[str]:
    """`agy models`: a line per model, its id first and then its name, a tab or a space between
    (`gemini-3.8-flash-high\tGemini 3.8 Flash (High)`)."""
    try:
        data = json.loads(stdout)
    except ValueError:
        data = None
    if isinstance(data, (list, dict)):
        items = data.get("models", []) if isinstance(data, dict) else data
        return [str(i.get("id") or i.get("slug") or i.get("name")) if isinstance(i, dict) else str(i)
                for i in items if i]
    out = []
    for line in stdout.splitlines():
        word = line.split(None, 1)[0] if line.strip() else ""
        if re.match(r"^[a-z][a-z0-9.\-]*\d[a-z0-9.\-]*$", word):
            out.append(word)
    return out


def cache_file() -> Path:
    base = os.environ.get("XDG_CACHE_HOME", "").strip() or str(Path.home() / ".cache")
    return Path(base) / "orkcraft" / "models.json"


def _read_cache() -> dict:
    try:
        data = json.loads(cache_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_cache(tool: str, entry: dict) -> None:
    data = _read_cache()
    data[tool] = entry
    path = cache_file()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
        tmp.replace(path)
    except OSError:
        pass


def _fresh(entry, now: float) -> bool:
    if not isinstance(entry, dict) or not isinstance(entry.get("at"), (int, float)):
        return False
    return now - entry["at"] < (TTL_S if entry.get("models") else FAILED_TTL_S)


def _ask(cmds: Iterable[list[str]], parse: Callable[[str], list[str]]) -> list[str]:
    """The first list a command gives (a refresh, then the tool's own bundled one)."""
    for argv in cmds:
        try:
            proc = subprocess.run(argv, capture_output=True, text=True, timeout=ASK_TIMEOUT_S,
                                  stdin=subprocess.DEVNULL)
        except (OSError, subprocess.SubprocessError):
            continue
        models = parse(proc.stdout) if proc.returncode == 0 else []
        if models:
            return models
    return []


def listed(tool: str, cmds: Iterable[list[str]], parse: Callable[[str], list[str]],
           now: float | None = None) -> list[str]:
    """The models `tool` lists: from the cache while it is a day old, else asked again."""
    now = time.time() if now is None else now
    with _lock:
        entry = _memory.get(tool)
        if not _fresh(entry, now):
            entry = _read_cache().get(tool)
        if not _fresh(entry, now):
            if getenv("MODEL_LIST") == "0":
                return list((entry or {}).get("models") or []) if isinstance(entry, dict) else []
            entry = {"at": now, "models": _ask(cmds, parse)}
            _write_cache(tool, entry)
        _memory[tool] = entry
        return list(entry.get("models") or [])


def forget() -> None:
    """Drop what is kept in memory (the tests; a person's "check for new models")."""
    with _lock:
        _memory.clear()


def resolve(tool: str, cmds: Iterable[list[str]] | None, parse: Callable[[str], list[str]] | None,
            model: str) -> str:
    """The model a run of `tool` names: a family → its newest listed model ("" when none: the tool's
    default); anything else as written (a version someone chose, a tool's alias)."""
    if not model or not is_family(model):
        return model or ""
    if cmds is None or parse is None:
        return ""
    return newest(model, listed(tool, cmds, parse))


def cached(tool: str) -> list[str] | None:
    """The models `tool` listed when it was last asked, never asking it; None when it has not been."""
    with _lock:
        entry = _memory.get(tool) or _read_cache().get(tool)
    return list(entry.get("models") or []) if isinstance(entry, dict) and "models" in entry else None


def known(family: str) -> str:
    """The newest model of `family` in any list kept in the cache, never asking a tool ("" if none)."""
    with _lock:
        lists = [e.get("models") or [] for e in _read_cache().values() if isinstance(e, dict)]
        lists += [e.get("models") or [] for e in _memory.values() if isinstance(e, dict)]
    return newest(family, [m for ms in lists for m in ms])


def for_api(family: str, models: Iterable[str] = ()) -> str:
    """A model an API call must name: the newest of `models`, else the cache's, else FALLBACK."""
    if not is_family(family):
        return family
    return newest(family, models) or known(family) or FALLBACK.get(family, "")


_UPPER = {"gpt": "GPT", "tts": "TTS"}


def words(family: str) -> str:
    """`gemini-flash-high` → `Gemini Flash High`; `opus` → `Opus`."""
    return " ".join(_UPPER.get(w, w.capitalize()) for w in (family or "").lower().split("-"))


def version(family: str) -> str:
    """`3.8`: the version of `family` it runs on, from the lists in the cache ("" when none says)."""
    v = version_of(family, known(family)) if is_family(family) else None
    return ".".join(map(str, v)) if v else ""


def label(model: str) -> str:
    """What a person reads: `gemini-flash-high` → `Gemini Flash High (3.8)`, the version it runs on when
    a list in the cache says (no version when none does); a model with its version stays as written."""
    if not is_family(model):
        return model or ""
    v = version(model)
    return f"{words(model)} ({v})" if v else words(model)
