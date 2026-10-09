"""🎯 The Catapult (T1107 stage 9): fan-in, schema check, send, dry run, confirm, never in the demo."""
from __future__ import annotations

import io
import json
import urllib.error
from pathlib import Path


from orkcraft.realm import catapult as cp

SCHEMA = {"type": "object", "required": ["notes", "version"],
          "properties": {"notes": {"type": "string"}, "version": {"type": "object", "required": ["tag"],
                                                                         "properties": {"tag": {"type": "string"}}}}}


class Answer(io.BytesIO):
    status = 201

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class Net:
    def __init__(self, status=201):
        self.requests, self.status = [], status

    def __call__(self, req, timeout=None):
        self.requests.append(req)
        if self.status >= 400:
            raise urllib.error.HTTPError(req.full_url, self.status, "nope", {}, io.BytesIO(b"bad token"))
        a = Answer(b'{"id": 7}')
        a.status = self.status
        return a


def test_load_check_and_fire(tmp_path: Path):
    load = cp.Load(tmp_path)
    load.put("notes", "release notes")
    assert not load.ready(["notes", "version"]) and load.missing(["notes", "version"]) == ["version"]
    load.put("version", '{"tag": "v0.2.0"}')
    assert load.ready(["notes", "version"])
    body = load.body(["notes", "version"])
    assert body == {"notes": "release notes", "version": {"tag": "v0.2.0"}}
    (tmp_path / "s.json").write_text(json.dumps(SCHEMA))
    assert cp.check(body, tmp_path / "s.json") == []
    assert cp.check({"notes": 1}, tmp_path / "s.json")
    net = Net()
    shot = cp.fire("https://api.example.com/releases", "POST", body, "t0k", net)
    req = net.requests[0]
    assert shot.ok and shot.status == 201 and req.get_header("Authorization") == "Bearer t0k"
    assert json.loads(req.data) == body and "t0k" not in shot.body
    bad = cp.fire("https://api.example.com/releases", "POST", body, "", Net(401))
    assert not bad.ok and bad.status == 401 and bad.answer == "bad token"
    assert "http or https" in cp.fire("file:///etc/passwd", "POST", body).error
    single = cp.Load(tmp_path / "one")
    single.put("pit", '{"a": 1}')
    assert single.body([]) == {"a": 1}
