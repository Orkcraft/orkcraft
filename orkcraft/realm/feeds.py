"""🗼 The Watchtower's feeds: comments and mentions in Slack, Jira, Confluence and Figma.

These services push their webhooks only to a public URL, and the Watchtower listens on 127.0.0.1
alone, so it asks them instead: every two minutes, read-only, through their REST APIs. One line of
the `feeds` setting is one feed; a line names the environment variables that hold the login, never
the token itself (the Town Hall's Warder flags a spec that does):

    slack: token=SLACK_TOKEN channels=C0123,D0456
        mentions of you (search.messages, a user token with search:read) and the new messages in
        the channels listed (conversations.history); a message in a direct channel (D…) is a mention
    jira: site=acme.atlassian.net user=ATL_EMAIL token=ATL_TOKEN jql=project = WEB
        new comments on the issues you watch, are assigned or reported (or what `jql=` picks — it
        takes the rest of the line); a comment that @-mentions you is a mention
    confluence: site=acme.atlassian.net user=ATL_EMAIL token=ATL_TOKEN spaces=DOC,ENG
        pages and comments that mention you (CQL `mention = currentUser()`), and new comments in
        the spaces listed (or what `cql=` picks — it takes the rest of the line)
    figma: token=FIGMA_TOKEN files=AbC123,XyZ789
        new comments in the files listed; one that @-mentions you or answers yours is a mention

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
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

TIMEOUT_S = 15
LOOK = 20                       # items a feed asks for per look
SEEN_KEEP = 500                 # keys a feed remembers
BODY = 1500

KINDS = {                       # kind: (required options, optional options, the option that takes the rest)
    "slack": (("token",), ("channels", "secret"), ""),
    "jira": (("site", "user", "token"), ("jql", "secret"), "jql"),
    "confluence": (("site", "user", "token"), ("spaces", "secret", "cql"), "cql"),
    "figma": (("token", "files"), ("secret",), ""),
}
ICON = {"slack": "💬", "jira": "🎫", "confluence": "📘", "figma": "🎨"}
ENV_NAME = re.compile(r"^[A-Z][A-Z0-9_]{1,63}$")
SITE = re.compile(r"^[a-z0-9][a-z0-9.-]*\.[a-z]{2,}$")
IDS = re.compile(r"^[A-Za-z0-9_-]+(,[A-Za-z0-9_-]+)*$")
SLACK_NAMES: dict[str, str] = {}     # user id → name, for the app's life
JIRA_JQL = "watcher = currentUser() OR assignee = currentUser() OR reporter = currentUser()"


@dataclass
class Feed:
    kind: str
    opts: dict[str, str]
    line: str                    # the setting as written: the key of what this feed has seen
    poll: bool = True            # False: only `secret=` — it listens to the webhook, never asks

    def env(self, name: str) -> str:
        return os.environ.get(self.opts.get(name, ""), "")

    @property
    def identity(self) -> str:
        """Who is asked and as whom: what it has seen survives a change of channels, files or query."""
        return "|".join([self.kind] + [self.opts.get(k, "") for k in ("site", "user", "token")])

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
        if k in opts and not ENV_NAME.match(opts[k]):
            return None, f"{kind}: {k}= names an environment variable (like ATL_TOKEN), not the value"
    if "site" in opts:
        opts["site"] = opts["site"].removeprefix("https://").rstrip("/")
        if not SITE.match(opts["site"]):
            return None, f"{kind}: site= is a host name, like acme.atlassian.net"
    for k in ("channels", "files", "spaces"):
        if k in opts and not IDS.match(opts[k]):
            return None, f"{kind}: {k}= is a comma-separated list of ids"
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
        return Look(error=f"slack: set {feed.opts['token']} in the environment (a user token, xoxp-…)")
    head = {"Authorization": f"Bearer {token}"}

    def call(method: str, **params) -> dict:
        data = get_json(f"https://slack.com/api/{method}?{urllib.parse.urlencode(params)}", head, opener)
        if not (data or {}).get("ok"):
            raise ValueError(f"{method}: {(data or {}).get('error', 'no answer')}")
        return data

    me = call("auth.test")
    uid, team = me.get("user_id", ""), str(me.get("url", "")).rstrip("/")

    def name(user: str) -> str:
        """users.info (users:read) once per person; without the scope, the id."""
        if user and user not in SLACK_NAMES:
            try:
                u = call("users.info", user=user).get("user") or {}
                SLACK_NAMES[user] = (u.get("profile") or {}).get("display_name") or u.get("real_name") or u.get("name") or user
            except (OSError, ValueError):
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
    missing = [feed.opts[k] for k, v in (("user", user), ("token", token)) if not v]
    if missing:
        return f"{feed.kind}: set {' and '.join(missing)} in the environment (your e-mail and an API token)"
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
        return Look(error=head)
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
        return Look(error=head)
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
        return Look(error=f"figma: set {feed.opts['token']} in the environment (a personal access token)")
    head = {"X-Figma-Token": token}
    me = get_json("https://api.figma.com/v1/me", head, opener)
    uid, handle = me.get("id", ""), str(me.get("handle", "")).lower()
    items = []
    for key in feed.ids("files"):
        comments = get_json(f"https://api.figma.com/v1/files/{key}/comments", head, opener).get("comments") or []
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


def look(feed: Feed, opener=urllib.request.urlopen) -> Look:
    """One feed, every network trouble turned into the look's error."""
    try:
        return READERS[feed.kind](feed, opener)
    except urllib.error.HTTPError as e:
        why = {401: "the token was refused", 403: "the token may not read this", 404: "not found",
               429: "too many requests, later"}.get(e.code, e.reason)
        return Look(error=f"{feed.kind}: {e.code} {why}")
    except (OSError, ValueError, AttributeError, TypeError) as e:
        return Look(error=f"{feed.kind}: {e}"[:200])


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
