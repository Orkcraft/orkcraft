"""🧪 The Test bench's environments and case sets (docs/design/improve-buildings.md §5.2): where its runs stand, and the
alike cases each runs there.

An **environment** is a small project written once from a person's words ("a Python service, no network, three
failing tests") — its files, kept beside the building and given to every run as the project it starts from; the
setup's own is *this project* (a copy of the town's). A **case set** is what its cases do in one environment and how
many: one call to a light model writes them all, alike enough that their mean says something, kept and read again
on every run; never one call a case.

    lab_envs.env_prompt(about) → parse_env(text)           one call, once: the environment's name and its files
    lab_envs.set_prompt(…) → lab_cases.parse_cases(text)   one call: the set's N cases
    lab_envs.estimate(results, n)                          what N cases will cost, from the last run of the set

No face and no model here: the calls are the caller's (gui/lab_runs.py).
"""
from __future__ import annotations

import datetime as dt
import json
import uuid
from pathlib import Path, PurePosixPath

from orkcraft.realm import bench_kits

PROJECT = "project"               # the setup's environment: a copy of the town's own project
PROJECT_NAME = "this project"
FILES_MAX = 24                    # files an environment may have
CHARS_MAX = 80_000                # characters in all of them
SET_MAX = 20                      # cases in one set
NAME_CHARS = 32


def project_env() -> dict:
    return {"id": PROJECT, "name": PROJECT_NAME, "about": "a copy of the town's own project", "files": 0, "at": ""}


def new_env(name: str, about: str, files: dict[str, str]) -> dict:
    return {"id": f"e{uuid.uuid4().hex[:6]}", "name": " ".join(name.split())[:NAME_CHARS] or "an environment",
            "about": about.strip()[:2000], "files": len(files), "at": dt.datetime.now().isoformat(timespec="seconds")}


def new_set(env: str, about: str, count: int) -> dict:
    return {"id": f"s{uuid.uuid4().hex[:6]}", "env": env, "about": about.strip()[:2000],
            "count": max(1, min(int(count), SET_MAX)), "at": dt.datetime.now().isoformat(timespec="seconds")}


# -- an environment's files, kept beside the building --------------------------------------------------------------

def files_path(state_dir: Path, env_id: str) -> Path:
    return state_dir / "envs" / f"{env_id}.json"


def save_files(state_dir: Path, env_id: str, files: dict[str, str]) -> None:
    path = files_path(state_dir, env_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(files, ensure_ascii=False, indent=1), encoding="utf-8")


def load_files(state_dir: Path, env_id: str) -> dict[str, str]:
    """Its files; {} for the setup's (a copy of the town's project is made instead) or one gone."""
    if env_id == PROJECT:
        return {}
    try:
        data = json.loads(files_path(state_dir, env_id).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}


# -- writing one ---------------------------------------------------------------------------------------------------

def env_prompt(about: str) -> str:
    return f"""You write a small, self-contained project a Test bench runs AI agents in. It has no network: nothing in it may
install packages, call an API or read a URL, so use only the language's standard library.

What the person wants it to be:
{about.strip()}

Make it real and small: at most {FILES_MAX} files and {CHARS_MAX // 1000}k characters in all, a README.md that says
what it is, and its tests or a check command when it has code. Give it a short name of at most three words.

Answer with JSON only:
{{"name": "…", "files": {{"README.md": "…", "path/to/file": "…"}}}}"""


def parse_env(text: str) -> tuple[str, dict[str, str]] | None:
    """(name, files) of a model's answer, its paths checked to stay inside the project; None when it holds none."""
    data = bench_kits.answer_json(text)
    files, total = {}, 0
    for rel, body in (data.get("files") or {}).items() if isinstance(data.get("files"), dict) else ():
        p = PurePosixPath(str(rel))
        if not str(rel) or p.is_absolute() or ".." in p.parts or str(rel).startswith(".git"):
            continue
        body = str(body)
        if total + len(body) > CHARS_MAX or len(files) >= FILES_MAX:
            break
        files[str(p)], total = body, total + len(body)
    if not files:
        return None
    return str(data.get("name") or "")[:NAME_CHARS], files


# -- a case set ----------------------------------------------------------------------------------------------------

def set_prompt(goal: str, about: str, entries: list[dict], env: dict, what: str, count: int) -> str:
    where = "\n".join(f"- `{e['id']}`: {e['title']} ({e['word']}) — {e.get('takes', '')}" for e in entries)
    return f"""You write the cases of one case set of a Test bench. It gives each case's input to a building or a chain of
buildings of an AI agents' town ({about}), and the same input to a bare AI tool, then compares time, tokens and how
well each did. The mean over the set is what counts, so the cases are alike: the same kind of work, different each.

The environment they run in: {env['name']} — {env['about']}
What the cases of this set do there: {what.strip()}
The goal of the testing: {goal or 'see whether the buildings do better than the bare tool'}

Where an input may go in:
{where}

Write exactly {count} cases. Each input is what a person would really send in, complete, never a description of one.
`expect` is 1–4 words or short phrases a good result must say (a group of alternatives as a list), or [].

Answer with JSON only:
{{"cases": [{{"title": "…", "entry": "<an id from the list>", "text": "…", "expect": ["…"], "why": "…"}}]}}"""


def cassette_path(state_dir: Path, subject_id: str, set_id: str = "") -> Path:
    """Where a case set's MCP cassette is kept (realm/cassette.py); the scheme's own for single cases."""
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in subject_id)
    return state_dir / "cassettes" / f"{safe}-{set_id or 'single'}.jsonl"


def cassette_of(state_dir: Path, subject_id: str, set_id: str = "") -> dict:
    """What a set's cassette holds: how many answers, how many calls it could not answer."""
    path = cassette_path(state_dir, subject_id, set_id)
    count = lambda p: len(p.read_text(encoding="utf-8").splitlines()) if p.is_file() else 0
    return {"answers": count(path), "missed": count(path.with_suffix(".missed"))}


def summary_of(cases: list[dict], results: dict) -> dict:
    """The set's last run, as the mean of each metric over its cases that ran (a share against the bare tool)."""
    rows = [results[c["id"]] for c in cases if c["id"] in results and results[c["id"]].get("scheme")]

    def mean(key: str) -> float | None:
        vals = [r[key] for r in rows if r.get(key) is not None]
        return round(sum(vals) / len(vals), 3) if vals else None

    return {"ran": len(rows), "time": mean("time"), "tokens": mean("tokens"), "quality": mean("quality")}


def estimate(cases: list[dict], results: dict, n: int) -> dict:
    """What running `n` cases will spend, from the last run of these: the building's side each, and the bare tool's
    only where its answer is not kept. {} before any run."""
    rows = [results[c["id"]] for c in cases if c["id"] in results and results[c["id"]].get("scheme")]
    if not rows:
        return {}
    cost = sum(float(r["scheme"].get("cost") or 0) for r in rows) / len(rows)
    tokens = sum(int(r["scheme"].get("tokens") or 0) for r in rows) / len(rows)
    return {"cost": round(cost * n, 2), "tokens": int(tokens * n)}
