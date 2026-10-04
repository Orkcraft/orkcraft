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

from orkcraft.realm.looks import OLD_ICONS, kind_icon

SCHEMAS = Path(__file__).resolve().parent / "schemas"
SCHEMA_PATH = SCHEMAS / "town-scroll.v3.json"
SCHEMA_V2_PATH = SCHEMAS / "town-scroll.v2.json"
SCHEMA_URL = "https://orkcraft.dev/schemas/town-scroll.v3.json"
# What the retros improve a building towards (docs/design/retros-and-goals.md §3).
GOALS = ("thrift", "balance", "quality")
GOAL_ICONS = {"thrift": "🪙", "balance": "⚖️", "quality": "💎"}
GOAL_TITLES = {"thrift": "Thrift", "balance": "Balance", "quality": "Quality"}
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

# Orc kinds, tried in this order when an orc is created from a prompt.
KINDS = ("chain", "script", "agent", "hybrid")
HARNESS_ROLES = ("run", "plan", "write", "review")
HARNESSES = ("claude", "agy")     # plus "pipeline:<repo-relative spec>.json"
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
        for key, empty in (("run", None), ("chain", []), ("script", None), ("why", "")):
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
    bounds: dict | None = None        # {"x","y","width","height"} in canvas cells
    frac: list[float] | None = None   # fractional slot, follows canvas resizes
    hut: list[float] | None = None    # town view: the hut's spot, fractions of the canvas room
    min_size: dict | None = None
    roads: list[Road] = field(default_factory=list)     # incoming
    chronicles: dict = field(default_factory=lambda: {"enabled": True})
    actions: list[dict] = field(default_factory=list)
    garrison: Garrison = field(default_factory=Garrison)

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
                bounds=b.get("bounds"), frac=b.get("frac"), hut=b.get("hut"), min_size=b.get("min_size"),
                roads=[Road.from_dict(r) for r in b.get("roads", [])],
                chronicles=b.get("chronicles") or {"enabled": True},
                actions=list(b.get("actions") or []),
                garrison=Garrison(OrcSpec(**g["steward"]) if g.get("steward") else None,
                                  [OrcSpec(**m) for m in g.get("handlers", [])]),
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


# -- validation ----------------------------------------------------------------------------------

def _schema(path: Path = SCHEMA_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _schema_errors(data: Any, path: Path, sub: str | None = None) -> list[str]:
    from jsonschema import Draft202012Validator

    schema = _schema(path)
    if sub:  # validate against one $defs entry, resolving refs inside the full schema
        schema = {**schema, "$ref": f"#/$defs/{sub}"}
        for k in ("required", "properties", "additionalProperties", "type"):
            schema.pop(k, None)
    return [
        f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
        for e in sorted(Draft202012Validator(schema).iter_errors(data), key=lambda e: list(e.absolute_path))
    ]


def _regex_problem(pattern: str) -> str:
    try:
        re.compile(pattern)
    except re.error as e:
        return f"bad regex {pattern!r}: {e}"
    return ""


def orc_problems(orc: dict, where: str = "") -> list[str]:
    """Schema and kind rules of one orc (a dict as in the file) — also the recruiter's check."""
    prefix = f"{where}: " if where else ""
    errors = [prefix + e for e in _schema_errors(orc, SCHEMA_PATH, "orc")]
    if errors:
        return errors
    kind = orc.get("kind", "agent")
    harness = orc.get("harness", DEFAULT_HARNESS)
    name = orc.get("id", "?")
    if kind == "chain" and not orc.get("chain"):
        errors.append(f"{prefix}ork {name}: a chain needs at least one op")
    if kind in ("script", "hybrid") and not orc.get("script"):
        errors.append(f"{prefix}ork {name}: a {kind} needs a script")
    if kind in ("agent", "hybrid") and not harness:
        errors.append(f"{prefix}ork {name}: an {kind} needs a harness")
    if kind != "chain" and orc.get("chain"):
        errors.append(f"{prefix}ork {name}: only a chain has chain ops")
    for op in orc.get("chain", []):
        pattern = op.get("regex") or (op.get("value") if op.get("cmp") == "matches" else None)
        if isinstance(pattern, str) and (p := _regex_problem(pattern)):
            errors.append(f"{prefix}ork {name}: {p}")
    return errors


def filter_problems(flt: dict) -> list[str]:
    errors = _schema_errors(flt, SCHEMA_PATH, "filter")
    if not errors and flt.get("match") and (p := _regex_problem(flt["match"])):
        errors.append(p)
    return errors


def _cycle(edges: dict[str, set[str]]) -> str | None:
    """A node on a directed cycle of `edges`, or None."""
    state: dict[str, int] = {}

    def visit(n: str) -> str | None:
        state[n] = 1
        for m in edges.get(n, ()):
            if state.get(m) == 1:
                return m
            if m not in state and (hit := visit(m)):
                return hit
        state[n] = 2
        return None

    for n in list(edges):
        if n not in state and (hit := visit(n)):
            return hit
    return None


def validate(data: dict[str, Any]) -> list[str]:
    """v3 schema errors plus the cross-references a JSON Schema cannot express."""
    errors = _schema_errors(data, SCHEMA_PATH)
    if errors:
        return errors
    errors += _common_refs(data)
    b_ids = {b["id"] for b in data["buildings"]}
    edges: dict[str, set[str]] = {}
    for b in data["buildings"]:
        g = b.get("garrison") or {}
        steward = g.get("steward")
        handlers = g.get("handlers", [])
        orcs = ([steward] if steward else []) + handlers
        ids = [m["id"] for m in orcs]
        dupes = sorted({m for m in ids if ids.count(m) > 1})
        if dupes:
            errors.append(f"building {b['id']}: duplicate ork ids {', '.join(dupes)}")
        if len(orcs) > MAX_GARRISON:
            errors.append(f"building {b['id']}: more than {MAX_GARRISON} orks in the garrison")
        for m in orcs:
            errors += orc_problems(m, f"building {b['id']}")
        handler_ids = {m["id"] for m in handlers}
        road_ids = [r["id"] for r in b.get("roads", [])]
        dupes = sorted({r for r in road_ids if road_ids.count(r) > 1})
        if dupes:
            errors.append(f"building {b['id']}: duplicate road ids {', '.join(dupes)}")
        seen: set[tuple] = set()
        for r in b.get("roads", []):
            where = f"building {b['id']}, road {r['id']}"
            if r["from"] not in b_ids:
                errors.append(f"{where}: source {r['from']!r} does not exist")
            if r["from"] == b["id"]:
                errors.append(f"{where}: a road cannot come from its own building")
            if r.get("handler") is not None and r["handler"] not in handler_ids:
                errors.append(f"{where}: handler {r['handler']!r} is not a handler of {b['id']}")
            errors += [f"{where}: filter {e}" for e in filter_problems(r.get("filter") or {})]
            key = (r["from"], r["event"], r.get("handler"), json.dumps(r.get("filter") or {}, sort_keys=True))
            if key in seen:
                errors.append(f"{where}: the same road twice")
            seen.add(key)
            edges.setdefault(r["from"], set()).add(b["id"])
    if (hit := _cycle(edges)) is not None:
        errors.append(f"roads form a loop through {hit!r}")
    return errors


def _common_refs(data: dict[str, Any]) -> list[str]:
    """Orkspace / building references shared by v2 and v3."""
    errors = []
    b_ids = [b["id"] for b in data["buildings"]]
    o_ids = [o["id"] for o in data["orkspaces"]]
    for kind, ids in (("building", b_ids), ("orkspace", o_ids)):
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        if dupes:
            errors.append(f"duplicate {kind} ids: {', '.join(dupes)}")
    hotkeys = [o["hotkey"] for o in data["orkspaces"] if o.get("hotkey")]
    if len(hotkeys) != len(set(hotkeys)):
        errors.append("two orkspaces share a hotkey")
    if data["active_orkspace_id"] not in o_ids:
        errors.append(f"active_orkspace_id {data['active_orkspace_id']!r} is not an orkspace")
    placed: dict[str, str] = {}
    for o in data["orkspaces"]:
        for bid in o["buildings"]:
            if bid not in b_ids:
                errors.append(f"orkspace {o['id']}: unknown building {bid!r}")
            elif bid in placed:
                errors.append(f"building {bid!r} is in two orkspaces ({placed[bid]}, {o['id']})")
            placed[bid] = o["id"]
    return errors


def validate_v2(data: dict[str, Any]) -> list[str]:
    """A v2 scroll (before migration): the v2 schema and its rally / garrison references."""
    errors = _schema_errors(data, SCHEMA_V2_PATH)
    if errors:
        return errors
    errors += _common_refs(data)
    b_ids = [b["id"] for b in data["buildings"]]
    for b in data["buildings"]:
        rp = b.get("rally_point")
        if rp and rp["target_building_id"] not in b_ids:
            errors.append(f"building {b['id']}: rally target {rp['target_building_id']!r} does not exist")
        if rp and rp["target_building_id"] == b["id"]:
            errors.append(f"building {b['id']}: a rally point cannot target itself")
        g = b.get("garrison") or {}
        members = [m["id"] for m in g.get("members", [])]
        dupes = sorted({m for m in members if members.count(m) > 1})
        if dupes:
            errors.append(f"building {b['id']}: duplicate ork ids {', '.join(dupes)}")
        if len(members) > MAX_GARRISON:
            errors.append(f"building {b['id']}: more than {MAX_GARRISON} orks in the garrison")
        if g.get("lead_orc_id") and g["lead_orc_id"] not in members:
            errors.append(f"building {b['id']}: lead ork {g['lead_orc_id']!r} is not in the garrison")
    edges = {b["id"]: {b["rally_point"]["target_building_id"]} for b in data["buildings"] if b.get("rally_point")}
    if (hit := _cycle(edges)) is not None:
        errors.append(f"rally points form a loop through {hit!r}")
    return errors


# -- defaults and migration ---------------------------------------------------------------------------

def _preset_ref(preset_id: str, presets: Presets) -> str:
    return f"{'core' if presets.get(preset_id, {}).get('category') == 'core' else 'legacy'}:{preset_id}"


def _orc_id(name: str) -> str:
    oid = _slug(name)
    return "orc" if oid == "camp" else oid  # _slug's fallback for names without latin letters


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
    incoming: dict[str, list[dict]] = {}
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


# -- orkspace operations (the UI calls these; they keep the cross-references valid) ---------------------------

HOTKEYS = tuple(f"F{i}" for i in range(1, 9))
MAX_ORKSPACES = len(HOTKEYS)


def ensure_presets(scroll: TownScroll, presets: Presets) -> list[str]:
    """Add registry buildings the scroll does not know yet (demolished, in the first orkspace).

    Buildings whose preset left the registry are kept in the file untouched. Returns the added ids.
    """
    known = {b.id for b in scroll.buildings}
    added = []
    for pid, p in presets.items():
        if pid in known:
            b = scroll.building(pid)
            if b is not None and (b.preset_ref.startswith("core:") or b.preset_ref.startswith("legacy:")):
                b.title = p.get("title", b.title)
                b.icon = p.get("icon", b.icon)
            continue
        b = building_from_preset(pid, presets)
        b.demolished = True
        scroll.buildings.append(b)
        scroll.orkspaces[0].buildings.append(b.id)
        added.append(b.id)
    return added


def _slug(name: str) -> str:
    out = "".join(c if c.isascii() and (c.isalnum() or c in "_-") else "_" for c in name.strip().lower())
    out = out.strip("_-")[:64]
    return out or "camp"


def new_orkspace(scroll: TownScroll, name: str, biome: str = "forest", icon: str = "⛺") -> Orkspace:
    """Append an empty orkspace with a unique id and the first free hotkey F1–F8.

    Raises ValueError for an unknown biome, an empty name or when all eight hotkeys are taken.
    """
    name = name.strip()
    if not name:
        raise ValueError("an orkspace needs a name")
    if biome not in BIOMES:
        raise ValueError(f"unknown biome {biome!r}")
    taken = {o.hotkey for o in scroll.orkspaces}
    hotkey = next((k for k in HOTKEYS if k not in taken), None)
    if hotkey is None or len(scroll.orkspaces) >= MAX_ORKSPACES:
        raise ValueError(f"at most {MAX_ORKSPACES} orkspaces (F1–F8)")
    base = _slug(name)
    ids = {o.id for o in scroll.orkspaces}
    oid, n = base, 2
    while oid in ids:
        suffix = f"_{n}"
        oid, n = base[: 64 - len(suffix)] + suffix, n + 1
    ork = Orkspace(oid, name, biome, icon, hotkey)
    scroll.orkspaces.append(ork)
    return ork


def orkspace_by_hotkey(scroll: TownScroll, hotkey: str) -> Orkspace | None:
    key = hotkey.upper()
    return next((o for o in scroll.orkspaces if o.hotkey == key), None)


def move_building(scroll: TownScroll, building_id: str, orkspace_id: str) -> None:
    """Put a building on another canvas (a building lives in exactly one orkspace) and raise it there."""
    target = scroll.orkspace(orkspace_id)
    b = scroll.building(building_id)
    if target is None or b is None:
        raise ValueError(f"unknown orkspace {orkspace_id!r} or building {building_id!r}")
    for o in scroll.orkspaces:
        if o is target:
            continue
        if building_id in o.buildings:
            o.buildings.remove(building_id)
        if building_id in o.window_order:
            o.window_order.remove(building_id)
        if o.active_building == building_id:
            o.active_building = None
    if building_id not in target.buildings:
        target.buildings.append(building_id)
    b.demolished = False


def remove_orkspace(scroll: TownScroll, orkspace_id: str) -> None:
    """Delete an empty orkspace; never the last one. The active one falls back to the first left."""
    ork = scroll.orkspace(orkspace_id)
    if ork is None:
        raise ValueError(f"unknown orkspace {orkspace_id!r}")
    if len(scroll.orkspaces) == 1:
        raise ValueError("the last orkspace cannot be removed")
    if ork.buildings:
        raise ValueError(f"{ork.name} still holds buildings: move or demolish them first")
    scroll.orkspaces.remove(ork)
    if scroll.active_orkspace_id == orkspace_id:
        scroll.active_orkspace_id = scroll.orkspaces[0].id


# -- garrison operations -----------------------------------------------------------------------------------

MAX_GARRISON = 9   # the roster selects orcs with the keys 1–9 (steward included)


def _building(scroll: TownScroll, building_id: str) -> BuildingSpec:
    b = scroll.building(building_id)
    if b is None:
        raise ValueError(f"unknown building {building_id!r}")
    return b


def _unique_orc_id(b: BuildingSpec, name: str) -> str:
    base = _orc_id(name)
    ids = {m.id for m in b.garrison.members}
    oid, n = base, 2
    while oid in ids:
        suffix = f"_{n}"
        oid, n = base[: 64 - len(suffix)] + suffix, n + 1
    return oid


def add_handler(scroll: TownScroll, building_id: str, name: str, *, kind: str = "agent", role: str = "",
                orders: str = "", harness: list[dict] | None = None, chain: list[dict] | None = None,
                script: dict | None = None, run: dict | None = None, why: str = "",
                trigger: dict | None = None, avatar: str | None = None) -> OrcSpec:
    """Add a handler (no roads yet — `subscribe(..., handler=id)` gives it some).

    Raises ValueError for an unknown building, an empty name, a full garrison or an orc that
    breaks the schema or the kind rules (`orc_problems`). A script handler starts as `draft`
    until the operator reviews its code.
    """
    b = _building(scroll, building_id)
    name = name.strip()
    if not name:
        raise ValueError("an ork needs a name")
    if len(b.garrison.members) >= MAX_GARRISON:
        raise ValueError(f"{b.title}: the garrison is full ({MAX_GARRISON})")
    if trigger is not None and trigger.get("type") not in TRIGGER_TYPES:
        raise ValueError(f"unknown trigger type {trigger.get('type')!r}")
    if harness is None:
        harness = [] if kind in ("chain", "script") else [dict(s) for s in DEFAULT_HARNESS]
    orc = OrcSpec(
        _unique_orc_id(b, name), name, role=role.strip(), orders=orders.strip(), kind=kind,
        avatar=avatar or kind_icon(kind),
        status="draft" if script is not None and not script.get("reviewed") else "idle",
        trigger=dict(trigger) if trigger else {"type": "pipe" if kind != "agent" else "on_demand"},
        harness=[dict(s) for s in harness], chain=[dict(op) for op in chain or []],
        script=dict(script) if script else None, run=dict(run) if run else None, why=why.strip(),
    )
    problems = orc_problems(orc.to_dict())
    if problems:
        raise ValueError("; ".join(problems))
    b.garrison.handlers.append(orc)
    return orc


def remove_handler(scroll: TownScroll, building_id: str, orc_id: str) -> list[str]:
    """Remove a handler; its roads stay as plain roads. Returns those road ids."""
    b = _building(scroll, building_id)
    orc = b.garrison.handler(orc_id)
    if orc is None:
        if b.garrison.steward and b.garrison.steward.id == orc_id:
            raise ValueError(f"{b.garrison.steward.name} is the steward of {b.title}: replace it, don't dismiss it")
        raise ValueError(f"{b.title}: no ork {orc_id!r}")
    b.garrison.handlers.remove(orc)
    freed = []
    for r in b.roads_of(orc_id):
        r.handler = None
        freed.append(r.id)
    return freed


def set_steward(scroll: TownScroll, building_id: str, orc_id: str) -> None:
    """Promote a handler to steward; the old steward becomes a handler without roads.

    Raises ValueError when the orc still works on roads (a steward watches the building, it
    does not handle roads) — unsubscribe them first.
    """
    b = _building(scroll, building_id)
    g = b.garrison
    if g.steward and g.steward.id == orc_id:
        return
    orc = g.handler(orc_id)
    if orc is None:
        raise ValueError(f"unknown building {building_id!r} or ork {orc_id!r}")
    if b.roads_of(orc_id):
        raise ValueError(f"{orc.name} works on roads of {b.title}: move them to another handler first")
    idx = g.handlers.index(orc)
    g.handlers.remove(orc)
    if g.steward is not None:
        g.handlers.insert(idx, g.steward)
    g.steward = orc


def update_orc(scroll: TownScroll, building_id: str, orc_id: str, **changes: Any) -> OrcSpec:
    """Change fields of a steward or handler (orders, trigger, kind, harness, chain, run, …),
    all or nothing: an orc that would break the rules is refused with ValueError."""
    b = _building(scroll, building_id)
    orc = b.garrison.orc(orc_id)
    if orc is None:
        raise ValueError(f"{b.title}: no ork {orc_id!r}")
    unknown = set(changes) - set(OrcSpec.__dataclass_fields__) - {"id"}
    if unknown or "id" in changes:
        raise ValueError(f"cannot change {', '.join(sorted(unknown | ({'id'} & set(changes))))}")
    candidate = {**orc.to_dict(), **changes}
    candidate = {k: v for k, v in candidate.items() if v is not None}
    problems = orc_problems(candidate)
    if problems:
        raise ValueError("; ".join(problems))
    for k, v in changes.items():
        setattr(orc, k, v)
    return orc


# v2 operations, kept for the current UI: recruit adds an agent handler (or the steward when
# there is none), dismiss removes a handler, set_lead promotes to steward.

def recruit(scroll: TownScroll, building_id: str, name: str, role: str = "", orders: str = "",
            trigger: dict | None = None, tier: str | None = None) -> OrcSpec:
    """`tier` (elder | warrior | laborer, realm/tiers.py) picks the model; None leaves the CLI's."""
    from orkcraft.realm import tiers
    b = _building(scroll, building_id)
    harness = tiers.with_tier([dict(s) for s in DEFAULT_HARNESS], tier) if tier else None
    orc = add_handler(scroll, building_id, name, role=role, orders=orders,
                      trigger=trigger or {"type": "on_demand"}, harness=harness)
    if b.garrison.steward is None:
        b.garrison.handlers.remove(orc)
        b.garrison.steward = orc
    return orc


def dismiss_orc(scroll: TownScroll, building_id: str, orc_id: str) -> None:
    b = _building(scroll, building_id)
    if b.garrison.steward and b.garrison.steward.id == orc_id:
        raise ValueError(f"{b.garrison.steward.name} leads {b.title} and cannot be dismissed")
    remove_handler(scroll, building_id, orc_id)


def set_lead(scroll: TownScroll, building_id: str, orc_id: str) -> None:
    set_steward(scroll, building_id, orc_id)


# -- roads ------------------------------------------------------------------------------------------------

def incoming(scroll: TownScroll, building_id: str) -> list[Road]:
    b = scroll.building(building_id)
    return list(b.roads) if b else []


def outgoing(scroll: TownScroll, building_id: str) -> list[tuple[BuildingSpec, Road]]:
    """(target building, road) for every road leaving `building_id`."""
    return [(b, r) for b in scroll.buildings for r in b.roads if r.source == building_id]


def find_road(scroll: TownScroll, road_id: str, target_id: str | None = None) -> tuple[BuildingSpec, Road] | None:
    """(target building, road) by road id — ids are unique per receiver, so pass the target when known."""
    for b in scroll.buildings:
        if target_id is not None and b.id != target_id:
            continue
        r = b.road(road_id)
        if r is not None:
            return b, r
    return None


def has_outgoing(scroll: TownScroll, building_id: str, event: str) -> bool:
    """Does any road carry `event` out of `building_id`? (whether to emit it at all)"""
    return any(r.event == event for _, r in outgoing(scroll, building_id))


def _road_edges(scroll: TownScroll) -> dict[str, set[str]]:
    edges: dict[str, set[str]] = {}
    for b in scroll.buildings:
        for r in b.roads:
            edges.setdefault(r.source, set()).add(b.id)
    return edges


def subscribe(scroll: TownScroll, target_id: str, source_id: str, event: str = "on_selection_change",
              filter: dict | None = None, handler: str | None = None, label: str = "") -> Road:
    """Give `target_id` an incoming road from `source_id` (Y on the receiver).

    Raises ValueError for unknown buildings, a self-road, an unknown event, a bad filter, a
    handler that is not one of the target's handlers, a duplicate road, too many roads or a loop.
    """
    src, dst = scroll.building(source_id), scroll.building(target_id)
    if src is None or dst is None:
        raise ValueError(f"unknown building {source_id!r} or {target_id!r}")
    if source_id == target_id:
        raise ValueError("a road cannot come from its own building")
    if event not in ROAD_EVENTS and event not in _typed_events():
        raise ValueError(f"unknown road event {event!r}")
    flt = dict(filter or {})
    if problems := filter_problems(flt):
        raise ValueError("filter: " + "; ".join(problems))
    if handler is not None and dst.garrison.handler(handler) is None:
        raise ValueError(f"{dst.title} has no handler {handler!r}")
    if len(dst.roads) >= MAX_ROADS:
        raise ValueError(f"{dst.title}: at most {MAX_ROADS} incoming roads")
    for r in dst.roads:
        if (r.source, r.event, r.handler, r.filter) == (source_id, event, handler, flt):
            raise ValueError(f"{dst.title} already has this road from {src.title}")
    edges = _road_edges(scroll)
    edges.setdefault(source_id, set()).add(target_id)
    if _cycle(edges) is not None:
        raise ValueError(f"{src.title} → {dst.title} would close a loop of roads")
    short = event.replace(".", "_") if "." in event else event.removeprefix("on_").split("_")[0]   # typed: mail_received
    base = f"{source_id}-{short}"[:60]
    ids = {r.id for r in dst.roads}
    rid, n = base, 2
    while rid in ids:
        rid, n = f"{base}-{n}", n + 1
    if label and not re.fullmatch(r"[a-z0-9_:.-]{1,32}", label):
        raise ValueError(f"bad road label {label!r}")
    road = Road(rid, source_id, event, flt, handler, label=label)
    dst.roads.append(road)
    return road


def unsubscribe(scroll: TownScroll, target_id: str, road_id: str) -> Road:
    b = _building(scroll, target_id)
    road = b.road(road_id)
    if road is None:
        raise ValueError(f"{b.title}: no road {road_id!r}")
    b.roads.remove(road)
    return road


def set_road_handler(scroll: TownScroll, target_id: str, road_id: str, handler: str | None) -> Road:
    """Put a handler on a road (or take it off: None → plain road)."""
    b = _building(scroll, target_id)
    road = b.road(road_id)
    if road is None:
        raise ValueError(f"{b.title}: no road {road_id!r}")
    if handler is not None and b.garrison.handler(handler) is None:
        raise ValueError(f"{b.title} has no handler {handler!r}")
    road.handler = handler
    return road


def set_road_filter(scroll: TownScroll, target_id: str, road_id: str, filter: dict | None) -> Road:
    b = _building(scroll, target_id)
    road = b.road(road_id)
    if road is None:
        raise ValueError(f"{b.title}: no road {road_id!r}")
    flt = dict(filter or {})
    if problems := filter_problems(flt):
        raise ValueError("filter: " + "; ".join(problems))
    road.filter = flt
    return road


# v2 rally points as seen by the current UI: one plain outgoing road per source.

def set_rally_point(scroll: TownScroll, source_id: str, target_id: str,
                    pipe_mode: str = "on_selection_change") -> RallyPoint:
    """Replace the source's plain outgoing roads with one plain road to `target_id`."""
    src, dst = scroll.building(source_id), scroll.building(target_id)
    if src is None or dst is None:
        raise ValueError(f"unknown building {source_id!r} or {target_id!r}")
    if source_id == target_id:
        raise ValueError("a rally point cannot target its own building")
    if pipe_mode not in ROAD_EVENTS:
        raise ValueError(f"unknown pipe mode {pipe_mode!r}")
    old = [(t, r) for t, r in outgoing(scroll, source_id) if r.plain]
    for t, r in old:
        t.roads.remove(r)
    try:
        road = subscribe(scroll, target_id, source_id, pipe_mode)
    except ValueError as e:
        for t, r in old:
            t.roads.append(r)
        if "loop" in str(e):
            raise ValueError(f"{src.title} → {dst.title} would close a loop of rally points") from None
        raise
    return RallyPoint(target_id, pipe_mode, road.id)


def clear_rally_point(scroll: TownScroll, source_id: str) -> bool:
    """Remove the source's plain outgoing roads; False when it had none."""
    old = [(t, r) for t, r in outgoing(scroll, source_id) if r.plain]
    for t, r in old:
        t.roads.remove(r)
    return bool(old)


# -- custom buildings (Mason & Artisan) ---------------------------------------------------------------

def add_custom_building(scroll: TownScroll, spec: dict, orkspace_id: str | None = None) -> BuildingSpec:
    """Register a validated custom building spec (`realm.masonry`) in an orkspace (default: the active).

    Its steward is the spec's orc. Raises ValueError when the id is taken or the orkspace unknown.
    """
    bid = str(spec["id"])
    if scroll.building(bid) is not None:
        raise ValueError(f"a building {bid!r} already exists")
    ork = scroll.orkspace(orkspace_id) if orkspace_id else scroll.active_orkspace
    if ork is None:
        raise ValueError(f"unknown orkspace {orkspace_id!r}")
    orc = spec.get("orc") or {}
    orc_name = str(orc.get("name") or "Peon")
    b = BuildingSpec(
        id=bid, preset_ref=f"custom:{bid}", title=str(spec["title"]), icon=str(spec.get("icon", "")),
        chronicles={"enabled": True, "log_file": str(HISTORY_DIR / f"{bid}.events.jsonl")},
        garrison=Garrison(OrcSpec(_orc_id(orc_name), orc_name, role=str(orc.get("role", "")))),
    )
    scroll.buildings.append(b)
    ork.buildings.append(bid)
    return b


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
