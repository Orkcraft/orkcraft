"""🗼 The Watchtower's feeds: comments and mentions in Slack, Jira, Confluence, Figma, GitHub, GitLab and Discord.

These services push their webhooks only to a public URL, and the Watchtower listens on 127.0.0.1
alone, so it asks them instead: every two minutes, read-only, through their REST APIs. One line of
the `feeds` setting is one feed; a line names the environment variables that hold the login, never
the token itself (the Town Hall's Warder flags a spec that does) — or a login kept on this machine,
`token=keychain:slack-acme` (realm/logins.py: what the Watchtower's Add a source saves):

    slack: token=SLACK_TOKEN channels=C0123,D0456
        mentions of you (search.messages, a user token with search:read) and the new messages in
        the channels listed (conversations.history); a message in a direct channel (D…) is a mention.
        `everything=on`: every message the person can see, by search (`after:` yesterday)
    jira: site=acme.atlassian.net user=ATL_EMAIL token=ATL_TOKEN jql=project = WEB
        new comments on the issues you watch, are assigned or reported (or what `jql=` picks — it
        takes the rest of the line); a comment that @-mentions you is a mention
    confluence: site=acme.atlassian.net user=ATL_EMAIL token=ATL_TOKEN spaces=DOC,ENG
        pages and comments that mention you (CQL `mention = currentUser()`), and new comments in
        the spaces listed (or what `cql=` picks — it takes the rest of the line)
    figma: token=FIGMA_TOKEN files=AbC123,XyZ789
        new comments in the files listed; one that @-mentions you or answers yours is a mention
    github: repos=owner/app,owner/api notifications=on
        your notifications (review requests, mentions, assignments, threads you are in — all mentions)
        and the events of the repos listed; `gh`'s login, or `token=` (realm/feeds_git.py)
    gitlab: host=gitlab.com token=GITLAB_TOKEN projects=group/app todos=on
        your to-dos (mentions) and the events of the projects listed (realm/feeds_git.py)
    discord: token=DISCORD_BOT_TOKEN channels=123,456 me=789
        new messages in the channels a bot you invited can see; one that mentions you (`me=`, your
        user id) or the bot, or answers you, is a mention (realm/feeds_discord.py)
    agent: tool=claude server=atlassian tools=searchJiraIssuesUsingJql every=30m ask=new comments in Jira
        the person's own connector, asked by a headless Claude allowed only those read-only tools;
        `ask=` takes the rest of the line (realm/feeds_agent.py)

A look that fails says which of three it is (`Look.kind`), so the fix is one button: `login` (the
token was refused or is gone — log in again), `target` (a channel, repo or file is gone or out of
reach — edit what it hears) or `network` (it could not get through — it tries again by itself).

Every feed's first look only marks what is there as seen; from then on each new item is one
signal, `watch.mention` when it is about you, else `watch.comment`. Your own messages are skipped.

`secret=ENV` on a line lets the same service push to the Watchtower's webhook (realm/inbound.py):
Slack's signing secret, Figma's passcode, Jira's webhook secret, the token of an Automation rule.
A line with only `secret=` listens and never asks (`slack: secret=SLACK_SIGNING_SECRET`).
"""
from __future__ import annotations

import base64
import datetime as dt
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

from orkcraft.realm import logins

TIMEOUT_S = 15
LOOK = 20                       # items a feed asks for per look
SEEN_KEEP = 500                 # keys a feed remembers
BODY = 1500

KINDS = {                       # kind: (required options, optional options, the option that takes the rest)
    "slack": (("token",), ("channels", "secret", "everything"), ""),
    "jira": (("site", "user", "token"), ("jql", "secret"), "jql"),
    "confluence": (("site", "user", "token"), ("spaces", "secret", "cql"), "cql"),
    "figma": (("token", "files"), ("secret",), ""),
    "github": ((), ("repos", "notifications", "token"), ""),
    "gitlab": ((), ("host", "token", "projects", "todos"), ""),
    "discord": (("token",), ("channels", "guilds", "me"), ""),
    "agent": (("server", "tools"), ("tool", "every", "ceiling"), "ask"),
}
ICON = {"slack": "💬", "jira": "🎫", "confluence": "📘", "figma": "🎨", "github": "🐙", "gitlab": "🦊", "discord": "🎮",
        "agent": "🤖"}
HOST = {"slack": "slack.com", "figma": "api.figma.com", "github": "api.github.com", "discord": "discord.com"}
FAILS = ("login", "target", "network")          # what a failed look says to do: log in again, edit, wait
ENV_NAME = re.compile(r"^[A-Z][A-Z0-9_]{1,63}$")
SITE = re.compile(r"^[a-z0-9][a-z0-9.-]*\.[a-z]{2,}$")
IDS = re.compile(r"^[A-Za-z0-9_-]+(,[A-Za-z0-9_-]+)*$")
PATH = r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+"
PATHS = re.compile(rf"^{PATH}(,{PATH})*$")      # GitLab's group/sub/project, GitHub's owner/repo
REPOS = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(,[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)*$")
SWITCH = ("on", "off")
EVERYTHING_JQL = "updated >= -1d"                      # Jira's Everything: every issue of the site (§6)
EVERYTHING_CQL = "type in (page, blogpost, comment)"   # Confluence's
SLACK_NAMES: dict[str, str] = {}     # user id → name, for the app's life
SLACK_LOGIN = ("invalid_auth", "not_authed", "token_revoked", "token_expired", "account_inactive", "missing_scope",
               "no_permission")
SLACK_TARGET = ("channel_not_found", "not_in_channel", "is_archived")
JIRA_JQL = "watcher = currentUser() OR assignee = currentUser() OR reporter = currentUser()"


@dataclass
class Feed:
    kind: str
    opts: dict[str, str]
    line: str                    # the setting as written: the key of what this feed has seen
    poll: bool = True            # False: only `secret=` — it listens to the webhook, never asks

    def env(self, name: str) -> str:
        """What option `name` names: an environment variable's value, or a login's (`keychain:…`)."""
        return logins.resolve(self.opts.get(name, ""))

    def missing(self, name: str, what: str) -> str:
        """Why option `name` gave nothing: the variable to set, or the login to make again."""
        ref = self.opts.get(name, "")
        return (f"{self.kind}: the login {ref[len(logins.PREFIX):]} is gone — log in again" if logins.is_ref(ref)
                else f"{self.kind}: set {ref} in the environment ({what})")

    @property
    def identity(self) -> str:
        """Who is asked and as whom: what it has seen survives a change of channels, files or query."""
        if self.kind == "agent":                 # no login of its own: the server and the ask say who
            return "|".join(["agent", self.opts.get("server", ""), self.opts.get("ask", "")])
        site = self.opts.get("site", "") or (self.host if self.kind == "gitlab" else "")
        return "|".join([self.kind, site] + [self.opts.get(k, "") for k in ("user", "token")])

    @property
    def host(self) -> str:
        """The host a look goes to: what `could not reach` names."""
        return self.opts.get("site") or self.opts.get("host") or HOST.get(self.kind, "gitlab.com")

    def on(self, name: str) -> bool:
        return self.opts.get(name, "off") in ("on", "all")

    def ids(self, name: str) -> list[str]:
        return [x for x in self.opts.get(name, "").split(",") if x]


@dataclass
class Item:
    key: str                     # stable: what makes "seen"
    title: str
    body: str = ""
    url: str = ""
    at: str = ""
    mention: bool = False


@dataclass
class Look:
    items: list[Item] = field(default_factory=list)      # oldest first
    error: str = ""
    me: dict = field(default_factory=dict)                 # who you are there: webhooks tell mentions by it
    kind: str = ""                                         # when it failed: login | target | network (FAILS)
    cost: float | None = None                              # what a look through a model cost (feeds_agent.py)


class Failed(Exception):
    """A look that cannot go on, and which of the three failures it is."""

    def __init__(self, text: str, kind: str = "network") -> None:
        super().__init__(text)
        self.kind = kind if kind in FAILS else "network"


def fail_kind(status: int) -> str:
    """An HTTP status as the failure it is: 401/403 the login, 400/404/410 a target, the rest the network."""
    return "login" if status in (401, 403) else "target" if status in (400, 404, 410) else "network"


# -- the setting ----------------------------------------------------------------------------------------

def parse(line: str) -> tuple[Feed | None, str]:
    """(the feed, "") or (None, what is wrong with the line)."""
    m = re.fullmatch(r"\s*([a-z]+)\s*:\s*(.*?)\s*", line or "", re.S)
    if not m or m.group(1) not in KINDS:
        return None, f"{line.strip()[:40]!r}: start with {', '.join(k + ':' for k in KINDS)}"
    kind, rest = m.group(1), m.group(2)
    required, optional, tail = KINDS[kind]
    opts: dict[str, str] = {}
    if tail and f"{tail}=" in rest:
        rest, opts[tail] = rest.split(f"{tail}=", 1)
        opts[tail] = opts[tail].strip()
    for word in rest.split():
        k, eq, v = word.partition("=")
        if not eq or k not in required + optional or k == tail:
            return None, f"{kind}: {word!r} — it takes {', '.join(o + '=' for o in required + optional)}"
        opts[k] = v
    missing = [k for k in required if not opts.get(k)]
    if missing and (not opts.get("secret") or len(missing) < len(required)):
        return None, f"{kind}: set {', '.join(k + '=' for k in missing)}"
    for k in ("token", "user", "secret"):
        if k in opts and not logins.is_name(opts[k]):
            return None, f"{kind}: {k}= names an environment variable (like ATL_TOKEN) or a login, not the value"
    if "site" in opts:
        opts["site"] = opts["site"].removeprefix("https://").rstrip("/")
        if not SITE.match(opts["site"]):
            return None, f"{kind}: site= is a host name, like acme.atlassian.net"
    for k in ("channels", "files", "spaces", "guilds"):
        if k in opts and not IDS.match(opts[k]):
            return None, f"{kind}: {k}= is a comma-separated list of ids"
    if "repos" in opts and not REPOS.match(opts["repos"]):
        return None, f"{kind}: repos= is a comma-separated list of owner/repo"
    if "projects" in opts and not PATHS.match(opts["projects"]):
        return None, f"{kind}: projects= is a comma-separated list of group/project"
    if "host" in opts:
        opts["host"] = opts["host"].removeprefix("https://").rstrip("/")
        if not SITE.match(opts["host"]):
            return None, f"{kind}: host= is a host name, like gitlab.com"
    for k in ("notifications", "todos", "everything"):
        if k in opts and opts[k] not in SWITCH + (("all",) if k == "notifications" else ()):
            return None, f"{kind}: {k}= is on or off" + (" (or all)" if k == "notifications" else "")
    if kind == "github" and not (opts.get("repos") or opts.get("notifications") in ("on", "all")):
        return None, "github: set repos= or notifications=on"
    if kind == "discord" and not (opts.get("channels") or opts.get("guilds")):
        return None, "discord: set channels= (or guilds= for every channel of a server)"
    if kind == "gitlab" and not (opts.get("projects") or opts.get("todos") == "on"):
        return None, "gitlab: set projects= or todos=on"
    if kind == "agent":
        if opts.get("tool", "claude") not in ("claude", "agy"):
            return None, "agent: tool= is claude or agy"
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", opts.get("server", "")):
            return None, "agent: server= is the MCP server's name, like atlassian"
        if not all(re.fullmatch(r"[A-Za-z0-9_.-]{1,120}", t) for t in opts["tools"].split(",")):
            return None, "agent: tools= is a comma-separated list of the server's read-only tools"
        if opts.get("every") and not re.fullmatch(r"\d{1,4}m?", opts["every"]):
            return None, "agent: every= is minutes, like 30m"
        if opts.get("ceiling") and not re.fullmatch(r"\d{1,4}(\.\d{1,2})?", opts["ceiling"]):
            return None, "agent: ceiling= is dollars a day, like 0.50"
    if kind == "discord" and opts.get("me") and not opts["me"].isdigit():
        return None, "discord: me= is your user id (digits)"
    return Feed(kind, opts, line.strip(), poll=not missing), ""


def check(lines: list[str]) -> list[str]:
    return [err for err in (parse(x)[1] for x in lines) if err]


# -- HTTP -----------------------------------------------------------------------------------------------

def get_json(url: str, headers: dict, opener=urllib.request.urlopen):
    req = urllib.request.Request(url, headers={"User-Agent": "orkcraft-watchtower", "Accept": "application/json",
                                               **headers})
    with opener(req, timeout=TIMEOUT_S) as r:
        return json.loads(r.read().decode("utf-8", errors="replace") or "null")


def _short(text: str, n: int = 90) -> str:
    one = re.sub(r"\s+", " ", text or "").strip()
    return one if len(one) <= n else one[:n - 1] + "…"


def _iso(value) -> str:
    """Slack's epoch, Atlassian's `…+0000` and Figma's `…Z` as one local-free ISO text."""
    try:
        if isinstance(value, (int, float)) or re.fullmatch(r"\d+(\.\d+)?", str(value or "")):
            return dt.datetime.fromtimestamp(float(value), dt.timezone.utc).isoformat(timespec="seconds")
        return dt.datetime.fromisoformat(re.sub(r"([+-]\d\d)(\d\d)$", r"\1:\2", str(value).replace("Z", "+00:00"))
                                         ).isoformat(timespec="seconds")
    except (TypeError, ValueError, OverflowError):
        return ""


# -- Slack ----------------------------------------------------------------------------------------------

def slack(feed: Feed, opener=urllib.request.urlopen) -> Look:
    token = feed.env("token")
    if not token:
        return Look(error=feed.missing("token", "a user token, xoxp-…"), kind="login")
    head = {"Authorization": f"Bearer {token}"}

    def call(method: str, **params) -> dict:
        data = get_json(f"https://slack.com/api/{method}?{urllib.parse.urlencode(params)}", head, opener)
        if not (data or {}).get("ok"):
            why = (data or {}).get("error", "no answer")
            if why in SLACK_TARGET:
                raise Failed(f"slack: {params.get('channel', '?')} is gone or the app was removed from it ({why})",
                             "target")
            raise Failed(f"slack: {method}: {why}" + (" — log in again" if why in SLACK_LOGIN else ""),
                         "login" if why in SLACK_LOGIN else "network")
        return data

    me = call("auth.test")
    uid, team = me.get("user_id", ""), str(me.get("url", "")).rstrip("/")

    def name(user: str) -> str:
        """users.info (users:read) once per person; without the scope, the id."""
        if user and user not in SLACK_NAMES:
            try:
                u = call("users.info", user=user).get("user") or {}
                SLACK_NAMES[user] = (u.get("profile") or {}).get("display_name") or u.get("real_name") or u.get("name") or user
            except (OSError, ValueError, Failed):
                SLACK_NAMES[user] = user
        return SLACK_NAMES.get(user, user or "?")

    def plain(text: str) -> str:
        return re.sub(r"<@([A-Z0-9]+)>", lambda m: "@you" if m.group(1) == uid else f"@{name(m.group(1))}", text or "")

    items: dict[str, Item] = {}
    for m in (call("search.messages", query=f"<@{uid}>", sort="timestamp", sort_dir="desc", count=LOOK)
              .get("messages") or {}).get("matches") or []:
        ch = m.get("channel") or {}
        if m.get("user") == uid:
            continue
        key = f"{ch.get('id', '')}:{m.get('ts', '')}"
        text = plain(m.get("text", ""))
        items[key] = Item(key, f"@ {m.get('username') or name(m.get('user', ''))} in #{ch.get('name', '?')}: "
                               f"{_short(text, 60)}", text[:BODY], m.get("permalink", ""),
                          _iso(m.get("ts")), mention=True)
    if feed.on("everything"):          # every channel the person can see: search, no channel list (§6)
        since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)).strftime("%Y-%m-%d")
        for m in (call("search.messages", query=f"after:{since}", sort="timestamp", sort_dir="desc", count=LOOK)
                  .get("messages") or {}).get("matches") or []:
            ch = m.get("channel") or {}
            key = f"{ch.get('id', '')}:{m.get('ts', '')}"
            if m.get("user") == uid or key in items:
                continue
            direct = bool(ch.get("is_im")) or str(ch.get("id", "")).startswith("D") or f"<@{uid}>" in m.get("text", "")
            text = plain(m.get("text", ""))
            where = "a direct message" if ch.get("is_im") else f"#{ch.get('name', '?')}"
            items[key] = Item(key, f"{'@ ' if direct else ''}{m.get('username') or name(m.get('user', ''))} in {where}: "
                                   f"{_short(text, 60)}", text[:BODY], m.get("permalink", ""), _iso(m.get("ts")),
                              mention=direct)
    oldest = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)).timestamp()
    for ch in feed.ids("channels"):
        for m in call("conversations.history", channel=ch, oldest=f"{oldest:.0f}", limit=LOOK).get("messages") or []:
            key = f"{ch}:{m.get('ts', '')}"
            if m.get("user") == uid or key in items or m.get("subtype") in ("channel_join", "channel_leave"):
                continue
            direct = ch.startswith("D") or f"<@{uid}>" in m.get("text", "")
            text = plain(m.get("text", ""))
            url = f"{team}/archives/{ch}/p{str(m.get('ts', '')).replace('.', '')}" if team else ""
            items[key] = Item(key, f"{'@ ' if direct else ''}{name(m.get('user', ''))} in {ch}: {_short(text, 60)}",
                              text[:BODY], url, _iso(m.get("ts")), mention=direct)
    return Look(sorted(items.values(), key=lambda i: i.at), me={"id": uid})


# -- Atlassian: Jira and Confluence -----------------------------------------------------------------------

def _atlassian(feed: Feed) -> dict | str:
    user, token = feed.env("user"), feed.env("token")
    for k, v in (("user", user), ("token", token)):
        if not v:
            return feed.missing(k, "your e-mail and an API token")
    return {"Authorization": "Basic " + base64.b64encode(f"{user}:{token}".encode()).decode()}


def adf_text(node) -> str:
    """The plain text of Atlassian's document format (mentions as their @name)."""
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return "".join(adf_text(n) for n in node)
    if not isinstance(node, dict):
        return ""
    if node.get("type") == "text":
        return node.get("text", "")
    if node.get("type") == "mention":
        return (node.get("attrs") or {}).get("text") or "@someone"
    inner = adf_text(node.get("content") or [])
    return inner + "\n" if node.get("type") in ("paragraph", "heading", "listItem", "codeBlock") else inner


def jira(feed: Feed, opener=urllib.request.urlopen) -> Look:
    head = _atlassian(feed)
    if isinstance(head, str):
        return Look(error=head, kind="login")
    base = f"https://{feed.opts['site']}"
    me = get_json(f"{base}/rest/api/3/myself", head, opener).get("accountId", "")
    jql = f"({feed.opts.get('jql') or JIRA_JQL}) AND updated >= -2d ORDER BY updated DESC"
    found = get_json(f"{base}/rest/api/3/search/jql?" + urllib.parse.urlencode(
        {"jql": jql, "fields": "summary,comment", "maxResults": LOOK}), head, opener)
    items = []
    for issue in found.get("issues") or []:
        ikey, f = issue.get("key", "?"), issue.get("fields") or {}
        for c in ((f.get("comment") or {}).get("comments") or [])[-LOOK:]:
            who = c.get("author") or {}
            if who.get("accountId") == me:
                continue
            mention = bool(me) and me in json.dumps(c.get("body"))
            text = adf_text(c.get("body")).strip()
            items.append(Item(f"{ikey}:{c.get('id', '')}",
                              f"{'@ ' if mention else ''}{ikey} {who.get('displayName', '?')}: {_short(text, 60)}",
                              f"{ikey} · {f.get('summary', '')}\n\n{text}"[:BODY],
                              f"{base}/browse/{ikey}?focusedCommentId={c.get('id', '')}", _iso(c.get("created")),
                              mention))
    return Look(sorted(items, key=lambda i: i.at), me={"id": me})


def confluence(feed: Feed, opener=urllib.request.urlopen) -> Look:
    head = _atlassian(feed)
    if isinstance(head, str):
        return Look(error=head, kind="login")
    base = f"https://{feed.opts['site']}/wiki"
    queries = [("mention = currentUser()", True)]
    if feed.opts.get("cql"):
        queries.append((feed.opts["cql"], False))
    elif feed.ids("spaces"):
        queries.append((f"type = comment AND space in ({','.join(feed.ids('spaces'))}) "
                        "AND creator != currentUser()", False))
    items: dict[str, Item] = {}
    for cql, mention in queries:
        found = get_json(f"{base}/rest/api/search?" + urllib.parse.urlencode(
            {"cql": f"({cql}) AND lastmodified >= now(\"-2d\") ORDER BY lastmodified DESC", "limit": LOOK}),
            head, opener)
        for r in found.get("results") or []:
            content = r.get("content") or {}
            key = str(content.get("id") or r.get("url", ""))
            if not key or key in items:
                continue
            kind = content.get("type", "page")
            title = r.get("title") or content.get("title", "")
            excerpt = re.sub(r"@@@(end)?hl@@@", "", r.get("excerpt", ""))
            items[key] = Item(key, f"{'@ ' if mention else ''}{kind} {_short(title, 40)}: {_short(excerpt, 50)}",
                              f"{title}\n\n{excerpt}"[:BODY], base + r.get("url", ""), _iso(r.get("lastModified")),
                              mention)
    return Look(sorted(items.values(), key=lambda i: i.at))


# -- Figma ----------------------------------------------------------------------------------------------

def figma(feed: Feed, opener=urllib.request.urlopen) -> Look:
    token = feed.env("token")
    if not token:
        return Look(error=feed.missing("token", "a personal access token"), kind="login")
    head = {"X-Figma-Token": token}
    me = get_json("https://api.figma.com/v1/me", head, opener)
    uid, handle = me.get("id", ""), str(me.get("handle", "")).lower()
    items = []
    for key in feed.ids("files"):
        try:
            comments = get_json(f"https://api.figma.com/v1/files/{key}/comments", head, opener).get("comments") or []
        except urllib.error.HTTPError as e:
            if e.code in (403, 404):          # the token is good (`/v1/me` answered): this file is out of reach
                raise Failed(f"figma: the file {key} is gone or this login may not open it", "target") from None
            raise
        mine = {c.get("id") for c in comments if (c.get("user") or {}).get("id") == uid}
        for c in sorted(comments, key=lambda c: c.get("created_at", ""))[-LOOK:]:
            who = c.get("user") or {}
            if who.get("id") == uid:
                continue
            text = c.get("message", "")
            mention = bool(handle) and f"@{handle}" in text.lower() or c.get("parent_id") in mine
            items.append(Item(f"{key}:{c.get('id', '')}",
                              f"{'@ ' if mention else ''}{who.get('handle', '?')} in {key}: {_short(text, 60)}",
                              text[:BODY], f"https://www.figma.com/design/{key}?comment={c.get('id', '')}",
                              _iso(c.get("created_at")), mention))
    return Look(sorted(items, key=lambda i: i.at), me={"id": uid, "handle": handle})


READERS = {"slack": slack, "jira": jira, "confluence": confluence, "figma": figma}


def reader(kind: str):
    """The function that looks at a feed of `kind`; GitHub, GitLab and Discord live in their own modules."""
    if kind in READERS:
        return READERS[kind]
    from orkcraft.realm import feeds_agent, feeds_discord, feeds_git     # they import this module
    return {"github": feeds_git.github, "gitlab": feeds_git.gitlab, "discord": feeds_discord.discord,
            "agent": lambda feed, opener: feeds_agent.look(feed)}[kind]


def look(feed: Feed, opener=urllib.request.urlopen, runner=None) -> Look:
    """One feed, every trouble turned into the look's error and which of the three it is (`kind`).
    `runner` is the `gh` / `glab` a GitHub or GitLab feed without a token asks (subprocess.run)."""
    try:
        if feed.kind in ("github", "gitlab"):
            return reader(feed.kind)(feed, opener, runner)
        return reader(feed.kind)(feed, opener)
    except urllib.error.HTTPError as e:
        why = {401: "the token was refused — log in again", 403: "the token may not read this — log in again",
               404: "not found — edit what it hears", 429: "too many requests, later"}.get(e.code, e.reason)
        return Look(error=f"{feed.kind}: {e.code} {why}", kind=fail_kind(e.code))
    except Failed as e:
        return Look(error=str(e)[:200], kind=e.kind)
    except urllib.error.URLError as e:
        return Look(error=f"{feed.kind}: could not reach {feed.host} ({e.reason})"[:200], kind="network")
    except (OSError, ValueError, AttributeError, TypeError) as e:
        return Look(error=f"{feed.kind}: {e}"[:200], kind="network")


def _when(at: str) -> dt.datetime | None:
    try:
        when = dt.datetime.fromisoformat(at)
    except (TypeError, ValueError):
        return None
    return when if when.tzinfo else when.astimezone()


def new_items(feed_look: Look, seen: list[str] | None, after: str = "") -> tuple[list[Item], list[str]]:
    """(what to send, the keys seen now). The first look (nothing seen yet) sends nothing; after the
    line was edited, an item older than the last look (`after`: a channel or file just added, an
    hour of slack for slow search indexes) is only marked seen."""
    keys = [i.key for i in feed_look.items]
    if seen is None:
        return [], keys[-SEEN_KEEP:]
    known, since = set(seen), _when(after)
    since = since - dt.timedelta(hours=1) if since else None
    unseen = [i for i in feed_look.items if i.key not in known]
    fresh = [i for i in unseen if since is None or (_when(i.at) or since) >= since]
    return fresh, (seen + [i.key for i in unseen])[-SEEN_KEEP:]


def slack_names(token: str, users: set[str], opener=urllib.request.urlopen) -> None:
    """users.info for the people not named yet (a webhook carries only their ids). Never raises."""
    for user in users - set(SLACK_NAMES):
        try:
            data = get_json(f"https://slack.com/api/users.info?{urllib.parse.urlencode({'user': user})}",
                            {"Authorization": f"Bearer {token}"}, opener)
        except (OSError, ValueError):
            continue
        u = (data or {}).get("user") or {}
        SLACK_NAMES[user] = ((u.get("profile") or {}).get("display_name") or u.get("real_name") or u.get("name")
                             or user) if (data or {}).get("ok") else user        # no users:read: the id, once
