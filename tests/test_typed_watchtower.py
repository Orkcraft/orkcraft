"""🗼 Watchtower (T1107 stage 4): mail (IMAP), GitHub, a schedule and a localhost webhook."""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import json
import socket
import urllib.error
import urllib.request
from pathlib import Path
from types import SimpleNamespace

import pytest

from orkcraft import scroll as ts
from orkcraft.app import OrkcraftApp
from orkcraft.realm import mailbox, masonry, watch
from orkcraft.screens.typed.watchtower_view import WatchtowerView

SIZE = (200, 46)
CFG = {"host": "imap.example.com", "user_env": "T_MAIL_USER", "password_env": "T_MAIL_PASS"}


class FakeIMAP:
    """Just enough of imaplib.IMAP4_SSL; records whether anything was opened read-write."""

    boxes: dict[int, dict] = {}
    log: list = []

    def __init__(self, host, port):
        self.log.append(("connect", host, port))

    def login(self, user, password):
        if password != "secret":
            raise mailbox.imaplib.IMAP4.error("AUTHENTICATIONFAILED")
        return "OK", [b""]

    def select(self, folder, readonly=False):
        self.log.append(("select", folder, readonly))
        return "OK", [str(len(self.boxes)).encode()]

    def uid(self, command, *args):
        if command == "search":
            crit = args[-1]
            uids = [u for u, m in self.boxes.items() if crit == "ALL" or (crit == "UNSEEN" and not m["seen"])]
            return "OK", [" ".join(map(str, sorted(uids))).encode()]
        uid, what = int(args[0]), args[1]
        assert "PEEK" in what                                        # never marks as read
        m = self.boxes[uid]
        head = f"From: {m['from']}\r\nSubject: {m['subject']}\r\nDate: Fri, 02 Oct 2026 05:10:00 +0000\r\n\r\n".encode()
        if "HEADER.FIELDS" in what:
            return "OK", [(f"{uid} (UID {uid} FLAGS ()".encode(), head), b")"]
        if "TEXT" in what:
            return "OK", [(b"x", m["body"].encode()), b")"]
        return "OK", [(b"x", head[:-2] + b"Content-Type: text/plain\r\n\r\n" + m["body"].encode()), b")"]

    def logout(self):
        return "BYE", [b""]


def mail(uid, sender, subject, body, seen=False):
    FakeIMAP.boxes[uid] = {"from": sender, "subject": subject, "body": body, "seen": seen}


@pytest.fixture
def server(monkeypatch):
    FakeIMAP.boxes, FakeIMAP.log = {}, []
    monkeypatch.setenv("T_MAIL_USER", "me@example.com")
    monkeypatch.setenv("T_MAIL_PASS", "secret")
    return FakeIMAP


def test_look_and_read(server, monkeypatch):
    mail(1, "Ann <ann@x.org>", "Lunch?", "Shall we eat at noon?", seen=True)
    mail(2, "=?utf-8?b?0JjQstCw0L0=?= <ivan@x.ru>", "=?utf-8?q?=D0=9F=D1=80=D0=B8=D0=B2=D0=B5=D1=82?=",
         "Hello there\r\n\r\nsecond line")
    look = mailbox.look(CFG, server)
    assert not look.error and look.unread == 1
    assert [(m.uid, m.sender, m.subject, m.unread) for m in look.messages] == [
        (2, "Иван", "Привет", True), (1, "Ann", "Lunch?", False)]
    assert look.messages[0].snippet == "Hello there second line" and look.messages[1].snippet == ""
    assert ("select", "INBOX", True) in server.log                   # read-only
    assert mailbox.new_since(None, look) == [] and [m.uid for m in mailbox.new_since(1, look)] == [2]
    assert "Shall we eat at noon?" in mailbox.read(CFG, 1, server)
    monkeypatch.setenv("T_MAIL_PASS", "wrong")
    assert "AUTHENTICATIONFAILED" in mailbox.look(CFG, server).error
    monkeypatch.delenv("T_MAIL_USER")
    assert "T_MAIL_USER" in mailbox.look(CFG, server).error
    assert "host" in mailbox.look({}, server).error


@pytest.mark.asyncio
async def test_the_watchtower_tells_what_is_new_in_the_mail(fake_repo: Path, server, monkeypatch):
    mail(1, "Ann <ann@x.org>", "Lunch?", "Noon?")
    spec = {"id": "post", "title": "Post", "icon": "📨", "orc": {"name": "Raven"}, "type": "mail", "config": CFG}
    assert masonry.save_spec(fake_repo, spec) == []                   # an old mail spec: now a Watchtower
    monkeypatch.setattr(WatchtowerView, "imap_factory", staticmethod(server))
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    ts.subscribe(app.scroll, "town_hall", "post", "mail.received")
    async with app.run_test(size=SIZE) as pilot:
        view = app.desktop.get_window("post").query_one(WatchtowerView)
        for _ in range(40):
            await pilot.pause(0.05)
            if view.look is not None:
                break
        assert view.mini_status() == ["1 unread", "✉ · 1 signals", "✉ Ann: Lunch?"]   # listed, not sent
        sent = []
        monkeypatch.setattr(app.roads, "emit", lambda payload, meta=None: sent.append(payload) or [])
        mail(2, "Bob <bob@x.org>", "Deploy done", "All green.")
        view.apply_look(mailbox.look(CFG, server))
        assert [(p.mode, p.value) for p in sent] == [("mail.received", "From: Bob\nSubject: Deploy done\n\nAll green.")]
        view.apply_look(mailbox.look(CFG, server))
        assert len(sent) == 1                                          # once per message
        assert view.quick_action("mail.open_new")
        for _ in range(40):
            await pilot.pause(0.05)
            if "All green" in view.query_one("#watch-read").source:
                break
        assert "All green" in view.query_one("#watch-read").source


GH_EVENTS = [
    {"id": "102", "type": "PullRequestEvent", "actor": {"login": "ann"}, "created_at": "2026-10-02T05:10:00Z",
     "payload": {"action": "opened", "pull_request": {"number": 12, "title": "Login form", "html_url": "https://gh/12"}}},
    {"id": "101", "type": "PushEvent", "actor": {"login": "bob"},
     "payload": {"ref": "refs/heads/main", "commits": [{"message": "fix parser\n\nbody"}]}},
]


def gh(events):
    return lambda cmd, **kw: SimpleNamespace(returncode=0, stdout=json.dumps(events), stderr="")


def test_github_cron_and_the_webhook_signature():
    signals, newest, err = watch.github_events("me/app", "", gh(GH_EVENTS))
    assert (signals, newest, err) == ([], "102", "")                  # the first look: a baseline
    signals, newest, _ = watch.github_events("me/app", "101", gh(GH_EVENTS))
    assert [s.title for s in signals] == ["PR #12 opened: Login form"] and newest == "102"
    assert watch.describe(GH_EVENTS[1]) == ("push to main: 1 commit", "- fix parser")
    assert "owner/repo" in watch.github_events("not a repo", "", gh([]))[2]
    at = lambda h, m: dt.datetime(2026, 10, 2, h, m)
    assert watch.cron_due("every 15m", at(5, 14), at(5, 15)) and not watch.cron_due("every 15m", at(5, 15), at(5, 20))
    assert watch.cron_due("daily 05:00", at(4, 59), at(5, 0)) and watch.schedule_ok("weekly mon 09:00")
    assert not watch.schedule_ok("sometimes")
    body = b'{"x": 1}'
    good = "sha256=" + hmac.new(b"s3", body, hashlib.sha256).hexdigest()
    assert watch.signed("s3", body, {"X-Hub-Signature-256": good}) and watch.signed("s3", body, {"X-Orkcraft-Token": "s3"})
    assert not watch.signed("s3", body, {}) and watch.signed("", body, {})


@pytest.mark.asyncio
async def test_the_watchtower_hears_github_the_schedule_and_a_webhook(fake_repo: Path, monkeypatch):
    port = free_port()
    spec = {"id": "tower", "title": "Watchtower", "icon": "🗼", "orc": {"name": "Lookout"}, "type": "watchtower",
            "config": {"github": "me/app", "cron": "every 15m", "webhook_port": port, "webhook_secret_env": "T_HOOK"}}
    assert masonry.save_spec(fake_repo, spec) == []
    monkeypatch.setenv("T_HOOK", "s3cret")
    events = {"now": GH_EVENTS[1:]}
    monkeypatch.setattr(WatchtowerView, "gh_runner", staticmethod(lambda cmd, **kw: gh(events["now"])(cmd)))
    clock = {"now": dt.datetime(2026, 10, 2, 5, 14)}
    monkeypatch.setattr(WatchtowerView, "clock", staticmethod(lambda: clock["now"]))
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    for ev in ("watch.github", "watch.cron", "watch.webhook"):
        ts.subscribe(app.scroll, "town_hall", "tower", ev)
    async with app.run_test(size=SIZE) as pilot:
        view = app.desktop.get_window("tower").query_one(WatchtowerView)
        for _ in range(40):
            await pilot.pause(0.05)
            if view.checked:
                break
        sent = []
        monkeypatch.setattr(app.roads, "emit", lambda payload, meta=None: sent.append(payload) or [])
        events["now"] = GH_EVENTS                                      # a PR opened since the first look
        view.refresh_data()
        for _ in range(40):
            await pilot.pause(0.05)
            if sent:
                break
        clock["now"] = dt.datetime(2026, 10, 2, 5, 15)
        view.tick()
        req = urllib.request.Request(f"http://127.0.0.1:{port}/deploy", data=b'{"env": "prod"}', method="POST",
                                     headers={"X-Orkcraft-Token": "s3cret"})
        assert urllib.request.urlopen(req, timeout=5).status == 202
        bad = urllib.request.Request(f"http://127.0.0.1:{port}/deploy", data=b"x", method="POST")
        with pytest.raises(urllib.error.HTTPError):
            urllib.request.urlopen(bad, timeout=5)                      # no secret: 401
        for _ in range(40):
            await pilot.pause(0.05)
            if len(sent) >= 3:
                break
        assert [p.mode for p in sent] == ["watch.github", "watch.cron", "watch.webhook"]
        assert sent[0].title == "PR #12 opened: Login form" and '"env": "prod"' in sent[2].value
        assert view.mini_status()[0].startswith("🐙 ⏰ 🪝 · 3 signals")
        assert f"127.0.0.1:{port}" in str(view.query_one("#watch-head").render())
    with pytest.raises(OSError):
        urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2)  # the listener stops with the app


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]
