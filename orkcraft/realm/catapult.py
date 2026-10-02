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
"""
from __future__ import annotations

import datetime as dt
import json
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

import jsonschema

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


def parse(value: str):
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return value


class Load:
    def __init__(self, state_dir: Path) -> None:
        self.file = state_dir / "loaded.json"
        try:
            self.items: dict[str, object] = json.loads(self.file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.items = {}

    def save(self) -> None:
        self.file.parent.mkdir(parents=True, exist_ok=True)
        self.file.write_text(json.dumps(self.items, ensure_ascii=False, indent=1), encoding="utf-8")

    def put(self, source: str, value: str) -> None:
        self.items[source] = parse(value)
        self.save()

    def clear(self) -> None:
        self.items = {}
        self.save()

    def missing(self, wait_for: list[str]) -> list[str]:
        return [s for s in wait_for if s not in self.items]

    def ready(self, wait_for: list[str]) -> bool:
        return bool(self.items) and not self.missing(wait_for)

    def body(self, wait_for: list[str]):
        if len(wait_for) <= 1 and len(self.items) == 1:
            return next(iter(self.items.values()))
        keys = wait_for or list(self.items)
        return {k: self.items[k] for k in keys if k in self.items}


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
