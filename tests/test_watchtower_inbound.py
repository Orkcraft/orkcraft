"""🗼 Webhooks pushed by Slack, Jira, Confluence and Figma: checked, answered, comments and mentions."""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.error
import urllib.request


from orkcraft.realm import catalog, feeds, inbound


def slack_headers(secret: str, body: bytes, ts: int | None = None) -> dict:
    ts = int(time.time()) if ts is None else ts
    sig = "v0=" + hmac.new(secret.encode(), f"v0:{ts}:".encode() + body, hashlib.sha256).hexdigest()
    return {"X-Slack-Request-Timestamp": str(ts), "X-Slack-Signature": sig}


def slack_event(text: str, user: str = "UANN", channel: str = "C1", ts: str = "1790000100.000200", **extra) -> dict:
    return {"type": "event_callback", "team_id": "T1", "authorizations": [{"user_id": "UME", "is_bot": False}],
            "event": {"type": "message", "user": user, "text": text, "channel": channel, "ts": ts, **extra}}


FIGMA_COMMENT = {"event_type": "FILE_COMMENT", "passcode": "fig-pass", "file_key": "AbC123", "file_name": "Checkout",
                 "comment_id": "c9", "timestamp": "2026-10-02T05:07:00Z", "triggered_by": {"id": "fbob", "handle": "bob"},
                 "comment": [{"text": "please look "}, {"mention": "fme"}], "mentions": [{"id": "fme", "handle": "vadim"}]}

JIRA_COMMENT = {"webhookEvent": "comment_created",
                "issue": {"key": "WEB-7", "self": "https://acme.atlassian.net/rest/api/2/issue/1",
                          "fields": {"summary": "Login fails"}},
                "comment": {"id": "101", "author": {"accountId": "acc-bob", "displayName": "Bob"},
                            "created": "2026-10-02T05:20:00.000+0000", "body": "[~accountid:acc-me] please check"}}


def test_each_service_proves_the_secret_its_own_way():
    body = json.dumps(slack_event("hi")).encode()
    assert inbound.verify("slack", "sign", body, slack_headers("sign", body))
    assert not inbound.verify("slack", "sign", body, slack_headers("other", body))
    assert not inbound.verify("slack", "sign", body, slack_headers("sign", body, int(time.time()) - 600))   # replayed
    fig = json.dumps(FIGMA_COMMENT).encode()
    assert inbound.verify("figma", "fig-pass", fig, {}) and not inbound.verify("figma", "nope", fig, {})
    jira = json.dumps(JIRA_COMMENT).encode()
    sig = "sha256=" + hmac.new(b"jira-s", jira, hashlib.sha256).hexdigest()
    assert inbound.verify("jira", "jira-s", jira, {"X-Hub-Signature": sig})
    assert not inbound.verify("jira", "jira-s", jira, {})
    assert inbound.verify("confluence", "tok", b"{}", {"X-Orkcraft-Token": "tok"})
    assert inbound.verify("slack", "", body, {})                                    # no secret: anyone
    assert inbound.answer("slack", b'{"type": "url_verification", "challenge": "abc"}') == b"abc"
    assert inbound.answer("slack", body) is None and inbound.answer("figma", fig) is None
    assert [inbound.service_of(p) for p in ("/slack", "/Figma/x?y=1", "/deploy", "")] == ["slack", "figma", "", ""]


def test_deliveries_become_comments_and_mentions():
    me = {"id": "UME"}
    [it] = inbound.parse("slack", json.dumps(slack_event("<@UME> can you look?")), me)
    assert (it.key, it.mention, it.title) == ("C1:1790000100.000200", True, "@ UANN in C1: @you can you look?")
    assert it.url == "https://app.slack.com/client/T1/C1"
    [it] = inbound.parse("slack", json.dumps(slack_event("deploy at 5")), {})          # me from the authorizations
    assert not it.mention
    assert inbound.parse("slack", json.dumps(slack_event("hi", channel="D2", channel_type="im")), me)[0].mention
    for skipped in (slack_event("mine", user="UME"), slack_event("bot", bot_id="B1"),
                    slack_event("edit", subtype="message_changed")):
        assert inbound.parse("slack", json.dumps(skipped), me) is inbound.IGNORED
    [it] = inbound.parse("jira", json.dumps(JIRA_COMMENT), {"id": "acc-me"})
    assert (it.key, it.mention, it.url) == ("WEB-7:101", True,
                                            "https://acme.atlassian.net/browse/WEB-7?focusedCommentId=101")
    assert not inbound.parse("jira", json.dumps(JIRA_COMMENT), {})[0].mention          # who you are: not known yet
    assert inbound.parse("jira", json.dumps({"webhookEvent": "jira:issue_updated"}), {}) is inbound.IGNORED
    [it] = inbound.parse("figma", json.dumps(FIGMA_COMMENT), {"id": "fme"})
    assert (it.key, it.mention, it.title) == ("AbC123:c9", True, "@ bob in Checkout: please look @vadim")
    assert inbound.parse("figma", json.dumps({"event_type": "PING"}), {}) is inbound.IGNORED
    [it] = inbound.parse("confluence", json.dumps({"id": "55", "title": "Roadmap", "text": "ask Me", "author": "Ann",
                                                   "url": "https://acme.atlassian.net/wiki/x", "mention": True}))
    assert (it.key, it.mention, it.title) == ("55", True, "@ Ann: Roadmap")
    assert inbound.parse("slack", "not json") is None and inbound.parse("confluence", "{}") is None


def test_a_line_only_to_listen():
    feed, err = feeds.parse("slack: secret=T_SLACK_SIGN")
    assert not err and not feed.poll
    assert feeds.parse("slack: token=T_SLACK secret=T_SLACK_SIGN")[0].poll
    assert "set user=, token=" in feeds.check(["jira: site=acme.atlassian.net"])[0]   # half a login
    assert "environment variable" in feeds.check(["figma: secret=hunter2"])[0]
    spec = {"id": "tower", "title": "Tower", "icon": "🗼", "type": "watchtower",
            "config": {"feeds": ["slack: secret=T_SLACK_SIGN"]}}
    assert any("set webhook_port" in e for e in catalog.validate(spec))


def post(port: int, path: str, body: bytes, headers: dict | None = None):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=body, method="POST", headers=headers or {})
    return urllib.request.urlopen(req, timeout=5)
