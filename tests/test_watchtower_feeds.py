"""🗼 Watchtower feeds: comments and mentions in Slack, Jira, Confluence and Figma; Gmail by name."""
from __future__ import annotations

import io
import json
import urllib.error
from pathlib import Path

import pytest

from orkcraft import scroll as ts
from orkcraft.app import OrkcraftApp
from orkcraft.realm import audit, catalog, feeds, mailbox, masonry
from orkcraft.screens.typed.watchtower_view import WatchtowerView

SLACK = "slack: token=T_SLACK channels=C1,D2"
JIRA = "jira: site=acme.atlassian.net user=T_ATL_USER token=T_ATL_TOKEN jql=project = WEB AND type = Bug"
CONFLUENCE = "confluence: site=https://acme.atlassian.net/ user=T_ATL_USER token=T_ATL_TOKEN spaces=DOC"
FIGMA = "figma: token=T_FIGMA files=AbC123"


def adf(*parts):
    return {"type": "doc", "content": [{"type": "paragraph", "content": list(parts)}]}


API = {
    "slack.com/api/auth.test": {"ok": True, "user_id": "UME", "url": "https://acme.slack.com/"},
    "slack.com/api/users.info?user=UBOB": {"ok": True, "user": {"name": "bob", "profile": {"display_name": "Bob"}}},
    "slack.com/api/users.info": {"ok": False, "error": "missing_scope"},
    "slack.com/api/search.messages": {"ok": True, "messages": {"matches": [
        {"ts": "1790000100.000200", "user": "UANN", "username": "ann", "text": "<@UME> can you look?",
         "channel": {"id": "C9", "name": "design"}, "permalink": "https://acme.slack.com/x"}]}},
    "slack.com/api/conversations.history?channel=C1": {"ok": True, "messages": [
        {"ts": "1790000200.000100", "user": "UBOB", "text": "deploy at 5"},
        {"ts": "1790000300.000100", "user": "UME", "text": "mine"}]},
    "slack.com/api/conversations.history?channel=D2": {"ok": True, "messages": [
        {"ts": "1790000400.000100", "user": "UCAT", "text": "hi, a minute?"}]},
    "acme.atlassian.net/rest/api/3/myself": {"accountId": "acc-me"},
    "acme.atlassian.net/rest/api/3/search/jql": {"issues": [{"key": "WEB-7", "fields": {"summary": "Login fails",
        "comment": {"comments": [
            {"id": "100", "author": {"accountId": "acc-ann", "displayName": "Ann"}, "created": "2026-10-02T05:10:00.000+0000",
             "body": adf({"type": "text", "text": "repro attached"})},
            {"id": "101", "author": {"accountId": "acc-bob", "displayName": "Bob"}, "created": "2026-10-02T05:20:00.000+0000",
             "body": adf({"type": "mention", "attrs": {"id": "acc-me", "text": "@Me"}}, {"type": "text", "text": " please check"})},
            {"id": "102", "author": {"accountId": "acc-me"}, "created": "2026-10-02T05:30:00.000+0000",
             "body": adf({"type": "text", "text": "on it"})}]}}}]},
    "acme.atlassian.net/wiki/rest/api/search": {"results": [
        {"content": {"id": "55", "type": "page"}, "title": "Roadmap", "excerpt": "ask @@@hl@@@Me@@@endhl@@@",
         "url": "/spaces/DOC/pages/55", "lastModified": "2026-10-02T06:00:00.000Z"}]},
    "api.figma.com/v1/me": {"id": "fme", "handle": "Vadim"},
    "api.figma.com/v1/files/AbC123/comments": {"comments": [
        {"id": "c1", "user": {"id": "fme", "handle": "Vadim"}, "message": "is the button right?",
         "created_at": "2026-10-02T05:00:00Z"},
        {"id": "c2", "user": {"id": "fann", "handle": "ann"}, "message": "yes", "parent_id": "c1",
         "created_at": "2026-10-02T05:05:00Z"},
        {"id": "c3", "user": {"id": "fbob", "handle": "bob"}, "message": "new icon set", "created_at": "2026-10-02T05:06:00Z"},
        {"id": "c4", "user": {"id": "fbob", "handle": "bob"}, "message": "@vadim see this", "created_at": "2026-10-02T05:07:00Z"}]},
}


class Opener:
    """A fake urlopen: answers by URL, remembers what was asked and with which headers."""

    def __init__(self, api: dict) -> None:
        self.api, self.asked = api, []

    def __call__(self, req, timeout=None):
        self.asked.append((req.full_url, dict(req.header_items())))
        for part, answer in sorted(self.api.items(), key=lambda kv: -len(kv[0])):
            if part in req.full_url:
                if isinstance(answer, int):
                    raise urllib.error.HTTPError(req.full_url, answer, "no", {}, None)
                return io.BytesIO(json.dumps(answer).encode())
        raise urllib.error.URLError(f"no route to {req.full_url}")


@pytest.fixture
def env(monkeypatch):
    feeds.SLACK_NAMES.clear()
    for k, v in (("T_SLACK", "xoxp-1"), ("T_ATL_USER", "me@acme.io"), ("T_ATL_TOKEN", "atl"), ("T_FIGMA", "fig")):
        monkeypatch.setenv(k, v)


def test_a_feed_line_is_checked():
    feed, err = feeds.parse(JIRA)
    assert not err and feed.opts == {"site": "acme.atlassian.net", "user": "T_ATL_USER", "token": "T_ATL_TOKEN",
                                     "jql": "project = WEB AND type = Bug"}
    assert feeds.parse(CONFLUENCE)[0].opts["site"] == "acme.atlassian.net"
    assert feeds.check([SLACK, JIRA, CONFLUENCE, FIGMA]) == []
    assert "start with" in feeds.check(["teams: token=X"])[0]
    assert "set files=" in feeds.check(["figma: token=T_FIGMA"])[0]
    assert "environment variable" in feeds.check(["slack: token=xoxp-123"])[0]
    assert "takes" in feeds.check(["slack: token=T_SLACK colour=red"])[0]
    assert "host name" in feeds.check(["jira: site=acme user=A_B token=A_C"])[0]
    spec = {"id": "tower", "title": "Tower", "icon": "🗼", "type": "watchtower", "config": {"feeds": [SLACK, "figma:"]}}
    assert any("feeds: figma: set token=, files=" in e for e in catalog.validate(spec))


def test_slack_mentions_direct_messages_and_channels(env):
    opener = Opener(API)
    got = feeds.look(feeds.parse(SLACK)[0], opener)
    assert not got.error
    assert [(i.key, i.mention) for i in got.items] == [("C9:1790000100.000200", True), ("C1:1790000200.000100", False),
                                                       ("D2:1790000400.000100", True)]       # mine is skipped
    assert got.items[0].title == "@ ann in #design: @you can you look?"
    assert [i.title.split(":")[0] for i in got.items[1:]] == ["Bob in C1", "@ UCAT in D2"]   # no users:read: the id
    assert got.items[1].url == "https://acme.slack.com/archives/C1/p1790000200000100"
    assert all(h.get("Authorization") == "Bearer xoxp-1" for _, h in opener.asked)


def test_jira_comments_and_mentions(env):
    opener = Opener(API)
    got = feeds.look(feeds.parse(JIRA)[0], opener)
    assert [(i.key, i.mention) for i in got.items] == [("WEB-7:100", False), ("WEB-7:101", True)]
    assert got.items[1].title == "@ WEB-7 Bob: @Me please check"
    assert got.items[1].url == "https://acme.atlassian.net/browse/WEB-7?focusedCommentId=101"
    search = next(u for u, _ in opener.asked if "search/jql" in u)
    assert "project+%3D+WEB" in search and "updated+%3E%3D+-2d" in search
    assert opener.asked[0][1]["Authorization"].startswith("Basic ")


def test_confluence_and_figma(env):
    got = feeds.look(feeds.parse(CONFLUENCE)[0], Opener(API))
    assert [(i.key, i.mention, i.title) for i in got.items] == [("55", True, "@ page Roadmap: ask Me")]
    assert got.items[0].url == "https://acme.atlassian.net/wiki/spaces/DOC/pages/55"
    got = feeds.look(feeds.parse(FIGMA)[0], Opener(API))
    assert [(i.key, i.mention) for i in got.items] == [("AbC123:c2", True), ("AbC123:c3", False), ("AbC123:c4", True)]


def test_errors_and_the_first_look(env, monkeypatch):
    assert "refused" in feeds.look(feeds.parse(FIGMA)[0], Opener({"api.figma.com": 401})).error
    assert feeds.look(feeds.parse(SLACK)[0], Opener({"slack.com": {"ok": False, "error": "invalid_auth"}})).error \
        == "slack: auth.test: invalid_auth"
    monkeypatch.delenv("T_ATL_TOKEN")
    assert "T_ATL_TOKEN" in feeds.look(feeds.parse(JIRA)[0], Opener(API)).error
    items = feeds.Look([feeds.Item("a", "A"), feeds.Item("b", "B")])
    assert feeds.new_items(items, None) == ([], ["a", "b"])                 # a baseline: nothing sent
    fresh, seen = feeds.new_items(feeds.Look(items.items + [feeds.Item("c", "C")]), ["a", "b"])
    assert [i.key for i in fresh] == ["c"] and seen == ["a", "b", "c"]


def test_gmail_by_name_and_the_warder(tmp_path):
    with pytest.raises(ValueError, match="T_NOBODY"):
        mailbox.credentials({"host": "gmail", "user_env": "T_NOBODY", "password_env": "T_NOBODY2"})
    assert mailbox.PROVIDERS["gmail"] == "imap.gmail.com"
    leaked = {"tower": {"title": "Tower", "type": "watchtower", "config": {"feeds": ["slack: token=xoxp-1234567890abc"]}}}
    assert any("looks like a secret" in f.text for f in audit._security(tmp_path, leaked))


@pytest.mark.asyncio
async def test_the_watchtower_sends_comments_and_mentions(fake_repo: Path, env, monkeypatch):
    spec = {"id": "tower", "title": "Watchtower", "icon": "🗼", "orc": {"name": "Lookout"}, "type": "watchtower",
            "config": {"host": "gmail", "user_env": "T_ATL_USER", "password_env": "T_ATL_TOKEN",
                       "feeds": [SLACK, FIGMA]}}
    assert masonry.save_spec(fake_repo, spec) == []
    monkeypatch.setattr(mailbox, "look", lambda cfg, factory: mailbox.Look())   # no IMAP here
    api = {k: ({"ok": True, "messages": []} if "conversations" in k else v) for k, v in API.items()}
    api["api.figma.com/v1/files/AbC123/comments"] = {"comments": API["api.figma.com/v1/files/AbC123/comments"]["comments"][:2]}
    opener = Opener(api)
    monkeypatch.setattr(WatchtowerView, "feed_opener", staticmethod(opener))
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    for ev in ("watch.comment", "watch.mention"):
        ts.subscribe(app.scroll, "town_hall", "tower", ev)
    async with app.run_test(size=(200, 46)) as pilot:
        view = app.desktop.get_window("tower").query_one(WatchtowerView)
        for _ in range(60):
            await pilot.pause(0.05)
            if view.checked:
                break
        assert view.sources == ["mail", "slack", "figma"] and view.signals == []    # the first look: a baseline
        sent = []
        monkeypatch.setattr(app.roads, "emit", lambda payload, meta=None: sent.append(payload) or [])
        api.update({k: v for k, v in API.items()})                                    # new things since then
        opener.api = api
        view.refresh_data()
        for _ in range(60):
            await pilot.pause(0.05)
            if len(sent) >= 4:
                break
        assert [(p.mode, p.title.split(":")[0]) for p in sent] == [
            ("watch.comment", "slack · Bob in C1"), ("watch.mention", "slack · @ UCAT in D2"),
            ("watch.comment", "figma · bob in AbC123"), ("watch.mention", "figma · @ bob in AbC123")]
        assert "https://www.figma.com/design/AbC123?comment=c3" in sent[2].value
        view.refresh_data()
        for _ in range(20):
            await pilot.pause(0.05)
        assert len(sent) == 4                                                          # once each
        assert view.mini_status()[:2] == ["0 unread", "✉ 💬 🎨 · 4 new · @2"]
        assert view.hut_lines([10] * 4) == ["gmail    0", "slack    2", "figma    2", ""]
        view.read(view.signals[0])
        assert view.hut_lines([10] * 4)[2] == "figma    1" and len(view.unread()) == 3
        assert view.quick_action("watch.read_all") and view.unread() == []
        assert view.hut_lines([10] * 4)[1] == "slack    0"
