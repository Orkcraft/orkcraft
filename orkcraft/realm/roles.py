"""The agents' roles and the task types (spec 34 §3, decisions §46): a role is a name, a model, an instruction and
how many may work at once; each task type is given one role.

    roles(state_dir)                       # the roles, the built-in two first
    save(state_dir, "Docs scribe", "warrior", 2, "Write plainly.")      # its slug
    drop(state_dir, "docs-scribe")         # its task types go back to Grunt
    kinds(state_dir)                       # {"code": "grunt", "tests": "grunt", …}
    set_kind(state_dir, "docs", "docs-scribe")
    role_for(state_dir, "docs")            # the role a task of that type runs as

One small file per role, `<state_dir>/roles/<slug>.md` (front matter `name, model, max_parallel`; the body is the
instruction), so it is seen and undone by hand; the types' roles are `<state_dir>/roles/kinds.json`. **Taskmaster**
(the keeper) and **Grunt** (the default worker) exist by themselves: they can be edited, not deleted. A model is a
tier (`elder · warrior · laborer`) or a model of the Claude harness; "" (Grunt only) is the task's own tier.

No face, no model.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import threading
from pathlib import Path

from orkcraft.realm import ideas

TASKMASTER, GRUNT = "taskmaster", "grunt"
BUILTIN = (TASKMASTER, GRUNT)
TASK_KINDS = ("code", "tests", "docs", "text", "research")
KIND_LABELS = {"code": "Code", "tests": "Tests", "docs": "Docs", "text": "Text for people", "research": "Research"}
DEFAULT_KIND = "code"
MAX_PARALLEL = (1, 8)
NAME_CHARS, INSTRUCTION_CHARS = 40, 4000
TIERS = ("elder", "warrior", "laborer")
_DEFAULTS = {
    TASKMASTER: {"name": "Taskmaster", "model": "elder", "max_parallel": 1, "instruction": ""},
    GRUNT: {"name": "Grunt", "model": "", "max_parallel": 8, "instruction": ""},
}
LOCK = threading.RLock()


def folder(state_dir: Path) -> Path:
    return Path(state_dir) / "roles"


def models() -> list[dict]:
    """What a role may run on: {"id", "label"} — the task's own tier, the three tiers, then the Claude harness's
    models as it names them."""
    from orkcraft.realm import harnesses
    h = harnesses.get("claude")
    named = list(dict.fromkeys(h.models.values())) if h else []
    out = [{"id": "", "label": "The task's own tier"}]
    out += [{"id": t, "label": f"{t.capitalize()} tier" + (f" ({h.models[t]})" if h and t in h.models else "")}
            for t in TIERS]
    return out + [{"id": m, "label": m} for m in named]


def _model(value: object, allow_empty: bool) -> str:
    value = str(value or "").strip()
    if not value:
        if allow_empty:
            return ""
        raise ValueError("Pick a model from the list")
    if re.fullmatch(r"[\w.\[\]-]{1,60}", value):      # a tier, or a model the harness takes as written
        return value
    raise ValueError("Pick a model from the list")


def _clean_parallel(value: object) -> int:
    try:
        n = int(str(value).strip())
    except (TypeError, ValueError):
        raise ValueError("At most how many at once is a number from 1 to 8") from None
    if not MAX_PARALLEL[0] <= n <= MAX_PARALLEL[1]:
        raise ValueError("At most how many at once is a number from 1 to 8")
    return n


def _path(state_dir: Path, slug: str) -> Path:
    if not re.fullmatch(r"[a-z0-9-]+", slug or ""):
        raise ValueError(f"No agent {slug!r}")
    return folder(state_dir) / f"{slug}.md"


def _read(state_dir: Path, slug: str) -> dict | None:
    try:
        text = _path(state_dir, slug).read_text(encoding="utf-8").replace("\r\n", "\n")
    except (OSError, ValueError):
        return None
    page = ideas.parse(text)
    base = _DEFAULTS.get(slug, {"name": slug, "model": "", "max_parallel": 1, "instruction": ""})
    try:
        mp = int(page.get("max_parallel") or base["max_parallel"])
    except ValueError:
        mp = base["max_parallel"]
    body = text[m.end():] if (m := ideas._FENCE.match(text)) else text
    return {"slug": slug, "name": page.get("name") or base["name"], "model": page.get("model", base["model"]),
            "max_parallel": min(max(mp, MAX_PARALLEL[0]), MAX_PARALLEL[1]), "instruction": body.strip()[:INSTRUCTION_CHARS],
            "builtin": slug in BUILTIN}


def role(state_dir: Path, slug: str) -> dict | None:
    got = _read(state_dir, slug)
    if got is None and slug in _DEFAULTS:
        return {"slug": slug, **_DEFAULTS[slug], "builtin": True}
    return got


def roles(state_dir: Path) -> list[dict]:
    """The built-in two, then the person's, by name."""
    out = [role(state_dir, s) for s in BUILTIN]
    mine = []
    for path in sorted(folder(state_dir).glob("*.md")) if folder(state_dir).is_dir() else []:
        if path.stem not in BUILTIN and (r := _read(state_dir, path.stem)) is not None:
            mine.append(r)
    return out + sorted(mine, key=lambda r: (r["name"].lower(), r["slug"]))


def _write(state_dir: Path, r: dict) -> None:
    page = ideas.Page([("name", r["name"]), ("model", r["model"]), ("max_parallel", str(r["max_parallel"]))])
    text = page.text() + (f"\n{r['instruction'].strip()}\n" if r["instruction"].strip() else "")
    ideas._write(_path(state_dir, r["slug"]), text)


def save(state_dir: Path, name: str, model: object, max_parallel: object, instruction: object = "",
         slug: str | None = None) -> str:
    """A role made or edited. A new one keeps the name it is given; the built-in two keep their names too (editable)."""
    name = " ".join(str(name or "").split())[:NAME_CHARS]
    if not name:
        raise ValueError("An agent needs a name")
    with LOCK:
        if slug:
            old = role(state_dir, slug)
            if old is None:
                raise ValueError(f"No agent {slug!r}")
        else:
            taken = {r["slug"] for r in roles(state_dir)}
            base = ideas.slugify(name) if ideas.slugify(name) not in BUILTIN else f"{ideas.slugify(name)}-2"
            slug, n = base, 2
            while slug in taken or slug in BUILTIN:
                slug, n = f"{base}-{n}", n + 1
        if any(r["name"].lower() == name.lower() and r["slug"] != slug for r in roles(state_dir)):
            raise ValueError(f"There is an agent called {name} already")
        _write(state_dir, {"slug": slug, "name": name, "model": _model(model, slug == GRUNT),
                           "max_parallel": _clean_parallel(max_parallel),
                           "instruction": str(instruction or "").replace("\r\n", "\n").strip()[:INSTRUCTION_CHARS]})
    return slug


def drop(state_dir: Path, slug: str) -> list[str]:
    """A role the person made goes; the task types it had go back to Grunt (returned)."""
    if slug in BUILTIN:
        raise ValueError("Taskmaster and Grunt can be edited, not deleted")
    with LOCK:
        if _read(state_dir, slug) is None:
            raise ValueError(f"No agent {slug!r}")
        back = [k for k, r in kinds(state_dir).items() if r == slug]
        _path(state_dir, slug).unlink(missing_ok=True)
        if back:
            _save_kinds(state_dir, {**kinds(state_dir), **{k: GRUNT for k in back}})
    return back


def kinds(state_dir: Path) -> dict[str, str]:
    """{task type: role slug}, every type named; a type whose role is gone is Grunt's."""
    try:
        raw = json.loads((folder(state_dir) / "kinds.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raw = {}
    raw = raw if isinstance(raw, dict) else {}
    known = {r["slug"] for r in roles(state_dir)}
    return {k: (raw.get(k) if raw.get(k) in known and raw.get(k) != TASKMASTER else GRUNT) for k in TASK_KINDS}


def _save_kinds(state_dir: Path, data: dict) -> None:
    ideas._write(folder(state_dir) / "kinds.json", json.dumps(data, indent=1) + "\n")


def set_kind(state_dir: Path, kind: str, slug: str) -> None:
    if kind not in TASK_KINDS:
        raise ValueError(f"No task type {kind!r}")
    with LOCK:
        if role(state_dir, slug) is None:
            raise ValueError(f"No agent {slug!r}")
        if slug == TASKMASTER:
            raise ValueError("The Taskmaster plans, it does not do tasks: pick a Grunt or an agent of your own")
        _save_kinds(state_dir, {**kinds(state_dir), kind: slug})


def role_for(state_dir: Path, kind: str) -> dict:
    """The role a task of this type runs as (a task without a known type is code)."""
    kind = kind if kind in TASK_KINDS else DEFAULT_KIND
    return role(state_dir, kinds(state_dir)[kind]) or role(state_dir, GRUNT)


def spend_today(tasks: list[tuple[str, dict]]) -> dict[str, float]:
    """{role slug: today's cost} of (role, task) pairs whose task was started today."""
    today, out = dt.date.today().isoformat(), {}
    for slug, t in tasks:
        if str(t.get("started") or "").startswith(today) and isinstance(t.get("cost"), (int, float)):
            out[slug] = round(out.get(slug, 0.0) + float(t["cost"]), 4)
    return out
