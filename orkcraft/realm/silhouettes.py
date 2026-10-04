"""Silhouettes: what a building looks like on the town map.

Every camp building has its own shape — a mill with sails, a watchtower with a roof, a forest of
trees on a long hall — drawn in box characters. The shape is a template: `§` marks a cell of text,
a run of them is a slot, and the building's live status fills the slots. The name and the icon
stand above the building (see `label`), the quick-action buttons below it.

    Silhouette.draw(live)    the template with its slots filled → [[(text, role)…]…]
                             role: frame | head (a static heading) | live

Small buildings (10 cells wide) keep one line of text in the frame; the big ones (18 and 26
wide) have seven to nine, the first of which is a fixed heading of what the building is for. The
Lake of Insight is the panorama (60 wide). Pure module, no Textual.
"""
from __future__ import annotations

import re
import textwrap
from functools import lru_cache
from dataclasses import dataclass, field

SLOT = "§"
_RUN = re.compile(f"{SLOT}+")
ELLIPSIS = "…"


def clip(text: str, width: int) -> str:
    """Cut to `width` cells, ending with … when something was cut (an emoji is two cells)."""
    from rich.cells import cell_len
    if width <= 0:
        return ""
    if cell_len(text) <= width:
        return text
    out, used = "", 0
    for ch in text:
        w = cell_len(ch)
        if used + w > width - 1:
            break
        out, used = out + ch, used + w
    return out + ELLIPSIS


def _fill(text: str, width: int, center: bool = False) -> str:
    """Pad `text` to exactly `width` cells (rich's cell width, so emoji do not push the frame out)."""
    from rich.cells import cell_len
    room = max(width - cell_len(text), 0)
    left = room // 2 if center else 0
    return " " * left + text + " " * (room - left)


@dataclass(frozen=True)
class Silhouette:
    id: str
    lines: tuple[str, ...]
    head: tuple[str, ...] = ()           # static headings: the texts of the first slots
    fallback: tuple[str, ...] = ()       # texts of the first live slots while the building has nothing live
    pad: int = 1                         # blank cells before a slot's text
    center: bool = False                 # centre the text in its slot (the small buildings)
    caption: bool = False                # no room inside: the first live line stands under the building
    body: tuple[int, int] = (0, 0)       # the frame as the design gives it (w, h) — informative, tested
    grow: str = ""                       # `lake` | `crag` | `frame`: rows follow the content, up to a maximum

    @property
    def width(self) -> int:
        return max(len(line) for line in self.lines)

    @property
    def height(self) -> int:
        return len(self.lines)

    @property
    def slots(self) -> list[tuple[int, int, int]]:
        """(row, column, width) of every slot, in reading order."""
        return [(y, m.start(), m.end() - m.start()) for y, line in enumerate(self.lines) for m in _RUN.finditer(line)]

    @property
    def live_widths(self) -> list[int]:
        """Widths of the slots live text goes to (after the static headings)."""
        return [w for _, _, w in self.slots][len(self.head):]

    def texts(self, live: list[str]) -> list[str]:
        """One string per slot: the headings, then the live lines, then the fallbacks of the empty ones."""
        n = len(self.slots)
        out = list(self.head[:n])
        room = n - len(out)
        shown = [str(x) for x in live[:room]] if not self.caption else []
        for i in range(room):
            text = " ".join(shown[i].split()) if i < len(shown) else ""
            if not text and not shown and i < len(self.fallback):
                text = self.fallback[i]
            out.append(text)
        return out

    def draw(self, live: list[str]) -> list[list[tuple[str, str]]]:
        """The template filled: per line, a list of (text, role) pieces."""
        texts, k = self.texts(live), 0
        rows: list[list[tuple[str, str]]] = []
        for line in self.lines:
            line = line.ljust(self.width)
            pieces, at = [], 0
            for m in _RUN.finditer(line):
                if m.start() > at:
                    pieces.append((line[at:m.start()], "frame"))
                w = m.end() - m.start()
                text = clip(texts[k], w - self.pad if not self.center else w)
                text = _fill(text, w, True) if self.center else _fill(" " * self.pad + text, w)
                pieces.append((text, "head" if k < len(self.head) else "live"))
                k, at = k + 1, m.end()
            if at < len(line):
                pieces.append((line[at:], "frame"))
            rows.append(pieces)
        return rows

    def caption_text(self, live: list[str]) -> str:
        return clip(" ".join(str(live[0]).split()), self.width + 4) if self.caption and live else ""


def _rows(side: str, n: int, width: int, left: str | None = None, right: str | None = None) -> list[str]:
    l, r = left or side, right or side
    return [l + SLOT * (width - 2) + r for _ in range(n)]


def _box(width: int, rows: int, top: str | None = None, bottom: str | None = None, sides: str = "│") -> list[str]:
    top = top or "┌" + "─" * (width - 2) + "┐"
    bottom = bottom or "└" + "─" * (width - 2) + "┘"
    return [top] + _rows(sides, rows, width) + [bottom]


def _make(sid: str, lines: list[str], **kw) -> Silhouette:
    return Silhouette(sid, tuple(lines), **kw)


# -- the small buildings (10 wide) ----------------------------------------------------------------

MILL = _make("mill", ["┌────────┐ \\ /", "│§§§§§§§§│-(O)-", "└────────┘ / \\"],
             fallback=("MAP",), pad=0, center=True, body=(10, 3))
CATAPULT = _make("catapult", ["┌────────┐ \\", "│§§§§§§§§│  \\═(O)", "└────────┘"],
                 fallback=("EGRESS",), pad=0, center=True, body=(10, 3))
PIT = _make("pit", ["    ┌───┐", "_// │ § │", "    └───┘"], head=("█",), pad=0, center=True,
            caption=True, body=(5, 3))
HORN = _make("horn", ["┌────────┐ /|", "│§§§§§§§§│=| )", "└────────┘ \\|"],
              fallback=("♪",), pad=0, center=True, body=(10, 3))
TOTEM = _make("totem", ["  ┌────┐  ", "  │■  ■│  ", "┌─┤ §§ ├─┐", "└─┤§§§§├─┘", "  └────┘  "],
              head=("||",), pad=0, center=True, body=(10, 5))
WATCHTOWER = _make("watchtower", ["    /\\    ", "   /  \\   ", " _/____\\_ ", "┌────────┐"]
                   + _rows("│", 4, 10) + ["└────────┘"], pad=0, body=(10, 6))

# -- the production and staff halls (18 wide, seven text rows) ------------------------------------

FIELDS = _make("fields", _box(18, 7, top="┌─\\||/─\\||/─\\||/─┐"), body=(18, 9))
BARRACKS = _make("barracks", ["  __    __    __  "] + _box(18, 7, top="┌|  |──|  |──|  |┐"),
                 head=("WORKER POOL",), body=(18, 9))
COUNCIL = _make("council", ["   o    o    o    "] + _box(18, 7, top="┌──/\\───/\\───/\\──┐"),
                head=("MULTI - AGENT", "DEBATE ENGINE"), body=(18, 9))
FORGE = _make("forge", ["       oOO        "] + _box(18, 7, top="┌─────|  |───────┐"),
              head=("MERGE ENGINE",), body=(18, 9))
SCROLLS = _make("scrolls", _box(18, 7, top="@" + "~" * 16 + "@", bottom="@" + "~" * 16 + "@"),
                head=("LLM WIKI / RAG",), body=(18, 9))

# -- the strategic complexes (26 wide, nine text rows) --------------------------------------------

WAR_DRUM = _make("war_drum", ["           \\ o /"] + _box(26, 9, top="┌" + "─" * 12 + "┴" + "─" * 11 + "┐"),
                 head=("TODAY'S RAIDS & MOOTS",), body=(26, 11))
FOREST = _make("forest", ["    /|\\  /|\\  /|\\  /|\\    "]
               + _box(26, 9, top="┌───/|\\──/|\\──/|\\──/|\\───┐"), head=("EXPLORER & CONTEXT",), body=(26, 11))
LOOT = _make("loot", ["/" + "═" * 10 + "[##]" + "═" * 10 + "\\"] + _box(26, 9), head=("ARTIFACT REPOSITORY",), body=(26, 11))
def _crag(rows: int = 9) -> Silhouette:
    return _make("crag", _box(26, rows, top=" /" + "─" * 22 + "\\ ", bottom=" \\" + "─" * 22 + "/ "),
                 head=("TELEMETRY & TELEGRAPHS",), body=(26, rows + 2), grow="crag")


CRAG = _crag()

# -- the panorama: the Lake of Insight (60 wide) --------------------------------------------------

_PANE_L, _PANE_R = 28, 24


def _lake(panes: int = 6) -> Silhouette:
    waves = "~" * 60

    def side(i: int, inner: str) -> str:
        l, r = ("(", ")") if i % 2 == 0 else (")", "(")
        return l + inner + r

    rows = [waves, side(0, SLOT * 58), side(1, " " * 58),
            side(2, " ┌── ACTIVE DIFF " + "─" * 13 + "┐┌── RENDER PREVIEW " + "─" * 6 + "┐ ")]
    for i in range(panes):
        rows.append(side(3 + i, " │" + SLOT * _PANE_L + "││" + SLOT * _PANE_R + "│ "))
    rows.append(side(3 + panes, " └" + "─" * _PANE_L + "┘└" + "─" * _PANE_R + "┘ "))
    rows.append(side(4 + panes, SLOT * 58))
    rows.append("(" + "_" * 58 + ")")
    return _make("lake", rows, head=("VIEWPORT & DIFF INSPECTOR",), body=(60, panes + 7), grow="lake")


LAKE = _lake()

# -- the Town Hall, the Workshop and the generic frame (no design given: drawn in the same spirit) -

TOWN_HALL = _make("town_hall", ["  |>        /\\        |> ", " /^\\_______/  \\_______/^\\"] + _box(26, 9),
                  head=("THE TOWN HALL",), body=(26, 11))
WORKSHOP = _make("workshop", ["     ||    ||     "] + _box(18, 5, top="┌────||────||────┐"),
                 head=("WORKSHOP",), body=(18, 7))

SILHOUETTES: dict[str, Silhouette] = {s.id: s for s in (
    MILL, CATAPULT, HORN, PIT, TOTEM, WATCHTOWER, FIELDS, BARRACKS, COUNCIL, FORGE, SCROLLS, WAR_DRUM, FOREST,
    LOOT, CRAG, LAKE, TOWN_HALL, WORKSHOP)}

# The catalog's types → their silhouette ids (the same names for all but a few).
BY_TYPE = {"pit": "pit", "watchtower": "watchtower", "totem": "totem", "mill": "mill", "horn": "horn", "fields": "fields",
           "barracks": "barracks", "council": "council", "war_drum": "war_drum", "forest": "forest",
           "scrolls": "scrolls", "lake": "lake", "forge": "forge", "loot": "loot", "crag": "crag",
           "catapult": "catapult", "town_hall": "town_hall", "workshop": "workshop"}

FRAME_SIZES = {"XS": (10, 5), "S": (14, 7), "M": (18, 9), "L": (26, 11)}
BUILTIN = {"loot": "loot", "town_hall": "town_hall"}      # built-in buildings that wear a camp silhouette


def frame(size: tuple[int, int], roof: tuple[str, ...] = ()) -> Silhouette:
    """The generic frame of a custom (panes) building: a box of `size`, an optional roof over it."""
    w, h = size
    top = [line[:w].center(w).rstrip() for line in roof]
    return Silhouette(f"frame{w}x{h}", tuple(top + _box(w, max(h - 2, 1))), body=(w, h), grow="frame")


# rows of text a growing silhouette may take: (least, most). The lake's and the crag's most is what a
# 140×42 town can hold beside other huts; the least of the lake is its design.
GROW_ROWS = {"lake": (6, 16), "crag": (5, 13), "frame": (3, 9)}


def fit(sil: Silhouette, rows: int) -> Silhouette:
    """`sil` with `rows` text rows (the lake's pane rows), clamped to its range; others come back as they are."""
    if not sil.grow:
        return sil
    lo, hi = GROW_ROWS[sil.grow]
    rows = min(max(rows, lo), hi)
    if sil.grow == "lake":
        return _lake(rows)
    if sil.grow == "crag":
        return _crag(rows)
    w, roof_lines = sil.width, []
    for ln in sil.lines:
        if ln.startswith("┌"):
            break
        roof_lines.append(ln)
    return Silhouette(f"frame{w}x{rows + 2}", tuple(roof_lines + _box(w, rows)), body=(w, rows + 2), grow="frame")


_SIDES = set("()|[]{}@┤├")


def _border_left(line: str, i: int) -> int:
    i = max(i - 1, 0)
    while i > 0 and line[i] == " ":
        i -= 1
    return i


def _border_right(line: str, i: int) -> int:
    i = min(i, len(line) - 1)
    while i < len(line) - 1 and line[i] == " ":
        i += 1
    return i


@lru_cache(maxsize=256)
def plain(sil: Silhouette) -> Silhouette:
    """The boring look: just a frame, with the same slots. Roofs, sails, trees, arms and waves go;
    what stays is the box, the rows of text and the lines between them (the Lake's pane headers)."""
    keep = [i for i, ln in enumerate(sil.lines) if SLOT in ln]
    if not keep:
        return sil
    lines = [ln.ljust(sil.width) for ln in sil.lines]
    spans = [(_border_left(lines[i], _RUN.search(lines[i]).start()),
              _border_right(lines[i], list(_RUN.finditer(lines[i]))[-1].end())) for i in keep]
    left, right = min(a for a, _ in spans), max(b for _, b in spans)
    rows = []
    for i in range(keep[0], keep[-1] + 1):
        row = list(lines[i][left:right + 1])
        for end in (0, -1):
            if row[end] in _SIDES:
                row[end] = "│"
        rows.append("".join(row))
    w = right - left + 1
    out = ["┌" + "─" * (w - 2) + "┐"] + rows + ["└" + "─" * (w - 2) + "┘"]
    return Silhouette(sil.id + "-plain", tuple(out), head=sil.head, fallback=sil.fallback, pad=sil.pad,
                      center=sil.center, caption=sil.caption, body=(w, len(out)), grow=sil.grow)


def styled(sil: Silhouette, is_plain: bool) -> Silhouette:
    return plain(sil) if is_plain else sil


def rows_needed(sil: Silhouette, lines: list[str]) -> int:
    """How many text rows `lines` (a view's live lines) fill: the lake's pane rows come interleaved."""
    filled = [i for i, ln in enumerate(lines) if str(ln).strip()]
    if sil.grow == "lake":
        panes = [i for i in filled if i < len(lines) - 1]
        return (max(panes) // 2 + 1) if panes else 0
    return len(filled) and max(filled) + 1


def of(spec: dict | None, building_id: str | None = None) -> Silhouette:
    """The silhouette of a building: its type's own; a built-in's (Artifacts wears the Loot Vault);
    a custom one (panes) a frame of its size."""
    from orkcraft.realm import catalog, huts
    t = catalog.type_of(spec) if spec is not None else None
    sid = BY_TYPE.get(t.id, "") if t else BUILTIN.get(building_id or "", "")
    if sid:
        return SILHOUETTES[sid]
    size = FRAME_SIZES.get((spec or {}).get("size") or "M", FRAME_SIZES["M"])
    return frame((size[0], GROW_ROWS["frame"][0] + 2), huts.roof((spec or {}).get("roof"), size[0]))


# -- the label above a building -------------------------------------------------------------------

LABEL_MIN_W = 14      # a title wraps at least this wide, so a 5-cell pit still reads "The pit"
LABEL_TITLE_LINES = 2
LABEL_GAP = 1         # a blank row between the name and the building


@dataclass(frozen=True)
class Label:
    head: str                                   # `7 🌾 Task fields`: the number, the one icon and the name
    title: tuple[str, ...] = field(default_factory=tuple)    # …the rest of a name that did not fit

    @property
    def text(self) -> tuple[str, ...]:
        return (self.head, *self.title)

    @property
    def lines(self) -> tuple[str, ...]:
        return (*self.text, *([""] * LABEL_GAP))

    @property
    def width(self) -> int:
        from rich.cells import cell_len
        return max(cell_len(x) for x in self.text)


def label(number: int, title: str, width: int) -> Label:
    """The name above a building: `7 🌾 Task fields` on one line (first letter capital, the rest
    small), wrapped to a second when long, then one blank row before the building."""
    if " · " in title:                                   # "🔮 Scrying Spire · Diff Inspector": the part after the dot
        icon, _, rest = title.partition(" ")
        title = f"{icon} {rest.rsplit(' · ', 1)[-1]}"
    icon, _, words = title.partition(" ")
    if not words:
        icon, words = "", title
    words = words[:1].upper() + words[1:].lower()
    full = " ".join(x for x in (str(number), icon, words) if x)
    room = max(width, LABEL_MIN_W) + 4
    wrapped = textwrap.wrap(full, room, break_long_words=True) or [""]
    if len(wrapped) > LABEL_TITLE_LINES:
        wrapped = wrapped[:LABEL_TITLE_LINES]
        wrapped[-1] = clip(wrapped[-1] + ELLIPSIS * 2, room)
    return Label(wrapped[0], tuple(wrapped[1:]))
