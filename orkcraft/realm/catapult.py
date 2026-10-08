"""🎯 The Catapult: the strict way out.

    load     each cart is loaded under its source building (the latest one wins); a JSON value is
             kept as JSON, anything else as text
    ready    when every building of `wait_for` has loaded (fan-in) — with no `wait_for`, every cart
    body     one source: its value; several: {source: value}
    check    against the JSON Schema file `schema` (in the project), when there is one
    fire     `method` (POST) to `url` (http or https only) with the body as JSON; the token from
             the environment variable `token_env` goes as `Authorization: Bearer …` and is never
             written anywhere

Shots are kept in `.orkcraft/catapult/<id>/shots.jsonl` (the answer's status and first lines).
Where a site has no API, the browser mode fills its web form instead (realm/catapult_web/).
"""
from __future__ import annotations

import datetime as dt
import json
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

import jsonschema
from orkcraft.realm.jobs import now_iso

SEND_TIMEOUT_S = 20
ANSWER_KEEP = 2000


@dataclass
class Shot:
    at: str
    ok: bool
    status: int
    url: str
    body: str               # what was sent (the token never is)
    answer: str = ""
    error: str = ""
    dry: bool = False
    track: str = ""         # mode mcp: direct, local or carrier (realm/catapult_mcp)


def parse(value: str):
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return value


class Load:
    """What is loaded, in groups: one group is one shot's worth of carts. With `key` (a body path,
    "version.tag") carts that name the same value share a group, so two releases never mix; a cart
    without it joins the newest group still missing its source. Each source keeps its latest cart
    in a group; carts older than `ttl` minutes are dropped."""

    def __init__(self, state_dir: Path) -> None:
        self.file = state_dir / "loaded.json"
        try:
            raw = json.loads(self.file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raw = {}
        if isinstance(raw, dict) and "groups" in raw:
            self.groups: dict[str, dict[str, dict]] = raw["groups"]
            self.seq = int(raw.get("seq", 0))
        else:                                     # the old flat {source: value}
            now = now_iso()
            self.groups = {"#0": {k: {"v": v, "at": now} for k, v in raw.items()}} if raw else {}
            self.seq = 1

    @property
    def items(self) -> dict[str, object]:
        """The newest group's carts, {source: value} (what the screen shows)."""
        g = self._newest()
        return {k: e["v"] for k, e in self.groups.get(g, {}).items()} if g else {}

    def _newest(self) -> str | None:
        if not self.groups:
            return None
        return max(self.groups, key=lambda g: max((e["at"] for e in self.groups[g].values()), default=""))

    def save(self) -> None:
        self.file.parent.mkdir(parents=True, exist_ok=True)
        self.file.write_text(json.dumps({"groups": self.groups, "seq": self.seq}, ensure_ascii=False, indent=1),
                             encoding="utf-8")

    def put(self, source: str, value: str, key: str = "", now: str | None = None) -> str:
        """Load a cart; returns its group."""
        v, now = parse(value), now or now_iso()
        named = _pick(v, key) if key else None
        if named is not None and not isinstance(named, (dict, list)):
            group = f"={named}"
        else:
            open_groups = sorted((g for g in self.groups if source not in self.groups[g]),
                                 key=lambda g: max((e["at"] for e in self.groups[g].values()), default=""))
            group = open_groups[-1] if open_groups else f"#{self.seq}"
            if not open_groups:
                self.seq += 1
        self.groups.setdefault(group, {})[source] = {"v": v, "at": now}
        self.save()
        return group

    def expire(self, ttl_min: int, now: dt.datetime | None = None) -> list[str]:
        """Drop carts older than `ttl_min` minutes (0: never); returns "source (group)" of each."""
        if not ttl_min:
            return []
        edge = ((now or dt.datetime.now()) - dt.timedelta(minutes=ttl_min)).isoformat(timespec="seconds")
        dropped = []
        for g in list(self.groups):
            for src in [s for s, e in self.groups[g].items() if e["at"] < edge]:
                del self.groups[g][src]
                dropped.append(f"{src} ({g.lstrip('=#')})")
            if not self.groups[g]:
                del self.groups[g]
        if dropped:
            self.save()
        return dropped

    def clear(self) -> None:
        self.groups = {}
        self.save()

    def missing(self, wait_for: list[str]) -> list[str]:
        """What the most complete group still waits for."""
        if not self.groups:
            return list(wait_for)
        best = min(self.groups.values(), key=lambda g: len([s for s in wait_for if s not in g]))
        return [s for s in wait_for if s not in best]

    def _ready(self, wait_for: list[str]) -> list[str]:
        ok = [g for g, items in self.groups.items() if items and all(s in items for s in wait_for)]
        return sorted(ok, key=lambda g: min(e["at"] for e in self.groups[g].values()))

    def ready(self, wait_for: list[str]) -> bool:
        return bool(self._ready(wait_for))

    @staticmethod
    def _body_of(items: dict[str, object], wait_for: list[str]):
        if len(wait_for) <= 1 and len(items) == 1:
            return next(iter(items.values()))
        keys = wait_for or list(items)
        return {k: items[k] for k in keys if k in items}

    def body(self, wait_for: list[str]):
        """The body of the oldest ready group, else of the newest (a look, nothing is taken)."""
        ready = self._ready(wait_for)
        g = ready[0] if ready else self._newest()
        return self._body_of({k: e["v"] for k, e in self.groups.get(g, {}).items()}, wait_for) if g else None

    def take(self, wait_for: list[str], force: bool = False):
        """Take the oldest ready group out (with `force`, the newest group, ready or not): its body,
        or None. Only that group's carts leave; carts loaded meanwhile stay."""
        ready = self._ready(wait_for)
        g = ready[0] if ready else (self._newest() if force else None)
        if g is None:
            return None
        items = {k: e["v"] for k, e in self.groups.pop(g).items()}
        self.save()
        return self._body_of(items, wait_for)


def _pick(body, path: str):
    cur = body
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        elif isinstance(cur, list) and part.isdigit() and int(part) < len(cur):
            cur = cur[int(part)]
        else:
            return None
    return cur


class Queue:
    """Shots waiting their turn: one fires at a time, the rest wait here (kept across restarts)."""

    def __init__(self, state_dir: Path) -> None:
        self.file = state_dir / "queue.json"
        try:
            self.items: list[dict] = json.loads(self.file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.items = []

    def save(self) -> None:
        self.file.parent.mkdir(parents=True, exist_ok=True)
        self.file.write_text(json.dumps(self.items, ensure_ascii=False, indent=1), encoding="utf-8")

    def push(self, body, start: int = 0, front: bool = False) -> None:
        item = {"body": body, "start": start, "at": now_iso()}
        self.items.insert(0, item) if front else self.items.append(item)
        self.save()

    def pop(self) -> dict | None:
        if not self.items:
            return None
        item = self.items.pop(0)
        self.save()
        return item

    def __len__(self) -> int:
        return len(self.items)


def check(body, schema_path: Path | None) -> list[str]:
    if schema_path is None:
        return []
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return [f"schema {schema_path.name}: {e}"]
    v = jsonschema.Draft202012Validator(schema)
    return [f"{'/'.join(str(p) for p in e.absolute_path) or '(root)'}: {e.message}" for e in v.iter_errors(body)][:10]


def request(url: str, method: str, body, token: str = "") -> urllib.request.Request:
    if not url.startswith(("http://", "https://")):
        raise ValueError(f"url {url!r}: http or https only")
    data = json.dumps(body, ensure_ascii=False).encode()
    headers = {"Content-Type": "application/json", "User-Agent": "orkcraft-catapult"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return urllib.request.Request(url, data=data, method=method or "POST", headers=headers)


def fire(url: str, method: str, body, token: str = "", opener=urllib.request.urlopen) -> Shot:
    at, sent = dt.datetime.now().isoformat(timespec="seconds"), json.dumps(body, ensure_ascii=False)[:ANSWER_KEEP]
    try:
        req = request(url, method, body, token)
        with opener(req, timeout=SEND_TIMEOUT_S) as resp:
            status = getattr(resp, "status", 200)
            answer = resp.read(ANSWER_KEEP).decode("utf-8", errors="replace")
        return Shot(at, 200 <= status < 300, status, url, sent, answer)
    except urllib.error.HTTPError as e:
        return Shot(at, False, e.code, url, sent, e.read(ANSWER_KEEP).decode("utf-8", errors="replace"), f"HTTP {e.code}")
    except Exception as e:  # the network and bad urls, of every kind
        return Shot(at, False, 0, url, sent, error=str(e)[:300])


def dry_run(url: str, method: str, body) -> Shot:
    sent = json.dumps(body, ensure_ascii=False, indent=2)[:ANSWER_KEEP]
    return Shot(dt.datetime.now().isoformat(timespec="seconds"), True, 0, url, sent,
                f"{method or 'POST'} {url}\nContent-Type: application/json\n\n{sent}", dry=True)


def dry_run_form(url: str, plan_text: str, body) -> Shot:
    """Browser mode's dry run: which field would get what — no browser opens."""
    sent = json.dumps(body, ensure_ascii=False, indent=2)[:ANSWER_KEEP]
    return Shot(dt.datetime.now().isoformat(timespec="seconds"), True, 0, url, sent,
                f"🌐 {url}\n\n{plan_text}", dry=True)


def form_shot(url: str, body, res, pressed_wanted: bool) -> Shot:
    """A run of fill.py (catapult_web.Result) as a shot: 0 = filled (and pressed, if asked)."""
    at, sent = dt.datetime.now().isoformat(timespec="seconds"), json.dumps(body, ensure_ascii=False)[:ANSWER_KEEP]
    s = res.summary or {}
    lines = [f"filled: {', '.join(s.get('filled') or []) or 'nothing'}"]
    if s.get("missed"):
        lines.append("missed: " + "; ".join(s["missed"]))
    if s.get("broken"):
        lines.append("broken: " + "; ".join(s["broken"]))
    lines.append(("pressed — " if s.get("pressed") else "handed over to you — ") + str(s.get("url") or url))
    if s.get("title"):
        lines.append(f"page: {s['title']}")
    error = "" if res.ok else (res.err or ("broken: " + s["broken"][0][:200] if s.get("broken") else
                                           s["missed"][0][:200] if s.get("missed") and not s.get("filled") else
                                           "some fields were not filled" if s.get("missed") else f"exit {res.code}"))
    if res.ok and pressed_wanted and not s.get("pressed"):
        error = "not pressed"
    return Shot(at, not error, res.code, str(s.get("url") or url), sent, "\n".join(lines)[:ANSWER_KEEP], error)


def log(state_dir: Path, shot: Shot) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    with (state_dir / "shots.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(shot), ensure_ascii=False) + "\n")


def shots(state_dir: Path, limit: int = 50) -> list[Shot]:
    try:
        lines = (state_dir / "shots.jsonl").read_text(encoding="utf-8").splitlines()[-limit:]
    except OSError:
        return []
    out = []
    for line in reversed(lines):
        try:
            out.append(Shot(**json.loads(line)))
        except (ValueError, TypeError):
            continue
    return out
