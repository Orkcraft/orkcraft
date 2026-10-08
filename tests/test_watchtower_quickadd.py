"""🗼 Add a source in three steps: Logins, a pasted link, the login checked, the picks, the first look, Add."""
from __future__ import annotations

import io
import json
import os
import stat
import time
import urllib.error
from pathlib import Path
from types import SimpleNamespace

import pytest

from orkcraft.core.workers.watchtower import WatchtowerWorker
from orkcraft.gui.host import CommandError, Host
from orkcraft.realm import audit, checkpoint, feeds, logins, mailbox, masonry, quickadd
from orkcraft.realm.sources_link import Link, recognise


class Opener:
    """A fake urlopen: answers by URL part, remembers what was asked."""

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


ATL = {
    "acme.atlassian.net/rest/api/3/myself": {"accountId": "acc-me", "displayName": "Ann"},
    "acme.atlassian.net/rest/api/3/project/search": {"values": [{"key": "WEB", "name": "Website"},
                                                                {"key": "SUP", "name": "Support"}]},
    "acme.atlassian.net/rest/api/3/search/jql": {"issues": [{"key": "WEB-7", "fields": {"summary": "Login fails",
        "comment": {"comments": [{"id": "100", "author": {"accountId": "acc-bob", "displayName": "Bob"},
                                  "created": "2026-10-02T05:10:00.000+0000", "body": "repro attached"}]}}}]},
}


def _until(check, timeout: float = 5.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if check():
            return True
        time.sleep(0.02)
    return check()


# -- Logins ------------------------------------------------------------------------------------------------

def test_a_login_is_kept_out_of_the_project_and_named_by_reference(monkeypatch):
    ref = logins.save("slack-acme", "xoxp-secret", "slack", "acme.slack.com")
    assert ref == "keychain:slack-acme" and logins.resolve(ref) == "xoxp-secret"
    assert stat.S_IMODE(os.stat(logins.path()).st_mode) == 0o600
    assert logins.listed("slack") == [{"name": "slack-acme", "service": "slack", "account": "acme.slack.com",
                                       "where": "file", "saved": logins.listed()[0]["saved"]}]
    monkeypatch.setenv("T_OLD", "from-env")
    assert logins.resolve("T_OLD") == "from-env" and logins.resolve("keychain:gone") == ""
    assert logins.is_name("T_OLD") and logins.is_name(ref) and not logins.is_name("xoxp-secret")
    with pytest.raises(ValueError):
        logins.save("Bad Name", "x")
    assert logins.remove("slack-acme") and logins.resolve(ref) == "" and not logins.remove("slack-acme")


def test_feeds_and_the_mailbox_take_a_login_and_the_warder_does_not_flag_it():
    logins.save("figma-ann", "figd_1", "figma", "ann")
    feed, err = feeds.parse("figma: token=keychain:figma-ann files=AbC")
    assert not err and feed.env("token") == "figd_1"
    assert "a login" in feeds.parse("figma: token=figd_raw files=AbC")[1]
    gone, _ = feeds.parse("figma: token=keychain:figma-bob files=AbC")
    assert "log in again" in feeds.look(gone, Opener({})).error
    logins.save("gmail-ann", "abcdabcdabcdabcd", "gmail", "ann@gmail.com")
    host, _, user, password, folder = mailbox.credentials({"host": "gmail", "user": "ann@gmail.com",
                                                           "password_env": "keychain:gmail-ann"})
    assert (host, user, password, folder) == ("imap.gmail.com", "ann@gmail.com", "abcdabcdabcdabcd", "INBOX")
    spec = {"id": "t", "title": "T", "type": "watchtower",
            "config": {"host": "gmail", "password_env": "keychain:gmail-ann", "feeds": ["slack: token=keychain:slack-x"]}}
    assert not [f for f in audit._security(Path("."), {"t": spec}) if "secret" in f.text]
    raw = dict(spec, config={"password_env": "hunter2-not-a-name"})
    assert [f for f in audit._security(Path("."), {"t": raw}) if "secret" in f.text]


# -- a pasted link -------------------------------------------------------------------------------------------

@pytest.mark.parametrize("text, link", [
    ("https://github.com/acme/app/pull/3", Link("github", "github.com", "acme/app", "the repo acme/app")),
    ("acme.slack.com/archives/C07SUPPORT", Link("slack", "acme.slack.com", "C07SUPPORT", "the channel C07SUPPORT")),
    ("https://acme.atlassian.net/browse/WEB-12", Link("jira", "acme.atlassian.net", "WEB", "the project WEB")),
    ("https://acme.atlassian.net/jira/software/projects/SUP/boards/1", Link("jira", "acme.atlassian.net", "SUP", "the project SUP")),
    ("https://acme.atlassian.net/wiki/spaces/DOC/pages/5", Link("confluence", "acme.atlassian.net", "DOC", "the space DOC")),
    ("https://www.figma.com/design/AbC123/Checkout?node-id=1-2", Link("figma", "www.figma.com", "AbC123", "the file AbC123")),
    ("https://www.figma.com/files/team/987/Acme", Link("figma", "www.figma.com", "team:987", "the team 987")),
    ("https://gitlab.com/acme/web/-/issues/4", Link("gitlab", "gitlab.com", "acme/web", "the project acme/web")),
    ("https://discord.com/channels/111/222", Link("discord", "111", "222", "the channel 222")),
    ("ann@gmail.com", Link("gmail", "ann@gmail.com", "", "the mailbox ann@gmail.com")),
])
def test_a_link_says_the_service_and_what_to_tick(text, link):
    assert recognise(text) == link


def test_a_link_it_does_not_know_is_none():
    assert recognise("https://example.com/x") is None and recognise("") is None


# -- the steps, without a face -------------------------------------------------------------------------------

def test_jira_logs_in_lists_projects_plans_a_line_and_looks():
    opener = Opener(ATL)
    login = quickadd.verify("jira", {"site": "acme", "email": "ann@acme.io", "token": "t" * 24}, opener)
    assert login.site == "acme.atlassian.net" and login.who == "Ann · acme.atlassian.net"
    assert login.refs == {"user": "keychain:atlassian-acme.atlassian.net-user", "token": "keychain:atlassian-acme.atlassian.net"}
    assert logins.resolve(login.refs["token"]) == "t" * 24
    assert [o.id for o in quickadd.options(login, opener)] == ["WEB", "SUP"]
    plan = quickadd.plan(login, ["WEB"], about_me=True)
    assert plan.feed.startswith("jira: site=acme.atlassian.net user=keychain:") and "OR project in (WEB)" in plan.feed
    assert feeds.check([plan.feed]) == []
    assert quickadd.first_look(login, plan, opener) == (1, "")
    assert quickadd.kept("confluence")[0].site == "acme.atlassian.net"          # one Atlassian login serves both
    with pytest.raises(quickadd.Refused, match="refused"):
        quickadd.verify("jira", {"site": "acme", "email": "a@b.c", "token": "x" * 24},
                        Opener({"acme.atlassian.net/rest/api/3/myself": 401}))


def test_a_feed_line_replaces_the_one_that_asks_the_same_way():
    a = "slack: token=keychain:slack-acme channels=C1"
    b = "slack: token=keychain:slack-acme channels=C1,C2"
    other = "slack: token=keychain:slack-home"
    assert quickadd.with_feed([a, other], b) == [other, b]
    assert quickadd.with_feed([a], a) == [a]


def test_gmail_checks_the_app_password_over_imap():
    seen = []

    class Server:
        def __init__(self, host, port):
            seen.append(host)

        def login(self, user, password):
            if password != "abcdabcdabcdabcd":
                import imaplib
                raise imaplib.IMAP4.error("bad")

        def logout(self):
            pass

    login = quickadd.verify("gmail", {"email": "ann@gmail.com", "password": "abcd abcd abcd abcd"}, imap_factory=Server)
    assert seen == ["imap.gmail.com"] and logins.resolve(login.refs["password"]) == "abcdabcdabcdabcd"
    plan = quickadd.plan(login, [])
    assert plan.changes == {"host": "gmail", "user": "ann@gmail.com", "user_env": None,
                            "password_env": "keychain:gmail-ann@gmail.com", "folder": "INBOX"}
    with pytest.raises(quickadd.Refused, match="app password"):
        quickadd.verify("gmail", {"email": "ann@gmail.com", "password": "wrong"}, imap_factory=Server)


# -- the steps in the GUI --------------------------------------------------------------------------------------

def _gh(cmd, **kw):
    if cmd[:3] == ["gh", "api", "user"]:
        return SimpleNamespace(returncode=0, stdout="ann\n", stderr="")
    if cmd[:2] == ["gh", "api"] and cmd[2].startswith("user/repos"):
        return SimpleNamespace(returncode=0, stdout=json.dumps([{"full_name": "acme/web", "pushed_at": "2026-10-01"}]),
                               stderr="")
    if cmd[:2] == ["gh", "api"] and cmd[2].startswith("notifications"):
        return SimpleNamespace(returncode=0, stdout=json.dumps([{"id": "1", "reason": "review_requested",
            "updated_at": "2026-10-02T05:00:00Z", "subject": {"title": "Fix login", "type": "PullRequest",
            "url": "https://api.github.com/repos/acme/web/pulls/3"}, "repository": {"full_name": "acme/web"}}]), stderr="")
    if cmd[:2] == ["gh", "api"] and cmd[2].startswith("repos/"):
        return SimpleNamespace(returncode=0, stdout=json.dumps([{"id": "9", "type": "WatchEvent", "actor": {"login": "bo"}}]),
                               stderr="")
    if cmd[:2] == ["git", "-C"]:
        return SimpleNamespace(returncode=0, stdout="git@github.com:acme/orkcraft.git\n", stderr="")
    return SimpleNamespace(returncode=0, stdout="[]", stderr="")


@pytest.fixture
def host(fake_repo, monkeypatch):
    monkeypatch.setattr(WatchtowerWorker, "gh_runner", staticmethod(_gh))
    monkeypatch.setattr(WatchtowerWorker, "feed_opener", Opener(ATL))
    spec = {"id": "tower", "title": "Tower", "icon": "🗼", "orc": {"name": "Lookout"}, "type": "watchtower", "config": {}}
    assert masonry.save_spec(fake_repo, spec) == []
    checkpoint.ensure(fake_repo)
    return Host(fake_repo, auto_commit=False)


def test_a_tower_with_no_source_adds_jira_from_a_link_in_three_steps(host):
    act = lambda name, **args: host.command("act", {"id": "tower", "act": name, "args": args})
    w = host.town.worker("tower")
    adding = lambda: host.detail("tower")["data"]["adding"]
    assert adding() is None and host.detail("tower")["data"]["listed"] == []
    act("add_open")
    assert _until(lambda: w.adding.gh == "ann")
    marks = {s["id"]: s["mark"] for s in adding()["services"]}
    assert marks["github"] == "✓ gh · ann" and marks["jira"] == "a token"
    assert act("add_link", link="https://acme.atlassian.net/browse/WEB-3") == "jira"
    a = adding()
    assert a["step"] == "login" and a["picks"] == ["WEB"] and [f["key"] for f in a["fields"]] == ["site", "email", "token"]
    act("add_login", values={"email": "ann@acme.io", "token": "t" * 24})      # the site comes from the link
    assert _until(lambda: adding()["step"] == "what" and not adding()["busy"])
    a = adding()
    assert a["who"] == "Ann · acme.atlassian.net" and [o["id"] for o in a["options"]] == ["WEB", "SUP"] and a["picks"] == ["WEB"]
    act("add_what", picks=["WEB"], about_me=True)
    assert _until(lambda: adding()["step"] == "check" and not adding()["busy"])
    a = adding()
    assert a["found"] == 1 and not a["error"] and "WEB" in a["says"]
    assert act("add_save") == "jira" and adding() is None
    line = w.config["feeds"][0]
    assert line.startswith("jira: site=acme.atlassian.net user=keychain:") and "t" * 24 not in json.dumps(w.config)
    listed = host.detail("tower")["data"]["listed"]
    assert [(x["kind"], x["label"]) for x in listed] == [("jira", "Jira")] and "a login" in listed[0]["line"]
    assert act("remove", source=listed[0]["id"]) and "feeds" not in w.config


def test_github_needs_no_paste_when_gh_is_logged_in(host):
    act = lambda name, **args: host.command("act", {"id": "tower", "act": name, "args": args})
    w = host.town.worker("tower")
    act("add_open")
    assert _until(lambda: w.adding.gh == "ann")
    act("add_start", service="github")
    assert _until(lambda: w.adding.step == "what" and not w.adding.busy)
    assert [(o.id, o.picked) for o in w.adding.options] == [("acme/orkcraft", True), ("acme/web", False)]
    with pytest.raises(CommandError, match="Pick a repo, or keep your notifications"):
        act("add_what", picks=[], about_me=False)
    act("add_what", picks=["acme/orkcraft", "acme/web"], about_me=True)
    assert _until(lambda: w.adding.step == "check" and not w.adding.busy)
    assert (w.adding.found, w.adding.error) == (3, "") and "your notifications" in w.adding.plan.says
    act("add_save")
    assert w.config["feeds"] == ["github: repos=acme/orkcraft,acme/web notifications=on"]
    act("add_open")
    act("add_back")
    assert w.adding.step == "pick"


def test_a_failed_login_stays_on_its_step_and_keeps_nothing(host, monkeypatch):
    monkeypatch.setattr(WatchtowerWorker, "feed_opener", Opener({"acme.atlassian.net/rest/api/3/myself": 401}))
    act = lambda name, **args: host.command("act", {"id": "tower", "act": name, "args": args})
    w = host.town.worker("tower")
    act("add_open")
    act("add_start", service="jira")
    act("add_login", values={"site": "acme", "email": "a@b.c", "token": "x" * 24})
    assert _until(lambda: w.adding.error and not w.adding.busy)
    assert w.adding.step == "login" and "refused" in w.adding.error and logins.listed() == []
    with pytest.raises(CommandError, match="Check it first"):
        act("add_save")
    with pytest.raises(CommandError, match="Not a link"):
        act("add_link", link="https://example.com")


def test_the_what_step_asks_what_is_wanted_done_with_the_source(host):
    """docs/design/barracks-flows.md §9: one more question per source, with its service's default; the answer is
    the tower's `wants` for that source, and it goes with each cart as its kind of work."""
    act = lambda name, **args: host.command("act", {"id": "tower", "act": name, "args": args})
    w = host.town.worker("tower")
    adding = lambda: host.detail("tower")["data"]["adding"]
    act("add_open")
    assert _until(lambda: w.adding.gh == "ann")
    act("add_start", service="github")
    assert _until(lambda: adding()["step"] == "what" and not adding()["busy"])
    a = adding()
    assert a["want"] == "change" and [x["label"] for x in a["wants"]] == ["Code change", "Reply", "Keep"]
    act("add_what", picks=["acme/orkcraft"], about_me=False, want="reply")
    assert _until(lambda: adding()["step"] == "check" and not adding()["busy"])
    act("add_save")
    assert w.config["wants"] == {"github": "reply"}
    act("add_open")
    act("add_start", service="github")
    assert _until(lambda: adding()["step"] == "what" and not adding()["busy"])
    assert adding()["want"] == "reply"                                       # what was set before
    act("add_what", picks=["acme/orkcraft"], about_me=False, want="")
    assert _until(lambda: adding()["step"] == "check" and not adding()["busy"])
    act("add_save")
    assert "wants" not in w.config                                           # nothing set: the pool decides
