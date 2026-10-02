"""Bars carved in text: vertical and horizontal, eighths of a cell, no dependency.

    vbars(values, height, width)   columns rising from the bottom (▁▂▃▄▅▆▇█), one per value
    hbars(items, width)            one row per (label, value): a bar (▏▎▍▌▋▊▉█) and the number
    spark(values, width)           one line of vertical eighths

A value at or above `warn` is yellow, at or above `crit` red.
"""
from __future__ import annotations

from rich.text import Text

V = " ▁▂▃▄▅▆▇█"
H = " ▏▎▍▌▋▊▉█"
COLOR = "#c9a86a"


def _style(v: float, warn: float | None, crit: float | None) -> str:
    if crit is not None and v >= crit:
        return "bold red"
    if warn is not None and v >= warn:
        return "yellow"
    return COLOR


def fmt(v: float | None) -> str:
    if v is None:
        return "—"
    if abs(v) >= 1000:
        return f"{v / 1000:.1f}k"
    if v == int(v):
        return str(int(v))
    return f"{v:.2f}" if abs(v) < 10 else f"{v:.1f}"


def _fit(values: list[float], width: int) -> list[float]:
    """At most `width` columns: neighbouring values merged (their max) when there are more."""
    if len(values) <= width or width <= 0:
        return values
    out, step = [], len(values) / width
    for i in range(width):
        chunk = values[int(i * step): max(int((i + 1) * step), int(i * step) + 1)]
        out.append(max(chunk))
    return out


def vbars(values: list[float], height: int = 6, width: int | None = None, scale: float | None = None,
          warn: float | None = None, crit: float | None = None) -> Text:
    vals = _fit([max(v, 0.0) for v in values], width or len(values))
    top = scale or max(vals or [0.0]) or 1.0
    text = Text(no_wrap=True)
    for row in range(height, 0, -1):
        for v in vals:
            eighths = int(round(min(v / top, 1.0) * height * 8))
            fill = max(0, min(8, eighths - (row - 1) * 8))
            text.append(V[fill], style=_style(v, warn, crit))
        text.append("\n")
    text.rstrip()
    return text


def hbars(items: list[tuple[str, float]], width: int = 30, scale: float | None = None, warn: float | None = None,
          crit: float | None = None, label_w: int = 12) -> Text:
    top = scale or max([v for _, v in items] or [0.0]) or 1.0
    bar_w = max(width - label_w - 8, 4)
    text = Text(no_wrap=True)
    for label, v in items:
        eighths = int(round(min(max(v, 0.0) / top, 1.0) * bar_w * 8))
        bar = "█" * (eighths // 8) + (H[eighths % 8] if eighths % 8 else "")
        text.append(f"{label[:label_w]:<{label_w}} ", style="dim")
        text.append(f"{bar:<{bar_w}}", style=_style(v, warn, crit))
        text.append(f" {fmt(v)}\n")
    text.rstrip()
    return text


def spark(values: list[float], width: int, scale: float | None = None, warn: float | None = None,
          crit: float | None = None) -> Text:
    return vbars(values, 1, width, scale, warn, crit)
