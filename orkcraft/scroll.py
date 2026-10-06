"""Town Scroll v3 (`.orkcraft.json`): the typed contract for orkspaces, buildings, roads and
garrisons, validated against `schemas/town-scroll.v3.json` (design: docs/design/roads-and-orcs.md).

This module is the only place that reads or writes the scroll. UI code works with the
dataclasses below; `load()` migrates v2 scrolls and the v1 layout files of orcraft/mgtui.

    scroll, problems = load(path, presets)      # never raises on bad input
    scroll.active_orkspace.buildings            # building ids on the current canvas
    save(path, scroll)                          # refuses to write an invalid scroll
    subscribe(scroll, "scrying", "forge", "on_task_completed", handler="scribe")
    add_handler(scroll, "scrying", "Scribe", kind="chain", chain=[{"op": "pick", "fields": ["id"]}])
    incoming(scroll, "scrying"); outgoing(scroll, "forge")     # roads into / out of a building

A building's roads are its **incoming** roads (the receiver subscribes; the source never knows
its consumers). A road's `handler` is one of the building's handlers, or None for a plain road.
The garrison is one steward (watches the building) plus handlers (work on the roads).
"""
from __future__ import annotations

import datetime as dt
import json
import re
import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from orkcraft.realm.looks import OLD_ICONS, kind_icon  # noqa: F401 (kind_icon: scroll_garrisons)

SCHEMAS = Path(__file__).resolve().parent / "schemas"
SCHEMA_PATH = SCHEMAS / "town-scroll.v3.json"
SCHEMA_V2_PATH = SCHEMAS / "town-scroll.v2.json"
SCHEMA_URL = "https://orkcraft.dev/schemas/town-scroll.v3.json"
# What the retros improve a building towards (docs/design/retros-and-goals.md §3).
GOALS = ("thrift", "balance", "quality")
GOAL_ICONS = {"thrift": "🪙", "balance": "⚖️", "quality": "💎"}
GOAL_TITLES = {"thrift": "Thrift", "balance": "Balance", "quality": "Quality"}
# How freely a building's steward applies its retro's changes (realm/evolution.py `may_apply`); the
# Town Hall's sets the Town retro's. None: as the town's autonomy level (autonomy.py).
FREEDOMS = ("chains", "clock", "free")
FREEDOM_ICONS = {"chains": "⛓️", "clock": "🕰", "free": "⛓️‍💥"}
FREEDOM_TITLES = {"chains": "In chains", "clock": "On the clock", "free": "Unchained"}
VERSION = "0.3.0"
BIOMES = ("void", "forest", "ice")
ROAD_EVENTS = ("on_selection_change", "on_task_completed", "on_stream")


def _typed_events() -> frozenset[str]:
    """The typed events of the building catalog a road may also wait for."""
    from orkcraft.realm import catalog
    return catalog.all_event_ids()
PIPE_MODES = ROAD_EVENTS          # v2 name, kept for callers
TRIGGER_TYPES = ("on_demand", "cron", "webhook", "event", "pipe")
HISTORY_DIR = Path(".orkcraft") / "history" / "buildings"
MAX_ROADS = 32
MAX_GARRISON = 9   # the roster selects orcs with the keys 1–9 (steward included)

# Orc kinds, tried in this order when an orc is created from a prompt.
KINDS = ("chain", "script", "agent", "hybrid")
HARNESS_ROLES = ("run", "plan", "write", "review")
HARNESSES = ("claude", "agy", "codex")     # plus "pipeline:<repo-relative spec>.json"
DEFAULT_HARNESS = [{"role": "run", "harness": "claude"}]
CHAIN_OPS = ("filter", "pick", "extract", "sort", "limit", "count", "group", "template", "join")
# Re-run policy per kind: cheap kinds rerun at once, agents coalesce a burst and restart.
RUN_DEFAULTS = {
    "chain": {"quiet_s": 0, "restart_on_new": True},
    "script": {"quiet_s": 0, "restart_on_new": True},
    "agent": {"quiet_s": 30, "restart_on_new": True},
    "hybrid": {"quiet_s": 30, "restart_on_new": True},
}
CART_MODES = ("off", "selected", "all")
_PIPELINE = re.compile(r"^pipeline:[A-Za-z0-9_-]+(/[A-Za-z0-9_-]+)*\.json$")

# Presets as the UI registry describes them: id → title, icon, orc, role, category (core | migrated).
Presets = dict[str, dict[str, str]]


# -- model ------------------------------------------------------------------------------------

@dataclass
class OrcSpec:
    id: str
    name: str
    role: str = ""
    avatar: str = "🧌"
    status: str = "idle"          # idle | busy | alert | frozen | draft
    trigger: dict = field(default_factory=lambda: {"type": "on_demand"})
    orders: str = ""              # the prompt / standing orders
    kind: str = "agent"           # chain | script | agent | hybrid
    harness: list[dict] = field(default_factory=lambda: [dict(s) for s in DEFAULT_HARNESS])
    run: dict | None = None       # None → RUN_DEFAULTS[kind]
    chain: list[dict] = field(default_factory=list)
    script: dict | None = None    # {"path", "sha256"?, "reviewed"?}
    why: str = ""                 # the recruiter's reason for this kind
    models: dict | None = None    # a steward's tier per task (realm/steward.py USES): {"watch": "laborer", …}

    def __post_init__(self) -> None:
        self.avatar = OLD_ICONS.get(self.avatar, self.avatar)

    @property
    def run_policy(self) -> dict:
        return {**RUN_DEFAULTS.get(self.kind, RUN_DEFAULTS["agent"]), **(self.run or {})}

    @property
    def uses_model(self) -> bool:
        return self.kind in ("agent", "hybrid")

    def to_dict(self) -> dict:
        d = asdict(self)
        for key, empty in (("run", None), ("chain", []), ("script", None), ("why", ""), ("models", None)):
            if d[key] == empty:
                d.pop(key)
        return d  # harness always: an empty list must not load back as the default


@dataclass
class Road:
    """An incoming road of the building that holds it: `source` → this building."""
    id: str
    source: str                   # "from" in the file
    event: str = "on_selection_change"
    filter: dict = field(default_factory=dict)
    handler: str | None = None    # a handler id of this building; None = plain road
    transform: str = ""           # carried over from v2 rally points, not interpreted
    label: str = ""               # display name of the signal (e.g. on_patch), not interpreted

    @property
    def plain(self) -> bool:
        return self.handler is None

    def to_dict(self) -> dict:
        d: dict[str, Any] = {"id": self.id, "from": self.source, "event": self.event}
        if self.filter:
            d["filter"] = dict(self.filter)
        d["handler"] = self.handler
        if self.transform:
            d["transform"] = self.transform
        if self.label:
            d["label"] = self.label
        return d

    @classmethod
    def from_dict(cls, d: dict) -> Road:
        from orkcraft.realm import catalog                  # a road of old waits for the event's new id
        return cls(d["id"], d["from"], catalog.event_id(d["event"]), dict(d.get("filter") or {}), d.get("handler"),
                   d.get("transform", ""), d.get("label", ""))


@dataclass
class Garrison:
    steward: OrcSpec | None = None
    handlers: list[OrcSpec] = field(default_factory=list)

    # v2 view (the roster and Unit Frame still read these): the steward leads.
    @property
    def members(self) -> list[OrcSpec]:
        return ([self.steward] if self.steward else []) + list(self.handlers)

    @property
    def lead_orc_id(self) -> str:
        return self.steward.id if self.steward else ""

    @property
    def lead(self) -> OrcSpec | None:
        return self.steward or (self.handlers[0] if self.handlers else None)

    def orc(self, orc_id: str) -> OrcSpec | None:
        return next((m for m in self.members if m.id == orc_id), None)

    def handler(self, orc_id: str) -> OrcSpec | None:
        return next((m for m in self.handlers if m.id == orc_id), None)


@dataclass(frozen=True)
class RallyPoint:
    """v2 view of a plain outgoing road (`TownScroll.rally_of`); the file no longer stores it."""
    target_building_id: str
    pipe_mode: str = "on_selection_change"
    road_id: str = ""


@dataclass
class BuildingSpec:
    id: str
    preset_ref: str
    title: str
    icon: str = ""
    pinned: bool = False
    demolished: bool = False
    goal: str | None = None           # thrift | balance | quality — what the retros aim at; None = balance
    autonomy: str | None = None       # chains | clock | free — how its retro's changes land; None = as the town
    bounds: dict | None = None        # {"x","y","width","height"} in canvas cells
    frac: list[float] | None = None   # fractional slot, follows canvas resizes
    hut: list[float] | None = None    # town view: the hut's spot, fractions of the canvas room
    min_size: dict | None = None
    roads: list[Road] = field(default_factory=list)     # incoming
    chronicles: dict = field(default_factory=lambda: {"enabled": True})
    actions: list[dict] = field(default_factory=list)
    garrison: Garrison = field(default_factory=Garrison)
    ui: dict | None = None            # its UI document (schemas/building-ui.v1.json); None: its type's default
    open_in_lake: list[str] | None = None   # events of it that open in the town's Lake window (realm/lake.py retire)

    @property
    def preset_id(self) -> str:
        return self.preset_ref.split(":", 1)[1]

    @property
    def aim(self) -> str:
        """Its goal, balance when none is set (docs/design/retros-and-goals.md §3)."""
        return self.goal if self.goal in GOALS else "balance"

    def road(self, road_id: str) -> Road | None:
        return next((r for r in self.roads if r.id == road_id), None)

    def roads_of(self, handler_id: str) -> list[Road]:
        return [r for r in self.roads if r.handler == handler_id]


@dataclass
class GitLink:
    enabled: bool = False
    mode: str = "root"                # root | worktree
    path: str = "./"
    branch: str = ""


@dataclass
class Orkspace:
    id: str
    name: str
    biome: str = "forest"
    icon: str = "🏰"
    hotkey: str = ""
    git: GitLink = field(default_factory=GitLink)
    buildings: list[str] = field(default_factory=list)
    window_order: list[str] = field(default_factory=list)
    active_building: str | None = None


@dataclass
class Budget:
    gold_session_limit_usd: float = 20.0
    lumber_context_limit_tokens: int = 131072
    supply_max_workers: int = 5


DEFAULT_VIEW = "town"   # town (huts, one building expanded) | tiles (every window open)


def _default_preferences() -> dict:
    return {"terrain_solid_black": False, "preview_linked": True, "carts": "selected", "roads": "faint",
            "view": DEFAULT_VIEW}         # "mode" only when the project overrides the machine's (settings.py)


@dataclass
class TownScroll:
    active_orkspace_id: str
    orkspaces: list[Orkspace]
    buildings: list[BuildingSpec]
    budget: Budget = field(default_factory=Budget)
    preferences: dict = field(default_factory=_default_preferences)
    meta: dict = field(default_factory=lambda: {"project_name": "orkcraft", "tagline": "Work vs Humans"})
    version: str = VERSION

    def building(self, building_id: str) -> BuildingSpec | None:
        return next((b for b in self.buildings if b.id == building_id), None)

    def orkspace(self, orkspace_id: str) -> Orkspace | None:
        return next((o for o in self.orkspaces if o.id == orkspace_id), None)

    @property
    def active_orkspace(self) -> Orkspace:
        return self.orkspace(self.active_orkspace_id) or self.orkspaces[0]

    def buildings_in(self, orkspace_id: str) -> list[BuildingSpec]:
        ork = self.orkspace(orkspace_id)
        return [b for bid in (ork.buildings if ork else []) if (b := self.building(bid))]

    def orkspace_of(self, building_id: str) -> Orkspace | None:
        return next((o for o in self.orkspaces if building_id in o.buildings), None)

    def rally_of(self, source_id: str) -> RallyPoint | None:
        """The first plain road leaving `source_id` — what the v2 rally-point UI shows and fires."""
        for target, road in outgoing(self, source_id):
            if road.plain:
                return RallyPoint(target.id, road.event, road.id)
        return None

    # -- (de)serialisation ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        def clean(d: dict) -> dict:
            return {k: v for k, v in d.items() if v is not None}

        buildings = []
        for b in self.buildings:
            item = clean({k: v for k, v in asdict(b).items() if k not in ("roads", "garrison")})
            if b.roads:
                item["roads"] = [r.to_dict() for r in b.roads]
            item["garrison"] = {
                "steward": b.garrison.steward.to_dict() if b.garrison.steward else None,
                "handlers": [m.to_dict() for m in b.garrison.handlers],
            }
            buildings.append(item)
        orkspaces = []
        for o in self.orkspaces:
            item = clean(asdict(o))
            item["git"] = clean(asdict(o.git)) if o.git.enabled else {"enabled": False}
            if not o.hotkey:
                item.pop("hotkey", None)
            orkspaces.append(item)
        return {
            "$schema": SCHEMA_URL,
            "version": self.version,
            "meta": {**self.meta, "updated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")},
            "budget": asdict(self.budget),
            "preferences": dict(self.preferences),
            "active_orkspace_id": self.active_orkspace_id,
            "orkspaces": orkspaces,
            "buildings": buildings,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TownScroll:
        buildings = []
        for b in data.get("buildings", []):
            g = b.get("garrison") or {}
            buildings.append(BuildingSpec(
                id=b["id"], preset_ref=b["preset_ref"], title=b["title"], icon=b.get("icon", ""),
                pinned=bool(b.get("pinned", False)), demolished=bool(b.get("demolished", False)),
                goal=b.get("goal") if b.get("goal") in GOALS else None,
                autonomy=b.get("autonomy") if b.get("autonomy") in FREEDOMS else None,
                bounds=b.get("bounds"), frac=b.get("frac"), hut=b.get("hut"), min_size=b.get("min_size"),
                roads=[Road.from_dict(r) for r in b.get("roads", [])],
                chronicles=b.get("chronicles") or {"enabled": True},
                actions=list(b.get("actions") or []),
                garrison=Garrison(OrcSpec(**g["steward"]) if g.get("steward") else None,
                                  [OrcSpec(**m) for m in g.get("handlers", [])]),
                ui=b.get("ui") if isinstance(b.get("ui"), dict) else None,
                open_in_lake=[str(e) for e in b["open_in_lake"]] if b.get("open_in_lake") else None,
            ))
        orkspaces = [
            Orkspace(
                id=o["id"], name=o["name"], biome=o.get("biome", "forest"), icon=o.get("icon", "🏰"),
                hotkey=o.get("hotkey", ""), git=GitLink(**(o.get("git") or {"enabled": False})),
                buildings=list(o.get("buildings", [])), window_order=list(o.get("window_order", [])),
                active_building=o.get("active_building"),
            )
            for o in data.get("orkspaces", [])
        ]
        return cls(
            active_orkspace_id=data["active_orkspace_id"], orkspaces=orkspaces, buildings=buildings,
            budget=Budget(**(data.get("budget") or {})),
            preferences={**_default_preferences(), **(data.get("preferences") or {})},
            meta={k: v for k, v in (data.get("meta") or {}).items() if k != "updated_at"} or
                 {"project_name": "orkcraft", "tagline": "Work vs Humans"},
            version=data.get("version", VERSION),
        )


# -- defaults and migration ---------------------------------------------------------------------------

def _preset_ref(preset_id: str, presets: Presets) -> str:
    return f"{'core' if presets.get(preset_id, {}).get('category') == 'core' else 'legacy'}:{preset_id}"


def building_from_preset(preset_id: str, presets: Presets, building_id: str | None = None) -> BuildingSpec:
    p = presets.get(preset_id, {})
    orc_name = p.get("orc", "Peon")
    return BuildingSpec(
        id=building_id or preset_id, preset_ref=_preset_ref(preset_id, presets),
        title=p.get("title", preset_id), icon=p.get("icon", ""),
        chronicles={"enabled": True, "log_file": str(HISTORY_DIR / f"{building_id or preset_id}.events.jsonl")},
        garrison=Garrison(OrcSpec(orc_name.lower().replace(" ", "_"), orc_name, role=p.get("role", ""))),
    )


# A new camp starts with the Town Hall alone: everything else is built from it.
# None stands every preset (the camp of old).
STARTING: tuple[str, ...] | None = ("town_hall",)


def default_scroll(presets: Presets, raised: list[str] | tuple[str, ...] | None = None) -> TownScroll:
    """One forest camp holding every preset; only `raised` (default: STARTING) stand."""
    buildings = [building_from_preset(pid, presets) for pid in presets]
    raised = STARTING if raised is None else raised
    if raised is not None:
        for b in buildings:
            b.demolished = b.id not in raised
    camp = Orkspace("main_camp", "Main Camp", "forest", "🏰", "F1", GitLink(True, "root", "./"),
                    [b.id for b in buildings])
    return TownScroll("main_camp", [camp], buildings)


def is_v1(data: object) -> bool:
    return isinstance(data, dict) and data.get("version") == 1 and isinstance(data.get("windows"), dict)


def is_v2(data: object) -> bool:
    return isinstance(data, dict) and str(data.get("version", "")).startswith("0.2.")


def migrate_v1(data: dict[str, Any], presets: Presets) -> TownScroll:
    """orcraft/mgtui layout (version 1) → a single-camp scroll, nothing lost."""
    scroll = default_scroll(presets, list(presets))
    windows = data.get("windows", {})
    for b in scroll.buildings:
        w = windows.get(b.id)
        if not isinstance(w, dict):
            b.demolished = True
            continue
        b.bounds = {"x": max(int(w.get("x", 0)), 0), "y": max(int(w.get("y", 0)), 0),
                    "width": max(int(w.get("w", 40)), 1), "height": max(int(w.get("h", 12)), 1)}
        b.frac = list(w["frac"]) if w.get("frac") else None
        b.demolished = bool(w.get("hidden", False))
        b.pinned = bool(w.get("pinned", False))
        unit = w.get("unit") or {}
        lead = b.garrison.lead
        if lead is not None:
            trig = unit.get("trigger") or {}
            if trig.get("type") in TRIGGER_TYPES:
                lead.trigger = {"type": trig["type"], **({"expression": trig["expression"]} if trig.get("expression") else {})}
            lead.orders = str(unit.get("context") or "")
    camp = scroll.orkspaces[0]
    camp.window_order = [i for i in data.get("order", []) if i in camp.buildings]
    camp.active_building = data.get("active") if data.get("active") in camp.buildings else None
    scroll.preferences["preview_linked"] = bool(data.get("preview_linked", True))
    # Stage 3 wrote the canvas biome and the solid-black toggle into the v1 file.
    if data.get("biome") in BIOMES:
        camp.biome = data["biome"]
    scroll.preferences["terrain_solid_black"] = bool(data.get("terrain_solid_black", False))
    return scroll


def migrate_v2(data: dict[str, Any]) -> dict[str, Any]:
    """A valid v2 scroll dict → a v3 scroll dict, nothing lost.

    A building's rally point becomes a plain road held by its target; the garrison lead becomes
    the steward, the other members agent handlers without roads.
    """
    out = json.loads(json.dumps(data))
    out["$schema"], out["version"] = SCHEMA_URL, VERSION
    incoming: dict[str, list[dict]] = {}  # noqa: F811 (a local, not scroll_roads.incoming)
    for b in out["buildings"]:
        rp = b.pop("rally_point", None)
        if rp:
            road = {"id": f"from-{b['id']}"[:64], "from": b["id"], "event": rp["pipe_mode"], "handler": None}
            if rp.get("transform"):
                road["transform"] = rp["transform"]
            incoming.setdefault(rp["target_building_id"], []).append(road)
        g = b.pop("garrison", None) or {}
        members = g.get("members", [])
        lead_id = g.get("lead_orc_id") or (members[0]["id"] if members else None)
        b["garrison"] = {
            "steward": next((m for m in members if m["id"] == lead_id), None),
            "handlers": [m for m in members if m["id"] != lead_id],
        }
    for b in out["buildings"]:
        if b["id"] in incoming:
            b["roads"] = incoming[b["id"]]
    return out


# -- files ------------------------------------------------------------------------------------------------

def load(path: Path, presets: Presets, legacy: list[Path] | tuple[Path, ...] = ()) -> tuple[TownScroll, list[str]]:
    """The scroll at `path` (or migrated from the first existing `legacy` v1 file).

    Never raises: an unreadable or invalid scroll is copied aside
    (`<name>.invalid-<timestamp>`) and a default scroll is returned with the problems.
    """
    source = path if path.exists() else next((p for p in legacy if p.exists()), None)
    if source is None:
        return default_scroll(presets), []
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return _set_aside(source, presets, [f"{source.name}: {e}"])
    if is_v1(data):
        return migrate_v1(data, presets), [f"migrated {source.name} (v1) to Town Scroll v3"]
    notes = []
    if is_v2(data):
        problems = validate_v2(data)
        if problems:
            return _set_aside(source, presets, problems)
        data = migrate_v2(data)
        notes = [f"migrated {source.name} (v2) to Town Scroll v3: rally points are now roads"]
    problems = validate(data) if isinstance(data, dict) else ["not a JSON object"]
    if problems:
        return _set_aside(source, presets, problems)
    return TownScroll.from_dict(data), notes


def _set_aside(source: Path, presets: Presets, problems: list[str]) -> tuple[TownScroll, list[str]]:
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = source.with_name(f"{source.name}.invalid-{stamp}")
    try:
        shutil.copy2(source, backup)
        problems = problems + [f"kept the unreadable scroll as {backup.name}"]
    except OSError:
        pass
    return default_scroll(presets), problems


def save(path: Path, scroll: TownScroll) -> list[str]:
    """Write atomically; an invalid scroll is refused (returns the problems, writes nothing)."""
    data = scroll.to_dict()
    problems = validate(data)
    if problems:
        return problems
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)
    return []


# -- Building Chronicles (event sourcing) ---------------------------------------------------------------------

def events_file(repo_root: Path, building_id: str) -> Path:
    return repo_root / HISTORY_DIR / f"{building_id}.events.jsonl"


def append_event(repo_root: Path, building_id: str, event: dict[str, Any]) -> Path:
    """Append one mutation, e.g. {"type": "card_moved", "id": "T1001", "to": "done", "by": "operator"}."""
    path = events_file(repo_root, building_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {"ts": dt.datetime.now().isoformat(timespec="seconds"), "building": building_id, **event}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return path


def read_events(repo_root: Path, building_id: str, limit: int = 200) -> list[dict[str, Any]]:
    """Newest last; malformed lines are skipped."""
    try:
        lines = events_file(repo_root, building_id).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for line in lines[-limit:]:
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


# -- the parts (validation, orkspace and garrison edits, roads): every name stays importable from here --
from orkcraft.scroll_checks import (  # noqa: E402, F401
    _schema, _schema_errors, _regex_problem, orc_problems, filter_problems, _cycle, validate, _common_refs,
    validate_v2,
)
from orkcraft.scroll_garrisons import (  # noqa: E402, F401
    HOTKEYS, MAX_ORKSPACES, ensure_presets, _slug, new_orkspace, orkspace_by_hotkey, move_building,
    remove_orkspace, _orc_id, _building, _unique_orc_id, add_handler, remove_handler, set_steward, update_orc,
    recruit, dismiss_orc, set_lead,
)
from orkcraft.scroll_roads import (  # noqa: E402, F401
    incoming, outgoing, road_key, split_key, find_road, has_outgoing, _road_edges, subscribe, unsubscribe,
    set_road_handler, set_road_filter, set_rally_point, clear_rally_point, add_custom_building,
)
