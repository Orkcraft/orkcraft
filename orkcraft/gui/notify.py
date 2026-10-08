"""The notifier (docs/design/mobile.md §5, stage 2): what came while a phone looked away, as one short line
each, to the phones whose app is open (the app shows it as a local notification). Pushes to a phone in a
pocket go through the relay (stage 3); this sends only over the sockets that are open.

    ← {"t": "news", "news": [{"kind": "alert", "id": "…", "line": "Grunt asks: Proceed?"}, …]}

What is news is `mobile.news` between two compact snapshots (a question that came, each once; spend or a
quota that crossed into warn or over), taken each time the listener sends the phones a snapshot, and two
things a snapshot does not keep, from the bus: a toast of severity `error` (only its title) and a
session that exited. A line carries no code, no file contents and no secrets: only a title and who.
While the person asked not to be disturbed (gui/you.py) every line waits but the spend over its limit,
and when it ends one line says everything that gathered.
"""
from __future__ import annotations

from typing import Any

from orkcraft.core import bus
from orkcraft.gui import mobile
from orkcraft.realm import lexicon, modes

_LEVEL = {"warn": "is near its limit", "over": "is over its limit"}


class Notifier:
    def __init__(self, host, listener) -> None:
        self.host, self.listener = host, listener
        self.before: dict | None = None          # the snapshot the phones had at the last look
        listener.on_push = self.after
        host.you.on_news = lambda item: self.listener.phones and self.listener.broadcast({"t": "news", "news": [item]})
        self.off = host.town.bus.subscribe(bus.ANY, self._event)

    def line(self, item: dict, snap: dict) -> dict[str, Any]:
        words = snap.get("resources") or {}
        if item["kind"] == "alert":
            who = modes.plain(item.get("who") or "") or "An ork"
            return {**item, "line": f"{who} asks: {modes.strip_emoji(item['title'])}"}   # the question keeps its words
        if item["kind"] == "episode":                  # an Audio briefing's episode to download (audio-briefing.md §8)
            minutes = max(1, round((item.get("seconds") or 0) / 60))
            return {**item, "line": f"{lexicon.term('gramophone')}: {item['title']} ({minutes} min) is ready"}
        word = words.get("gold" if item["kind"] == "gold" else "quota") or item["kind"].title()
        return {**item, "line": f"{word} {_LEVEL.get(item['level'], item['level'])}: {item.get('text', '')}".rstrip(": ")}

    def after(self, snap: dict | None) -> None:
        """The listener sent the phones `snap` (None: no phone is open, so the next one looks afresh)."""
        if snap is None:
            self.before = None
            return
        news = [self.line(n, snap) for n in mobile.news(self.before, snap) if not self.host.you.hold_push(n)]
        self.before = snap
        if news:
            self.listener.broadcast({"t": "news", "news": news})

    def _event(self, event: bus.Event) -> None:
        if not self.listener.phones:
            return
        item = None
        if event.topic == bus.TOAST and event.data.get("severity") == "error":
            title = modes.plain(str(event.data.get("title") or "")) or "Orkcraft"
            item = {"kind": "error", "line": f"Something failed: {title}"}
        elif event.topic == bus.SESSION and event.data.get("state") == "exited":
            key = str(event.data.get("key") or "")
            who = next((o.name for o in self.host.muster.roster.orcs if key and key in (o.session, o.ref)), "")
            code = event.data.get("code")
            done = "finished" if code in (0, None) else "stopped with an error"
            item = {"kind": "exited", "key": key, "line": f"{modes.plain(who) or 'A session'} {done}"}
        if item is not None and not self.host.you.hold_push(item):
            self.listener.broadcast({"t": "news", "news": [item]})
