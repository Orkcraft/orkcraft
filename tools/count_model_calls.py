"""Count the model calls a town makes on its own (docs/design/script-first.md §2).

    python tools/count_model_calls.py [--carts N] [--ticks N] [--dislike BUILDING] [--fail BUILDING]

Builds the dashboard demo in a temporary folder and opens it as a real town (not the sandbox: there no
model is ever called), with every model seam replaced by a counter — `builders.ask` (every `-p` call:
the steward, the retros, the keeper, the Council's Fast Path) and `roads.run_agent` (an agent handler,
a Mill's `agent:` step). Then it drops N pastes into the Gates' Pit, ticks the host N times (the roads,
the workers' own refreshes, the retros with their schedules due) and prints who called a model, how
often, from which function, for which building. Nothing leaves the machine.
"""
from __future__ import annotations

import argparse
import collections
import os
import sys
import tempfile
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SKIP = ("count_model_calls", "builders.py", "roads.py", "threading.py")


def _caller() -> str:
    """The first frame outside the seams: the function that wanted a model."""
    for f in reversed(traceback.extract_stack()[:-2]):
        name = Path(f.filename).name
        if not any(s in f.filename for s in SKIP) and "orkcraft" in f.filename:
            return f"{name}:{f.name}"
    return "?"


def _counted(calls: collections.Counter, name: str):
    def runner(prompt, model=None):
        calls[("runner", name)] += 1
        return '{"proposals": []}', 0.01
    return runner


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--carts", type=int, default=20)
    ap.add_argument("--ticks", type=int, default=120)
    ap.add_argument("--dislike", default="")
    ap.add_argument("--fail", default="", help="a building whose worker reports ERROR from the start")
    ap.add_argument("--goal", action="append", default=[], help="BUILDING=thrift|balance|quality")
    ap.add_argument("--keep", default="", help="build the demo here instead of a temporary folder")
    args = ap.parse_args(argv)

    tmp = Path(args.keep or tempfile.mkdtemp(prefix="orkcraft-count-"))
    os.environ.setdefault("ORKCRAFT_HOME", str(tmp / "home"))
    from orkcraft import demo
    from orkcraft.core import runners
    from orkcraft.realm import builders, fastpath, roads

    root = demo.build(tmp / "town", set_name="dashboard")

    calls: collections.Counter = collections.Counter()

    def ask(harness, prompt, model=None):
        calls[("ask", _caller())] += 1
        return '{"proposals": [{"type": "note", "text": "counted", "why": "counted"}]}', 0.01

    def run_agent(harness, prompt, repo_root, env, cancel, model=""):
        calls[("agent", env.get("ORKCRAFT_ORC") or _caller())] += 1
        return "counted", 0.01, 10

    builders.ask = ask
    roads.run_agent = run_agent
    for name in [n for n in dir(runners) if n.endswith("_RUNNER")]:
        setattr(runners, name, _counted(calls, name))
    fastpath.save_settings(root, {**fastpath.settings(root), "optimize_at": "* * * * *", "weekly_at": "* * * * *"})

    from orkcraft.realm import optimize
    picked: collections.Counter = collections.Counter()
    real_leader = optimize.leader

    def leader(*a, **k):
        c = real_leader(*a, **k)
        picked[c.building if c is not None else "(none)"] += 1
        return c
    optimize.leader = leader
    from orkcraft.gui.host import Host
    host = Host(root, auto_commit=False)
    host.town.roads._agent_runner = run_agent
    for pair in args.goal:
        bid, _, aim = pair.partition("=")
        host.town.scroll.building(bid).goal = aim
    host.town.call = lambda fn, *a, **k: fn(*a, **k)
    if args.fail:
        w = host.town.workers.get(args.fail) or host.town.worker(args.fail)
        w.status = lambda: "ERROR"
    if args.dislike:
        from orkcraft.core import buildings as core_buildings
        core_buildings.dislike(host.town, args.dislike, "logic", "counted")

    pit = host.town.worker("gate_pit")
    t0 = time.monotonic()
    for i in range(args.ticks):
        if i < args.carts:
            text = "release notes for v0.%d: faster carts" % i if i % 3 == 0 else '{"v": %d}' % i if i % 3 == 1 else f"paste {i}"
            pit.drop(text)
        host.tick(t0 + i * 61.0)           # a minute apart: the retros' checks and the refreshes come due
        time.sleep(0.01)
    time.sleep(1.0)
    host.close()

    total = sum(calls.values())
    print(f"{args.carts} carts into the Pit, {args.ticks} ticks a minute apart: {total} model calls")
    for (seam, who), n in calls.most_common():
        print(f"  {n:4d}  {seam:6s}  {who}")
    for bid, n in picked.most_common():
        print(f"  Building retro picked {bid}: {n}x")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
