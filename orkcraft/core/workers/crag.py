"""🪨 The Tally Crag's work: a dashboard of charts carved from the town's numbers (realm/metrics.py).

Each chart has a source (quotas used, spend, tokens, runs, busy orks, tasks per lane, CPU load, or
numbers that come by road), a window, an orientation, `warn` / `crit` lines and where it shows
(`all`, `command`, `full`); the keeper writes them from plain words into the `charts` setting. A
Crag without one has a single chart, from its old settings (`source`, `orientation`, `window`,
`warn`, `crit`).

`tick()` samples what is sampled (CPU; busy orks and quotas through the face's `probe`) and
carves every chart again; a value that climbs over a line sends `charts.threshold` once per climb
and is kept in the history of crossings. Flip turns the chart in front over, Next brings the next
chart to the front (with one chart: charts the next source).
"""
from __future__ import annotations

import datetime as dt
import json
import os
from typing import Callable

from orkcraft.core.workers import Worker
from orkcraft.realm import metrics
from orkcraft.realm.metrics import Chart

CROSSINGS_KEEP = 200
LEVELS = ("ok", "warning", "critical")


def fmt(v: float | None) -> str:
    """A value as the Crag says it (widgets/bars.py `fmt`, the TUI's): 1.5, 12, 3.2k, — for none."""
    if v is None:
        return "—"
    if abs(v) >= 1000:
        return f"{v / 1000:.1f}k"
    if v == int(v):
        return str(int(v))
    return f"{v:.2f}" if abs(v) < 10 else f"{v:.1f}"


class CragWorker(Worker):
    TYPE = "crag"
    ERROR_IS_FAILURE = False            # its ERROR is a reading over its red line: what it is for

    def __init__(self, town, building_id: str) -> None:
        super().__init__(town, building_id)
        self.series: dict[int, metrics.Series] = {}       # chart index → what it shows now
        self.levels: dict[str, int] = {}                  # chart line → 0 fine, 1 over warn, 2 over crit
        self.current = 0                                  # the chart in front (the Command Card, Flip)
        self.window = ""                                  # the dashboard's window ("" each chart's own)
        # What only the face knows: {"orcs": busy orks, "limits": [(label, % used)]} (the TUI's roster
        # and quotas); None samples CPU and the town's own numbers only.
        self.probe: Callable[[], dict] | None = None

    def start(self) -> None:
        self.tick()

    # -- its charts -----------------------------------------------------------------------------

    def charts(self) -> list[Chart]:
        cfg = self.config
        if isinstance(cfg.get("charts"), list) and cfg["charts"]:
            return metrics.parse_charts(cfg["charts"])[0]
        warn, crit = cfg.get("warn"), cfg.get("crit")
        return [Chart(str(cfg.get("source") or "spend"), "", str(cfg.get("window") or "24h"),
                      str(cfg.get("orientation") or "vertical"),
                      float(warn) if isinstance(warn, (int, float)) else None,
                      float(crit) if isinstance(crit, (int, float)) else None)]

    def shown(self, view: str) -> list[tuple[int, Chart]]:
        """The charts (with their index) that show in `view`: closed, command or full."""
        return [(i, c) for i, c in enumerate(self.charts()) if c.shows_in(view)]

    def front(self) -> int:
        """The index of the chart in front of the Command Card."""
        ids = [i for i, _ in self.shown("command")]
        if not ids:
            return -1
        return self.current if self.current in ids else ids[0]

    @staticmethod
    def level(c: Chart, value: float | None) -> int:
        if value is None:
            return 0
        if c.crit is not None and value >= c.crit:
            return 2
        return 1 if c.warn is not None and value >= c.warn else 0

    # -- sampling and carving -------------------------------------------------------------------

    def tick(self) -> None:
        self.sample()
        self.refresh()

    def sample(self) -> None:
        try:
            metrics.sample(self.state_dir, "cpu", os.getloadavg()[0])
        except OSError:
            pass
        probe = self.probe() if self.probe is not None else {}
        if probe.get("orcs") is not None:
            metrics.sample(self.state_dir, "orcs", float(probe["orcs"]))
        for label, used in probe.get("limits") or []:
            metrics.sample(self.state_dir, "limits", round(float(used), 1), str(label)[:24])

    def tasks(self) -> dict[str, int]:
        """Tasks per lane of every Task Fields in the town (their workers read the boards)."""
        from orkcraft.core.workers import type_id
        from orkcraft.realm.tasklist import LABELS
        counts: dict[str, int] = {}
        for bid, spec in list(self.town.custom_specs.items()):
            if type_id(spec) != "fields":
                continue
            w = self.town.worker(bid)
            for t in getattr(w, "tasks", []):
                counts[LABELS[t.column]] = counts.get(LABELS[t.column], 0) + 1
        return counts

    def carve(self, c: Chart, window: str = "", now: dt.datetime | None = None) -> metrics.Series:
        return metrics.series(c.source, self.repo_root, self.state_dir, window or c.window, now,
                              tasks=self.tasks() if c.source == "tasks" else None)

    def refresh(self, now: dt.datetime | None = None) -> None:
        """Carve every chart again; a value over its line sends `charts.threshold` once per climb."""
        charts = self.charts()
        self.series = {}
        for i, c in enumerate(charts):
            s = self.carve(c, "", now)
            self._check(c, s, now)
            self.series[i] = self.carve(c, self.window, now) if self.window and self.window != c.window else s
        self.changed()

    def _check(self, c: Chart, s: metrics.Series, now: dt.datetime | None) -> None:
        key = metrics.chart_line(c)
        level = self.level(c, s.now)
        if level > self.levels.get(key, 0):
            line = c.crit if level == 2 else c.warn
            text = f"{c.name} {fmt(s.now)} {s.unit} ≥ {fmt(line)} ({LEVELS[level]})".replace("  ", " ")
            self.emit("charts.threshold", text, c.name)
            self._keep_crossing(c, s.now, line, level, now)
        self.levels[key] = level

    def _keep_crossing(self, c: Chart, value, line, level: int, now: dt.datetime | None) -> None:
        row = {"at": (now or dt.datetime.now()).isoformat(timespec="seconds"), "chart": c.name,
               "source": c.source, "value": value, "line": line, "level": LEVELS[level]}
        path = self.state_dir / "crossings.jsonl"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            rows = path.read_text(encoding="utf-8").splitlines()[-(CROSSINGS_KEEP - 1):] if path.exists() else []
            path.write_text("".join(r + "\n" for r in rows) + json.dumps(row) + "\n", encoding="utf-8")
        except OSError:
            pass

    def crossings(self, limit: int = 50) -> list[dict]:
        """The latest crossings of a warn or crit line, newest first."""
        try:
            lines = (self.state_dir / "crossings.jsonl").read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        out = []
        for line in reversed(lines[-limit:]):
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
        return out

    def receive(self, payload, title: str, markdown: str) -> None:
        """A number by road is a sample of the `road` source."""
        n = metrics.first_number(f"{payload.value}")
        if n is not None:
            metrics.sample(self.state_dir, "road", n, (payload.title or title)[:24])
            if any(c.source == "road" for c in self.charts()):
                self.refresh()

    # -- acts -----------------------------------------------------------------------------------

    def _save_charts(self, charts: list[Chart]) -> bool:
        return self.save_config({"charts": [metrics.chart_line(c) for c in charts]})

    def _uses_charts(self) -> bool:
        return bool(self.config.get("charts"))

    def flip(self, index: int | None = None) -> bool:
        """Vertical bars (over time) ⇄ horizontal bars (broken down), of the chart in front or `index`."""
        charts = self.charts()
        i = self.front() if index is None else index
        if not 0 <= i < len(charts):
            return False
        c = charts[i]
        c.orientation = "horizontal" if c.orientation == "vertical" else "vertical"
        ok = self._save_charts(charts) if self._uses_charts() else self.save_config({"orientation": c.orientation})
        if ok:
            self.refresh()
        return ok

    def next(self) -> bool:
        """The next chart to the front; with one chart, it charts the next source."""
        ids = [i for i, _ in self.shown("command")]
        if len(ids) > 1:
            at = ids.index(self.front())
            self.current = ids[(at + 1) % len(ids)]
            self.changed()
            return True
        charts = self.charts()
        i = ids[0] if ids else 0
        if not charts:
            return False
        c = charts[i]
        k = metrics.SOURCES.index(c.source) if c.source in metrics.SOURCES else -1
        c.source = metrics.SOURCES[(k + 1) % len(metrics.SOURCES)]
        ok = self._save_charts(charts) if self._uses_charts() else self.save_config({"source": c.source})
        if ok:
            self.refresh()
        return ok

    def set_show(self, index: int, show: str) -> bool:
        """Where chart `index` shows: all, command or full."""
        charts = self.charts()
        if show not in metrics.SHOWS or not 0 <= index < len(charts):
            return False
        charts[index].show = show
        ok = self._save_charts(charts)
        if ok:
            self.changed()
        return ok

    def set_window(self, window: str) -> None:
        """The dashboard's window over every chart ("" each chart's own)."""
        self.window = window if window in metrics.WINDOWS else ""
        self.refresh()

    # -- the hut --------------------------------------------------------------------------------

    def status(self) -> str:
        return "ERROR" if any(self.level(c, s.now) == 2 for c, s in self._pairs()) else ""

    def _pairs(self) -> list[tuple[Chart, metrics.Series]]:
        charts = self.charts()
        return [(charts[i], s) for i, s in sorted(self.series.items()) if i < len(charts)]

    def mini_status(self) -> list[str]:
        pairs = [(c, s) for c, s in self._pairs() if c.shows_in("closed")] or self._pairs()[:1]
        if not pairs:
            return ["carving…"]
        return [f"{c.name} {fmt(s.now)} {s.unit}".strip() for c, s in pairs[:3]]
