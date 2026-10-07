"""🪨 Tally Crag in the GUI: a dashboard of charts. Every act is the worker's (core/workers/crag.py);
the charts themselves are written by its keeper from plain words (js/keeper.js)."""
from __future__ import annotations

import time

from orkcraft.core.workers.crag import fmt
from orkcraft.gui.views import ActError, text
from orkcraft.realm import metrics

REFRESH_S = 60.0              # as the TUI: it samples and carves once a minute
THUMBS = 4                    # charts on the hut card
THUMB_BARS = 12               # bars in a thumbnail


def refresh(w) -> None:
    w.tick()


def attach(w, host) -> None:
    """The host hands the worker what only the face knows (the worker's `probe`), as the TUI's view does."""
    w.probe = lambda: probe(host)


def probe(host) -> dict:
    """Busy orks (the roster's, and every Barracks' working orks) and the quotas the Town Hall read
    (`% used`): the TUI's `CragView.probe`, from what the GUI host has."""
    busy = host.muster.roster.active
    for other in list(host.town.workers.values()):
        if getattr(other, "TYPE", "") == "barracks":
            busy += sum(1 for o in other.state.orcs if o.status == "working")
    limits = [(f"{x.provider} {x.group or x.window}", (1 - x.remaining) * 100)
              for x in host.limits() if x.remaining is not None]
    return {"orcs": busy, "limits": limits}


def _values(s: metrics.Series, c: metrics.Chart) -> list[float]:
    return [v for _, v in s.buckets] if c.orientation == "vertical" and s.buckets else [v for _, v in s.parts]


def _thin(values: list[float], n: int) -> list[float]:
    """At most `n` values: neighbours merged (their max)."""
    if len(values) <= n:
        return values
    step = len(values) / n
    return [max(values[int(i * step):max(int((i + 1) * step), int(i * step) + 1)]) for i in range(n)]


def card(w) -> dict:
    """Closed (docs/design/building-views.md): thumbnails of the charts set to `all`, without numbers; the last
    crossing of a line and when."""
    out = []
    for i, c in w.shown("closed")[:THUMBS]:
        s = w.series.get(i)
        if s is None:
            continue
        out.append({"title": c.name, "values": [round(v, 3) for v in _thin(_values(s, c), THUMB_BARS)],
                    "scale": s.scale, "warn": c.warn, "crit": c.crit, "level": w.level(c, s.now)})
    last = w.crossings(1)
    x = last[0] if last else None
    at = str(x.get("at") or "").replace("T", " ") if x else ""
    return {"charts": out, "last": {"chart": str(x.get("chart", "")), "level": str(x.get("level", "")),
                                    "at": at[11:16] if at[:10] == time.strftime("%Y-%m-%d") else at[5:10]} if x else None}


def _chart(w, i: int, c: metrics.Chart) -> dict:
    s = w.series.get(i) or metrics.Series(c.source, metrics.UNITS.get(c.source, ""))
    return {"index": i, "title": c.name, "source": c.source, "unit": s.unit, "window": w.window or c.window,
            "orientation": c.orientation, "show": c.show, "warn": c.warn, "crit": c.crit, "scale": s.scale,
            "now": s.now, "now_text": f"{fmt(s.now)} {s.unit}".strip(), "note": s.note,
            "level": w.level(c, s.now), "line": metrics.chart_line(c),
            "buckets": [[lab, v] for lab, v in s.buckets], "parts": [[lab, v] for lab, v in s.parts[:12]]}


def detail(w) -> dict:
    charts = [_chart(w, i, c) for i, c in enumerate(w.charts())]
    errors = metrics.parse_charts(w.config.get("charts") or [])[1]
    return {"charts": charts, "front": w.front(), "window": w.window, "windows": list(metrics.WINDOWS),
            "shows": list(metrics.SHOWS), "crossings": w.crossings(30), "errors": errors}


def _index(w, args: dict) -> int:
    try:
        i = int(args.get("chart", -1))
    except (TypeError, ValueError):
        raise ActError("Which chart?") from None
    if not 0 <= i < len(w.charts()):
        raise ActError("That chart is gone from the dashboard")
    return i


def _flip(w, args: dict) -> bool:
    return w.flip(_index(w, args) if "chart" in args else None)


def _next(w, args: dict) -> bool:
    return w.next()


def _show(w, args: dict) -> bool:
    show = text(args, "show", 20)
    if show not in metrics.SHOWS:
        raise ActError(f"A chart shows in {', '.join(metrics.SHOWS)}")
    return w.set_show(_index(w, args), show)


def _window(w, args: dict) -> str:
    window = text(args, "window", 10)
    if window and window not in metrics.WINDOWS:
        raise ActError(f"A window is {', '.join(metrics.WINDOWS)}")
    w.set_window(window)
    return w.window


# The type's quick actions (realm/catalog.py) by their ids, then its own.
ACTS = {"crag.flip": _flip, "crag.next": _next, "flip": _flip, "show": _show, "window": _window}
