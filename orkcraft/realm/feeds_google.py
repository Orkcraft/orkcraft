"""🗼 Gmail through a Google sign-in (realm/google.py, docs/design/google-account.md): read-only, no password.

    gmail: login=keychain:google-ann@gmail.com query=in:inbox newer_than:2d

`login=` names the account's sign-in (made in Settings → Accounts, never a token in the line); `query=`
is Gmail's own search and takes the rest of the line (default: the inbox of the last two days). Each new
message is one signal: a mention when it is addressed to you in To, else a comment. What you sent is
skipped. The mailbox is never changed: nothing is marked read.
"""
from __future__ import annotations

import datetime as dt
import re
from email.utils import getaddresses, parseaddr

from orkcraft.realm import feeds, google

QUERY = "in:inbox newer_than:2d"


def _when(ms: str) -> str:
    try:
        return dt.datetime.fromtimestamp(int(ms) / 1000, dt.timezone.utc).isoformat(timespec="seconds")
    except (TypeError, ValueError, OverflowError):
        return ""


def gmail(feed: feeds.Feed, opener=None) -> feeds.Look:
    ref = feed.opts.get("login", "")
    try:
        me = google.gmail_profile(ref, opener).lower()
        found = google.gmail_messages(ref, feed.opts.get("query") or QUERY, feeds.LOOK, opener)
    except google.GoogleError as e:
        raise feeds.Failed(f"gmail: {e}", e.kind) from None
    items = []
    for m in found:
        name, addr = parseaddr(m["from"])
        if (me and addr.lower() == me) or "SENT" in m["labels"]:
            continue
        to = {a.lower() for _, a in getaddresses([m["to"]]) if a}
        mention = bool(me) and me in to
        subject = m["subject"] or "(no subject)"
        who = name or addr or "(unknown)"
        text = re.sub(r"\s+", " ", m["snippet"]).strip()
        items.append(feeds.Item(m["id"], f"{'@ ' if mention else ''}{who}: {feeds._short(subject, 70)}",
                                f"From: {m['from']}\nSubject: {subject}\n\n{text}"[:feeds.BODY],
                                f"https://mail.google.com/mail/#all/{m['thread'] or m['id']}", _when(m["at"]), mention))
    return feeds.Look(sorted(items, key=lambda i: i.at), me={"email": me})
