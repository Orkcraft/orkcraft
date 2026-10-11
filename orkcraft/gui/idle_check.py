"""✅ How many model calls a town makes on its own (docs/design/script-first.md §2, docs/design/check.md): the
dashboard demo built in a temporary folder and opened as a real town (not the sandbox, where no model is ever
called), every model seam replaced by a counter, then ticked a minute a tick. Nothing leaves the machine and no
model runs. `orkcraft check` asks it of a quiet town; tools/count_model_calls.py also drops carts and 👎.

    idle_check.count(ticks=480)                       {"calls": n, "by": [[who, n], …], "picked": {…}}
"""
from __future__ import annotations

import collections
import contextlib
import os
import tempfile
import time
import traceback
from pathlib import Path

SKIP = ("idle_check", "count_model_calls", "builders.py", "roads.py", "threading.py")


def _caller() -> str:
    """The first frame outside the seams: the function that wanted a model."""
    for f in reversed(traceback.extract_stack()[:-2]):
        name = Path(f.filename).name
        if not any(s in f.filename for s in SKIP) and "orkcraft" in f.filename:
            return f"{name}:{f.name}"
    return "?"


@contextlib.contextmanager
def _patched(obj, name: str, value):
    old = getattr(obj, name)
    setattr(obj, name, value)
    try:
        yield
    finally:
        setattr(obj, name, old)


def count(ticks: int = 480, carts: int = 0, keep: Path | None = None, dislike: str = "", fail: str = "",
          goals: dict[str, str] | None = None, retros_every_minute: bool = False) -> dict:
    """Open the demo town, drop `carts` pastes into its Gates' Pit (one a tick, from the first), tick it `ticks`
    times a minute apart, and count who asked a model. `dislike`: a 👎 for that building first; `fail`: that
    building's worker says ERROR; `goals`: {building: thrift | balance | quality}; `retros_every_minute`: the
    proposal and the weekly retro due on every tick (to see what they cost), else on their own schedules."""
    tmp = keep or Path(tempfile.mkdtemp(prefix="orkcraft-idle-"))
    home = os.environ.get("ORKCRAFT_HOME")
    os.environ["ORKCRAFT_HOME"] = str(tmp / "home")         # the demo's logins and machine, never the person's
    calls: collections.Counter = collections.Counter()
    picked: collections.Counter = collections.Counter()
    try:
        from orkcraft import demo
        from orkcraft.core import runners
        from orkcraft.realm import builders, fastpath, optimize, roads
        root = demo.build(tmp / "town", set_name="dashboard")

        def ask(harness, prompt, model=None):
            calls[("ask", _caller())] += 1
            return '{"proposals": [{"type": "note", "text": "counted", "why": "counted"}]}', 0.01

        def run_agent(harness, prompt, repo_root, env, cancel, model="", *a, **k):
            calls[("agent", env.get("ORKCRAFT_ORC") or _caller())] += 1
            return "counted", 0.01, 10

        def counted(name: str):
            def runner(prompt, model=None, *a, **k):
                calls[("runner", name)] += 1
                return '{"proposals": []}', 0.01
            return runner

        real_leader = optimize.leader

        def leader(*a, **k):
            c = real_leader(*a, **k)
            picked[c.building if c is not None else "(none)"] += 1
            return c

        with contextlib.ExitStack() as stack:
            stack.enter_context(_patched(builders, "ask", ask))
            stack.enter_context(_patched(roads, "run_agent", run_agent))
            stack.enter_context(_patched(optimize, "leader", leader))
            for name in [n for n in dir(runners) if n.endswith("_RUNNER")]:
                stack.enter_context(_patched(runners, name, counted(name)))
            if retros_every_minute:
                fastpath.save_settings(root, {**fastpath.settings(root), "optimize_at": "* * * * *",
                                              "weekly_at": "* * * * *"})
            from orkcraft.gui.host import Host
            host = Host(root, auto_commit=False)
            try:
                host.town.roads._agent_runner = run_agent
                for bid, aim in (goals or {}).items():
                    host.town.scroll.building(bid).goal = aim
                host.town.call = lambda fn, *a, **k: fn(*a, **k)
                if fail:
                    w = host.town.workers.get(fail) or host.town.worker(fail)
                    w.status = lambda: "ERROR"
                if dislike:
                    from orkcraft.core import buildings as core_buildings
                    core_buildings.dislike(host.town, dislike, "logic", "counted")
                pit = host.town.worker("gate_pit")
                t0 = time.monotonic()
                for i in range(ticks):
                    if i < carts:
                        pit.drop("release notes for v0.%d: faster carts" % i if i % 3 == 0
                                 else '{"v": %d}' % i if i % 3 == 1 else f"paste {i}")
                    host.tick(t0 + i * 61.0)     # a minute apart: the retros' checks and the refreshes come due
                    time.sleep(0.005)
                time.sleep(1.0)
            finally:
                host.close()
    finally:
        if home is None:
            os.environ.pop("ORKCRAFT_HOME", None)
        else:
            os.environ["ORKCRAFT_HOME"] = home
    return {"calls": sum(calls.values()), "hours": round(ticks / 60, 1), "carts": carts,
            "by": [[f"{seam} · {who}", n] for (seam, who), n in calls.most_common()],
            "picked": dict(picked)}
