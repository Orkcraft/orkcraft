"""Carts on roads and coin flashes (roads v2).

A cart is a real event only — one `roads.Cart` from the engine — travelling from the exit gate
to the entry gate along the road's cells. It is a rock 🪨 (two cells, `realm/modes.py`). Its colour
(the rock's ground) is the cargo's status:

    sent / delivered   the road's brown, arrives and vanishes
    filtered           grey: a few cells out of the source, then turns back (the filter said no)
    held               yellow: waits at the entry gate (a script not reviewed yet, or changed since)
    error              red: stops at the entry gate (the handler failed on it)

A cart that reaches a handler still running waits at the entry gate: a **jam**. When carts pile up
(or more than `MAX_MOVING` would travel one road at once) a counter `🛒×N` at the entry gate
replaces the stream. Visibility (`preferences.carts`): off · selected (the active building's and
the selected road's, default) · all. Nothing redraws while nothing moves.

Coins are not cargo: `flash_coin` shows 🪙 at a building's frame for a moment when its agent spends.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from rich.text import Text
from textual import events
from textual.message import Message
from textual.widgets import Static

from orkcraft.realm import modes
from orkcraft.widgets.road_layer import ROAD_SELECTED, road_key

if TYPE_CHECKING:
    from orkcraft.wm.desktop import Desktop

FPS = 8
MAX_MOVING = 6              # per road; more become the 🛒×N counter
TRAVEL_TICKS = 12           # a whole road in about 1.5 s, however long it is
FILTERED_CELLS = 3          # how far a filtered cart gets before turning back
WAIT_TICKS = {"held": 2 * FPS, "error": 2 * FPS, "jam": 10 * FPS, "arrived": 2}
COUNTER_QUIET_TICKS = 3 * FPS
COIN_TICKS = 12
COIN = "🪙"
# A rock keeps its own colours: the status shows as the ground under it (none on the way).
ROCK_STYLE = {"filtered": "on #4a4a4a", "held": "on #8a6d0b", "error": "on #7f1d1d"}


def cart_look(status: str) -> Text:
    """The cart: a 🪨 on the ground of its status."""
    return Text(modes.ROCK, style=ROCK_STYLE.get(status, ""))


class CartClicked(Message):
    def __init__(self, cart) -> None:
        super().__init__()
        self.cart = cart


class CartSprite(Static):
    DEFAULT_CSS = """
    CartSprite { layer: roads; position: absolute; width: 1; height: 1; }
    """

    def __init__(self, cart, status: str) -> None:
        super().__init__(cart_look(status), markup=False, classes="road-cart")
        self.cart = cart
        self.status = status
        self.styles.width = 2

    def set_status(self, status: str) -> None:
        self.status = status
        self.update(cart_look(status))

    def on_click(self, event: events.Click) -> None:
        event.stop()
        self.post_message(CartClicked(self.cart))


class Counter(Static):
    DEFAULT_CSS = """
    Counter { layer: roads; position: absolute; width: auto; height: 1; }
    """


class Coin(Static):
    DEFAULT_CSS = """
    Coin { layer: roads; position: absolute; width: 2; height: 1; }
    """


@dataclass
class Moving:
    cart: object                 # roads.Cart
    key: str                     # road key on the canvas
    status: str
    sprite: CartSprite
    pos: float = 0.0             # index into the path cells
    back: bool = False           # a filtered cart on its way back
    wait: int = 0                # ticks left at the entry gate
    waiting: str = ""            # held | error | jam | arrived


@dataclass
class Traffic:
    """Owned by the Desktop: which carts move where, the counters and the coins."""
    desktop: "Desktop"
    moving: list[Moving] = field(default_factory=list)
    counters: dict[str, tuple[int, int, Counter]] = field(default_factory=dict)   # key → (n, quiet, widget)
    coins: dict[str, tuple[int, Coin]] = field(default_factory=dict)             # building → (ticks, widget)

    @property
    def busy(self) -> bool:
        return bool(self.moving or self.counters or self.coins)

    # -- what is shown --------------------------------------------------------------------------

    def mode(self) -> str:
        scroll = self.desktop.scroll
        return scroll.preferences.get("carts", "selected") if scroll is not None else "selected"

    def visible_road(self, key: str) -> bool:
        mode = self.mode()
        if mode == "off" or key not in self.desktop.road_paths:
            return False
        if mode == "all" or key == self.desktop.selected_road:
            return True
        active = self.desktop.active
        if active is None and getattr(self.desktop, "town_active", False):
            return True   # the town with nothing open is the overview: every road's carts
        p = self.desktop.road_paths[key]
        return active is not None and not active.hidden and active.window_id in (p.source, p.target)

    # -- carts -------------------------------------------------------------------------------------

    def launch(self, cart) -> None:
        key = road_key(cart.target, cart.road_id)
        if not self.visible_road(key):
            return
        on_road = [m for m in self.moving if m.key == key]
        if len(on_road) >= MAX_MOVING:
            self._count(key)
            return
        sprite = CartSprite(cart, cart.status)
        m = Moving(cart, key, cart.status, sprite)
        self.moving.append(m)
        self._place(m)
        self.desktop.mount(sprite)
        self.desktop.traffic_changed()

    def mark_error(self, target_id: str, road_ids: list[str]) -> None:
        """A handler failed: its carts waiting at the gate turn red (or one red cart shows up there)."""
        keys = {road_key(target_id, r) for r in road_ids}
        hit = False
        for m in self.moving:
            if m.key in keys and m.waiting in ("jam", "arrived", ""):
                m.status, m.waiting, m.wait = "error", "error", WAIT_TICKS["error"]
                m.sprite.set_status("error")
                hit = True
        if not hit:
            for key in keys:
                p = self.desktop.road_paths.get(key)
                if p is None or not self.visible_road(key):
                    continue
                cart = type("ErrorCart", (), {"road_id": key.split(":", 1)[1], "target": target_id,
                                              "source": p.source, "status": "error", "payload": None, "detail": ""})()
                sprite = CartSprite(cart, "error")
                m = Moving(cart, key, "error", sprite, pos=len(p.cells) - 1, waiting="error", wait=WAIT_TICKS["error"])
                self.moving.append(m)
                self._place(m)
                self.desktop.mount(sprite)
        self.desktop.traffic_changed()

    def _count(self, key: str) -> None:
        n, _, widget = self.counters.get(key, (0, 0, None))
        if widget is None:
            widget = Counter("", markup=False)
            self.desktop.mount(widget)
        n += 1
        self.counters[key] = (n, COUNTER_QUIET_TICKS, widget)
        self._place_counter(key, n, widget)
        self.desktop.traffic_changed()

    def _place_counter(self, key: str, n: int, widget: Counter) -> None:
        p = self.desktop.road_paths.get(key)
        if p is None:
            return
        label = f"🛒×{n}"
        ox, oy = p.entry.outside
        x = ox - len(label) - 1 if p.entry.side == "left" else ox + 1 if p.entry.side == "right" else ox
        y = oy - 1 if p.entry.side in ("left", "right") else oy
        width = self.desktop.dims[0]
        widget.styles.offset = (max(0, min(x, width - len(label) - 1)), max(0, y))
        widget.update(Text(label, style=f"bold {ROAD_SELECTED}"))

    def _place(self, m: Moving) -> None:
        p = self.desktop.road_paths.get(m.key)
        if p is None or not p.cells:
            m.sprite.display = False
            return
        i = max(0, min(int(m.pos), len(p.cells) - 1))
        x, y = p.cells[i]
        m.sprite.styles.offset = (x, y)
        m.sprite.display = (x, y) not in p.covered or m.key == self.desktop.selected_road

    def _handler_running(self, cart) -> bool:
        app = getattr(self.desktop, "app", None)
        engine = getattr(app, "roads", None)
        scroll = self.desktop.scroll
        if engine is None or scroll is None:
            return False
        b = scroll.building(cart.target)
        road = b.road(cart.road_id) if b else None
        if road is None or road.handler is None:
            return False
        st = engine.states.get((cart.target, road.handler))
        return bool(st and st.running)

    def tick(self) -> None:
        done: list[Moving] = []
        for m in self.moving:
            p = self.desktop.road_paths.get(m.key)
            if p is None or not self.visible_road(m.key):
                done.append(m)
                continue
            last = len(p.cells) - 1
            if m.waiting:
                if m.waiting == "jam" and not self._handler_running(m.cart):
                    m.wait = 0
                m.wait -= 1
                if m.wait <= 0:
                    done.append(m)
                continue
            step = max(1.0, len(p.cells) / TRAVEL_TICKS)
            if m.status == "filtered":
                m.pos += -1 if m.back else 1        # one cell a frame: the turn-back must be seen
                if not m.back and m.pos >= min(FILTERED_CELLS, last):
                    m.back = True
                if m.back and m.pos <= 0:
                    done.append(m)
            else:
                m.pos = min(m.pos + step, last)
                if m.pos >= last:
                    if m.status in ("held", "error"):
                        m.waiting = m.status
                    elif self._handler_running(m.cart):
                        m.waiting = "jam"
                    else:
                        m.waiting = "arrived"
                    m.wait = WAIT_TICKS[m.waiting]
            self._place(m)
        for m in done:
            self.moving.remove(m)
            m.sprite.remove()
        # a jam: two or more carts waiting at one gate become the counter
        jams: dict[str, int] = {}
        for m in self.moving:
            if m.waiting == "jam":
                jams[m.key] = jams.get(m.key, 0) + 1
        for key, n in jams.items():
            if n >= 2:
                old, _, widget = self.counters.get(key, (0, 0, None))
                if widget is None:
                    widget = Counter("", markup=False)
                    self.desktop.mount(widget)
                self.counters[key] = (max(n, old), COUNTER_QUIET_TICKS, widget)
                self._place_counter(key, max(n, old), widget)
        for key, (n, quiet, widget) in list(self.counters.items()):
            if key in jams:
                continue
            quiet -= 1
            if quiet <= 0 or key not in self.desktop.road_paths:
                widget.remove()
                del self.counters[key]
            else:
                self.counters[key] = (n, quiet, widget)
        for bid, (ticks, coin) in list(self.coins.items()):
            ticks -= 1
            if ticks <= 0:
                coin.remove()
                del self.coins[bid]
            else:
                self.coins[bid] = (ticks, coin)

    def replaced(self) -> None:
        """The plan changed: carts keep their progress, clamped to the new paths."""
        for m in self.moving:
            self._place(m)
        for key, (n, _, widget) in self.counters.items():
            self._place_counter(key, n, widget)

    # -- coins ------------------------------------------------------------------------------------

    def flash_coin(self, building_id: str) -> None:
        if self.mode() == "off":
            return
        g = self.desktop.anchor_geom(building_id)
        if g is None or self.desktop.single:
            return
        ticks, coin = self.coins.get(building_id, (0, None))
        if coin is None:
            coin = Coin(Text(COIN), markup=False)
            self.desktop.mount(coin)
        # on a hut's fence (its lines are full of status text), inside a window's top-right corner
        top = g.y if getattr(self.desktop, "town_active", False) else g.y + 1
        coin.styles.offset = (max(g.x, g.x + g.w - 4), max(0, top))
        self.coins[building_id] = (COIN_TICKS, coin)
        self.desktop.traffic_changed()

    def clear(self) -> None:
        for m in self.moving:
            m.sprite.remove()
        for _, _, w in self.counters.values():
            w.remove()
        for _, c in self.coins.values():
            c.remove()
        self.moving.clear()
        self.counters.clear()
        self.coins.clear()
