"""The sandbox's traffic: demo carts on the demo town's roads, so the carts, the stewards' stops, the Review gate's
barrier, the catapult's launch, the task's history and the score show the real thing — and no model runs.

    traffic = Traffic(town); traffic.start()     # gui/host.py, in the demo only
    traffic.stop()

Every few seconds a cart sets off along the next road of each orkspace (round its roads, the roads into a Publisher
more often), so whichever orkspace is shown has carts on it, carrying a trail of hops with the tokens, spend and time a run like it would have recorded. A cart waits at
every Review gate (held for the person) and is sent again before it would leave the snapshot; now and then a gate sends
one back for rework to the building that made it, so it goes round again (design-system-v3.md §4c). Two weeks of accepted
results (`results`) feed the score. All of it is demo data: every hop's model is "demo", and it lives in memory only
(nothing is written to the town's logs; the demo has none).
"""
from __future__ import annotations

import datetime as dt
import random
import threading
import time

from orkcraft.core import bus
from orkcraft.realm import pipes
from orkcraft.realm.roads import Cart

EVERY_S = 3.5                    # a new cart this often
BACK_EVERY = 3                   # a Review gate sends a cart back for rework every this many ticks
STAND_S = 50 * 60                # a waiting cart is sent again before the snapshot lets it go (gui/state.py)
DEMO = "demo"                    # the model every demo hop names: never a real run
TITLES = ("Fix the login form", "Release notes v0.3", "Triage: billing mail", "Add the export button",
          "Weekly digest", "Pricing page copy", "Refactor the parser", "Answer the Jira ticket")


def _hops(town, source: str, rnd: random.Random, at: dt.datetime) -> tuple[pipes.Hop, ...]:
    """Its hop at `source`, with the tokens, spend and time a run would have recorded (a script's records no tokens)."""
    tokens = rnd.choice((0, 2400, 6800, 9100, 12500, 18000))
    return (pipes.Hop(source, orc=rnd.choice(("Grub", "Thrak", "Snaga", "Lookout")), kind="agent" if tokens else "script",
                      tokens=tokens or None, cost=round(tokens * 0.000015, 4) if tokens else None,
                      ms=rnd.randint(2, 240) * 1000, at=(at - dt.timedelta(minutes=5)).isoformat(timespec="seconds"),
                      outcome="done", model=DEMO),)


def results(now: dt.datetime | None = None, seed: int = 7) -> list[dict]:
    """Two weeks of accepted results as the event log keeps them (realm/score.py `rows`): a leaner week this week."""
    now = now or dt.datetime.now().astimezone()
    rnd, out = random.Random(seed), []
    for day in range(14):
        for _ in range(rnd.randint(2, 5)):
            base = 9500 if day < 7 else 11800
            out.append({"at": (now - dt.timedelta(days=day, hours=rnd.randint(1, 9))).isoformat(timespec="seconds"),
                        "event": "result_built", "kind": rnd.choice(("passed", "done")), "building": "demo",
                        "tokens": base + rnd.randint(-2500, 2500), "cost": None, "title": rnd.choice(TITLES)})
    return out


class Traffic:
    def __init__(self, town, seed: int = 11) -> None:
        self.town, self.rnd = town, random.Random(seed)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._turn = 0
        self._held: dict[str, float] = {}
        self._ref = 100                # each task its own ref, as real ones are: a send-back reads `round 2`, never more

    def roads(self) -> list[tuple]:
        """(source, target, road) for every road whose two buildings stand; the roads into a Publisher twice, none into a
        Review gate (its one waiting cart stays the newest there, so the gate that asks shows it waiting: `tick`)."""
        out = []
        for b in self.town.scroll.buildings:
            if b.demolished:
                continue
            for r in b.roads:
                if self.town.scroll.building(r.source) is None:
                    continue
                kind = (self.town.spec_of(b.id) or {}).get("type")
                out += [(r.source, b.id, r)] * (2 if kind == "catapult" else 0 if kind == "loot" else 1)
        return out

    def next_ref(self) -> str:
        self._ref += 1
        return str(self._ref)

    def send(self, source: str, target: str, road, status: str = "delivered", title: str = "") -> Cart:
        now = dt.datetime.now().astimezone()
        title = title or self.rnd.choice(TITLES)
        payload = pipes.Payload(kind="text", value=title, source=source, mode=road.event, title=title, ref=self.next_ref(),
                                trail=_hops(self.town, source, self.rnd, now), want="change")
        cart = Cart(road.id, source, target, status, payload, "demo", time.monotonic())
        engine = self.town.roads
        with engine._lock:
            engine.carts = (engine.carts + [cart])[-500:]
        self.town.publish(bus.CART, cart=cart)
        return cart

    def tick(self) -> None:
        """One step: in each orkspace the next road's cart, and a cart waiting at every Review gate."""
        every = self.roads()
        spaces = [set(o.buildings) for o in getattr(self.town.scroll, "orkspaces", []) or []] or [None]
        for space in spaces:
            mine = [x for x in every if space is None or (x[0] in space and x[1] in space)]
            if mine:
                source, target, road = mine[self._turn % len(mine)]
                self.send(source, target, road)
        self._turn += 1
        if self._turn % BACK_EVERY == 0:
            self.send_back()
        now = time.monotonic()
        for b in self.town.scroll.buildings:
            if b.demolished or (self.town.spec_of(b.id) or {}).get("type") != "loot" or not b.roads:
                continue
            road = b.roads[0]
            if self.town.scroll.building(road.source) is not None and now - self._held.get(b.id, -1e9) > STAND_S:
                self._held[b.id] = now
                self.send(road.source, b.id, road, title="Fix the parser")

    def send_back(self) -> list[Cart]:
        """Each Review gate hands a cart back for rework to the building its first road comes from (as a rework is
        handed back, not sent down a road: core/delivery.py `went_back`)."""
        out = []
        for b in self.town.scroll.buildings:
            if b.demolished or (self.town.spec_of(b.id) or {}).get("type") != "loot" or not b.roads:
                continue
            maker = b.roads[0].source
            if self.town.scroll.building(maker) is None:
                continue
            title = self.rnd.choice(TITLES)
            now = dt.datetime.now().astimezone()
            payload = pipes.Payload(kind="text", value=title, source=b.id, mode="loot.rework", title=title,
                                    ref=self.next_ref(), trail=_hops(self.town, maker, self.rnd, now), want="change")
            out.append(self.town.roads.sent_back(b.id, maker, payload))
        return out

    def _run(self) -> None:
        while not self._stop.wait(EVERY_S):
            try:
                self.tick()
            except Exception:              # the demo's traffic never takes the town down
                pass

    def start(self) -> None:
        self.town.demo_results = results()
        self.tick()
        self._thread = threading.Thread(target=self._run, name="demo-traffic", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
