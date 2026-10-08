"""📍 Areas in work: the files and folders every open task of a repository changes, shared by every Agent
pool on it (design: docs/design/barracks-designs.md §3–4).

    narrow(paths)               a claim never holds the root or a whole top-level folder: it would overlap
                                every task
    Claims(repo_root)           `.orkcraft/claims.json`: load, put, release, drop the stale
    overlaps(claims, c)         the other claims whose paths meet `c`'s
    holds(claims, c)            the older one in `work` that `c` waits for, else None

A claim is `work` while its task is queued, planned or worked, `review` while its pull request (or its
branch) waits to be merged, and released when the PR is merged or closed, the task fails, or it ends with
no branch to merge. No model: paths are compared as `plans.overlap` compares a plan's parts.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from orkcraft.realm import plans

WORK, REVIEW = "work", "review"
DEFAULT_WAIT_MIN = 60          # a task waits for an older one on its area at most this long, then goes on flagged
DEFAULT_DAYS = 14              # a claim older than this is released as stale
MODES = ("wait", "flag", "off")
MAX_PATHS = 40


@dataclass
class Claim:
    key: str                    # `<building>:<task id>`
    building: str
    task: str
    title: str
    paths: list[str] = field(default_factory=list)
    guessed: bool = False       # the sort's guess, before the work showed what it changed
    branch: str = ""
    status: str = WORK          # work | review
    pr: str = ""
    brief: str = ""             # its design brief's path (realm/briefs.py), "" when it has none
    since: str = ""             # when it was first claimed (ISO): the older one never waits for the newer


def now() -> str:
    """When a claim is made: to the microsecond, so two tasks claimed in one second still have an order."""
    return datetime.now().isoformat(timespec="microseconds")


def norm(path: str) -> str:
    return str(path or "").strip().strip("`").removeprefix("./").strip("/")


def too_wide(path: str) -> bool:
    """The root, or one top-level folder (`src/`, `docs`): a claim on it would meet every task."""
    p = norm(path)
    return not p or p == "." or ("/" not in p and "." not in p)


def narrow(paths: list[str]) -> list[str]:
    out = [norm(p) for p in paths if not too_wide(p)]
    return list(dict.fromkeys(out))[:MAX_PATHS]


def key_of(building: str, task: str) -> str:
    return f"{building}:{task}"


def meets(a: list[str], b: list[str]) -> list[str]:
    """The paths of `a` that meet one of `b` (a folder holds what is under it)."""
    return [x for x in a if b and plans.overlap([x], b)]


def overlaps(claims: list[Claim], c: Claim) -> list[Claim]:
    return [o for o in claims if o.key != c.key and c.paths and o.paths and meets(c.paths, o.paths)]


def holds(claims: list[Claim], c: Claim) -> Claim | None:
    """The oldest other claim in `work` on `c`'s area that came before it: `c` waits for it."""
    older = [o for o in overlaps(claims, c) if o.status == WORK and (o.since or "") < (c.since or "~")]
    return min(older, key=lambda o: o.since) if older else None


def stale(c: Claim, days: int, now: datetime | None = None) -> bool:
    try:
        since = datetime.fromisoformat(c.since)
    except ValueError:
        return True
    now = now or datetime.now()
    if since.tzinfo is not None and now.tzinfo is None:
        now = now.astimezone()
    return now - since > timedelta(days=days)


class Claims:
    """The repository's areas in work, on disk. Every call reads the file anew: two pools write it."""

    def __init__(self, repo_root: Path) -> None:
        self.path = Path(repo_root) / ".orkcraft" / "claims.json"

    def load(self) -> list[Claim]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        out = []
        for item in data.get("claims", []) if isinstance(data, dict) else []:
            try:
                out.append(Claim(**item))
            except TypeError:
                continue
        return out

    def save(self, claims: list[Claim]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"claims": [asdict(c) for c in claims]}, indent=2, ensure_ascii=False),
                       encoding="utf-8")
        tmp.replace(self.path)

    def get(self, key: str) -> Claim | None:
        return next((c for c in self.load() if c.key == key), None)

    def put(self, c: Claim) -> Claim:
        """Write `c` (keeping when it first claimed); the claim as kept."""
        claims = self.load()
        old = next((x for x in claims if x.key == c.key), None)
        if old is not None:
            c.since = old.since or c.since
            c.brief = c.brief or old.brief
            claims.remove(old)
        claims.append(c)
        self.save(claims)
        return c

    def release(self, key: str) -> bool:
        claims = self.load()
        kept = [c for c in claims if c.key != key]
        if len(kept) == len(claims):
            return False
        self.save(kept)
        return True

    def drop_stale(self, days: int, now: datetime | None = None) -> list[Claim]:
        claims = self.load()
        gone = [c for c in claims if stale(c, days, now)]
        if gone:
            self.save([c for c in claims if c not in gone])
        return gone
