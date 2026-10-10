"""Showcase sandbox: eight orkspaces, one closed workflow each, with simulated data.

    orkcraft --demo [DIR]            build the sandbox (once) and open it in the TUI (the 8 roles)
    orkcraft gui --demo [DIR]        … in the GUI: the dashboard set, every building type with its state
    orkcraft --demo DIR --demo-reset rebuild it from scratch
    orkcraft --demo DIR --demo-screens OUT   walk F1–F8 headless and save SVG (+ PNG) screenshots

The sandbox is a separate fake project with its own Town Scroll; the operator's
`.orkcraft.json` is never touched. Everything shown is simulated (see `scenarios.py`).
"""
from __future__ import annotations

import datetime as dt
import json
import shutil
from pathlib import Path

from orkcraft import scroll as ts
from orkcraft.realm import chronicles, masonry
from orkcraft.demo.scenarios import SCENARIOS, SETS

DEFAULT_DIR = Path.home() / ".orkcraft-demo"


def default_dir(set_name: str = "main") -> Path:
    return DEFAULT_DIR if set_name == "main" else Path.home() / f".orkcraft-demo-{set_name}"
# 2 × 2 with gaps, so the roads between the windows show: TL, TR, BL, BR.
QUADRANTS = [(0.0, 0.0, 0.44, 0.46), (0.56, 0.0, 0.44, 0.46), (0.0, 0.54, 0.44, 0.46), (0.56, 0.54, 0.44, 0.46)]
MARKER = ".orkcraft-demo"
SAMPLES = Path(".orkcraft") / "demo-samples.json"
VERSION = 4          # raise it when a set changes: an older sandbox is then built again


def _node_md(scenario_id: str, n: dict) -> tuple[Path, str]:
    scenario_id = n.get("tag") or scenario_id
    if n["type"] == "context":
        rel = Path("context") / "knowledge" / f"{n['id']}.md"
        fm = (f"id: {n['id']}\ntype: context\nsubtype: knowledge\ntitle: \"{n['title']}\"\ncreated: 2026-09-28\n"
              f"modified: 2026-09-30\nstatus: {n['status']}\nassignee: {n['assignee']}\nsummary: \"{n['summary']}\"\n"
              f"tags: [\"{scenario_id}\"]\n")
    else:
        rel = Path("tasks") / n["status"] / f"{n['id']}.md"
        fm = (f"id: {n['id']}\ntype: task\ntitle: \"{n['title']}\"\ncreated: 2026-09-28\nmodified: 2026-09-30\n"
              f"status: {n['status']}\nassignee: {n['assignee']}\npriority: {n['priority']}\ndeadline: null\n"
              f"creator: human\nsummary: \"{n['summary']}\"\ntags: [\"{scenario_id}\"]\n")
    body = n["body"] or f"## Description\n\n{n['summary']}\n"
    return rel, f"---\n{fm}---\n\n{body}\n"


def _stamp(set_name: str) -> str:
    return f"orkcraft showcase sandbox · set {set_name} · demo {VERSION} — simulated data\n"


def build(root: Path = DEFAULT_DIR, reset: bool = False, set_name: str = "main") -> Path:
    """Write the sandbox under `root` and return it. Refuses a non-empty folder it did not create;
    a sandbox of another set or of an older demo is built again."""
    root = Path(root).expanduser().resolve()
    if root.exists() and any(root.iterdir()):
        if not (root / MARKER).exists():
            raise ValueError(f"{root} is not empty and is not an orkcraft demo — choose another folder")
        if not reset and (root / MARKER).read_text(encoding="utf-8") == _stamp(set_name):
            return root
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    (root / MARKER).write_text("orkcraft showcase sandbox — simulated data\n", encoding="utf-8")
    for sub in ("tasks/todo", "tasks/in-progress", "tasks/done", "tasks/ongoing", "context/knowledge", "processes"):
        (root / sub).mkdir(parents=True, exist_ok=True)

    scenarios = SETS[set_name]
    buildings_all: list[dict] = []
    for sc in scenarios:
        for n in sc["nodes"]:
            rel, text = _node_md(sc["id"], n)
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text(text, encoding="utf-8")
        for rel, text in sc["files"].items():
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text(text, encoding="utf-8")
        buildings_all += sc["buildings"]

    taken: set[str] = set()
    for spec in buildings_all:
        problems = masonry.save_spec(root, spec, taken)
        if problems:
            raise ValueError(f"demo building {spec['id']}: {'; '.join(problems)}")
        taken.add(spec["id"])

    scroll = make_scroll(scenarios)
    problems = ts.save(root / ".orkcraft.json", scroll)
    if problems:
        raise ValueError("demo scroll: " + "; ".join(problems))
    _chronicles(root, scroll)
    if set_name == "dashboard":
        from orkcraft.demo import dashboard
        dashboard.prepare(root)            # a real git repository, seeded Barracks and Council
    (root / SAMPLES).write_text(json.dumps(samples(scenarios), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (root / MARKER).write_text(_stamp(set_name), encoding="utf-8")       # last: a half-built sandbox is built again
    return root


def samples(scenarios: list[dict] = SCENARIOS) -> dict[str, dict]:
    """building id → the last result of its agent handler, shown in its 📥 pane (agents do not
    run in the demo, so their output is a prepared example)."""
    out = {}
    for sc in scenarios:
        for target, handlers in sc.get("handlers", {}).items():
            for h in handlers:
                if h.get("sample"):
                    harness = "→".join(s["harness"] for s in h.get("harness", [])) or h["kind"]
                    out[target] = {"title": f"{h['name']} · last result ({harness}, example)", "markdown": h["sample"]}
    return out


def make_scroll(scenarios: list[dict] = SCENARIOS) -> ts.TownScroll:
    """The Town Scroll of a sandbox set: up to eight orkspaces F1–F8, roads, handlers, stewards."""
    orkspaces = []
    for i, sc in enumerate(scenarios, 1):
        orkspaces.append(ts.Orkspace(sc["id"], sc["name"], sc["biome"], sc["icon"], f"F{i}", ts.GitLink(**sc["git"])))
    scroll = ts.TownScroll(scenarios[0]["id"], orkspaces, [])
    scroll.meta = {"project_name": "orkcraft demo", "tagline": "Work vs Humans — showcase (simulated data)"}
    scroll.preferences.update({"carts": "all", "roads": "faint", "view": "town"})
    scroll.budget.gold_session_limit_usd = 5.0
    for sc in scenarios:
        ork = scroll.orkspace(sc["id"])
        for spec, frac in zip(sc["buildings"], sc.get("layout") or QUADRANTS):
            b = ts.add_custom_building(scroll, spec, ork.id)
            b.frac = list(frac)
            if spec["id"] in sc.get("huts", {}):          # a spot of its own on the GUI's town (fractions)
                b.hut = list(sc["huts"][spec["id"]])
        ork.active_building = sc["buildings"][0]["id"]
        for target, handlers in sc.get("handlers", {}).items():
            for h in handlers:
                kw = {k: v for k, v in h.items() if k not in ("name", "sample")}
                ts.add_handler(scroll, target, h["name"], **kw)
        for target, source, event, label, handler, flt in sc["roads"]:
            ts.subscribe(scroll, target, source, event, flt, handler=handler, label=label)
        for (bid, orc_id), status in sc.get("status", {}).items():
            changes = {"status": status}
            order = sc.get("orders", {}).get((bid, orc_id))
            if order:
                changes["orders"] = order
            ts.update_orc(scroll, bid, orc_id, **changes)
        # stewards watch their buildings every morning, in the operator's working window
        for spec in sc["buildings"]:
            st = scroll.building(spec["id"]).garrison.steward
            if st.status == "idle":
                ts.update_orc(scroll, spec["id"], st.id, trigger={"type": "cron", "expression": "daily 05:00"})
    return scroll


def _chronicles(root: Path, scroll: ts.TownScroll) -> None:
    """A few past events per building, so the Chronicles overlay (L) has a history."""
    for b in scroll.buildings:
        ork = scroll.orkspace_of(b.id)
        chronicles.record(root, scroll, b.id, "building_raised", orkspace=ork.name if ork else "")
        for r in b.roads:
            src = scroll.building(r.source)
            orc = b.garrison.handler(r.handler) if r.handler else None
            chronicles.record(root, scroll, b.id, "road_subscribed", source=src.title if src else r.source,
                              event=r.label or r.event, handler=orc.name if orc else "plain")
        for h in b.garrison.handlers:
            chronicles.record(root, scroll, b.id, "orc_recruited", orc=h.name)


def scenario_summary(set_name: str = "main") -> list[dict]:
    """For docs and tests: id, name, segment, story, hotkey, roads with their signals."""
    out = []
    for i, sc in enumerate(SETS[set_name], 1):
        out.append({"hotkey": f"F{i}", "id": sc["id"], "name": sc["name"], "segment": sc["segment"],
                    "story": sc["story"], "signals": [r[3] for r in sc["roads"]]})
    return out
