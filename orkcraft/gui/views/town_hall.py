"""🏰 Town Hall in the GUI, the town's way in (docs/design/building-views.md §3):

- closed (`card`): what happens in the hall — a town order waits, the Warchief is answering, the
  audit found something — else nothing, and the page shows Build and Ask me anything;
- command and full (`detail`): the Warchief's chat, the hall (its orks, the audit, the proposals),
  spend and the quotas (Limits). The live sessions are the snapshot's (`sessions`).

The work is the worker's (core/workers/town_hall.py): a question to the Warchief, an audit, the
quotas read again.
"""
from __future__ import annotations

import datetime as dt

from orkcraft.core import warchief
from orkcraft.core.workers.town_hall import LIMITS_REFRESH_S, buildable
from orkcraft.gui import markdown
from orkcraft.gui.views import ActError, text
from orkcraft.realm import modes

REFRESH_S = 30.0              # the hall looks again (a town order, the audit's findings); the quotas every 10 min
SHOWN = 30                    # chat messages a page gets


def refresh(w) -> None:
    w.look()
    if w.limits_at is None or (dt.datetime.now() - w.limits_at).total_seconds() >= LIMITS_REFRESH_S:
        w.read_limits()


def card(w) -> dict:
    """The hut: only what happens (tiny: it goes in every snapshot)."""
    news = []
    if w.order_waits:
        news.append("A town order waits")
    if w.thinking:
        news.append(f"{w.warchief} is answering…")
    if w.serious:
        news.append(f"Audit: {w.serious} to look at")
    return {"news": news, "warchief": w.warchief}


def _message(m: dict, titles: dict[str, str], buildings: dict[str, str]) -> dict:
    out = {"who": m["who"], "ts": str(m.get("ts", ""))[11:16], "error": bool(m.get("error"))}
    if m["who"] == "warchief":
        out["html"] = markdown.render(m["text"])
    else:
        out["text"] = m["text"]
    if isinstance(m.get("card"), dict):                 # the work he gave a specialist (core/warchief.py)
        out["card"] = _plain(warchief.public(m["card"], buildings))
    if m.get("suggest") in titles:                       # an older answer's building to build
        out["suggest"], out["suggest_title"] = m["suggest"], titles[m["suggest"]]
        out["asked"] = str(m.get("asked") or "")
    return out


def _plain(value):
    """The hall's data without pictographs (Office drops them; Camp shows its icons apart)."""
    if isinstance(value, str):
        return modes.strip_emoji(value)
    if isinstance(value, list):
        return [_plain(v) for v in value]
    if isinstance(value, dict):
        return {k: (v if k == "icon" else _plain(v)) for k, v in value.items()}
    return value


def detail(w) -> dict:
    titles = {t.id: t.title for t in buildable()}
    buildings = {b.id: b.title for b in w.town.scroll.buildings}
    return {
        "warchief": w.warchief,
        "chat": [_message(m, titles, buildings) for m in w.chat[-SHOWN:]],
        "thinking": w.thinking,
        "hall": _plain(w.hall()),
        "spend": w.spend(),
        "limits": [{"provider": x.provider, "what": " ".join(p for p in (x.window, x.group) if p and p != "—"),
                    "remaining": x.remaining, "error": x.error or "", "note": x.note,
                    "reset": x.reset.strftime("%a %H:%M") if x.reset else ""} for x in w.limits or ()],
        "limits_at": w.limits_at.strftime("%H:%M") if w.limits_at else "",
        "reading_limits": w.reading_limits or w.limits is None,
        "lowest": w.lowest(),
    }


def _ask(w, args: dict) -> None:
    about = [str(x)[:200] for x in args.get("about") or [] if isinstance(x, str)][:8]
    problem = w.ask(text(args, "text", 8000), about)
    if problem:
        raise ActError(problem)


def _card(w, args: dict) -> bool:
    """A card of the Warchief's answered: build, cancel or undo."""
    choice = text(args, "choice", 20)
    if choice not in ("build", "cancel", "undo") or not w.card_act(text(args, "card", 100), choice):
        raise ActError("That card has moved on")
    return True


def _forget(w, args: dict) -> None:
    w.forget()


def _audit(w, args: dict) -> str:
    return w.audit().summary()


def _limits(w, args: dict) -> None:
    w.read_limits()


def _proposal(w, args: dict) -> bool:
    """The Building retro's proposal: Apply (a checkpoint, Revert takes it back) or Dismiss."""
    from orkcraft.core import buildings as core_buildings
    from orkcraft.realm import optimize
    p = next((x for x in optimize.pending(w.repo_root) if x.id == text(args, "id", 100)), None)
    if p is None:
        raise ActError("That proposal was answered already")
    if text(args, "choice", 20) == "dismiss":
        p.status = "dismissed"
        optimize.save(w.repo_root, p)
        w.changed()
        return True
    return core_buildings.apply_proposal(w.town, p, by="you")


def _weekly(w, args: dict) -> bool:
    """One item of the Town retro: Apply (checked again first) or Decline (never applied, by the orks either)."""
    from orkcraft.core import retros
    from orkcraft.realm import weekly
    report = weekly.latest(w.repo_root)
    try:
        n = int(args.get("n"))
    except (TypeError, ValueError):
        raise ActError("Which item?") from None
    if report is None or not any(i.n == n for i in report.items):
        raise ActError("That item is gone")
    if text(args, "choice", 20) == "decline":
        retros.decline_weekly_item(w.town, report, n)
        return True
    return retros.apply_weekly_item(w.town, report, n)


ACTS = {"ask": _ask, "card": _card, "forget": _forget, "audit": _audit, "limits": _limits, "proposal": _proposal, "weekly": _weekly}
