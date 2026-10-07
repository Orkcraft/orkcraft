"""🗼 Discord as a Watchtower feed (realm/feeds.py): new messages in the channels a bot can see.

Discord forbids automating a person's account, so the tower listens as a bot the person made and
invited to their server (docs/design/watchtower-quick-add.md §5):

    discord: token=keychain:discord-bot channels=123,456 me=789
    discord: token=keychain:discord-bot guilds=111 me=789       # every text channel of a server (§6)

Each look asks `GET /channels/{id}/messages` per channel (the newest `LOOK`); a message that
mentions `me` (the person's user id) or the bot, or answers a message of `me`, is a mention; the
bot's own messages and the person's are skipped. A message's text needs the bot's **Message
Content Intent** switched on *(check: without it the text comes back empty but for mentions)*.

No face, no bus; the network is the caller's thread.
"""
from __future__ import annotations

import re
import urllib.error
import urllib.parse
import urllib.request

from orkcraft.realm import feeds
from orkcraft.realm.feeds import Failed, Feed, Item, Look, _iso, _short

API = "https://discord.com/api/v10"
PERMISSIONS = 1024 + 65536          # View Channels + Read Message History, nothing else
TEXT_CHANNELS = (0, 5)              # a text channel, an announcement channel
CHANNELS: dict[str, dict] = {}      # channel id → {name, guild_id}, for the app's life
GUILD_MAX = 25                      # channels a `guilds=` look asks at most, per server


def head(token: str) -> dict:
    return {"Authorization": f"Bot {token}"}


def invite(client_id: str) -> str:
    """The link that adds the bot to a server the person picks, allowed to read and nothing else."""
    return "https://discord.com/oauth2/authorize?" + urllib.parse.urlencode(
        {"client_id": client_id, "scope": "bot", "permissions": PERMISSIONS})


def _channel(ch: str, h: dict, opener) -> dict:
    if ch not in CHANNELS:
        info = feeds.get_json(f"{API}/channels/{ch}", h, opener) or {}
        CHANNELS[ch] = {"name": str(info.get("name") or ch), "guild_id": str(info.get("guild_id") or "")}
    return CHANNELS[ch]


def _name(user: dict) -> str:
    return str(user.get("global_name") or user.get("username") or user.get("id") or "?")


def discord(feed: Feed, opener=urllib.request.urlopen) -> Look:
    token = feed.env("token")
    if not token:
        return Look(error=feed.missing("token", "the bot's token"), kind="login")
    h = head(token)
    bot = feeds.get_json(f"{API}/users/@me", h, opener) or {}
    bid, me = str(bot.get("id") or ""), feed.opts.get("me", "")
    items: list[Item] = []
    channels = feed.ids("channels")
    for guild in feed.ids("guilds"):            # its text channels, asked each look: a new one is heard too
        try:
            listed = feeds.get_json(f"{API}/guilds/{guild}/channels", h, opener) or []
        except urllib.error.HTTPError as e:
            if e.code in (403, 404):
                raise Failed(f"discord: the bot is not in the server {guild} — invite it again, or edit", "target") from None
            raise
        text = [c for c in sorted(listed, key=lambda c: c.get("position", 0)) if c.get("type") in TEXT_CHANNELS]
        for c in text[:GUILD_MAX]:                  # a big server: its first channels, as Discord orders them
            CHANNELS[str(c["id"])] = {"name": str(c.get("name") or c["id"]), "guild_id": guild}
            if str(c["id"]) not in channels:
                channels.append(str(c["id"]))
    for ch in channels:
        try:
            where = _channel(ch, h, opener)
            messages = feeds.get_json(f"{API}/channels/{ch}/messages?limit={feeds.LOOK}", h, opener) or []
        except urllib.error.HTTPError as e:
            if e.code in (403, 404):            # the bot answered `/users/@me`: this channel is out of its sight
                raise Failed(f"discord: the bot cannot see the channel {ch} — invite it again, or edit the channels",
                             "target") from None
            raise
        for m in messages:
            author = m.get("author") or {}
            if author.get("id") in (bid, me) and author.get("id"):
                continue
            named = {str(u.get("id")): _name(u) for u in m.get("mentions") or []}
            answers = ((m.get("referenced_message") or {}).get("author") or {}).get("id")
            mention = bool(me) and (me in named or answers == me) or bool(bid) and bid in named
            text = re.sub(r"<@!?(\d+)>", lambda x: "@you" if x.group(1) == me else f"@{named.get(x.group(1), x.group(1))}",
                          m.get("content") or "")
            url = f"https://discord.com/channels/{where['guild_id'] or '@me'}/{ch}/{m.get('id', '')}"
            items.append(Item(f"{ch}:{m.get('id', '')}",
                              f"{'@ ' if mention else ''}{_name(author)} in #{where['name']}: {_short(text, 60)}",
                              text[:feeds.BODY], url, _iso(m.get("timestamp")), mention))
    return Look(sorted(items, key=lambda i: i.at), me={"id": me, "bot": bid})
