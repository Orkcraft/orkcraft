"""🚶 Leaving the camp (docs/design/audience.md §2a, backlog W3): in the morning one press, "I'm off". The Warchief says
what the orks will do until evening — which carts — and the cap, up to `CAP_PCT` % of the AI tool's window, and asks
what to take first. While carts are in work the town keeps the computer from sleeping (gui/awake.py, only on power);
it lets it sleep when the work is done or the cap is reached. A closed lid still sleeps a laptop, and the line says so.

    leaving = Leaving(town)
    leaving.plan()                 # {"carts", "until", "cap", "window", "line", "lid"}: what "I'm off" will do
    leaving.leave(first=task_id)   # away until evening; that cart is taken first
    leaving.tick()                 # the window's share spent since; at the cap the Agent pools pause; at evening, back
    leaving.back()                 # the person is back: what happened, as one line; paused pools take tasks again
    leaving.busy()                 # carts are in work: the computer is worth keeping awake
    leaving.snapshot()             # what the page shows while away, or None

The night's work stays off by default (cut-list.md): leaving the camp is the day's, chosen by the person. The cap is
measured on the tightest window of the subscription tools (town-time.md §3), in percentage points spent since leaving,
so a window that resets in the day does not count twice. With no window to read (every tool on an API key), only the
town's spend limit holds, and the line says so.

A service: it changes the town (pauses and resumes an Agent pool, moves a cart to the front of its queue), keeps its
state in `.orkcraft/away.json` and publishes on the bus. It never shows a toast or a dialog.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any

from orkcraft import schedule
from orkcraft.core import bus
from orkcraft.realm import event_log

FILE = Path(".orkcraft") / "away.json"
CAP_PCT = 30                            # the share of the window the orks may spend while the person is away
EVENING = 19 * 60                       # "until evening" when the person set no working hours
WAITING = ("queued",)                   # a cart in a pool's queue
WORKING = ("working", "reviewing", "planning")   # a cart an ork is on
SHOWN = 3                               # carts the Warchief names; the rest are "+N more"


def _pools(town) -> list[tuple[str, Any]]:
    return [(bid, w) for bid, w in list(town.workers.items()) if getattr(w, "TYPE", "") == "barracks"]


def carts(town) -> list[dict[str, str]]:
    """The carts in work in the town's Agent pools: those an ork is on first, then the queue in its order."""
    on, queued = [], []
    for bid, w in _pools(town):
        st = w.state
        on += [{"building": bid, "task": t.id, "title": t.title, "status": t.status}
               for t in st.tasks if t.status in WORKING]
        queued += [{"building": bid, "task": t.id, "title": t.title, "status": t.status}
                   for t in st.queue if t.status in WAITING]
    return on + queued


def window_used(town) -> float | None:
    """The used share (0–100) of the tightest window of the subscription tools, as the Town Hall last read it; None
    when no tool on a subscription reports one."""
    from orkcraft.core.treasury import subscriptions
    hall = town.workers.get("town_hall")
    limits = list(getattr(hall, "limits", None) or [])
    subs = subscriptions(town.machine)
    left = [x.remaining for x in limits if getattr(x, "provider", "") in subs and getattr(x, "remaining", None) is not None]
    return round((1 - min(left)) * 100, 1) if left else None


def until(machine, now: dt.datetime) -> dt.datetime:
    """Evening: where today's working hours end (schedule.py), else 19:00 — the next one after `now`."""
    minute = machine.work.end if getattr(machine, "work", None) is not None else EVENING
    at = now.replace(hour=minute // 60, minute=minute % 60, second=0, microsecond=0)
    return at if at > now else at + dt.timedelta(days=1)


def lid(platform: str | None = None) -> str:
    """The plain sentence about the lid, in the system's own word for the machine."""
    machine = "Mac" if (platform or sys.platform) == "darwin" else "computer"
    return (f"While carts are in work and the {machine} is on power, the town keeps it from sleeping, and lets it "
            f"sleep when the work is done or the cap is reached. A closed lid still sleeps a laptop: leave the lid open.")


def _names(rows: list[dict]) -> str:
    titles = [f"“{r['title'][:60]}”" for r in rows[:SHOWN]]
    more = len(rows) - SHOWN
    return ", ".join(titles) + (f" and {more} more" if more > 0 else "")


def _many(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


class Leaving:
    def __init__(self, town) -> None:
        self.town = town
        self.away: dict[str, Any] | None = self._load()

    # -- where it is kept ----------------------------------------------------------------------------

    @property
    def root(self) -> Path | None:
        """The town's folder; None in the demo (nothing is written or counted there)."""
        return None if getattr(self.town, "demo", False) else getattr(self.town, "repo_root", None)

    def _load(self) -> dict[str, Any] | None:
        if self.root is None:
            return None
        try:
            data = json.loads((self.root / FILE).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return data if isinstance(data, dict) and data.get("since") and data.get("until") else None

    def _save(self) -> None:
        if self.root is None:
            return
        f = self.root / FILE
        try:
            if self.away is None:
                f.unlink(missing_ok=True)
            else:
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_text(json.dumps(self.away, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass

    def _changed(self) -> None:
        self._save()
        self.town.publish(bus.HUD, away=self.away is not None)

    # -- what it reads --------------------------------------------------------------------------------

    def busy(self) -> bool:
        return bool(carts(self.town))

    @property
    def capped(self) -> bool:
        return bool(self.away and self.away.get("capped"))

    def plan(self, now: dt.datetime | None = None) -> dict[str, Any]:
        """What "I'm off" would do now: the carts, until when, the cap, the Warchief's line and the lid's sentence."""
        now = now or dt.datetime.now()
        rows = carts(self.town)
        end = schedule.fmt(until(self.town.machine, now).hour * 60 + until(self.town.machine, now).minute)
        used = window_used(self.town)
        if rows:
            line = (f"Until {end} the orks work on {_many(len(rows), 'cart', 'carts')}: {_names(rows)}. "
                    + (f"They spend up to {CAP_PCT} % of the window, then wait for you. " if used is not None else
                       "No AI tool here reports a window, so only the spend limit in Town settings holds them. ")
                    + "What do they take first?")
        else:
            line = (f"No cart is in work: until {end} the orks have nothing to do unless work comes in. "
                    "The town lets the computer sleep.")
        return {"carts": rows, "until": end, "cap": CAP_PCT, "window": used, "line": line, "lid": lid()}

    def snapshot(self, now: dt.datetime | None = None) -> dict[str, Any] | None:
        a = self.away
        if a is None:
            return None
        return {"since": a["since"][11:16], "until": a["until"][11:16], "cap": a.get("cap", CAP_PCT),
                "spent": round(a.get("spent", 0.0), 1), "metered": a.get("last") is not None,
                "capped": bool(a.get("capped")), "carts": len(carts(self.town)), "lid": lid()}

    # -- what it does ---------------------------------------------------------------------------------

    def _first(self, task_id: str) -> str:
        """That cart to the front of its pool's queue; its title ("" when it is not waiting in one)."""
        for _bid, w in _pools(self.town):
            st = w.state
            t = next((x for x in st.queue if x.id == task_id), None)
            if t is not None:
                st.queue.remove(t)
                st.queue.insert(0, t)
                st.save()
                w.changed()
                return t.title
            t = next((x for x in st.tasks if x.id == task_id and x.status in WORKING), None)
            if t is not None:
                return t.title                   # an ork is on it already
        return ""

    def leave(self, first: str = "", on_power: bool | None = None, now: dt.datetime | None = None) -> dict[str, Any]:
        """"I'm off": away until evening, `first` taken first. What the page shows."""
        now = (now or dt.datetime.now()).replace(microsecond=0)
        rows = carts(self.town)
        taken = self._first(first) if first else ""
        used = window_used(self.town)
        self.away = {"since": now.isoformat(), "until": until(self.town.machine, now).isoformat(), "cap": CAP_PCT,
                     "last": used, "spent": 0.0, "capped": False, "paused": [], "first": taken}
        event_log.record(self.root, event_log.CAMP_LEFT, carts=len(rows), first=taken, cap_pct=CAP_PCT,
                         until=self.away["until"][11:16], on_power=on_power)
        self._changed()
        return self.snapshot(now) or {}

    def tick(self, now: dt.datetime | None = None) -> str:
        """The window's share spent since the last look; the cap reached: the Agent pools pause. Evening: back.
        What it said ("" for nothing new)."""
        a = self.away
        if a is None:
            return ""
        now = now or dt.datetime.now()
        if now.isoformat() >= a["until"]:
            return self.back("evening", now)
        used = window_used(self.town)
        if used is not None:
            last = a.get("last")
            if last is not None and used > last:
                a["spent"] = round(a.get("spent", 0.0) + used - last, 1)
            a["last"] = used                    # lower than before: the window reset, nothing spent
        if not a.get("capped") and a.get("spent", 0.0) >= a.get("cap", CAP_PCT):
            a["capped"] = True
            for bid, w in _pools(self.town):
                if not w.state.paused:
                    w.state.paused = True
                    w.state.save()
                    w.changed()
                    a["paused"].append(bid)
            self._changed()
            return (f"The orks spent {a['cap']} % of the window: the Agent pool waits for you. "
                    "The computer may sleep now.")
        self._save()
        return ""

    def back(self, why: str = "person", now: dt.datetime | None = None) -> str:
        """The person is back (or evening came): the pools the cap paused take tasks again; what happened."""
        a = self.away
        if a is None:
            return ""
        now = now or dt.datetime.now()
        for bid in a.get("paused", []):
            w = self.town.workers.get(bid)
            if w is not None and getattr(w, "TYPE", "") == "barracks" and w.state.paused:
                w.pause()                       # takes tasks again, and the idle orks pick up what waited
        try:
            minutes = max(0, round((now - dt.datetime.fromisoformat(a["since"])).total_seconds() / 60))
        except ValueError:
            minutes = 0
        left = len(carts(self.town))
        event_log.record(self.root, event_log.CAMP_BACK, why=why, minutes=minutes, window_pct=a.get("spent", 0.0),
                         capped=bool(a.get("capped")), carts_left=left)
        spent = f"{a.get('spent', 0.0):g} % of the window spent" if a.get("last") is not None else "no window measured"
        lead = "Evening, the day away is over" if why == "evening" else "Welcome back"
        text = (f"{lead}. Away since {a['since'][11:16]}: {spent}"
                + (", the cap reached" if a.get("capped") else "")
                + (f"; {_many(left, 'cart', 'carts')} still in work." if left else "; no cart left in work."))
        self.away = None
        self._changed()
        return text
