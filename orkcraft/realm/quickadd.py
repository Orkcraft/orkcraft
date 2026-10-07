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

from orkcraft.realm import feeds, logins, mailbox, sources_link, watch

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


@dataclass(frozen=True)
class Service:
    id: str
    label: str
    fields: tuple[Field, ...] = ()
    how: tuple[tuple[str, str], ...] = ()       # (what to do, a link) — the clicks before the paste
    picks: str = ""                             # what step 2 lists: repos, channels, projects, spaces, files
    about_me: str = ""                          # the "about me" switch, on by default, when the service has one
    note: str = ""


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

SERVICES: dict[str, Service] = {s.id: s for s in (
    Service("github", "GitHub", picks="repos",
            note="Uses the gh command's login: nothing to paste. Not logged in? Run `gh auth login` in a terminal."),
    Service("gmail", "Gmail",
            (Field("email", "Your Gmail address", placeholder="you@gmail.com"),
             Field("password", "App password", True, "16 letters", r"^[a-zA-Z]{4}( ?[a-zA-Z]{4}){3}$",
                   "an app password is 16 letters")),
            (("Turn on 2-Step Verification, if it is off", "https://myaccount.google.com/signinoptions/twosv"),
             ("Create an app password (any name) and copy its 16 letters", "https://myaccount.google.com/apppasswords")),
            note="Read-only: the tower never marks mail read in the mailbox."),
    Service("slack", "Slack",
            (Field("token", "User OAuth Token", True, "xoxp-…", r"^xoxp-\S+$", "a user token starts with xoxp-"),),
            (("Create the app — Slack opens with it filled in; pick the workspace, Create", SLACK_NEW_APP),
             ("Install it: Install to Workspace → Allow", ""),
             ("On OAuth & Permissions, copy the User OAuth Token (xoxp-…)", "")),
            picks="channels", about_me="Mentions and direct messages"),
    Service("jira", "Jira", (ATL_SITE, ATL_EMAIL, ATL_TOKEN), ATL_HOW, picks="projects",
            about_me="Issues I watch, am assigned or reported"),
    Service("confluence", "Confluence", (ATL_SITE, ATL_EMAIL, ATL_TOKEN), ATL_HOW, picks="spaces",
            about_me="Pages and comments that mention me"),
    Service("figma", "Figma",
            (Field("token", "Personal access token", True, "figd_…", r"^figd_\S+$", "a Figma token starts with figd_"),),
            (("Settings → Security → Generate new token; allow reading comments and files", "https://www.figma.com/settings"),),
            picks="files"),
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
    v = {k: str(values.get(k) or "").strip() for k in ("site", "email", "token", "password")}
    if service == "github":
        who = gh_login(runner)
        if not who:
            raise Refused("gh is not logged in — run `gh auth login` in a terminal, then Check again")
        return Verified(service, who, who)
    for f in s.fields:
        if not v.get(f.key):
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
    elif service == "figma":
        for e in logins.listed("figma"):
            out.append(Verified(service, e["account"], e["account"], {"token": logins.PREFIX + e["name"]}))
    elif service in ATLASSIAN:
        names = {e["name"] for e in logins.listed("atlassian")}
        for e in logins.listed("atlassian"):
            if not e["name"].endswith("-user") and f"{e['name']}-user" in names:
                out.append(Verified(service, e["account"], e["account"],
                                    {"user": f"{logins.PREFIX}{e['name']}-user", "token": logins.PREFIX + e["name"]},
                                    e["account"]))
    return out


# -- step 2: what to hear ---------------------------------------------------------------------------------

def origin_repo(repo_root: Path, runner=subprocess.run) -> str:
    """This project's GitHub repo (`owner/repo`) from its `origin`, or ""."""
    try:
        out = runner(["git", "-C", str(repo_root), "remote", "get-url", "origin"], capture_output=True, text=True,
                     timeout=TIMEOUT_S)
    except (OSError, subprocess.SubprocessError):
        return ""
    url = (out.stdout or "").strip() if out.returncode == 0 else ""
    m = re.match(r"^(?:git@github\.com:|ssh://git@github\.com/)([^/]+/[^/]+?)(?:\.git)?/?$", url)
    if m:
        return m.group(1)
    link = sources_link.recognise(url)
    return link.target if link and link.service == "github" else ""


def options(login: Verified, opener=urllib.request.urlopen, runner=subprocess.run, repo_root: Path | None = None,
            files: list[str] | None = None) -> list[Option]:
    """What there is to pick for this login, the likely ones ticked."""
    service = login.service
    if service == "github":
        mine = origin_repo(repo_root, runner) if repo_root else ""
        try:
            out = _run(runner, ["gh", "repo", "list", "--json", "nameWithOwner,pushedAt", "--limit", "50"])
            repos = json.loads(out.stdout or "[]") if out.returncode == 0 else []
        except (OSError, subprocess.SubprocessError, ValueError):
            repos = []
        found = [Option(r["nameWithOwner"], r["nameWithOwner"], str(r.get("pushedAt") or "")[:10],
                        r["nameWithOwner"] == mine) for r in repos if isinstance(r, dict) and r.get("nameWithOwner")]
        if mine and not any(o.id == mine for o in found):
            found.insert(0, Option(mine, mine, "this project", True))
        return sorted(found, key=lambda o: (not o.picked, -int(re.sub(r"\D", "", o.meta) or 0)))
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

def plan(login: Verified, picks: list[str], about_me: bool = True, folder: str = "INBOX") -> Plan:
    """The settings the picks make, and what the tower will hear, in words."""
    service, picks = login.service, [p for p in picks if re.fullmatch(r"[A-Za-z0-9_.:/-]{1,120}", p)]
    if service == "github":
        if len(picks) != 1:
            raise Refused("Pick one repo — the tower hears one GitHub repo for now")
        return Plan({"github": picks[0]}, f"the events of {picks[0]}")
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
        got = feeds.look(feed, opener)
        return len(got.items), got.error
    if login.service == "gmail":
        got = mailbox.look(p.changes, imap_factory)
        return got.unread, got.error
    if login.service == "github":
        _, _, err = watch.github_events(p.changes["github"], "", runner)
        return -1, err
    return 0, ""
