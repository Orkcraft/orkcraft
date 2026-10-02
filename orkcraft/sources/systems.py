"""Multi-agent systems: any top-level folder with `pipelines/*.json` agy_chain specs.

A system's stages are its specs (ordered by the table in the README, `| # | `spec.json` |`,
when there is one); a stage's scheme is its steps grouped into waves by `after`.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

HARNESS_AGY = "agy"
HARNESS_SCRIPT = "script"
_ORDER_ROW = re.compile(r"^\|\s*(\d+)\s*\|\s*`([\w.-]+\.json)`", re.MULTILINE)


@dataclass
class Step:
    id: str
    kind: str  # agent | run | group
    agent: str | None = None
    model: str | None = None
    run: str | None = None
    after: list[str] = field(default_factory=list)
    steps: list[Step] = field(default_factory=list)  # group members
    items_from: str | None = None
    sequential: bool = False
    loops: list[dict] = field(default_factory=list)

    @property
    def harness(self) -> str:
        return HARNESS_SCRIPT if self.kind == "run" else HARNESS_AGY


@dataclass
class Stage:
    name: str
    description: str
    path: Path
    steps: list[Step]
    loops: list[dict]
    order: int | None = None

    def waves(self) -> list[list[Step]]:
        """Topological levels: steps in one wave may run in parallel."""
        by_id = {s.id: s for s in self.steps}
        level: dict[str, int] = {}

        def depth(sid: str, trail: frozenset[str]) -> int:
            if sid in level:
                return level[sid]
            s = by_id.get(sid)
            deps = [d for d in (s.after if s else []) if d in by_id and d not in trail]
            level[sid] = 1 + max((depth(d, trail | {d}) for d in deps), default=-1)
            return level[sid]

        for s in self.steps:
            depth(s.id, frozenset({s.id}))
        waves: list[list[Step]] = []
        for s in self.steps:
            while len(waves) <= level[s.id]:
                waves.append([])
            waves[level[s.id]].append(s)
        return waves

    def agent_steps(self) -> list[Step]:
        out: list[Step] = []
        for s in self.steps:
            out += [m for m in s.steps if m.kind == "agent"] if s.kind == "group" else ([s] if s.kind == "agent" else [])
        return out


@dataclass
class System:
    name: str
    root: Path
    stages: list[Stage]


def _model(step: dict, defaults: dict) -> str | None:
    if step.get("model"):
        return str(step["model"])
    if step.get("chain"):
        return " → ".join(step["chain"])
    if defaults.get("model"):
        return str(defaults["model"])
    if defaults.get("chain"):
        return " → ".join(defaults["chain"])
    return None


def _step(raw: dict, defaults: dict) -> Step:
    after = list(raw.get("after") or [])
    if "run" in raw:
        return Step(raw["id"], "run", run=str(raw["run"]), after=after)
    return Step(raw["id"], "agent", agent=raw.get("agent"), model=_model(raw, defaults), after=after)


def load_stage(path: Path) -> Stage | None:
    try:
        spec = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    defaults = spec.get("defaults") or {}
    steps = [_step(s, defaults) for s in spec.get("steps", [])]
    for g in spec.get("groups", []):
        steps.append(Step(
            g["id"], "group",
            after=list(g.get("after") or []),
            steps=[_step(s, defaults) for s in g.get("steps", [])],
            items_from=g.get("items_from"),
            sequential=bool(g.get("sequential")),
            loops=list(g.get("review_loops") or []),
        ))
    return Stage(
        name=str(spec.get("name") or path.stem),
        description=str(spec.get("description") or ""),
        path=path,
        steps=steps,
        loops=list(spec.get("review_loops") or []),
    )


def _readme_order(root: Path) -> dict[str, int]:
    for readme in (root / "pipelines" / "README.md", root / "README.md"):
        try:
            text = readme.read_text(encoding="utf-8")
        except OSError:
            continue
        found = {name: int(n) for n, name in _ORDER_ROW.findall(text)}
        if found:
            return found
    return {}


def discover_systems(repo_root: Path) -> list[System]:
    systems: list[System] = []
    for pipelines in sorted(repo_root.glob("*/pipelines")):
        root = pipelines.parent
        if root.name.startswith((".", "_")):
            continue
        order = _readme_order(root)
        stages = [s for s in (load_stage(p) for p in sorted(pipelines.glob("*.json"))) if s]
        if not stages:
            continue
        for s in stages:
            s.order = order.get(s.path.name)
        stages.sort(key=lambda s: (s.order is None, s.order or 0, s.name))
        systems.append(System(root.name, root, stages))
    return systems


def _loop_line(loop: dict) -> str:
    cap = loop.get("max_rounds", "?")
    on_cap = loop.get("on_cap", "continue")
    how = "checks" if loop.get("verdict") == "checks" else "review"
    return f"⇄ {loop.get('review')} ↔ {loop.get('fix')}  ({how}, max {cap}, at cap: {on_cap})"


def _step_line(s: Step) -> str:
    if s.kind == "run":
        cmd = s.run or ""
        return f"⚙ {s.id}: script `{cmd if len(cmd) <= 70 else cmd[:67] + '…'}`"
    return f"🤖 {s.id}: {s.agent}  [{HARNESS_AGY} · {s.model or 'default model'}]"


def scheme_lines(stage: Stage) -> list[str]:
    """Plain-text scheme: waves top to bottom, ∥ inside a wave means parallel."""
    lines: list[str] = []
    waves = stage.waves()
    for n, wave in enumerate(waves, 1):
        par = "  ∥ parallel" if len(wave) > 1 else ""
        lines.append(f"── wave {n}{par}")
        for s in wave:
            if s.kind == "group":
                mode = "one item at a time" if s.sequential else "items in parallel"
                lines.append(f"   ⟳ {s.id}: for each item of `{s.items_from}` ({mode})")
                for i, m in enumerate(s.steps):
                    arrow = "→ " if i else "  "
                    lines.append(f"      {arrow}{_step_line(m)}")
                lines += [f"      {_loop_line(l)}" for l in s.loops]
            else:
                lines.append(f"   {_step_line(s)}")
        if n < len(waves):
            lines.append("      ↓")
    if stage.loops:
        lines.append("")
        lines += [f"{_loop_line(l)}" for l in stage.loops]
    return lines
