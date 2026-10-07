"""Huts: the `mini` block of a custom building, the roofs of a custom frame and the older ASCII art
library. (What a camp building looks like on the map is in `tui/silhouettes.py`.)

The town view shows every building as a hut and expands one at a time. This module is pure (no
Textual): the art library, which art a built-in building wears, and the `mini` block of a custom
building spec — its checks and how its status lines are rendered from the data the building
already fetches. Like the rest of a custom building it is data, never code: a template over
whitelisted fields of one data entry.
"""
from __future__ import annotations

import re
from typing import Any

# Every piece: 4 lines, at most ART_W cells, plain ASCII (no wide glyphs, so the width is exact).
ART_W = 18
ART_H = 4
STATUS_LINES = 3      # a compact hut (the default) shows three lines

# name → (lines, what it suits — the Mason prompt lists these)
ART: dict[str, tuple[tuple[str, ...], str]] = {
    "burrow": ((
        "     ,------.",
        "  ,-'/\\/\\/\\/`-.",
        "  |  _     [] |",
        "~~|_|_|_______|~~",
    ), "inbox, triage, incoming notes and requests"),
    "forge": ((
        "         ~~",
        " ________||_____",
        " | _/\\_   [==] |",
        " |[====]__|__|_|",
    ), "tasks, kanban, builds, work in progress"),
    "watchtower": ((
        "     _|^|_",
        "    |[] []|",
        "     |   |",
        "    /|___|\\",
    ), "calendar, schedules, deadlines, monitoring"),
    "great_hall": ((
        " |>           |>",
        "/^\\___/^^\\___/^\\",
        "| | [] [] [] | |",
        "|_|___|##|___|_|",
    ), "goals, OKRs, epics, strategy"),
    "spire": ((
        "       <>",
        "      /  \\",
        "     | () |",
        "   __|____|__",
    ), "preview, documents, specs, reading"),
    "war_tent": ((
        "      /\\   |>",
        "     /  \\  |",
        "    / /\\ \\ |",
        "   /_/  \\_\\|",
    ), "chat, live agent sessions, conversations"),
    "vault": ((
        " ____________",
        "|  $   ___   |",
        "| [$]  |o|   |",
        "|______|_|___|",
    ), "money, limits, quotas, budgets, artifacts"),
    "barracks": ((
        "_[]___[_]___[]_",
        "|  _   _   _  |",
        "| |#| |#| |#| |",
        "|_|_|_|_|_|_|_|",
    ), "agents, teams, people, capacity"),
    "library": ((
        "  ___________",
        " /  ~~~~~~~  \\",
        "| |=||=||=|  |",
        "|_|=||=||=|__|",
    ), "wiki, knowledge, notes, research"),
    "workshop": ((
        "    _____   o",
        " __|_____|__|_",
        "| [] (*)  [] |",
        "|____|##|____|",
    ), "tools, CI, scripts, anything else"),
    "mill": ((
        "   \\   |   /",
        "    \\  |  /",
        "  ----(O)----",
        "  ___/_|_\\___",
    ), "processes, recurring runs, pipelines"),
    "rookery": ((
        "   v    v   v",
        "  ___________",
        " | @  [====] |",
        " |____|__|___|",
    ), "mail, messages, notifications, feeds"),
}
DEFAULT_ART = "workshop"

# Built-in buildings (realm/buildings.py) → art.
BUILTIN_ART: dict[str, str] = {
    "farm": "burrow", "forge": "forge", "loot": "vault", "watchtower": "watchtower",
    "great_hall": "great_hall", "scrying": "spire", "chat": "war_tent", "processes": "mill",
    "agents": "barracks", "systems": "workshop", "limits": "vault", "town_hall": "great_hall",
}

ROW_FIELDS = ("title", "id", "status", "priority", "assignee", "type", "deadline", "when", "meta")
TEXT_FIELDS = ("last", "first", "heading", "count")
_PLACEHOLDER = re.compile(r"\{([a-z_]+)\}")
EMPTY = "—"


def art(name: str | None) -> tuple[str, ...]:
    return ART.get(name or "", ART[DEFAULT_ART])[0]


def art_catalog() -> str:
    """One line per piece, for the Mason prompt."""
    return "\n".join(f"- {name}: {use}" for name, (_, use) in ART.items())


# -- the `mini` block of a custom building spec --------------------------------------------------

def validate_mini(spec: dict, kinds: dict[str, str]) -> list[str]:
    """Problems of `spec["mini"]` given the kind of each data entry (list / text / tree)."""
    mini = spec.get("mini")
    if mini is None:
        return []
    errors = []
    if mini.get("art") is not None and mini["art"] not in ART:
        errors.append(f"mini: unknown art {mini['art']!r}; choose one of {', '.join(ART)}")
    for i, line in enumerate(mini.get("lines") or []):
        kind = kinds.get(line.get("data", ""))
        if kind is None:
            errors.append(f"mini/lines/{i}: no data named {line.get('data')!r}")
            continue
        allowed = ("count",) + ROW_FIELDS if kind == "list" else TEXT_FIELDS if kind == "text" else ("count",)
        for name in _PLACEHOLDER.findall(line.get("template", "")):
            if name not in allowed:
                errors.append(f"mini/lines/{i}: {{{name}}} is not available for {kind} data; use {', '.join(allowed)}")
        where = line.get("where") or {}
        if where and kind != "list":
            errors.append(f"mini/lines/{i}: where only applies to list data")
        for key in where:
            if key not in ROW_FIELDS:
                errors.append(f"mini/lines/{i}: where on unknown field {key!r}; use {', '.join(ROW_FIELDS)}")
    return errors


def render_line(template: str, data: Any, where: dict | None = None) -> str:
    """Fill a template from one fetched data entry (masonry.Data): rows, text or a tree."""
    if getattr(data, "error", ""):
        return f"⚠ {data.error}"
    kind = getattr(data, "kind", "text")
    values: dict[str, str] = {}
    if kind == "list":
        rows = list(getattr(data, "rows", []) or [])
        for key, want in (where or {}).items():
            rows = [r for r in rows if r.get(key) == str(want)]
        values["count"] = str(len(rows))
        first = rows[0] if rows else None
        for f in ROW_FIELDS:
            values[f] = (first.get(f) if first is not None else "") or EMPTY
    elif kind == "text":
        # Markdown is shown plain: no code fences, no backticks or bold marks, headings without #.
        lines = [_plain(ln) for ln in str(getattr(data, "text", "")).splitlines()
                 if ln.strip() and not ln.strip().startswith("```")]
        heading = next((ln.lstrip("#").strip() for ln in lines if ln.startswith("#")), "")
        values.update(last=lines[-1] if lines else EMPTY, first=lines[0] if lines else EMPTY,
                      heading=heading or EMPTY, count=str(len(lines)))
    else:
        path = getattr(data, "path", None)
        try:
            values["count"] = str(sum(1 for _ in path.iterdir())) if path is not None else "0"
        except OSError:
            values["count"] = "0"
    return _PLACEHOLDER.sub(lambda m: values.get(m.group(1), EMPTY), template)


def _plain(line: str) -> str:
    return re.sub(r"[`*]", "", line).strip()


def custom_status(spec: dict, data: dict[str, Any]) -> list[str]:
    """The status lines of a custom building from the data it fetched (name → masonry.Data)."""
    lines = (spec.get("mini") or {}).get("lines") or []
    out = [render_line(ln["template"], data[ln["data"]], ln.get("where"))
           for ln in lines[:STATUS_LINES] if ln.get("data") in data]
    if out:
        return out
    # No `mini`: what the first data entry holds.
    first = next(iter(data.values()), None)
    if first is None:
        return []
    if getattr(first, "kind", "") == "list":
        return [render_line("{count} rows · {title}", first)]
    return [render_line("{last}", first)]


# -- shape of a hut: size from the type, the roof, the quick actions ------------------------

# Roof library: name → 2–3 lines drawn for the hut's inner width, so one roof fits
# an XS hut (6 cells inside) and an L one (22) alike. A roof is a function of the width; a fixed
# tuple of lines works too.
ROOF_W = 22


def _slope(w: int, rows: int, fill: str = " ", base: str | None = None, left: str = "/", right: str = "\\") -> list[str]:
    """A pitched roof spanning `w` at the eaves: three rows rise to a peak, two make a hip roof."""
    out, span = [], max(w - 2, 0)
    for i in range(rows):
        if rows >= 3:
            inner = round(span * i / (rows - 1))
            inner -= (inner - span) % 2                       # keep it centred like the base
        else:
            inner = max(span - 4 * (rows - 1 - i), 0)
        body = (base if base is not None and i == rows - 1 else fill) * inner
        out.append((left + body + right).center(w))
    return out


def _battlements(w: int) -> str:
    return ("▄ " * w)[:w].rstrip().center(w)


def _gable(w):
    return tuple(_slope(w, 3 if w >= 12 else 2, " ", "_"))


def _thatch(w):
    return tuple(_slope(w, 2, "≈"))


def _tiles(w):
    return tuple(_slope(w, 3 if w >= 12 else 2, "▒", left="╱", right="╲"))


def _pagoda(w):
    top = _slope(min(w, 8), 1, "▔", left="╱", right="╲")[0].strip()
    return ("┬".center(w), top.center(w), ("⌒" + "▔" * max(w - 2, 0) + "⌒")[:w])


def _dome(w):
    cap = "╭" + "─" * max(w // 2 - 2, 1) + "╮"
    return (cap.center(w), ("╭╯" + " " * max(w - 4, 0) + "╰╮")[:w].center(w))


def _castle(w):
    return (_battlements(w), "█" * w)


def _tent(w):
    rows = _slope(w, 3 if w >= 12 else 2)
    peak = rows[0].replace("/\\", "▲")
    return (peak, *[r[: len(r) // 2] + "│" + r[len(r) // 2 + 1:] if i else r for i, r in enumerate(rows[1:])])


def _chimney(w):
    rows = _slope(w, 2, " ", "_")
    x = max(w * 3 // 4 - 1, 1)
    smoke = (" " * x + "°°").ljust(w)[:w]
    rows[0] = rows[0][:x] + "▐▌" + rows[0][x + 2:] if len(rows[0]) > x + 2 else rows[0]
    return (smoke, *rows)


def _flag(w):
    return ("⚑".center(w), _battlements(w), "▀" * w)


def _snow(w):
    flakes = "".join("*" if i % 3 == 1 else " " for i in range(w))
    return (flakes, *_slope(w, 2, "▄", left="▟", right="▙"))


ROOFS: dict[str, object] = {
    "gable": _gable, "thatch": _thatch, "tiles": _tiles, "pagoda": _pagoda, "dome": _dome,
    "castle": _castle, "tent": _tent, "chimney": _chimney, "flag": _flag, "snow": _snow,
}


def roof(name: str | None, width: int = ROOF_W) -> tuple[str, ...]:
    """The roof's lines for a hut `width` cells wide inside (none for an unknown name)."""
    r = ROOFS.get(name or "")
    if r is None:
        return ()
    lines = r(max(width, 4)) if callable(r) else r
    return tuple(line[:width].rstrip() for line in lines)
