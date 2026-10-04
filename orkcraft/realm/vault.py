"""📦 What the Loot Vault keeps: finished things, with when and what they cost.

A cart that reaches the Vault is stored: text lands as `loot/<building>/<stamp>-<slug>.md`, a file
is noted by its path. Each item is one line of `.orkcraft/loot/<id>/stored.jsonl`: when, from
which building, the title, the path, its size, and what the chain before it spent — the tokens
and cost of its trail (`pipes.Hop`), never a `$…` read out of the text.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from orkcraft.realm import pipes

KEEP = 300


@dataclass
class Stored:
    at: str
    source: str
    title: str
    path: str
    bytes: int = 0
    cost: float | None = None
    tokens: int | None = None
    trail: list[dict] = field(default_factory=list)
    ref: str = ""

    @property
    def hops(self) -> tuple[pipes.Hop, ...]:
        return pipes.trail_of(self.trail)


def _slug(text: str) -> str:
    return (re.sub(r"[^\w]+", "-", text.lower(), flags=re.U).strip("-") or "item")[:40]


def store(repo_root: Path, building_id: str, state_dir: Path, kind: str, value: str, title: str, source: str,
          now: dt.datetime | None = None, trail: tuple[pipes.Hop, ...] = (), ref: str = "") -> Stored:
    now = now or dt.datetime.now()
    tokens, cost = pipes.trail_totals(trail)
    if kind == "file":
        p = repo_root / value
        rel, size = value, (p.stat().st_size if p.is_file() else 0)
    else:
        folder = repo_root / "loot" / re.sub(r"[^a-z0-9_-]", "_", building_id.lower())
        folder.mkdir(parents=True, exist_ok=True)
        path, n = folder / f"{now:%Y%m%d-%H%M%S}-{_slug(title or value[:40])}.md", 2
        while path.exists():
            path, n = path.with_name(f"{path.stem}-{n}.md"), n + 1
        path.write_text(f"# {title or 'loot'}\n\n_from {source} · {now:%Y-%m-%d %H:%M}_\n\n{value}\n", encoding="utf-8")
        rel, size = str(path.relative_to(repo_root)), path.stat().st_size
    item = Stored(now.isoformat(timespec="seconds"), source, title or Path(rel).name, rel, size,
                  cost, tokens, [h.as_dict() for h in trail], ref)
    state_dir.mkdir(parents=True, exist_ok=True)
    with (state_dir / "stored.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(item), ensure_ascii=False) + "\n")
    return item


def stored(state_dir: Path, limit: int = KEEP) -> list[Stored]:
    try:
        lines = (state_dir / "stored.jsonl").read_text(encoding="utf-8").splitlines()[-limit:]
    except OSError:
        return []
    out = []
    for line in reversed(lines):
        try:
            out.append(Stored(**json.loads(line)))
        except (ValueError, TypeError):
            continue
    return out
