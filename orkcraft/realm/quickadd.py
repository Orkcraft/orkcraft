"""Add a source to the Watchtower in three steps: log in, pick what, check (docs/design/watchtower-quick-add.md).

Each service says what its login takes (at most one secret), how the person gets it (a link, the
clicks), how the login is checked, what there is to pick from, and what setting the picks make.
The first look runs before anything is saved, so the person sees it work — or why not — first.

    verify("figma", {"token": "figd_…"})            → Verified(who="ann", account="ann", …)
    options("jira", login)                           → [Option("WEB", "Website", …), …]
    plan("jira", login, ["WEB"], {"about_me": True}) → Plan({"feeds": [...]}, "…")
    first_look(plan, …)                              → (14, "")

The network is the caller's thread: nothing here runs on the town's. Tokens go to realm/logins.py
and nowhere else; what this module returns names them (`keychain:…`), never holds them.
"""
from __future__ import annotations

import base64
import imaplib
import json
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from orkcraft.realm import feeds, feeds_discord, feeds_git, logins, mailbox, sources_link, watch

TIMEOUT_S = 15
LIST_MAX = 200


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    secret: bool = False
    placeholder: str = ""
    shape: str = ""             # a regex the value should match (checked as typed, a hint only)
    shape_says: str = ""
    optional: bool = False      # may stay empty: a CLI's login (gh, glab), a default host


@dataclass(frozen=True)
class Service:
    id: str
    label: str
    fields: tuple[Field, ...] = ()
    how: tuple[tuple[str, str], ...] = ()       # (what to do, a link) — the clicks before the paste
    picks: str = ""                             # what step 2 lists: repos, channels, projects, spaces, files
    about_me: str = ""                          # the "about me" switch, on by default, when the service has one
    note: str = ""
    everything: str = ""                        # the Everything switch (§6), off by default; "" none


ATL_SITE = Field("site", "Your Atlassian site", placeholder="acme.atlassian.net")
ATL_EMAIL = Field("email", "Your e-mail at Atlassian", placeholder="you@acme.com")
ATL_TOKEN = Field("token", "API token", True, "paste the token", r"^\S{20,}$", "an Atlassian API token is long")
ATL_HOW = (("Create an API token (Create API token → any label → Copy)",
            "https://id.atlassian.com/manage-profile/security/api-tokens"),)

SLACK_SCOPES = ("search:read", "channels:history", "groups:history", "im:history", "mpim:history",
                "channels:read", "groups:read", "users:read")
SLACK_MANIFEST = {"display_information": {"name": "Orkcraft listener",
                                          "description": "Reads your mentions, DMs and the channels you pick, for orkcraft."},
                  "oauth_config": {"scopes": {"user": list(SLACK_SCOPES)}},
                  "settings": {"org_deploy_enabled": False, "socket_mode_enabled": False}}
SLACK_NEW_APP = "https://api.slack.com/apps?new_app=1&manifest_json=" + urllib.parse.quote(json.dumps(SLACK_MANIFEST))

GH_TOKEN_PAGE = "https://github.com/settings/personal-access-tokens/new"
GITLAB_TOKEN_PAGE = "https://{host}/-/user_settings/personal_access_tokens?name=orkcraft&scopes=read_api"

SERVICES: dict[str, Service] = {s.id: s for s in (
    Service("github", "GitHub",
            (Field("token", "Or a token", True, "github_pat_… or ghp_…", r"^(github_pat_|gh[pousr]_)\S+$",
                   "a GitHub token starts with github_pat_ or ghp_", optional=True),),
            (("Without gh: make a token — read-only Metadata, Issues, Pull requests "
              "(a classic token with notifications to hear them)", GH_TOKEN_PAGE),),
            picks="repos", about_me="My notifications — review requests, mentions, assignments",
            everything="Everything — the notifications of the repos I watch too",
            note="Uses the gh command's login: nothing to paste. Not logged in? Run `gh auth login` in a terminal "
                 "and Check again — or paste a token."),
    Service("gitlab", "GitLab",
            (Field("host", "Your GitLab", placeholder="gitlab.com", optional=True),
             Field("token", "Personal access token", True, "glpat-…", r"^glpat-\S+$",
                   "a GitLab token starts with glpat-", optional=True)),
            (("Make a token — the page opens filled in (read_api); Create, then copy it", GITLAB_TOKEN_PAGE),),
            picks="projects", about_me="My to-dos — mentions, assignments, review requests",
            note="Logged in with glab? Leave the token empty and Continue."),
    Service("gmail", "Gmail",
            (Field("email", "Your Gmail address", placeholder="you@gmail.com"),
             Field("password", "App password", True, "16 letters", r"^[a-zA-Z]{4}( ?[a-zA-Z]{4}){3}$",
                   "an app password is 16 letters")),
            (("Turn on 2-Step Verification, if it is off", "https://myaccount.google.com/signinoptions/twosv"),
             ("Create an app password (any name) and copy its 16 letters", "https://myaccount.google.com/apppasswords")),
            note="Read-only: the tower never marks mail read in the mailbox.",
            everything="Everything — the whole mailbox (All Mail), not only the inbox"),
    Service("slack", "Slack",
            (Field("token", "User OAuth Token", True, "xoxp-…", r"^xoxp-\S+$", "a user token starts with xoxp-"),),
            (("Create the app — Slack opens with it filled in; pick the workspace, Create", SLACK_NEW_APP),
             ("Install it: Install to Workspace → Allow", ""),
             ("On OAuth & Permissions, copy the User OAuth Token (xoxp-…)", "")),
            picks="channels", about_me="Mentions and direct messages",
            everything="Everything — every message I can see, in every channel"),
    Service("jira", "Jira", (ATL_SITE, ATL_EMAIL, ATL_TOKEN), ATL_HOW, picks="projects",
            about_me="Issues I watch, am assigned or reported",
            everything="Everything — new comments on every issue of the site"),
    Service("confluence", "Confluence", (ATL_SITE, ATL_EMAIL, ATL_TOKEN), ATL_HOW, picks="spaces",
            about_me="Pages and comments that mention me",
            everything="Everything — every new page and comment of the site"),
    Service("figma", "Figma",
            (Field("token", "Personal access token", True, "figd_…", r"^figd_\S+$", "a Figma token starts with figd_"),),
            (("Settings → Security → Generate new token; allow reading comments and files", "https://www.figma.com/settings"),),
            picks="files"),
    Service("discord", "Discord",
            (Field("token", "The bot's token", True, "paste the token", r"^[\w-]{20,}\.[\w-]{4,}\.[\w-]{20,}$",
                   "a bot token is three parts with dots"),),
            (("New Application → Bot → Reset Token, and copy it", "https://discord.com/developers/applications"),
             ("On the same page switch on Message Content Intent, then Save", ""),
             ("Paste the token here; the next step gives the link that invites it to your server", "")),
            picks="channels", everything="Everything — every channel of the servers it is in",
            note="Discord lets a tool listen only as a bot you invite: it hears the channels it can see."),
)}
ATLASSIAN = ("jira", "confluence")


@dataclass
class Verified:
    """A login that works: who it is, and the names it is kept under (`keychain:…`, or gh's)."""
    service: str
    who: str
    account: str                                   # the site, the address, the workspace, the handle
    refs: dict[str, str] = field(default_factory=dict)     # field → `keychain:<name>`
    site: str = ""


@dataclass(frozen=True)
class Option:
    id: str
    label: str
    meta: str = ""
    picked: bool = False


@dataclass
class Plan:
    changes: dict                                  # the building's settings to change
    says: str                                      # what it will hear, in words
    feed: str = ""                                 # the feeds line, when it is one


class Refused(Exception):
    """The service said no, or could not be reached: the text says which and what to do."""


# -- helpers ----------------------------------------------------------------------------------------------

def _site(value: str) -> str:
    v = (value or "").strip().lower().removeprefix("https://").removeprefix("http://").split("/")[0]
    if v and "." not in v:
        v += ".atlassian.net"
    if not feeds.SITE.match(v):
        raise Refused("That is not a site — like acme.atlassian.net")
    return v


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9._@-]+", "-", (text or "").lower()).strip("-")[:80] or "login"


def _get(url: str, head: dict, opener) -> dict | list:
    try:
        return feeds.get_json(url, head, opener)
    except urllib.error.HTTPError as e:
        raise Refused({401: "The token was refused — copy it again",
                       403: "The token may not read this — check what it is allowed",
                       404: "Not found — check the site or the link"}.get(e.code, f"{e.code} {e.reason}")) from None
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise Refused(f"Could not reach {urllib.parse.urlsplit(url).hostname}: {getattr(e, 'reason', e)}") from None


def _host(value: str, default: str = "gitlab.com") -> str:
    v = (value or "").strip().lower().removeprefix("https://").removeprefix("http://").split("/")[0] or default
    if not feeds.SITE.match(v):
        raise Refused("That is not a host — like gitlab.com or gitlab.acme.io")
    return v


def _gh_head(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}


def _cli(runner, cmd: list[str], kind: str):
    try:
        return feeds_git.cli(runner, cmd, kind)
    except feeds.Failed as e:
        raise Refused(str(e).removeprefix(f"{kind}: ")) from None


def _git_api(login: "Verified", path: str, opener, runner):
    """GitHub's or GitLab's API as this login: its token over HTTPS, else the CLI's (`gh` / `glab`)."""
    token = logins.resolve(login.refs["token"]) if login.refs.get("token") else ""
    if login.service == "github":
        return _get(f"{feeds_git.GH_API}/{path}", _gh_head(token), opener) if token else \
            _cli(runner, ["gh", "api", path], "github")
    if token:
        return _get(f"https://{login.site}/api/v4/{path}", {"PRIVATE-TOKEN": token}, opener)
    return _cli(runner, ["glab", "api", "--hostname", login.site, path], "gitlab")


def _basic(email: str, token: str) -> dict:
    return {"Authorization": "Basic " + base64.b64encode(f"{email}:{token}".encode()).decode()}


def _run(runner, cmd: list[str]) -> subprocess.CompletedProcess:
    return runner(cmd, capture_output=True, text=True, timeout=TIMEOUT_S)


# -- step 1: log in ---------------------------------------------------------------------------------------

def gh_login(runner=subprocess.run) -> str:
    """Who `gh` is logged in as on github.com, or "" (not installed, not logged in)."""
    try:
        out = _run(runner, ["gh", "api", "user", "--jq", ".login"])
    except (OSError, subprocess.SubprocessError):
        return ""
    who = (out.stdout or "").strip() if out.returncode == 0 else ""
    return who if re.fullmatch(r"[A-Za-z0-9-]{1,39}", who) else ""


def verify(service: str, values: dict, opener=urllib.request.urlopen, runner=subprocess.run,
           imap_factory=imaplib.IMAP4_SSL) -> Verified:
    """Check a login with the service itself; on success keep its secrets in realm/logins.py.
    Raises Refused with what to do."""
    s = SERVICES.get(service)
    if s is None:
        raise Refused(f"{service!r} cannot be added here yet")
    v = {k: str(values.get(k) or "").strip() for k in ("site", "email", "token", "password", "host")}
    if service == "github":
        if not v["token"]:
            who = gh_login(runner)
            if not who:
                raise Refused("gh is not logged in — run `gh auth login` in a terminal and Check again, or paste a token")
            return Verified(service, who, who)
        me = _get(f"{feeds_git.GH_API}/user", _gh_head(v["token"]), opener)
        who = str((me or {}).get("login") or "") if isinstance(me, dict) else ""
        if not who:
            raise Refused("GitHub did not say who this token is")
        return Verified(service, who, who, {"token": logins.save(f"github-{_slug(who)}", v["token"], "github", who)})
    if service == "gitlab":
        host = _host(v["host"])
        if not v["token"]:
            me = _cli(runner, ["glab", "api", "--hostname", host, "user"], "gitlab")
            refs: dict[str, str] = {}
        else:
            me = _get(f"https://{host}/api/v4/user", {"PRIVATE-TOKEN": v["token"]}, opener)
            refs = {"token": logins.save(f"gitlab-{_slug(host)}", v["token"], "gitlab", host)}
        who = str((me or {}).get("username") or "?") if isinstance(me, dict) else "?"
        return Verified(service, f"{who} · {host}", host, refs, host)
    for f in s.fields:
        if not v.get(f.key) and not f.optional:
            raise Refused(f"{f.label} is empty")
    if service == "gmail":
        email, password = v["email"], v["password"].replace(" ", "")
        try:
            conn = imap_factory(mailbox.PROVIDERS["gmail"], 993)
            conn.login(email, password)
            conn.logout()
        except imaplib.IMAP4.error:
            raise Refused("Gmail refused it — check the address and make a new app password") from None
        except OSError as e:
            raise Refused(f"Could not reach Gmail: {e}") from None
        name = f"gmail-{_slug(email)}"
        return Verified(service, email, email, {"password": logins.save(name, password, "gmail", email)})
    if service == "slack":
        me = _get("https://slack.com/api/auth.test", {"Authorization": f"Bearer {v['token']}"}, opener)
        if not isinstance(me, dict) or not me.get("ok"):
            raise Refused(f"Slack refused the token: {(me or {}).get('error', 'no answer')}")
        team = urllib.parse.urlsplit(str(me.get("url", ""))).hostname or str(me.get("team", "slack"))
        ref = logins.save(f"slack-{_slug(team.split('.')[0])}", v["token"], "slack", team)
        return Verified(service, f"{me.get('user', '?')} · {team}", team, {"token": ref}, team)
    if service in ATLASSIAN:
        site = _site(v["site"])
        base = f"https://{site}" + ("/wiki/rest/api/user/current" if service == "confluence" else "/rest/api/3/myself")
        me = _get(base, _basic(v["email"], v["token"]), opener)
        who = str((me or {}).get("displayName") or v["email"]) if isinstance(me, dict) else v["email"]
        name = f"atlassian-{_slug(site)}"
        refs = {"user": logins.save(f"{name}-user", v["email"], "atlassian", site),
                "token": logins.save(name, v["token"], "atlassian", site)}
        return Verified(service, f"{who} · {site}", site, refs, site)
    if service == "figma":
        me = _get("https://api.figma.com/v1/me", {"X-Figma-Token": v["token"]}, opener)
        handle = str((me or {}).get("handle") or "figma") if isinstance(me, dict) else "figma"
        return Verified(service, handle, handle, {"token": logins.save(f"figma-{_slug(handle)}", v["token"], "figma", handle)})
    if service == "discord":
        me = _get(f"{feeds_discord.API}/users/@me", feeds_discord.head(v["token"]), opener)
        if not isinstance(me, dict) or not me.get("id"):
            raise Refused("Discord did not say who this token is")
        if not me.get("bot"):
            raise Refused("That is not a bot's token — Discord lets a tool listen only as a bot")
        name = str(me.get("username") or "bot")
        ref = logins.save(f"discord-{_slug(name)}", v["token"], "discord", name)
        return Verified(service, name, name, {"token": ref}, str(me["id"]))
    raise Refused(f"{service!r} cannot be added here yet")


def kept(service: str) -> list[Verified]:
    """The logins this machine already has for a service (step 1 is skipped with one of them)."""
    out = []
    if service == "gmail":
        for e in logins.listed("gmail"):
            out.append(Verified(service, e["account"], e["account"], {"password": logins.PREFIX + e["name"]}))
    elif service == "slack":
        for e in logins.listed("slack"):
            out.append(Verified(service, e["account"], e["account"], {"token": logins.PREFIX + e["name"]}, e["account"]))
    elif service in ("figma", "github", "discord"):
        for e in logins.listed(service):
            out.append(Verified(service, e["account"], e["account"], {"token": logins.PREFIX + e["name"]}))
    elif service == "gitlab":
        for e in logins.listed("gitlab"):
            out.append(Verified(service, e["account"], e["account"], {"token": logins.PREFIX + e["name"]}, e["account"]))
    elif service in ATLASSIAN:
        names = {e["name"] for e in logins.listed("atlassian")}
        for e in logins.listed("atlassian"):
            if not e["name"].endswith("-user") and f"{e['name']}-user" in names:
                out.append(Verified(service, e["account"], e["account"],
                                    {"user": f"{logins.PREFIX}{e['name']}-user", "token": logins.PREFIX + e["name"]},
                                    e["account"]))
    return out


# -- step 2: what to hear ---------------------------------------------------------------------------------

def origin(repo_root: Path, runner=subprocess.run) -> tuple[str, str]:
    """This project's `origin` as (host, path): ("github.com", "owner/repo"), or ("", "")."""
    try:
        out = runner(["git", "-C", str(repo_root), "remote", "get-url", "origin"], capture_output=True, text=True,
                     timeout=TIMEOUT_S)
    except (OSError, subprocess.SubprocessError):
        return "", ""
    url = (out.stdout or "").strip() if out.returncode == 0 else ""
    m = re.match(r"^(?:[\w.-]+@([\w.-]+):|ssh://[\w.-]+@([\w.-]+)(?::\d+)?/|https?://(?:[^@/]+@)?([\w.-]+)(?::\d+)?/)"
                 r"([\w.-]+(?:/[\w.-]+)+?)(?:\.git)?/?$", url)
    if not m:
        return "", ""
    return (m.group(1) or m.group(2) or m.group(3)).lower(), m.group(4).removesuffix(".git")


def origin_repo(repo_root: Path, runner=subprocess.run) -> str:
    """This project's GitHub repo (`owner/repo`) from its `origin`, or ""."""
    host, path = origin(repo_root, runner)
    return path if host == "github.com" and path.count("/") == 1 else ""


def options(login: Verified, opener=urllib.request.urlopen, runner=subprocess.run, repo_root: Path | None = None,
            files: list[str] | None = None) -> list[Option]:
    """What there is to pick for this login, the likely ones ticked."""
    service = login.service
    if service in ("github", "gitlab"):
        host, path = origin(repo_root, runner) if repo_root else ("", "")
        mine = path if host == (login.site or "github.com") else ""
        try:
            repos = _git_api(login, "user/repos?sort=pushed&per_page=100" if service == "github" else
                             "projects?membership=true&order_by=last_activity_at&per_page=50", opener, runner)
        except Refused:
            if not mine:                                  # nothing to offer: say why
                raise
            repos = []                                    # this project's own still offered, ticked
        if service == "github":
            found = [Option(r["full_name"], r["full_name"], str(r.get("pushed_at") or "")[:10], r["full_name"] == mine)
                     for r in repos or [] if isinstance(r, dict) and r.get("full_name")]
        else:
            found = [Option(r["path_with_namespace"], r["path_with_namespace"], str(r.get("last_activity_at") or "")[:10],
                            r["path_with_namespace"] == mine)
                     for r in repos or [] if isinstance(r, dict) and r.get("path_with_namespace")]
        if mine and not any(o.id == mine for o in found):
            found.insert(0, Option(mine, mine, "this project", True))
        return sorted(found, key=lambda o: (not o.picked, -int(re.sub(r"\D", "", o.meta) or 0)))
    if service == "discord":
        head = feeds_discord.head(logins.resolve(login.refs["token"]))
        found = []
        for g in _get(f"{feeds_discord.API}/users/@me/guilds", head, opener) or []:
            chans = _get(f"{feeds_discord.API}/guilds/{g.get('id')}/channels", head, opener) or []
            found += [Option(str(c["id"]), f"{g.get('name', '?')} · #{c.get('name', c['id'])}")
                      for c in sorted(chans, key=lambda c: c.get("position", 0))
                      if isinstance(c, dict) and c.get("id") and c.get("type") in feeds_discord.TEXT_CHANNELS]
        return found
    if service == "slack":
        head = {"Authorization": f"Bearer {logins.resolve(login.refs['token'])}"}
        data = _get("https://slack.com/api/users.conversations?" + urllib.parse.urlencode(
            {"types": "public_channel,private_channel", "exclude_archived": "true", "limit": LIST_MAX}), head, opener)
        if not isinstance(data, dict) or not data.get("ok"):
            raise Refused(f"Slack would not list the channels: {(data or {}).get('error', 'no answer')}")
        return sorted((Option(c["id"], f"#{c.get('name', c['id'])}", "private" if c.get("is_private") else "")
                       for c in data.get("channels") or [] if c.get("id")), key=lambda o: o.label)
    if service in ATLASSIAN:
        head = _basic(logins.resolve(login.refs["user"]), logins.resolve(login.refs["token"]))
        if service == "jira":
            data = _get(f"https://{login.site}/rest/api/3/project/search?maxResults=50&orderBy=-lastIssueUpdatedTime",
                        head, opener)
            return [Option(p["key"], f"{p['key']} · {p.get('name', '')}") for p in (data or {}).get("values") or []
                    if isinstance(p, dict) and p.get("key")]
        data = _get(f"https://{login.site}/wiki/api/v2/spaces?limit=50", head, opener)
        return [Option(s["key"], f"{s['key']} · {s.get('name', '')}") for s in (data or {}).get("results") or []
                if isinstance(s, dict) and s.get("key")]
    if service == "figma":
        head = {"X-Figma-Token": logins.resolve(login.refs["token"])}
        out: list[Option] = []
        for key in files or []:
            if key.startswith("team:"):
                for p in (_get(f"https://api.figma.com/v1/teams/{key[5:]}/projects", head, opener) or {}).get("projects") or []:
                    for f in (_get(f"https://api.figma.com/v1/projects/{p.get('id')}/files", head, opener) or {}).get("files") or []:
                        out.append(Option(f["key"], f.get("name", f["key"]), str(f.get("last_modified", ""))[:10]))
            else:
                out.append(Option(key, key, "from the link", True))
        return out
    return []


# -- what it makes ----------------------------------------------------------------------------------------

ALL_MAIL = "[Gmail]/All Mail"


def plan(login: Verified, picks: list[str], about_me: bool = True, folder: str = "INBOX", me: str = "",
         everything: bool = False, guilds: tuple[str, ...] = ()) -> Plan:
    """The settings the picks make, and what the tower will hear, in words. `everything`: the whole
    service at once (§6) — the picks are not needed then; Discord's takes the servers the bot is in."""
    service, picks = login.service, [p for p in picks if re.fullmatch(r"[A-Za-z0-9_.:/-]{1,120}", p)]
    token = f" token={login.refs['token']}" if login.refs.get("token") else ""
    if everything:
        whole = _everything(login, picks, me, guilds, token)
        if whole is not None:
            return whole
    if service in ("github", "gitlab"):
        pattern, what = (feeds.REPOS, "repos") if service == "github" else (feeds.PATHS, "projects")
        picks = [p for p in picks if pattern.match(p)]
        if not picks and not about_me:
            raise Refused("Pick a repo, or keep your notifications" if service == "github" else
                          "Pick a project, or keep your to-dos")
        line = f"{service}:" + (f" host={login.site}" if service == "gitlab" else "") + token + \
            (f" {what}={','.join(picks)}" if picks else "") + \
            (f" {'notifications' if service == 'github' else 'todos'}=on" if about_me else "")
        says = [x for x in (("your notifications" if service == "github" else "your to-dos") if about_me else "",
                            f"the events of {', '.join(picks)}" if picks else "") if x]
        return Plan({}, " and ".join(says), line.replace(":  ", ": "))
    if service == "discord":
        picks = [p for p in picks if p.isdigit()]
        if not picks:
            raise Refused("Pick a channel — invite the bot first if the list is empty")
        if me and not me.isdigit():
            raise Refused("Me is your Discord user id — digits, or a link to a message you wrote")
        line = f"discord:{token} channels={','.join(picks)}" + (f" me={me}" if me else "")
        return Plan({}, f"{len(picks)} channel(s)" + (", mentions of you told" if me else ""), line)
    if service == "gmail":
        folder = (folder or "INBOX").strip()[:100]
        return Plan({"host": "gmail", "user": login.account, "user_env": None, "password_env": login.refs["password"],
                     "folder": folder}, f"new mail in {login.account} · {folder}")
    if service == "slack":
        if not about_me and not picks:
            raise Refused("Pick a channel, or keep mentions and DMs")
        line = f"slack: token={login.refs['token']}" + (f" channels={','.join(picks)}" if picks else "")
        return Plan({}, "mentions and DMs" + (f" and {len(picks)} channel(s)" if picks else ""), line)
    if service in ATLASSIAN:
        line = f"{service}: site={login.site} user={login.refs['user']} token={login.refs['token']}"
        if service == "jira":
            if picks:
                keys = ", ".join(picks)
                line += f" jql={feeds.JIRA_JQL} OR project in ({keys})" if about_me else f" jql=project in ({keys})"
            says = [x for x in ("comments on issues about you" if about_me or not picks else "",
                                (f"comments in {', '.join(picks)}" if picks else "")) if x]
            return Plan({}, " and ".join(says), line)
        if picks:
            line += f" spaces={','.join(picks)}"
        return Plan({}, "mentions of you" + (f" and comments in {', '.join(picks)}" if picks else ""), line)
    if service == "figma":
        if not picks:
            raise Refused("Paste a Figma file link, or pick a file")
        return Plan({}, f"comments in {len(picks)} file(s)", f"figma: token={login.refs['token']} files={','.join(picks)}")
    raise Refused(f"{service!r} cannot be added here yet")


def _everything(login: Verified, picks: list[str], me: str, guilds: tuple[str, ...], token: str) -> Plan | None:
    """The whole service as one line (docs/design/watchtower-quick-add.md §6); None: it has no Everything."""
    service = login.service
    if service == "github":
        repos = [p for p in picks if feeds.REPOS.match(p)]
        return Plan({}, "every notification, the repos you watch too" + (f", and the events of {', '.join(repos)}"
                                                                           if repos else ""),
                    f"github:{token}" + (f" repos={','.join(repos)}" if repos else "") + " notifications=all")
    if service == "slack":
        return Plan({}, "every message you can see", f"slack: token={login.refs['token']} everything=on")
    if service in ATLASSIAN:
        line = f"{service}: site={login.site} user={login.refs['user']} token={login.refs['token']}"
        if service == "jira":
            return Plan({}, f"new comments on every issue of {login.site}", f"{line} jql={feeds.EVERYTHING_JQL}")
        return Plan({}, f"every new page and comment of {login.site}", f"{line} cql={feeds.EVERYTHING_CQL}")
    if service == "discord":
        ids = [g for g in guilds if g.isdigit()]
        if not ids:
            raise Refused("The bot is in no server yet — invite it, then List again")
        if me and not me.isdigit():
            raise Refused("Me is your Discord user id — digits, or a link to a message you wrote")
        return Plan({}, f"every channel of {len(ids)} server(s)" + (", mentions of you told" if me else ""),
                    f"discord:{token} guilds={','.join(ids)}" + (f" me={me}" if me else ""))
    if service == "gmail":
        return Plan({"host": "gmail", "user": login.account, "user_env": None, "password_env": login.refs["password"],
                     "folder": ALL_MAIL}, f"new mail in {login.account} · the whole mailbox")
    return None


def with_feed(current: list, line: str) -> list[str]:
    """The `feeds` setting with `line` in: it replaces a line that asks the same service as the same login."""
    new, _ = feeds.parse(line)
    out = [str(x) for x in current or []]
    if new is not None:
        out = [x for x in out if (feeds.parse(x)[0] or new).identity != new.identity or x == line]
    return out if line in out else out + [line]


def first_look(login: Verified, p: Plan, opener=urllib.request.urlopen, runner=subprocess.run,
               imap_factory=imaplib.IMAP4_SSL) -> tuple[int, str]:
    """The look the tower will make, made now: (what is there now, why it failed or "")."""
    if p.feed:
        feed, err = feeds.parse(p.feed)
        if feed is None:
            return 0, err
        got = feeds.look(feed, opener, runner)
        return len(got.items), got.error
    if login.service == "gmail":
        got = mailbox.look(p.changes, imap_factory)
        return got.unread, got.error
    if login.service == "github":
        _, _, err = watch.github_events(p.changes["github"], "", runner)
        return -1, err
    return 0, ""


# -- Discord: the invite, and who "me" is ------------------------------------------------------------------

def discord_invite(login: Verified) -> str:
    """The link that adds the bot to a server, allowed to read and nothing else ("" without its id)."""
    return feeds_discord.invite(login.site) if login.site.isdigit() else ""


def discord_bot(login: Verified, opener=urllib.request.urlopen) -> Verified:
    """A kept bot login with its id (the Logins file keeps the name only): `/users/@me` once."""
    if login.site.isdigit():
        return login
    me = _get(f"{feeds_discord.API}/users/@me", feeds_discord.head(logins.resolve(login.refs["token"])), opener)
    return Verified(login.service, login.who, login.account, login.refs, str((me or {}).get("id") or ""))


def discord_guilds(login: Verified, opener=urllib.request.urlopen) -> tuple[str, ...]:
    """The servers the bot is in: Everything listens to all of them."""
    found = _get(f"{feeds_discord.API}/users/@me/guilds", feeds_discord.head(logins.resolve(login.refs["token"])), opener)
    return tuple(str(g["id"]) for g in found or [] if isinstance(g, dict) and g.get("id"))


def discord_me(login: Verified, text: str, opener=urllib.request.urlopen) -> str:
    """The person's Discord user id from what they typed: the id, `<@id>`, or a link to a message they wrote."""
    text = (text or "").strip()
    if not text:
        return ""
    m = re.fullmatch(r"<@!?(\d{1,25})>|(\d{1,25})", text)
    if m:
        return m.group(1) or m.group(2)
    link = re.search(r"discord(?:app)?\.com/channels/(?:\d+|@me)/(\d+)/(\d+)", text)
    if not link:
        raise Refused("Me is your Discord user id — digits, or a link to a message you wrote")
    msg = _get(f"{feeds_discord.API}/channels/{link.group(1)}/messages/{link.group(2)}",
               feeds_discord.head(logins.resolve(login.refs["token"])), opener)
    who = str(((msg or {}).get("author") or {}).get("id") or "") if isinstance(msg, dict) else ""
    if not who:
        raise Refused("That message did not say who wrote it")
    return who


# -- a source already listed, back into the steps -----------------------------------------------------------

@dataclass
class Source:
    """A listed source as the steps take it again: the login it uses, what it hears, its switches."""
    login: Verified
    picks: list[str] = field(default_factory=list)
    about_me: bool = True
    folder: str = "INBOX"
    me: str = ""
    everything: bool = False


PICKS = {"slack": "channels", "confluence": "spaces", "figma": "files", "github": "repos", "gitlab": "projects",
         "discord": "channels"}


def from_source(config: dict, source: str) -> Source:
    """`mail`, `github` (the old one-repo setting) or `feed:<line>` as the steps' login and picks.
    Raises Refused for a source the steps cannot make again (a schedule, a webhook, an own query)."""
    if source == "mail":
        if str(config.get("host") or "").lower() != "gmail":
            raise Refused("This mailbox is not Gmail — change it in the building's settings")
        user = str(config.get("user") or "") or logins.resolve(str(config.get("user_env") or ""))
        folder = str(config.get("folder") or "INBOX")
        return Source(Verified("gmail", user, user, {"password": str(config.get("password_env") or "")}),
                      folder=folder, everything=folder == ALL_MAIL)
    if source == "github":
        return Source(Verified("github", "gh", "gh"), [str(config.get("github") or "")], about_me=False)
    feed, err = feeds.parse(source.removeprefix("feed:")) if source.startswith("feed:") else (None, "")
    if feed is None or feed.kind not in SERVICES:
        raise Refused(err or f"{source!r} cannot be changed here — change it in the building's settings")
    o = feed.opts
    if not feed.poll:
        raise Refused("This line only listens to a webhook — change it in the building's settings")
    everything = (feed.kind == "slack" and feed.on("everything") or o.get("notifications") == "all"
                  or o.get("jql") == feeds.EVERYTHING_JQL or o.get("cql") == feeds.EVERYTHING_CQL or bool(o.get("guilds")))
    if not everything and (o.get("cql") or (o.get("jql") and feeds.JIRA_JQL not in o["jql"] and not re.fullmatch(
            r"project in \([A-Z0-9_, ]+\)", o["jql"]))):
        raise Refused("This line asks its own query — change it in the building's settings")
    refs = {k: o[k] for k in ("token", "user") if o.get(k)}
    site = o.get("site") or (feed.host if feed.kind == "gitlab" else "")
    account = site or (o["token"][len(logins.PREFIX):] if logins.is_ref(o.get("token", "")) else feed.kind)
    picks = feed.ids(PICKS[feed.kind]) if feed.kind in PICKS else []
    keys = re.search(r"project in \(([^)]*)\)", o.get("jql", ""))
    if feed.kind == "jira" and keys:
        picks = [k.strip() for k in keys.group(1).split(",") if k.strip()]
    about_me = {"github": feed.on("notifications"), "gitlab": feed.on("todos"),
                "jira": not o.get("jql") or feeds.JIRA_JQL in o["jql"] or everything}.get(feed.kind, True)
    return Source(Verified(feed.kind, account, account, refs, site), picks, about_me, me=o.get("me", ""),
                  everything=everything)
