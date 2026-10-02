"""Agents of the project's multi-agent systems: what each one runs on, what it is doing, how much is queued.

- Harness agents: Claude Code (orchestrator, owns tickets with `assignee: agent`)
  and direct `agy` dispatch.
- Pipeline agents: `<system>/.agents/agents/*.md`, with the model the pipeline
  specs actually give them (specs override the definition's own model).
- Activity comes from agy_chain run folders `<system>/.chain/<spec>_<stamp>/`: a
  `<step>.<n>.brief.md` without its `.out.txt` is running; a run without
  `run.md` is still active. Steps of an active run that never started are queued.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from orkcraft.sources.systems import HARNESS_AGY, System, discover_systems

HARNESS_CLAUDE = "claude"
ACTIVE_RUN_MAX_AGE_S = 12 * 3600
_BRIEF = re.compile(r"^(?P<label>.+)\.(?P<n>\d+)\.brief\.md$")
_RUN_DIR = re.compile(r"^(?P<spec>.+)_(?P<stamp>\d{8}_\d{6})$")
_FM_SEP = re.compile(r"\n---")


def _parse_frontmatter(text: str) -> dict:
    """Minimal frontmatter parser — only what agent definitions need."""
    if not text.startswith("---"):
        return {}
    m = _FM_SEP.search(text, 3)
    if not m:
        return {}
    fm_raw = text[3:m.start()].strip()
    out: dict = {}
    for line in fm_raw.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out



@dataclass
class Agent:
    name: str
    system: str
    harness: str
    models: list[str] = field(default_factory=list)
    declared_model: str | None = None
    doing: list[str] = field(default_factory=list)
    queue: list[str] = field(default_factory=list)
    path: Path | None = None
    description: str = ""
    schedule: str = ""
    status: str = ""  # from the definition, e.g. draft
    orc: str = ""     # orc name in orkcraft's clan (watchers → Council), from the definition

    @property
    def busy(self) -> bool:
        return bool(self.doing)


@dataclass
class ChainRun:
    system: str
    spec: str
    stamp: str
    path: Path
    running: list[str]   # step ids with a brief but no output yet
    started: set[str]    # step ids that got at least one brief
    finished: bool


def _step_id(label: str) -> str:
    """`code@T1#fix.2` style labels → spec step id `code`."""
    return label.split("#", 1)[0].split("@", 1)[0]


def scan_runs(system_root: Path, now: float | None = None) -> list[ChainRun]:
    now = now or time.time()
    runs: list[ChainRun] = []
    chain = system_root / ".chain"
    if not chain.is_dir():
        return runs
    for d in sorted(chain.iterdir()):
        m = _RUN_DIR.match(d.name)
        if not d.is_dir() or not m:
            continue
        files = list(d.iterdir())
        finished = (d / "run.md").exists()
        newest = max((f.stat().st_mtime for f in files), default=d.stat().st_mtime)
        if not finished and now - newest > ACTIVE_RUN_MAX_AGE_S:
            finished = True  # abandoned: the runner died without a summary
        names = {f.name for f in files}
        running, started = [], set()
        for name in names:
            b = _BRIEF.match(name)
            if not b or ".dry." in name:
                continue
            label = b.group("label")
            started.add(_step_id(label))
            if not finished and f"{label}.{b.group('n')}.out.txt" not in names:
                running.append(label)
        runs.append(ChainRun(system_root.name, m.group("spec"), m.group("stamp"), d, sorted(running), started, finished))
    return runs


def _definition(path: Path) -> dict:
    """Frontmatter of an agent definition (files may open with an HTML comment)."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    text = re.sub(r"^\s*<!--.*?-->\s*", "", text, count=1, flags=re.DOTALL)
    return _parse_frontmatter(text)


def collect_agents(repo_root: Path, now: float | None = None) -> list[Agent]:
    systems = discover_systems(repo_root)
    agents: dict[tuple[str, str], Agent] = {}

    for defn in sorted(repo_root.glob("*/.agents/agents/*.md")):
        system = defn.parent.parent.parent.name
        fm = _definition(defn)
        agents[(system, defn.stem)] = Agent(
            defn.stem, system,
            # Pipeline agents run under agy; a definition may name another harness.
            str(fm.get("harness") or HARNESS_AGY),
            declared_model=str(fm["model"]) if fm.get("model") else None,
            path=defn,
            description=str(fm.get("description") or ""),
            schedule=str(fm.get("schedule") or ""),
            status=str(fm.get("status") or ""),
            orc=str(fm.get("orc") or ""),
        )

    for sysm in systems:
        _attach_pipelines(sysm, agents, scan_runs(sysm.root, now))

    result = sorted(agents.values(), key=lambda a: (a.system, a.name))
    for a in result:
        if not a.models and a.declared_model:
            a.models = [a.declared_model]
    return result


def _attach_pipelines(sysm: System, agents: dict[tuple[str, str], Agent], runs: list[ChainRun]) -> None:
    stages = {s.name: s for s in sysm.stages}
    for stage in sysm.stages:
        for step in stage.agent_steps():
            if not step.agent:
                continue
            a = agents.setdefault((sysm.name, step.agent), Agent(step.agent, sysm.name, HARNESS_AGY))
            if step.model and step.model not in a.models:
                a.models.append(step.model)
    for run in runs:
        stage = stages.get(run.spec)
        if stage is None or run.finished:
            continue
        by_id = {s.id: s for s in stage.agent_steps()}
        for label in run.running:
            step = by_id.get(_step_id(label))
            if step and step.agent and (sysm.name, step.agent) in agents:
                agents[(sysm.name, step.agent)].doing.append(f"{run.spec}/{label}")
        for sid, step in by_id.items():
            if sid not in run.started and step.agent and (sysm.name, step.agent) in agents:
                agents[(sysm.name, step.agent)].queue.append(f"{run.spec}/{sid}")
