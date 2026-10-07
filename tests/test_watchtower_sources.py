"""🗼 The sources the Watchtower's Add a source grew: failures that say which fix (Log in again, Edit, wait),
GitHub's many repos and notifications, GitLab, Discord — on recorded answers, no service asked."""
from __future__ import annotations

import imaplib
import json
import urllib.error
from types import SimpleNamespace

import pytest

from orkcraft.core.workers.watchtower import WatchtowerWorker
from orkcraft.gui.host import CommandError, Host
from orkcraft.realm import checkpoint, feeds, feeds_discord, logins, mailbox, masonry, quickadd, watch
from orkcraft.realm.sources_link import Link, recognise
from tests.test_watchtower_quickadd import ATL, Opener, _until


def ok(out) -> SimpleNamespace:
    return SimpleNamespace(returncode=0, stdout=json.dumps(out), stderr="")


def failed(said: str) -> SimpleNamespace:
    return SimpleNamespace(returncode=1, stdout="", stderr=said)


class Runner:
    """A fake `gh` / `glab` / `git`: answers by the command's start, remembers what ran."""

    def __init__(self, answers: dict) -> None:
        self.answers, self.ran = answers, []

    def __call__(self, cmd, **kw):
        self.ran.append(cmd)
        line = " ".join(cmd)
        for start, answer in sorted(self.answers.items(), key=lambda kv: -len(kv[0])):
            if line.startswith(start):
                return answer
        return failed(f"no fake for {line}")


GH = {
    "gh api notifications": ok([{"id": "77", "reason": "review_requested", "updated_at": "2026-10-02T05:00:00Z",
                                 "subject": {"title": "Fix login", "type": "PullRequest",
                                             "url": "https://api.github.com/repos/acme/web/pulls/3"},
                                 "repository": {"full_name": "acme/web", "html_url": "https://github.com/acme/web"}}]),
    "gh api repos/acme/web/events": ok([{"id": "501", "type": "IssuesEvent", "created_at": "2026-10-02T04:00:00Z",
                                         "actor": {"login": "bo"},
                                         "payload": {"action": "opened", "issue": {"number": 8, "title": "Crash"}}}]),
    "gh api repos/acme/gone/events": failed("gh: Not Found (HTTP 404)"),
}

GITLAB = {
    "gitlab.acme.io/api/v4/user": {"id": 5, "username": "ann"},
    "gitlab.acme.io/api/v4/todos": [{"id": 31, "action_name": "review_requested", "target_type": "MergeRequest",
                                     "target": {"title": "Pricing page"}, "author": {"username": "bo"},
                                     "project": {"path_with_namespace": "web/app"}, "body": "Pricing page",
                                     "target_url": "https://gitlab.acme.io/web/app/-/merge_requests/4",
                                     "created_at": "2026-10-02T05:00:00Z"}],
    "gitlab.acme.io/api/v4/projects/web%2Fapp/events": [
        {"id": 900, "author_id": 7, "author": {"username": "bo"}, "action_name": "commented on",
         "target_title": "Pricing page", "created_at": "2026-10-02T05:10:00Z",
         "note": {"id": 12, "body": "@ann can you check?", "noteable_type": "MergeRequest", "noteable_iid": 4}},
        {"id": 901, "author_id": 5, "author": {"username": "ann"}, "action_name": "opened", "target_type": "Issue",
         "target_title": "Mine", "target_iid": 2, "created_at": "2026-10-02T05:20:00Z"},
        {"id": 902, "author_id": 7, "author": {"username": "bo"}, "action_name": "pushed to",
         "push_data": {"ref": "main", "commit_count": 2, "commit_title": "Fix the tag"},
         "created_at": "2026-10-02T05:30:00Z"}],
    "gitlab.acme.io/api/v4/projects?membership": [{"path_with_namespace": "web/app", "last_activity_at": "2026-10-03"},
                                                  {"path_with_namespace": "web/api", "last_activity_at": "2026-10-01"}],
    "gitlab.acme.io/api/v4/projects/web%2Fgone/events": 404,
}

DISCORD = {
    "discord.com/api/v10/users/@me/guilds": [{"id": "111", "name": "Acme"}],
    "discord.com/api/v10/users/@me": {"id": "900", "username": "orkbot", "bot": True},
    "discord.com/api/v10/guilds/111/channels": [{"id": "222", "name": "general", "type": 0, "position": 1},
                                                {"id": "223", "name": "Voice", "type": 2, "position": 2},
                                                {"id": "224", "name": "support", "type": 0, "position": 0}],
    "discord.com/api/v10/channels/222/messages/555": {"id": "555", "author": {"id": "789", "username": "ann"}},
    "discord.com/api/v10/channels/222/messages": [
        {"id": "3", "content": "<@789> can you look?", "timestamp": "2026-10-02T05:10:00+00:00",
         "author": {"id": "42", "username": "bo", "global_name": "Bo"}, "mentions": [{"id": "789", "username": "ann"}]},
        {"id": "2", "content": "mine", "timestamp": "2026-10-02T05:05:00+00:00", "author": {"id": "789", "username": "ann"}},
        {"id": "1", "content": "deploy at 5", "timestamp": "2026-10-02T05:00:00+00:00",
         "author": {"id": "43", "username": "cy"}, "referenced_message": {"author": {"id": "789"}}},
        {"id": "0", "content": "beep", "timestamp": "2026-10-02T04:00:00+00:00", "author": {"id": "900", "username": "orkbot"}}],
    "discord.com/api/v10/channels/222": {"id": "222", "name": "general", "guild_id": "111"},
    "discord.com/api/v10/channels/224/messages": [],
    "discord.com/api/v10/channels/224": {"id": "224", "name": "support", "guild_id": "111"},
    "discord.com/api/v10/channels/333": 403,
}


@pytest.fixture(autouse=True)
def fresh():
    feeds_discord.CHANNELS.clear()


# -- failures say which fix -------------------------------------------------------------------------------

@pytest.mark.parametrize("answer, kind", [(401, "login"), (403, "login"), (404, "target"), (500, "network"),
                                          (429, "network")])
def test_a_failed_look_says_which_of_three_it_is(monkeypatch, answer, kind):
    monkeypatch.setenv("T_SLACK", "xoxp-1")
    got = feeds.look(feeds.parse("slack: token=T_SLACK")[0], Opener({"slack.com": answer}))
    assert got.kind == kind and got.error.startswith(f"slack: {answer}")


def test_a_target_out_of_reach_and_a_network_down_are_told_apart(monkeypatch):
    monkeypatch.setenv("T_SLACK", "xoxp-1")
    monkeypatch.setenv("T_FIGMA", "figd_1")
    gone = Opener({"slack.com/api/auth.test": {"ok": True, "user_id": "U1"},
                   "slack.com/api/search.messages": {"ok": True, "messages": {"matches": []}},
                   "slack.com/api/conversations.history": {"ok": False, "error": "channel_not_found"}})
    got = feeds.look(feeds.parse("slack: token=T_SLACK channels=C9")[0], gone)
    assert (got.kind, got.error) == ("target", "slack: C9 is gone or the app was removed from it (channel_not_found)")
    got = feeds.look(feeds.parse("figma: token=T_FIGMA files=AbC")[0],
                     Opener({"api.figma.com/v1/me": {"id": "1"}, "api.figma.com/v1/files/AbC/comments": 404}))
    assert got.kind == "target" and "the file AbC is gone" in got.error
    got = feeds.look(feeds.parse("figma: token=T_FIGMA files=AbC")[0], Opener({}))
    assert got.kind == "network" and got.error.startswith("figma: could not reach api.figma.com")
    gone_login = feeds.look(feeds.parse("figma: token=keychain:figma-nobody files=AbC")[0], Opener({}))
    assert gone_login.kind == "login" and "log in again" in gone_login.error


def test_the_mailbox_tells_a_refused_login_from_a_missing_folder_and_the_network():
    class Server:
        def __init__(self, host, port, *, refuse=False, folder="OK", down=False):
            if down:
                raise OSError("no route")
            self.refuse, self.folder = refuse, folder

        def login(self, user, password):
            if self.refuse:
                raise imaplib.IMAP4.error("AUTHENTICATIONFAILED")

        def select(self, folder, readonly=True):
            return self.folder, [b""]

        def logout(self):
            pass

    cfg = {"host": "gmail", "user": "ann@gmail.com", "password_env": "T_PW"}
    import os
    os.environ["T_PW"] = "abcdabcdabcdabcd"
    try:
        assert mailbox.look(cfg, lambda h, p: Server(h, p, refuse=True)).kind == "login"
        assert mailbox.look(cfg, lambda h, p: Server(h, p, folder="NO")).kind == "target"
        assert mailbox.look(cfg, lambda h, p: Server(h, p, down=True)).kind == "network"
    finally:
        del os.environ["T_PW"]
    assert mailbox.look({"host": "gmail", "user": "a@b.c", "password_env": "keychain:gone"}).kind == "login"
    assert [watch.error_kind(x) for x in ("github: HTTP 401: Bad credentials", "github: gh: Not Found (HTTP 404)",
                                          "github: 'x' is not owner/repo", "github: timed out")] == \
        ["login", "target", "target", "network"]


# -- GitHub: many repos and the notifications ----------------------------------------------------------------

def test_github_hears_notifications_as_mentions_and_many_repos_through_gh():
    feed, err = feeds.parse("github: repos=acme/web notifications=on")
    assert not err and feed.identity == "github|||"
    got = feeds.look(feed, Opener({}), Runner(GH))
    assert [(i.key, i.mention) for i in got.items] == [("acme/web:501", False), ("n:77:2026-10-02T05:00:00Z", True)]
    note = got.items[1]
    assert note.title == "@ review asked · acme/web: Fix login" and note.url == "https://github.com/acme/web/pull/3"
    assert got.items[0].title == "acme/web · issue #8 opened: Crash"
    assert watch.Signal("t", "github", note.title, mention=True).event == "watch.mention"
    assert watch.Signal("t", "github", "x").event == "watch.github"
    gone = feeds.look(feeds.parse("github: repos=acme/gone")[0], Opener({}), Runner(GH))
    assert (gone.kind, gone.error) == ("target", "github: acme/gone is gone or this login may not read it")
    out = feeds.look(feed, Opener({}), Runner({"gh api": failed("To get started with GitHub CLI, please run:  gh auth login")}))
    assert out.kind == "login"


def test_github_with_a_token_asks_over_https(monkeypatch):
    monkeypatch.setenv("T_GH", "github_pat_1")
    api = Opener({"api.github.com/notifications": [], "api.github.com/repos/acme/web/events": [
        {"id": "7", "type": "PushEvent", "created_at": "2026-10-02T04:00:00Z", "actor": {"login": "bo"},
         "payload": {"ref": "refs/heads/main", "commits": [{"message": "Fix"}]}}]})
    got = feeds.look(feeds.parse("github: token=T_GH repos=acme/web notifications=on")[0], api, Runner({}))
    assert [i.title for i in got.items] == ["acme/web · push to main: 1 commit"]
    assert all(h.get("Authorization") == "Bearer github_pat_1" for _, h in api.asked)


@pytest.mark.parametrize("line, err", [
    ("github: notifications=off", "set repos= or notifications=on"),
    ("github: repos=acme", "owner/repo"),
    ("github: repos=acme/web notifications=yes", "on or off"),
    ("gitlab: host=gitlab.acme.io", "set projects= or todos=on"),
    ("gitlab: host=not_a_host todos=on", "host name"),
    ("discord: token=T_D channels=1 me=ann", "user id"),
    ("discord: token=T_D", "channels="),
])
def test_the_new_lines_say_what_is_wrong(line, err):
    assert err in feeds.parse(line)[1]


# -- GitLab ----------------------------------------------------------------------------------------------

def test_gitlab_hears_todos_and_project_events_but_not_your_own(monkeypatch):
    monkeypatch.setenv("T_GL", "glpat-1")
    feed, err = feeds.parse("gitlab: host=gitlab.acme.io token=T_GL projects=web/app todos=on")
    assert not err and feed.identity == "gitlab|gitlab.acme.io||T_GL"
    api = Opener(GITLAB)
    got = feeds.look(feed, api)
    assert [(i.key, i.mention) for i in got.items] == [("todo:31", True), ("web/app:900", True), ("web/app:902", False)]
    assert got.items[0].title == "@ review asked · web/app: Pricing page"
    assert got.items[1].url == "https://gitlab.acme.io/web/app/-/merge_requests/4#note_12"
    assert got.items[2].title == "web/app · bo pushed to main: 2 commits"
    assert all(h.get("Private-token") == "glpat-1" for _, h in api.asked)
    gone = feeds.look(feeds.parse("gitlab: host=gitlab.acme.io token=T_GL projects=web/gone")[0], api)
    assert gone.kind == "target" and "web/gone is gone" in gone.error
    assert watch.Signal("t", "gitlab", "x", mention=True).event == "watch.mention"
    assert watch.Signal("t", "gitlab", "x").event == "watch.comment"


def test_gitlab_without_a_token_asks_glab():
    runner = Runner({"glab api --hostname gitlab.com user": ok({"id": 5, "username": "ann"}),
                     "glab api --hostname gitlab.com todos": ok([])})
    got = feeds.look(feeds.parse("gitlab: todos=on")[0], Opener({}), runner)
    assert got.error == "" and runner.ran[0][:3] == ["glab", "api", "--hostname"]


# -- Discord ---------------------------------------------------------------------------------------------

def test_discord_tells_mentions_and_answers_and_skips_its_own(monkeypatch):
    monkeypatch.setenv("T_D", "bot.token.here")
    api = Opener(DISCORD)
    got = feeds.look(feeds.parse("discord: token=T_D channels=222 me=789")[0], api)
    assert [(i.key, i.mention) for i in got.items] == [("222:1", True), ("222:3", True)]
    assert got.items[1].title == "@ Bo in #general: @you can you look?"
    assert got.items[1].url == "https://discord.com/channels/111/222/3"
    assert all(h.get("Authorization") == "Bot bot.token.here" for _, h in api.asked)
    blind = feeds.look(feeds.parse("discord: token=T_D channels=333")[0], api)
    assert blind.kind == "target" and "cannot see the channel 333" in blind.error
    assert feeds.look(feeds.parse("discord: token=T_D channels=222")[0], Opener({"discord.com": 401})).kind == "login"


def test_discord_quick_add_checks_a_bot_lists_channels_and_finds_me_from_a_link():
    api = Opener(DISCORD)
    with pytest.raises(quickadd.Refused, match="not a bot"):
        quickadd.verify("discord", {"token": "a.b.c"}, Opener({"discord.com/api/v10/users/@me": {"id": "1"}}))
    login = quickadd.verify("discord", {"token": "bot.token.here"}, api)
    assert (login.who, login.site, login.refs) == ("orkbot", "900", {"token": "keychain:discord-orkbot"})
    assert quickadd.discord_invite(login) == \
        "https://discord.com/oauth2/authorize?client_id=900&scope=bot&permissions=66560"
    kept = quickadd.kept("discord")[0]
    assert kept.site == "" and quickadd.discord_bot(kept, api).site == "900"
    assert [(o.id, o.label) for o in quickadd.options(login, api)] == [("224", "Acme · #support"), ("222", "Acme · #general")]
    assert quickadd.discord_me(login, "https://discord.com/channels/111/222/555", api) == "789"
    assert quickadd.discord_me(login, "<@789>", api) == "789" and quickadd.discord_me(login, "", api) == ""
    with pytest.raises(quickadd.Refused, match="user id"):
        quickadd.discord_me(login, "ann", api)
    plan = quickadd.plan(login, ["222"], me="789")
    assert plan.feed == "discord: token=keychain:discord-orkbot channels=222 me=789" and feeds.check([plan.feed]) == []
    assert quickadd.first_look(login, plan, api) == (2, "")
    assert recognise("https://discord.com/channels/@me/555") == Link("discord", "", "", "")


# -- the steps in the GUI: GitLab from a self-hosted link, Discord, Log in again, Edit -------------------------

@pytest.fixture
def host(fake_repo, monkeypatch):
    monkeypatch.setattr(WatchtowerWorker, "gh_runner", staticmethod(Runner({
        "git -C": SimpleNamespace(returncode=0, stdout="git@gitlab.acme.io:web/app.git\n", stderr=""),
        "gh api user": failed("not logged in: run gh auth login"),
        "glab": failed("glab: not logged in")})))
    monkeypatch.setattr(WatchtowerWorker, "feed_opener", Opener({**ATL, **GITLAB, **DISCORD}))
    spec = {"id": "tower", "title": "Tower", "icon": "🗼", "orc": {"name": "Lookout"}, "type": "watchtower", "config": {}}
    assert masonry.save_spec(fake_repo, spec) == []
    checkpoint.ensure(fake_repo)
    return Host(fake_repo, auto_commit=False)


def _act(host):
    return lambda name, **args: host.command("act", {"id": "tower", "act": name, "args": args})


def test_gitlab_from_a_self_hosted_link_with_a_token_ticks_this_project(host):
    act, w = _act(host), host.town.worker("tower")
    logins.save("gitlab-gitlab.acme.io", "glpat-old", "gitlab", "gitlab.acme.io")
    assert recognise("https://gitlab.acme.io/web/app/-/issues/3") is None          # unknown host…
    act("add_open")
    assert act("add_link", link="https://gitlab.acme.io/web/app/-/issues/3") == "gitlab"   # …known by its login
    assert w.adding.prefill == {"host": "gitlab.acme.io"}
    view = host.detail("tower")["data"]["adding"]
    assert view["how"][0]["url"].startswith("https://gitlab.acme.io/-/user_settings/personal_access_tokens?name=orkcraft")
    act("add_login", values={"token": "glpat-new"})
    assert _until(lambda: w.adding.step == "what" and not w.adding.busy)
    assert w.adding.login.who == "ann · gitlab.acme.io"
    assert [(o.id, o.picked) for o in w.adding.options] == [("web/app", True), ("web/api", False)]
    act("add_what", picks=["web/app"], about_me=True)
    assert _until(lambda: w.adding.step == "check" and not w.adding.busy)
    assert (w.adding.found, w.adding.error) == (3, "")
    act("add_save")
    assert w.config["feeds"] == ["gitlab: host=gitlab.acme.io token=keychain:gitlab-gitlab.acme.io projects=web/app todos=on"]
    assert logins.resolve("keychain:gitlab-gitlab.acme.io") == "glpat-new"


def test_discord_adds_a_bot_and_a_channel_from_its_link(host):
    act, w = _act(host), host.town.worker("tower")
    act("add_open")
    assert act("add_link", link="https://discord.com/channels/111/222") == "discord"
    act("add_login", values={"token": "bot.token.here"})
    assert _until(lambda: w.adding.step == "what" and not w.adding.busy)
    a = host.detail("tower")["data"]["adding"]
    assert a["invite"].endswith("client_id=900&scope=bot&permissions=66560") and a["picks"] == ["222"]
    act("add_again")
    assert _until(lambda: not w.adding.busy) and w.adding.picks == ["222"]
    act("add_what", picks=["222"], about_me=True, me="https://discord.com/channels/111/222/555")
    assert _until(lambda: w.adding.step == "check" and not w.adding.busy)
    act("add_save")
    assert w.config["feeds"] == ["discord: token=keychain:discord-orkbot channels=222 me=789"]


def test_a_refused_token_is_fixed_with_log_in_again_and_the_line_keeps_its_place(host, monkeypatch):
    act, w = _act(host), host.town.worker("tower")
    old = "jira: site=acme.atlassian.net user=keychain:atl-user token=keychain:atl jql=project in (WEB)"
    other = "figma: token=keychain:figma-ann files=AbC"
    assert w.save_config({"feeds": [old, other]})
    w.apply_feeds([(feeds.parse(old)[0], feeds.Look(error="jira: 401 the token was refused — log in again", kind="login"))])
    row = next(x for x in host.detail("tower")["data"]["listed"] if x["kind"] == "jira")
    assert (row["fails"], row["fix"], row["editable"]) == ("login", "Log in again", True)
    assert act("edit", source=row["id"], login=True) == "jira"
    a = host.detail("tower")["data"]["adding"]
    assert (a["step"], a["editing"], a["picks"], a["about_me"]) == ("login", row["id"], ["WEB"], False)
    assert a["link"]["site"] == "acme.atlassian.net"                           # the site is not asked again
    assert a["kept"] == []                                                     # not the login just refused
    act("add_login", values={"email": "ann@acme.io", "token": "n" * 24})
    assert _until(lambda: w.adding.step == "what" and not w.adding.busy)
    assert w.adding.picks == ["WEB"]
    act("add_what", picks=["WEB"], about_me=False)
    assert _until(lambda: w.adding.step == "check" and not w.adding.busy)
    act("add_save")
    new = w.config["feeds"]
    assert len(new) == 2 and new[1] == other and new[0].startswith("jira: site=acme.atlassian.net user=keychain:atlassian-")
    assert new[0].endswith("jql=project in (WEB)") and logins.resolve(feeds.parse(new[0])[0].opts["token"]) == "n" * 24


def test_edit_opens_step_two_with_its_picks_and_a_network_failure_offers_no_button(host):
    act, w = _act(host), host.town.worker("tower")
    logins.save("discord-orkbot", "bot.token.here", "discord", "orkbot")
    line = "discord: token=keychain:discord-orkbot channels=222 me=789"
    assert w.save_config({"feeds": [line], "cron": "every 15m"})
    w.apply_feeds([(feeds.parse(line)[0], feeds.Look(error="discord: could not reach discord.com", kind="network"))])
    rows = {x["kind"]: x for x in host.detail("tower")["data"]["listed"]}
    assert (rows["discord"]["fails"], rows["discord"]["fix"]) == ("network", "")
    assert rows["cron"]["editable"] is False
    with pytest.raises(CommandError, match="change it in the building's settings"):
        act("edit", source="cron")
    act("edit", source=f"feed:{line}")
    assert _until(lambda: w.adding.step == "what" and not w.adding.busy)
    assert (w.adding.picks, w.adding.me) == (["222"], "789")
    act("add_what", picks=["222", "224"], about_me=True, me="789")
    assert _until(lambda: w.adding.step == "check" and not w.adding.busy)
    act("add_save")
    assert w.config["feeds"] == ["discord: token=keychain:discord-orkbot channels=222,224 me=789"]
    act("edit", source=f"feed:{w.config['feeds'][0]}", login=True)
    act("add_back")                                                            # to the picker: the edit is dropped
    assert (w.adding.step, w.adding.editing) == ("pick", "")


def test_the_old_github_setting_moves_into_a_line_when_edited(host, monkeypatch):
    act, w = _act(host), host.town.worker("tower")
    monkeypatch.setattr(WatchtowerWorker, "gh_runner", staticmethod(Runner({
        **GH, "gh api user/repos": ok([{"full_name": "acme/web", "pushed_at": "2026-10-01"}]),
        "gh api user": SimpleNamespace(returncode=0, stdout="ann\n", stderr=""), "git -C": failed("no origin")})))
    assert w.save_config({"github": "acme/web"})
    row = host.detail("tower")["data"]["listed"][0]
    assert (row["id"], row["editable"]) == ("github", True)
    act("edit", source="github")
    assert _until(lambda: w.adding.step == "what" and not w.adding.busy)
    assert (w.adding.picks, w.adding.about_me) == (["acme/web"], False)
    act("add_what", picks=["acme/web"], about_me=True)
    assert _until(lambda: w.adding.step == "check" and not w.adding.busy)
    act("add_save")
    assert "github" not in w.config and w.config["feeds"] == ["github: repos=acme/web notifications=on"]


def test_from_source_refuses_what_the_steps_cannot_make_again():
    with pytest.raises(quickadd.Refused, match="own query"):
        quickadd.from_source({}, "feed:jira: site=a.atlassian.net user=U_X token=T_X jql=status = Done")
    with pytest.raises(quickadd.Refused, match="not Gmail"):
        quickadd.from_source({"host": "imap.acme.io"}, "mail")
    s = quickadd.from_source({"host": "gmail", "user": "ann@gmail.com", "password_env": "keychain:gmail-ann",
                              "folder": "Work"}, "mail")
    assert (s.login.service, s.login.account, s.folder) == ("gmail", "ann@gmail.com", "Work")
    s = quickadd.from_source({}, "feed:github: repos=a/b,c/d")
    assert (s.picks, s.about_me, s.login.refs) == (["a/b", "c/d"], False, {})


def test_a_list_that_cannot_be_read_still_offers_this_project(fake_repo):
    runner = Runner({"git -C": SimpleNamespace(returncode=0, stdout="https://github.com/acme/web.git\n", stderr=""),
                     "gh api user/repos": failed("gh: HTTP 403: not available")})
    login = quickadd.Verified("github", "ann", "ann")
    assert [(o.id, o.picked) for o in quickadd.options(login, Opener({}), runner, fake_repo)] == [("acme/web", True)]
    with pytest.raises(quickadd.Refused, match="not available"):
        quickadd.options(login, Opener({}), Runner({"gh api user/repos": failed("gh: HTTP 403: not available")}), fake_repo)


# -- Everything (§6) --------------------------------------------------------------------------------------

def test_everything_is_one_line_per_service_and_each_reads_back():
    gh = quickadd.Verified("github", "ann", "ann")
    atl = quickadd.Verified("jira", "Ann", "acme.atlassian.net", {"user": "keychain:u", "token": "keychain:t"},
                            "acme.atlassian.net")
    conf = quickadd.Verified("confluence", "Ann", "acme.atlassian.net", atl.refs, "acme.atlassian.net")
    slack = quickadd.Verified("slack", "ann", "acme.slack.com", {"token": "keychain:slack-acme"}, "acme.slack.com")
    bot = quickadd.Verified("discord", "orkbot", "orkbot", {"token": "keychain:discord-orkbot"}, "900")
    mail = quickadd.Verified("gmail", "ann@gmail.com", "ann@gmail.com", {"password": "keychain:gmail-ann"})
    lines = {
        "github": quickadd.plan(gh, ["acme/web"], everything=True).feed,
        "jira": quickadd.plan(atl, ["WEB"], everything=True).feed,
        "confluence": quickadd.plan(conf, [], everything=True).feed,
        "slack": quickadd.plan(slack, [], everything=True).feed,
        "discord": quickadd.plan(bot, [], me="789", everything=True, guilds=("111",)).feed,
    }
    assert lines["github"] == "github: repos=acme/web notifications=all"
    assert lines["jira"].endswith("jql=updated >= -1d") and lines["confluence"].endswith("cql=type in (page, blogpost, comment)")
    assert lines["slack"] == "slack: token=keychain:slack-acme everything=on"
    assert lines["discord"] == "discord: token=keychain:discord-orkbot guilds=111 me=789"
    assert feeds.check(list(lines.values())) == []
    for line in lines.values():
        assert quickadd.from_source({}, f"feed:{line}").everything
    assert quickadd.plan(mail, [], everything=True).changes["folder"] == "[Gmail]/All Mail"
    assert quickadd.from_source({"host": "gmail", "folder": "[Gmail]/All Mail"}, "mail").everything
    with pytest.raises(quickadd.Refused, match="no server"):
        quickadd.plan(bot, [], everything=True)
    figma = quickadd.Verified("figma", "ann", "ann", {"token": "keychain:figma-ann"})
    assert quickadd.plan(figma, ["AbC"], everything=True).feed == "figma: token=keychain:figma-ann files=AbC"


def test_slack_everything_searches_every_channel_and_github_all_tells_watching_from_mentions(monkeypatch):
    monkeypatch.setenv("T_SLACK", "xoxp-1")
    api = Opener({"slack.com/api/auth.test": {"ok": True, "user_id": "UME"},
                  "slack.com/api/search.messages?query=after": {"ok": True, "messages": {"matches": [
                      {"ts": "1790000100.1", "user": "UBO", "username": "bo", "text": "lunch?",
                       "channel": {"id": "C1", "name": "random"}},
                      {"ts": "1790000200.1", "user": "UBO", "username": "bo", "text": "hi",
                       "channel": {"id": "D1", "is_im": True}}]}},
                  "slack.com/api/search.messages": {"ok": True, "messages": {"matches": []}}})
    got = feeds.look(feeds.parse("slack: token=T_SLACK everything=on")[0], api)
    assert [(i.title, i.mention) for i in got.items] == [("bo in #random: lunch?", False),
                                                          ("@ bo in a direct message: hi", True)]
    watching = dict(GH)
    watching["gh api notifications"] = ok([{"id": "1", "reason": "subscribed", "updated_at": "2026-10-02T05:00:00Z",
                                            "subject": {"title": "Bump"}, "repository": {"full_name": "acme/web"}}])
    runner = Runner(watching)
    got = feeds.look(feeds.parse("github: notifications=all")[0], Opener({}), runner)
    assert [(i.title, i.mention) for i in got.items] == [("watching · acme/web: Bump", False)]
    assert "participating=false" in runner.ran[0][2]


def test_discord_everything_hears_every_text_channel_of_a_server(monkeypatch):
    monkeypatch.setenv("T_D", "bot.token.here")
    got = feeds.look(feeds.parse("discord: token=T_D guilds=111 me=789")[0], Opener(DISCORD))
    assert got.error == "" and {i.key.split(":")[0] for i in got.items} == {"222"}
    asked = feeds.look(feeds.parse("discord: token=T_D guilds=999")[0], Opener({**DISCORD, "guilds/999/channels": 403}))
    assert asked.kind == "target" and "not in the server 999" in asked.error


def test_everything_in_the_panel_asks_what_to_listen_for(host):
    act, w = _act(host), host.town.worker("tower")
    act("add_open")
    act("add_link", link="https://acme.atlassian.net/browse/WEB-3")
    act("add_login", values={"email": "ann@acme.io", "token": "t" * 24})
    assert _until(lambda: w.adding.step == "what" and not w.adding.busy)
    a = host.detail("tower")["data"]["adding"]
    assert a["everything_says"].startswith("Everything") and a["asks_intent"] and not a["everything"]
    act("add_what", picks=["WEB"], about_me=True, everything=True, intent="user feedback about the app")
    assert _until(lambda: w.adding.step == "check" and not w.adding.busy)
    assert host.detail("tower")["data"]["adding"]["listens_for"] == "user feedback about the app"
    act("add_save")
    assert w.config["feeds"][0].endswith("jql=updated >= -1d") and w.intent == "user feedback about the app"
    row = host.detail("tower")["data"]["listed"][0]
    assert "everything" in row["line"] and row["editable"]
