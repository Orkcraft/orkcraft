"""🗼 Watchtower in the GUI: what is new per source, the chosen source's feed, the item read in full,
and the sources' settings with the intent. The listening is the worker's
(core/workers/watchtower.py); the page's clock pulses it once a second (the webhook's inbox, the
schedule every 30 s, a look every 2 min)."""
from __future__ import annotations

import datetime as dt
import re

from orkcraft.core.workers import watchtower_add
from orkcraft.gui import markdown
from orkcraft.gui.views import ActError, text
from orkcraft.realm import quickadd, watch

REFRESH_S = 1.0
CARD_ROWS = 4                   # counters on the closed card; more sources fold into `+N more`
LATEST = 5                      # the newest per source on the Command Card
CARD_LATEST = 1                 # the newest signal the closed card previews
FRESH_S = 90                    # a signal this young is marked as just arrived
_FROM = re.compile(r"^(@ )?(.{1,48}?): (.+)$", re.S)     # `Ann: Lunch?`, `@ ann in #dev: hi`


def refresh(w) -> None:
    w.pulse()


def _who(title: str, source: str = "mail") -> tuple[str, str]:
    """(from, title) out of a signal's title: mail is `sender: subject`, a feed's `who in where: text`;
    GitHub, the schedule and a webhook say no one."""
    m = _FROM.match(title or "") if source == "mail" or source in watch.FEEDS else None
    return (m.group(2), m.group(3)) if m else ("", title)


def subject(title: str) -> str:
    """What a signal's cart is about, without its source and sender: `slack · Sam in #team: Hi?` → `Hi?`."""
    rest = re.sub(r"^(?:" + "|".join(watch.FEEDS) + r") · ", "", title or "")
    return _who(rest, "mail")[1] or rest


def _signal(w, s) -> dict:
    who, title = _who(s.title, s.source)
    return {"key": s.key, "source": s.source, "label": w.label(s.source), "at": s.at[:16].replace("T", " "),
            "from": who, "title": title, "read": s.read, "mention": s.mention, "kept": s.kept, "why": s.why}


def _fresh(at: str, now: dt.datetime) -> bool:
    try:
        return 0 <= (now - dt.datetime.fromisoformat(at)).total_seconds() <= FRESH_S
    except ValueError:
        return False


def card(w) -> dict:
    """Closed: how many are new (`new`) and how many sources fail; what is new per source (`gmail 3`,
    `slack 99+`, `jira ERR`), more than four → `+N more`; then the newest signals kept (source, from,
    title, time), the one that just arrived marked `fresh`."""
    if not w.sources:
        return {"sources": [], "more": None, "latest": [], "new": 0, "failing": 0}
    shown, more = w.counters(CARD_ROWS)
    now = dt.datetime.now()
    latest = []
    for s in [x for x in w.signals if x.kept is not False][:CARD_LATEST]:
        who, title = _who(s.title, s.source)
        latest.append({"key": s.key, "source": s.source, "label": w.label(s.source), "from": who, "title": title,
                       "at": s.at[11:16], "read": s.read, "fresh": _fresh(s.at, now)})
    return {"sources": [{"label": label, "n": n} for label, n in shown],
            "more": {"count": more[0], "n": more[1]} if more else None, "latest": latest,
            "new": len(w.unread()), "failing": sum(1 for x in w.shown() if w.failing(x))}


def detail(w) -> dict:
    sources = [{"id": s, "label": w.label(s), "new": len(w.unread(s)), "why": w.why(s)} for s in w.shown()]
    latest, seen = [], set()
    for s in w.signals:                                   # newest first: the newest of each source
        if s.source not in seen and len(latest) < LATEST:
            seen.add(s.source)
            latest.append(_signal(w, s))
    reading = None
    if w.reading:
        reading = {"key": w.reading["key"], "html": markdown.render(w.reading["markdown"])}
    cfg = w.config
    return {
        "sources": sources, "latest": latest, "signals": [_signal(w, s) for s in w.signals],
        "new": len(w.unread()), "reading": reading, "checked": w.checked, "looking": w._looking,
        "listening": w.hook.port if w.hook is not None else 0,
        "mailbox": w.look.unread if w.look is not None and not w.look.error else None,
        "intent": w.intent, "intent_error": w.errors.get("intent", ""), "error": w.errors.get("look", ""),
        "adding": w.adding.view(), "listed": watchtower_add.listed(w),
        "settings": {"host": str(cfg.get("host") or ""), "folder": str(cfg.get("folder") or ""),
                     "github": str(cfg.get("github") or ""), "cron": str(cfg.get("cron") or ""),
                     "webhook_port": cfg.get("webhook_port") or "", "feeds": [str(x) for x in cfg.get("feeds") or []]},
    }


def _read(w, args: dict) -> str:
    sig = w.signal(text(args, "key", 500))
    if sig is None:
        raise ActError("That signal is no longer in the list")
    w.read(sig)
    return sig.key


def _open_new(w, args: dict) -> str:
    sig = w.open_new()
    if sig is None:
        raise ActError("Nothing came in yet")
    return sig.key


def _read_all(w, args: dict) -> int:
    source = text(args, "source", 40)
    return w.mark_read([s for s in w.signals if s.source == source] if source else None)


def _check_now(w, args: dict) -> None:
    w.check_now()


def _intent(w, args: dict) -> bool:
    """What to listen for, in plain words: the Lookout lets through only what matches ("" lets all through)."""
    intent = " ".join(text(args, "intent", 500).split())
    if intent == w.intent:
        return False
    if not w.save_config({"intent": intent}):
        raise ActError("Not saved")
    w.changed()
    return True


def _simulate(w, args: dict) -> str:
    """The sandbox only: a mail or a message arrives as its source would send it (a film or a walk-through)."""
    sig = w.simulate(text(args, "source", 20), text(args, "title", 300), text(args, "body", 4000))
    if sig is None:
        raise ActError("Only the demo makes messages up")
    return sig.key


# -- Add a source (docs/design/watchtower-quick-add.md): the steps are the worker's (watchtower_add.py) -------

def _adding(fn):
    """An Add-a-source act: a Refused from the steps is shown to the person."""
    def act(w, args: dict):
        try:
            return fn(w, args)
        except quickadd.Refused as e:
            raise ActError(str(e)) from None
    return act


def _strings(args: dict, key: str, limit: int = 200) -> list[str]:
    value = args.get(key) or []
    if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
        raise ActError(f"{key} is not a list of text")
    return [x[:120] for x in value[:limit]]


@_adding
def _add_open(w, args: dict) -> None:
    w.adding.open()


@_adding
def _add_link(w, args: dict) -> str:
    """A pasted link or address: its service starts, what it names ticked."""
    link = w.adding.recognise(text(args, "link", 2000))
    if link is None:
        raise ActError("Not a link this can listen to yet — pick the service instead")
    w.adding.start(link.service, link)
    return link.service


@_adding
def _add_start(w, args: dict) -> None:
    w.adding.start(text(args, "service", 40))


@_adding
def _add_login(w, args: dict) -> None:
    values = args.get("values") or {}
    if not isinstance(values, dict):
        raise ActError("values is not a form")
    w.adding.log_in({k: text(values, k, 500) for k in ("site", "email", "token", "password") if k in values})


@_adding
def _add_use(w, args: dict) -> None:
    w.adding.use_kept(text(args, "account", 200))


@_adding
def _add_files(w, args: dict) -> None:
    w.adding.add_files(text(args, "links", 4000))


@_adding
def _add_what(w, args: dict) -> None:
    w.adding.what(_strings(args, "picks"), bool(args.get("about_me", True)), text(args, "folder", 100) or "INBOX")


@_adding
def _add_save(w, args: dict) -> str:
    return w.adding.save()


@_adding
def _add_back(w, args: dict) -> None:
    w.adding.back()


@_adding
def _add_close(w, args: dict) -> None:
    w.adding.close()


@_adding
def _remove(w, args: dict) -> bool:
    return watchtower_add.remove(w, text(args, "source", 2000))


ACTS = {"add_open": _add_open, "add_link": _add_link, "add_start": _add_start, "add_login": _add_login,
        "add_use": _add_use, "add_files": _add_files, "add_what": _add_what, "add_save": _add_save,
        "add_back": _add_back, "add_close": _add_close, "remove": _remove,
        "simulate": _simulate, "read": _read, "open_new": _open_new, "read_all": _read_all, "check_now": _check_now, "intent": _intent}
