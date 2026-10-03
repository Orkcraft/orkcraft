"""🪨 The Tally Crag: telemetry carved in stone.

One source per Crag (`source`; ⟳ moves to the next): quotas used, spend, tokens, runs, busy orcs,
tasks per column, CPU load, or numbers that come by road (realm/metrics.py). Vertical bars are the
source over the window (`window`: 1h, 24h, 7d), horizontal bars break it down (⇅ flips). The Crag
samples quotas, busy orcs and CPU once a minute. A value that climbs over `warn` or `crit` sends
`charts.threshold`.
"""
from __future__ import annotations

import os

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Static

from orkcraft.realm import metrics
from orkcraft.widgets import bars
from orkcraft.screens.typed.base import TypedView

SAMPLE_S = 60.0


class CragView(TypedView):
    TYPE = "crag"

    def __init__(self, *a, **kw) -> None:
        super().__init__(*a, **kw)
        self.series: metrics.Series | None = None
        self._level = 0                     # 0 fine, 1 over warn, 2 over crit

    @property
    def source(self) -> str:
        return str(self.config.get("source") or "spend")

    @property
    def orientation(self) -> str:
        return str(self.config.get("orientation") or "vertical")

    @property
    def window(self) -> str:
        return str(self.config.get("window") or "24h")

    def _limit(self, key: str) -> float | None:
        v = self.config.get(key)
        return float(v) if isinstance(v, (int, float)) else None

    def compose_body(self) -> ComposeResult:
        yield Static("", id="crag-head", classes="typed-head")
        with VerticalScroll():
            yield Static("", id="crag-chart")

    def on_mount(self) -> None:
        self.sample()
        self.refresh_data()
        self.set_interval(SAMPLE_S, self.tick)

    def tick(self) -> None:
        self.sample()
        self.refresh_data()

    # -- sampling -----------------------------------------------------------------------------------

    def sample(self) -> None:
        app = self.app
        try:
            metrics.sample(self.state_dir, "cpu", os.getloadavg()[0])
        except OSError:
            pass
        roster = getattr(app, "roster", None)
        busy = roster.active if roster is not None else 0
        from orkcraft.screens.typed.pool_view import PoolView
        busy += sum(1 for v in app.query(PoolView) for o in v.state.orcs if o.status == "working")
        metrics.sample(self.state_dir, "orcs", float(busy))
        from orkcraft.screens.limits_view import LimitsView
        for lv in app.query(LimitsView):
            for lim in lv.limits or []:
                if lim.remaining is not None:
                    metrics.sample(self.state_dir, "limits", round((1 - lim.remaining) * 100, 1),
                                   f"{lim.provider} {lim.group or lim.window}"[:24])

    def _tasks(self) -> dict[str, int]:
        from orkcraft.realm.tasklist import LABELS
        from orkcraft.screens.typed.tasks_view import TasksView
        counts: dict[str, int] = {}
        for v in self.app.query(TasksView):
            for t in v.tasks:
                counts[LABELS[t.column]] = counts.get(LABELS[t.column], 0) + 1
        return counts

    def receive(self, payload, title: str, markdown: str) -> None:
        """A number by road is a sample of the `road` source."""
        n = metrics.first_number(f"{payload.value}")
        if n is not None:
            metrics.sample(self.state_dir, "road", n, (payload.title or title)[:24])
            if self.source == "road":
                self.refresh_data()

    # -- drawing ------------------------------------------------------------------------------------

    def refresh_data(self) -> None:
        self.series = metrics.series(self.source, self._get_repo_root(), self.state_dir, self.window,
                                     tasks=self._tasks() if self.source == "tasks" else None)
        self._check_threshold()
        self._render_chart()

    def _check_threshold(self) -> None:
        s, warn, crit = self.series, self._limit("warn"), self._limit("crit")
        if s is None or s.now is None or (warn is None and crit is None):
            return
        level = 2 if crit is not None and s.now >= crit else 1 if warn is not None and s.now >= warn else 0
        if level > self._level:
            line = crit if level == 2 else warn
            self.emit("charts.threshold", f"{self.source} {bars.fmt(s.now)} {s.unit} ≥ {bars.fmt(line)}"
                                          f" ({'critical' if level == 2 else 'warning'})", self.source)
        self._level = level

    def _render_chart(self) -> None:
        s = self.series
        try:
            head, chart = self.query_one("#crag-head", Static), self.query_one("#crag-chart", Static)
        except Exception:
            return
        if s is None:
            return
        head.update(Text.assemble((f"{self.source} ", "bold"), (f"({s.unit}) · {self.window} · {self.orientation}"
                                                                f" · now {bars.fmt(s.now)}", "dim"),
                                  (f" · {s.note}" if s.note else "", "dim"),
                                  ("  ⇅ flips · ⟳ next source", "dim")))
        warn, crit = self._limit("warn"), self._limit("crit")
        width = max((self.size.width or 80) - 4, 20)
        if self.orientation == "horizontal" or not s.buckets:
            chart.update(bars.hbars(s.parts or [("—", 0.0)], width, s.scale, warn, crit, 16))
            return
        values = [v for _, v in s.buckets]
        body = bars.vbars(values, 10, None, s.scale, warn, crit)
        labels = Text(" ".join(lab for lab, _ in s.buckets[:: max(1, len(s.buckets) // 6)]), style="dim")
        chart.update(Text.assemble(body, "\n", labels))

    # -- the hut ----------------------------------------------------------------------------------

    def mini_status(self) -> list[str]:
        return self._hut_lines(22)

    def hut_lines(self, widths: list[int]) -> list[str]:
        return self._hut_lines(max(widths[0] - 3, 6) if widths else 22)    # the frame's text width

    def _hut_lines(self, w: int) -> list[str]:
        s = self.series
        if s is None:
            return ["carving…"]
        warn, crit = self._limit("warn"), self._limit("crit")
        lines = [f"{self.source} {bars.fmt(s.now)} {s.unit}".strip()]
        if self.orientation == "vertical" and s.buckets:
            chart = bars.vbars([v for _, v in s.buckets], 6, w, s.scale, warn, crit)
            lines += [ln.plain for ln in chart.split("\n")]
        else:
            top = s.parts[:6]
            hb = bars.hbars(top, w + 2, s.scale, warn, crit, 4) if top else Text(s.note or "—")
            lines += [ln.plain for ln in hb.split("\n")]
        return lines

    def quick_action(self, action_id: str) -> bool:
        if action_id == "crag.flip":
            if self.save_config({"orientation": "horizontal" if self.orientation == "vertical" else "vertical"}):
                self.refresh_data()
            return True
        if action_id == "crag.next":
            i = metrics.SOURCES.index(self.source) if self.source in metrics.SOURCES else -1
            if self.save_config({"source": metrics.SOURCES[(i + 1) % len(metrics.SOURCES)]}):
                self._level = 0
                self.refresh_data()
            return True
        return False
