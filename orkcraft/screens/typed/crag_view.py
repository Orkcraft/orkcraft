"""🪨 The Tally Crag: telemetry carved in stone.

A dashboard of charts, each from a source: quotas used, spend, tokens, runs, busy orcs, tasks per
column, CPU load, or numbers that come by road (realm/metrics.py). Vertical bars are the source over
the window (1h, 24h, 7d), horizontal bars break it down (⇅ flips the chart in front, ⟳ brings the
next one; with one chart ⟳ charts the next source). A value that climbs over `warn` or `crit` sends
`charts.threshold`.

The work — the charts, sampling, carving, the thresholds — is the building's worker's
(core/workers/crag.py). The view draws every chart and tells the worker what only the TUI knows:
busy orcs and the quotas (its `probe`), once a minute.
"""
from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Static

from orkcraft.core.workers.crag import CragWorker
from orkcraft.realm import metrics
from orkcraft.widgets import bars
from orkcraft.screens.typed.base import TypedView

SAMPLE_S = 60.0


class CragView(TypedView):
    TYPE = "crag"
    UI_PANES = {"head": "#crag-head", "charts": "#crag-scroll", "crossings": "#crag-crossings"}

    @property
    def worker(self) -> CragWorker:
        return super().worker

    # -- the worker's state, as the view's own (tests and other views read these) ------------------

    @property
    def series(self) -> metrics.Series | None:
        """The chart in front's series."""
        return self.worker.series.get(self.worker.front())

    @property
    def chart(self) -> metrics.Chart | None:
        charts, i = self.worker.charts(), self.worker.front()
        return charts[i] if 0 <= i < len(charts) else None

    @property
    def source(self) -> str:
        c = self.chart
        return c.source if c is not None else ""

    @property
    def orientation(self) -> str:
        c = self.chart
        return c.orientation if c is not None else "vertical"

    # -- the view -------------------------------------------------------------------------------

    def compose_body(self) -> ComposeResult:
        yield Static("", id="crag-head", classes="typed-head")
        with Horizontal(classes="typed-row"):
            with VerticalScroll(id="crag-scroll", classes="typed-detail"):
                yield Static("", id="crag-chart")
            with VerticalScroll(id="crag-crossings", classes="typed-list"):
                yield Static("", id="crag-history")

    def on_mount(self) -> None:
        self.worker.probe = self.probe
        self.tick()
        self.set_interval(SAMPLE_S, self.tick)
        self.apply_ui()

    def tick(self) -> None:
        self.worker.tick()

    def sample(self) -> None:
        self.worker.sample()

    def refresh_data(self) -> None:
        self.worker.refresh()

    def receive(self, payload, title: str, markdown: str) -> None:
        """A number by road is a sample of the `road` source (the worker takes it)."""
        self.worker.receive(payload, title, markdown)

    def probe(self) -> dict:
        """What only the TUI knows: busy orcs (the roster and every Barracks) and the quotas read."""
        app = self.app
        roster = getattr(app, "roster", None)
        busy = roster.active if roster is not None else 0
        from orkcraft.screens.typed.pool_view import PoolView
        busy += sum(1 for v in app.query(PoolView) for o in v.state.orcs if o.status == "working")
        limits = []
        from orkcraft.screens.limits_view import LimitsView
        for lv in app.query(LimitsView):
            for lim in lv.limits or []:
                if lim.remaining is not None:
                    limits.append((f"{lim.provider} {lim.group or lim.window}", (1 - lim.remaining) * 100))
        return {"orcs": busy, "limits": limits}

    def redraw(self) -> None:
        try:
            head, chart = self.query_one("#crag-head", Static), self.query_one("#crag-chart", Static)
        except Exception:
            return
        w = self.worker
        pairs = [(i, c, w.series.get(i)) for i, c in w.shown("full")]
        front = w.front()
        head.update(Text(f"{len(pairs)} chart{'s' if len(pairs) != 1 else ''}"
                         + (f" · window {w.window}" if w.window else "") + "  ⇅ flips · ⟳ next", style="dim"))
        width = max((self.size.width or 80) - 4, 20)
        out = Text()
        for i, c, s in pairs:
            if s is None:
                continue
            if out:
                out.append("\n\n")
            out.append_text(Text.assemble(("▶ " if i == front and len(pairs) > 1 else "", "bold"),
                                          (f"{c.name} ", "bold"),
                                          (f"({s.unit}) · {w.window or c.window} · {c.orientation} · now "
                                           f"{bars.fmt(s.now)} · {c.show}", "dim"),
                                          (f" · {s.note}" if s.note else "", "dim"), "\n"))
            if c.orientation == "horizontal" or not s.buckets:
                out.append_text(bars.hbars(s.parts or [("—", 0.0)], width, s.scale, c.warn, c.crit, 16))
                continue
            out.append_text(bars.vbars([v for _, v in s.buckets], 10, None, s.scale, c.warn, c.crit))
            out.append("\n")
            out.append(" ".join(lab for lab, _ in s.buckets[:: max(1, len(s.buckets) // 6)]), style="dim")
        chart.update(out)
        history = Text("threshold crossings\n", style="dim")
        for x in w.crossings(30):
            history.append(f"{str(x.get('at', ''))[5:16].replace('T', ' ')} ", style="dim")
            history.append(f"{x.get('chart', '')} {bars.fmt(x.get('value'))} ≥ {bars.fmt(x.get('line'))}\n",
                           style="bold red" if x.get("level") == "critical" else "yellow")
        try:
            self.query_one("#crag-history", Static).update(history if w.crossings(1) else Text("no crossings yet", style="dim"))
        except Exception:
            pass

    # -- the hut ----------------------------------------------------------------------------------

    def mini_status(self) -> list[str]:
        return self._hut_lines(22)

    def hut_lines(self, widths: list[int]) -> list[str]:
        return self._hut_lines(max(widths[0] - 3, 6) if widths else 22)    # the frame's text width

    def _hut_lines(self, w: int) -> list[str]:
        s, c = self.series, self.chart
        if s is None or c is None:
            return ["carving…"]
        lines = [f"{c.name} {bars.fmt(s.now)} {s.unit}".strip()]
        if c.orientation == "vertical" and s.buckets:
            chart = bars.vbars([v for _, v in s.buckets], 6, w, s.scale, c.warn, c.crit)
            lines += [ln.plain for ln in chart.split("\n")]
        else:
            top = s.parts[:6]
            hb = bars.hbars(top, w + 2, s.scale, c.warn, c.crit, 4) if top else Text(s.note or "—")
            lines += [ln.plain for ln in hb.split("\n")]
        return lines

    def quick_action(self, action_id: str) -> bool:
        if action_id == "crag.flip":
            self.worker.flip()
            return True
        if action_id == "crag.next":
            self.worker.next()
            return True
        return False
