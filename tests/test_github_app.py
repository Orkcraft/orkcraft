"""GitHub for the Improve buildings (docs/design/improve-buildings.md §4): the Orkcraft Improve app's device flow, a
Test bench's code change sent as a pull request through the API (merged three ways when Orkcraft's main moved), and
the evidence that decides whether it may go. GitHub itself is a fake here: no request leaves the machine."""
from __future__ import annotations

import base64
import io
import json
import urllib.error

import pytest

from orkcraft.realm import github_app, lab_pr


class FakeGithub:
    """A tiny GitHub: answers by (method, path start); every request it saw is kept."""

    def __init__(self, routes: dict):
        self.routes, self.seen = routes, []

    def __call__(self, req, timeout=None):
        path = req.full_url.replace(github_app.API, "")
        body = json.loads(req.data) if req.data and req.headers.get("Content-type") == "application/json" else \
            (req.data.decode() if req.data else None)
        self.seen.append((req.get_method(), path, body))
        for (method, start), answer in self.routes.items():
            if req.get_method() == method and path.startswith(start):
                status, got = answer(body) if callable(answer) else answer
                if status >= 400:
                    raise urllib.error.HTTPError(req.full_url, status, "no", {}, io.BytesIO(json.dumps(got).encode()))
                return _Resp(status, got)
        raise AssertionError(f"no route for {req.get_method()} {path}")


class _Resp(io.BytesIO):
    def __init__(self, status, got):
        super().__init__(json.dumps(got).encode())
        self.status = status


def test_the_device_flow_waits_slows_down_and_keeps_the_token():
    answers = iter([(200, {"error": "authorization_pending"}), (200, {"error": "slow_down", "interval": 9}),
                    (200, {"access_token": "gho_x"})])
    gh = FakeGithub({("POST", "https://github.com/login/device/code"): (200, {
        "device_code": "dc", "user_code": "ABCD-1234", "verification_uri": "https://github.com/login/device",
        "interval": 5, "expires_in": 900}),
        ("POST", "https://github.com/login/oauth/access_token"): lambda _b: next(answers),
        ("GET", "/user"): (200, {"login": "orkfan"})})
    d = github_app.start(opener=gh)
    assert d.user_code == "ABCD-1234" and "client_id=" + github_app.CLIENT_ID in gh.seen[0][2]
    assert github_app.poll(d, opener=gh) == "" and github_app.poll(d, opener=gh) == "" and d.interval == 9
    assert github_app.poll(d, opener=gh) == "orkfan"
    assert github_app.account() == {"login": "orkfan", "token": "gho_x"}
    assert github_app.disconnect() and github_app.account() is None
    denied = FakeGithub({("POST", "https://github.com/login/oauth/access_token"): (200, {"error": "access_denied"})})
    with pytest.raises(github_app.GithubError, match="told no"):
        github_app.poll(d, opener=denied)


def test_a_change_is_merged_three_ways_or_refused():
    base = "a\nb\nc\n"
    assert github_app.merged(base, "a\nB\nc\n", base) == "a\nB\nc\n"
    assert github_app.merged(base, "a\nB\nc\n", "a\nb\nc\nd\n") == "a\nB\nc\nd\n"      # main moved elsewhere
    assert github_app.merged(base, "a\nB\nc\n", "a\nX\nc\n") is None                    # the same line


def _upstream(text: str) -> dict:
    return {"content": base64.b64encode(text.encode()).decode()}


def test_a_pull_request_is_made_with_the_api_on_the_persons_fork():
    acct = {"login": "orkfan", "token": "gho_x"}
    gh = FakeGithub({
        ("GET", "/user/installations"): (200, {"installations": [{"account": {"login": "OrkFan"}}]}),
        ("GET", "/repos/orkfan/orkcraft"): (200, {"full_name": "orkfan/orkcraft"}),
        ("GET", "/repos/orkcraft/orkcraft/git/ref/heads/main"): (200, {"object": {"sha": "head1"}}),
        ("GET", "/repos/orkcraft/orkcraft/git/commits/head1"): (200, {"tree": {"sha": "tree1"}}),
        ("GET", "/repos/orkcraft/orkcraft/contents/orkcraft/realm/x.py"): (200, _upstream("a\nb\nc\nd\n")),
        ("GET", "/repos/orkcraft/orkcraft/contents/orkcraft/realm/new.py"): (404, {"message": "Not Found"}),
        ("POST", "/repos/orkfan/orkcraft/git/blobs"): lambda b: (201, {"sha": f"blob-{len(b['content'])}"}),
        ("POST", "/repos/orkfan/orkcraft/git/trees"): (201, {"sha": "tree2"}),
        ("POST", "/repos/orkfan/orkcraft/git/commits"): (201, {"sha": "commit2"}),
        ("POST", "/repos/orkfan/orkcraft/git/refs"): (201, {}),
        ("POST", "/repos/orkcraft/orkcraft/pulls"): (201, {"number": 7, "html_url": "https://github.com/orkcraft/orkcraft/pull/7"}),
        ("POST", "/repos/orkcraft/orkcraft/issues/7/labels"): (403, {"message": "no"}),   # a label it may not put: no matter
    })
    changes = {"orkcraft/realm/x.py": ("a\nb\nc\n", "a\nB\nc\n"), "orkcraft/realm/new.py": ("", "print(1)\n")}
    url = github_app.send(changes, "Skip the plan for one-liners", "body", "improve/barracks-1", acct, opener=gh)
    assert url.endswith("/pull/7")
    blobs = [b for m, p, b in gh.seen if p.endswith("/git/blobs")]
    assert {b["content"] for b in blobs} == {"a\nB\nc\nd\n", "print(1)\n"}            # merged onto main as it is
    [pr] = [b for m, p, b in gh.seen if p == "/repos/orkcraft/orkcraft/pulls"]
    assert pr["head"] == "orkfan:improve/barracks-1" and pr["base"] == "main"
    not_installed = FakeGithub({("GET", "/user/installations"): (200, {"installations": []})})
    with pytest.raises(github_app.GithubError, match="Install the Orkcraft Improve app"):
        github_app.send(changes, "t", "b", "br", acct, opener=not_installed)
    with pytest.raises(github_app.GithubError, match="Connect GitHub"):
        github_app.send(changes, "t", "b", "br", None)


def test_the_evidence_decides_whether_it_may_go():
    cases = [{"id": "a", "set": "s1"}, {"id": "b", "set": "s1"}, {"id": "c"}]
    results = {"a": {"scheme": {"cost": 0.1}, "at": "2026-10-11T12:00:00", "tokens": -0.3, "time": 0.1, "quality": 0.0},
               "b": {"scheme": {"cost": 0.1}, "at": "2026-10-11T12:05:00", "tokens": -0.1, "time": -0.1, "quality": 1.0},
               "c": {"scheme": {"cost": 0.1}, "at": "2026-10-10T09:00:00", "tokens": 0.4}}                  # before the change
    since = "2026-10-11T11:00:00"
    assert lab_pr.ready(cases, results, since, "tokens") == (True, "")
    ok, why = lab_pr.ready(cases, results, since, "time")
    assert not ok and "1 of 2" in why
    assert not lab_pr.ready(cases, {}, since, "tokens")[0]
    rows = lab_pr.with_change(cases, results, since)
    body = lab_pr.body("Spend fewer tokens", "Agent pool", "Skip the plan", "tokens",
                       [{"id": "s1", "about": "Fix one failing test", "env_name": "Tiny shop"}], rows,
                       ["orkcraft/core/workers/barracks.py"], ["Agent pool: Shorter orders"])
    assert "**2 of 2**" in body and "| Fix one failing test | Tiny shop | 2 | +0% | -20% | +0.5 |" in body
    assert "Fix bug" not in body and "Shorter orders" in body


def test_a_picture_goes_as_bytes_and_is_refused_when_main_moved_it():
    """The UX bench sends pictures (docs/design/improve-buildings.md §6.5): bytes, base64 on the wire, no merge."""
    acct = {"login": "orkfan", "token": "gho_x"}
    old, new = b"\x89PNG old", b"\x89PNG new"

    def gh(upstream: bytes):
        return FakeGithub({
            ("GET", "/user/installations"): (200, {"installations": [{"account": {"login": "orkfan"}}]}),
            ("GET", "/repos/orkfan/orkcraft"): (200, {}),
            ("GET", "/repos/orkcraft/orkcraft/git/ref/heads/main"): (200, {"object": {"sha": "h"}}),
            ("GET", "/repos/orkcraft/orkcraft/git/commits/h"): (200, {"tree": {"sha": "t"}}),
            ("GET", "/repos/orkcraft/orkcraft/contents/design-system/sprites/x.png"):
                (200, {"content": base64.b64encode(upstream).decode()}),
            ("GET", "/repos/orkcraft/orkcraft/contents/design-system/sprites/new.png"): (404, {}),
            ("POST", "/repos/orkfan/orkcraft/git/blobs"): (201, {"sha": "b"}),
            ("POST", "/repos/orkfan/orkcraft/git/trees"): (201, {"sha": "t2"}),
            ("POST", "/repos/orkfan/orkcraft/git/commits"): (201, {"sha": "c2"}),
            ("POST", "/repos/orkfan/orkcraft/git/refs"): (201, {}),
            ("POST", "/repos/orkcraft/orkcraft/pulls"): (201, {"number": 8, "html_url": "https://x/pull/8"}),
            ("POST", "/repos/orkcraft/orkcraft/issues/8/labels"): (200, {}),
        })
    changes = {"design-system/sprites/x.png": (old, new), "design-system/sprites/new.png": (b"", new)}
    fine = gh(old)
    assert github_app.send(changes, "UX bench: 2 pictures", "b", "improve/ux-1", acct, opener=fine).endswith("/pull/8")
    blobs = [b for m, p, b in fine.seen if p.endswith("/git/blobs")]
    assert len(blobs) == 2 and all(b["encoding"] == "base64" and base64.b64decode(b["content"]) == new for b in blobs)
    with pytest.raises(github_app.GithubError, match="changed in Orkcraft's main"):
        github_app.send(changes, "t", "b", "br", acct, opener=gh(b"\x89PNG theirs"))
