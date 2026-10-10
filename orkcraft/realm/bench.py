"""🧪 The Test bench: one building on a test case, beside the bare AI tool (docs/design/test-bench.md).

    bench.cases(root, "barracks")          the cases of a type: the shipped ones, then the town's own
    bench.make_project(case, root, dest)   a copy of the project to run in: no `origin`, nothing goes out
    bench.bare(case, workdir, tool, tier)  the AI tool alone, the task its only prompt → a Side
    bench.check(case, workdir)             the case's check in a tree: (passed, its last lines)
    bench.Report(...).save(run_dir)        both sides of a run, kept in .orkcraft/bench/runs/<run>/

The building's side opens a town on its copy (core/bench.py); this module has no face and no town.
A run never touches the town it was started from: its copies have no remote and their state is their own.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import shutil
import subprocess
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from orkcraft.realm import bench_cases, halt, jobs, tiers

BENCH = Path(".orkcraft") / "bench"
RUNS = BENCH / "runs"
CHECK_TIMEOUT_S = 600
TAIL = 1500
DEFAULT_MAX_SPEND = 2.0             # $ the building's side may spend in one run
DONE = "Test bench run kept: "      # the last line `orkcraft bench` prints: the run's id after it (gui/bench.py)
AUTHOR = ("-c", "user.name=Orkcraft bench", "-c", "user.email=bench@orkcraft.local")
_SLUG = re.compile(r"[^a-z0-9-]+")


# -- cases --------------------------------------------------------------------------------------------------

@dataclass
class Case:
    id: str
    type: str
    title: str
    task: str
    files: dict[str, str] = field(default_factory=dict)   # the whole project; empty: a copy of the town's own
    check: str = ""                                        # run in the result's tree: exit 0 passes
    expect: str = ""                                       # what a good result has, in words (for a judge)
    reviewed: bool = True                                  # an agent's case counts once the operator read it
    level: str = ""                                        # simple | medium | parallel: the path it should take

    @classmethod
    def of(cls, data: dict, type_id: str = "") -> Case:
        files = data.get("files") or {}
        return cls(id=slug(str(data.get("id") or data.get("title") or "case")),
                   type=str(data.get("type") or type_id), title=str(data.get("title") or data.get("id") or ""),
                   task=str(data.get("task") or ""),
                   files={str(k): str(v) for k, v in files.items()} if isinstance(files, dict) else {},
                   check=str(data.get("check") or ""), expect=str(data.get("expect") or ""),
                   reviewed=data.get("reviewed", True) is not False, level=str(data.get("level") or ""))


def slug(text: str) -> str:
    return _SLUG.sub("-", text.lower()).strip("-")[:40] or "case"


def cases(root: Path, type_id: str) -> list[Case]:
    """The shipped cases of a type, then the town's own (`.orkcraft/bench/<type>/*.json`); the town's wins on the
    same id. A file that does not read is left out."""
    found = {c.id: c for c in (Case.of(d, type_id) for d in bench_cases.CASES.get(type_id, ()))}
    folder = root / BENCH / type_id
    for path in sorted(folder.glob("*.json")) if folder.is_dir() else ():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict):
            c = Case.of({"id": path.stem, **data}, type_id)
            found[c.id] = c
    return [c for c in found.values() if c.task]


def case(root: Path, type_id: str, case_id: str) -> Case | None:
    return next((c for c in cases(root, type_id) if c.id == case_id), None)


LEVELS = ("simple", "medium", "parallel")      # the path a case should take in the building
ALL = "all"


def series(found: list[Case], case_id: str = "", level: str = "") -> list[Case]:
    """The cases a run takes, in order: one by its id, `all` of them, every one of a level, else the first. Only
    the cases the operator read count in a series."""
    if level:
        return [c for c in found if c.level == level and c.reviewed]
    if case_id == ALL:
        return [c for c in found if c.reviewed]
    if case_id:
        return [c for c in found if c.id == case_id][:1]
    return found[:1]


def bench_cases_of(type_id: str) -> list[dict]:
    """The shipped cases of a type, as data."""
    return list(bench_cases.CASES.get(type_id, ()))


def save_case(root: Path, c: Case) -> Path:
    """A case in the town's own (`.orkcraft/bench/<type>/<id>.json`)."""
    path = root / BENCH / c.type / f"{c.id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {k: v for k, v in asdict(c).items() if k != "id"}
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def mark_read(root: Path, type_id: str, case_id: str) -> bool:
    """The operator read a written case: it counts from now on. False when there is no such case of the town's."""
    c = case(root, type_id, case_id)
    if c is None or not (root / BENCH / type_id / f"{case_id}.json").is_file():
        return False
    c.reviewed = True
    save_case(root, c)
    return True


# -- the copy of a project ----------------------------------------------------------------------------------

def git(cwd: Path, *args: str, timeout: float = jobs.GIT_TIMEOUT_S) -> str:
    done = halt.run(["git", *args], cwd=cwd, timeout=timeout, who="bench git")
    if done.returncode != 0:
        raise RuntimeError((done.stderr or done.stdout).strip()[:300] or f"git {args[0]} failed")
    return done.stdout.strip()


def make_project(c: Case, root: Path, dest: Path) -> str:
    """The project the case starts from, in `dest`, committed: the case's own files, else a clone of the town's
    project at its HEAD. It never has an `origin`, so nothing is pushed and no pull request opens. Its base commit."""
    if dest.exists():
        shutil.rmtree(dest)
    if c.files:
        dest.mkdir(parents=True)
        for rel, text in c.files.items():
            path = (dest / rel).resolve()
            if dest.resolve() not in path.parents:
                raise ValueError(f"the case's file {rel!r} is outside its project")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        if ".gitignore" not in c.files:              # the town the bench opens on it, and what a check leaves
            (dest / ".gitignore").write_text(".orkcraft/\n.orkcraft.json\n__pycache__/\n.pytest_cache/\n",
                                             encoding="utf-8")
        git(dest, "init", "-q", "-b", "main")
        git(dest, "add", "-A")
        git(dest, *AUTHOR, "commit", "-q", "-m", f"bench: {c.id}")
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        git(dest.parent, "clone", "-q", "--no-hardlinks", str(root), dest.name)
        git(dest, "remote", "remove", "origin")
    git(dest, "config", "user.name", "Orkcraft bench")
    git(dest, "config", "user.email", "bench@orkcraft.local")
    return git(dest, "rev-parse", "HEAD")


def changed(workdir: Path, base: str, ref: str = "") -> tuple[list[str], int]:
    """(files, lines added and removed) from `base` to `ref`, or to the tree as it is (what is not committed too)."""
    if ref:
        out = git(workdir, "diff", "--numstat", f"{base}..{ref}")
    else:
        git(workdir, "add", "-A")
        out = git(workdir, "diff", "--cached", "--numstat", base)
    files, lines = [], 0
    for row in out.splitlines():
        parts = row.split("\t")
        if len(parts) == 3:
            files.append(parts[2])
            lines += sum(int(n) for n in parts[:2] if n.isdigit())
    return files, lines


def check(c: Case, workdir: Path, timeout: float = CHECK_TIMEOUT_S) -> tuple[bool | None, str]:
    """The case's check in `workdir`: (passed, its last lines); (None, "") when the case has none."""
    if not c.check.strip():
        return None, ""
    try:
        done = halt.run(["sh", "-c", c.check], cwd=workdir, timeout=timeout, who="bench check")
    except subprocess.TimeoutExpired:
        return False, f"the check ran over {int(timeout)} s"
    return done.returncode == 0, ((done.stdout or "") + (done.stderr or "")).strip()[-TAIL:]


# -- a side and a run ---------------------------------------------------------------------------------------

@dataclass
class Side:
    name: str                          # building | bare
    seconds: float = 0.0
    cost: float = 0.0                  # $, the steward's included
    tokens: int = 0
    error: str = ""                    # it did not finish: why
    cut: bool = False                  # stopped at the run's spend limit or its time
    passed: bool | None = None         # the case's check; None: no check, or nothing to check
    check_tail: str = ""
    files: list[str] = field(default_factory=list)
    lines: int = 0
    text: str = ""                     # its last report
    how: list[str] = field(default_factory=list)   # how it went: decisions, orks, parts, reworks
    orks: int = 0
    where: str = ""                    # the tree its result is in
    steps: list[dict] = field(default_factory=list)   # its decisions on the run's clock: {t, who, action, why}


def bare(c: Case, workdir: Path, tool: str = "main", tier: str = "", cancel: threading.Event | None = None,
         runner=None) -> Side:
    """The AI tool alone in `workdir`, on the tier's model, with the task as its only prompt, then the check."""
    model = tiers.resolve(tool, tier) if tier else ""
    run = runner or jobs.run_work
    side, start = Side("bare", where=str(workdir)), time.monotonic()
    base = git(workdir, "rev-parse", "HEAD")
    try:
        text, cost, tokens, _session = run(tool, c.task, workdir, cancel or threading.Event(), model)
        side.text, side.cost, side.tokens = (text or "")[:4000], float(cost or 0.0), int(tokens or 0)
    except (RuntimeError, OSError, halt.Halted) as e:
        side.error = str(e)[:500] or type(e).__name__
    side.seconds = round(time.monotonic() - start, 1)
    side.files, side.lines = changed(workdir, base)
    if not side.error:
        side.passed, side.check_tail = check(c, workdir)
    return side


@dataclass
class Report:
    id: str
    type: str
    case: str
    tool: str = "main"
    tier: str = ""
    at: str = ""
    building: Side | None = None
    bare: Side | None = None
    orders_changed: bool = False       # the building ran on instructions changed for this run

    def save(self, run_dir: Path) -> Path:
        run_dir.mkdir(parents=True, exist_ok=True)
        path = run_dir / "report.json"
        path.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: Path) -> Report:
        data = json.loads(path.read_text(encoding="utf-8"))
        known = set(Side.__dataclass_fields__)
        sides = {k: Side(**{f: v for f, v in data[k].items() if f in known}) if data.get(k) else None
                 for k in ("building", "bare")}
        return cls(**{**{k: v for k, v in data.items() if k in cls.__dataclass_fields__}, **sides})


def run_dir(root: Path, c: Case, now: dt.datetime | None = None) -> Path:
    stamp = (now or dt.datetime.now()).strftime("%Y%m%d-%H%M%S")
    return root / RUNS / f"{stamp}-{c.type}-{c.id}"


def runs(root: Path, type_id: str = "") -> list[Report]:
    """The kept runs, newest first (of one type, when named)."""
    folder = root / RUNS
    out = []
    for path in sorted(folder.glob("*/report.json"), reverse=True) if folder.is_dir() else ():
        try:
            r = Report.load(path)
        except (OSError, ValueError, TypeError):
            continue
        if not type_id or r.type == type_id:
            out.append(r)
    return out


# -- what a person reads ------------------------------------------------------------------------------------

def verdict(s: Side) -> str:
    if s.error:
        return "did not finish"
    return {True: "passed", False: "failed", None: "no check"}[s.passed]


def render(r: Report, building_word: str = "Building") -> str:
    """The run as a table: each side's time, spend, tokens, check and change, then how the building went."""
    sides = [s for s in (r.building, r.bare) if s is not None]
    names = {"building": building_word, "bare": "Bare AI tool"}
    rows = [("", *(names.get(s.name, s.name) for s in sides)),
            ("Time", *(f"{s.seconds:.0f} s" + (" (cut)" if s.cut else "") for s in sides)),
            ("Spend", *(f"${s.cost:.2f}" for s in sides)),
            ("Tokens", *(f"{s.tokens:,}" if s.tokens else "not reported" for s in sides)),
            ("Check", *(verdict(s) for s in sides)),
            ("Change", *(f"{len(s.files)} file{'' if len(s.files) == 1 else 's'}, {s.lines} line{'' if s.lines == 1 else 's'}"
                         for s in sides))]
    width = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]
    tier = f", {tiers.label(r.tier)}" if r.tier else ""
    out = [f"Test bench: {r.case} ({r.type}), AI tool {r.tool}{tier}", ""]
    out += ["  ".join(cell.ljust(width[i]) for i, cell in enumerate(row)).rstrip() for row in rows]
    for s in sides:
        if s.error:
            out += ["", f"{names.get(s.name, s.name)} did not finish: {s.error}"]
        if s.passed is False and s.check_tail:
            out += ["", f"{names.get(s.name, s.name)}'s check, last lines:", s.check_tail[-600:]]
    if r.building and r.building.how:
        out += ["", f"How the {building_word} went ({r.building.orks} ork{'' if r.building.orks == 1 else 's'}):"] + [f"  {h}" for h in r.building.how]
    for s in sides:
        if s.where:
            out += [f"{names.get(s.name, s.name)}'s result: {s.where}"]
    return "\n".join(out)


GAP_LIMIT = 0.10                    # how far the building may be from the bare tool, on time and on spend


def gaps(r: Report) -> dict[str, float | None]:
    """How far the building is from the bare tool: time and spend as a share over it (0.25: 25 % more, below 0:
    less), quality 0 when both checks agree, 1 when the building's is worse, -1 when better. None: not measured."""
    b, t = r.building, r.bare
    if b is None or t is None:
        return {"time": None, "spend": None, "quality": None}

    def over(mine: float, theirs: float) -> float | None:
        return (mine - theirs) / theirs if theirs > 0 else None

    def score(s: Side) -> int:
        return -2 if s.error else {True: 1, None: 0, False: -1}[s.passed]

    quality = float((score(t) > score(b)) - (score(b) > score(t)))
    return {"time": over(b.seconds, t.seconds), "spend": over(b.cost, t.cost), "quality": quality}


def summary(reports: list[Report], building_word: str = "Building", limit: float = GAP_LIMIT) -> str:
    """The runs of several cases side by side: each one's time, spend and check, the building against the bare
    tool, and whether it stays within `limit`."""
    def pct(v: float | None) -> str:
        return "—" if v is None else f"{v:+.0%}"

    rows = [("Case", "Time", "Spend", "Check", f"Within {limit:.0%}")]
    for r in reports:
        g, b, t = gaps(r), r.building, r.bare
        check = f"{verdict(b)} / {verdict(t)}" if b and t else "—"
        rows.append((r.case, pct(g["time"]), pct(g["spend"]), check, "yes" if within(g, limit) else "no"))
    width = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]
    out = [f"{building_word} against the bare AI tool (time and spend: how much more; check: {building_word} / bare)", ""]
    out += ["  ".join(cell.ljust(width[i]) for i, cell in enumerate(row)).rstrip() for row in rows]
    return "\n".join(out)


def against(root: Path, type_id: str) -> list[dict]:
    """The latest run with both sides of each case, by the cases' order: how far the building is from the bare tool.
    For the bench window's summary."""
    order = {c.id: (n, c.level) for n, c in enumerate(cases(root, type_id))}
    latest: dict[str, Report] = {}
    for r in runs(root, type_id):                      # newest first
        if r.building is not None and r.bare is not None and r.case not in latest:
            latest[r.case] = r
    rows = []
    for cid, r in sorted(latest.items(), key=lambda kv: order.get(kv[0], (len(order), ""))[0]):
        g = gaps(r)
        rows.append({"case": cid, "level": order.get(cid, (0, ""))[1], "run": r.id, "tool": r.tool, **g,
                     "building": verdict(r.building), "bare": verdict(r.bare),
                     "within": within(g)})
    return rows


def within(g: dict, limit: float = GAP_LIMIT) -> bool:
    """The building is no worse on its check and at most `limit` over the bare tool on time and on spend."""
    return g["quality"] is not None and g["quality"] <= 0 and \
        all(v is not None and v <= limit for v in (g["time"], g["spend"]))
