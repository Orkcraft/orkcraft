"""`orkcraft check`: the gate before people use it (docs/design/check.md, realm/check.py). Each scenario's cases run
in their building and in the bare AI tool (core/bench.py), `repeat` times each, on the cheap AI tool by default (agy,
its lightest model); the pictures are painted and judged (realm/check_pictures.py); then a quiet demo town is ticked
for hours with every model seam counted (gui/idle_check.py).

Everything one check saw is kept in one folder, made to be read by an agent overnight (`.orkcraft/check/<stamp>/`):
README.md (what is where, and how to work through it), report.md, results.json, every run with every model call in
full (prompt, output, the tool's own trail), the pictures, the idle count — and check.zip of it all. The exit code is 0
when it is green, 1 when it is red.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import tempfile
import zipfile
from pathlib import Path

LATEST = "latest.txt"                       # .orkcraft/check/latest.txt: the stamp of the last check


def add_parser(subparsers) -> None:
    p = subparsers.add_parser("check", help="Run the main jobs on the cheap AI tool and a quiet town: green or red")
    p.add_argument("--scenario", action="append", default=[],
                   help="Only this scenario (mail, todos, board, pictures, wiki); may be given more than once")
    p.add_argument("--only", choices=("scenarios", "idle"), default=None, help="Only the scenarios, or only idle")
    p.add_argument("--tool", default=None, help="The AI tool both sides run on (default: the budget's, agy)")
    p.add_argument("--tier", default=None, help="novice, seasoned or veteran (default: the budget's, novice)")
    p.add_argument("--repeat", type=int, default=None, help="Runs of each case (default: the budget's, 3)")
    p.add_argument("--max-spend", type=float, default=None, help="$ one run of a building may spend (default: 2)")
    p.add_argument("--list", action="store_true", help="Say what it would run, and the budget, and stop")
    p.add_argument("--replay", default="", metavar="STAMP",
                   help="Run the buildings again on the answers a check recorded (its stamp, or latest): free, no AI "
                        "tool is called; says whether each run came out as it did then")


def run(root: Path, args: argparse.Namespace, tier_words: dict[str, str]) -> int:
    from orkcraft.realm import bench, check
    if args.replay:
        return replay(root, args.replay, args.scenario)
    budget = check.budgets(root)
    for key, value in (("repeat", args.repeat), ("max_spend", args.max_spend), ("tool", args.tool),
                       ("tier", args.tier)):
        if value is not None:
            budget[key] = value
    if not 1 <= int(budget["repeat"]) <= bench.REPEAT_MAX:
        sys.stderr.write(f"orkline error: --repeat is 1 to {bench.REPEAT_MAX}\n")
        return 2
    tier = tier_words.get(str(budget["tier"]).lower(), str(budget["tier"]).lower())
    if tier and tier not in tier_words.values():
        sys.stderr.write("orkline error: --tier is novice, seasoned or veteran\n")
        return 2
    known = [s.id for s in check.SCENARIOS]
    if any(s not in known for s in args.scenario):
        sys.stderr.write(f"orkline error: the scenarios are {', '.join(known)}\n")
        return 2
    tool = str(budget["tool"] or "main")
    scenarios = check.picked(args.scenario) if args.only != "idle" else []
    runs = sum(len(s.cases) for s in scenarios if s.type and s.type != check.LOOK) * int(budget["repeat"])
    print(f"Orkline check: {runs} runs on {tool}{' (' + budget['tier'] + ')' if budget['tier'] else ''}, each "
          f"building run stopped at ${budget['max_spend']:.2f}; the bare tool's answers already kept are not asked again"
          + ("" if args.only == "scenarios" else f"; then a quiet demo town ticked for {budget['idle_hours']} hours "
                                                  "with its model calls counted (none is made)") + ".", flush=True)
    for s in scenarios:
        print(f"  {s.id:8} {s.title}: {', '.join(s.cases) if s.type else 'not checked yet'} — {s.about}")
    if args.list:
        print(json.dumps(budget, indent=2))
        return 0
    series = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    folder = root / check.DIR / series
    folder.mkdir(parents=True, exist_ok=True)
    results = []
    for s in scenarios:
        cases = []
        for cid in s.cases:
            if s.type == check.LOOK:
                cases += _looks(root, folder, tool, tier)
                break
            if s.type == check.PICTURE:
                cases.append((cid, _picture(s, cid, tool, tier, budget, folder / "runs" / s.id / cid)))
            elif s.type:
                cases.append((cid, _case(root, s, cid, tool, tier, budget, series, folder / "runs" / s.id / cid)))
        results.append({"scenario": s, "cases": cases})
    idle = None
    if args.only != "scenarios":
        print("\nA quiet town, ticked a minute a tick…", flush=True)
        from orkcraft.gui import idle_check
        idle = idle_check.count(int(float(budget["idle_hours"]) * 60))
        (folder / "idle.json").write_text(json.dumps(idle, indent=2), encoding="utf-8")
    green, text = check.report(results, idle, budget, tool)
    data = {"series": series, "green": green, "budget": budget, "idle": idle,
            "scenarios": [{"id": r["scenario"].id, "type": r["scenario"].type,
                           "cases": [{"case": c, **j} for c, j in r["cases"]]} for r in results]}
    plain = check.words(check.told(root, series, json.loads(json.dumps(data, default=str))["scenarios"]))
    if plain:
        text = text.replace("\n\n**GREEN**", f"\n\n## In plain words\n\n{plain}\n\n**GREEN**") \
            .replace("\n\n**RED**", f"\n\n## In plain words\n\n{plain}\n\n**RED**")
    from orkcraft.realm import check_history
    check_history.add(root, series, json.loads(json.dumps(data, default=str)))
    moved = check_history.since(root, series)
    data["since"] = moved
    if moved:
        lines = "\n".join(f"- {'▼' if m['dir'] == 'worse' else '▲'} {m['case']}: {m['said']}" for m in moved)
        text = text.replace("\n\n## In plain words", f"\n\n## Since the last check\n\n{lines}\n\n## In plain words", 1) \
            if "## In plain words" in text else text + f"\n## Since the last check\n\n{lines}\n"
    (folder / "report.md").write_text(text, encoding="utf-8")
    (folder / "results.json").write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    (folder / "README.md").write_text(readme(series, green, text), encoding="utf-8")
    pack(folder)
    (root / check.DIR / LATEST).write_text(series, encoding="utf-8")
    print("\n" + text)
    print(f"Everything it saw: {folder} (README.md first; check.zip is all of it).", flush=True)
    return 0 if green else 1


def _case(root: Path, s, cid: str, tool: str, tier: str, budget: dict, series: str, out: Path) -> dict:
    from orkcraft.core import bench as building_bench
    from orkcraft.realm import bench, check
    case = bench.case(root, s.type, cid)
    if case is None:
        return {"ok": False, "why": f"no case {cid!r} of the {s.type} type", "runs": 0}
    reports = []
    for attempt in range(int(budget["repeat"])):
        print(f"\n{s.title} · {case.title} (run {attempt + 1} of {budget['repeat']})", flush=True)
        try:
            report, _folder = building_bench.run(root, case, tool, tier, "", float(budget["max_spend"]),
                                                 say=lambda line: print(f"  {line}", flush=True),
                                                 attempt=attempt, series=series)
        except (ValueError, RuntimeError, OSError) as e:
            return {"ok": False, "why": f"it did not run: {e}"[:300], "runs": len(reports)}
        reports.append(report)
        _keep_run(root, report, out / f"run-{attempt + 1}", s.title)
    got = check.judge(reports, budget)
    print(f"  → {'✅' if got['ok'] else '❌'} {got['why'] or 'within the budget'}", flush=True)
    return got


def _picture(s, cid: str, tool: str, tier: str, budget: dict, out: Path) -> dict:
    from orkcraft.realm import call_log, check, check_pictures, tiers
    case = next(c for c in check_pictures.CASES if c["id"] == cid)
    judge_model = tiers.resolve(tool, tier) if tier else ""
    judge_model = "" if judge_model in tiers.TIERS else judge_model
    runs = []
    for attempt in range(int(budget["repeat"])):
        print(f"\n{s.title} · {cid}: “{case['words']}” (run {attempt + 1} of {budget['repeat']})", flush=True)
        at = out / f"run-{attempt + 1}"
        with tempfile.TemporaryDirectory(prefix="orkcraft-check-") as tmp, call_log.kept(Path(tmp), "building"):
            # the painting on the tool's own model (a light one may make no pictures); the judging on the light one
            got = check_pictures.run(case, tool, "", at, judge=lambda p, w: _read(tool, p, w, judge_model))
            _export_calls(Path(tmp), at / "calls")
        (at / "result.json").write_text(json.dumps(got, indent=2, ensure_ascii=False), encoding="utf-8")
        runs.append(got)
        said = f"error: {got['error']}" if got["error"] else f"judge {got['score']}/10: {got['notes'][:160]}"
        print(f"  {said}", flush=True)
    j = check.judge_pictures(runs, budget)
    print(f"  → {'✅' if j['ok'] else '❌'} {j['why'] or 'within the budget'}", flush=True)
    return j


def _read(tool: str, prompt: str, workdir: Path, model: str) -> str:
    import threading
    from orkcraft.realm import jobs
    return jobs.run_read(tool, prompt, workdir, threading.Event(), model)[0]


def _keep_run(root: Path, report, at: Path, title: str) -> None:
    """A run as an agent reads it: its report, its analysis as text, and every model call in full."""
    from orkcraft.realm import bench, call_log
    at.mkdir(parents=True, exist_ok=True)
    (at / "report.json").write_text(json.dumps(_asdict(report), indent=2, ensure_ascii=False), encoding="utf-8")
    lines = bench.calls_of(root, report)
    (at / "analysis.md").write_text(bench.analysis(report, title, lines), encoding="utf-8")
    own = root / bench.RUNS / report.id / "calls"
    _export_calls(own, at / "calls", [x for x in call_log.read(own)])
    if report.bare is not None and report.bare.kept and report.bare.kept != report.id:
        kept = root / bench.RUNS / report.bare.kept / "calls"
        _export_calls(kept, at / "calls", [x for x in call_log.read(kept) if x.get("side") == "bare"], prefix="kept-")


def _asdict(report) -> dict:
    from dataclasses import asdict
    return asdict(report)


def _export_calls(src: Path, dst: Path, lines: list[dict] | None = None, prefix: str = "") -> None:
    """Each call as plain JSON: its line, the prompt, the output, the errors and the tool's trail."""
    from orkcraft.realm import call_log
    lines = call_log.read(src) if lines is None else lines
    if not lines:
        return
    dst.mkdir(parents=True, exist_ok=True)
    with (dst / f"{prefix}calls.jsonl").open("a", encoding="utf-8") as f:
        for x in lines:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")
    for x in lines:
        name = f"{prefix}{x.get('side') or 'call'}-{str(x.get('raw') or '').removesuffix('.gz')}"
        (dst / name).write_text(json.dumps({"line": x, **call_log.raw(src, x)}, indent=1, ensure_ascii=False),
                                encoding="utf-8")


def readme(series: str, green: bool, report: str) -> str:
    """What the folder holds and how to work through it: the brief an agent reads before anything else."""
    return f"""# Orkline check {series}: {'GREEN' if green else 'RED'}

This folder is everything one `orkcraft check` saw. It is made to be read by an agent (Claude Code, overnight) that
finds why a line is red or costly and changes Orkline so the next check is better.

## What is where

- `report.md` — the verdict: each case, its check (building · bare), time and spend over the bare AI tool, ✅/❌, why.
- `results.json` — the same as data, with the budget it was held to.
- `runs/<scenario>/<case>/run-<n>/` — one run:
  - `analysis.md` — both sides in full: the table, the model calls added up, the decisions on the clock, the report;
  - `report.json` — the run as data;
  - `calls/` — every model call: `calls.jsonl` a line each (who, what for, model, seconds, tokens, cost, usage), and
    `<side>-<n>-<who>.json` the call itself (`prompt`, `stdout`, `stderr`, `trail`: the tool's own session, with
    its thinking and tool calls, when it keeps one); `kept-…` is the bare tool's answer read back from an earlier run;
  - for a picture: `reference.png`, `out.png`, `judge.json`, `result.json`.
- `idle.json` — the model calls a quiet town made on its own (it should make none) and who made them.

## How to work through it

1. Read `report.md`. Take the ❌ lines first, then the most expensive ✅ ones.
2. For each, open its runs' `analysis.md`, then the calls: compare the building's calls with the bare tool's. Look for
   prompts that repeat context, calls that could be skipped (a review the tests already settle), a heavier model than
   the work needs, reworks, answers that miss what the check asks for.
3. Find the cause in the code (`orkcraft/core/workers/<building>.py`, its prompts in `orkcraft/realm/`), change the
   smallest thing that fixes it, and run the tests of the modules you touched.
4. Check again only what you changed: `orkcraft check --scenario <id>` (and `--repeat 3`: medians, not one run).
5. Write what you changed and what the numbers did, case by case, before and after.

The project's rules for changes are in its CLAUDE.md.

## The verdict

{report}"""


def pack(folder: Path) -> Path:
    """check.zip: the whole folder, for a download."""
    target = folder / "check.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(folder.rglob("*")):
            if p.is_file() and p != target:
                z.write(p, p.relative_to(folder))
    return target


def latest(root: Path) -> Path | None:
    """The folder of the last check (None before the first)."""
    from orkcraft.realm import check
    try:
        stamp = (root / check.DIR / LATEST).read_text(encoding="utf-8").strip()
    except OSError:
        return None
    folder = root / check.DIR / stamp
    return folder if stamp and folder.is_dir() else None



# -- the answers played back (docs/design/check.md §11) -------------------------------------------------------------------

def replay(root: Path, stamp: str, scenarios: list[str] | None = None) -> int:
    """Each run of the check `stamp` again, its building's calls answered from what was recorded (realm/call_log.py
    `replaying`): no AI tool is called, nothing is paid. A run is the same when its building finishes, asks for no
    more than it did, and passes or fails its check as it did then. 0 when every run is the same."""
    from orkcraft.core import bench as building_bench
    from orkcraft.realm import bench, call_log, check
    folder = latest(root) if stamp == "latest" else root / check.DIR / stamp
    try:
        data = json.loads((folder / "results.json").read_text(encoding="utf-8")) if folder else {}
    except (OSError, ValueError):
        data = {}
    if not data:
        sys.stderr.write(f"orkline error: no check {stamp!r} to play back (.orkcraft/check/<stamp>/results.json)\n")
        return 2
    series = dt.datetime.now().strftime("%Y%m%d-%H%M%S") + "-replay"
    rows, same_all = [], True
    for sc in data.get("scenarios") or []:
        if not sc.get("type") or sc["type"] == check.PICTURE or (scenarios and sc.get("id") not in scenarios):
            continue
        for case_dir in sorted((folder / "runs" / sc["id"]).glob("*")):
            case = bench.case(root, sc["type"], case_dir.name)
            for n, run_dir in enumerate(sorted(case_dir.glob("run-*"))):
                try:
                    then = bench.Report.load(run_dir / "report.json")
                except (OSError, ValueError, TypeError):
                    continue
                if case is None or then.building is None:
                    rows.append((sc["id"], case_dir.name, run_dir.name, "—", "no such case now", False))
                    same_all = False
                    continue
                print(f"{sc['id']} · {case.title} · {run_dir.name}: played back", flush=True)
                with call_log.replaying(run_dir / "calls"):
                    try:
                        now, _f = building_bench.run(root, case, then.tool, then.tier, "", bench.DEFAULT_MAX_SPEND,
                                                     sides=("building",), attempt=n, series=series)
                    except (ValueError, RuntimeError, OSError) as e:
                        now = None
                        error = str(e)[:200]
                    left = call_log.unanswered()
                same, why = _same(then.building, now.building if now is not None else None, left)
                if now is None:
                    why = f"it did not run: {error}"
                rows.append((sc["id"], case_dir.name, run_dir.name, bench.verdict(then.building),
                             why, same))
                same_all = same_all and same
    out = [f"# Replay of the check {folder.name}", "",
           "Each run again, its building's model calls answered from what was recorded: no AI tool called.", "",
           "| Scenario | Case | Run | Then | Now | |", "|---|---|---|---|---|---|"]
    out += [f"| {s} | {c} | {r} | {t} | {w} | {'✅' if ok else '❌'} |" for s, c, r, t, w, ok in rows]
    out += ["", f"**{'SAME' if same_all and rows else 'CHANGED'}**: {sum(r[5] for r in rows)} of {len(rows)} runs came "
                "out as they did"]
    text = "\n".join(out) + "\n"
    target = root / check.DIR / series
    target.mkdir(parents=True, exist_ok=True)
    (target / "report.md").write_text(text, encoding="utf-8")
    print("\n" + text)
    return 0 if same_all and rows else 1


def _same(then, now, left: int) -> tuple[bool, str]:
    """Whether a run played back came out as it was recorded, and what it came to now, in words."""
    from orkcraft.realm import bench
    if now is None:
        return False, "it did not run"
    if now.error:
        return False, f"did not finish: {now.error[:160]}"
    failed = lambda s: sorted(x["name"] for x in s.checks if not x.get("ok"))  # noqa: E731
    said = bench.verdict(now)
    if now.passed != then.passed or failed(now) != failed(then):
        return False, f"{said} (then {bench.verdict(then)})"
    if left:
        return False, f"{said}, but it asked the AI tool {left} time{'s' if left > 1 else ''} less than then"
    return True, said


# -- the windows' look (gui/look_check.py, docs/design/check.md §12) -------------------------------------------------------

def _looks(root: Path, folder: Path, tool: str, tier: str) -> list[tuple[str, dict]]:
    """Every window pictured, held against the last check that pictured them; a changed one judged, broken or not."""
    import shutil
    from orkcraft.gui import look_check
    from orkcraft.realm import call_log, check, tiers
    print("\nWindows look right · every building's window pictured…", flush=True)
    after = folder / "runs" / "looks" / "after"
    got = look_check.capture(after)
    if got["error"]:
        return [("windows", {"ok": True, "runs": 0, "why": f"not checked: {got['error']}"})]
    before = next((d / "runs" / "looks" / "after" for d in sorted((root / check.DIR).glob("2*"), reverse=True)
                   if d != folder and (d / "runs" / "looks" / "after").is_dir()), None)
    if before is None:
        return [("windows", {"ok": True, "runs": 1,
                             "why": f"{len(got['windows'])} windows pictured: the next check holds them against these"})]
    shares = look_check.compare(before, after)
    changed = {w: s for w, s in shares.items() if s > look_check.CHANGED}
    if not changed:
        return [("windows", {"ok": True, "runs": 1, "share": 0.0,
                             "why": f"{len(shares)} windows, none changed since {before.parent.parent.parent.name}"})]
    model = tiers.resolve(tool, tier) if tier else ""
    model = "" if model in tiers.TIERS else model
    out = []
    for window, share in changed.items():
        at = folder / "runs" / "looks" / window
        at.mkdir(parents=True, exist_ok=True)
        if (before / f"{window}.png").is_file():
            shutil.copy(before / f"{window}.png", at / "before.png")
        else:
            shutil.copy(after / f"{window}.png", at / "before.png")      # a new window: judged on itself
        shutil.copy(after / f"{window}.png", at / "after.png")
        verdict = {}
        with tempfile.TemporaryDirectory(prefix="orkcraft-look-") as tmp, call_log.kept(at / "calls_raw", "building"):
            for name in ("before.png", "after.png"):
                shutil.copy(at / name, Path(tmp) / name)
            try:
                text = _read(tool, look_check.judge_prompt(window), Path(tmp), model)
                m = re.search(r"\{.*\}", text or "", re.S)
                verdict = json.loads(m.group(0)) if m else {}
            except (RuntimeError, OSError, ValueError) as e:
                verdict = {"notes": f"the judge failed: {e}"[:200]}
        _export_calls(at / "calls_raw", at / "calls")
        (at / "judge.json").write_text(json.dumps(verdict, indent=2, ensure_ascii=False), encoding="utf-8")
        broken = bool(verdict.get("broken")) or (isinstance(verdict.get("score"), (int, float)) and verdict["score"] < 5)
        why = f"{share:.0%} of it changed; " + (f"broken: {verdict.get('notes', '')}" if broken else
                                                 f"reads well: {verdict.get('notes', '') or 'the judge saw nothing wrong'}")
        print(f"  {window}: {why[:160]}", flush=True)
        out.append((window, {"ok": not broken, "runs": 1, "share": share, "why": why[:300],
                             "score": verdict.get("score")}))
    return out
