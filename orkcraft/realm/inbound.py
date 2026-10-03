"""🗼 Webhooks the services push to the Watchtower: checked, answered, turned into comments and mentions.

The Watchtower listens on 127.0.0.1 only; a tunnel (cloudflared, ngrok, tailscale funnel, smee.io)
gives it a public address. The first part of the path names the service:

    /slack        Slack Events API: the signing secret checks `X-Slack-Signature` (and a request
                  older than five minutes is refused); `url_verification` gets its challenge back
    /figma        Figma webhooks v2 (FILE_COMMENT): the passcode in the body; PING is ignored
    /jira         a Jira webhook (comment_created): `X-Hub-Signature` with the webhook's secret
    /confluence   an Automation rule's "Send web request" (Jira's too): `X-Orkcraft-Token`
    anything else as before: `X-Orkcraft-Token` or GitHub's `X-Hub-Signature-256`, a raw `watch.webhook`

The secret is the `secret=` of that service's `feeds` line, else `webhook_secret_env`. What is
parsed becomes the same items the feeds ask for (the same keys, so a thing heard both ways is sent
once): `watch.mention` when it is about you, else `watch.comment`. The simple form, for Automation
rules and anything else: `{"id", "title", "text", "url", "author", "mention"}`.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import time

from orkcraft.realm import feeds
from orkcraft.realm.feeds import Item, _iso, _short, adf_text

SERVICES = ("slack", "jira", "confluence", "figma")
SLACK_SKEW_S = 300
IGNORED = object()           # a known event that carries nothing to tell (a ping, an edit)


def service_of(path: str) -> str:
    head = (path or "").split("?", 1)[0].strip("/").split("/", 1)[0].lower()
    return head if head in SERVICES else ""


def _hmac(secret: str, data: bytes) -> str:
    return hmac.new(secret.encode(), data, hashlib.sha256).hexdigest()


def verify(service: str, secret: str, body: bytes, headers, now: float | None = None) -> bool:
    """True when the request carries the service's proof of the secret (no secret: anyone)."""
    if not secret:
        return True
    token = headers.get("X-Orkcraft-Token", "")
    if token and hmac.compare_digest(token, secret):
        return True
    if service == "slack":
        ts, sig = headers.get("X-Slack-Request-Timestamp", ""), headers.get("X-Slack-Signature", "")
        if not ts.isdigit() or abs((now or time.time()) - int(ts)) > SLACK_SKEW_S:
            return False
        return bool(sig) and hmac.compare_digest(sig, "v0=" + _hmac(secret, b"v0:" + ts.encode() + b":" + body))
    if service == "figma":
        try:
            passcode = str(json.loads(body or b"{}").get("passcode", ""))
        except (ValueError, AttributeError):
            return False
        return bool(passcode) and hmac.compare_digest(passcode, secret)
    for name in ("X-Hub-Signature-256", "X-Hub-Signature"):         # GitHub; Jira's webhook secret
        sig = headers.get(name, "")
        if sig and hmac.compare_digest(sig, "sha256=" + _hmac(secret, body)):
            return True
    return False


def answer(service: str, body: bytes) -> bytes | None:
    """What the sender wants back besides a 2xx: Slack's challenge when it checks the URL."""
    if service != "slack":
        return None
    try:
        data = json.loads(body or b"{}")
    except ValueError:
        return None
    return str(data.get("challenge", "")).encode() if data.get("type") == "url_verification" else None


# -- what came: items --------------------------------------------------------------------------------------

def parse(service: str, text: str, me: dict | None = None):
    """The items of one delivery; IGNORED for a known event with nothing to tell; None when unknown."""
    try:
        data = json.loads(text or "")
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    me = me or {}
    reader = {"slack": _slack, "jira": _jira, "figma": _figma}.get(service)
    got = reader(data, me) if reader else None
    return got if got is not None else _simple(service, data)


def _slack(data: dict, me: dict):
    if data.get("type") == "url_verification":
        return IGNORED
    if data.get("type") != "event_callback":
        return None
    ev = data.get("event") or {}
    users = [a.get("user_id") for a in data.get("authorizations") or [] if not a.get("is_bot")]
    uid = me.get("id") or (users[0] if users else "")
    if ev.get("type") not in ("message", "app_mention") or ev.get("bot_id") or \
            ev.get("subtype") not in (None, "thread_broadcast", "file_share") or (uid and ev.get("user") == uid):
        return IGNORED
    raw, ch = ev.get("text", ""), ev.get("channel", "")
    mention = ev.get("type") == "app_mention" or ev.get("channel_type") == "im" or bool(uid and f"<@{uid}>" in raw)
    text = re.sub(r"<@([A-Z0-9]+)>", lambda m: "@you" if m.group(1) == uid else
                  f"@{feeds.SLACK_NAMES.get(m.group(1), m.group(1))}", raw)
    who = feeds.SLACK_NAMES.get(ev.get("user", ""), ev.get("user", "?"))
    team = data.get("team_id", "")
    return [Item(f"{ch}:{ev.get('ts', '')}", f"{'@ ' if mention else ''}{who} in {ch}: {_short(text, 60)}",
                 text[:feeds.BODY], f"https://app.slack.com/client/{team}/{ch}" if team and ch else "",
                 _iso(ev.get("ts")), mention)]


def _jira(data: dict, me: dict):
    event = str(data.get("webhookEvent", ""))
    if not event:
        return None
    c, issue = data.get("comment") or {}, data.get("issue") or {}
    if event != "comment_created" or not c:
        return IGNORED
    who = c.get("author") or {}
    if me.get("id") and who.get("accountId") == me["id"]:
        return IGNORED
    key = issue.get("key", "?")
    mention = bool(me.get("id")) and me["id"] in json.dumps(c.get("body"))
    text = adf_text(c.get("body")).strip()
    site = str(issue.get("self", "")).split("/rest/", 1)[0]
    return [Item(f"{key}:{c.get('id', '')}",
                 f"{'@ ' if mention else ''}{key} {who.get('displayName', '?')}: {_short(text, 60)}",
                 f"{key} · {(issue.get('fields') or {}).get('summary', '')}\n\n{text}"[:feeds.BODY],
                 f"{site}/browse/{key}?focusedCommentId={c.get('id', '')}" if site else "", _iso(c.get("created")),
                 mention)]


def _figma(data: dict, me: dict):
    event = data.get("event_type")
    if not event:
        return None
    if event != "FILE_COMMENT":
        return IGNORED                                   # PING, FILE_UPDATE, …
    who = data.get("triggered_by") or {}
    if me.get("id") and who.get("id") == me["id"]:
        return IGNORED
    handles = {m.get("id"): m.get("handle", "") for m in data.get("mentions") or []}
    text = "".join(f.get("text") or (f"@{handles.get(f.get('mention'), 'someone')}" if f.get("mention") else "")
                   for f in data.get("comment") or [] if isinstance(f, dict))
    mention = bool(me.get("id")) and me["id"] in handles
    key, cid = data.get("file_key", ""), data.get("comment_id", "")
    return [Item(f"{key}:{cid}", f"{'@ ' if mention else ''}{who.get('handle', '?')} in "
                                 f"{data.get('file_name') or key}: {_short(text, 60)}",
                 text[:feeds.BODY], f"https://www.figma.com/design/{key}?comment={cid}", _iso(data.get("timestamp")),
                 mention)]


def _simple(service: str, data: dict):
    title, text = str(data.get("title") or ""), str(data.get("text") or data.get("body") or "")
    if not (title or text):
        return None
    mention = data.get("mention") in (True, "true", "yes", 1)
    who = str(data.get("author") or "")
    head = f"{who}: {title or text}" if who else (title or text)
    key = str(data.get("id") or hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:16])
    return [Item(key, f"{'@ ' if mention else ''}{_short(head, 80)}", f"{title}\n\n{text}".strip()[:feeds.BODY],
                 str(data.get("url") or ""), _iso(data.get("at")) if data.get("at") else "", mention)]
