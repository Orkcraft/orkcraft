"""Limits window: claude / agy / codex quota bars, read in the background through orkcraft.quota."""
from __future__ import annotations

import datetime as dt

from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.widget import Widget
from textual.widgets import Static

from orkcraft.sources.limits import PROVIDERS, Limit, fetch_limits

LIMITS_REFRESH_S = 10 * 60
BAR = 10
PROVIDER_STYLE = {"claude": "bold magenta", "agy": "bold blue", "codex": "bold green"}


def limit_line(lim: Limit) -> Text:
    """claude ██████░░░░ 62% 5h session ↻14:00 — what the quota is for comes before the reset."""
    t = Text(no_wrap=True, overflow="ellipsis")
    t.append(f"{lim.provider:<6} ", style=PROVIDER_STYLE.get(lim.provider, "bold"))
    if lim.error or lim.remaining is None:
        t.append(lim.error or "no data", style="dim italic")
        return t
    frac = max(0.0, min(1.0, lim.remaining))
    filled = round(frac * BAR)
    style = "green" if frac > 0.5 else ("yellow" if frac > 0.2 else "bold red")
    t.append("█" * filled, style=style)
    t.append("░" * (BAR - filled), style="dim")
    t.append(f" {frac * 100:3.0f}% ", style=style)
    t.append(" ".join(p for p in (lim.window, lim.group) if p))
    if lim.reset:
        soon = lim.reset - dt.datetime.now() < dt.timedelta(hours=24)
        t.append(f"  ↻{lim.reset.strftime('%H:%M' if soon else '%a %H:%M')}", style="dim")
    if lim.note:
        t.append(f"  {lim.note}", style="dim")
    return t


class LimitsView(VerticalScroll):
    """`u` re-reads the limits now; otherwise every 10 minutes."""

    BINDINGS = [
        Binding("u", "reload_limits", "Update Limits"),
    ]

    DEFAULT_CSS = """
    LimitsView {
        height: 100%;
        width: 100%;
        padding: 0 1;
    }
    LimitsView > #limits-body {
        text-wrap: nowrap;
        text-overflow: ellipsis;
    }
    """

    def __init__(
        self,
        *children: Widget,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        super().__init__(*children, name=name, id=id, classes=classes, disabled=disabled)
        self.limits: list[Limit] | None = None
        self.updated: dt.datetime | None = None

    def compose(self) -> ComposeResult:
        yield Static(Text("loading…", style="dim"), id="limits-body")

    def on_mount(self) -> None:
        self.load_limits()
        self.set_interval(LIMITS_REFRESH_S, self.load_limits)

    @work(thread=True, exclusive=True, group="limits")
    def load_limits(self) -> None:
        limits = fetch_limits(self.app.repo_root)  # type: ignore[attr-defined]
        self.app.call_from_thread(self._set_limits, limits)

    def _set_limits(self, limits: list[Limit]) -> None:
        self.limits = limits
        self.updated = dt.datetime.now()
        self.refresh_view()
        refresh_hud = getattr(self.app, "refresh_hud", None)
        if refresh_hud is not None:
            refresh_hud()

    def mini_status(self) -> list[str]:
        """Hut lines: the lowest remaining quota per provider."""
        if not self.limits:
            return ["quota not read yet", ""]
        lines = []
        for provider in PROVIDERS:
            left = [x.remaining for x in self.limits if x.provider == provider and x.remaining is not None]
            if left:
                lines.append(f"{provider} {round(min(left) * 100)}% left")
        return lines or ["quota unknown"]

    def refresh_view(self) -> None:
        body = self.query_one("#limits-body", Static)
        if self.limits is None:
            body.update(Text("loading…", style="dim"))
            return
        lines = [limit_line(l) for l in self.limits] or [Text("no limits reported", style="dim")]
        if self.updated:
            lines.append(Text(f"updated {self.updated:%H:%M} · u to refresh", style="dim"))
        body.update(Text("\n").join(lines))

    def action_reload_limits(self) -> None:
        self.limits = None
        self.refresh_view()
        self.load_limits()
