"""You in the GUI (docs/design/portrait.md): what the portrait's menu sets for the person, per machine —
the look (camp | office), Do not disturb, the working hours and the fire on the roofs (`fire`) — and what gathered
while Do not disturb or the working hours held, said once when they end: in the Warchief's line (`summary`) and to
the phones that are open (`on_news`).

The working hours (docs/design/audience.md §2a) are quiet for the person's own project: an ork's question raises no
toast and no push while they hold (it stays pinned in Answers, gathered for "since your last look"), each one held
is counted into the local event log, and the orks are told to assume and mark where that is safe
(core/workers/barracks_asks.py). Outside them, as before.

    you = You(host)                  # sets `town.hushed`: the Horn keeps quiet while it holds
    host.commands.update(you.commands())
    you.tick()                       # from the host's clock: a timed Do not disturb that ran out
    you.hold_toast(data)             # True: a toast the page does not show now (counted)
    you.hold_push(item)              # True: a line the phones do not get now (counted)
    you.at_work()                    # the working hours hold: a question's toast and push wait
    you.snapshot()                   # {"look", "mono", "fire", "dnd": {...}, "summary": {...} | None}
"""
from __future__ import annotations

import datetime as dt
from typing import Any, Callable

from orkcraft import disturb, schedule, settings
from orkcraft.gui import state
from orkcraft.realm import event_log, intents, jobs

# The role's two letters, the portrait in Office (docs/design/portrait.md §1).
MONOGRAMS = {"engineer": "SE", "qa": "QA", "eng_manager": "EM", "product_manager": "PM", "designer": "PD",
             "game_designer": "GD", "aso_manager": "AS", "marketing": "MK", "data_analyst": "DA", "founder": "FO"}


class YouError(Exception):
    """A setting of the portrait's menu the host refuses; its text is shown to the person."""


def _many(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


class You:
    def __init__(self, host) -> None:
        self.host = host
        self.on_news: Callable[[dict], None] = lambda item: None    # gui/notify.py: one line to the phones
        self.summary: dict | None = None
        self._start()
        self.work_held = 0                     # questions held in today's working hours (said when they end)
        self._was_at_work = self.at_work()
        host.town.hushed = self.holds

    @property
    def machine(self):
        return self.host.town.machine

    def holds(self) -> bool:
        return disturb.holds(self.machine)

    def at_work(self, now: dt.datetime | None = None) -> bool:
        return schedule.at_work(self.machine, now)

    def _held_at_work(self, how: str, title: str) -> None:
        self.work_held += 1
        root = None if getattr(self.host.town, "demo", False) else self.host.town.repo_root
        event_log.record(root, event_log.HELD_AT_WORK, how=how, title=title)

    # -- what gathers while it holds ------------------------------------------------------------------

    def _start(self) -> None:
        self.held = {"toasts": 0, "errors": 0, "pushes": 0}
        self.since = jobs.now_iso()

    def hold_toast(self, data: dict) -> bool:
        """An error still shows (and is counted); any other toast waits. In the working hours a question's waits."""
        if data.get("kind") == "question" and data.get("severity") != "error" and self.at_work():
            self._held_at_work("toast", str(data.get("title_plain") or data.get("title") or ""))
            return True
        if not self.holds():
            return False
        if data.get("severity") == "error":
            self.held["errors"] += 1
            return False
        self.held["toasts"] += 1
        return True

    def hold_push(self, item: dict) -> bool:
        """Every line to the phones waits but one: the spend over its limit, the budget spent. In the working hours
        an ork's question waits (the phone's Answers still has it when the person looks)."""
        if item.get("kind") == "alert" and self.at_work():
            self._held_at_work("push", str(item.get("title") or ""))
            return True
        if not self.holds() or (item.get("kind") == "gold" and item.get("level") == "over"):
            return False
        self.held["pushes"] += 1
        return True

    def _kept(self) -> tuple[int, str]:
        """The Horn's calls kept since it began, and the first horn that kept one."""
        n, first = 0, ""
        for bid, w in self.host.town.workers.items():
            if getattr(w, "TYPE", "") != "horn":
                continue
            k = sum(1 for c in getattr(w, "calls", []) if c.played == "dnd" and c.at >= self.since)
            if k and not first:
                first = bid
            n += k
        return n, first

    def _end(self, lead: str = "While you were away") -> None:
        """It ended: everything that gathered, as one line in the Warchief's line and one to the phones."""
        questions = len(self.host.muster.roster.alerts)
        sounds, horn_id = self._kept()
        parts = []
        if questions:
            parts.append(_many(questions, "question", "questions"))
        if sounds:
            parts.append(_many(sounds, "sound kept", "sounds kept"))
        if self.held["errors"]:
            parts.append(_many(self.held["errors"], "error", "errors"))
        if self.held["toasts"]:
            parts.append(_many(self.held["toasts"], "message held", "messages held"))
        if self.held["pushes"]:
            parts.append(_many(self.held["pushes"], "push held", "pushes held"))
        hud = state.hud(self.host.town, self.host.muster, self.host.treasury, self.host.limits())
        if hud.get("show_gold") and hud.get("gold_level") in ("warn", "over"):
            parts.append(f"spend at {hud['gold']}")
        text = f"{lead}: " + (", ".join(parts) if parts else "nothing came") + "."
        self.summary = {"id": self.since, "text": text, "open": "orders" if questions else ("horn" if sounds else ""),
                        "building": horn_id if not questions else ""}
        self.on_news({"kind": "dnd", "line": text})
        self._start()

    # -- the clock ------------------------------------------------------------------------------------

    def tick(self, now: dt.datetime | None = None) -> None:
        if disturb.ended(self.machine):
            settings.save(self.machine)
            self._end()
            self.host.on_change()
        working = self.at_work(now)
        if self._was_at_work and not working:
            self._work_over()
        self._was_at_work = working

    def _work_over(self) -> None:
        """The working day ended: the questions that wait are said once, unless nothing was held and none waits."""
        held, self.work_held = self.work_held, 0
        if not held and not self.host.muster.roster.alerts:
            return
        if not self.holds():
            self._end("Your working day is over")
            self.host.on_change()

    # -- what the page sees ---------------------------------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        m = self.machine
        now = dt.datetime.now()
        morning = disturb.morning(m, now)
        role = intents.role(str((m.profile or {}).get("role") or "")).id
        return {"look": settings.look_now(m, now), "look_choice": m.look,
                "shift": settings.shift(m).label(),
                "mono": MONOGRAMS.get(role, "··"), "role": role if role in MONOGRAMS else "",
                "fire": m.fire,
                "dnd": {"on": disturb.holds(m, now), "choice": disturb.choice(m, now), "label": disturb.label(m, now),
                        "morning": schedule.fmt(morning.hour * 60 + morning.minute)},
                "work": {"set": m.work is not None, "on": self.at_work(now), "held": self.work_held,
                         **(m.work or schedule.DEFAULT_WORK).to_dict()},
                "summary": self.summary}

    # -- the page's commands --------------------------------------------------------------------------

    def _look(self, args: dict) -> dict[str, Any]:
        look = args.get("look")
        if look not in settings.LOOKS:
            raise YouError(f"No look {look!r}: camp, office or shift")
        self.machine.look = look
        settings.save(self.machine)
        self.host.on_change()
        return self.snapshot()

    def _fire(self, args: dict) -> dict[str, Any]:
        """Whether flames climb the roof of a building that waits for you: how the town looks, so it is yours."""
        if not isinstance(args.get("fire"), bool):
            raise YouError("Fire on the roofs is on or off")
        self.machine.fire = args["fire"]
        settings.save(self.machine)
        self.host.on_change()
        return self.snapshot()

    def _quiet(self, args: dict) -> dict[str, Any]:
        """Quiet hours on (the ones kept, else 23:00 to the morning) or off, from the sun and moon in the HUD."""
        if not isinstance(args.get("on"), bool):
            raise YouError("Quiet hours are on or off")
        self.machine.quiet = (self.machine.quiet or schedule.DEFAULT_QUIET) if args["on"] else None
        settings.save(self.machine)
        self.host.on_change()
        return self.snapshot()

    def _work(self, args: dict) -> dict[str, Any]:
        """The working hours: {"start": "10:00", "end": "19:00"} sets them, {"on": false} turns them off."""
        if args.get("on") is False:
            self.machine.work = None
        else:
            span = schedule.Span.parse(str(args.get("start", "")), str(args.get("end", "")))
            if span is None:
                raise YouError("Working hours are a start and an end, half an hour apart at least")
            self.machine.work = span
        settings.save(self.machine)
        self._was_at_work = self.at_work()
        self.host.on_change()
        return self.snapshot()

    def _dnd(self, args: dict) -> dict[str, Any]:
        what = args.get("dnd")
        if what not in disturb.CHOICES:
            raise YouError(f"Do not disturb is one of {', '.join(disturb.CHOICES)}")
        was = self.holds()
        disturb.choose(self.machine, what)
        settings.save(self.machine)
        if self.holds() and not was:
            self._start()
            self.summary = None
        elif was and not self.holds():
            self._end()
        self.host.on_change()
        return self.snapshot()

    def _seen(self, args: dict) -> None:
        self.summary = None
        self.host.on_change()

    def commands(self) -> dict[str, Callable[[dict], Any]]:
        return {"you.look": self._look, "you.dnd": self._dnd, "you.fire": self._fire, "you.seen": self._seen,
                "you.quiet": self._quiet, "you.work": self._work}
